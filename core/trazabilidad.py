"""Qué cifras de una respuesta no están sostenidas por una consulta ejecutada.

D-04 —*todo número tiene que salir de una consulta*— convertido en una propiedad
que el loop verifica antes de devolver el contrato, en vez de una instrucción que
el prompt pide y nadie comprueba.

## Qué cuenta como cifra a verificar, y qué no

Es lo que separa una baranda usable de una ruidosa: un validador que marca toda
respuesta correcta se termina apagando. Se verifica lo que la respuesta
**afirma**, y quedan afuera tres clases de número que no afirman nada: las
fechas (la de corte es obligatoria en la pantalla), los años **con su palabra
delante** —un año suelto sí se verifica, porque exceptuar todo entero de cuatro
dígitos dejaría pasar cualquier cifra escrita sin el punto de miles— y los
identificadores, que se reconocen por estar *soldados* al texto (`#8891`,
`ALT-4472`). El guion se lleva puestos de paso a los negativos, y está bien: las
cifras del dominio son conteos, montos y promedios, todos no negativos.

Entre marcar de más y dejar pasar un número inventado, D-04 elige marcar de más.
Un porcentaje se verifica como cualquier cifra —un "9,2 %" sacado de dividir dos
escalones es justo la aritmética que D-04 prohíbe—; `filas.total` no, porque no
es un valor que la consulta haya devuelto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

# Una cifra en es-AR: `7.859` con punto de miles, `2,73` con coma decimal.
_CIFRA = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")

_MESES = (
    "enero|febrero|marzo|abril|mayo|junio|julio|"
    "agosto|septiembre|setiembre|octubre|noviembre|diciembre"
)

# Se borra la fecha entera y no sólo el año, que es lo que saca de en medio al
# día: "1 de junio de 2026" tiene dos números que no son cantidades, no uno.
_FECHAS = re.compile(
    rf"\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}"
    rf"|\d{{1,2}}\s+de\s+(?:{_MESES})(?:\s+de\s+\d{{4}})?"
    rf"|(?:{_MESES})\s+de\s+\d{{4}}",
    re.IGNORECASE,
)

# Un token que mezcle dígitos con letras, `#`, `_` o guion se descarta entero.
_TOKEN = re.compile(r"[#\w.,-]+")
_ES_CODIGO = re.compile(r"[^\W\d_]|[#_-]")

# `de` y `del` quedan afuera a propósito: "un total de 1950 clientes" es una
# cantidad, y las fechas que sí usan "de" ya se fueron con `_FECHAS`.
_ANIO_CON_PISTA = re.compile(
    r"\b(?:año|anio|años|anios|ejercicio|en|desde|hasta|durante|para)\s+"
    r"(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CifraSinRespaldo:
    donde: str  # qué parte del contrato hay que corregir
    texto: str  # la cifra tal como se escribió
    n: Decimal


def cifras_sin_respaldo(
    contrato: dict, resultados: Iterable[Any]
) -> list[CifraSinRespaldo]:
    """Las cifras del contrato que ninguna consulta ejecutada sostiene.

    `resultados` son las **filas** de las consultas de esa conversación, en la
    forma que sea: se recorre en profundidad y se junta todo número. Filas y no
    los `Ok` enteros del seam de SQL, que traen además `ms` y el costo del
    `EXPLAIN` — una cifra sostenida por el costo del plan es exactamente lo que
    D-04 existe para impedir.
    """
    respaldo = _valores(list(resultados))
    return [
        CifraSinRespaldo(donde, texto, n)
        for donde, texto, n in _cifras_afirmadas(contrato)
        if not _sostenida(n, respaldo)
    ]


def _cifras_afirmadas(contrato: dict) -> list[tuple[str, str, Decimal]]:
    afirmadas = [
        ("respuesta", texto, n)
        for texto, n in _cifras_del_texto(contrato.get("respuesta") or "")
    ]

    # Los escalones se verifican igual que el texto: un escalón restado en Python
    # es el número inventado más creíble de todos, porque llega formateado como
    # parte de una cascada que cierra.
    for escalon in contrato.get("derivacion") or []:
        afirmadas += _cifra_del_campo(
            f"derivacion.{escalon.get('escalon')}", escalon
        )

    afirmadas += _cifra_del_campo("valor", contrato.get("valor") or {})
    for i, opcion in enumerate(contrato.get("opciones") or []):
        afirmadas += _cifra_del_campo(f"opciones[{i}]", opcion)

    return afirmadas


def _cifra_del_campo(donde: str, campo: dict) -> list[tuple[str, str, Decimal]]:
    n = campo.get("n")
    if n is None:
        return []
    return [(donde, str(n), Decimal(str(n)))]


def _cifras_del_texto(texto: str) -> list[tuple[str, Decimal]]:
    """Las cantidades que el texto afirma, ya descontadas fechas y códigos."""
    sin_fechas = _ANIO_CON_PISTA.sub(" ", _FECHAS.sub(" ", texto))
    sin_codigos = _TOKEN.sub(
        lambda m: " " if _ES_CODIGO.search(m.group()) else m.group(), sin_fechas
    )
    return [(m.group(), _numero(m.group())) for m in _CIFRA.finditer(sin_codigos)]


def _sostenida(n: Decimal, respaldo: set[Decimal]) -> bool:
    """Si algún valor consultado da `n` al redondearlo como `n` se presenta.

    La tolerancia es la del redondeo con el que se muestra el número y ni un
    dígito más: el promedio de resolución sale de un `avg` de dieciséis decimales
    y se presenta como `2,73`. Con más que esto, un número aproximado pasaría
    como exacto.
    """
    if n in respaldo:
        return True
    decimales = n.as_tuple().exponent
    if decimales >= 0:
        # Una cifra sin decimales no se redondeó al presentarla: si no está
        # exacta, no está.
        return False
    return any(
        v.quantize(Decimal(1).scaleb(decimales), rounding=ROUND_HALF_UP) == n
        for v in respaldo
    )


def _numero(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def _valores(estructura: Any) -> set[Decimal]:
    """Todo número que haya adentro, sin importar cómo esté anidado."""
    # `bool` es un `int` en Python: un `True` de una columna de flags sostendría
    # cualquier `1` de la respuesta.
    if isinstance(estructura, bool):
        return set()
    if isinstance(estructura, (int, float, Decimal)):
        return {Decimal(str(estructura))}
    if isinstance(estructura, dict):
        return {v for item in estructura.values() for v in _valores(item)}
    if isinstance(estructura, (list, tuple, set)):
        return {v for item in estructura for v in _valores(item)}
    return set()

