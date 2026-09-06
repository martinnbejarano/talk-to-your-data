"""Corre cada skill de `core/semantics/` contra la base y la muestra.

Los cinco criterios de `plan/h2-semantica.md` ahora viven además en
`tests/test_semantica.py`, que es donde suenan solos. Este script sigue
existiendo por lo que un test no da: la **salida legible** — la cascada de cada
skill con sus números, en las dos instituciones, que es como se lee si una
definición dice lo que pretende.

Los cinco criterios, los cinco afirmados acá:

  1. Corre en los dos tenants de trabajo y da resultados coherentes.
  2. Corre por debajo del `statement_timeout`, con el rol `agent_ro`.
  3. Su `EXPLAIN` no recorre entera una tabla grande (el corte de D-06).
  4. El resultado se cruza contra una consulta escrita de otra forma
     — el `verificacion_sql` de cada skill, que tiene que llegar al mismo
     número por otro camino.
  5. Toda tabla con `deleted_at` que entra al join lleva su filtro, y no
     sólo la principal.

El quinto parecía cosa de leer y no lo es: el chequeo ata el filtro al **alias**
de cada tabla, porque en las consultas de cascada vive dentro de un `FILTER` que
aparece antes del `FROM` —el primer escalón cuenta las borradas para poder decir
cuántas se excluyeron—. Un chequeo por cercanía de texto marca en falso justo a
las consultas mejor escritas, que es como estaba escrito el primer intento.

Corre como el agente y no como administrador **a propósito**: una golden query
que anduviera como `postgres` y muriera bajo RLS o sin permisos no sirve de
nada, y ésa es justamente la diferencia que el script existe para no dejar
pasar.

    .venv/bin/python scripts/validar_semantica.py
    .venv/bin/python scripts/validar_semantica.py riesgo_alto
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import AS_OF, dsn_admin  # noqa: E402
from core.db import agent_connection  # noqa: E402
from core.periodos import ULTIMO_TRIMESTRE, resolver_periodo  # noqa: E402
from tests.criterio_fixture import Q_FIXTURE  # noqa: E402
from tests.criterios_semanticos import (  # noqa: E402
    SEMANTICS,
    cargar_skills,
    parametros,
    seq_scans_prohibidos,
    soft_delete_sin_filtrar,
    tablas_borrables,
)

# Los períodos canónicos ya no se escriben acá como literales: los resuelve
# `core.periodos` contra la fecha de corte. El diccionario queda armado —y
# tecleado como lo escriben las skills, con eñe— porque
# `scripts/valores_esperados.py` lo importa de este módulo para anotar el
# período de cada pregunta en el YAML del eval.
PERIODOS = {
    periodo: resolver_periodo(periodo)
    for periodo in {
        skill.get("periodo_por_defecto", ULTIMO_TRIMESTRE) for skill in cargar_skills()
    }
}


def tenants_de_trabajo() -> list[tuple[str, int, str]]:
    """Las dos instituciones del criterio de H1. Los IDs son un resultado."""
    with psycopg.connect(dsn_admin()) as conn:
        filas = conn.execute(Q_FIXTURE, {"as_of": AS_OF}).fetchall()
    return [(rol, tid, slug) for rol, tid, slug, *_ in filas]


def tablas_grandes() -> set[str]:
    """Las de `reltuples >= 100k`: el corte de D-06."""
    with psycopg.connect(dsn_admin()) as conn:
        filas = conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid = c.relnamespace WHERE n.nspname='public' "
            "AND c.relkind='r' AND c.reltuples >= 100000"
        ).fetchall()
    return {t for (t,) in filas}


def validar(
    skill: dict,
    tenants: list[tuple[str, int, str]],
    grandes: set[str],
    borrables: set[str],
) -> bool:
    """Corre una skill en las dos instituciones. Devuelve si pasó todo."""
    concepto = skill["concepto"]
    escalones = [d["escalon"] for d in skill["derivacion"]]
    metricas = [m["nombre"] for m in skill.get("metricas", [])]
    esperadas = escalones + metricas
    ok = True

    print(f"\n{'=' * 78}\n{concepto} · {skill['nombre_humano']}\n{'=' * 78}")

    # Criterio 5: se lee del SQL, así que se chequea una vez y no por tenant.
    for campo in ("golden_sql", "desglose_sql", "verificacion_sql"):
        if campo in skill:
            faltan = soft_delete_sin_filtrar(skill[campo], borrables)
            if faltan:
                print(f"  ✗ {campo}: sin filtro de borrado en {', '.join(faltan)}")
                ok = False

    for rol, tenant_id, slug in tenants:
        params = parametros(tenant_id, skill)
        with agent_connection(tenant_id) as conn:
            t0 = time.monotonic()
            cur = conn.execute(skill["golden_sql"], params)
            filas = cur.fetchall()
            ms = (time.monotonic() - t0) * 1000
            columnas = [c.name for c in cur.description]

            if len(filas) != 1:
                print(f"  ✗ {slug}: la golden devolvió {len(filas)} filas, tiene que ser 1")
                ok = False
                continue
            if columnas != esperadas:
                print(f"  ✗ {slug}: columnas {columnas} != derivacion+metricas {esperadas}")
                ok = False
                continue

            valores = dict(zip(columnas, filas[0]))
            scans = seq_scans_prohibidos(conn, skill["golden_sql"], params, grandes)

            # Criterio 4: el segundo camino tiene que dar el mismo número.
            resultado = valores[skill["resultado"]]
            verificado = conn.execute(skill["verificacion_sql"], params).fetchone()[0]
            coincide = resultado == verificado

            print(f"\n  {rol} · {slug} (id={tenant_id}) · {ms:.0f} ms")
            for d in skill["derivacion"]:
                marca = "→" if d["escalon"] == skill["resultado"] else " "
                print(f"    {marca} {d['texto']:<52} {valores[d['escalon']]:>14,}")
            for m in skill.get("metricas", []):
                marca = "→" if m["nombre"] == skill["resultado"] else " "
                print(f"    {marca} {m['texto']:<52} {valores[m['nombre']]:>14} {m['unidad']}")

            if skill.get("desglose_sql"):
                # El desglose corre bajo el mismo presupuesto que la golden: es
                # parte de la respuesta, no un anexo. Cuando se pasa hay que
                # verlo como una falla de la skill y no como una excepción.
                print("    · desglose:")
                t1 = time.monotonic()
                try:
                    for fila in conn.execute(skill["desglose_sql"], params).fetchall():
                        print(f"        {fila}")
                    ms += (time.monotonic() - t1) * 1000
                except psycopg.errors.QueryCanceled:
                    print("    ✗ el desglose se pasó del statement_timeout")
                    ok = False
                    continue

            if ms > 15_000:
                print(f"    ✗ se pasó del statement_timeout ({ms:.0f} ms)")
                ok = False
            if scans:
                print(f"    ✗ Seq Scan sobre tabla grande: {', '.join(sorted(set(scans)))}")
                ok = False
            if not coincide:
                print(f"    ✗ el segundo camino da {verificado}, la golden da {resultado}")
                ok = False
            if not scans and coincide and ms <= 15_000:
                print(f"    ✓ índice · {ms:.0f} ms · verificada por segundo camino ({verificado:,})")

    return ok


def main() -> int:
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    tenants = tenants_de_trabajo()
    grandes = tablas_grandes()
    with psycopg.connect(dsn_admin()) as conn:
        borrables = tablas_borrables(conn)

    skills = cargar_skills(filtro)
    if not skills:
        print(f"No hay skills que matcheen {filtro!r} en {SEMANTICS}")
        return 1

    fallaron = []
    for skill in skills:
        if not validar(skill, tenants, grandes, borrables):
            fallaron.append(skill["concepto"])

    print(f"\n{'=' * 78}")
    if fallaron:
        print(f"✗ {len(fallaron)} de {len(skills)}: {', '.join(fallaron)}")
        return 1
    print(f"✓ {len(skills)} skills validadas en las dos instituciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
