"""Los criterios con los que se valida una skill de `core/semantics/`.

Compartido entre `tests/test_semantica.py` y `scripts/validar_semantica.py`, y
sin pytest ni conexión encima: el criterio del filtro de borrado marcó al revés
siete de las nueve goldens en su primer intento (`NOTES/02-semantica.md` §2.4), y
dos copias serían dos lugares donde volver a equivocarse.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from core.config import AS_OF
from core.periodos import ULTIMO_TRIMESTRE, resolver_periodo

SEMANTICS = Path(__file__).resolve().parents[1] / "core" / "semantics"

# Por catálogo y no escritas acá: si el dump cambia, el criterio acompaña.
Q_TABLAS_BORRABLES = """
SELECT table_name FROM information_schema.columns
WHERE table_schema = 'public' AND column_name = 'deleted_at';
"""

def tablas_borrables(conn) -> set[str]:
    """Recibe la conexión en vez de abrirla: el script la quiere de administrador y
    la suite la saca de su propia fixture."""
    return {t for (t,) in conn.execute(Q_TABLAS_BORRABLES).fetchall()}


_ALIAS = re.compile(
    r"\b(?:FROM|JOIN)\s+(?P<tabla>\w+)(?:\s+(?!ON\b|AS\b|WHERE\b|GROUP\b|ORDER\b|"
    r"LEFT\b|JOIN\b|CROSS\b|LIMIT\b|HAVING\b)(?P<alias>\w+))?",
    re.IGNORECASE,
)


def cargar_skills(filtro: str | None = None) -> list[dict]:
    """Las skills de `core/semantics/`, en orden de archivo."""
    archivos = sorted(SEMANTICS.glob("*.yaml"))
    if filtro:
        archivos = [a for a in archivos if filtro in a.stem]
    return [yaml.safe_load(a.read_text(encoding="utf-8")) for a in archivos]


def parametros(tenant_id: int, skill: dict) -> dict:
    """Los cuatro parámetros de una golden, siempre los cuatro aunque la consulta
    use dos."""
    desde, hasta = resolver_periodo(skill.get("periodo_por_defecto", ULTIMO_TRIMESTRE))
    return {"tenant": tenant_id, "as_of": AS_OF, "desde": desde, "hasta": hasta}


def soft_delete_sin_filtrar(sql: str, borrables: set[str]) -> list[str]:
    """Tablas con `deleted_at` que entran al join sin su filtro.

    Se busca atado al **alias** y no cerca del nombre de la tabla: en las cascadas
    el filtro vive dentro de un `FILTER` que aparece *antes* del `FROM`, y buscarlo
    por cercanía marca en falso justo a las consultas mejor escritas.
    """
    faltan = []
    for m in _ALIAS.finditer(sql):
        tabla = m.group("tabla")
        if tabla not in borrables:
            continue
        prefijo = m.group("alias") or tabla
        if not re.search(rf"\b{re.escape(prefijo)}\.deleted_at\s+IS\s+NULL", sql, re.I):
            faltan.append(f"{tabla} (como {prefijo})")
    return faltan


def seq_scans_prohibidos(conn, sql: str, params: dict, grandes: set[str]) -> list[str]:
    """Nodos `Seq Scan` sobre una tabla grande, que es lo que D-06 rechaza.

    Sobre una chica no es un hallazgo: para las cinco sin índice por `tenant_id` es
    el único plan posible y cuesta 55-170 ms.
    """
    plan = conn.execute(f"EXPLAIN (FORMAT JSON) {sql}", params).fetchone()[0]
    encontrados: list[str] = []

    def recorrer(nodo: dict) -> None:
        if nodo.get("Node Type") == "Seq Scan" and nodo.get("Relation Name") in grandes:
            encontrados.append(nodo["Relation Name"])
        for hijo in nodo.get("Plans", []):
            recorrer(hijo)

    recorrer(plan[0]["Plan"])
    return encontrados
