"""Los cinco criterios con los que H2 validó las nueve skills de `core/semantics/`.

Portado de `scripts/validar_semantica.py`, que sigue existiendo por lo que un
test no da: la cascada de cada skill con sus números, legible.
"""

from __future__ import annotations

import pytest

from conftest import conectar_como_admin
from core.db import agent_connection
from criterios_semanticos import (
    cargar_skills,
    parametros,
    seq_scans_prohibidos,
    soft_delete_sin_filtrar,
    tablas_borrables,
)

SKILLS = cargar_skills()
IDS = [skill["concepto"] for skill in SKILLS]

# `parametrize` sobre una lista vacía no falla: no colecta nada y da verde sin
# afirmar nada. Si un día ninguna skill trae desglose, esto lo dice en voz alta.
CON_DESGLOSE = [s for s in SKILLS if s.get("desglose_sql")] or [
    pytest.param(None, id="ninguna-skill-trae-desglose")
]


@pytest.fixture(params=["tenant_a", "tenant_b"])
def institucion(request) -> int:
    """Contrastan por el criterio de `Q_FIXTURE`: umbral versionado contra umbral
    único, SLA de 24 h contra 72 h, las dos perillas prendidas contra las dos
    apagadas."""
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="session")
def tablas_con_deleted_at(bootstrap_aplicado) -> set[str]:
    """Las tablas con `deleted_at`, por catálogo y no escritas a mano."""
    with conectar_como_admin() as conn:
        return tablas_borrables(conn)


def test_las_goldens_se_validan_como_el_agente_y_no_como_administrador(
    institucion, bootstrap_aplicado
):
    """Una golden que anduviera como `postgres` y muriera bajo RLS no sirve de
    nada. Acá se comprueba que el `statement_timeout` está puesto; que muerde lo
    afirma el servidor cancelando la consulta, y lo mide `test_limites.py`."""
    with agent_connection(institucion) as conn:
        rol, timeout = conn.execute(
            "SELECT current_user, current_setting('statement_timeout')"
        ).fetchone()

    assert rol == "agent_ro", f"las goldens se están validando como {rol}"
    assert timeout not in ("0", "0ms"), "el rol corre sin statement_timeout"


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_la_golden_devuelve_su_cascada_por_indice_y_verificada(
    skill, institucion, tablas_grandes, bootstrap_aplicado
):
    """Las cuatro afirmaciones van juntas porque son cuatro observaciones de una
    sola corrida: separarlas costaría cuatro ejecuciones de cada golden en cada
    institución sin afirmar nada nuevo."""
    params = parametros(institucion, skill)
    esperadas = [d["escalon"] for d in skill["derivacion"]] + [
        m["nombre"] for m in skill.get("metricas", [])
    ]

    with agent_connection(institucion) as conn:
        cur = conn.execute(skill["golden_sql"], params)
        filas = cur.fetchall()
        columnas = [c.name for c in cur.description]
        scans = seq_scans_prohibidos(conn, skill["golden_sql"], params, tablas_grandes)
        segundo_camino = conn.execute(skill["verificacion_sql"], params).fetchone()[0]

    assert len(filas) == 1, f"la golden devolvió {len(filas)} filas y tiene que ser 1"
    assert columnas == esperadas, "las columnas no son las de derivacion + metricas"
    assert scans == [], f"Seq Scan sobre tabla grande: {sorted(set(scans))}"
    assert dict(zip(columnas, filas[0]))[skill["resultado"]] == segundo_camino


@pytest.mark.parametrize("skill", SKILLS, ids=IDS)
def test_toda_tabla_con_deleted_at_del_join_lleva_su_filtro(skill, tablas_con_deleted_at):
    """La trampa deja entrar 103.146 evaluaciones de riesgo vivas de clientes
    borrados. Se lee del SQL, así que no se corre por institución."""
    for campo in ("golden_sql", "desglose_sql", "verificacion_sql"):
        if campo in skill:
            faltan = soft_delete_sin_filtrar(skill[campo], tablas_con_deleted_at)
            assert faltan == [], f"{campo}: sin filtro de borrado en {', '.join(faltan)}"


@pytest.mark.parametrize("skill", CON_DESGLOSE, ids=lambda s: s and s["concepto"])
def test_el_desglose_corre_bajo_el_mismo_presupuesto_que_la_golden(
    skill, institucion, bootstrap_aplicado
):
    """Regresión con nombre: sin `AS MATERIALIZED` el desglose de `monto_transado`
    moría por `statement_timeout` en la institución chica, porque Postgres
    inlineaba el CTE del screening vigente y lo recalculaba una vez por fila."""
    assert skill is not None, "ninguna skill trae desglose: el test no afirma nada"

    with agent_connection(institucion) as conn:
        cur = conn.execute(skill["desglose_sql"], parametros(institucion, skill))
        filas = cur.fetchall()

    assert filas, "el desglose no devolvió ninguna fila"
