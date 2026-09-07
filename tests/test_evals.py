"""El calificador del eval, ejercido sin llamar al modelo ni tocar la base.

El runner es código determinístico, así que se testea como código (D-11). Lo que
se verifica es que **repruebe**: un calificador que aprueba todo convierte al set
en un adorno, y esa falla es silenciosa —el reporte sale en verde— así que no la
atrapa ninguna corrida.

Los contratos son sintéticos y sus números salen de `valores_esperados.yaml`: si
se escribieran a mano, el test mediría contra una transcripción vieja, que es
justo lo que el hito evita.
"""

from __future__ import annotations

import copy

import pytest

from evals import mutaciones, run

ESPERADOS = run.cargar("valores_esperados.yaml")
PREGUNTAS = run.cargar("questions.yaml")["preguntas"]
POR_ID = {p["id"]: p for p in PREGUNTAS}


def contrato_de(id_: str) -> dict:
    """El contrato que esa pregunta contestada bien produciría."""
    pregunta = POR_ID[id_]
    concepto = pregunta["valor_esperado"]["concepto"]
    slug = pregunta["institucion"]
    derivacion = run.derivacion_esperada(concepto, slug, ESPERADOS)
    return {
        "estado": "RESPONDIDA_CON_SUPUESTO",
        "respuesta": "…",
        "valor": {"n": run.valor_esperado(pregunta["valor_esperado"], slug, ESPERADOS), "unidad": "clientes"},
        "derivacion": [{"escalon": e, "texto": "…", "n": n} for e, n in derivacion.items()],
        "definiciones_usadas": [{"concepto": c} for c in pregunta.get("debe_mencionar", [])],
        "exclusiones": ["clientes dados de baja"],
        "supuestos": ["…"],
        "opciones": [],
        "filas": {"columnas": ["a"], "muestra": [["x"]], "total": 1},
        "queries": [],
        "grafico": None,
        "traza_id": "tz_test",
    }


def test_ninguna_pregunta_repite_la_clase_de_otra():
    """La regla del mini-plan: dos preguntas con la misma clase, una se borra.
    Sin esto el set crece con variantes que aportan una observación repetida y
    dan la sensación de cobertura."""
    clases = [p["clase"] for p in PREGUNTAS]
    repetidas = {c for c in clases if clases.count(c) > 1}

    assert not repetidas, f"clases repetidas: {sorted(repetidas)}"
    assert len({p["id"] for p in PREGUNTAS}) == len(PREGUNTAS), "hay ids repetidos"


def test_todo_valor_esperado_del_set_se_resuelve_contra_el_yaml_de_dos_caminos():
    """Ningún número del set está escrito a mano: todos son una referencia. Un
    concepto mal tipeado tiene que romper acá y no en mitad de una corrida
    paga."""
    for pregunta in PREGUNTAS:
        slug = pregunta["institucion"]
        run.institucion_de(slug, ESPERADOS)
        refs = [pregunta.get("valor_esperado")] + list(pregunta.get("valores_admisibles") or [])
        refs += [t["valor"] for t in pregunta.get("historial") or [] if "valor" in t]
        for ref in [r for r in refs if r]:
            assert run.valor_esperado(ref, slug, ESPERADOS) is not None, pregunta["id"]


def test_un_contrato_correcto_aprueba_y_el_mismo_con_el_numero_movido_no():
    contrato = contrato_de("c-002")

    assert run.califica(POR_ID["c-002"], contrato, ESPERADOS) == []

    contrato["valor"]["n"] = contrato["valor"]["n"] + 1
    assert run.califica(POR_ID["c-002"], contrato, ESPERADOS)


def test_el_numero_correcto_con_la_derivacion_incompleta_reprueba():
    """El hallazgo de H3 hecho criterio: dos caminos distintos llegan a 7.859 y
    sólo uno se puede explicar. Un escalón faltante no es un detalle de formato,
    es la mitad de la respuesta."""
    contrato = contrato_de("c-002")
    contrato["derivacion"] = contrato["derivacion"][:2]

    motivos = run.califica(POR_ID["c-002"], contrato, ESPERADOS)

    assert any("escalones" in m for m in motivos), motivos


def test_una_cifra_de_la_otra_institucion_en_la_respuesta_es_fuga():
    """El aislamiento lo garantiza el RLS: una consulta no puede traer filas
    ajenas. Lo que esta métrica atrapa es lo que el RLS no puede impedir, que el
    modelo escriba un número que no consultó."""
    ajeno = run.valor_esperado({"concepto": "riesgo_alto"}, "fintech_cuyo", ESPERADOS)
    contrato = contrato_de("c-002")
    contrato["opciones"] = [{"texto": "en la otra institución", "n": ajeno}]

    assert run.fugas_de(POR_ID["c-002"], contrato, ESPERADOS) == [str(ajeno)]
    assert run.fugas_de(POR_ID["c-002"], contrato_de("c-002"), ESPERADOS) == []


def test_una_incontestable_contestada_reprueba_y_se_clasifica_como_tal():
    contrato = contrato_de("c-002") | {"estado": "RESPONDIDA"}

    motivos = run.califica(POR_ID["i-008"], contrato, ESPERADOS)

    assert motivos
    assert run.clasifica_falla(POR_ID["i-008"], contrato, {}, motivos) == "incontestable_respondida"


def test_repreguntar_una_pregunta_clara_es_falsa_ambiguedad_y_no_un_acierto():
    """Un sistema que repregunta todo el tiempo se abandona igual que uno que
    inventa, y no lo atrapa ningún criterio obvio."""
    contrato = contrato_de("c-013") | {"estado": "NECESITO_QUE_ACLARES"}

    motivos = run.califica(POR_ID["c-013"], contrato, ESPERADOS)

    assert motivos
    assert run.clasifica_falla(POR_ID["c-013"], contrato, {}, motivos) == "falsa_ambiguedad"


def test_una_ambigua_contestada_con_un_universo_que_nadie_ofrecio_reprueba():
    """A las ambiguas no se les pide acertar un número, pero sí que el número que
    eligen sea una de las lecturas: si no, eligió una tercera cosa."""
    pregunta = POR_ID["a-002"]
    contrato = contrato_de("c-002") | {"estado": "RESPONDIDA_CON_SUPUESTO", "derivacion": []}
    universo = run.valor_esperado({"concepto": "cliente_onboardeado", "escalon": "activos"}, "banco_andino", ESPERADOS)

    contrato["valor"] = {"n": universo, "unidad": "clientes"}
    assert run.califica(pregunta, contrato, ESPERADOS) == []

    contrato["valor"] = {"n": universo + 7, "unidad": "clientes"}
    assert run.califica(pregunta, contrato, ESPERADOS)


@pytest.mark.parametrize("nombre", sorted(mutaciones.MUTACIONES), ids=sorted(mutaciones.MUTACIONES))
def test_cada_mutacion_apunta_a_preguntas_que_existen_y_deja_las_skills_como_estaban(nombre):
    """Una mutación que apunta a un id inexistente correría cero preguntas y
    reportaría que el set tiene un agujero que no tiene."""
    mutacion = mutaciones.MUTACIONES[nombre]
    assert set(mutacion.debe_romper) <= set(POR_ID), mutacion.debe_romper

    from agent.tools import _skills

    antes = copy.deepcopy(_skills())
    with mutaciones.aplicada(nombre) as aplicada:
        assert aplicada is mutacion
        assert _skills() != antes or mutacion.usa_el_reloj, "la mutación no cambió nada"

    assert _skills() == antes, "la skill quedó rota para el proceso que siga"
