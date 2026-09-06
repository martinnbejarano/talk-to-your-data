"""D-04 escrito como test: toda cifra de la respuesta tiene que estar en una
consulta ejecutada. Función pura, corre con Postgres apagado.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from core.trazabilidad import cifras_sin_respaldo


def test_una_respuesta_que_cita_un_numero_que_no_esta_en_la_traza_no_pasa():
    """El caso que motivó la baranda: 1.847 es plausible y no salió de ninguna
    consulta."""
    contrato = {
        "respuesta": "Tenés 1.847 clientes de riesgo alto.",
        "derivacion": [],
    }
    resultados = [[(174_669, 7_859)]]

    sin_respaldo = cifras_sin_respaldo(contrato, resultados)

    assert [c.texto for c in sin_respaldo] == ["1.847"]


def test_la_fecha_de_corte_y_el_anio_no_son_cifras_a_verificar():
    """Una respuesta correcta nombra la fecha de corte y ni el día ni el año salen
    de una consulta: marcarlos convertiría cada respuesta buena en un falso
    positivo, y al validador en algo que se apaga."""
    contrato = {
        "respuesta": (
            "Al 1 de junio de 2026 hay 7.859 clientes de riesgo alto sobre "
            "174.669 clientes, y los casos se resuelven en 2,73 días."
        ),
        "derivacion": [],
    }
    resultados = [[(174_669, 7_859)], [(Decimal("2.73"),)]]

    assert cifras_sin_respaldo(contrato, resultados) == []


def test_un_identificador_no_es_una_cifra_a_verificar():
    """El criterio es estar pegado al texto: un número soldado a letras, a `#` o a
    un guion es un código; uno que se lee solo es una cantidad."""
    contrato = {
        "respuesta": "El caso #8891 y la alerta ALT-4472 quedaron sin revisar: son 12.",
        "derivacion": [],
    }

    assert cifras_sin_respaldo(contrato, [[(12,)]]) == []


def test_un_escalon_de_la_derivacion_tambien_tiene_que_estar_en_un_resultado():
    """Un escalón restado en Python es el número inventado más creíble de todos:
    viene formateado como parte de una cascada que cierra."""
    contrato = {
        "respuesta": "Son 7.859 clientes de riesgo alto.",
        "derivacion": [
            {"escalon": "activos", "texto": "activos (no dados de baja)", "n": 174_669},
            {"escalon": "por_score", "texto": "score ≥ umbral", "n": 5_399},
            {"escalon": "riesgo_alto", "texto": "= de riesgo alto", "n": 7_859},
        ],
    }
    resultados = [[(174_669, 7_859)]]

    sin_respaldo = cifras_sin_respaldo(contrato, resultados)

    assert [(c.donde, c.n) for c in sin_respaldo] == [
        ("derivacion.por_score", Decimal(5_399))
    ]


def test_el_valor_grande_y_los_numeros_de_las_opciones_se_verifican_igual():
    contrato = {
        "respuesta": "Depende de qué quieras contar.",
        "derivacion": [],
        "valor": {"n": 660, "unidad": "clientes PEP"},
        "opciones": [
            {"texto": "los que hoy figuran como PEP", "n": 660},
            {"texto": "los que alguna vez dieron positivo", "n": 2_161},
        ],
    }
    resultados = [[(660,)]]

    sin_respaldo = cifras_sin_respaldo(contrato, resultados)

    assert [(c.donde, c.n) for c in sin_respaldo] == [("opciones[1]", Decimal(2_161))]


def test_un_promedio_se_sostiene_con_el_redondeo_con_el_que_se_presenta():
    """Sin esta tolerancia el validador marcaría la única skill que no responde un
    conteo. Con ella tolera el redondeo y nada más: `2,80` sigue sin sostenerse."""
    promedio_crudo = [[(Decimal("2.7312894736842105"),)]]

    bien = {"respuesta": "Los casos se resuelven en 2,73 días.", "derivacion": []}
    assert cifras_sin_respaldo(bien, promedio_crudo) == []

    redondeado_de_mas = {
        "respuesta": "Los casos se resuelven en 2,80 días.",
        "derivacion": [],
    }
    assert [c.texto for c in cifras_sin_respaldo(redondeado_de_mas, promedio_crudo)] == [
        "2,80"
    ]


def test_una_fila_real_trae_texto_fechas_y_flags_y_ninguno_sostiene_un_numero():
    """Un `true` no sostiene un `1`: en Python un booleano es un entero, y sin
    decirlo el flag `is_current` respaldaría cualquier "1 cliente" que el modelo
    escriba."""
    fila = [("banco_andino", True, None, datetime.date(2026, 6, 1), 12)]

    doce = {"respuesta": "Quedaron 12 alertas sin revisar.", "derivacion": []}
    assert cifras_sin_respaldo(doce, [fila]) == []

    uno = {"respuesta": "Quedó 1 alerta sin revisar.", "derivacion": []}
    assert [c.texto for c in cifras_sin_respaldo(uno, [fila])] == ["1"]


def test_un_conteo_de_cuatro_digitos_sin_punto_de_miles_no_se_confunde_con_un_anio():
    """Un modelo escribe "1950 clientes" tan fácil como "1.950": un año se exime por
    la palabra que lo precede, no por tener cuatro dígitos."""
    contrato = {
        "respuesta": "En 2026 hubo 1950 clientes de riesgo alto.",
        "derivacion": [],
    }

    assert [c.texto for c in cifras_sin_respaldo(contrato, [[(7_859,)]])] == ["1950"]


def test_un_conteo_no_se_sostiene_con_un_valor_fraccionario_parecido():
    """La tolerancia es la del redondeo y un conteo no se redondea: si se aplicara
    igual, un `7.859,4` en la traza sostendría un "7.859" que nadie contó así."""
    contrato = {"respuesta": "Son 7.859 clientes de riesgo alto.", "derivacion": []}

    sin_respaldo = cifras_sin_respaldo(contrato, [[(Decimal("7859.4"),)]])

    assert [c.texto for c in sin_respaldo] == ["7.859"]
