"""El bootstrap se corre después de cada restore, así que tiene que ser idempotente.

Aplicarlo no es un paso de instalación que se hace una vez, es rutina — y una
rutina que puede fallar la segunda vez no es rutina.
"""

from __future__ import annotations

from core.db import agent_connection, apply_bootstrap


def test_aplicar_el_bootstrap_dos_veces_seguidas_deja_el_blindaje_en_pie(tenant_a):
    """Correrlo de nuevo no falla y no afloja nada.

    Se afirma comportamiento observable y no la forma interna del script. Si el
    segundo `CREATE ROLE` o el segundo `CREATE POLICY` explotaran, el test se
    cae con la excepción antes de llegar a las afirmaciones.
    """
    apply_bootstrap()
    apply_bootstrap()

    # Si el segundo bootstrap le hubiera cambiado el password, esto no conecta.
    with agent_connection() as conn:
        sin_institucion = conn.execute("SELECT count(*) FROM cases").fetchone()[0]

    with agent_connection(tenant_a) as conn:
        instituciones_visibles = {
            fila[0] for fila in conn.execute("SELECT DISTINCT tenant_id FROM cases")
        }

    assert sin_institucion == 0
    assert instituciones_visibles == {tenant_a}
