"""Fixtures de la suite.

Los tests de datos corren contra el Postgres real del `docker compose` (D-11).
Si la base no está levantada o restaurada, fallan con un mensaje claro en vez de
saltearse: un test de aislamiento salteado da verde sin afirmar nada, que es peor
que no tenerlo.

Nada se hardcodea — tablas, tamaños e instituciones de prueba salen del
catálogo — y la suite no importa nada de `scripts/`.

**Importar este módulo no toca la base.** Es una propiedad deliberada y frágil,
así que conviene decir por qué: los conjuntos que salen del catálogo se resuelven
la primera vez que un test los pide, nunca al importar, y el bootstrap se aplica
sólo a los tests que lo declaran. Antes no era así, y eso ataba la *colección* de
toda la suite a tener Postgres levantado — con lo cual un test de una función
pura (normalizar un documento, resolver un período) no podía correr sin la base,
aunque no la necesitara para nada.

La regla, entonces: **un test que toca la base lo dice en su firma**, pidiendo
`bootstrap_aplicado` o alguna fixture que dependa de él (`tenant_a`, `tenant_b`).
Uno que no lo dice, corre solo.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import psycopg
import pytest

_RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_RAIZ))

from core.config import AS_OF, dsn_admin  # noqa: E402
from core.db import apply_bootstrap  # noqa: E402
from tests.criterio_fixture import Q_FIXTURE  # noqa: E402

_AYUDA = (
    "No se pudo conectar a la base del compose. Esta suite corre contra "
    "Postgres real y no tiene sentido sin él:\n"
    "    docker compose up -d db\n"
    "    docker compose run --rm restore    # sólo la primera vez\n"
    "y revisá el `.env` (copialo de `.env.example`)."
)

# `is_nullable` es lo que separa los dos regímenes de policy: las columnas NOT
# NULL son fail-closed estricto, las nullable admiten además las filas globales
# (ver `infra/bootstrap.sql`).
Q_TABLAS_CON_TENANT = """
SELECT c.table_name, c.is_nullable = 'YES' AS admite_globales
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE c.table_schema = 'public'
  AND c.column_name = 'tenant_id'
  AND t.table_type = 'BASE TABLE'
ORDER BY c.table_name;
"""

# Los catálogos: tablas de referencia compartidas, sin `tenant_id` y sin RLS.
# La única exclusión escrita a mano es `tenants`, que tampoco tiene `tenant_id`
# pero lleva RLS por `id` (ver `infra/bootstrap.sql`).
Q_CATALOGOS = """
SELECT t.table_name
FROM information_schema.tables t
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
  AND t.table_name <> 'tenants'
  AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
      WHERE c.table_schema = t.table_schema
        AND c.table_name = t.table_name
        AND c.column_name = 'tenant_id'
  )
ORDER BY t.table_name;
"""

# El corte en 100k filas es el de D-06 y separa las tablas donde un recorrido
# completo se come el presupuesto de 15s de aquellas donde da lo mismo. Las dos
# consultas de acá abajo son los dos lados del mismo corte, y por eso viven
# juntas: si una se toca, la otra tiene que acompañar.
Q_TABLAS_GRANDES = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.reltuples >= 100000
ORDER BY c.relname;
"""

# Las chicas se piden además NOT NULL: las mixtas tienen filas globales legibles
# siempre, así que el conjunto visible nunca sería exactamente `{tenant}`.
Q_TABLAS_CHICAS = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN information_schema.columns col
  ON col.table_schema = 'public'
 AND col.table_name = c.relname
 AND col.column_name = 'tenant_id'
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.reltuples < 100000
  AND col.is_nullable = 'NO'
ORDER BY c.relname;
"""


def conectar_como_admin() -> psycopg.Connection:
    """Conexión con el rol administrador, con un error claro si la base no está."""
    try:
        return psycopg.connect(dsn_admin(), connect_timeout=5)
    except psycopg.OperationalError as e:
        raise RuntimeError(f"{_AYUDA}\n\nError original: {e}") from e


@cache
def _del_catalogo(consulta: str) -> list[tuple]:
    """Resuelve una consulta al catálogo, una sola vez por corrida.

    El `cache` no es una optimización: es lo que permite que varias fixtures y
    el hook de parametrización pidan lo mismo sin abrir cuatro conexiones.
    """
    with conectar_como_admin() as conn:
        return conn.execute(consulta).fetchall()


def _tablas_mixtas() -> list[str]:
    """Las tablas con `tenant_id` nullable, que llevan la policy de las mixtas."""
    return [t for t, admite_globales in _del_catalogo(Q_TABLAS_CON_TENANT) if admite_globales]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametriza desde el catálogo, y recién cuando un test lo pide.

    Este hook corre una vez por función colectada, así que la consulta se hace
    sólo si esa función declara el parámetro. Es lo que reemplaza a los tres
    `with conectar_como_admin()` que antes vivían a nivel de módulo y conectaban
    apenas pytest importaba el archivo.

    Los nombres son largos a propósito (`tabla_con_tenant` y no `tabla`): este
    hook mira todos los tests de la suite, y `test_permisos.py` ya usa `tabla`
    para una lista escrita a mano. Dos parametrizaciones sobre el mismo nombre
    es un error de pytest, no un merge silencioso.
    """
    if "tabla_con_tenant" in metafunc.fixturenames:
        tablas = _del_catalogo(Q_TABLAS_CON_TENANT)
        metafunc.parametrize(
            "tabla_con_tenant, admite_globales", tablas, ids=[t for t, _ in tablas]
        )

    if "catalogo" in metafunc.fixturenames:
        catalogos = [tabla for (tabla,) in _del_catalogo(Q_CATALOGOS)]
        metafunc.parametrize("catalogo", catalogos)

    # Las mixtas: `tenant_id` nullable, o sea filas globales de referencia
    # mezcladas con filas de una institución. Hoy sólo `watchlists`.
    #
    # El cálculo va adentro de cada `if` y no arriba, aunque se repita: puesto
    # arriba consulta el catálogo para *cada* función colectada de la suite, que
    # es exactamente el acoplamiento que este hook existe para romper.
    if "tabla_mixta_o_aviso" in metafunc.fixturenames:
        mixtas = _tablas_mixtas()
        # `parametrize` sobre una lista vacía no falla: no colecta nada y la
        # suite da verde sin afirmar nada. Este caso único hace que eso se diga
        # en voz alta, y por eso es un nombre aparte del de abajo.
        metafunc.parametrize(
            "tabla_mixta_o_aviso",
            mixtas or [pytest.param(None, id="no-hay-tablas-mixtas")],
        )

    if "tabla_mixta" in metafunc.fixturenames:
        metafunc.parametrize("tabla_mixta", _tablas_mixtas())


@pytest.fixture(scope="session")
def bootstrap_aplicado() -> None:
    """Aplica el blindaje antes de los tests que tocan la base.

    No es `autouse`: si lo fuera, una función pura no podría correr sin Postgres,
    que es justamente lo que este módulo evita. El precio es que cada test de
    datos declare la dependencia, y ese precio es en realidad una ventaja —
    leyendo la firma se sabe si el test necesita la base.

    Se aplica acá en vez de suponer que alguien se acordó de correrlo después del
    restore, que se lleva puestos los GRANT y las policies.
    """
    try:
        apply_bootstrap()
    except psycopg.OperationalError as e:
        pytest.fail(f"{_AYUDA}\n\nError original: {e}", pytrace=False)


@pytest.fixture(scope="session")
def par_de_tenants(bootstrap_aplicado) -> tuple[int, int]:
    """Las dos instituciones de prueba, descubiertas consultando la base.

    El criterio es `Q_FIXTURE`, en `tests/criterio_fixture.py`. Que las dos
    contrasten importa: si A y B dieran los mismos números, una fuga entre
    instituciones no se vería.

    Los IDs no se escriben en ningún lado. Hoy dan 3 y 14; eso es un resultado,
    no una constante.
    """
    with conectar_como_admin() as conn:
        filas = conn.execute(Q_FIXTURE, {"as_of": AS_OF}).fetchall()
    if len(filas) != 2:
        pytest.fail(
            "El criterio de fixture no devolvió dos instituciones "
            f"(devolvió {len(filas)}). Revisá `Q_FIXTURE` contra la data: "
            "cambió el dump o cambió el criterio, y las dos cosas hay que "
            "mirarlas.",
            pytrace=False,
        )
    return filas[0][1], filas[1][1]


@pytest.fixture(scope="session")
def tenant_a(par_de_tenants) -> int:
    return par_de_tenants[0]


@pytest.fixture(scope="session")
def tenant_b(par_de_tenants) -> int:
    return par_de_tenants[1]


@pytest.fixture(scope="session")
def tablas_grandes() -> set[str]:
    """Las tablas donde recorrer entero se come el presupuesto de 15s (D-06)."""
    return {tabla for (tabla,) in _del_catalogo(Q_TABLAS_GRANDES)}


@pytest.fixture(scope="session")
def tablas_chicas() -> list[str]:
    """Las tablas con `tenant_id` NOT NULL sobre las que un `SELECT DISTINCT`
    es barato. Sobre `transactions` esa consulta se come los 15s antes de
    afirmar nada; si el aislamiento se rompe, se rompe igual de visible en
    `users`."""
    return [tabla for (tabla,) in _del_catalogo(Q_TABLAS_CHICAS)]
