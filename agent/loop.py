"""El ciclo de function calling que convierte una pregunta en el contrato.

El diseño está en `plan/h3-vertical-slice.md`; lo que midió el prototipo, y que
justifica los topes y las verificaciones de acá, en `NOTES/03-prototipo.md`.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import OrderedDict
from functools import cache

from openai import OpenAI

from agent.tools import (
    ESPECIFICACIONES,
    TOOLS,
    catalogo_de_conceptos,
    escalones_de,
    esquema_con_indices,
    texto_para_el_modelo,
)
from core import config
from core.config import AS_OF
from core.db.ejecucion import Fallo, Ok, Rechazada
from core.trazabilidad import cifras_sin_respaldo

# El prototipo midió 2 pasos hasta la consulta correcta y 5 en el peor caso de
# 18 corridas (`NOTES/03-prototipo.md` §2). Doce deja aire para explorar y es
# bajo a propósito: un rechazo del gate cuesta el 70 % de una pregunta en tokens.
TOPE_DE_PASOS = 12

# Cinco es lo que dibuja el mockup: alcanzan para reconciliar contra lo conocido
# sin tapar el hallazgo principal.
MUESTRA_DE_FILAS = 5

# A ~4 KB por traza, doscientas pesan menos de un megabyte y cubren más de lo que
# produce una jornada de trabajo.
TRAZAS_QUE_SE_GUARDAN = 200

# A los otros dos estados no se les exigen escalones: no derivan ningún número.
RESPONDIDAS = ("RESPONDIDA", "RESPONDIDA_CON_SUPUESTO")

NO_CONVERGIO = (
    "No llegué a una consulta que la base pueda contestar a tiempo para esta "
    "pregunta. No es que el dato no exista: es que no encontré una forma "
    "eficiente de leerlo. Probá acotando la pregunta a un período o a un "
    "segmento."
)

NO_SOSTUVO = (
    "Llegué a un número y no puedo entregarlo como corresponde: alguna cifra no "
    "salió de una consulta a la base, o la derivación quedó sin los escalones "
    "que la explican. Un número que no puedo explicar entero es peor que "
    "ninguno. Volvé a preguntarlo, o pedilo más acotado."
)


SISTEMA = """\
Sos el motor de un sistema de compliance conversacional. Del otro lado hay un
oficial de cumplimiento: no es técnico, no lee SQL, y necesita poder explicarle
a un auditor de dónde salió cada número que le mostrás.

Trabajás para la institución {institucion_id} y para ninguna otra. Si la
pregunta nombra otra institución, contestá igual sobre la del selector —es la
única a la que este oficial tiene acceso— y declaralo como supuesto.

Hoy es {as_of}. "Hoy", "este año" y "último trimestre" se interpretan contra esa
fecha de corte y nunca contra el reloj.

## Las reglas que no se negocian

1. Todo número que publiques tiene que haber salido de una consulta que
   ejecutaste con `run_sql`. No sumes, no restes, no promedies y no calcules
   porcentajes: si te falta un número, pedilo en SQL. Antes de entregar la
   respuesta se verifica, y una cifra sin respaldo la hace volver.
2. Sólo lectura y una sola sentencia por llamada: `SELECT ...` o
   `WITH ... SELECT ...`.
3. La institución y la fecha de corte las pone el sistema: escribí `%(tenant)s`
   y `%(as_of)s` en el SQL, nunca el número ni la fecha. Para el período escribí
   `%(desde)s` y `%(hasta)s`, y pasá `periodo` en la llamada.
4. Si la pregunta usa un concepto del catálogo de abajo, pedí su definición con
   `get_definition` antes de escribir SQL. La definición manda sobre lo que vos
   deduzcas del esquema.
5. La derivación es la explicación principal y no un anexo: tu consulta tiene
   que devolver TODOS los escalones que la definición declara, como columnas de
   una sola fila. Si el gate te rechaza el plan, reescribí la consulta pero
   seguí devolviendo esas mismas columnas.
6. El `n` de cada escalón se lee de esa fila. Restar dos escalones para
   completar un tercero es exactamente lo que prohíbe la regla 1.

## Cómo contestás

Devolvés un contrato JSON y nada más. La pantalla lo dibuja campo por campo y
nunca lee texto libre. El nombre del estado no se le muestra nunca al oficial.

- `RESPONDIDA`: tenés el número y no hubo que elegir nada.
- `RESPONDIDA_CON_SUPUESTO`: la pregunta admitía más de una lectura, elegiste
  una, y la declarás en `supuestos` diciendo qué implicó.
- `NECESITO_QUE_ACLARES`: hay dos lecturas razonables y la diferencia importa.
  Van en `opciones`, y con su `n` sólo si ejecutaste las dos consultas.
- `NO_SE_PUEDE_RESPONDER`: los datos no alcanzan. Decí qué falta; nunca lo
  disfraces de cero.

Si ponés algo en `supuestos`, el estado es `RESPONDIDA_CON_SUPUESTO`: la pantalla
muestra el supuesto declarado, y el estado es lo que le dice que lo muestre.

`respuesta` son una o dos oraciones para el oficial, en castellano rioplatense,
sin SQL y sin jerga. `exclusiones` lleva sólo lo que efectivamente excluyó algo.
`definiciones_usadas` lleva el parámetro que aplicaste, de dónde salió y desde
cuándo rige. No inventes una fecha de vigencia: salen de `get_definition`.

## Conceptos con definición curada

{conceptos}

## El esquema, con sus índices

{esquema}
"""


# El contrato, en el dialecto del proveedor. Va como esquema estricto y no como
# pedido en el prompt porque un campo faltante rompería la pantalla, y eso no se
# sostiene con una promesa. Los cuatro campos que el modelo NO escribe —`filas`,
# `queries`, `grafico` y `traza_id`— los pone el loop.
CONTRATO = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "estado",
        "respuesta",
        "valor",
        "derivacion",
        "definiciones_usadas",
        "exclusiones",
        "supuestos",
        "opciones",
    ],
    "properties": {
        "estado": {
            "type": "string",
            "enum": [
                "RESPONDIDA",
                "RESPONDIDA_CON_SUPUESTO",
                "NECESITO_QUE_ACLARES",
                "NO_SE_PUEDE_RESPONDER",
            ],
        },
        "respuesta": {"type": "string"},
        "valor": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["n", "unidad"],
            "properties": {"n": {"type": "number"}, "unidad": {"type": "string"}},
        },
        "derivacion": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["escalon", "texto", "n", "unidad"],
                "properties": {
                    "escalon": {"type": "string"},
                    "texto": {"type": "string"},
                    "n": {"type": "number"},
                    "unidad": {"type": ["string", "null"]},
                },
            },
        },
        "definiciones_usadas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["concepto", "texto", "parametro", "origen", "vigente_desde"],
                "properties": {
                    "concepto": {"type": "string"},
                    "texto": {"type": "string"},
                    "parametro": {"type": ["string", "null"]},
                    "origen": {"type": ["string", "null"]},
                    "vigente_desde": {"type": ["string", "null"]},
                },
            },
        },
        "exclusiones": {"type": "array", "items": {"type": "string"}},
        "supuestos": {"type": "array", "items": {"type": "string"}},
        "opciones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["texto", "n"],
                "properties": {"texto": {"type": "string"}, "n": {"type": ["number", "null"]}},
            },
        },
    },
}


def responder(pregunta: str, institucion_id: int, historial: list[dict] | None = None) -> dict:
    """Contesta una pregunta del oficial sobre los datos de su institución.

    `institucion_id` llega por parámetro y **nunca** se deduce del texto (D-03).
    `historial` son los turnos previos, `[{"pregunta": ..., "respuesta": ...}]`:
    el servidor no guarda sesiones. Es también la puerta por la que mide el
    runner de evals, y no por HTTP, para que no mida una copia del sistema.
    """
    mensajes = _mensajes_iniciales(pregunta, institucion_id, historial)
    ejecutadas: list[tuple[str, Ok]] = []
    leidas: dict[str, dict[str, str]] = {}
    ya_le_reclamamos = False
    traza = _Traza(pregunta, institucion_id)

    for _ in range(TOPE_DE_PASOS):
        mensaje, tokens = _le_preguntamos_al_modelo(mensajes)
        traza.abrir_paso(tokens)
        mensajes.append(mensaje.model_dump(exclude_none=True))

        if not mensaje.tool_calls:
            contrato = _contrato_de(mensaje)
            if not (falta := _lo_que_falta(contrato, leidas, ejecutadas)):
                return traza.guardar(_completar(contrato, ejecutadas))
            if ya_le_reclamamos:
                return traza.guardar(_sin_respuesta(NO_SOSTUVO, ejecutadas))
            mensajes.append({"role": "user", "content": falta})
            ya_le_reclamamos = True
            continue

        for llamada in mensaje.tool_calls:
            nombre, argumentos, resultado = _correr(llamada, institucion_id)
            traza.anotar_tool(nombre, argumentos, resultado)
            # Lo único que el loop se queda de una tool, para verificar el
            # contrato antes de entregarlo (`NOTES/03-prototipo.md` §5).
            if nombre == "run_sql" and isinstance(resultado, Ok):
                ejecutadas.append((argumentos["sql"], resultado))
            if nombre == "get_definition" and (escalones := escalones_de(argumentos.get("concepto", ""))):
                leidas[argumentos["concepto"]] = escalones
            mensajes.append(
                {
                    "role": "tool",
                    "tool_call_id": llamada.id,
                    "content": texto_para_el_modelo(resultado),
                }
            )

    return traza.guardar(_sin_respuesta(NO_CONVERGIO, ejecutadas))


@cache
def _cliente() -> OpenAI:
    """Perezoso y no de módulo: importar `agent.loop` no tiene que exigir una
    credencial, para que la suite pueda colectar los tests sin `OPENAI_API_KEY`.
    """
    return OpenAI(api_key=config.openai_api_key())


def _le_preguntamos_al_modelo(mensajes: list[dict]):
    """Devuelve el mensaje y lo que costó. Los tokens salen del proveedor y no de
    una estimación sobre el texto: el único que sabe cuánto se facturó es él.
    """
    respuesta = _cliente().chat.completions.create(
        model=config.modelo(),
        messages=mensajes,
        tools=ESPECIFICACIONES,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "contrato", "strict": True, "schema": CONTRATO},
        },
    )
    return respuesta.choices[0].message, _tokens(respuesta.usage)


def _tokens(usage) -> dict:
    """En cero si el proveedor no las mandó: el número que IT mira para saber qué
    paga tiene que ser el que vino, o ninguno.
    """
    if usage is None:
        return {"prompt": 0, "respuesta": 0, "total": 0}
    return {
        "prompt": usage.prompt_tokens,
        "respuesta": usage.completion_tokens,
        "total": usage.total_tokens,
    }


def _mensajes_iniciales(
    pregunta: str, institucion_id: int, historial: list[dict] | None
) -> list[dict]:
    """El historial entra como turnos y no como un resumen: para entender qué
    opción eligió el oficial, el modelo necesita ver qué había ofrecido.
    """
    mensajes = [
        {
            "role": "system",
            "content": SISTEMA.format(
                institucion_id=institucion_id,
                as_of=AS_OF,
                conceptos=catalogo_de_conceptos(),
                esquema=esquema_con_indices(institucion_id),
            ),
        }
    ]
    for turno in historial or []:
        mensajes.append({"role": "user", "content": turno["pregunta"]})
        mensajes.append({"role": "assistant", "content": turno["respuesta"]})
    mensajes.append({"role": "user", "content": pregunta})
    return mensajes


def _contrato_de(mensaje) -> dict:
    """El contrato que el modelo devolvió, o vacío si vino cortado a la mitad.

    El esquema estricto garantiza la forma pero no la entrega. Vacío entra al
    mismo camino que un contrato incompleto —se le reclama una vez— en vez de
    llevarse puesta la respuesta con un traceback.
    """
    try:
        return json.loads(mensaje.content or "{}")
    except json.JSONDecodeError:
        return {}


def _correr(llamada, institucion_id: int) -> tuple[str, dict, Ok | Rechazada | Fallo | str]:
    """Corre una tool con los argumentos que escribió el modelo.

    El `except` es ancho a propósito: un argumento mal escrito tiene que ser una
    vuelta más de la conversación y no una excepción que mate la respuesta. Los
    errores de Postgres no pasan por acá: vienen normalizados desde el seam.

    Los `null` se descartan porque el esquema estricto obliga al modelo a mandar
    todas las propiedades, y un `limite=None` pisaría el default de la tool.
    """
    nombre = llamada.function.name
    try:
        argumentos = {
            clave: valor
            for clave, valor in json.loads(llamada.function.arguments or "{}").items()
            if valor is not None
        }
        return nombre, argumentos, TOOLS[nombre](institucion_id=institucion_id, **argumentos)
    except Exception as e:
        return nombre, {}, f"La llamada a `{nombre}` no se pudo ejecutar: {e}"


def _lo_que_falta(
    contrato: dict, leidas: dict[str, dict[str, str]], ejecutadas: list[tuple[str, Ok]]
) -> str:
    """Qué le falta al contrato para poder entregarse, dicho para el modelo.

    Cadena vacía es que está listo. Los reclamos van juntos en un solo mensaje
    porque el reintento es **uno**: de a uno se gastaría en el primero.
    """
    if "estado" not in contrato:
        return "Devolvé el contrato completo: falta el estado y el resto de los campos."

    reclamos = []

    # D-04. Se le pasan las **filas** y no los `Ok`: un costo estimado del
    # `EXPLAIN` sosteniendo una cifra es lo que la regla existe para impedir.
    if sin_respaldo := cifras_sin_respaldo(contrato, [ok.filas for _, ok in ejecutadas]):
        reclamos.append(
            "Estas cifras no salieron de ninguna consulta que hayas ejecutado: "
            + "; ".join(f"{c.texto} (en {c.donde})" for c in sin_respaldo)
            + ". Ejecutá la consulta que las devuelva y volvé a armar el "
            "contrato con los números que devolvió, o sacalas."
        )

    if contrato["estado"] in RESPONDIDAS:
        traidos = {escalon.get("escalon") for escalon in contrato.get("derivacion") or []}
        declarados = {d.get("concepto") for d in contrato.get("definiciones_usadas") or []}
        for concepto, escalones in leidas.items():
            if faltan := [e for e in escalones if e not in traidos]:
                reclamos.append(
                    f"A la derivación le faltan escalones de `{concepto}`: "
                    + ", ".join(f"`{e}`" for e in faltan)
                    + ". Son los que la definición declara y la pantalla dibuja "
                    "como cascada: ejecutá una consulta que los devuelva todos "
                    "en una sola fila y ponelos con el `n` que devolvió."
                )
            if concepto not in declarados:
                reclamos.append(
                    f"Leíste la definición de `{concepto}` y no está en "
                    "`definiciones_usadas`. La definición aplicada va junto al "
                    "número, con su parámetro, su origen y desde cuándo rige."
                )

    return "\n".join(reclamos)


def _completar(contrato: dict, ejecutadas: list[tuple[str, Ok]]) -> dict:
    """Los cuatro campos que pone el sistema y no el modelo. `grafico` va siempre
    en `null`: dejar el hueco cuesta nada y agregarlo después cambia el contrato.
    """
    contrato["filas"] = _filas(ejecutadas)
    contrato["queries"] = [{"sql": sql, "plan": ok.plan, "ms": ok.ms} for sql, ok in ejecutadas]
    contrato["grafico"] = None
    contrato["traza_id"] = f"tz_{uuid.uuid4()}"
    return contrato


def _sin_respuesta(texto: str, ejecutadas: list[tuple[str, Ok]]) -> dict:
    """El contrato de las dos salidas que no traen número. Va con las consultas
    que sí se ejecutaron, para que se vea qué se intentó. Ninguno de los dos
    textos lleva una cifra, que sería una cifra sin respaldo.
    """
    return _completar(
        {
            "estado": "NO_SE_PUEDE_RESPONDER",
            "respuesta": texto,
            "valor": None,
            "derivacion": [],
            "definiciones_usadas": [],
            "exclusiones": [],
            "supuestos": [],
            "opciones": [],
        },
        ejecutadas,
    )


def _filas(ejecutadas: list[tuple[str, Ok]]) -> dict | None:
    """La **última** consulta con más de una fila es la tabla que el agente fue a
    buscar. Las cascadas traen sus escalones en una sola fila: ahí no hay tabla
    que mostrar y el campo va en `null`, como en el mockup.
    """
    for _, ok in reversed(ejecutadas):
        if len(ok.filas) > 1:
            return {
                "columnas": ok.columnas,
                "muestra": [[_serializable(v) for v in fila] for fila in ok.filas[:MUESTRA_DE_FILAS]],
                "total": len(ok.filas),
            }
    return None


def _serializable(valor):
    """Lo que no es un tipo de JSON viaja como texto. El `Decimal` de un monto va
    como texto y no como `float`: redondearlo es inventar un número, aunque sea
    en el último decimal.
    """
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    return str(valor)


# En memoria del proceso y no en Postgres: el rol del agente es de sólo lectura
# por diseño (D-02). Limitación conocida y asumida — una traza no sobrevive a un
# reinicio, y con más de un worker sólo la encuentra el worker que contestó.
_TRAZAS: OrderedDict[str, dict] = OrderedDict()

# uvicorn corre los endpoints sincrónicos en un threadpool: dos preguntas en
# vuelo son dos hilos acá. Guardar y desalojar tienen que ser una sola operación.
_CANDADO = threading.Lock()


def traza_de(traza_id: str) -> dict | None:
    """La traza de una pregunta, o `None` si ya no está. `None` no distingue
    "nunca existió" de "se cayó por el tope o por un reinicio", y no puede: el
    identificador no lleva nada adentro que permita separarlos.
    """
    with _CANDADO:
        return _TRAZAS.get(traza_id)


class _Traza:
    """Lo que costó una respuesta, que el contrato a propósito no lleva.

    Un **paso** es una vuelta del ciclo, la misma unidad que cuenta
    `TOPE_DE_PASOS`: así "costó 9 pasos" es comparable con "el tope son 12".
    """

    def __init__(self, pregunta: str, institucion_id: int) -> None:
        self.pregunta = pregunta
        self.institucion_id = institucion_id
        self.comenzo = time.monotonic()
        self.pasos: list[dict] = []
        self.rechazos_del_gate = 0

    def abrir_paso(self, tokens: dict) -> None:
        """Se abre antes de correr las tools: `anotar_tool` cuelga de la vuelta
        que esto deja abierta.
        """
        self.pasos.append({"paso": len(self.pasos) + 1, "tokens": tokens, "tools": []})

    def anotar_tool(self, nombre: str, argumentos: dict, resultado) -> None:
        """Una tool que se llamó en la vuelta abierta, y cómo salió.

        Los argumentos van enteros porque para una consulta que el gate rechazó
        éste es el **único** lugar donde queda el SQL: `queries` lleva sólo las
        que se ejecutaron.
        """
        if isinstance(resultado, Rechazada):
            self.rechazos_del_gate += 1
        self.pasos[-1]["tools"].append(
            {"tool": nombre, "argumentos": argumentos, "resultado": _como_salio(resultado)}
        )

    def guardar(self, contrato: dict) -> dict:
        """Cierra la traza y devuelve el contrato, para que ninguna salida de
        `responder` pueda contestar sin dejar traza. Las consultas se leen de
        `queries` en vez de acumularse acá: una segunda copia se desincroniza.
        """
        traza = {
            "traza_id": contrato["traza_id"],
            "institucion_id": self.institucion_id,
            "pregunta": self.pregunta,
            "estado": contrato["estado"],
            "ms": round((time.monotonic() - self.comenzo) * 1000, 1),
            "pasos": len(self.pasos),
            "tokens": {
                clave: sum(paso["tokens"][clave] for paso in self.pasos)
                for clave in ("prompt", "respuesta", "total")
            },
            "rechazos_del_gate": self.rechazos_del_gate,
            "consultas": contrato["queries"],
            "detalle": self.pasos,
        }
        with _CANDADO:
            _TRAZAS[traza["traza_id"]] = traza
            while len(_TRAZAS) > TRAZAS_QUE_SE_GUARDAN:
                _TRAZAS.popitem(last=False)
        return contrato


def _como_salio(resultado) -> dict:
    """Cómo terminó una tool, en lo poco que la auditoría necesita. Las filas no
    entran: son del contrato, y repetirlas por paso multiplicaría el peso de la
    traza. El rechazo del gate sí entra entero — explica por qué una respuesta
    costó tres pasos más de lo normal.
    """
    if isinstance(resultado, Ok):
        return {"clase": "OK", "filas": len(resultado.filas), "ms": round(resultado.ms, 1)}
    if isinstance(resultado, Rechazada):
        return {
            "clase": "RECHAZADA",
            "motivo": resultado.motivo,
            "sugerencia": resultado.sugerencia,
        }
    if isinstance(resultado, Fallo):
        return {"clase": f"FALLO_{resultado.clase}", "detalle": resultado.detalle}
    # Las cuatro tools que no son `run_sql` contestan en texto, y un argumento
    # mal escrito también: para la auditoría son lo mismo, el ciclo siguió.
    return {"clase": "TEXTO"}
