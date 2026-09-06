# 01 · Los límites de recursos y el costo de RLS

> **La autoridad es [`tests/test_planes.py`](../tests/test_planes.py); los números de acá son una foto del 2026-09-05 y pueden estar viejos.**

**Ticket:** H0/04 · El timeout muerde y RLS no rompe el uso de índices
**Fecha de la corrida:** 2026-09-05 · **Postgres:** 17.11 (aarch64, imagen `postgres:17`)

Dos preguntas, las dos medidas contra la base real:

1. ¿Cuál es exactamente el error con el que muere una consulta por timeout?
   Es el insumo de H3: el feedback accionable que se le devuelve al agente (D-06).
2. ¿RLS degrada los planes de ejecución? Es la pregunta que podía tumbar el hito.

Lo que esta nota aporta —y el test no— es la **medición comparativa**, con y
sin RLS, que es cómo se eligieron las consultas que entraron a
[`tests/test_planes.py`](../tests/test_planes.py) y
[`tests/test_limites.py`](../tests/test_limites.py), más el registro del error
exacto.

Reproducible con:

```
.venv/bin/pytest              # la suite completa, con los lentos (~17 s)
.venv/bin/pytest -m "not lento"   # el ciclo rápido (~2 s)
```

---

## 1. El error exacto del timeout

Lo que hay que devolverle al agente en H3, tal como sale de la base:

| | |
|---|---|
| **SQLSTATE** | `57014` |
| **Nombre de la condición** | `query_canceled` |
| **Mensaje** | `canceling statement due to statement timeout` |
| **Severidad** | `ERROR` |
| **Excepción de psycopg 3** | `psycopg.errors.QueryCanceled` |
| **Cuándo llega** | a los 15,01 s medidos desde el cliente |

**Lo que se afirma en el test es el sqlstate, nunca el mensaje.** El código es
estable entre versiones de Postgres; el wording no, y además se traduce con la
locale del servidor. Un test que afirmara el texto sería un change detector con
otro nombre (`plan/testing.md`, regla 4).

Para H3, `57014` es lo que distingue *"la consulta era demasiado cara"* de
*"la consulta estaba mal escrita"* (`42601`, error de sintaxis) o de
*"no tenés permiso"* (`42501`). Son tres reintentos distintos: la primera se
reescribe más acotada, la segunda se corrige, la tercera no se reintenta.

### Dos límites, no uno

| Dónde | Valor | Origen |
|---|---|---|
| Servidor | `15000` ms | `docker-compose.yml`, `source = command line` |
| Rol `agent_ro` | `15s` | `ALTER ROLE` en `infra/bootstrap.sql` |

La redundancia es deliberada y está justificada en el script. El detalle que
importa para testearla: **el del rol pisa al del servidor**, en los dos
sentidos. Bajarlo a `200ms` hace morir un `pg_sleep(1)` que el servidor habría
dejado terminar de sobra, y ponerlo en `0` **desactiva el límite por completo**
aunque el servidor tenga los suyos 15 s. Eso último se verificó rompiendo el
bootstrap a propósito: con el rol en `0`, la consulta desbocada siguió corriendo
más de 65 segundos sin que nada la cancelara.

### La consulta desbocada del test

Con RLS activo, el planificador **nunca elige por su cuenta un `Seq Scan` sobre
`transactions`**: el predicado de la policy entra al índice y le acota el
recorrido a los 10,8 M de filas del tenant en vez de los 72 M de la tabla. Es un
efecto lateral simpático del blindaje, y obliga a apagar los caminos por índice
(`enable_indexscan`, `enable_bitmapscan`, `enable_indexonlyscan` — `agent_ro`
puede hacerlo por su cuenta) para poder ejercer el peor caso en el test.

El trabajo por fila —200 `md5` por cada fila de `transactions`— está para que el
test no dependa del hardware. Esta máquina recorre entera la tabla de 13 GB en
unos 5 segundos: un test de timeout calibrado para una máquina lenta daría verde
sin haber afirmado nada.

---

## 2. RLS y los planes de ejecución

**Resultado: RLS no degrada los planes. El plan B no hace falta.**

> **Pendiente para el usuario.** Amerita una corrección de D-02 en
> `DECISIONS.md`: el plan B de vistas por tenant con `security_barrier` queda
> descartado con la medición de acá abajo. `DECISIONS.md` no se toca desde el
> código; la escribe el usuario.

El predicado de la policy es *sargable*: `current_setting` es `STABLE`, así que
el planificador la resuelve una vez y usa el resultado como **condición de
índice**, no como filtro fila por fila. Como los índices tienen `tenant_id` como
primera columna, compone exactamente igual que un literal escrito a mano.

### La medición

Tres formas de la misma consulta, con el par de tenants que descubre
`Q_FIXTURE` (hoy A = 1 `banco_norte`, el tenant más grande de la base):

| | Quién | Filtro por institución |
|---|---|---|
| **CON RLS** | `agent_ro` vía `agent_connection` | sólo el que pone la policy |
| **SIN RLS** | admin (superusuario, se saltea RLS) | ninguno — ve las 40 instituciones |
| **Ideal** | admin | `WHERE tenant_id = 1` escrito a mano |

Costo total estimado del plan, y el nodo de acceso a la tabla grande:

| Consulta | CON RLS | Ideal (literal) | SIN RLS ni filtro |
|---|---:|---:|---:|
| Clientes de riesgo alto (`clients` ⋈ `risk_assessments`) | **68.893** · Index Scan + Bitmap Index Scan | 68.164 · mismos nodos | 119.283 · **2 Seq Scan** |
| Transacciones del trimestre (`transactions`) | **1.128.451** · Bitmap Index Scan `idx_tx_tenant_date` | 1.123.839 · mismo nodo | 1.586.422 · **Seq Scan** |
| Alertas del trimestre (`alerts`) | **4.696** · Bitmap Index Scan `idx_alerts_tenant_status_triggered` | 4.567 · mismo nodo | 5.590 · **Seq Scan** |
| Altas del año (`clients`) | **8.818,72** · Index Scan `idx_clients_tenant_active` | 8.818,71 · mismo nodo | 37.045 · **Seq Scan** |
| Screenings confirmados (`screenings`) | **66.393** · Bitmap Index Scan `idx_screenings_tenant_client` | 63.254 · mismo nodo | 72.795 · **Seq Scan** |

Las dos conclusiones:

- **CON RLS ≈ Ideal.** El sobrecosto contra el filtro escrito a mano va del
  **0,00 % al 4,96 %**, y en los cinco casos el plan es *el mismo* — mismos
  nodos, mismos índices. La única diferencia en el `EXPLAIN` es que donde el
  ideal dice `Index Cond: (tenant_id = 1)`, con RLS dice
  `Index Cond: (tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::bigint)`.
- **CON RLS es mejor que SIN RLS.** Contra el mismo SQL sin filtro —que es lo
  que el agente va a escribir cuando se olvide— RLS **evita** cinco `Seq Scan`
  sobre tablas grandes. La policy no es sólo una garantía de aislamiento: es
  también la que le impide al agente recorrer entera una tabla de 72 M de filas.

### Tiempos reales, con RLS

Ejecutadas por `agent_connection` sobre el tenant más grande (10,8 M de
transacciones), bajo el `statement_timeout` de 15 s:

| Consulta | Tiempo | Resultado |
|---|---:|---|
| Clientes de riesgo alto | 0,06 s | 5.399 |
| Transacciones del trimestre | 1,59 s | 639.674 · 1.536.226.681,57 |
| Alertas del trimestre por estado | 0,02 s | 4 estados |
| Altas del año | 0,02 s | 18.002 |
| Screenings confirmados | 0,05 s | 2.159 |

La más cara usa el 10,6 % del presupuesto de 15 segundos, **en el peor tenant de
la base**. El riesgo que el mini-plan anotaba —"RLS degrada los planes y todo
empieza a dar timeout"— no se materializó.

### Qué se versionó como test, y qué no

Al test entraron las tres primeras: entre las tres tocan cinco de las nueve
tablas grandes (`clients`, `risk_assessments`, `transactions`, `alerts`) y las
tres formas de acceso que aparecen (Index Scan, Bitmap Index Scan, e Index Scan
sobre índice parcial). Las otras dos no agregaban una forma de plan nueva.

El test afirma dos cosas separadas, y la segunda es la sutil:

1. Ningún nodo `Seq Scan` sobre una tabla grande (las de ≥ 100 k filas,
   descubiertas por catálogo).
2. El predicado de la policy aparece en un `Index Cond` y **no** en un `Filter`.

La segunda existe porque la primera, sola, se puede engañar: un predicado no
sargable puede dejar el plan usando un índice por las *otras* columnas y
esconder la degradación. Verificado rompiendo el bootstrap a propósito —
reescribiendo el predicado como `tenant_id::text = current_setting(...)`— y
confirmando que las cuatro afirmaciones se caen.

---

## 3. Qué queda pendiente

| Hallazgo | Va a |
|---|---|
| `57014` / `canceling statement due to statement timeout` es el feedback de timeout para el agente | H3 · tool `run_sql` |
| `42601` (sintaxis) y `42501` (permisos) son reintentos distintos de `57014` | H3 |
| Con RLS activo el planificador no elige `Seq Scan` sobre `transactions`: el gate de `EXPLAIN` de D-06 tiene que mirar el costo, no sólo el tipo de nodo | H3 · gate de D-06 |
| El presupuesto real de una golden query en el peor tenant es ~1,6 s sobre 15 s | H2 / H4 |
