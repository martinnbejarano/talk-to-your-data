"""Fixtures de la suite de integración.

Todo corre contra el Postgres real del `docker compose` (D-11). Si la base no
está levantada o restaurada, la suite falla con un mensaje claro en vez de
saltearse: un test de aislamiento salteado da verde sin afirmar nada, que es
peor que no tenerlo.

Nada se hardcodea — tablas, tamaños e instituciones de prueba salen del
catálogo — y la suite no importa nada de `scripts/`.
"""

from __future__ import annotations

import sys
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

# Se resuelve en tiempo de colección porque parametriza el fail-closed.
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


def conectar_como_admin() -> psycopg.Connection:
    """Conexión con el rol administrador, con un error claro si la base no está."""
    try:
        return psycopg.connect(dsn_admin(), connect_timeout=5)
    except psycopg.OperationalError as e:
        raise RuntimeError(f"{_AYUDA}\n\nError original: {e}") from e


def tablas_con_tenant_id() -> list[tuple[str, bool]]:
    with conectar_como_admin() as conn:
        return [(t, nullable) for t, nullable in conn.execute(Q_TABLAS_CON_TENANT)]


def catalogos() -> list[str]:
    with conectar_como_admin() as conn:
        return [tabla for (tabla,) in conn.execute(Q_CATALOGOS)]


@pytest.fixture(scope="session", autouse=True)
def bootstrap_aplicado() -> None:
    """Aplica el blindaje antes de cualquier test, en vez de suponer que alguien
    se acordó de correrlo después del restore."""
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

    Los IDs no se escriben en ningún lado. Hoy dan 1 y 8; eso es un resultado,
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
