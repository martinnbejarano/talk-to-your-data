"""La lista de instituciones para el selector."""

from __future__ import annotations

import psycopg

from core import config

# Deuda deliberada: se abre psycopg acá y no en `core/db/` porque `tenants` lleva
# RLS por `id` (`infra/bootstrap.sql` §4) y ningún scope produce esta lista — la
# lista es lo que se usa para elegir el scope. De ahí el rol administrador, la
# transacción de sólo lectura y ni un dato que pertenezca a una institución.

# Sólo las activas: el dump trae un banco en liquidación y una fintech legacy.
_Q_INSTITUCIONES = """
SELECT id, slug, legal_name
FROM tenants
WHERE is_active
ORDER BY legal_name
"""


def instituciones_elegibles() -> list[dict]:
    with psycopg.connect(config.dsn_admin()) as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            filas = conn.execute(_Q_INSTITUCIONES).fetchall()

    return [
        {"institucion_id": id, "slug": slug, "nombre": nombre}
        for id, slug, nombre in filas
    ]
