"""Romper una skill a propósito, para saber si el set mide algo.

Es el paso 5 de la heurística de `plan/testing.md` —romper el código a mano y
confirmar que el test falla— aplicado al eval. La tabla es la de ese documento.
**Si una mutación no rompe ninguna pregunta, el set tiene un agujero**, y lo que
falta es una pregunta, no una mutación más floja.

Las mutaciones se aplican **en memoria**, sobre el diccionario que `agent.tools`
cachea, y se deshacen al salir. Ningún archivo de `core/semantics/` se toca: una
mutación que edita el repo es una que alguien se olvida de revertir.

Cada una corre **sólo las preguntas que debería romper** (`debe_romper`): correr
el set entero seis veces costaría veinte dólares para responder una pregunta de
sí o no.

Este módulo también hospeda las dos ablaciones que pide H5 —el agente sin
definiciones curadas, y con una sola— porque son la misma maniobra: cambiarle al
modelo lo que lee antes de escribir SQL.
"""

from __future__ import annotations

import copy
import datetime
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

import agent.tools
import core.periodos
from agent.tools import _skills


@dataclass(frozen=True)
class Mutacion:
    nombre: str
    que_rompe: str
    debe_romper: tuple[str, ...]
    # (concepto, patrón, reemplazo) sobre el SQL de referencia que lee el modelo.
    parches: tuple[tuple[str, str, str], ...] = ()
    # Trampas a borrar: la skill no puede advertir contra el error que le metimos.
    calla: tuple[tuple[str, str], ...] = ()
    reescribe_definicion: tuple[tuple[str, str], ...] = ()
    usa_el_reloj: bool = False
    # `get_definition` le inyecta al modelo el valor **vigente** de cada perilla,
    # aparte del SQL de referencia. Sin mutar también eso, mover el `ORDER BY` de
    # la golden no cambia nada: el modelo ya tiene el número correcto servido.
    usa_la_config_vieja: bool = False

    def aplicar(self, skills: dict) -> None:
        """Un parche que no engancha deja la skill sana y el reporte diría que el
        set tiene un agujero: por eso corta en vez de seguir."""
        for concepto, patron, reemplazo in self.parches:
            skill = skills[concepto]
            enganchados = 0
            for campo in ("golden_sql", "desglose_sql"):
                if campo in skill:
                    skill[campo], n = re.subn(patron, reemplazo, skill[campo])
                    enganchados += n
            if not enganchados:
                raise ValueError(f"{self.nombre}: {patron!r} no engancha en {concepto}")
        for concepto, fragmento in self.calla:
            skill = skills[concepto]
            quedan = [t for t in skill.get("trampas", []) if fragmento not in t]
            if len(quedan) == len(skill.get("trampas", [])):
                raise ValueError(f"{self.nombre}: ninguna trampa de {concepto} dice {fragmento!r}")
            skill["trampas"] = quedan
        for concepto, texto in self.reescribe_definicion:
            skills[concepto]["definicion"] = texto


MUTACIONES = {
    m.nombre: m
    for m in [
        Mutacion(
            nombre="sin_soft_delete",
            que_rompe="Sacar `deleted_at IS NULL` de riesgo alto",
            debe_romper=("c-002", "c-003", "c-013"),
            parches=(("riesgo_alto", r"\w+\.deleted_at IS NULL", "true"),),
            calla=(("riesgo_alto", "NO su historia"), ("riesgo_alto", "se borran 13 veces")),
            reescribe_definicion=(
                (
                    "riesgo_alto",
                    "Un cliente es de riesgo alto si su evaluación de riesgo vigente "
                    "supera el umbral configurado por su institución, si está marcado a "
                    "mano como riesgo alto, o —sólo donde la institución lo configuró "
                    "así— si es PEP vigente.\n",
                ),
            ),
        ),
        Mutacion(
            nombre="falso_positivo_es_hallazgo",
            que_rompe="Contar `CLOSED_FALSE_POSITIVE` como hallazgo",
            debe_romper=("c-005", "c-006", "a-008"),
            parches=(
                (
                    "hallazgo_real",
                    r"a\.status = 'CLOSED_TRUE_POSITIVE'",
                    "a.status IN ('CLOSED_TRUE_POSITIVE', 'CLOSED_FALSE_POSITIVE')",
                ),
            ),
            calla=(("hallazgo_real", "falsos positivos cerrados"),),
            reescribe_definicion=(
                (
                    "hallazgo_real",
                    "Un hallazgo real es toda alerta que se cerró, sin importar cómo "
                    "haya cerrado, más las escaladas donde la institución así lo "
                    "configuró.\n",
                ),
            ),
        ),
        Mutacion(
            nombre="umbral_viejo",
            que_rompe="Tomar el `effective_from_date` más viejo en vez del vigente",
            debe_romper=("c-002", "c-004", "c-013"),
            parches=(
                ("riesgo_alto", r"ORDER BY (key, )?effective_from_date DESC", r"ORDER BY \1effective_from_date ASC"),
                ("monto_transado", r"ORDER BY (key, )?effective_from_date DESC", r"ORDER BY \1effective_from_date ASC"),
            ),
            calla=(("riesgo_alto", "El umbral varía"),),
            usa_la_config_vieja=True,
        ),
        Mutacion(
            nombre="monedas_sumadas",
            que_rompe="Sumar los montos entre monedas",
            debe_romper=("c-004", "a-001"),
            parches=(
                (
                    "monto_transado",
                    r"SELECT t\.currency, t\.direction, count\(\*\) AS operaciones",
                    "SELECT count(*) AS operaciones",
                ),
                ("monto_transado", r"\n\s*GROUP BY t\.currency, t\.direction", ""),
                ("monto_transado", r"\n\s*ORDER BY t\.currency, t\.direction", ""),
            ),
            calla=(("monto_transado", "amount es siempre positivo"), ("monto_transado", "moneda")),
            reescribe_definicion=(
                (
                    "monto_transado",
                    "El monto transado es la suma de los importes de las transacciones "
                    "liquidadas del período. Se entrega como un total único.\n",
                ),
            ),
        ),
        Mutacion(
            nombre="reloj_en_vez_de_corte",
            que_rompe="Resolver los períodos con `now()` en lugar del `AS_OF`",
            debe_romper=("c-001", "c-004", "c-005", "c-007", "c-012", "c-014"),
            usa_el_reloj=True,
        ),
        Mutacion(
            nombre="potencial_es_pep",
            que_rompe="Contar `POTENTIAL_HIT` como PEP",
            debe_romper=("c-002", "a-005"),
            parches=(
                ("riesgo_alto", r"= 'CONFIRMED_HIT'", "IN ('CONFIRMED_HIT', 'POTENTIAL_HIT')"),
                ("pep_confirmado", r"= 'CONFIRMED_HIT'", "IN ('CONFIRMED_HIT', 'POTENTIAL_HIT')"),
            ),
            calla=(("pep_confirmado", "DISCARDED"),),
        ),
    ]
}


_CONFIG_VIEJA = agent.tools._Q_CONFIG_VIGENTE.replace(
    "ORDER BY key, effective_from_date DESC", "ORDER BY key, effective_from_date ASC"
)
assert "ASC" in _CONFIG_VIEJA, "cambió la consulta de config y esta mutación quedó inerte"


def _con_el_reloj(expresion: str, corte: str | None = None, fiscal_year_start_month=None):
    """La mutación que el enunciado llama "usar now()": los períodos contra el
    reloj de la máquina y no contra la fecha de corte del dataset."""
    return core.periodos.resolver_periodo(
        expresion, datetime.date.today().isoformat(), fiscal_year_start_month
    )


@contextmanager
def aplicada(nombre: str | None, sin_skills: bool = False, solo_skill: str | None = None):
    """Deja el sistema mutado mientras dure el bloque, y lo devuelve intacto.

    Se restaura en `finally` y no al final del bloque: si una corrida se cae a la
    mitad, el proceso siguiente no puede heredar una skill rota.
    """
    skills = _skills()
    intactas = copy.deepcopy(skills)
    resolver = agent.tools.resolver_periodo
    config_vigente = agent.tools._Q_CONFIG_VIGENTE
    mutacion = MUTACIONES[nombre] if nombre else None

    try:
        if sin_skills:
            skills.clear()
        elif solo_skill:
            for concepto in [c for c in skills if c != solo_skill]:
                del skills[concepto]
        if mutacion:
            mutacion.aplicar(skills)
            if mutacion.usa_el_reloj:
                agent.tools.resolver_periodo = _con_el_reloj
            if mutacion.usa_la_config_vieja:
                agent.tools._Q_CONFIG_VIGENTE = _CONFIG_VIEJA
        yield mutacion
    finally:
        skills.clear()
        skills.update(intactas)
        agent.tools.resolver_periodo = resolver
        agent.tools._Q_CONFIG_VIGENTE = config_vigente


def titulo(nombre: str | None, sin_skills: bool = False, solo_skill: str | None = None) -> str:
    if nombre:
        return f"Mutación · {MUTACIONES[nombre].que_rompe}"
    if sin_skills:
        return "Ablación · el agente sin definiciones curadas"
    if solo_skill:
        return f"Ablación · sólo la definición de `{solo_skill}`"
    return "Set de evaluación"


def slug(nombre: str | None, sin_skills: bool = False, solo_skill: str | None = None) -> str:
    if nombre:
        return f"mutacion-{nombre.replace('_', '-')}"
    if sin_skills:
        return "ablacion-sin-skills"
    if solo_skill:
        return f"ablacion-solo-{solo_skill.replace('_', '-')}"
    return ""
