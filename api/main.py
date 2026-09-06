"""Los tres endpoints HTTP (`plan/h3-vertical-slice.md`).

    .venv/bin/uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.loop import responder, traza_de
from api.instituciones import instituciones_elegibles

app = FastAPI(
    title="Compliance conversacional",
    description="Una pregunta del oficial, contestada con su derivación y su traza.",
)

# Deuda deliberada: abierto a cualquier origen porque en H3 no hay auth ni
# cookies, así que no hay credencial de sesión que un origen ajeno pueda usar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turno(BaseModel):
    pregunta: str
    respuesta: str


class Pregunta(BaseModel):
    # El historial viaja en cada request porque el servidor no guarda sesiones.
    institucion_id: int
    pregunta: str
    historial: list[Turno] = []


@app.get("/instituciones")
def get_instituciones() -> list[dict]:
    return instituciones_elegibles()


# La institución viaja en el request y nunca se deduce del texto (D-03): es lo
# que impide que una pregunta sea una puerta a los datos de otra institución.
# Sin `response_model`: el contrato sale entero de `responder()` y declararlo acá
# sería una segunda definición que se le desalinearía en silencio.
@app.post("/ask")
def post_ask(cuerpo: Pregunta) -> dict:
    return responder(
        pregunta=cuerpo.pregunta,
        institucion_id=cuerpo.institucion_id,
        historial=[turno.model_dump() for turno in cuerpo.historial],
    )


# Para IT y no para el oficial (D-07): al oficial se le muestra la derivación,
# que ya viaja en el contrato.
@app.get("/auditoria/{traza_id}")
def get_auditoria(traza_id: str) -> dict:
    if (traza := traza_de(traza_id)) is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay traza con el identificador `{traza_id}`. Las trazas "
                "viven en la memoria del proceso: no sobreviven a un reinicio "
                "del servidor y se pisan cuando pasan las últimas doscientas."
            ),
        )
    return traza
