"""Escribe `evals/valores_esperados.yaml` desde las skills ya validadas.

El insumo de H4: para cada pregunta de referencia, el número correcto en las dos
instituciones de trabajo, con su cascada completa.

**No se escribe a mano.** Un valor esperado transcrito a mano se desincroniza de
su definición en silencio, y entonces el eval mide contra un número viejo y da
verde. Acá cada valor sale de la golden query de su skill *y* de la consulta
escrita de otra forma; si los dos caminos no coinciden, el script corta.

    .venv/bin/python scripts/valores_esperados.py
"""

from __future__ import annotations

import datetime
import decimal
import sys
from pathlib import Path

import psycopg
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import AS_OF, dsn_admin  # noqa: E402
from core.db import agent_connection  # noqa: E402
from scripts.validar_semantica import PERIODOS, SEMANTICS, parametros  # noqa: E402
from tests.criterio_fixture import Q_FIXTURE  # noqa: E402

SALIDA = Path(__file__).resolve().parents[1] / "evals" / "valores_esperados.yaml"

# Las ocho preguntas del enunciado, más la que se desprendió de "hallazgo real"
# al separarla en dos conceptos (D-12).
PREGUNTAS = {
    "cliente_onboardeado": "¿Cuántos clientes onboardeamos este año?",
    "riesgo_alto": "¿Cuántos clientes de riesgo alto tenemos?",
    "monto_transado": (
        "¿Cuál fue el monto total transado por los clientes de riesgo alto "
        "el último trimestre?"
    ),
    "alerta_fuera_de_sla": "¿Qué alertas están fuera del SLA de revisión?",
    "hallazgo_real": "¿Cuántos hallazgos reales tuvimos el último trimestre?",
    "pep_confirmado": "¿Alguno de nuestros clientes es PEP?",
    "resolucion_de_casos": "¿Cuál es el tiempo promedio de resolución de casos?",
    "misma_persona": "¿Qué clientes son probablemente la misma persona?",
    "caso_reportado": "¿Cuántos casos reportamos a la UIF el último trimestre?",
}


def _decimal_como_float(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:float", str(data))


yaml.add_representer(decimal.Decimal, _decimal_como_float)


def main() -> int:
    with psycopg.connect(dsn_admin()) as conn:
        tenants = [
            (rol, tid, slug)
            for rol, tid, slug, *_ in conn.execute(Q_FIXTURE, {"as_of": AS_OF}).fetchall()
        ]

    salida = {
        "_generado": f"scripts/valores_esperados.py · {datetime.date.today()} · AS_OF={AS_OF}",
        "_nota": (
            "Cada valor sale de la golden query de su skill Y de una consulta "
            "escrita de otra forma (verificacion_sql). Los dos caminos "
            "coinciden: eso es lo que hace creíble el número. Regenerar con el "
            "script, no editar a mano."
        ),
        "preguntas": [],
    }

    for archivo in sorted(SEMANTICS.glob("*.yaml")):
        skill = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        concepto = skill["concepto"]
        entrada = {
            "concepto": concepto,
            "pregunta": PREGUNTAS[concepto],
            "resultado": skill["resultado"],
            "por_institucion": {},
        }

        for _rol, tenant_id, slug in tenants:
            params = parametros(tenant_id, skill)
            with agent_connection(tenant_id) as conn:
                cur = conn.execute(skill["golden_sql"], params)
                fila = dict(zip([c.name for c in cur.description], cur.fetchone()))
                segundo = conn.execute(skill["verificacion_sql"], params).fetchone()[0]
                desglose = None
                if skill.get("desglose_sql"):
                    d = conn.execute(skill["desglose_sql"], params)
                    columnas = [c.name for c in d.description]
                    desglose = [
                        dict(zip(columnas, [str(v) for v in f])) for f in d.fetchall()
                    ]

            if fila[skill["resultado"]] != segundo:
                print(
                    f"✗ {concepto} en {slug}: la golden da "
                    f"{fila[skill['resultado']]} y el segundo camino {segundo}. "
                    "No se escribe nada.",
                    file=sys.stderr,
                )
                return 1

            entrada["por_institucion"][slug] = {
                "tenant_id": tenant_id,
                "periodo": list(
                    PERIODOS[skill.get("periodo_por_defecto", "ultimo_trimestre")]
                ),
                "valor_esperado": fila[skill["resultado"]],
                "derivacion": fila,
            }
            if desglose:
                entrada["por_institucion"][slug]["desglose"] = desglose

        salida["preguntas"].append(entrada)

    SALIDA.parent.mkdir(exist_ok=True)
    with SALIDA.open("w", encoding="utf-8") as f:
        yaml.dump(salida, f, allow_unicode=True, sort_keys=False, width=100)

    print(f"✓ {len(salida['preguntas'])} preguntas escritas en {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
