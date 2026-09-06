"""De dónde salen los parámetros del sistema. De acá y de ningún otro lado.

Módulo aparte y no una entrada más en `core/db` porque `scripts/` y `tests/`
necesitan conectarse como administrador sin pasar por esa costura, que expone
`agent_connection` y `apply_bootstrap` y nada más. Acá se resuelve *de dónde
salen los valores*; en `core/db`, *qué se hace con la conexión*.

Una sola fuente: cuando la resolución del entorno estaba duplicada, las dos
copias tenían defaults distintos para el mismo password y el síntoma no
apuntaba a la causa.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg import conninfo

RAIZ = Path(__file__).resolve().parents[1]

# El único `load_dotenv` del proyecto, y por eso corre al importar y no dentro
# de cada función. No pisa lo que ya esté en el entorno, así que una variable
# exportada en la shell o inyectada por CI le gana al archivo.
load_dotenv(RAIZ / ".env")


# La fecha de corte que declara DATA_DICTIONARY.md, verificada contra la data en
# `scripts/smoke_check.py`. Todo el sistema interpreta "hoy", "este año" y
# "último trimestre" relativo a esto y nunca a `now()`: es una trampa del
# dataset.
AS_OF = "2026-06-01"


def dsn_admin() -> str:
    """DSN del rol administrador: el que restaura, explora y aplica el bootstrap.

    Los defaults son los del `docker-compose.yml`, que está versionado: no hay
    secreto que proteger y sí valor en que el proyecto ande recién clonado.
    """
    if url := os.getenv("DATABASE_URL"):
        return url
    return conninfo.make_conninfo(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "55432"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "compliance"),
        dbname=os.getenv("PGDATABASE", "compliance"),
    )


def dsn_agente() -> str:
    """DSN del rol del agente: la misma base que el admin, otro usuario.

    Se deriva del DSN de administrador a propósito: armado por separado, un
    error de configuración podría apuntarlo a otra base y los tests de
    aislamiento estarían verificando cualquier cosa.
    """
    params = conninfo.conninfo_to_dict(dsn_admin())
    params["user"] = os.getenv("AGENT_RO_USER", "agent_ro")
    params["password"] = agent_ro_password()
    return conninfo.make_conninfo(**params)


def agent_ro_password() -> str:
    """El password del rol del agente, que no tiene default y no puede tenerlo.

    Un default acá sería una credencial conocida con permiso de lectura sobre
    toda la base.
    """
    password = os.getenv("AGENT_RO_PASSWORD")
    if not password:
        raise RuntimeError(
            "Falta AGENT_RO_PASSWORD en el entorno. Copiá `.env.example` a "
            "`.env` y completalo: el password lo elegís vos y el bootstrap se "
            "lo aplica al rol."
        )
    return password
