"""La única costura por la que el sistema toca la base.

Expone ``agent_connection`` y ``apply_bootstrap``, y nada más: cuantas menos
costuras, menos lugares donde la garantía de aislamiento puede evaporarse. Si
mañana hay pooling, o cambia el manejo de sesión, se toca acá y en ningún otro
lado.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import sql

from core import config

__all__ = ["agent_connection", "apply_bootstrap"]

_BOOTSTRAP_SQL = config.RAIZ / "infra" / "bootstrap.sql"


@contextmanager
def agent_connection(tenant_id: int | None = None) -> Iterator[psycopg.Connection]:
    """Conexión del agente, scopeada a una institución.

    El default ``None`` es parte del contrato: expresa el caso "nadie declaró
    institución", que sin RLS sería el modo inseguro y acá devuelve cero filas.

    ``SET LOCAL`` y nunca ``SET`` de sesión, para anticipar el pooling: un
    ``SET`` de sesión sobrevive a la devolución de la conexión al pool, y una
    conexión reciclada que conserva el ``app.tenant_id`` del oficial anterior es
    exactamente la filtración que este blindaje existe para hacer imposible.

    Sin institución se declara la cadena vacía en vez de no declarar nada: así
    la transacción pisa cualquier valor arrastrado de la sesión, y el ``NULLIF``
    de la policy la convierte en ``NULL``, que no matchea con nada.
    """
    valor = "" if tenant_id is None else str(int(tenant_id))

    with psycopg.connect(config.dsn_agente()) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute(
                sql.SQL("SET LOCAL app.tenant_id = {}").format(sql.Literal(valor))
            )
            yield conn


def apply_bootstrap() -> None:
    """Aplica ``infra/bootstrap.sql`` con el rol administrador.

    Idempotente, y correrlo después de cada ``docker compose run --rm restore``
    no es opcional: el restore se lleva puestos los GRANT y las policies.

    El password viaja como parámetro de sesión y no como texto dentro del
    script, para que el ``.sql`` quede versionable y sin credenciales.
    """
    password = config.agent_ro_password()
    script = _BOOTSTRAP_SQL.read_text(encoding="utf-8")

    with psycopg.connect(config.dsn_admin()) as conn:
        with conn.transaction():
            conn.execute(
                sql.SQL("SET LOCAL bootstrap.agent_ro_password = {}").format(
                    sql.Literal(password)
                )
            )
            conn.execute(script)
