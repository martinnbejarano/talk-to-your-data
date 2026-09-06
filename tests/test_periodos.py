""""Este año" y "último trimestre" contra la fecha de corte, nunca contra el reloj.

Función pura: corre con Postgres apagado.
"""

from __future__ import annotations

import pytest

from core.periodos import resolver_periodo


def test_este_anio_va_del_primero_de_enero_a_la_fecha_de_corte():
    assert resolver_periodo("este año") == ("2026-01-01", "2026-06-01")


def test_el_ultimo_trimestre_es_el_calendario_anterior_al_del_corte():
    """`2026-04-01` es el límite **excluido**: escribirlo cerrado, `2026-03-31`,
    nombra la misma ventana pero invita a un `<=` que en un campo con hora deja
    afuera casi todo el 31 de marzo."""
    assert resolver_periodo("último trimestre") == ("2026-01-01", "2026-04-01")


def test_la_unica_referencia_temporal_es_el_corte_que_se_le_pasa():
    """Un corte de febrero es el caso interesante: el último trimestre cerrado queda
    en el año anterior."""
    assert resolver_periodo("este año", "2025-02-14") == ("2025-01-01", "2025-02-14")
    assert resolver_periodo("último trimestre", "2025-02-14") == (
        "2024-10-01",
        "2025-01-01",
    )


@pytest.mark.parametrize("mes_fiscal", range(1, 13))
def test_el_anio_fiscal_de_la_institucion_no_mueve_ningun_periodo(mes_fiscal):
    """`fiscal_year_start_month` es un distractor: toma cinco valores en la base y
    ninguno redefine períodos que son de calendario (`CONTEXT.md`)."""
    assert resolver_periodo("este año", fiscal_year_start_month=mes_fiscal) == (
        "2026-01-01",
        "2026-06-01",
    )
    assert resolver_periodo(
        "último trimestre", fiscal_year_start_month=mes_fiscal
    ) == ("2026-01-01", "2026-04-01")


@pytest.mark.parametrize(
    "escrito_asi, mismo_que",
    [
        ("este_año", "este año"),          # la clave de las nueve skills
        ("Este Año", "este año"),          # el modelo escribe con mayúscula
        ("este ano", "este año"),          # y a veces sin la eñe
        ("ultimo_trimestre", "último trimestre"),
        ("ultimo trimestre", "último trimestre"),
        ("Último Trimestre", "último trimestre"),
    ],
)
def test_las_variantes_de_escritura_nombran_el_mismo_periodo(escrito_asi, mismo_que):
    """`core/semantics/*.yaml` declara `periodo_por_defecto: este_año`; el agente
    escribe "este año". Sin unirlas acá, cada llamador normalizaría por su cuenta."""
    assert resolver_periodo(escrito_asi) == resolver_periodo(mismo_que)


def test_un_periodo_que_no_conoce_no_se_resuelve_al_que_tenga_mas_a_mano():
    """El error tiene que llegar hasta arriba: un período mal resuelto no rompe nada
    visible, devuelve un número plausible sobre otra ventana de tiempo."""
    with pytest.raises(ValueError, match="el mes pasado"):
        resolver_periodo("el mes pasado")
