"""El seam por el que el sistema ejecuta SQL, con el gate de punta a punta contra
la base real. Las reglas del gate como función pura están en `test_gate.py`.

Nunca se afirma el texto de un error de Postgres: el wording se traduce con la
locale del servidor, el SQLSTATE no (`NOTES/01-limites-y-planes.md` §1).
"""

from __future__ import annotations

import pytest

from conftest import conectar_como_admin
from core.db.ejecucion import (
    Fallo,
    Ok,
    Rechazada,
    ejecutar,
    tablas_grandes_del_catalogo,
)
from core.db.gate import PALABRAS_QUE_NO_SON_LECTURA


def test_una_consulta_legitima_vuelve_como_ok_con_filas_columnas_plan_y_ms(tenant_a):
    resultado = ejecutar(
        "SELECT count(*) AS clientes FROM clients WHERE deleted_at IS NULL",
        {},
        tenant_a,
    )

    assert isinstance(resultado, Ok), f"la consulta no se ejecutó: {resultado}"
    assert resultado.columnas == ["clientes"]
    assert resultado.filas[0][0] > 0, "la institución de prueba no tiene clientes vivos"
    assert "Node Type" in resultado.plan, "el plan no es el nodo raíz del EXPLAIN"
    assert 0 < resultado.ms < 15_000


def test_la_institucion_la_pone_el_seam_y_el_llamador_no_la_puede_pisar(
    tenant_a, tenant_b
):
    """Se pasa la institución equivocada como parámetro a propósito: si el seam lo
    respetara el conteo daría cero, porque RLS ya scopeó la conexión a A."""
    con_el_parametro_ajeno = ejecutar(
        "SELECT count(*) AS n FROM clients "
        "WHERE tenant_id = %(tenant)s AND deleted_at IS NULL",
        {"tenant": tenant_b},
        tenant_a,
    )
    sin_filtro_propio = ejecutar(
        "SELECT count(*) AS n FROM clients WHERE deleted_at IS NULL", {}, tenant_a
    )

    assert isinstance(con_el_parametro_ajeno, Ok), con_el_parametro_ajeno
    assert con_el_parametro_ajeno.filas[0][0] > 0
    assert con_el_parametro_ajeno.filas[0][0] == sin_filtro_propio.filas[0][0]


def test_recorrer_entera_una_tabla_grande_se_rechaza_y_las_grandes_salen_del_catalogo(
    tenant_a, tablas_grandes
):
    """`audit_log` es de las pocas tablas grandes que la policy de RLS no salva: sin
    índice por `tenant_id`, un `count(*)` la recorre entera. Es el caso real que
    D-06 existe para frenar."""
    assert "audit_log" in tablas_grandes, "el catálogo no reconoció la tabla grande"
    assert tablas_grandes_del_catalogo() == tablas_grandes

    resultado = ejecutar("SELECT count(*) FROM audit_log", {}, tenant_a)

    assert isinstance(resultado, Rechazada), (
        f"el plan recorre entera `audit_log` y el gate lo dejó pasar: {resultado}"
    )
    assert "audit_log" in resultado.motivo
    assert resultado.sugerencia.strip(), "un rechazo sin sugerencia no sirve de nada"


def test_recorrer_entera_una_tabla_chica_se_acepta(tenant_a, tablas_chicas):
    """`client_risk_overrides` es una de las cinco sin índice por `tenant_id`: el
    recorrido completo es el único plan posible y cuesta lo que D-06 dice."""
    assert "client_risk_overrides" in tablas_chicas

    resultado = ejecutar("SELECT count(*) FROM client_risk_overrides", {}, tenant_a)

    assert isinstance(resultado, Ok), (
        f"un Seq Scan sobre una tabla chica es el único plan posible: {resultado}"
    )


def test_lo_que_no_es_una_lectura_se_rechaza_y_no_llega_a_la_base(tenant_a):
    """`Fallo` significaría que Postgres lo vio y lo negó; `Rechazada`, que el seam
    lo frenó antes de abrir la conexión."""
    resultado = ejecutar("DROP TABLE clients", {}, tenant_a)

    assert isinstance(resultado, Rechazada), (
        f"un DROP tiene que frenarse antes de tocar la base: {resultado}"
    )

    assert isinstance(ejecutar("SELECT count(*) FROM clients", {}, tenant_a), Ok)


def test_ninguna_tabla_ni_columna_del_esquema_choca_con_las_palabras_prohibidas(
    bootstrap_aplicado,
):
    """El precio de chequear palabras sueltas sobre el texto del SQL: una columna
    llamada `comment` haría rechazar una consulta legítima. Hoy no hay ninguna, y
    esto avisa ruidosamente si el dump trae una."""
    with conectar_como_admin() as conn:
        identificadores = {
            nombre
            for (nombre,) in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "UNION SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        }

    chocan = sorted(
        nombre
        for nombre in identificadores
        if nombre.upper() in PALABRAS_QUE_NO_SON_LECTURA
    )

    assert chocan == [], (
        f"el esquema tiene identificadores que el gate de forma confunde con "
        f"una escritura: {chocan}. O se citan en las consultas, o salen de la "
        f"lista de `core/db/gate.py`"
    )


CLASES_POR_SQLSTATE = {
    "SINTAXIS": "SELECT count(*) FRM clients",  # 42601
    "PERMISO": "SELECT count(*) FROM pg_authid",  # 42501
    "OTRO": "SELECT count(*) FROM la_tabla_que_el_agente_invento",  # 42P01
}


@pytest.mark.parametrize("clase", list(CLASES_POR_SQLSTATE))
def test_los_errores_de_postgres_vuelven_normalizados_por_clase(clase, tenant_a):
    """Cada clase es un reintento distinto: la primera se corrige, la segunda no se
    reintenta, y la tercera —el agente inventó una tabla, que es lo que más le
    pasa— cae en `OTRO` porque una clase por SQLSTATE sería un vocabulario que no
    sabe usar."""
    resultado = ejecutar(CLASES_POR_SQLSTATE[clase], {}, tenant_a)

    assert isinstance(resultado, Fallo), f"esperaba un Fallo y volvió {resultado}"
    assert resultado.clase == clase
    assert resultado.detalle, "el fallo no dice nada de qué pasó"


@pytest.mark.lento
def test_una_consulta_que_se_pasa_del_timeout_vuelve_como_fallo_de_clase_timeout(
    tenant_a,
):
    """Tarda 15 segundos a propósito. `pg_sleep` es la única forma de llegar acá con
    el gate puesto: una consulta cara de verdad ya se rechaza por costo."""
    resultado = ejecutar("SELECT pg_sleep(20)", {}, tenant_a)

    assert isinstance(resultado, Fallo), f"el timeout se escapó como {resultado}"
    assert resultado.clase == "TIMEOUT"
