"""«Sólo lectura» tiene que ser una propiedad de la base, no una costumbre del código.

Tres capas, y las tres hacen falta:

1. A través de la costura: lo que le va a pasar al agente de verdad.
2. Contra el ACL, con una escritura real en una transacción `READ WRITE`. Hace
   falta porque la costura abre la transacción de sólo lectura y la escritura
   muere ahí (`25006`) *antes* de que Postgres mire el ACL: con la capa 1 sola,
   un `GRANT UPDATE` accidental daría verde igual.
3. Sobre los privilegios declarados, tabla por tabla. Hace falta porque un
   `GRANT` sobre una tabla que a nadie se le ocurrió poner en `ESCRITURAS` sólo
   se ve ahí.
"""

from __future__ import annotations

import psycopg
import pytest

from core.config import dsn_agente
from core.db import agent_connection
from conftest import conectar_como_admin

# Los dos sqlstate con los que la base puede negar una escritura. Por la costura
# sale siempre el primero; el test de la costura acepta los dos porque cuál de
# las dos barreras la frenó es un detalle interno.
DENEGADA_POR_SOLO_LECTURA = "25006"
DENEGADA_POR_PERMISOS = "42501"

# Ninguna de estas escrituras puede tocar información regulatoria ni siquiera si
# un día dejaran de ser denegadas: `WHERE false` no matchea nada y los `INSERT`
# van a la institución 0, que no existe. Ni el chequeo de la transacción ni el
# del ACL miran las filas, así que el resguardo sale gratis.
ESCRITURAS = [
    ("clients", "INSERT INTO clients (tenant_id) VALUES (0)"),
    ("clients", "UPDATE clients SET full_name = 'x' WHERE false"),
    ("clients", "DELETE FROM clients WHERE false"),
    ("transactions", "INSERT INTO transactions (tenant_id) VALUES (0)"),
    ("transactions", "UPDATE transactions SET amount = 0 WHERE false"),
    ("transactions", "DELETE FROM transactions WHERE false"),
]

# Los ocho que Postgres 17 puede otorgar sobre una tabla. Se preguntan todos para
# afirmar "tiene exactamente SELECT" y no "no tiene los tres que se me ocurrieron".
PRIVILEGIOS_DE_TABLA = [
    "SELECT", "INSERT", "UPDATE", "DELETE",
    "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN",
]

Q_PRIVILEGIOS_SOBRE_TABLAS = """
SELECT c.relname, p.privilegio
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN unnest(%s::text[]) AS p(privilegio)
WHERE n.nspname = 'public'
  AND c.relkind IN ('r', 'p', 'v', 'm')
  AND has_table_privilege('agent_ro', c.oid, p.privilegio)
ORDER BY c.relname, p.privilegio;
"""

Q_PRIVILEGIOS_SOBRE_SECUENCIAS = """
SELECT c.relname, p.privilegio
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN unnest(ARRAY['SELECT', 'UPDATE', 'USAGE']) AS p(privilegio)
WHERE n.nspname = 'public'
  AND c.relkind = 'S'
  AND has_sequence_privilege('agent_ro', c.oid, p.privilegio)
ORDER BY c.relname, p.privilegio;
"""

Q_RELACIONES_DE_AGENT_RO = """
SELECT c.relname, c.relkind
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relowner = 'agent_ro'::regrole
ORDER BY c.relname;
"""


@pytest.mark.parametrize(
    "tabla, escritura",
    ESCRITURAS,
    ids=[f"{tabla}-{escritura.split()[0].lower()}" for tabla, escritura in ESCRITURAS],
)
def test_la_costura_deniega_toda_escritura(tabla, escritura, tenant_a):
    """Por donde va a pasar el agente, escribir no se puede."""
    with agent_connection(tenant_a) as conn:
        with pytest.raises(psycopg.Error) as denegada:
            conn.execute(escritura)

    assert denegada.value.sqlstate in (DENEGADA_POR_SOLO_LECTURA, DENEGADA_POR_PERMISOS), (
        f"{tabla}: la escritura no fue denegada por la base, falló por otra "
        f"cosa (sqlstate {denegada.value.sqlstate})"
    )


@pytest.mark.parametrize(
    "tabla, escritura",
    ESCRITURAS,
    ids=[f"{tabla}-{escritura.split()[0].lower()}" for tabla, escritura in ESCRITURAS],
)
def test_una_escritura_real_muere_por_permisos_y_no_por_la_transaccion(tabla, escritura):
    """La denegación que la costura tapa, observada de verdad.

    La transacción de sólo lectura es una decisión de `agent_connection`, no un
    atributo del rol: `agent_ro` puede pedir `READ WRITE`, y sin esa barrera de
    encima la escritura llega hasta el ACL y muere con `42501`. Por eso se
    conecta por fuera de la costura, sin abrirle a `core/db` una tercera entrada.

    El caso del `INSERT` es más débil y conviene decirlo: con RLS activo y sin
    policy `FOR INSERT`, un `GRANT INSERT` daría `42501` igual. Ese lo caza el
    test de privilegios de acá abajo, no éste.
    """
    with psycopg.connect(dsn_agente()) as conn:
        try:
            conn.execute("SET TRANSACTION READ WRITE")
            with pytest.raises(psycopg.Error) as denegada:
                conn.execute(escritura)
        finally:
            # La transacción quedó abortada por el error: se cierra a mano.
            conn.rollback()

    assert denegada.value.sqlstate == DENEGADA_POR_PERMISOS, (
        f"{tabla}: la escritura no fue denegada por permisos sino con sqlstate "
        f"{denegada.value.sqlstate}. Si dice {DENEGADA_POR_SOLO_LECTURA}, la "
        f"transacción se abrió de sólo lectura y el test volvió a tapar el ACL"
    )


def test_la_superficie_de_permisos_es_usage_sobre_el_esquema_y_select_sobre_las_tablas():
    """El `GRANT` de más que la costura no puede ver.

    `has_*_privilege` contempla también lo que llega por `PUBLIC` o por
    pertenencia a otro rol, que es lo que un `SELECT` sobre `information_schema`
    se perdería.
    """
    with conectar_como_admin() as adm:
        puede_usar_el_esquema, puede_crear_en_el_esquema = adm.execute(
            "SELECT has_schema_privilege('agent_ro', 'public', 'USAGE'),"
            "       has_schema_privilege('agent_ro', 'public', 'CREATE')"
        ).fetchone()
        privilegios = set(adm.execute(Q_PRIVILEGIOS_SOBRE_TABLAS, [PRIVILEGIOS_DE_TABLA]))
        tablas = {tabla for (tabla,) in adm.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm')"
        )}

    assert puede_usar_el_esquema, "agent_ro no puede ni abrir el esquema public"
    assert not puede_crear_en_el_esquema, "agent_ro puede crear objetos en public"
    assert privilegios == {(tabla, "SELECT") for tabla in tablas}, (
        "los privilegios de agent_ro no son exactamente SELECT sobre cada "
        f"tabla: sobran {sorted(privilegios - {(t, 'SELECT') for t in tablas})}, "
        f"faltan {sorted({(t, 'SELECT') for t in tablas} - privilegios)}"
    )


def test_agent_ro_no_tiene_ningun_privilegio_sobre_las_secuencias():
    """Nada sobre secuencias: no las necesita, porque no escribe."""
    with conectar_como_admin() as adm:
        cuantas_secuencias = adm.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind = 'S'"
        ).fetchone()[0]
        privilegios = adm.execute(Q_PRIVILEGIOS_SOBRE_SECUENCIAS).fetchall()

    assert cuantas_secuencias > 0, "no hay secuencias en el dump: el test no afirma nada"
    assert privilegios == [], f"agent_ro tiene privilegios sobre secuencias: {privilegios}"


def test_agent_ro_no_es_dueno_de_ninguna_relacion():
    """La propiedad silenciosa de la que depende todo el blindaje.

    El dueño de una tabla se saltea las policies salvo que tenga `FORCE ROW
    LEVEL SECURITY`. Alcanza con que alguien cree una tabla conectado como
    `agent_ro` para romperlo, y desde afuera no se nota hasta que se filtra algo.
    """
    with conectar_como_admin() as adm:
        de_agent_ro = adm.execute(Q_RELACIONES_DE_AGENT_RO).fetchall()
        duenos = adm.execute(
            "SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()

    assert de_agent_ro == [], f"agent_ro es dueño de {de_agent_ro}"
    assert duenos and all(dueno != "agent_ro" for (dueno,) in duenos), (
        f"las tablas de public tienen que ser de otro rol, y son de {duenos}"
    )
