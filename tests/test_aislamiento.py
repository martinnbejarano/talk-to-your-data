"""El entregable real del hito: el agente no puede cruzar instituciones.

Todo se verifica a través de `core.db.agent_connection`, que es por donde va a
pasar el agente de verdad; testear el SQL del bootstrap por otro camino diría
algo del script y nada del producto.

Las consultas van a propósito sin un solo `WHERE tenant_id = ...`: la garantía
que se afirma es justamente que el filtro no hace falta.
"""

from __future__ import annotations

import pytest

from core.db import agent_connection
from conftest import conectar_como_admin

# Los conjuntos que salen del catálogo —las tablas con `tenant_id`, las mixtas,
# las chicas y los catálogos— los resuelve `tests/conftest.py`: como fixtures de
# sesión cuando el test los recorre, y como parametrización cuando el test es uno
# por tabla. Acá no se conecta al importar, para que colectar la suite no exija
# tener Postgres levantado.


def test_sin_institucion_declarada_no_se_ve_ninguna_fila_de_ninguna_institucion(
    tabla_con_tenant, admite_globales, bootstrap_aplicado
):
    """Fail-closed: sin `app.tenant_id`, cero filas de cualquier institución.

    Las tablas con `tenant_id` NOT NULL devuelven cero filas, punto. Las mixtas
    siguen mostrando sus filas globales, que son de referencia, pero ni una que
    pertenezca a una institución.
    """
    with agent_connection() as conn:
        de_alguna_institucion = conn.execute(
            f'SELECT count(*) FROM public."{tabla_con_tenant}" WHERE tenant_id IS NOT NULL'
        ).fetchone()[0]
        total = conn.execute(
            f'SELECT count(*) FROM public."{tabla_con_tenant}"'
        ).fetchone()[0]

    assert de_alguna_institucion == 0, (
        f"{tabla_con_tenant}: sin institución declarada se vieron "
        f"{de_alguna_institucion} filas que pertenecen a alguna institución"
    )
    if not admite_globales:
        assert total == 0, (
            f"{tabla_con_tenant}: sin institución declarada se vieron {total} filas"
        )


def test_con_la_institucion_declarada_solo_se_ven_filas_de_esa_institucion(
    tenant_a, tenant_b, tablas_chicas
):
    """Scoping: declarada A se ve exactamente A; declarada B, exactamente B."""
    assert tenant_a != tenant_b
    assert tablas_chicas, (
        "el catálogo no devolvió ninguna tabla chica con `tenant_id`: el test "
        "no estaría afirmando nada. Revisá el corte de `reltuples` contra el "
        "dump — o corré un ANALYZE, que es de donde sale la estimación."
    )

    with agent_connection(tenant_a) as conn:
        vistas_por_a = {
            tabla: {fila[0] for fila in conn.execute(f"SELECT DISTINCT tenant_id FROM {tabla}")}
            for tabla in tablas_chicas
        }

    with agent_connection(tenant_b) as conn:
        vistas_por_b = {
            tabla: {fila[0] for fila in conn.execute(f"SELECT DISTINCT tenant_id FROM {tabla}")}
            for tabla in tablas_chicas
        }

    for tabla in tablas_chicas:
        assert vistas_por_a[tabla] == {tenant_a}, f"{tabla}: {vistas_por_a[tabla]}"
        assert vistas_por_b[tabla] == {tenant_b}, f"{tabla}: {vistas_por_b[tabla]}"


def test_una_tabla_mixta_sin_institucion_declarada_muestra_sus_filas_globales(
    tabla_mixta_o_aviso, bootstrap_aplicado
):
    """El contrapeso del fail-closed sobre las tablas mixtas.

    La mitad severa que afirma el test de arriba la cumpliría también una policy
    estricta que escondiera *todo*, y ahí se perderían las 11 listas PEP
    compartidas: la base quedaría protegida y a la vez inútil.

    Se compara contra el conteo del administrador y no contra "más de cero":
    una policy que dejara pasar la mitad también tiene que romper esto.
    """
    if tabla_mixta_o_aviso is None:
        pytest.fail(
            "Este dump no tiene ninguna tabla con `tenant_id` nullable, así que "
            "el régimen de tablas mixtas no lo está ejerciendo nadie. "
            "Si la tercera clase de tabla desapareció de verdad, se saca la "
            "rama del bootstrap; hasta entonces esto es un agujero.",
            pytrace=False,
        )

    with conectar_como_admin() as adm:
        globales = adm.execute(
            f'SELECT count(*) FROM public."{tabla_mixta_o_aviso}" WHERE tenant_id IS NULL'
        ).fetchone()[0]
    assert globales > 0, (
        f"{tabla_mixta_o_aviso} no tiene filas globales en este dump: el test "
        f"no afirmaría nada"
    )

    with agent_connection() as conn:
        visibles = conn.execute(
            f'SELECT count(*) FROM public."{tabla_mixta_o_aviso}"'
        ).fetchone()[0]

    assert visibles == globales, (
        f"{tabla_mixta_o_aviso}: sin institución declarada se vieron {visibles} "
        f"filas y las "
        f"globales son {globales}. Las de referencia se leen siempre y las de "
        f"una institución no se ven nunca; acá se rompió una de las dos"
    )


def test_una_tabla_mixta_muestra_lo_global_y_esconde_lo_ajeno(tabla_mixta, tenant_a):
    """El caso de `watchlists`: filas globales de referencia + filas de institución.

    La spec daba estas tablas por catálogo sin `tenant_id`; contra la data tienen
    un `tenant_id` nullable y las dos salidas simples fallan — sin RLS se filtran
    las listas internas de la competencia, con la policy estricta desaparecen las
    públicas (ver NOTES/00-restore-y-humo.md).

    Se descubren por `is_nullable`, no por nombre.
    """
    with conectar_como_admin() as adm:
        globales, ajenas = adm.execute(
            f"SELECT count(*) FILTER (WHERE tenant_id IS NULL),"
            f"       count(*) FILTER (WHERE tenant_id IS NOT NULL AND tenant_id <> %s)"
            f' FROM public."{tabla_mixta}"',
            [tenant_a],
        ).fetchone()
    assert globales > 0 and ajenas > 0, (
        f"{tabla_mixta} dejó de ser mixta en este dump: el test no estaría "
        f"afirmando nada"
    )

    with agent_connection(tenant_a) as conn:
        vistos = {
            fila[0]
            for fila in conn.execute(
                f'SELECT DISTINCT tenant_id FROM public."{tabla_mixta}"'
            )
        }
        cuantas_globales = conn.execute(
            f'SELECT count(*) FROM public."{tabla_mixta}" WHERE tenant_id IS NULL'
        ).fetchone()[0]

    assert vistos <= {None, tenant_a}, (
        f"{tabla_mixta}: se vieron instituciones ajenas {vistos}"
    )
    assert cuantas_globales == globales, (
        f"{tabla_mixta}: las filas globales son de referencia y tienen que seguir "
        f"siendo legibles ({cuantas_globales} de {globales})"
    )


def test_con_la_institucion_declarada_tenants_devuelve_una_sola_fila(tenant_a):
    """El agente ve su institución, no la lista de competidores.

    Sin esta policy un oficial no accedería a los datos ajenos, pero sí a la
    lista de quiénes son sus competidores con sus nombres legales.
    """
    with conectar_como_admin() as adm:
        cuantas_hay = adm.execute("SELECT count(*) FROM public.tenants").fetchone()[0]
    assert cuantas_hay > 1, (
        "Hay una sola institución en el dump: este test no estaría afirmando nada"
    )

    with agent_connection(tenant_a) as conn:
        visibles = conn.execute("SELECT id FROM public.tenants").fetchall()

    assert visibles == [(tenant_a,)], (
        f"con la institución {tenant_a} declarada se vieron {len(visibles)} "
        f"instituciones de las {cuantas_hay} que hay: {visibles}"
    )


def test_los_catalogos_se_leen_sin_institucion_declarada(catalogo, bootstrap_aplicado):
    """El contrapeso del fail-closed: la protección no vuelve inútil la base.

    Los catálogos quedan sin RLS a propósito y el agente los necesita para
    resolver códigos. Se compara contra el conteo del administrador y no contra
    "más de cero": una policy mal puesta que dejara pasar la mitad también tiene
    que romper esto.
    """
    with conectar_como_admin() as adm:
        filas_que_hay = adm.execute(
            f'SELECT count(*) FROM public."{catalogo}"'
        ).fetchone()[0]
    assert filas_que_hay > 0, f"{catalogo} está vacía: el test no afirmaría nada"

    with agent_connection() as conn:
        filas_visibles = conn.execute(
            f'SELECT count(*) FROM public."{catalogo}"'
        ).fetchone()[0]

    assert filas_visibles == filas_que_hay, (
        f"{catalogo}: sin institución declarada se vieron {filas_visibles} de "
        f"{filas_que_hay} filas de referencia"
    )
