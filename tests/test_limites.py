"""El `statement_timeout` muerde, y muerde porque es del rol.

Dos afirmaciones, y hacen falta las dos:

1. Que muerde, con `SQLSTATE 57014`. Se afirma el sqlstate y nunca el texto del
   mensaje: el código es estable, el wording cambia entre versiones y con la
   locale (ver NOTES/01-limites-y-planes.md).
2. Que el límite es del rol y no del servidor. El `docker-compose.yml` ya trae
   los 15s a nivel servidor, así que el test 1 solo daría verde igual aunque
   `infra/bootstrap.sql` no tuviera el `ALTER ROLE`.

El primero espera los 15 segundos completos y por eso va marcado `lento`.
"""

from __future__ import annotations

import psycopg
import pytest

from core.db import agent_connection, apply_bootstrap
from conftest import conectar_como_admin

# `query_canceled`: el único identificador estable de "murió por timeout", y lo
# que H3 mira para distinguirlo de un error de sintaxis o de permisos.
QUERY_CANCELED = "57014"

# El `CROSS JOIN` —200 md5 por fila— está para que el costo no dependa del
# hardware: un test de timeout que en una máquina rápida termina antes de los
# 15 s no falla ruidosamente, da verde sin haber afirmado nada.
CONSULTA_DESBOCADA = """
    SELECT count(*)
    FROM transactions t
    CROSS JOIN generate_series(1, 200) AS g
    WHERE md5((t.id + g)::text) < '00'
"""

# Con RLS activo el planificador nunca elige un `Seq Scan` sobre `transactions`
# por su cuenta (ver `test_planes.py`), así que para ejercer el peor caso hay que
# apagarle los caminos por índice — algo que `agent_ro` puede hacer por su cuenta
# y que el agente de H3 podría hacer sin querer.
APAGAR_LOS_CAMINOS_POR_INDICE = (
    "SET LOCAL enable_indexscan = off",
    "SET LOCAL enable_bitmapscan = off",
    "SET LOCAL enable_indexonlyscan = off",
)


@pytest.mark.lento
def test_una_consulta_desbocada_sobre_transactions_muere_por_timeout(tenant_a):
    """Tarda 15 segundos a propósito: es lo que se está afirmando.

    Falla si se saca el `ALTER ROLE ... SET statement_timeout` del bootstrap *y*
    se afloja el límite del servidor. Que con una sola de las dos siga verde es
    la redundancia que se buscaba.
    """
    with agent_connection(tenant_a) as conn:
        for apagar in APAGAR_LOS_CAMINOS_POR_INDICE:
            conn.execute(apagar)

        plan = "\n".join(
            fila[0] for fila in conn.execute("EXPLAIN " + CONSULTA_DESBOCADA)
        )
        assert "Seq Scan on transactions" in plan, (
            f"la consulta dejó de recorrer entera `transactions`, así que ya no "
            f"es el peor caso que este test quiere ejercer:\n{plan}"
        )

        with pytest.raises(psycopg.Error) as murio:
            conn.execute(CONSULTA_DESBOCADA)

    assert murio.value.sqlstate == QUERY_CANCELED, (
        f"la consulta desbocada no murió por timeout sino con sqlstate "
        f"{murio.value.sqlstate}: {murio.value}"
    )


def test_el_limite_es_del_rol_y_no_solo_del_servidor(tenant_a):
    """Que el rol lleve su propio límite es observable, y así se observa.

    Se le baja el `statement_timeout` al rol y se corre una consulta que el
    límite del servidor habría dejado terminar de sobra: si muere igual, el que
    gobierna la conexión del agente es el del rol. El del servidor no se toca en
    ningún momento, sólo se lee para poder afirmar que habría alcanzado.
    """
    with conectar_como_admin() as adm:
        limite_del_servidor_ms = int(
            adm.execute(
                "SELECT setting FROM pg_settings WHERE name = 'statement_timeout'"
            ).fetchone()[0]
        )
    assert limite_del_servidor_ms >= 2000, (
        f"el límite del servidor es de {limite_del_servidor_ms} ms y no habría "
        f"dejado terminar el pg_sleep(1): el test no distinguiría un límite del "
        f"otro"
    )

    try:
        with conectar_como_admin() as adm:
            adm.execute("ALTER ROLE agent_ro SET statement_timeout = '200ms'")

        with agent_connection(tenant_a) as conn:
            with pytest.raises(psycopg.Error) as murio:
                conn.execute("SELECT pg_sleep(1)")
    finally:
        apply_bootstrap()

    assert murio.value.sqlstate == QUERY_CANCELED, (
        f"con el límite del rol en 200 ms, un pg_sleep(1) tendría que morir por "
        f"timeout y murió con sqlstate {murio.value.sqlstate}: {murio.value}"
    )

    with agent_connection(tenant_a) as conn:
        assert conn.execute("SHOW statement_timeout").fetchone()[0] == "15s", (
            "el bootstrap no le devolvió al rol su statement_timeout de 15s"
        )
