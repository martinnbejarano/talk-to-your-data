"""Las cinco tools del agente, contra la base real.

Ninguno llama al modelo: lo que se afirma es lo que devuelven las tools, que es
determinístico. Si el agente las usa bien lo mide el eval de H4 (D-11).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agent import loop, tools
from agent.tools import (
    SEMANTICS,
    describe_table,
    escalones_de,
    get_definition,
    list_tables,
    run_sql,
    sample_values,
    texto_para_el_modelo,
)
from core.db.ejecucion import Ok, Rechazada

# Leídos del directorio y no escritos acá: una skill nueva entra a esta suite por
# existir. Leer nombres de archivo al colectar no toca la base.
CONCEPTOS = sorted(archivo.stem for archivo in SEMANTICS.glob("*.yaml"))


@pytest.fixture(params=["tenant_a", "tenant_b"])
def institucion(request) -> int:
    """Contrastan por construcción (`tests/criterio_fixture.py`): umbral versionado
    contra umbral único, las dos perillas prendidas contra las dos apagadas."""
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("modulo", [tools, loop])
def test_el_agente_nunca_ve_psycopg(modulo):
    """`core/db/ejecucion.py` es la única costura contra la base y es donde vive el
    `SET LOCAL app.tenant_id`; una tool con su propia conexión sería una segunda.
    Se miran los imports y no el texto: la palabra aparece en los comentarios."""
    arbol = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
    importados = {
        (alias.name if isinstance(nodo, ast.Import) else nodo.module or "").split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.Import, ast.ImportFrom))
        for alias in nodo.names
    }

    assert "psycopg" not in importados, (
        f"{modulo.__name__} habla psycopg: toda consulta tiene que pasar por "
        f"`core.db.ejecucion.ejecutar`"
    )


def test_list_tables_dice_cual_es_grande_y_cual_se_filtra(institucion, tablas_grandes):
    """El agente necesita saber cuál es "grande" antes de que el gate se lo diga:
    un rechazo cuesta el 70 % de una pregunta entera en tokens."""
    listado = list_tables(institucion)

    for grande in tablas_grandes:
        assert f"{grande} · " in listado, f"`{grande}` no aparece en el listado"
    assert listado.count("GRANDE") == len(tablas_grandes)

    de_clients = next(l for l in listado.splitlines() if l.startswith("clients · "))
    assert "GRANDE" in de_clients and "tenant_id, deleted_at" in de_clients


def test_describe_table_trae_los_indices_que_pide_d06(institucion):
    """Se afirma sobre el índice **parcial** de `clients`, el que hace barata la
    consulta de riesgo alto: un índice parcial cuyo `WHERE` no llega es un índice
    que el agente no usa."""
    ficha = describe_table(institucion, "clients")

    assert "onboarding_status" in ficha and "boolean" in ficha
    assert "idx_clients_tenant_active" in ficha
    assert "WHERE (deleted_at IS NULL)" in ficha, "el índice parcial perdió su condición"


@pytest.mark.parametrize(
    "tabla, columna, valor",
    [
        ("screenings", "result", "CONFIRMED_HIT"),  # grande, y el enum de la trampa de PEP
        ("clients", "onboarding_status", "APPROVED"),  # grande
        ("countries", "code", "AR"),  # de catálogo: ni `tenant_id` ni RLS
    ],
)
def test_sample_values_trae_los_valores_que_el_esquema_no_declara(
    tabla, columna, valor, institucion
):
    """Los siete enums sin `CHECK` que encontró H1 no están en el esquema. Las dos
    tablas grandes obligan a la tool a pasar el gate; la de catálogo, que no tiene
    `tenant_id`, ejerce el otro extremo: un `WHERE tenant_id = ...` la rompería."""
    valores = sample_values(institucion, tabla, columna)

    assert valor in valores, f"`{valor}` no está entre los valores de {tabla}.{columna}"
    assert "RECHAZADA" not in valores and "FALLO" not in valores


@pytest.mark.parametrize("concepto", CONCEPTOS)
def test_las_nueve_definiciones_se_cargan_con_sus_escalones_y_su_referencia(
    concepto, institucion
):
    """Si una skill nueva llegara sin `derivacion`, el loop no tendría qué reclamar
    y la cascada volvería a quedar a criterio del modelo (`NOTES/03-prototipo.md`
    §5.2)."""
    definicion = get_definition(institucion, concepto)
    escalones = escalones_de(concepto)

    assert escalones, f"`{concepto}` no declara escalones"
    for escalon in escalones:
        assert f"`{escalon}`" in definicion
    assert "TIENE que devolver" in definicion, "los escalones no se piden como obligación"
    assert "```sql" in definicion, "la definición no trae la consulta de referencia"


def test_la_definicion_trae_la_perilla_vigente_de_cada_institucion(tenant_a, tenant_b):
    """El umbral está versionado y la versión vieja infla el número 9,6 veces. La
    fecha y el origen van porque el validador de trazabilidad no verifica fechas:
    si el modelo las inventara, no las atraparía nadie."""
    de_a = get_definition(tenant_a, "riesgo_alto")
    de_b = get_definition(tenant_b, "riesgo_alto")

    def perilla(definicion: str, clave: str) -> str:
        """El renglón que la tool escribió para una perilla, sin el de la golden."""
        return next(l for l in definicion.splitlines() if l.startswith("- `") and clave in l)

    umbral_de_a = perilla(de_a, "high_risk_score_threshold")

    assert "85" in umbral_de_a, "el umbral de A no es el vigente"
    assert "68" in perilla(de_b, "high_risk_score_threshold"), "el umbral de B no es el suyo"
    assert "2026-02-01" in umbral_de_a, "el umbral vino sin decir desde cuándo rige"
    assert "tenant_config" in umbral_de_a, "el umbral vino sin decir de dónde salió"
    assert "true" in perilla(de_a, "pep_is_high_risk")
    assert "false" in perilla(de_b, "pep_is_high_risk")


def test_un_rechazo_del_gate_le_llega_al_modelo_con_su_sugerencia_y_sus_columnas(
    institucion,
):
    """`audit_log` no tiene índice por `tenant_id`: contarla entera es el caso real
    que D-06 frena. El recordatorio de conservar columnas va porque obedecer una
    sugerencia de costo a secas fusionó `total` con `activos` y la derivación
    perdió la resta que el oficial tiene que ver (`NOTES/03-prototipo.md` §5.3)."""
    rechazo = run_sql(institucion, "SELECT count(*) FROM audit_log")

    assert isinstance(rechazo, Rechazada), f"el gate dejó pasar el recorrido entero: {rechazo}"
    texto = texto_para_el_modelo(rechazo)
    assert rechazo.sugerencia in texto
    assert "seguí devolviendo las mismas columnas" in texto


def test_el_periodo_lo_resuelve_el_sistema_y_uno_que_no_conoce_no_se_traga(institucion):
    """El desconocido corta ruidosamente porque mal resuelto no rompe nada visible:
    devuelve un número plausible sobre otra ventana de tiempo."""
    del_periodo = run_sql(
        institucion,
        "SELECT count(*) AS n FROM clients "
        "WHERE onboarded_at >= %(desde)s AND onboarded_at < %(hasta)s",
        periodo="este año",
    )

    assert isinstance(del_periodo, Ok), del_periodo
    with pytest.raises(ValueError):
        run_sql(institucion, "SELECT 1 AS n", periodo="el año que viene")
