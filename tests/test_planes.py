"""La pregunta abierta del hito: ¿RLS rompe el uso de índices?

Si RLS degradara los planes, el agente de H3 chocaría contra el timeout en cada
pregunta. La medición comparativa —con RLS contra el mismo SQL con el rol
administrador— está en NOTES/01-limites-y-planes.md, y es cómo se eligieron
estas tres consultas; lo que se versiona es el test y no un `EXPLAIN` pegado en
un documento, que envejece en silencio.

Las consultas van sin filtro de institución a propósito: el único predicado por
`tenant_id` del plan es el que pone la policy, que es el caso que se da cuando
el agente se olvida del filtro.

`EXPLAIN` sin `ANALYZE`: se afirma el plan, no el tiempo.
"""

from __future__ import annotations

import pytest

from core.db import agent_connection

# Cuáles son las tablas grandes (`reltuples >= 100k`, el corte de D-06) lo
# resuelve la fixture de sesión `tablas_grandes`, en `tests/conftest.py`. Acá no
# se conecta al importar: colectar la suite no tiene que exigir Postgres.

# Tres preguntas típicas de un oficial de compliance. Entre las tres tocan cinco
# de las nueve tablas grandes.
CONSULTAS_TIPICAS = {
    "clientes de riesgo alto": """
        SELECT count(*)
        FROM clients c
        JOIN risk_assessments r ON r.client_id = c.id AND r.tenant_id = c.tenant_id
        WHERE r.is_current AND r.deleted_at IS NULL AND r.score >= 80
          AND c.deleted_at IS NULL
    """,
    "transacciones del trimestre": """
        SELECT count(*), sum(amount)
        FROM transactions
        WHERE tx_date >= DATE '2026-01-01' AND tx_date < DATE '2026-04-01'
          AND deleted_at IS NULL AND status = 'SETTLED'
    """,
    "alertas del trimestre por estado": """
        SELECT status, count(*)
        FROM alerts
        WHERE triggered_at >= TIMESTAMPTZ '2026-01-01'
          AND triggered_at < TIMESTAMPTZ '2026-04-01'
          AND deleted_at IS NULL
        GROUP BY status
    """,
}


def nodos_del_plan(conn, consulta) -> list[dict]:
    """Todos los nodos del plan, aplanados. `EXPLAIN`, nunca `ANALYZE`."""
    (explicacion,) = conn.execute("EXPLAIN (FORMAT JSON) " + consulta).fetchone()
    raiz = explicacion[0]["Plan"]

    def recorrer(nodo):
        yield nodo
        for hijo in nodo.get("Plans", []):
            yield from recorrer(hijo)

    return list(recorrer(raiz))


@pytest.mark.parametrize("pregunta", list(CONSULTAS_TIPICAS))
def test_con_rls_activo_ninguna_consulta_tipica_recorre_entera_una_tabla_grande(
    pregunta, tenant_a, tablas_grandes
):
    """El test que puede tumbar el hito, y hoy no lo tumba.

    Falla si la policy deja de ser sargable, o si un cambio de esquema rompe la
    composición con los índices que tienen `tenant_id` como primera columna.
    """
    assert "transactions" in tablas_grandes, "el catálogo no reconoció la tabla grande"

    with agent_connection(tenant_a) as conn:
        nodos = nodos_del_plan(conn, CONSULTAS_TIPICAS[pregunta])

    recorridas_enteras = [
        nodo["Relation Name"]
        for nodo in nodos
        if "Seq Scan" in nodo["Node Type"]
        and nodo.get("Relation Name") in tablas_grandes
    ]
    assert recorridas_enteras == [], (
        f"«{pregunta}»: con RLS activo el plan recorre entera(s) "
        f"{recorridas_enteras}. Si esto salta, hay que medir con y sin RLS "
        f"antes de tocar nada: puede ser la policy que dejó de componer con el "
        f"índice, o la consulta que cambió."
    )


def test_el_predicado_de_la_policy_entra_al_indice_y_no_al_filtro(tenant_a):
    """Por qué los planes siguen siendo buenos, dicho como afirmación.

    `current_setting` es `STABLE`, así que el planificador la resuelve una vez y
    usa el resultado como condición de índice.

    Va separado del test de arriba porque el de arriba, solo, se puede engañar:
    con un predicado no sargable el plan puede seguir usando un índice por las
    *otras* columnas y esconder la degradación.
    """
    with agent_connection(tenant_a) as conn:
        nodos = nodos_del_plan(conn, CONSULTAS_TIPICAS["transacciones del trimestre"])

    en_condicion_de_indice = any(
        "app.tenant_id" in nodo.get("Index Cond", "") for nodo in nodos
    )
    en_filtro_fila_por_fila = [
        nodo["Node Type"] for nodo in nodos if "app.tenant_id" in nodo.get("Filter", "")
    ]

    assert en_condicion_de_indice, (
        "el predicado de la policy no llegó a ninguna condición de índice: "
        "dejó de ser sargable. Nodos de acceso: "
        + str([nodo["Node Type"] for nodo in nodos if "Scan" in nodo["Node Type"]])
    )
    assert en_filtro_fila_por_fila == [], (
        "el predicado de la policy se evalúa fila por fila en "
        f"{en_filtro_fila_por_fila} en vez de entrar al índice"
    )
