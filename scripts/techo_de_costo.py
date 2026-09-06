"""Mide el techo de costo del gate de D-06: el máximo de las dieciocho corridas
de las nueve goldens de `core/semantics/` en las dos instituciones, con margen
×3 (por qué ×3: `NOTES/01-limites-y-planes.md` §2).

El resultado se copia **a mano** a `TECHO_DE_COSTO` en `core/db/gate.py`: el gate
tiene que ser una función pura, y un techo recalculado contra la base haría que
el mismo plan se acepte hoy y se rechace mañana según el último `ANALYZE`.

    .venv/bin/python scripts/techo_de_costo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import agent_connection  # noqa: E402
from scripts.validar_semantica import (  # noqa: E402
    SEMANTICS,
    parametros,
    tenants_de_trabajo,
)

MARGEN = 3


def costo_total(conn: psycopg.Connection, sql: str, params: dict) -> float:
    # El nodo raíz y no el máximo de los nodos: el costo de Postgres es
    # acumulado, el de la raíz ya incluye el de todos sus hijos.
    (explicacion,) = conn.execute(f"EXPLAIN (FORMAT JSON) {sql}", params).fetchone()
    return explicacion[0]["Plan"]["Total Cost"]


def main() -> int:
    tenants = tenants_de_trabajo()

    skills = [
        yaml.safe_load(archivo.read_text(encoding="utf-8"))
        for archivo in sorted(SEMANTICS.glob("*.yaml"))
    ]

    medidas: list[tuple[float, str]] = []
    desgloses: list[tuple[float, str]] = []

    print(f"{'skill':<22} {'institución':<16} {'costo del plan':>16}")
    print("-" * 56)
    for skill in skills:
        for _rol, tenant_id, slug in tenants:
            params = parametros(tenant_id, skill)
            with agent_connection(tenant_id) as conn:
                costo = costo_total(conn, skill["golden_sql"], params)
                medidas.append((costo, f"{skill['concepto']} · {slug}"))
                print(f"{skill['concepto']:<22} {slug:<16} {costo:>16,.2f}")

                if skill.get("desglose_sql"):
                    desgloses.append(
                        (
                            costo_total(conn, skill["desglose_sql"], params),
                            f"{skill['concepto']} · {slug} (desglose)",
                        )
                    )

    maximo, cual = max(medidas)
    techo = maximo * MARGEN
    print("-" * 56)
    print(f"máximo de las {len(medidas)} corridas: {maximo:,.2f}  ({cual})")
    print(f"techo con margen ×{MARGEN}:            {techo:,.2f}")

    # El desglose no entra al techo —el ticket lo fija sobre las goldens— pero sí
    # pasa por el gate cuando el sistema lo corre: si no entrara, el techo estaría
    # dejando afuera media respuesta, y eso sale por el código de salida.
    peor_desglose, cual_desglose = max(desgloses)
    entra = peor_desglose < techo
    print(
        f"peor desglose:                 {peor_desglose:,.2f}  "
        f"({cual_desglose}) · {'entra' if entra else 'NO ENTRA'} en el techo"
    )

    print(f"\nTECHO_DE_COSTO = {round(techo):_}")
    return 0 if entra else 1


if __name__ == "__main__":
    raise SystemExit(main())
