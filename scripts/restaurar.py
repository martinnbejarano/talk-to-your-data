#!/usr/bin/env python3
"""Restaura el dump contra la base que diga el entorno, y reaplica el bootstrap.

    .venv/bin/python scripts/restaurar.py dump/compliance.dump   # restore + bootstrap
    .venv/bin/python scripts/restaurar.py --solo-bootstrap       # sólo el bootstrap

Existe porque el paso que se olvida es siempre el mismo: `pg_restore --clean` se
lleva puestos los GRANT y las policies de RLS, y sin `infra/bootstrap.sql`
reaplicado el rol del agente queda sin permisos —o peor, sin aislamiento—.
Los dos pasos viven acá para que no puedan separarse.

La base sale de `core.config.dsn_admin()`: `DATABASE_URL` si está, si no las
`PG*`. Es el mismo camino que usan la API y los tests, así que apunta a la de
Railway exportando la variable y nada más:

    DATABASE_URL=postgresql://... .venv/bin/python scripts/restaurar.py dump/compliance.dump
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from psycopg import conninfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import dsn_admin  # noqa: E402
from core.db import apply_bootstrap  # noqa: E402

LOCALES = {"localhost", "127.0.0.1", "::1", "db"}


def _destino(dsn: str) -> tuple[str, str]:
    params = conninfo.conninfo_to_dict(dsn)
    return params.get("host", "localhost"), params.get("dbname", "")


def _confirmar(host: str, base: str) -> None:
    """`--clean` vacía la base antes de escribir: contra un host remoto, un DSN
    equivocado destruye datos ajenos. Local no pregunta porque el flujo del
    README lo repite y una confirmación que se contesta sola no protege nada."""
    if host in LOCALES:
        return
    print(f"Vas a restaurar con --clean sobre `{base}` en `{host}`, que no es local.")
    print("Eso borra lo que haya antes de escribir el dump.")
    if input("Escribí el nombre de la base para confirmar: ").strip() != base:
        sys.exit("Cancelado: el nombre no coincide.")


def restaurar(dump: Path, dsn: str) -> None:
    # Sin timeout para esta sesión y sólo para ésta: crear los índices sobre
    # decenas de millones de filas no entra en los 15s del server.
    entorno = os.environ | {"PGOPTIONS": "-c statement_timeout=0"}
    orden = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "-j4",
        "-d",
        dsn,
        str(dump),
    ]
    # `check=False`: pg_restore devuelve != 0 por errores que `--clean` produce
    # sobre una base vacía (DROP de lo que no existe). El bootstrap que sigue y
    # `scripts/smoke_check.py` son la verificación real.
    codigo = subprocess.run(orden, env=entorno).returncode
    if codigo != 0:
        print(f"pg_restore terminó con código {codigo}; suele ser el ruido de --clean.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dump",
        nargs="?",
        type=Path,
        help="el archivo .dump a restaurar; omitilo con --solo-bootstrap",
    )
    parser.add_argument(
        "--solo-bootstrap",
        action="store_true",
        help="salta el restore y sólo reaplica infra/bootstrap.sql",
    )
    args = parser.parse_args()

    # Antes de resolver la base y de preguntar nada: que el error del dump que
    # no está no llegue después de una confirmación.
    if not args.solo_bootstrap:
        if args.dump is None:
            parser.error("falta el dump, o pasá --solo-bootstrap")
        if not args.dump.is_file():
            sys.exit(f"No existe el dump `{args.dump}`. El link de descarga va aparte.")

    dsn = dsn_admin()
    host, base = _destino(dsn)
    print(f"Base: `{base}` en `{host}`")

    if not args.solo_bootstrap:
        _confirmar(host, base)
        restaurar(args.dump, dsn)

    apply_bootstrap()
    print("Bootstrap aplicado: rol read-only, RLS por institución y grants.")


if __name__ == "__main__":
    main()
