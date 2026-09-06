#!/usr/bin/env python3
"""Verificación de humo de la base restaurada (H0/01).

Cinco preguntas, todas contestadas contra la data real y ninguna contra lo que
dice el diccionario: qué tablas hay, cuántas filas, si el `AS_OF` se sostiene,
qué instituciones existen y cuál es el par que usan los tests de aislamiento.
La corrida está registrada en NOTES/00-restore-y-humo.md.

    .venv/bin/python scripts/smoke_check.py     # 0 si todo pasa, 1 si algo falla

Conecta con el usuario `postgres` del compose: es una verificación de entorno,
no el rol read-only del agente.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# La dependencia va del script hacia la suite y no al revés: este script es el
# artefacto de un hito y la suite sobrevive a todos.
from core.config import AS_OF, dsn_admin  # noqa: E402
from tests.criterio_fixture import Q_FIXTURE  # noqa: E402

# El diccionario avisa que documenta *algunas* tablas a propósito: esta lista es
# la afirmación a contrastar, no la verdad. Lo que sobre en la base es hallazgo.
TABLAS_DOCUMENTADAS = [
    "tenants",
    "tenant_config",
    "clients",
    "risk_assessments",
    "screenings",
    "alerts",
    "cases",
    "transactions",
    # catálogos / lookup
    "countries",
    "document_types",
    "channels",
    "alert_rules",
    "watchlists",
]

Q_TABLAS = """
SELECT c.relname AS tabla,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano,
       EXISTS (
           SELECT 1 FROM information_schema.columns col
           WHERE col.table_schema = 'public'
             AND col.table_name = c.relname
             AND col.column_name = 'tenant_id'
       ) AS tiene_tenant_id
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname;
"""

Q_AS_OF = """
SELECT min(tx_date) AS min_tx_date,
       max(tx_date) AS max_tx_date,
       max(booked_at) AS max_booked_at
FROM transactions;
"""

Q_TENANTS = """
SELECT count(*) AS total,
       count(*) FILTER (WHERE is_active) AS activos,
       count(*) FILTER (WHERE NOT is_active) AS inactivos
FROM tenants;
"""

Q_TENANTS_DETALLE = """
SELECT id, slug, kind, is_active
FROM tenants
ORDER BY is_active DESC, id;
"""


class Reporte:
    """Acumula el resultado de las verificaciones para decidir el exit code."""

    def __init__(self) -> None:
        self.fallas: list[str] = []

    def check(self, ok: bool, descripcion: str) -> None:
        print(f"  [{'OK ' if ok else 'FALLA'}] {descripcion}")
        if not ok:
            self.fallas.append(descripcion)


def titulo(texto: str) -> None:
    print(f"\n{texto}\n{'-' * len(texto)}")


def main() -> int:
    rep = Reporte()

    with psycopg.connect(dsn_admin()) as conn:
        server_timeout = conn.execute("SHOW statement_timeout").fetchone()[0]
        version = conn.execute("SHOW server_version").fetchone()[0]
        print(f"Postgres {version} · statement_timeout del server = {server_timeout}")
        print("Todas las consultas de este script corren bajo ese timeout: si alguna")
        print("no entra en 15s, el problema es la consulta, no la base.")

        # -- 1. Inventario de tablas ---------------------------------------
        titulo("1. Tablas en el esquema public")
        tablas = conn.execute(Q_TABLAS).fetchall()
        presentes = {t[0] for t in tablas}

        documentadas_faltantes = sorted(set(TABLAS_DOCUMENTADAS) - presentes)
        sin_documentar = sorted(presentes - set(TABLAS_DOCUMENTADAS))

        print(f"  Total de tablas: {len(presentes)}")
        print(f"  Documentadas en DATA_DICTIONARY.md: {len(TABLAS_DOCUMENTADAS)}")
        rep.check(
            not documentadas_faltantes,
            f"todas las tablas documentadas existen"
            + (f" — faltan: {documentadas_faltantes}" if documentadas_faltantes else ""),
        )
        print(f"\n  Tablas presentes que el diccionario NO documenta ({len(sin_documentar)}):")
        con_tenant = {t[0] for t in tablas if t[2]}
        for nombre in sin_documentar:
            marca = "tenant_id" if nombre in con_tenant else "sin tenant_id"
            print(f"    - {nombre:<28} ({marca})")

        # El riesgo de plan/h0-base.md: una tabla no documentada con tenant_id
        # que se escape del RLS. Se listan todas, no se asume.
        print(f"\n  Tablas CON tenant_id ({len(con_tenant)}) — todas necesitan RLS en H0/02:")
        print("    " + ", ".join(sorted(con_tenant)))
        sin_tenant = sorted(presentes - con_tenant)
        print(f"  Tablas SIN tenant_id ({len(sin_tenant)}):")
        print("    " + ", ".join(sin_tenant))

        # -- 2. Conteo de filas --------------------------------------------
        titulo("2. Conteo exacto de filas")
        total_filas = 0
        for nombre, tamano, _ in tablas:
            # `nombre` sale del catálogo de Postgres, no de input externo.
            filas = conn.execute(f'SELECT count(*) FROM public."{nombre}"').fetchone()[0]
            total_filas += filas
            print(f"  {nombre:<28} {filas:>12,}   {tamano:>8}")
        print(f"  {'TOTAL':<28} {total_filas:>12,}")
        rep.check(total_filas > 0, "la base tiene datos (el restore no quedó vacío)")

        # -- 3. AS_OF -------------------------------------------------------
        titulo(f"3. Fecha de corte declarada: AS_OF = {AS_OF}")
        min_tx, max_tx, max_booked = conn.execute(Q_AS_OF).fetchone()
        print(f"  min(tx_date)   = {min_tx}")
        print(f"  max(tx_date)   = {max_tx}")
        print(f"  max(booked_at) = {max_booked}")
        rep.check(
            str(max_tx) <= AS_OF,
            f"max(tx_date) = {max_tx} no supera el AS_OF = {AS_OF}",
        )

        # -- 4. Instituciones -----------------------------------------------
        titulo("4. Instituciones")
        total, activos, inactivos = conn.execute(Q_TENANTS).fetchone()
        print(f"  total = {total} · activas = {activos} · dadas de baja = {inactivos}")
        for tid, slug, kind, is_active in conn.execute(Q_TENANTS_DETALLE):
            estado = "activa" if is_active else "BAJA  "
            print(f"    {tid:>3}  {estado}  {kind:<8} {slug}")
        rep.check(activos >= 2, "hay al menos dos instituciones activas")

        # -- 5. Fixture de tests --------------------------------------------
        titulo("5. Tenants fixture para los tests de aislamiento")
        print("  Criterio (`Q_FIXTURE`, en tests/criterio_fixture.py; el porqué está en")
        print("  NOTES/00-restore-y-humo.md): activos, con filas vivas en")
        print("  todas las tablas del núcleo, uno con umbral versionado y otro que")
        print("  contrasta con él en kind, umbral vigente y mes fiscal.")
        print()
        fixture = conn.execute(Q_FIXTURE, {"as_of": AS_OF}).fetchall()
        for rol, tid, slug, kind, versiones, umbral, mes in fixture:
            print(
                f"    tenant {rol}: id={tid:<3} slug={slug:<16} kind={kind:<8} "
                f"umbral={umbral} ({versiones} versión/es) mes_fiscal={mes}"
            )
        rep.check(len(fixture) == 2, "el criterio devuelve exactamente dos tenants")
        if len(fixture) == 2:
            a, b = fixture
            rep.check(a[1] != b[1], "los dos tenants del fixture son distintos")
            rep.check(a[4] > 1, "el tenant A tiene el umbral de riesgo versionado")
            rep.check(a[5] != b[5], "A y B tienen umbrales de riesgo vigentes distintos")

    # -- Cierre -------------------------------------------------------------
    titulo("Resultado")
    if rep.fallas:
        print(f"  {len(rep.fallas)} verificación/es fallaron:")
        for f in rep.fallas:
            print(f"    - {f}")
        return 1
    print("  Todas las verificaciones pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
