"""El gate de D-06 como par de funciones puras: corre sin Postgres.

Los planes y el set de tablas grandes van escritos a mano porque son la *entrada*
de la función —con RLS activo el planificador no elige un `Seq Scan` sobre
`transactions`—. El gate contra la base real está en `tests/test_ejecucion.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.db.gate import TECHO_DE_COSTO, revisar_forma, revisar_plan

GRANDES = {"transactions", "clients", "risk_assessments", "alerts"}


def nodo(tipo: str, costo: float, tabla: str | None = None, hijos=()) -> dict:
    """El costo de Postgres es acumulado: el de la raíz ya incluye a sus hijos."""
    n = {"Node Type": tipo, "Total Cost": costo, "Plans": list(hijos)}
    if tabla is not None:
        n["Relation Name"] = tabla
    return n


# ── Regla 1 · una sola sentencia, y `SELECT` ──────────────────────────────────

NO_SON_UNA_LECTURA = {
    "dos sentencias": "SELECT 1; SELECT 2",
    "lectura y escritura": "SELECT 1; DROP TABLE clients",
    "insert": "INSERT INTO clients (tenant_id) VALUES (3)",
    "update": "UPDATE clients SET deleted_at = now()",
    "delete": "DELETE FROM clients WHERE tenant_id = 3",
    "drop": "DROP TABLE transactions",
    "cte que escribe": (
        "WITH borrados AS (DELETE FROM clients RETURNING id) SELECT count(*) FROM borrados"
    ),
    "set de sesión colado adelante": "SET enable_indexscan = off; SELECT 1",
    "explain": "EXPLAIN SELECT 1",
}


@pytest.mark.parametrize("caso", list(NO_SON_UNA_LECTURA))
def test_lo_que_no_es_una_sola_lectura_se_rechaza_antes_de_tocar_la_base(caso):
    rechazo = revisar_forma(NO_SON_UNA_LECTURA[caso])

    assert rechazo is not None, f"«{caso}» pasó el gate de forma"


SON_LECTURAS = {
    "select pelado": "SELECT count(*) FROM clients",
    "with … select": "WITH vivos AS (SELECT id FROM clients) SELECT count(*) FROM vivos",
    "unión entre paréntesis": "(SELECT 1 AS n) UNION ALL (SELECT 2 AS n)",
    "con comentario adelante": "-- cuántos clientes\nSELECT count(*) FROM clients",
    "con punto y coma final": "SELECT count(*) FROM clients;",
}


@pytest.mark.parametrize("caso", list(SON_LECTURAS))
def test_una_lectura_pasa_el_gate_de_forma_aunque_no_empiece_con_la_palabra(caso):
    """`(SELECT …) UNION (SELECT …)` no empieza con una palabra, y ahí se escondía
    un crash del chequeo de la primera palabra."""
    assert revisar_forma(SON_LECTURAS[caso]) is None


def test_las_nueve_goldens_validadas_pasan_el_gate_de_forma():
    """Evita que la regla 1 se implemente demasiado ancha: ocho de las nueve
    goldens empiezan con `WITH … SELECT`, que es lo que más fácil se rompe."""
    semantics = Path(__file__).resolve().parents[1] / "core" / "semantics"
    goldens = {
        archivo.stem: yaml.safe_load(archivo.read_text(encoding="utf-8"))["golden_sql"]
        for archivo in sorted(semantics.glob("*.yaml"))
    }
    assert len(goldens) == 9, "cambió el set de skills; revisá qué se está afirmando"

    rechazadas = {
        concepto: revisar_forma(sql).motivo
        for concepto, sql in goldens.items()
        if revisar_forma(sql) is not None
    }

    assert rechazadas == {}, f"el gate rechazó goldens validadas: {rechazadas}"


# ── Regla 2 · ningún `Seq Scan` sobre una tabla grande ────────────────────────


def test_un_seq_scan_sobre_una_tabla_grande_se_rechaza():
    """El `Seq Scan` va anidado a propósito: mirar sólo la raíz dejaría pasar el
    caso real, donde el recorrido cuelga de un agregado."""
    plan = nodo(
        "Aggregate",
        1_500.0,
        hijos=[nodo("Seq Scan", 1_400.0, tabla="transactions")],
    )

    rechazo = revisar_plan(plan, GRANDES)

    assert rechazo is not None, "el plan recorre entera `transactions` y pasó"
    assert "transactions" in rechazo.motivo, (
        f"el rechazo no dice qué tabla se recorre entera: {rechazo.motivo!r}"
    )


def test_un_seq_scan_sobre_una_tabla_chica_se_acepta():
    """Para las cinco tablas sin índice por `tenant_id` el recorrido completo es
    el único plan posible y cuesta 55-170 ms (D-06)."""
    plan = nodo(
        "Aggregate",
        180.0,
        hijos=[nodo("Seq Scan", 170.0, tabla="tenant_config")],
    )

    assert revisar_plan(plan, GRANDES) is None, (
        "`tenant_config` no está entre las grandes: recorrerla entera es legítimo"
    )


# ── Regla 3 · el costo por debajo del techo medido ────────────────────────────


def test_un_plan_por_indice_pero_carisimo_se_rechaza_igual():
    """Un plan sin un solo `Seq Scan` puede morir por timeout si un CTE inlineado
    se recalcula por fila (`NOTES/01-limites-y-planes.md` §3)."""
    plan = nodo(
        "Aggregate",
        TECHO_DE_COSTO * 2,
        hijos=[nodo("Index Scan", TECHO_DE_COSTO * 2 - 10, tabla="transactions")],
    )

    rechazo = revisar_plan(plan, GRANDES)

    assert rechazo is not None, (
        f"un plan por índice de costo {TECHO_DE_COSTO * 2:,.0f} pasó el techo "
        f"de {TECHO_DE_COSTO:,.0f}"
    )


def test_un_plan_por_indice_por_debajo_del_techo_se_acepta():
    """El otro lado del corte: sin esto el techo podría estar en cero."""
    plan = nodo(
        "Aggregate",
        TECHO_DE_COSTO - 1,
        hijos=[nodo("Index Scan", TECHO_DE_COSTO - 10, tabla="transactions")],
    )

    assert revisar_plan(plan, GRANDES) is None


def test_el_techo_sigue_rechazando_la_consulta_que_muere_por_timeout_de_verdad():
    """El número es medido: es el costo del plan de `CONSULTA_DESBOCADA` de
    `tests/test_limites.py`, la única consulta del repo que sabemos que muere por
    timeout. Si el dump cambia y baja del techo, hay que volver a medir."""
    desbocada_que_muere_por_timeout = 32_711_505.57

    assert revisar_plan(nodo("Aggregate", desbocada_que_muere_por_timeout), GRANDES)


# ── Todo rechazo trae una sugerencia accionable ───────────────────────────────

RECHAZOS = {
    "no es una lectura": revisar_forma("DROP TABLE clients"),
    "dos sentencias": revisar_forma("SELECT 1; SELECT 2"),
    "escribe adentro de un CTE": revisar_forma(
        "WITH b AS (DELETE FROM clients RETURNING id) SELECT count(*) FROM b"
    ),
    "seq scan sobre tabla grande": revisar_plan(
        nodo("Aggregate", 1_500.0, hijos=[nodo("Seq Scan", 1_400.0, tabla="alerts")]),
        GRANDES,
    ),
    "costo por encima del techo": revisar_plan(
        nodo("Aggregate", TECHO_DE_COSTO * 5), GRANDES
    ),
}


@pytest.mark.parametrize("caso", list(RECHAZOS))
def test_todo_rechazo_trae_una_sugerencia_accionable_para_un_agente(caso):
    """El acento grave marca lo accionable —una construcción de SQL, un parámetro,
    una tool— y no es el change detector que prohíbe `plan/testing.md`: esas
    sugerencias son constantes nuestras en `core/db/gate.py`, no texto del modelo."""
    rechazo = RECHAZOS[caso]

    assert rechazo is not None, f"«{caso}» no rechazó nada"
    assert rechazo.sugerencia.strip(), f"«{caso}» rechazó sin sugerencia"
    assert rechazo.sugerencia != rechazo.motivo, (
        f"«{caso}»: la sugerencia repite el motivo en vez de decir qué hacer"
    )
    assert "`" in rechazo.sugerencia, (
        f"«{caso}»: la sugerencia no nombra nada accionable, sólo describe el "
        f"problema: {rechazo.sugerencia!r}"
    )
