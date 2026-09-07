"""Corre el set de evaluación y escribe el reporte.

    .venv/bin/python evals/run.py --corridas 1 --workers 4
    .venv/bin/python evals/run.py --corridas 3                # la línea de base
    .venv/bin/python evals/run.py --mutacion sin_soft_delete  # validar el set
    .venv/bin/python evals/run.py --sin-skills                # ablación (H5)

Entra por `responder(...)` y no por HTTP: medir la API sería medir una copia del
sistema, con la latencia del transporte encima. La instrumentación —tokens,
pasos, rechazos del gate, milisegundos— ya la produce el loop y se lee de la
traza; acá no se estima nada.

Lo que hace distinto a un eval de un test es que el sujeto no es determinístico
(D-11): por eso cada pregunta se corre N veces y el reporte trae **Pass@1** —la
fracción de corridas que acertaron— junto a **Pass^N** —la fracción de preguntas
que acertaron *todas* las veces—. Un sistema que acierta dos de tres no es un
sistema que acierta.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.loop import NO_CONVERGIO, NO_SOSTUVO, RESPONDIDAS, responder, traza_de  # noqa: E402
from core import config  # noqa: E402

EVALS = Path(__file__).resolve().parent
REPORTES = EVALS / "reports"

# Los precios del proveedor al momento de la medición, tal como los registró
# `NOTES/03-prototipo.md` §4. Van acá y no en la config porque son un dato del
# reporte —"esto costó"— y no un parámetro del sistema.
USD_POR_MILLON_PROMPT = 5.0
USD_POR_MILLON_RESPUESTA = 30.0

# Debajo de esto, que un número de una institución aparezca en la respuesta de la
# otra es coincidencia y no fuga: los conteos chicos se repiten solos. Los
# números que importan —los universos, los conteos grandes— están todos arriba.
FUGA_MINIMA = 100


@dataclass
class Resultado:
    """Una corrida de una pregunta: si acertó, por qué no, y qué costó."""

    id: str
    clase: str
    categoria: str
    institucion: str
    corrida: int
    estado: str
    acerto: bool
    respuesta: str = ""
    motivos: list[str] = field(default_factory=list)
    falla: str = ""
    fugas: list[str] = field(default_factory=list)
    falsa_ambiguedad: bool = False
    ms: float = 0.0
    pasos: int = 0
    tokens_prompt: int = 0
    tokens_respuesta: int = 0
    rechazos_del_gate: int = 0
    timeouts: int = 0
    traza_id: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# El set y los valores esperados
# ─────────────────────────────────────────────────────────────────────────────


def cargar(nombre: str) -> dict:
    return yaml.safe_load((EVALS / nombre).read_text(encoding="utf-8"))


def institucion_de(slug: str, esperados: dict) -> int:
    """El id de una institución, leído de los datos y no escrito en el set.

    Las instituciones de trabajo las elige un criterio sobre la base
    (`tests/criterio_fixture.py`), y el generador de valores esperados dejó el id
    de cada una junto a sus números. Hardcodear un 3 acá sería la única parte del
    proyecto que decide una institución de memoria.
    """
    for entrada in esperados["preguntas"]:
        if slug in entrada["por_institucion"]:
            return entrada["por_institucion"][slug]["tenant_id"]
    raise KeyError(f"La institución {slug!r} no está en valores_esperados.yaml")


def _entrada(concepto: str, esperados: dict) -> dict:
    for entrada in esperados["preguntas"]:
        if entrada["concepto"] == concepto:
            return entrada
    raise KeyError(f"No hay valor esperado para el concepto {concepto!r}")


def valor_esperado(ref: dict, slug: str, esperados: dict) -> Decimal:
    """El número que referencia una pregunta del set.

    `{concepto: riesgo_alto}` es el resultado de la skill; con `escalon` se
    apunta a un peldaño de su cascada, que es como las preguntas ambiguas nombran
    sus dos lecturas sin escribir ningún número a mano.
    """
    datos = _entrada(ref["concepto"], esperados)["por_institucion"][slug]
    if escalon := ref.get("escalon"):
        return Decimal(str(datos["derivacion"][escalon]))
    return Decimal(str(datos["valor_esperado"]))


def derivacion_esperada(concepto: str, slug: str, esperados: dict) -> dict[str, Decimal]:
    datos = _entrada(concepto, esperados)["por_institucion"][slug]
    return {k: Decimal(str(v)) for k, v in datos["derivacion"].items()}


def desglose_esperado(concepto: str, slug: str, esperados: dict) -> list[Decimal]:
    datos = _entrada(concepto, esperados)["por_institucion"][slug]
    return [
        Decimal(str(fila["monto"]))
        for fila in datos.get("desglose", [])
        if "monto" in fila
    ]


def numeros_ajenos(slug: str, esperados: dict) -> set[Decimal]:
    """Los números que sólo puede producir la **otra** institución.

    Se sacan los que las dos comparten —que los hay, y son los chicos— y los
    menores a `FUGA_MINIMA`, para que la métrica de fuga no se dispare por una
    coincidencia aritmética. Lo que queda son cifras que, si aparecen en una
    respuesta, no salieron de ningún lado legítimo.
    """
    propios: set[Decimal] = set()
    ajenos: set[Decimal] = set()
    for entrada in esperados["preguntas"]:
        for otro_slug, datos in entrada["por_institucion"].items():
            destino = propios if otro_slug == slug else ajenos
            destino |= _numeros(datos["valor_esperado"]) | _numeros(datos["derivacion"])
    return {n for n in ajenos - propios if n >= FUGA_MINIMA}


# ─────────────────────────────────────────────────────────────────────────────
# La calificación
# ─────────────────────────────────────────────────────────────────────────────


def califica(pregunta: dict, contrato: dict, esperados: dict) -> list[str]:
    """Los motivos por los que esta respuesta no acierta. Vacío es acierto.

    Comparación exacta y sin juez LLM: un juez metería ruido justo donde queremos
    determinismo, y el número correcto ya está calculado por dos caminos.
    """
    estado = contrato.get("estado", "")
    if estado not in pregunta["estado_esperado"]:
        esperaba = " o ".join(pregunta["estado_esperado"])
        return [f"estado `{estado}`, esperaba {esperaba}"]

    califican = {
        "contestable": _califica_contestable,
        "ambigua": _califica_ambigua,
        "incontestable": _califica_incontestable,
    }
    return califican[pregunta["categoria"]](pregunta, contrato, esperados)


def _califica_contestable(pregunta: dict, contrato: dict, esperados: dict) -> list[str]:
    slug, motivos = pregunta["institucion"], []
    ref = pregunta["valor_esperado"]

    esperado = valor_esperado(ref, slug, esperados)
    valor = (contrato.get("valor") or {}).get("n")
    if valor is None:
        # `exige_valor: false` es para la pregunta cuya respuesta correcta NO es un
        # escalar: exigirle uno a "¿cuánto transamos?" sería exigirle que viole D-08.
        if pregunta.get("exige_valor", True):
            motivos.append(f"sin valor; esperaba {esperado}")
    elif not _coincide(Decimal(str(valor)), esperado):
        motivos.append(f"valor {valor}, esperaba {esperado}")
    elif not (contrato.get("valor") or {}).get("unidad"):
        motivos.append("el número salió sin unidad")

    if pregunta.get("exige_derivacion"):
        motivos += _revisa_derivacion(ref["concepto"], slug, contrato, esperados)

    if pregunta.get("exige_desglose"):
        faltan = [
            str(m)
            for m in desglose_esperado(ref["concepto"], slug, esperados)
            if not any(_coincide(n, m) for n in _numeros(contrato))
        ]
        if faltan:
            motivos.append(f"el desglose no trae los montos {', '.join(faltan)}")

    if pregunta.get("exige_filas") and not (contrato.get("filas") or {}).get("muestra"):
        motivos.append("contestó sin filas: la pregunta pedía el listado")

    if faltantes := _conceptos_faltantes(pregunta, contrato):
        motivos.append(f"no declaró las definiciones {', '.join(faltantes)}")

    return motivos


def _revisa_derivacion(
    concepto: str, slug: str, contrato: dict, esperados: dict
) -> list[str]:
    """La cascada entera, escalón por escalón. Es lo que separa un número que dio
    bien de un número que se derivó bien: dos caminos distintos llegan a 7.859, y
    sólo uno de los dos se puede explicar."""
    esperada = derivacion_esperada(concepto, slug, esperados)
    devuelta = {
        e.get("escalon"): Decimal(str(e["n"]))
        for e in contrato.get("derivacion") or []
        if e.get("n") is not None
    }
    if faltan := [e for e in esperada if e not in devuelta]:
        return [f"la derivación no trae los escalones {', '.join(faltan)}"]
    if movidos := [e for e, n in esperada.items() if not _coincide(devuelta[e], n)]:
        detalle = ", ".join(f"{e}={devuelta[e]} (esperaba {esperada[e]})" for e in movidos)
        return [f"escalones con otro número: {detalle}"]
    return []


def _califica_ambigua(pregunta: dict, contrato: dict, esperados: dict) -> list[str]:
    """No se le pide acertar un número: se le pide no elegir en silencio."""
    motivos = []
    estado = contrato["estado"]

    if estado == "RESPONDIDA_CON_SUPUESTO" and not contrato.get("supuestos"):
        motivos.append("dijo que suponía algo y no declaró qué")
    if estado == "NECESITO_QUE_ACLARES" and not contrato.get("opciones"):
        motivos.append("repreguntó sin ofrecer opciones para elegir")

    admisibles = pregunta.get("valores_admisibles")
    valor = (contrato.get("valor") or {}).get("n")
    if admisibles and valor is not None:
        esperados_ = [
            valor_esperado(ref, pregunta["institucion"], esperados) for ref in admisibles
        ]
        if not any(_coincide(Decimal(str(valor)), e) for e in esperados_):
            lecturas = ", ".join(str(e) for e in esperados_)
            motivos.append(f"eligió {valor}, que no es ninguna de las lecturas ({lecturas})")

    return motivos


def _califica_incontestable(pregunta: dict, contrato: dict, esperados: dict) -> list[str]:
    """El estado ya se verificó. Lo que queda es que no haya disfrazado la falta
    de datos de resultado: un cero se lee como "no hay ninguno", que es una
    afirmación sobre el negocio que nadie consultó.

    **No** se le prohíbe traer una derivación. La primera corrida reprobó dos
    respuestas correctas por eso —contaban lo que sí existe para mostrar contra
    qué se estrella la pregunta— y ninguna decisión del proyecto lo prohíbe: el
    contrato reserva `valor` para el número, y es ése el que tiene que faltar.
    """
    if contrato.get("valor") is not None:
        return ["devolvió un valor: no se puede responder no es un número"]
    return []


def _conceptos_faltantes(pregunta: dict, contrato: dict) -> list[str]:
    declarados = {d.get("concepto") for d in contrato.get("definiciones_usadas") or []}
    return [c for c in pregunta.get("debe_mencionar") or [] if c not in declarados]


def fugas_de(pregunta: dict, contrato: dict, esperados: dict) -> list[str]:
    """Cifras de la otra institución en una respuesta. Tiene que dar vacío.

    El aislamiento lo garantiza el RLS y no esta función: una consulta no puede
    traer filas ajenas. Lo que se mide acá es lo que el RLS no puede impedir —que
    el modelo escriba un número que no consultó— y por eso mira los campos donde
    el sistema **afirma** cifras, no las filas.
    """
    ajenos = numeros_ajenos(pregunta["institucion"], esperados)
    afirmadas = _numeros(contrato.get("valor")) | _numeros(contrato.get("derivacion"))
    afirmadas |= _numeros(contrato.get("opciones"))
    return [str(n) for n in sorted(afirmadas & ajenos)]


def clasifica_falla(pregunta: dict, contrato: dict, traza: dict, motivos: list[str]) -> str:
    """La falla en la taxonomía de H5 (`plan/h5-iteracion.md`), leída de la traza.

    Sirve para saber **dónde** se arregla: una skill no consultada se arregla en
    el prompt, una definición equivocada en la skill, y un rechazo del gate en el
    contexto de índices.
    """
    if not motivos:
        return ""

    respuesta, estado = contrato.get("respuesta", ""), contrato.get("estado", "")
    categoria = pregunta["categoria"]

    if respuesta == NO_CONVERGIO:
        return "sql_ineficiente"
    if respuesta == NO_SOSTUVO:
        return "numero_no_trazable"
    if categoria == "incontestable" and estado != "NO_SE_PUEDE_RESPONDER":
        return "incontestable_respondida"
    if categoria == "contestable" and estado == "NECESITO_QUE_ACLARES":
        return "falsa_ambiguedad"
    if categoria == "ambigua" and estado in RESPONDIDAS:
        return "ambiguedad_no_detectada"
    if _conceptos_faltantes(pregunta, contrato) or not _consulto_la_skill(pregunta, traza):
        return "skill_no_consultada"
    if traza.get("rechazos_del_gate"):
        return "sql_ineficiente"
    return "definicion_equivocada"


def _consulto_la_skill(pregunta: dict, traza: dict) -> bool:
    esperados = set(pregunta.get("debe_mencionar") or [])
    if not esperados:
        return True
    pedidos = {
        tool["argumentos"].get("concepto")
        for paso in traza.get("detalle", [])
        for tool in paso["tools"]
        if tool["tool"] == "get_definition"
    }
    return esperados <= pedidos


def _coincide(devuelto: Decimal, esperado: Decimal) -> bool:
    """Igualdad con la tolerancia del redondeo con el que se presenta el número.

    El promedio de resolución sale de un `avg` de dieciséis decimales y se muestra
    como 2,73: exigir igualdad binaria reprobaría una respuesta correcta. Con más
    tolerancia que ésta, un número aproximado pasaría por exacto.
    """
    if devuelto == esperado:
        return True
    decimales = min(devuelto.as_tuple().exponent, esperado.as_tuple().exponent)
    if decimales >= 0:
        return False
    cuanto = Decimal(1).scaleb(decimales)
    return devuelto.quantize(cuanto, ROUND_HALF_UP) == esperado.quantize(cuanto, ROUND_HALF_UP)


def _numeros(estructura: Any) -> set[Decimal]:
    """Todo número que haya adentro, sin importar cómo esté anidado. `bool` no:
    es un `int` en Python y un flag en `true` sostendría cualquier 1."""
    if isinstance(estructura, bool) or estructura is None:
        return set()
    if isinstance(estructura, (int, float, Decimal)):
        return {Decimal(str(estructura))}
    if isinstance(estructura, str):
        try:
            return {Decimal(estructura)}
        except ArithmeticError:
            return set()
    if isinstance(estructura, dict):
        return {n for v in estructura.values() for n in _numeros(v)}
    if isinstance(estructura, (list, tuple, set)):
        return {n for v in estructura for n in _numeros(v)}
    return set()


# ─────────────────────────────────────────────────────────────────────────────
# La corrida
# ─────────────────────────────────────────────────────────────────────────────


def historial_de(pregunta: dict, esperados: dict) -> list[dict]:
    """Los turnos previos, con los números resueltos contra el YAML.

    El turno anterior lleva un número, y ese número tampoco se escribe a mano: si
    la definición cambia, el historial del eval cambia con ella.
    """
    turnos = []
    for turno in pregunta.get("historial") or []:
        texto = turno["respuesta"]
        if ref := turno.get("valor"):
            texto = texto.format(n=valor_esperado(ref, pregunta["institucion"], esperados))
        turnos.append({"pregunta": turno["pregunta"], "respuesta": texto})
    return turnos


def corre_una(pregunta: dict, corrida: int, esperados: dict) -> Resultado:
    institucion_id = institucion_de(pregunta["institucion"], esperados)
    contrato = responder(
        pregunta["pregunta"], institucion_id, historial_de(pregunta, esperados)
    )
    traza = traza_de(contrato["traza_id"]) or {}

    motivos = califica(pregunta, contrato, esperados)
    fugas = fugas_de(pregunta, contrato, esperados)
    if traza.get("institucion_id") not in (None, institucion_id):
        fugas.append(f"la traza corrió con la institución {traza['institucion_id']}")

    return Resultado(
        id=pregunta["id"],
        clase=pregunta["clase"],
        categoria=pregunta["categoria"],
        institucion=pregunta["institucion"],
        corrida=corrida,
        estado=contrato.get("estado", ""),
        acerto=not motivos and not fugas,
        respuesta=contrato.get("respuesta", ""),
        motivos=motivos,
        falla=clasifica_falla(pregunta, contrato, traza, motivos),
        fugas=fugas,
        falsa_ambiguedad=(
            pregunta["categoria"] == "contestable"
            and contrato.get("estado") == "NECESITO_QUE_ACLARES"
        ),
        ms=traza.get("ms", 0.0),
        pasos=traza.get("pasos", 0),
        tokens_prompt=traza.get("tokens", {}).get("prompt", 0),
        tokens_respuesta=traza.get("tokens", {}).get("respuesta", 0),
        rechazos_del_gate=traza.get("rechazos_del_gate", 0),
        timeouts=_timeouts(traza),
        traza_id=contrato.get("traza_id", ""),
    )


def _timeouts(traza: dict) -> int:
    return sum(
        1
        for paso in traza.get("detalle", [])
        for tool in paso["tools"]
        if tool["resultado"].get("clase") == "FALLO_TIMEOUT"
    )


def corre_el_set(
    preguntas: list[dict], esperados: dict, corridas: int, workers: int
) -> list[Resultado]:
    """Todas las preguntas por todas las corridas, en paralelo.

    Se paraleliza sobre el producto y no sobre las preguntas para que las tres
    corridas de una misma pregunta no caigan seguidas: si el proveedor tiene un
    mal minuto, que no se lo lleve entero a una sola pregunta.
    """
    trabajos = [(p, c) for c in range(1, corridas + 1) for p in preguntas]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = [pool.submit(corre_una, p, c, esperados) for p, c in trabajos]
        resultados = []
        for i, futuro in enumerate(futuros, 1):
            resultados.append(futuro.result())
            print(f"  {i}/{len(trabajos)} · {resultados[-1].id}", flush=True)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# El reporte
# ─────────────────────────────────────────────────────────────────────────────


def metricas(resultados: list[Resultado], corridas: int) -> dict:
    por_pregunta: dict[str, list[Resultado]] = {}
    for r in resultados:
        por_pregunta.setdefault(r.id, []).append(r)

    categorias = {}
    for categoria in ("contestable", "ambigua", "incontestable"):
        de_la_categoria = {
            id_: rs for id_, rs in por_pregunta.items() if rs[0].categoria == categoria
        }
        if not de_la_categoria:
            continue
        intentos = [r for rs in de_la_categoria.values() for r in rs]
        categorias[categoria] = {
            "preguntas": len(de_la_categoria),
            "pass_1": sum(r.acerto for r in intentos) / len(intentos),
            "pass_n": sum(all(r.acerto for r in rs) for rs in de_la_categoria.values())
            / len(de_la_categoria),
        }

    latencias = sorted(r.ms for r in resultados)
    prompt = sum(r.tokens_prompt for r in resultados)
    respuesta = sum(r.tokens_respuesta for r in resultados)

    return {
        "corridas": corridas,
        "preguntas": len(por_pregunta),
        "llamadas": len(resultados),
        "por_categoria": categorias,
        "fugas": sum(bool(r.fugas) for r in resultados),
        "falsa_ambiguedad": sum(r.falsa_ambiguedad for r in resultados),
        "timeouts": sum(r.timeouts for r in resultados),
        "rechazos_del_gate": sum(r.rechazos_del_gate for r in resultados),
        "latencia_ms": {
            "p50": statistics.median(latencias) if latencias else 0,
            "p95": latencias[int(len(latencias) * 0.95) - 1] if latencias else 0,
        },
        "tokens": {"prompt": prompt, "respuesta": respuesta},
        "usd": round(
            prompt / 1e6 * USD_POR_MILLON_PROMPT
            + respuesta / 1e6 * USD_POR_MILLON_RESPUESTA,
            2,
        ),
        "fallas": _fallas(resultados),
    }


def _fallas(resultados: list[Resultado]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for r in resultados:
        if r.falla:
            conteo[r.falla] = conteo.get(r.falla, 0) + 1
    return dict(sorted(conteo.items(), key=lambda kv: -kv[1]))


def reporte(resultados: list[Resultado], m: dict, titulo: str) -> str:
    lineas = [
        f"# {titulo}",
        "",
        f"- Modelo: `{config.modelo()}` · fecha de corte `{config.AS_OF}`",
        f"- {m['preguntas']} preguntas × {m['corridas']} corridas = {m['llamadas']} llamadas",
        f"- Costo: US$ {m['usd']} · {m['tokens']['prompt']:,} tokens de entrada y "
        f"{m['tokens']['respuesta']:,} de salida",
        f"- Latencia: p50 {m['latencia_ms']['p50'] / 1000:.1f} s · "
        f"p95 {m['latencia_ms']['p95'] / 1000:.1f} s",
        "",
        "## Acierto por categoría",
        "",
        f"| Categoría | Preguntas | Pass@1 | Pass^{m['corridas']} |",
        "|---|---|---|---|",
    ]
    for categoria, datos in m["por_categoria"].items():
        lineas.append(
            f"| {categoria} | {datos['preguntas']} | {datos['pass_1']:.0%} | "
            f"{datos['pass_n']:.0%} |"
        )

    lineas += [
        "",
        "## Las que bloquean, y las que avisan",
        "",
        "| Métrica | Valor | Qué significa |",
        "|---|---|---|",
        f"| **Fugas cross-tenant** | **{m['fugas']}** | Cualquier valor distinto de 0 "
        "bloquea la entrega |",
        f"| Falsa ambigüedad | {m['falsa_ambiguedad']} | Repreguntas sobre preguntas "
        "que eran claras |",
        f"| Timeouts | {m['timeouts']} | Consultas que no entraron en el plazo |",
        f"| Rechazos del gate | {m['rechazos_del_gate']} | Planes malos reescritos; "
        "cada uno cuesta el 70 % de una pregunta |",
        "",
        "## Fallas por tipo",
        "",
    ]
    if m["fallas"]:
        lineas += ["| Tipo | Corridas | Dónde se arregla |", "|---|---|---|"]
        lineas += [
            f"| {tipo} | {n} | {DONDE_SE_ARREGLA.get(tipo, '')} |"
            for tipo, n in m["fallas"].items()
        ]
    else:
        lineas.append("Ninguna.")

    lineas += ["", "## Pregunta por pregunta", "", "| id | clase | inst. | acierto | qué pasó |", "|---|---|---|---|---|"]
    por_pregunta: dict[str, list[Resultado]] = {}
    for r in resultados:
        por_pregunta.setdefault(r.id, []).append(r)
    for id_, rs in sorted(por_pregunta.items()):
        aciertos = sum(r.acerto for r in rs)
        detalle = next((r for r in rs if not r.acerto), None)
        que_paso = "—" if detalle is None else "; ".join(detalle.motivos + detalle.fugas)
        lineas.append(
            f"| `{id_}` | {rs[0].clase} | {rs[0].institucion} | {aciertos}/{len(rs)} | "
            f"{que_paso} |"
        )

    return "\n".join(lineas) + "\n"


DONDE_SE_ARREGLA = {
    "definicion_equivocada": "la skill (H2)",
    "skill_no_consultada": "el prompt o la descripción de la tool",
    "sql_ineficiente": "el contexto de índices",
    "ambiguedad_no_detectada": "el prompt y sus ejemplos de ambigüedad",
    "falsa_ambiguedad": "el prompt: la fricción innecesaria mata la confianza",
    "incontestable_respondida": "el prompt: explicitar qué **no** hay en el esquema",
    "numero_no_trazable": "la validación post-hoc (H3)",
}


# ─────────────────────────────────────────────────────────────────────────────
# El veredicto de una mutación
# ─────────────────────────────────────────────────────────────────────────────


def linea_de_base(ruta: str | None) -> dict[str, bool]:
    """Qué preguntas acertaban **todas** sus corridas antes de la mutación.

    Sin esto, "la mutación rompió tres preguntas" no dice nada: puede que las
    tres ya estuvieran rotas. Lo que valida el set es que una pregunta que
    **pasaba** deje de pasar.
    """
    if ruta is None:
        corridas = sorted(REPORTES.glob("[0-9]*.json"))
        corridas = [c for c in corridas if "mutacion" not in c.name and "ablacion" not in c.name]
        if not corridas:
            raise SystemExit("No hay línea de base: corré el set entero antes de mutarlo.")
        ruta = corridas[-1]
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    pasaba: dict[str, bool] = {}
    for r in datos["resultados"]:
        pasaba[r["id"]] = pasaba.get(r["id"], True) and r["acerto"]
    return pasaba


def veredicto(nombre: str, resultados: list[Resultado], pasaba: dict[str, bool]) -> int:
    """Imprime qué rompió la mutación y devuelve el código de salida.

    Devuelve 1 si ninguna pregunta que pasaba dejó de pasar. Eso **no** prueba por
    sí solo que el set tenga un agujero: puede ser que la mutación no haya movido
    al sistema. Las dos causas se separan mirando quién sobrevivió, y el texto que
    imprime dice cómo.
    """
    ahora: dict[str, bool] = {}
    for r in resultados:
        ahora[r.id] = ahora.get(r.id, True) and r.acerto

    rotas = [id_ for id_, acierta in ahora.items() if pasaba.get(id_) and not acierta]
    ya_estaban = [id_ for id_ in ahora if not pasaba.get(id_, False)]
    aguantaron = [id_ for id_, acierta in ahora.items() if pasaba.get(id_) and acierta]

    print(f"\n## Mutación `{nombre}`\n")
    print(f"- Rompió (pasaban y dejaron de pasar): {', '.join(rotas) or 'ninguna'}")
    print(f"- Aguantaron la mutación: {', '.join(aguantaron) or 'ninguna'}")
    print(f"- No prueban nada (ya fallaban en la línea de base): {', '.join(ya_estaban) or 'ninguna'}")

    if not rotas:
        print(
            "\n**Nada que pasaba dejó de pasar.** Son dos causas distintas y hay que "
            "separarlas: si las que aguantaron son contestables, su número se compara "
            "exacto, así que no cambió y la mutación fue inerte — el problema es la "
            "mutación. Si todas las apuntadas ya fallaban, la regla queda sin custodia "
            "y el agujero sí es del set."
        )
    return 0 if rotas else 1


# ─────────────────────────────────────────────────────────────────────────────
# La línea de comandos
# ─────────────────────────────────────────────────────────────────────────────


def filtrar(preguntas: list[dict], solo: str | None) -> list[dict]:
    """`--solo c-002,ambigua` acepta ids y categorías en la misma lista."""
    if not solo:
        return preguntas
    pedidos = {p.strip() for p in solo.split(",")}
    return [p for p in preguntas if p["id"] in pedidos or p["categoria"] in pedidos]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corridas", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--solo", help="ids o categorías separados por coma")
    parser.add_argument("--mutacion", help="rompe una skill a propósito y corre sólo lo que debería romper")
    parser.add_argument("--sin-skills", action="store_true", help="ablación: el agente sin definiciones curadas")
    parser.add_argument("--solo-skill", help="ablación: sólo esta definición disponible")
    parser.add_argument("--sin-reporte", action="store_true", help="imprime y no escribe archivos")
    parser.add_argument("--contra", help="el .json contra el que se compara una mutación (por defecto, el último)")
    args = parser.parse_args(argv)

    esperados = cargar("valores_esperados.yaml")
    preguntas = filtrar(cargar("questions.yaml")["preguntas"], args.solo)

    from evals import mutaciones as mut

    with mut.aplicada(args.mutacion, args.sin_skills, args.solo_skill) as mutacion:
        if mutacion:
            preguntas = [p for p in preguntas if p["id"] in mutacion.debe_romper]
        titulo = mut.titulo(args.mutacion, args.sin_skills, args.solo_skill)
        print(f"{titulo} · {len(preguntas)} preguntas × {args.corridas}", flush=True)
        resultados = corre_el_set(preguntas, esperados, args.corridas, args.workers)

    m = metricas(resultados, args.corridas)
    texto = reporte(resultados, m, titulo)
    print("\n" + texto)

    if not args.sin_reporte:
        REPORTES.mkdir(exist_ok=True)
        sello = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        variante = mut.slug(args.mutacion, args.sin_skills, args.solo_skill)
        nombre = f"{sello}-{variante}" if variante else sello
        (REPORTES / f"{nombre}.md").write_text(texto, encoding="utf-8")
        (REPORTES / f"{nombre}.json").write_text(
            json.dumps(
                {"metricas": m, "resultados": [asdict(r) for r in resultados]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"→ evals/reports/{nombre}.md")

    if args.mutacion:
        return veredicto(args.mutacion, resultados, linea_de_base(args.contra))

    return 1 if m["fugas"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
