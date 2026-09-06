"""El seam por el que el sistema ejecuta SQL: el agente nunca ve psycopg.

Adentro y sólo adentro quedan la conexión de `agent_ro` con la institución que
pone el seam y no el llamador (D-03), la transacción de sólo lectura, el
`EXPLAIN`, el gate sobre ese plan y los errores de Postgres, que salen como
`Fallo` y no como excepción.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import cache

import psycopg

from core.config import AS_OF
from core.db import agent_connection
from core.db.gate import Rechazada, revisar_forma, revisar_plan

__all__ = ["Ok", "Rechazada", "Fallo", "ejecutar", "tablas_grandes_del_catalogo"]


@dataclass(frozen=True)
class Ok:
    filas: list[tuple]
    columnas: list[str]
    plan: dict  # el nodo raíz del `EXPLAIN (FORMAT JSON)`: el que mira el gate
    ms: float  # sólo la ejecución, no el `EXPLAIN`: comparable con los tiempos de H2


@dataclass(frozen=True)
class Fallo:
    clase: str
    detalle: str


# La clase sale del SQLSTATE y nunca del mensaje: el código es estable entre
# versiones y el wording se traduce con la locale del servidor
# (`NOTES/01-limites-y-planes.md` §1). Es lo que decide el reintento: TIMEOUT se
# reescribe más acotada, SINTAXIS se corrige, PERMISO no se reintenta. Todo lo
# demás cae en OTRO, incluida una base caída, que no trae SQLSTATE.
CLASE_POR_SQLSTATE = {
    "57014": "TIMEOUT",
    "42601": "SINTAXIS",
    "42501": "PERMISO",
}

# El corte de D-06 (`reltuples >= 100k`), descubierto por catálogo y no escrito a
# mano. El mismo número está copiado en `tests/conftest.py` y en
# `scripts/validar_semantica.py`: si se toca, se toca en los cuatro lugares.
_Q_TABLAS_GRANDES = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND c.reltuples >= 100000
"""


@cache
def tablas_grandes_del_catalogo() -> frozenset[str]:
    """Las tablas donde recorrer entero se come el presupuesto de 15 s.

    El `cache` es por proceso: `reltuples` sólo se mueve con un `ANALYZE`. Se
    resuelve al primer pedido y no al importar, para que importar este módulo no
    exija Postgres.
    """
    with agent_connection() as conn:
        return frozenset(t for (t,) in conn.execute(_Q_TABLAS_GRANDES).fetchall())


def ejecutar(sql: str, params: dict, institucion_id: int) -> Ok | Rechazada | Fallo:
    """Ejecuta una consulta de lectura para una institución, o explica por qué no.

    `tenant` y `as_of` los pone el seam y pisan lo que venga: la institución sale
    del selector y nunca de quien escribe el SQL (D-03), y la fecha de corte es
    una regla del sistema. Del período se encarga el llamador. Sobran las claves
    que la consulta no use: psycopg liga por nombre.
    """
    if rechazo := revisar_forma(sql):
        return rechazo

    parametros = {
        **params,
        "tenant": institucion_id,
        "as_of": AS_OF,
    }

    try:
        grandes = tablas_grandes_del_catalogo()

        with agent_connection(institucion_id) as conn:
            # El salto de línea no es cosmético: hace que el renglón que
            # Postgres señala al reportar un error de sintaxis sea el que
            # escribió el agente, sin un prefijo que nunca puso.
            (explicacion,) = conn.execute(
                f"EXPLAIN (FORMAT JSON)\n{sql}", parametros
            ).fetchone()
            plan = explicacion[0]["Plan"]

            if rechazo := revisar_plan(plan, grandes):
                return rechazo

            comienzo = time.monotonic()
            cursor = conn.execute(sql, parametros)
            filas = cursor.fetchall()
            ms = (time.monotonic() - comienzo) * 1000
            columnas = [c.name for c in cursor.description]

    except psycopg.Error as e:
        return Fallo(
            clase=CLASE_POR_SQLSTATE.get(e.sqlstate, "OTRO"),
            detalle=str(e).strip(),
        )

    return Ok(filas=filas, columnas=columnas, plan=plan, ms=ms)
