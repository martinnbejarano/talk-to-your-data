"""Las cinco tools que el agente puede llamar, y lo que el modelo lee de ellas.

Ninguna toca psycopg: las cinco pasan por `core.db.ejecucion.ejecutar`, el único
lugar donde vive la garantía de aislamiento (D-02, D-03).
"""

from __future__ import annotations

import re
from functools import cache

import yaml

from core.config import RAIZ
from core.db.ejecucion import (
    Fallo,
    Ok,
    Rechazada,
    ejecutar,
    tablas_grandes_del_catalogo,
)
from core.periodos import resolver_periodo

SEMANTICS = RAIZ / "core" / "semantics"

# El validador de trazabilidad mira las filas **enteras**, así que recortar acá
# no habilita a publicar un número sin respaldo: sólo cuida el contexto.
FILAS_QUE_VE_EL_MODELO = 50

# Un identificador tal como lo escribe el esquema de esta base: en minúscula y
# sin comillas. Lo necesita `sample_values`, la única tool que interpola.
_IDENTIFICADOR = re.compile(r"^[a-z_][a-z0-9_]*$")


_Q_TABLAS = """
SELECT c.relname,
       c.reltuples::bigint,
       EXISTS (SELECT 1 FROM information_schema.columns col
                WHERE col.table_schema = 'public'
                  AND col.table_name = c.relname
                  AND col.column_name = 'tenant_id'),
       EXISTS (SELECT 1 FROM information_schema.columns col
                WHERE col.table_schema = 'public'
                  AND col.table_name = c.relname
                  AND col.column_name = 'deleted_at')
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname
"""

_Q_COLUMNAS = """
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position
"""

_Q_INDICES = """
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname
"""

# La trampa más cara del dataset es tomar la versión vieja de un umbral: de ahí
# el `DISTINCT ON`, igual que en las nueve goldens.
_Q_CONFIG_VIGENTE = """
SELECT DISTINCT ON (key) key, value #>> '{}', effective_from_date
FROM tenant_config
WHERE tenant_id = %(tenant)s
  AND key = ANY(%(claves)s)
  AND effective_from_date <= %(as_of)s::date
ORDER BY key, effective_from_date DESC
"""


# `list_tables` y `describe_table` no son el camino caliente: con el esquema en
# el system prompt no se llamaron ni una vez en las 18 corridas del prototipo
# (`NOTES/03-prototipo.md` §2). Se quedan para la pregunta sin skill, y para el
# día que el esquema del prompt se recorte.
def list_tables(institucion_id: int) -> str:
    """Las tablas, con su tamaño estimado y las dos columnas que cambian una consulta.

    El tamaño va porque el agente necesita saber cuál es "grande" **antes** de
    que el gate se lo diga: un rechazo cuesta el 70 % de una pregunta entera en
    tokens (§2). `tenant_id` y `deleted_at`, porque olvidadas producen un número
    plausible y equivocado.
    """
    resultado = ejecutar(_Q_TABLAS, {}, institucion_id)
    if not isinstance(resultado, Ok):
        return texto_para_el_modelo(resultado)

    grandes = tablas_grandes_del_catalogo()
    lineas = ["tabla · filas estimadas · tamaño · columnas que importan"]
    for tabla, filas, tiene_tenant, tiene_borrado in resultado.filas:
        marcas = [c for c, hay in (("tenant_id", tiene_tenant), ("deleted_at", tiene_borrado)) if hay]
        lineas.append(
            f"{tabla} · {_miles(filas)} · "
            f"{'GRANDE' if tabla in grandes else 'chica'} · "
            f"{', '.join(marcas) or 'sin tenant_id ni deleted_at'}"
        )
    return "\n".join(lineas)


def describe_table(institucion_id: int, tabla: str) -> str:
    """Columnas, tipos, nullability e índices de una tabla.

    Los índices los pide D-06: sin la lista el agente escribe consultas que el
    gate rechaza. Sale de la misma ficha que el system prompt a propósito — dos
    representaciones de la misma tabla envejecerían distinto.
    """
    ficha = _fichas(institucion_id).get(tabla)
    if ficha is None:
        conocidas = ", ".join(sorted(_fichas(institucion_id)))
        return f"No existe la tabla `{tabla}`. Las que hay son: {conocidas}."
    return ficha


def sample_values(institucion_id: int, tabla: str, columna: str, limite: int = 25) -> str:
    """Existe por los **siete enums sin `CHECK`** que encontró H1: sus valores no
    están en el esquema, y adivinarlos produce un `WHERE` que filtra todo o nada.

    No lleva `WHERE tenant_id` y no le hace falta: la conexión ya corre bajo RLS,
    y sobre las tablas grandes el planificador resuelve el `DISTINCT` por el
    índice que tiene la institución como primera columna
    (`NOTES/01-limites-y-planes.md` §2). La única que el gate rechaza es
    `audit_log`, que no tiene ese índice — y el filtro tampoco la salvaría.
    """
    if not _IDENTIFICADOR.match(tabla) or not _IDENTIFICADOR.match(columna):
        return (
            f"`{tabla}`.`{columna}` no es un nombre de tabla y columna: se "
            "escriben en minúscula, sin comillas y sin el nombre del esquema."
        )

    # Un `limite` sin tope es una columna de alta cardinalidad devuelta entera:
    # el modelo puede pedir cualquier número, y unirlos todos en una sola línea
    # sin cortar reventó una corrida real con un string de 64 MB.
    limite = min(int(limite), FILAS_QUE_VE_EL_MODELO)

    resultado = ejecutar(
        f"SELECT DISTINCT {columna} AS valor FROM {tabla} LIMIT {int(limite)}",
        {},
        institucion_id,
    )
    if not isinstance(resultado, Ok):
        return texto_para_el_modelo(resultado)

    valores = ", ".join(repr(v) for (v,) in resultado.filas)
    return f"{tabla}.{columna} · {len(resultado.filas)} valores distintos: {valores or '(ninguno)'}"


def get_definition(institucion_id: int, concepto: str) -> str:
    """La skill de un concepto: definición, trampas, escalones, config y golden.

    Los escalones van como obligación y no como sugerencia porque de ocho
    corridas del prototipo sólo tres devolvieron los siete que la skill declara
    (`NOTES/03-prototipo.md` §5.2). La config va con su `effective_from_date`
    porque si no el `parametro` y el `vigente_desde` los escribiría el modelo de
    memoria, y una fecha inventada no la atrapa el validador de trazabilidad.
    """
    skill = _skills().get(concepto)
    if skill is None:
        return (
            f"No hay definición curada para `{concepto}`. Los conceptos con "
            f"definición son: {', '.join(sorted(_skills()))}."
        )

    partes = [
        f"# {skill['concepto']} — {skill['nombre_humano']}",
        f"\n## Definición\n{skill['definicion'].strip()}",
        "\n## Trampas\n" + "\n".join(f"- {t.strip()}" for t in skill.get("trampas", [])),
        (
            "\n## Escalones que tu consulta TIENE que devolver\n"
            "Una sola fila, una columna por escalón, con estos nombres y en este orden:\n"
            + "\n".join(f"- `{e}` — {t}" for e, t in escalones_de(concepto).items())
            + "\n\nSi reescribís la consulta —porque el gate te rechazó el plan o porque la "
            "pregunta se corre de la canónica— seguí devolviendo estas mismas columnas."
            f"\n\n**El escalón que va en `valor` es `{skill['resultado']}`.** No es "
            "necesariamente el último de la lista: leé el nombre, no la posición."
        ),
        f"\n## Período por defecto\n{skill.get('periodo_por_defecto', '(la pregunta no lleva período)')}",
        "\n## Exclusiones a declarar\n" + "\n".join(f"- {e}" for e in skill.get("exclusiones", [])),
    ]
    if supuestos := skill.get("supuestos"):
        partes.append("\n## Supuestos a declarar\n" + "\n".join(f"- {s.strip()}" for s in supuestos))
    if opciones := skill.get("opciones"):
        partes.append("\n## Lecturas posibles\n" + "\n".join(f"- {o}" for o in opciones))
    if no_aplica := skill.get("no_aplica_cuando"):
        partes.append(f"\n## No aplica cuando\n{no_aplica.strip()}")

    partes.append(_config_vigente(institucion_id, skill))
    partes.append(
        "\n## Consulta de referencia (validada, adaptala)\n"
        "Es la consulta con la que se verificó esta definición contra la base. "
        "Adaptala a la pregunta —cambiá el período, agregá un segmento, abrí por "
        "país— en vez de copiarla textual.\n"
        f"```sql\n{skill['golden_sql'].strip()}\n```"
    )
    return "\n".join(partes)


def run_sql(institucion_id: int, sql: str, periodo: str | None = None) -> Ok | Rechazada | Fallo:
    """El seam de SQL, tal cual. Lo único que agrega es el período.

    Que `periodo` lo resuelva el sistema y no el modelo impide que un "este año"
    termine siendo un `now()` o un rango inventado. La institución y la fecha de
    corte no viajan por acá: las pone el seam (D-03) y pisan lo que el modelo
    escriba.
    """
    desde, hasta = resolver_periodo(periodo) if periodo else (None, None)
    return ejecutar(sql, {"desde": desde, "hasta": hasta}, institucion_id)


# A mano y no por descubrimiento con decorador: leer este archivo tiene que
# alcanzar para saber qué puede hacer el agente.
TOOLS = {
    "list_tables": list_tables,
    "describe_table": describe_table,
    "sample_values": sample_values,
    "get_definition": get_definition,
    "run_sql": run_sql,
}

# Lo mismo en el dialecto del proveedor, al lado del registro para que agregar
# una tool sea una edición en un solo lugar. `institucion_id` no está en ningún
# esquema a propósito: no es un argumento del modelo, lo pone el loop.
#
# Shape de `/v1/responses` (plano), no el de `/v1/chat/completions` (anidado
# bajo `"function"`): la migración de H5 movió el loop de endpoint porque los
# modelos gpt-5.6 no soportan tool calling con razonamiento en el viejo.
ESPECIFICACIONES = [
    {
        "type": "function",
        "name": "list_tables",
        "description": (
            "Las tablas de la base con su tamaño estimado, y si tienen "
            "tenant_id y deleted_at."
        ),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "describe_table",
        "description": "Columnas, tipos, nullability e índices disponibles de una tabla.",
        "parameters": {
            "type": "object",
            "properties": {"tabla": {"type": "string"}},
            "required": ["tabla"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "sample_values",
        "description": (
            "Los valores distintos que toma una columna. Usalo cuando el "
            "tipo no te dice qué valores admite: varios enums de esta base "
            "no tienen CHECK y sus valores no están en el esquema."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tabla": {"type": "string"},
                "columna": {"type": "string"},
                "limite": {"type": ["integer", "null"], "description": "por defecto 25, tope 50"},
            },
            "required": ["tabla", "columna", "limite"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_definition",
        "description": (
            "La definición curada de un concepto del negocio: qué cuenta, "
            "qué trampas tiene, qué escalones tiene que devolver la "
            "derivación, la config vigente de la institución y una consulta "
            "de referencia validada. Pedila SIEMPRE antes de escribir SQL "
            "sobre un concepto del catálogo."
        ),
        "parameters": {
            "type": "object",
            "properties": {"concepto": {"type": "string"}},
            "required": ["concepto"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "run_sql",
        "description": (
            "Ejecuta un SELECT de lectura y devuelve sus filas, su plan y "
            "su tiempo. La institución y la fecha de corte las pone el "
            "sistema: escribí %(tenant)s y %(as_of)s en el SQL. Para el "
            "período escribí %(desde)s y %(hasta)s y pasá `periodo`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string"},
                "periodo": {
                    "type": ["string", "null"],
                    "enum": ["este año", "último trimestre", None],
                    "description": "sólo si la consulta usa %(desde)s y %(hasta)s",
                },
            },
            "required": ["sql", "periodo"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def texto_para_el_modelo(resultado) -> str:
    """Cómo lee el modelo lo que devolvió una tool.

    Un `Rechazada` que se leyera como un error haría que el agente abandone en
    vez de reescribir, que es lo contrario de lo que el gate quiere.
    """
    if isinstance(resultado, str):
        return resultado

    if isinstance(resultado, Ok):
        cabecera = f"OK · {len(resultado.filas)} fila(s) · {resultado.ms:.0f} ms"
        if not resultado.filas:
            return f"{cabecera}\nLa consulta no devolvió ninguna fila."
        renglones = [" | ".join(resultado.columnas)]
        renglones += [
            " | ".join("NULL" if v is None else str(v) for v in fila)
            for fila in resultado.filas[:FILAS_QUE_VE_EL_MODELO]
        ]
        if len(resultado.filas) > FILAS_QUE_VE_EL_MODELO:
            renglones.append(f"… ({len(resultado.filas)} filas en total)")
        return f"{cabecera}\n" + "\n".join(renglones)

    if isinstance(resultado, Rechazada):
        # El renglón final: obedecer una sugerencia de costo a secas fusionó
        # `total` con `activos` y la derivación perdió la resta que el oficial
        # tiene que ver (`NOTES/03-prototipo.md` §5.3).
        return (
            "RECHAZADA por el gate: la consulta no se ejecutó.\n"
            f"motivo: {resultado.motivo}\n"
            f"sugerencia: {resultado.sugerencia}\n"
            "Reescribila siguiendo la sugerencia, pero seguí devolviendo las "
            "mismas columnas: la derivación las necesita."
        )

    if isinstance(resultado, Fallo):
        return f"FALLO {resultado.clase}: {resultado.detalle}\n{_QUE_HACER_CON[resultado.clase]}"

    raise TypeError(f"una tool devolvió algo que el modelo no sabe leer: {type(resultado)}")


# La clase del error decide el reintento, no el texto de Postgres
# (`NOTES/01-limites-y-planes.md` §1). `PERMISO` es el único que no reintenta.
_QUE_HACER_CON = {
    "TIMEOUT": "La consulta era demasiado cara. Reescribila más acotada: acotá el período o sacá un join.",
    "SINTAXIS": "Corregí la consulta. El renglón del error es el de tu SQL.",
    "PERMISO": "No reintentes: el rol es de sólo lectura y esto no lo puede leer. Contestá qué falta.",
    "OTRO": "Revisá contra el esquema que la tabla y las columnas existan y se llamen así.",
}


def esquema_con_indices(institucion_id: int) -> str:
    """El esquema entero para el system prompt: tablas, columnas e índices.

    Va en el prompt y no detrás de una tool porque con el esquema adelante el
    prototipo midió convergencia en dos pasos, sin gastar un turno explorando.
    Se descubre por catálogo: uno transcripto envejece con el primer `ALTER`.
    """
    return "\n".join(_fichas(institucion_id).values())


@cache
def catalogo_de_conceptos() -> str:
    """Nombre y una línea por concepto, no las nueve skills enteras: alcanzó para
    que el agente pidiera la definición como primer paso en 12 de 12 corridas
    del prototipo, y las nueve costarían el contexto de tres preguntas.
    """
    return "\n".join(
        f"- `{concepto}` — {skill['nombre_humano']}" for concepto, skill in sorted(_skills().items())
    )


def escalones_de(concepto: str) -> dict[str, str]:
    """Los escalones que la derivación de un concepto tiene que traer, con su texto.

    `metricas` entra en la misma lista porque el contrato aplana los dos campos
    en uno solo: un promedio con su unidad es un escalón más.
    """
    skill = _skills().get(concepto)
    if skill is None:
        return {}
    return {d["escalon"]: d["texto"] for d in skill["derivacion"]} | {
        m["nombre"]: f"{m['texto']} · unidad: {m['unidad']}" for m in skill.get("metricas", [])
    }


@cache
def _skills() -> dict[str, dict]:
    """Las nueve skills de `core/semantics/`, por concepto. Se leen al primer
    pedido y no al importar: importar `agent.tools` no tiene que hacer I/O.
    """
    archivos = sorted(SEMANTICS.glob("*.yaml"))
    skills = [yaml.safe_load(a.read_text(encoding="utf-8")) for a in archivos]
    return {skill["concepto"]: skill for skill in skills}


def _config_vigente(institucion_id: int, skill: dict) -> str:
    """El valor vigente al corte de las perillas de las que depende una skill."""
    claves = skill.get("depende_de_config") or []
    if not claves:
        return "\n## Config de tu institución\nEste concepto no depende de ninguna perilla."

    resultado = ejecutar(_Q_CONFIG_VIGENTE, {"claves": list(claves)}, institucion_id)
    if not isinstance(resultado, Ok):
        return "\n## Config de tu institución\n" + texto_para_el_modelo(resultado)

    lineas = [
        f"- `{clave}` = {valor} · origen `tenant_config` · rige desde {desde}"
        for clave, valor, desde in resultado.filas
    ]
    faltantes = [c for c in claves if c not in {f[0] for f in resultado.filas}]
    lineas += [f"- `{c}` — sin valor configurado para esta institución" for c in faltantes]
    return (
        "\n## Config de tu institución (vigente a la fecha de corte)\n"
        + "\n".join(lineas)
        + "\nEstos valores salieron de una consulta: usalos en `definiciones_usadas`."
    )


@cache
def _fichas(institucion_id: int) -> dict[str, str]:
    """Una ficha de texto por tabla: tamaño, columnas e índices. Alimenta tanto el
    system prompt como `describe_table`, que son lo mismo mirado entero o de a
    una tabla. El `cache` evita tres viajes a la base por llamada.
    """
    tablas = ejecutar(_Q_TABLAS, {}, institucion_id)
    columnas = ejecutar(_Q_COLUMNAS, {}, institucion_id)
    indices = ejecutar(_Q_INDICES, {}, institucion_id)
    for resultado in (tablas, columnas, indices):
        if not isinstance(resultado, Ok):
            raise RuntimeError(f"no se pudo leer el catálogo: {texto_para_el_modelo(resultado)}")

    grandes = tablas_grandes_del_catalogo()
    fichas = {}
    for tabla, filas, _, _ in tablas.filas:
        cols = [
            f"{nombre} {tipo}{'' if nulable == 'YES' else ' NOT NULL'}"
            for t, nombre, tipo, nulable in columnas.filas
            if t == tabla
        ]
        # De `CREATE INDEX x ON public.y USING btree (a, b) WHERE …` sólo
        # interesa lo que sigue al `USING`: método, columnas y —lo que más
        # importa acá— el `WHERE` de los índices parciales.
        idx = [
            f"{nombre} {definicion.partition(' USING ')[2]}"
            for t, nombre, definicion in indices.filas
            if t == tabla
        ]
        fichas[tabla] = (
            f"## {tabla} · {_miles(filas)} filas · {'GRANDE' if tabla in grandes else 'chica'}\n"
            f"cols: {', '.join(cols)}\n"
            f"idx: {'; '.join(idx) or '(ninguno)'}"
        )
    return fichas


def _miles(n: int) -> str:
    """180000 se lee `180.000`, que es como lo escribe el oficial y el contrato."""
    return f"{n:,}".replace(",", ".")
