"""Los tres endpoints, cruzados por HTTP con `TestClient`.

Lo único que `TestClient` no da es el socket, y levantar uvicorn para tenerlo
compraría un test flaky a cambio de nada.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from api import main
from api.main import app
from conftest import conectar_como_admin
from core.config import RAIZ

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


@pytest.fixture(scope="module")
def cliente() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def respuestas(cliente, tenant_a, tenant_b) -> dict:
    """De módulo y no de función: son dos llamadas al modelo real, entre 13 y 20
    segundos y unos ocho centavos cada una, y los dos tests `caro` miran cosas
    distintas de las mismas dos respuestas."""
    return {
        institucion: cliente.post(
            "/ask",
            json={"institucion_id": institucion, "pregunta": REFERENCIA["pregunta"]},
        )
        for institucion in (tenant_a, tenant_b)
    }


def test_el_selector_trae_las_instituciones_elegibles_y_ninguna_dada_de_baja(
    cliente, tenant_a, tenant_b
):
    """`GET /instituciones` llena el selector, y el selector es D-03. Las inactivas
    quedan afuera: el dump trae un banco en liquidación y una fintech legacy."""
    with conectar_como_admin() as conn:
        de_baja = [t for (t,) in conn.execute("SELECT id FROM tenants WHERE NOT is_active")]

    respuesta = cliente.get("/instituciones")
    instituciones = respuesta.json()

    assert respuesta.status_code == 200
    ids = [i["institucion_id"] for i in instituciones]
    assert tenant_a in ids and tenant_b in ids
    assert not (set(ids) & set(de_baja)), "el selector ofrece instituciones dadas de baja"
    assert all(set(i) == {"institucion_id", "slug", "nombre"} for i in instituciones)


def test_la_institucion_sale_del_request_y_nunca_del_texto_de_la_pregunta(
    cliente, tenant_a, tenant_b, monkeypatch
):
    """D-03 sobre lo único que el adaptador puede romper: qué le llegó a
    `responder()`. Que la **respuesta** tampoco cambie de scope ya se afirma
    contra el modelo real en `tests/test_loop.py`."""
    recibido = {}

    def espiar(pregunta, institucion_id, historial):
        recibido.update(pregunta=pregunta, institucion_id=institucion_id, historial=historial)
        return {"estado": "RESPONDIDA", "traza_id": "tz_de_mentira"}

    monkeypatch.setattr(main, "responder", espiar)
    pregunta = f"¿Cuántos clientes de riesgo alto tiene la institución {tenant_b}?"

    cliente.post("/ask", json={"institucion_id": tenant_a, "pregunta": pregunta})

    assert recibido["institucion_id"] == tenant_a
    assert recibido["institucion_id"] != tenant_b
    assert recibido["pregunta"] == pregunta
    assert recibido["historial"] == []


def test_una_traza_que_no_existe_no_se_inventa(cliente):
    """404 y no un objeto vacío: para IT, "no hay traza" y "hubo una traza sin
    consultas" son dos cosas distintas."""
    respuesta = cliente.get("/auditoria/tz_este-identificador-no-lo-emitio-nadie")

    assert respuesta.status_code == 404
    assert "traza" in respuesta.json()["detail"]


@pytest.mark.caro
def test_por_http_cada_institucion_recibe_su_numero_y_ninguna_ve_el_de_la_otra(
    respuestas, tenant_a, tenant_b
):
    """El criterio de aceptación del hito, cruzando la API. Las dos instituciones
    no comparten un solo cliente, así que ni el total ni ninguno de los siete
    escalones puede coincidir; `filas` puede venir en `None` cuando la cascada
    entra en una sola fila y no hay tabla que mostrar."""
    de_a, de_b = respuestas[tenant_a], respuestas[tenant_b]

    assert de_a.status_code == 200 and de_b.status_code == 200
    contrato_a, contrato_b = de_a.json(), de_b.json()

    assert contrato_a["valor"]["n"] == esperado_de(tenant_a)["valor_esperado"], contrato_a["respuesta"]
    assert contrato_b["valor"]["n"] == esperado_de(tenant_b)["valor_esperado"], contrato_b["respuesta"]
    assert contrato_a["valor"]["n"] != contrato_b["valor"]["n"]
    assert {e["escalon"]: e["n"] for e in contrato_a["derivacion"]} == esperado_de(tenant_a)["derivacion"]
    assert {e["escalon"]: e["n"] for e in contrato_b["derivacion"]} == esperado_de(tenant_b)["derivacion"]
    assert contrato_a["filas"] is None or contrato_a["filas"] != contrato_b["filas"], (
        "las dos instituciones devolvieron la misma muestra de filas, y no "
        "comparten un solo cliente"
    )
    assert set(contrato_a) == {
        "estado", "respuesta", "valor", "derivacion", "definiciones_usadas",
        "exclusiones", "filas", "supuestos", "opciones", "queries", "grafico", "traza_id",
    }, "el contrato no llegó completo, y el front lee campos y no texto libre"


@pytest.mark.caro
def test_la_auditoria_devuelve_lo_que_costo_la_respuesta(cliente, respuestas, tenant_a):
    """La traza de la historia 27. Los tres contadores se afirman contra el
    detalle, que es de donde salen: uno calculado aparte podría mentir sin que
    nada lo note."""
    contrato = respuestas[tenant_a].json()

    respuesta = cliente.get(f"/auditoria/{contrato['traza_id']}")
    traza = respuesta.json()

    assert respuesta.status_code == 200
    assert traza["institucion_id"] == tenant_a
    assert traza["pregunta"] == REFERENCIA["pregunta"]
    assert traza["estado"] == contrato["estado"]
    assert traza["pasos"] == len(traza["detalle"]) >= 1
    assert traza["tokens"]["total"] > 0
    assert traza["rechazos_del_gate"] == len(
        [t for paso in traza["detalle"] for t in paso["tools"] if t["resultado"]["clase"] == "RECHAZADA"]
    )
    assert [c["sql"] for c in traza["consultas"]] == [q["sql"] for q in contrato["queries"]]
    assert all(c["plan"] and c["ms"] > 0 for c in traza["consultas"]), "una consulta sin plan o sin tiempo"
