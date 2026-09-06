# 00 · Restore y verificación de humo

**Ticket:** H0/01 · Base restaurada y AS_OF verificado contra la data
**Fecha de la corrida:** 2026-09-05 · **Postgres:** 17.11 (aarch64, imagen `postgres:17`)

Este es el log de la precondición ambiental del hito. La única pregunta que
contesta es: *¿la base que tenemos es la que el diccionario dice que es?*
Todo lo que sigue sale de consultar la data, no de leer `DATA_DICTIONARY.md`.

Reproducible con:

```
docker compose up -d db
docker compose run --rm restore      # ~5-10 min, una sola vez
.venv/bin/python scripts/smoke_check.py
```

El script sale con código 0 si todas las verificaciones pasan. En esta corrida
salió 0.

---

## Estado del entorno

| Qué | Valor |
|---|---|
| Contenedor | `challenge_pg`, `Up (healthy)` |
| Puerto | `localhost:55432` |
| Credenciales | `postgres` / `compliance` / `compliance` |
| `statement_timeout` del server | `15s` |
| Dump | `dump/compliance.dump`, 1,7 GB (1.758.771.135 bytes) |
| `docker-compose.yml` | **sin modificar** (`git diff` vacío) |

**Lo que no verifiqué de primera mano.** El `docker compose run --rm restore` ya
estaba corrido cuando escribí esto, así que no vi la salida del `pg_restore` en
vivo. Lo que sí verifiqué es el *resultado*: 22 tablas, 93.800.083 filas, los 12
índices que promete el diccionario presentes, **cero índices inválidos**
(`pg_index WHERE NOT indisvalid` da 0 — un `pg_restore` cortado a la mitad deja
índices inválidos). Con eso doy el restore por completo. Si algún día aparece una
tabla vacía que no debería estarlo, el sospechoso número uno es este supuesto.

Todas las consultas del script corren bajo el `statement_timeout = 15s` del
server: no hay que aflojarlo para hacer la verificación, ni siquiera para contar
las 72 millones de filas de `transactions` (los `count(*)` van por index-only
scan y tardan menos de un segundo).

---

## 1. Tablas: lo que hay vs. lo que está documentado

**22 tablas** en `public`. El diccionario documenta **13** y avisa de entrada que
lo hace a propósito parcial. Ninguna tabla documentada falta.

### Las 9 tablas que aparecieron sin documentar

Todas tienen `tenant_id`. Ninguna es cosmética:

| tabla | filas | por qué importa |
|---|---:|---|
| `audit_log` | 5.965.000 | quién hizo qué; `metadata` JSONB |
| `client_documents` | 3.579.000 | documentación KYC, con `expires_date` y soft-delete |
| `notes` | 954.261 | notas libres sobre `(entity, entity_id)` — polimórfico, sin FK |
| `transaction_counterparties` | 238.600 | contrapartes por transacción, con `country` |
| `client_risk_overrides` | 23.799 | overrides manuales de riesgo, con soft-delete |
| `alert_case_links` | 10.629 | **el vínculo alerta↔caso que el diccionario dice que "vive en otra parte"** |
| `sar_reports` | 5.356 | reportes a la UIF, colgados de `case_id` |
| `users` | 93 | analistas del tenant; `assigned_to` de `cases` probablemente apunta acá |
| `screening_runs` | 200 | corridas batch de screening |

`alert_case_links` es el hallazgo con más consecuencias: confirma la nota del
diccionario de que `alerts.case_id` no se usa. Lo verifiqué —
`count(case_id) FROM alerts` da **0** sobre 202.556 filas. Cualquier join
alerta→caso tiene que pasar por `alert_case_links`.

### Columnas que existen y el diccionario no menciona

| tabla | columnas de más |
|---|---|
| `alerts` | `metadata` |
| `cases` | `outcome`, `metadata` |
| `risk_assessments` | `metadata` |
| `transactions` | `counterparty_name`, `metadata` |
| `tenant_config` | `id`, `created_at` |
| `screenings` | — (coincide) |
| `clients` | — (coincide) |

No falta ninguna columna documentada. El diccionario no miente; se queda corto,
que es lo que avisó.

### Discrepancia que sí hay que corregir antes de H0/02

**`watchlists` tiene `tenant_id`.** El diccionario la clasifica como catálogo
lookup junto a `countries`, `document_types`, `channels` y `alert_rules`, y
`plan/h0-base.md` decidió dejar los cinco catálogos **sin RLS** con el argumento
de que "no tienen `tenant_id`". Para `watchlists` ese argumento es falso:

```
 es_global | count
-----------+-------
 f         |     4     <- INTERNAL_BLOCKLIST / INTERNAL_WATCH, de los tenants 1, 2, 4 y 6
 t         |    11     <- OFAC_SDN, PEP_AR, etc.: listas públicas, tenant_id NULL
```

Es una tabla **mixta**: filas globales con `tenant_id NULL` y listas internas que
pertenecen a un tenant. Dejarla sin RLS filtra los nombres de las listas internas
de la competencia; ponerle la policy estándar
`tenant_id = current_setting('app.tenant_id')` esconde las 11 listas globales y
rompe cualquier pregunta sobre PEPs. Necesita una policy propia:

```sql
USING (tenant_id IS NULL OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint)
```

**No lo implemento acá** — es trabajo de H0/02 (ticket #3). Queda anotado como
input de ese ticket.

> **Pendiente para el usuario.** Amerita una corrección de D-02 en
> `DECISIONS.md`: existe una tercera clase de tabla —la **mixta**— que la
> decisión no preveía, y lleva la policy `tenant_id IS NULL OR tenant_id = <predicado>`.
> `DECISIONS.md` no se toca desde el código; la escribe el usuario.

### Reparto para el RLS de H0/02

| | tablas |
|---|---|
| **Con `tenant_id` (17)** | `alert_case_links`, `alerts`, `audit_log`, `cases`, `client_documents`, `client_risk_overrides`, `clients`, `notes`, `risk_assessments`, `sar_reports`, `screening_runs`, `screenings`, `tenant_config`, `transaction_counterparties`, `transactions`, `users`, `watchlists` |
| **Sin `tenant_id` (5)** | `alert_rules`, `channels`, `countries`, `document_types`, `tenants` |

`tenants` no tiene `tenant_id` pero igual lleva RLS, con `id = app.tenant_id`
(ya estaba previsto en `plan/h0-base.md`). `watchlists` es el caso especial de
arriba. Los otros cuatro son catálogos de verdad.

Esto confirma que el bootstrap tiene que descubrir las tablas por
`information_schema`, no por una lista escrita a mano: nueve de las diecisiete
tablas que necesitan RLS no están en el diccionario.

### Un detalle estructural: no hay ni una sola foreign key

`pg_constraint` sobre las 22 tablas: 22 PKs, 15 CHECKs, **0 FKs**. Nada garantiza
que un `client_id` de `transactions` exista en `clients`, ni que el `case_id` de
`sar_reports` apunte a un caso vivo. Los joins pueden perder filas o encontrar
huérfanos, y eso es problema de H1.

---

## 2. Conteo de filas

93.800.083 filas en total. Conteo exacto (`count(*)`, no estimación de
`reltuples`):

| tabla | filas | tamaño |
|---|---:|---:|
| `transactions` | 71.974.632 | 13 GB |
| `audit_log` | 5.965.000 | 790 MB |
| `screenings` | 4.844.951 | 540 MB |
| `risk_assessments` | 4.772.000 | 562 MB |
| `client_documents` | 3.579.000 | 394 MB |
| `clients` | 1.193.000 | 304 MB |
| `notes` | 954.261 | 136 MB |
| `transaction_counterparties` | 238.600 | 28 MB |
| `alerts` | 202.556 | 39 MB |
| `cases` | 35.722 | 6640 kB |
| `client_risk_overrides` | 23.799 | 2368 kB |
| `alert_case_links` | 10.629 | 1000 kB |
| `sar_reports` | 5.356 | 568 kB |
| `tenant_config` | 203 | 80 kB |
| `screening_runs` | 200 | 40 kB |
| `users` | 93 | 40 kB |
| `tenants` | 40 | 48 kB |
| `watchlists` | 15 | 32 kB |
| `countries` | 10 | 32 kB |
| `alert_rules` | 8 | 32 kB |
| `channels` | 4 | 32 kB |
| `document_types` | 4 | 32 kB |

Los 12 índices que lista el diccionario existen todos, con esos nombres. No hay
índices de más más allá de las PKs y el `tenants_slug_key`.

La base ocupa **15 GB** en total. `transactions` sola es el 77% de las filas y el
82% del tamaño. Es la tabla donde el
`statement_timeout` va a morder, y la única razón por la que el gate de `EXPLAIN`
de D-06 tiene sentido.

---

## 3. El AS_OF es real

El diccionario afirma `AS_OF = 2026-06-01`. Contra la data:

```
min(tx_date)   = 2023-12-14
max(tx_date)   = 2026-05-31
max(booked_at) = 2026-05-31 23:59:56+00
```

**Confirmado.** No hay nada después del 31 de mayo de 2026, ni en la fecha
contable ni en el timestamp de registro. La afirmación del diccionario se
sostiene, así que las definiciones de período que fija `plan/00-plan-general.md`
quedan en pie:

- "este año" = `[2026-01-01, 2026-06-01]`
- "último trimestre" = `[2026-01-01, 2026-03-31]`

> **Nota de H3.** Estas dos líneas quedan como se escribieron —esto es el log de
> H0, no la definición vigente—, pero la notación cerrada de acá **no es la que
> usa el código**. Los períodos se escriben semiabiertos, `[desde, hasta)`, y en
> "este año" la diferencia no es de notación sino de un día. La definición que
> manda está en `plan/testing.md` y en `core/periodos.py`.

La ventana total de datos es de **2 años y 5 meses y medio**, arrancando el
2023-12-14 — el mismo día para los 40 tenants, así que la base es sintética y
generada de una sola pasada. No hay tenants "nuevos" con historia corta, aunque
sus `created_at` en `tenants` vayan de 2020 a 2025: **el `created_at` del tenant
no dice desde cuándo hay datos suyos.** Trampa anotada.

---

## 4. Instituciones

**40 tenants: 38 activos, 2 dados de baja.**

Los dos de baja son `banco_nortte` (id 39) y `fintech_pampa_old` (id 40). Los dos
nombres son deliberados y son una trampa:

- `banco_nortte` con doble T es un casi-homónimo de `banco_norte` (id 1, activo).
- `fintech_pampa_old` es el "viejo" de `fintech_pampa` (id 6, activo).

Los dos inactivos **tienen datos** (1.500 clientes y 90.014 transacciones cada
uno), o sea que no se los puede descartar por vacíos. Sí se distinguen en una
cosa: son los únicos dos tenants **sin ningún caso** (`cases` = 0).

Volumen por tenant, agrupado por escalón (todos con datos desde 2023-12-14):

| escalón | tenants | clients | transactions | alerts | cases |
|---|---|---:|---:|---:|---:|
| grandes | 1–3 (bancos) | 180.000 | ~10,86 M | ~30.600 | ~5.400 |
| medianos | 4–13 | 45.000 | ~2,71 M | ~7.650 | ~1.350 |
| chicos | 14–38 | 8.000 | ~482.000 | ~1.364 | ~240 |
| de baja | 39–40 | 1.500 | 90.014 | 75 | 0 |

`tenant_config` tiene 203 filas: 5 claves × 40 tenants = 200, más 3 versiones
extra. Las claves reales son cinco, dos más de las que documenta el diccionario:

| clave | qué es | documentada |
|---|---|---|
| `high_risk_score_threshold` | umbral de score para riesgo alto | sí |
| `fiscal_year_start_month` | mes de inicio del año fiscal | sí |
| `review_sla_hours` | SLA de revisión de alertas, en horas | no (mencionada al pasar) |
| `pep_is_high_risk` | si un PEP cuenta como riesgo alto por sí solo | **no** |
| `escalated_counts_as_finding` | si `ESCALATED` cuenta como hallazgo real | **no** |

Las dos últimas son parámetros de negocio que cambian el resultado de preguntas
enteras y no aparecen en el diccionario. Van a H1/H2.

**Sólo 3 tenants tienen configuración versionada**, y sólo de una clave: los
tenants 1, 3 y 6 tienen dos filas de `high_risk_score_threshold`.

| tenant | vigente desde | valor |
|---|---|---|
| 1 · `banco_norte` | 2025-09-01 → 2026-01-01 | 70 → **80** |
| 3 · `banco_andino` | 2025-10-15 → 2026-02-01 | 80 → **85** |
| 6 · `fintech_pampa` | 2025-08-01 → 2026-01-01 | 72 → **78** |

Los 37 restantes tienen una sola versión. Esto es importante: la trampa de
"tomar el `effective_from_date` vigente y no el más viejo" **sólo se puede
detectar en tres tenants**. Si el fixture de tests no incluye uno de esos tres,
el bug pasa desapercibido.

---

## 5. Tenants fixture para los tests de aislamiento

### El problema con "dos tenants activos con datos"

Los **38** tenants activos pasan el filtro obvio (activos, con al menos una fila
viva en `clients`, `transactions`, `alerts`, `cases`, `screenings` y
`risk_assessments`). Elegir "dos cualesquiera" no es un criterio: es tirar una
moneda y después hardcodear el resultado.

El fixture tiene dos trabajos distintos y el criterio los cubre a los dos:

1. **Probar aislamiento.** Para eso los dos tenants tienen que dar respuestas
   *distintas* a la misma pregunta. Si A y B dan el mismo número, una fuga entre
   tenants no se ve.
2. **Ser el par sobre el que corren todas las golden queries** (`plan/testing.md`:
   "cada una corre en los 2 tenants"). Para eso el par tiene que tocar las
   trampas semánticas del dataset, no esquivarlas.

### Criterio

Implementado como una sola consulta en
[`scripts/smoke_check.py`](../scripts/smoke_check.py) (`Q_FIXTURE`). En prosa:

**Conjunto base** — el tenant está `is_active` **y** tiene al menos una fila con
`deleted_at IS NULL` en `clients`, `transactions`, `alerts`, `cases`,
`screenings`, y al menos un `risk_assessments` vivo con `is_current`. Descarta
los dados de baja y cualquier tenant que no soporte una golden query completa.
Hoy pasan los 38 activos.

**Tenant A** — de ese conjunto, el de **menor `id` con
`high_risk_score_threshold` versionado** (más de una fila vigente al AS_OF). Es
el requisito duro: sin un tenant versionado, la mutación *"tomar el
`effective_from_date` más viejo en vez del vigente"* de `plan/testing.md` no
rompe ningún test, y el set de evals tiene un agujero.

**Tenant B** — de ese conjunto, el de **menor `id`** que tenga umbral de una sola
versión y que **contraste con A en las tres dimensiones** que cambian la
respuesta:

- `kind` distinto — que no sean dos bancos;
- `high_risk_score_threshold` vigente distinto — la misma pregunta de "clientes
  de riesgo alto" da números distintos;
- `fiscal_year_start_month` distinto — **no** porque el año fiscal redefina los
  períodos (el diccionario dice explícitamente que no lo hace), sino
  precisamente para tener un tenant donde se pueda *probar* que no los redefine.

El desempate por `id` menor es lo único arbitrario, y está ahí para que el
criterio sea determinístico: la consulta devuelve siempre el mismo par.

### Resultado de la corrida

```
tenant A: id=1  slug=banco_norte  kind=BANK  umbral=80 (2 versiones)  mes_fiscal=1
tenant B: id=8  slug=emi_capital  kind=EMI   umbral=68 (1 versión)    mes_fiscal=10
```

Perfil completo del par:

| | A · `banco_norte` (1) | B · `emi_capital` (8) |
|---|---|---|
| `kind` | BANK | EMI |
| `high_risk_score_threshold` | **80** (versionado: 70 desde 2025-09-01, 80 desde 2026-01-01) | **68** (una sola versión) |
| `fiscal_year_start_month` | 1 | 10 |
| `review_sla_hours` | 48 | 72 |
| `pep_is_high_risk` | true | true |
| `escalated_counts_as_finding` | true | false |
| clients | 180.000 | 45.000 |
| transactions | 10.865.499 | 2.716.408 |
| alerts | 30.597 | 7.650 |
| cases | 5.400 | 1.348 |
| screenings | 731.073 | 182.696 |
| risk_assessments | 720.000 | 180.000 |
| sar_reports | 810 | 202 |

Contrastan en cinco de los seis parámetros de negocio. El único que comparten es
`pep_is_high_risk`; si más adelante hace falta discriminarlo, hay que agregarlo
al criterio y volver a correr la consulta, no elegir otro tenant a dedo.

Dos propiedades que salieron de arriba y conviene no perder:

- **A es el tenant más grande de la base** (10,8 M de transacciones). Es el peor
  caso de performance: una golden query que entra en 15 s en A entra en
  cualquiera. Es una ventaja, no un accidente a corregir.
- **A es `banco_norte`, y existe `banco_nortte` (id 39, de baja) con datos.** Si
  el RLS se cae, la contaminación más probable es justamente entre esos dos, y
  el test la va a ver.

### Regla

Los IDs `1` y `8` **no se escriben en ningún lado**. Los tests toman el par
resolviendo `Q_FIXTURE` contra la base; este documento registra qué devolvió hoy,
para poder detectar si algún día cambia. Si cambia, cambió la data o cambió el
criterio, y las dos cosas hay que mirarlas.

---

## Qué queda pendiente

Fuera del alcance de este ticket, anotado para no perderlo:

| Hallazgo | Va a |
|---|---|
| `watchlists` necesita policy propia (`tenant_id IS NULL OR ...`) | H0/02 · ticket #3 |
| El bootstrap descubre las 17 tablas con `tenant_id` por catálogo | H0/02 · ticket #3 |
| No hay una sola FK: joins con huérfanos posibles | H1 |
| `alerts.case_id` está vacío; el vínculo real es `alert_case_links` | H1 |
| Claves de `tenant_config` sin documentar: `pep_is_high_risk`, `escalated_counts_as_finding`, `review_sla_hours` | H1 / H2 |
| Columnas `metadata` JSONB en `alerts`, `cases`, `risk_assessments`, `transactions` sin explorar | H1 |
| `cases.outcome` y `transactions.counterparty_name` sin documentar | H1 |
| `tenants.created_at` no indica desde cuándo hay datos del tenant | H1 |
| Valores reales de los enums (`status`, `severity`, `result`, `channel`, ...) | H1 |
| Cuántas filas tienen `deleted_at` no nulo por tabla | H1 |
