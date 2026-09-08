"""El seam alto: `responder(pregunta, institucion_id, historial)`.

Se afirma sólo lo observable (D-11): número, estado, escalones, institución.
Los dos tests `caro` llaman al modelo real —la spec del hito los pide por ese
seam, y la consistencia está medida en `NOTES/03-prototipo.md` §2.
"""

from __future__ import annotations

import yaml

import pytest

from agent import loop
from agent.loop import responder
from agent.tools import escalones_de
from core.config import RAIZ
from core.db.ejecucion import Ok

# Los esperados no se transcriben: los genera `evals/valores_esperados.yaml` por
# dos caminos independientes. Leerlo al colectar no toca la base.
_EVAL = yaml.safe_load((RAIZ / "evals" / "valores_esperados.yaml").read_text(encoding="utf-8"))
REFERENCIA = next(p for p in _EVAL["preguntas"] if p["concepto"] == "riesgo_alto")


def esperado_de(institucion_id: int) -> dict:
    """Lo que la pregunta de referencia tiene que dar en una institución."""
    return next(
        datos
        for datos in REFERENCIA["por_institucion"].values()
        if datos["tenant_id"] == institucion_id
    )


@pytest.fixture(params=["tenant_a", "tenant_b"])
def institucion(request) -> int:
    return request.getfixturevalue(request.param)


def test_la_derivacion_se_exige_y_no_se_espera():
    """El hallazgo §5.2 del prototipo hecho mecanismo: de ocho corridas con la
    definición delante, cuatro se comieron `total` y una devolvió cuatro de siete
    escalones. Pedirlo en el prompt no alcanzó."""
    ejecutada = Ok(filas=[(180000, 174669, 7859)], columnas=["a", "b", "c"], plan={}, ms=1.0)
    contrato = {
        "estado": "RESPONDIDA",
        "respuesta": "Tenemos 7.859 clientes de riesgo alto.",
        "valor": {"n": 7859, "unidad": "clientes"},
        "derivacion": [{"escalon": "riesgo_alto", "texto": "= riesgo alto", "n": 7859, "unidad": None}],
        "definiciones_usadas": [{"concepto": "riesgo_alto", "texto": "…"}],
    }

    reclamo = loop._lo_que_falta(contrato, {"riesgo_alto": escalones_de("riesgo_alto")}, [("…", ejecutada)])

    faltantes = [e for e in escalones_de("riesgo_alto") if e != "riesgo_alto"]
    assert all(f"`{escalon}`" in reclamo for escalon in faltantes), reclamo

    contrato["derivacion"] += [
        {"escalon": escalon, "texto": texto, "n": 174669, "unidad": None}
        for escalon, texto in escalones_de("riesgo_alto").items()
        if escalon != "riesgo_alto"
    ]
    assert loop._lo_que_falta(contrato, {"riesgo_alto": escalones_de("riesgo_alto")}, [("…", ejecutada)]) == ""


def test_las_filas_y_el_detalle_tecnico_los_pone_el_sistema_y_no_el_modelo():
    """`filas` sale de la última consulta con más de una fila —la cascada viene en
    una sola y no es una tabla que mostrar—; si la escribiera el modelo serían
    cinco filas verosímiles que nadie devolvió. Sin mapeo del modelo no hay
    gráfico, que es el caso de las 33 preguntas del set."""
    tabla = Ok(filas=[("AR", 7000), ("UY", 859)], columnas=["pais", "n"], plan={"a": 1}, ms=3.0)
    cascada = Ok(filas=[(180000, 7859)], columnas=["total", "riesgo_alto"], plan={"b": 2}, ms=4.0)

    contrato = loop._completar({}, [("SELECT … pais", tabla), ("SELECT … cascada", cascada)])

    assert contrato["filas"] == {"columnas": ["pais", "n"], "muestra": [["AR", 7000], ["UY", 859]], "total": 2}
    assert [q["sql"] for q in contrato["queries"]] == ["SELECT … pais", "SELECT … cascada"]
    assert [q["plan"] for q in contrato["queries"]] == [{"a": 1}, {"b": 2}]
    assert contrato["grafico"] is None


def test_el_mapeo_que_escribe_el_modelo_sale_del_loop_con_los_numeros_de_la_base():
    """El seam entre el loop y `core/grafico.py`: el modelo nombró dos columnas y
    el contrato sale con los puntos que devolvió Postgres. `filas.muestra` sigue
    siendo la muestra —el gráfico no la usa— y por eso las dos cosas no se pisan."""
    serie = Ok(
        filas=[("2026-01", 1240), ("2026-02", 1105)],
        columnas=["mes", "altas"],
        plan={"a": 1},
        ms=3.0,
    )

    contrato = loop._completar(
        {"grafico": {"x": "mes", "y": "altas", "unidad": "clientes"}}, [("SELECT … mes", serie)]
    )

    assert contrato["grafico"]["marca"] == "linea"
    assert contrato["grafico"]["puntos"] == [["2026-01", "1240"], ["2026-02", "1105"]]
    assert contrato["filas"]["total"] == 2


def test_al_agotarse_el_tope_de_pasos_la_respuesta_sale_explicada_y_sin_numero(
    institucion, monkeypatch
):
    """El tope se lleva a cero para ejercer la salida sin depender de que el modelo
    se trabe. Sin número adentro: sería la única cifra del sistema sin una
    consulta que la sostenga."""
    monkeypatch.setattr(loop, "TOPE_DE_PASOS", 0)

    contrato = responder("¿Cuántos clientes de riesgo alto tenemos?", institucion)

    assert contrato["estado"] == "NO_SE_PUEDE_RESPONDER"
    assert contrato["valor"] is None
    assert not any(c.isdigit() for c in contrato["respuesta"])
    assert contrato["grafico"] is None and contrato["traza_id"].startswith("tz_")


@pytest.mark.caro
def test_la_pregunta_de_referencia_da_el_numero_y_la_derivacion_de_su_institucion(
    institucion,
):
    """El criterio de aceptación del hito. Las dos instituciones contrastan a
    propósito: en una la perilla de PEP está prendida y en la otra apagada, así
    que olvidarse del tercer escalón daría bien en una y mal en la otra."""
    esperado = esperado_de(institucion)

    contrato = responder(REFERENCIA["pregunta"], institucion)

    assert contrato["estado"] in loop.RESPONDIDAS, contrato["respuesta"]
    assert contrato["valor"]["n"] == esperado["valor_esperado"]
    assert contrato["valor"]["unidad"], "el número salió sin unidad"
    assert {e["escalon"]: e["n"] for e in contrato["derivacion"]} == esperado["derivacion"]
    assert [d["concepto"] for d in contrato["definiciones_usadas"]] != []
    assert contrato["exclusiones"], "no declaró qué quedó afuera"
    assert contrato["queries"], "el detalle técnico salió sin la consulta"
    assert set(contrato) == {
        "estado", "respuesta", "valor", "derivacion", "definiciones_usadas",
        "exclusiones", "filas", "supuestos", "opciones", "queries", "grafico", "traza_id",
    }, "el contrato no salió completo, y el front lee campos y no texto libre"


@pytest.mark.caro
def test_la_institucion_no_se_deduce_del_texto_aunque_la_pregunta_nombre_otra(
    tenant_a, tenant_b
):
    """D-14: nombrar otra institución tiene que negarse, no contestarse con el
    número propio como si fuera lo pedido. Antes de este arreglo el sistema
    hacía justo eso —"Fintech Cuyo tiene 7.859 clientes", el número de
    banco_andino— y no era una fuga (el RLS no dejó leer ninguna fila ajena)
    pero salía con la cara de una respuesta correcta."""
    slug_ajeno = next(
        slug for slug, datos in REFERENCIA["por_institucion"].items() if datos["tenant_id"] == tenant_b
    )

    contrato = responder(f"¿Cuántos clientes de riesgo alto tiene {slug_ajeno}?", tenant_a)

    assert contrato["estado"] == "NO_SE_PUEDE_RESPONDER"
    assert contrato["valor"] is None
