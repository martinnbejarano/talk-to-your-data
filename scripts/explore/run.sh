#!/usr/bin/env bash
# Corre un script de exploración contra la base restaurada.
#
#     scripts/explore/run.sh 01-inventario.sql
#     scripts/explore/run.sh                     # todos, en orden
#
# Corre como `postgres` y con `statement_timeout = 0`, a propósito: explorar es
# un trabajo distinto de responder. Las consultas del producto viven bajo el rol
# `agent_ro` y sus límites; éstas necesitan ver todo aunque tarden.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENEDOR="${PG_CONTAINER:-challenge_pg}"

# `max_parallel_workers_per_gather = 0`: el contenedor trae el /dev/shm chico
# por default y un Parallel Hash sobre `clients` ⋈ `risk_assessments` muere con
# "could not resize shared memory segment ... No space left on device". Explorar
# no tiene apuro; el plan serial da el mismo resultado.
correr() {
  echo "── $(basename "$1") ────────────────────────────────────────────"
  docker exec -i \
    -e PGOPTIONS='-c statement_timeout=0 -c max_parallel_workers_per_gather=0' \
    "$CONTENEDOR" \
    psql -U postgres -d compliance -v ON_ERROR_STOP=1 -f - < "$1"
}

if [ $# -gt 0 ]; then
  for f in "$@"; do correr "$AQUI/$(basename "$f")"; done
else
  for f in "$AQUI"/[0-9]*.sql; do correr "$f"; done
fi
