"""Cuándo una respuesta se puede dibujar, y con qué.

D-19 —*el gráfico es la forma de una respuesta que ya era una serie*— convertido
en una función que el loop llama antes de entregar el contrato, en vez de una
instrucción que el prompt pide y nadie comprueba. Vive acá y no en `agent/loop.py`
por la misma razón que `core/trazabilidad.py`: es una propiedad sobre datos, se
prueba sin API y sin Postgres, y el ciclo de function calling no tiene por qué
crecer con ella. Del loop se tocan cuatro líneas, y las tres piezas que necesita
—el fragmento del contrato, la regla del prompt y esta función— salen de acá.

## Qué se le deja decidir al modelo, y qué no

El modelo nombra tres cosas —qué columna va en el eje horizontal, cuál en el
vertical y qué se cuenta— y **ningún número**: los puntos los copia esta función
de las filas que devolvió Postgres. Un punto inventado no queda prohibido por una
regla del prompt: queda imposible, que es la misma estrategia con la que se
defiende D-04. Por eso `cifras_sin_respaldo` no tiene que aprender a mirar el
gráfico.

Todo lo demás lo decide el código, y ante cualquier duda la respuesta es `None`:
se contesta sin dibujo. Un gráfico de menos cuesta una lectura; uno de más es una
afirmación que nadie sostiene.

## Por qué los puntos viajan como texto

Igual que en `filas.muestra`, un `Decimal` va como texto y no como `float`:
redondearlo es inventar un número. La pantalla hace `Number()` sobre el valor
**sólo para calcular la altura de la barra**, y muestra el texto tal cual en la
tabla de abajo. El número que se lee es exacto; el que se dibuja es aproximado,
que es lo que un píxel puede ser de todos modos.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Sequence

__all__ = ["CAMPO_DEL_CONTRATO", "REGLA", "TOPE_DE_PUNTOS", "grafico_de"]

# Treinta barras todavía se leen de un vistazo; doscientas son una textura. Y no
# hay bucket "otros" que recorte la cola: esa suma la haría la pantalla y no una
# consulta, que es exactamente lo que prohíbe D-04.
TOPE_DE_PUNTOS = 30

# Una serie cuyo eje horizontal son monedas es D-08 puesto en un eje: un pico en
# pesos aplasta al dólar contra el piso y el ojo lee "no hubo dólares". No se
# dibuja. El desglose por moneda sigue siendo la respuesta correcta a "¿cuánto
# transamos?" — lo que no es, es un gráfico.
_MONEDA = re.compile(r"^[A-Z]{3}$")

_NUMEROS = (int, float, Decimal)

# Un `date` llega como `date`, pero un `to_char(fecha, 'YYYY-MM')` llega como
# texto, y es lo que el modelo escribe cuando agrupa por mes. Las dos cosas son
# temporales y las dos van en línea: leerlo sólo del tipo de Python daría barras
# sobre doce meses, que es justo lo que tapa la tendencia.
_FECHA_EN_TEXTO = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


# El fragmento que se enchufa en `CONTRATO`. El modelo escribe el mapeo y nada
# más: `marca` y `puntos` los agrega `grafico_de`, así que no están acá.
CAMPO_DEL_CONTRATO = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["x", "y", "unidad"],
    "properties": {
        "x": {"type": "string"},
        "y": {"type": "string"},
        "unidad": {"type": "string"},
    },
}


# Pasiva a propósito: no le pide ninguna consulta de más. Una serie necesitaría
# dos —la cascada con todos los escalones en una fila, y la agrupada—, contra un
# tope de doce pasos y un gate que rechaza justo la forma agrupada. El gráfico
# nunca puede costar la respuesta.
REGLA = """\
8. Si alguna consulta que ejecutaste devolvió **una fila por categoría** —una por
   mes, una por estado, una por tipo— **declarala en `grafico`**: `x` es el nombre
   de la columna que tiene la categoría, `y` el de la que tiene el número que
   estás contestando, y `unidad` qué se cuenta. Vale igual si esa consulta trae
   además los escalones de la cascada: lo que importa es que haya una fila por
   categoría. Nombrás columnas y nunca valores; los números los copia el sistema
   de las filas que devolvió la base. **No ejecutes ninguna consulta de más para
   esto**: si ninguna de las que corriste devolvió una serie, `grafico` va en
   `null`."""


def grafico_de(
    mapeo: dict | None, consultas: Iterable[tuple[Sequence[str], Sequence[Sequence]]]
) -> dict | None:
    """El gráfico dibujable que declaró el modelo, o `None` si no hay ninguno.

    `consultas` son los `(columnas, filas)` de lo que se ejecutó, en orden. Se
    busca de atrás para adelante, igual que `filas`: la última serie es la que el
    agente fue a buscar.
    """
    if not mapeo:
        return None

    x, y, unidad = mapeo.get("x"), mapeo.get("y"), mapeo.get("unidad")
    if not (x and y and unidad) or x == y:
        return None

    for columnas, filas in reversed(list(consultas)):
        if x not in columnas or y not in columnas or len(filas) <= 1:
            continue
        return _dibujable(filas, columnas.index(x), columnas.index(y), x, y, unidad)

    return None


def _dibujable(filas, ix: int, iy: int, x: str, y: str, unidad: str) -> dict | None:
    """La serie encontrada, si pasa las cinco pruebas que quedan. Cortar acá y no
    seguir buscando es deliberado: la consulta que nombra las dos columnas es la
    que el modelo quiso graficar, y una serie más vieja contestaría otra pregunta.

    La consulta puede traer más columnas que las dos: lo normal en este sistema es
    que el modelo devuelva los escalones de la cascada **y** la serie en una sola
    consulta, porque `_lo_que_falta` le exige los escalones igual. Eso está bien y
    conviene: son diez columnas y una sola pasada por la tabla.
    """
    horizontales = [fila[ix] for fila in filas]
    verticales = [fila[iy] for fila in filas]

    if len(filas) > TOPE_DE_PUNTOS:
        return None
    if any(v is None for v in horizontales):
        return None
    # **Una fila por categoría, y sólo una.** Si el valor horizontal se repite, la
    # serie está partida por otra dimensión que no se está dibujando —el caso
    # típico es `mes, moneda, monto`— y las barras sumarían visualmente lo que los
    # números no suman. Es D-08, y es la prueba que reemplazó a "exactamente dos
    # columnas", que además de gruesa mataba el caso normal.
    if len(set(map(str, horizontales))) != len(horizontales):
        return None
    # `bool` es subclase de `int` y no es una cantidad: dos barras de altura 1 y 0
    # sobre "sí" y "no" serían un conteo que nadie contó.
    if not all(isinstance(v, _NUMEROS) and not isinstance(v, bool) for v in verticales):
        return None
    if all(isinstance(v, str) and _MONEDA.match(v) for v in horizontales):
        return None

    return {
        "x": x,
        "y": y,
        "unidad": unidad,
        "marca": _marca(horizontales[0]),
        "puntos": [[str(h), str(v)] for h, v in zip(horizontales, verticales)],
    }


def _marca(primero: Any) -> str:
    """Barras o línea, deducido y no elegido: el tipo del valor ya lo dice. Una
    línea entre categorías sugiere una continuidad que no existe —¿qué hay entre
    "cerrada" y "escalada"?—, y barras sobre doce meses tapan la tendencia, que es
    lo único que una serie temporal tiene para mostrar.

    Sale del valor y no de los tipos de Postgres: es la misma información y no
    obliga a `Ok` a acarrear los OID de columna.
    """
    if isinstance(primero, (date, datetime)):
        return "linea"
    if isinstance(primero, str) and _FECHA_EN_TEXTO.match(primero):
        return "linea"
    return "barras"
