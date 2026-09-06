"""Los dos períodos con nombre, resueltos contra la fecha de corte.

No mira el reloj —en este dataset "hoy" es el 1 de junio de 2026 y `now()`
devolvería cero filas sin avisar (`CONTEXT.md`)— y los intervalos son
semiabiertos `[desde, hasta)`, como los filtran las nueve goldens: un `<=` sobre
un campo con hora deja afuera casi todo el último día.

    resolver_periodo("este año")         -> ("2026-01-01", "2026-06-01")
    resolver_periodo("último trimestre") -> ("2026-01-01", "2026-04-01")
"""

from __future__ import annotations

import datetime
import unicodedata

from core.config import AS_OF

ESTE_ANIO = "este_ano"
ULTIMO_TRIMESTRE = "ultimo_trimestre"

# Los dos que las nueve skills declaran en `periodo_por_defecto` y que define
# `CONTEXT.md`. Cualquier otro se rechaza en vez de aproximarse.
CONOCIDOS = (ESTE_ANIO, ULTIMO_TRIMESTRE)


def _clave(expresion: str) -> str:
    """"Este Año", "este_año" y "este ano" son la misma cosa."""
    sin_tildes = unicodedata.normalize("NFD", expresion.strip().lower())
    sin_combinantes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return sin_combinantes.replace(" ", "_")


def resolver_periodo(
    expresion: str,
    corte: str = AS_OF,
    fiscal_year_start_month: int | None = None,
) -> tuple[str, str]:
    """El intervalo semiabierto `[desde, hasta)` que nombra `expresion`.

    `fiscal_year_start_month` se recibe y **no se usa**, a propósito: es un
    parámetro real de cada institución y su nombre invita a creer que corre "este
    año", pero los dos períodos son de calendario.
    """
    clave = _clave(expresion)
    if clave not in CONOCIDOS:
        # Un período mal resuelto no rompe nada visible: devuelve un número
        # plausible sobre otra ventana de tiempo. Por eso corta en vez de elegir.
        raise ValueError(
            f"No sé resolver el período {expresion!r}. Los que conozco son "
            f"{', '.join(CONOCIDOS)}."
        )

    fin = datetime.date.fromisoformat(corte)

    if clave == ESTE_ANIO:
        return (fin.replace(month=1, day=1).isoformat(), fin.isoformat())

    # El último trimestre de calendario que terminó, no el que contiene al corte:
    # contar uno en curso da un número que crece cada día que pasa.
    hasta = datetime.date(fin.year, (fin.month - 1) // 3 * 3 + 1, 1)
    desde = datetime.date(hasta.year - (hasta.month == 1), (hasta.month - 4) % 12 + 1, 1)
    return (desde.isoformat(), hasta.isoformat())
