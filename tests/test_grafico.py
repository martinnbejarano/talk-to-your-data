"""D-19 escrito como test: se dibuja una serie, y sólo si se puede dibujar sin
mentir. Función pura, corre con Postgres apagado y sin API.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from core.grafico import TOPE_DE_PUNTOS, grafico_de

MAPEO = {"x": "mes", "y": "altas", "unidad": "clientes"}

CASCADA = (["total", "riesgo_alto"], [(180_000, 7_859)])

MESES = (
    ["mes", "altas"],
    [
        (datetime.date(2026, 1, 1), 1_240),
        (datetime.date(2026, 2, 1), 1_105),
        (datetime.date(2026, 3, 1), 998),
    ],
)


def test_una_serie_temporal_se_dibuja_como_linea_con_todos_sus_puntos():
    """El caso que motiva todo esto. Los puntos salen de las filas y no de
    `filas.muestra`, que son cinco: doce barras tienen que significar doce meses y
    no "los doce que entraron"."""
    grafico = grafico_de(MAPEO, [MESES, CASCADA])

    assert grafico["marca"] == "linea"
    assert grafico["unidad"] == "clientes"
    assert grafico["puntos"] == [
        ["2026-01-01", "1240"],
        ["2026-02-01", "1105"],
        ["2026-03-01", "998"],
    ]


def test_una_serie_por_categoria_se_dibuja_como_barras():
    """Una línea entre "cerrada" y "escalada" sugiere una continuidad que no
    existe: no hay nada en el medio."""
    estados = (["estado", "alertas"], [("CERRADA", 4_120), ("ESCALADA", 806)])

    grafico = grafico_de({"x": "estado", "y": "alertas", "unidad": "alertas"}, [estados])

    assert grafico["marca"] == "barras"
    assert grafico["puntos"] == [["CERRADA", "4120"], ["ESCALADA", "806"]]


def test_un_mes_agrupado_como_texto_tambien_es_una_serie_temporal():
    """`to_char(fecha, 'YYYY-MM')` es lo que el modelo escribe de verdad al agrupar
    por mes, y llega como texto. Leer sólo el tipo de Python daría barras sobre doce
    meses y taparía la tendencia, que es lo único que una serie temporal muestra."""
    por_mes = (["mes", "altas"], [("2026-01", 3_621), ("2026-02", 3_281)])

    assert grafico_de(MAPEO, [por_mes])["marca"] == "linea"


def test_una_serie_por_moneda_no_se_dibuja_aunque_el_modelo_la_declare():
    """D-08 dibujado, y el motivo por el que la regla dejó de ser "un panel por
    moneda": compartir el eje de valores es sumar visualmente lo que los números no
    suman, y partirlo daría cuatro paneles de una barra cada uno."""
    monedas = (
        ["moneda", "monto"],
        [("ARS", Decimal("1204500.30")), ("USD", Decimal("340210.00"))],
    )

    assert grafico_de({"x": "moneda", "y": "monto", "unidad": "monto"}, [monedas]) is None


def test_una_serie_particionada_por_otra_dimension_no_se_dibuja():
    """`mes, moneda, monto` trae dos filas por mes. Dibujarla sin partirla apilaría
    monedas en un eje, que es D-08; lo que la delata es que el valor horizontal se
    repite, no que haya una tercera columna."""
    por_mes_y_moneda = (
        ["mes", "moneda", "monto"],
        [
            (datetime.date(2026, 1, 1), "ARS", 12),
            (datetime.date(2026, 1, 1), "USD", 8),
            (datetime.date(2026, 2, 1), "ARS", 15),
            (datetime.date(2026, 2, 1), "USD", 9),
        ],
    )

    assert grafico_de({"x": "mes", "y": "monto", "unidad": "monto"}, [por_mes_y_moneda]) is None


def test_la_serie_y_los_escalones_pueden_venir_en_la_misma_consulta():
    """El caso normal de este sistema, y el que la regla anterior mataba: el modelo
    devuelve los escalones que `_lo_que_falta` le exige **y** la serie en una sola
    consulta. Diez columnas y una sola pasada por la tabla es lo que conviene."""
    con_cascada = (
        ["mes", "total", "activos", "aprobados", "altas_del_periodo"],
        [
            (datetime.date(2026, 1, 1), 180_000, 174_669, 107_250, 3_621),
            (datetime.date(2026, 2, 1), 180_000, 174_669, 107_250, 3_281),
        ],
    )

    grafico = grafico_de(
        {"x": "mes", "y": "altas_del_periodo", "unidad": "clientes"}, [con_cascada]
    )

    assert grafico["marca"] == "linea"
    assert grafico["puntos"] == [["2026-01-01", "3621"], ["2026-02-01", "3281"]]


def test_pasado_el_tope_de_puntos_no_hay_grafico_y_no_se_recorta():
    """Doscientas barras son una textura, y un bucket "otros" que recorte la cola
    sería una suma hecha por la pantalla en vez de por una consulta (D-04)."""
    largo = (
        ["mes", "altas"],
        [(datetime.date(2020, 1, 1) + datetime.timedelta(days=i), i) for i in range(TOPE_DE_PUNTOS + 1)],
    )

    assert grafico_de(MAPEO, [largo]) is None


def test_una_serie_demasiado_larga_no_habilita_a_dibujar_una_mas_vieja():
    """Cortar en la primera coincidencia es deliberado: la serie vieja contestaría
    una pregunta distinta de la que el agente terminó haciendo."""
    largo = (
        ["mes", "altas"],
        [(datetime.date(2020, 1, 1) + datetime.timedelta(days=i), i) for i in range(TOPE_DE_PUNTOS + 1)],
    )

    assert grafico_de(MAPEO, [MESES, largo]) is None


def test_un_eje_vertical_que_no_es_numerico_no_se_dibuja():
    """Sin esto, una columna de texto se dibujaría como una fila de barras de altura
    cero y el oficial leería "no hubo ninguna" donde no hubo medición."""
    texto = (["mes", "altas"], [("2026-01", "muchas"), ("2026-02", "pocas")])

    assert grafico_de(MAPEO, [texto]) is None


def test_un_booleano_no_cuenta_como_cantidad():
    """`bool` es subclase de `int`: sin la exclusión, dos barras de altura 1 y 0
    serían un conteo que nadie contó."""
    banderas = (["mes", "altas"], [("2026-01", True), ("2026-02", False)])

    assert grafico_de(MAPEO, [banderas]) is None


def test_una_columna_que_el_modelo_nombro_y_no_existe_no_se_dibuja():
    """El mapeo lo escribe el modelo y puede estar mal. Cualquier duda es `None`:
    un gráfico de menos cuesta una lectura, uno de más es una afirmación que nadie
    sostiene."""
    assert grafico_de({"x": "trimestre", "y": "altas", "unidad": "clientes"}, [MESES]) is None


def test_sin_mapeo_del_modelo_no_hay_grafico():
    """El caso normal de las 33 preguntas del set: ninguna es una serie, y el campo
    sale en `null` sin que nadie haga nada."""
    assert grafico_de(None, [MESES]) is None
    assert grafico_de({}, [MESES]) is None


def test_una_cascada_de_una_sola_fila_no_es_una_serie():
    """Los escalones vienen en una sola fila. Ahí no hay serie que dibujar: eso ya
    está dibujado, y es la derivación."""
    una_fila = (["mes", "altas"], [(datetime.date(2026, 1, 1), 1_240)])

    assert grafico_de(MAPEO, [una_fila]) is None
