"""El gate de D-06: qué consultas llegan a ejecutarse, y por qué no las demás.

Dos funciones puras, sobre el texto y sobre el JSON del `EXPLAIN`. `Rechazada`
no es un error: su destinatario es un agente que va a reintentar, y por eso
lleva `sugerencia` accionable en vez de un mensaje para una persona.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["TECHO_DE_COSTO", "Rechazada", "revisar_forma", "revisar_plan"]


# Medido, no inventado: máximo de las dieciocho corridas de las nueve goldens en
# las dos instituciones de trabajo, con margen ×3. Lo regenera y lo justifica
# `scripts/techo_de_costo.py`. Mirar el costo y no sólo el tipo de nodo es lo que
# atrapa al CTE que se recalcula por fila (`NOTES/01-limites-y-planes.md` §3).
TECHO_DE_COSTO = 4_101_448


@dataclass(frozen=True)
class Rechazada:
    motivo: str
    sugerencia: str


# Todo lo que puede contener un `;` o una palabra reservada sin ser una
# sentencia. Una sola alternancia y un solo `sub` porque el orden de consumo
# importa: un `--` adentro de un literal tiene que consumirse con el literal.
# El dollar-quoting no está contemplado y falla cerrado — un `;` adentro de un
# `$$` se lee como segunda sentencia y la consulta se rechaza.
_RUIDO = re.compile(
    r"'(?:[^']|'')*'"  # literal de texto
    r'|"(?:[^"]|"")*"'  # identificador citado
    r"|--[^\n]*"  # comentario de línea
    r"|/\*.*?\*/",  # comentario de bloque
    re.DOTALL,
)

# Adentro de un CTE convierten una lectura en escritura: `WITH borrados AS
# (DELETE … RETURNING id)` es SQL válido, y mirar sólo la primera palabra lo
# dejaría pasar.
PALABRAS_QUE_NO_SON_LECTURA = (
    "INSERT UPDATE DELETE MERGE TRUNCATE DROP CREATE ALTER GRANT REVOKE COPY "
    "CALL DO SET LOCK REFRESH VACUUM REINDEX CLUSTER ANALYZE COMMENT PREPARE "
    "EXECUTE DISCARD IMPORT NOTIFY LISTEN BEGIN COMMIT ROLLBACK SAVEPOINT"
).split()

# Los paréntesis se saltean: `(SELECT …) UNION (SELECT …)` es una lectura válida.
_PRIMERA_PALABRA = re.compile(r"[\s(]*(\w+)")


def revisar_forma(sql: str) -> Rechazada | None:
    """Una sola sentencia y de lectura, mirando el texto.

    Corre antes de abrir la conexión: el rol y la transacción ya son de sólo
    lectura, pero acá la escritura muere sin gastar conexión y con una sugerencia
    en vez de un error de Postgres.
    """
    cuerpo = _RUIDO.sub(" ", sql).strip().rstrip(";").strip()

    if ";" in cuerpo:
        return Rechazada(
            motivo="la consulta trae más de una sentencia",
            sugerencia=(
                "mandá una sola sentencia por llamada: sacá el `;` del medio y "
                "dejá sólo el `SELECT` que responde la pregunta"
            ),
        )

    if not cuerpo:
        return Rechazada(
            motivo="la consulta está vacía",
            sugerencia="mandá un `SELECT` con la consulta que querés ejecutar",
        )

    primera = _PRIMERA_PALABRA.match(cuerpo)
    if primera is None or primera.group(1).upper() not in ("SELECT", "WITH"):
        empieza = primera.group(1).upper() if primera else cuerpo[:12]
        return Rechazada(
            motivo=f"la consulta empieza con `{empieza}` y no es una lectura",
            sugerencia=(
                "reescribila como `SELECT …` o `WITH … SELECT …`: es lo único "
                "que se ejecuta, y el rol de la conexión es de sólo lectura"
            ),
        )

    escriben = [
        palabra
        for palabra in PALABRAS_QUE_NO_SON_LECTURA
        if re.search(rf"\b{palabra}\b", cuerpo, re.IGNORECASE)
    ]
    if escriben:
        return Rechazada(
            motivo=f"la consulta contiene {', '.join(f'`{p}`' for p in escriben)}",
            sugerencia=(
                "sacá esa parte y dejá sólo la lectura: un CTE que escribe "
                "(`WITH x AS (DELETE … RETURNING …)`) sigue siendo una escritura"
            ),
        )

    return None


def revisar_plan(plan: dict, tablas_grandes: set[str]) -> Rechazada | None:
    """Ningún `Seq Scan` sobre tabla grande y costo bajo el techo, sobre el nodo
    raíz del `EXPLAIN (FORMAT JSON)`.

    `tablas_grandes` entra por parámetro para que la función quede pura y el peor
    caso se pueda testear sin base; `ejecutar` lo resuelve por catálogo.
    """
    recorridas_enteras = sorted(
        {
            nodo["Relation Name"]
            for nodo in _nodos(plan)
            # `in` y no `==`: un `Parallel Seq Scan` recorre la tabla entera igual.
            if "Seq Scan" in nodo.get("Node Type", "")
            and nodo.get("Relation Name") in tablas_grandes
        }
    )
    if recorridas_enteras:
        cuales = ", ".join(f"`{t}`" for t in recorridas_enteras)
        return Rechazada(
            motivo=f"el plan recorre entera(s) {cuales}, que es tabla grande",
            sugerencia=(
                f"acotá el acceso a {cuales} con un filtro sobre una columna "
                f"indexada: el período con `>= %(desde)s AND < %(hasta)s`, o "
                f"`tenant_id = %(tenant)s`. Pedí `describe_table` para ver qué "
                f"índices hay antes de reescribirla"
            ),
        )

    costo = plan.get("Total Cost", 0.0)
    if costo > TECHO_DE_COSTO:
        return Rechazada(
            motivo=(
                f"el plan cuesta {costo:,.0f} y el techo es "
                f"{TECHO_DE_COSTO:,.0f}"
            ),
            sugerencia=(
                "achicá el trabajo estimado: acotá el período con `%(desde)s` y "
                "`%(hasta)s`, sacá los joins que no usás, y si tenés un CTE que "
                "se recalcula por fila declaralo `AS MATERIALIZED`"
            ),
        )

    return None


def _nodos(plan: dict):
    yield plan
    for hijo in plan.get("Plans", []):
        yield from _nodos(hijo)
