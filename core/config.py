"""De dónde salen los parámetros del sistema. De acá y de ningún otro lado:
cuando la resolución del entorno estaba duplicada, las dos copias tenían defaults
distintos para el mismo password y el síntoma no apuntaba a la causa.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg import conninfo

RAIZ = Path(__file__).resolve().parents[1]

# El único `load_dotenv` del proyecto. No pisa lo que ya esté en el entorno: una
# variable exportada en la shell o inyectada por CI le gana al archivo.
load_dotenv(RAIZ / ".env")


# Trampa del dataset: "hoy", "este año" y "último trimestre" se interpretan
# relativo a esta fecha y nunca a `now()`. La declara DATA_DICTIONARY.md.
AS_OF = "2026-06-01"


def dsn_admin() -> str:
    # Defaults del `docker-compose.yml`, que está versionado: no hay secreto que
    # proteger y sí valor en que el proyecto ande recién clonado.
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
    # Derivado del DSN de admin a propósito: armado por separado, un error de
    # configuración podría apuntarlo a otra base y los tests de aislamiento
    # estarían verificando cualquier cosa.
    params = conninfo.conninfo_to_dict(dsn_admin())
    params["user"] = os.getenv("AGENT_RO_USER", "agent_ro")
    params["password"] = agent_ro_password()
    return conninfo.make_conninfo(**params)


def modelo() -> str:
    # Sin default a propósito: un modelo elegido por omisión hace irreproducible
    # una medición de `NOTES/` sin que nadie se entere.
    nombre = os.getenv("OPENAI_MODEL")
    if not nombre:
        raise RuntimeError(
            "Falta OPENAI_MODEL en el entorno. Copiá `.env.example` a `.env` y "
            "completalo: el nombre del modelo es parte de la configuración, no "
            "del código."
        )
    return nombre


def openai_api_key() -> str:
    # El loop la pide acá y no al entorno para no dejar una segunda resolución
    # de configuración fuera de este módulo.
    clave = os.getenv("OPENAI_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta OPENAI_API_KEY en el entorno. Copiá `.env.example` a `.env` "
            "y completalo con tu credencial del proveedor del modelo."
        )
    return clave


def agent_ro_password() -> str:
    # Un default acá sería una credencial conocida con permiso de lectura sobre
    # toda la base.
    password = os.getenv("AGENT_RO_PASSWORD")
    if not password:
        raise RuntimeError(
            "Falta AGENT_RO_PASSWORD en el entorno. Copiá `.env.example` a "
            "`.env` y completalo: el password lo elegís vos y el bootstrap se "
            "lo aplica al rol."
        )
    return password
