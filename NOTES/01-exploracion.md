# 01 · Exploración de la data

**Hito:** H1 · Completar los huecos que el diccionario deja a propósito, y
confirmar o desmentir las 16 trampas anotadas en `DECISIONS.md`.
**Fecha de la corrida:** 2026-09-06 · **Postgres:** 17.11

Reproducible con:

```
scripts/explore/run.sh              # los once scripts, en orden
scripts/explore/run.sh 06-riesgo-alto.sql   # uno solo
```

Corre como `postgres` con `statement_timeout = 0`, no como `agent_ro`. Explorar
es un trabajo distinto de responder: acá quiero ver todo, aunque tarde. Las
consultas del producto sí viven bajo las restricciones.

> **Nota de método.** Esto se escribió *mientras* exploraba. El orden de las
> secciones es el de las tareas del mini-plan, pero el orden en que aparecieron
> los hallazgos fue otro, y donde algo me confundió lo dejé dicho.

---

## Resumen: qué cambió respecto de lo que creía al empezar

Cinco cosas que daba por ciertas y no lo eran:

| Creía | Es |
|---|---|
| El soft-delete es parejo y hay que excluirlo siempre | Sólo 4 de las 8 tablas con `deleted_at` tienen filas borradas. En `alerts`, `cases`, `screenings` y `client_risk_overrides` el filtro no cambia ni un número |
| `alert_case_links` es el vínculo alerta↔caso que faltaba | Es un señuelo: `alert_id` es una **copia de `case_id`** en las 10.629 filas. El vínculo **no existe** en la base |
| Las dos fuentes de "riesgo alto" se contradicen y hay que medir cuánto | Son **disjuntas por construcción**: 0 clientes en la intersección, en las 40 instituciones. Y son **tres**, no dos: donde `pep_is_high_risk` está en `true` los PEP vigentes agregan un escalón más, también disjunto |
| El `AS_OF` vale para toda la base (H0 lo verificó) | Vale para `transactions`. Hay **70.000 filas con fecha posterior** en otras dos columnas |
| Sin foreign keys, cualquier join puede tener huérfanos | Las relaciones documentadas están **perfectamente limpias**. Las dos únicas rotas son las dos tablas puente no documentadas |

Y una decisión que se movió: **el par de instituciones de trabajo dejó de ser
(1, 8) y pasó a ser (3, 14)** — el par viejo tenía un punto ciego que hacía
inofensiva media definición de "fuera de SLA". El detalle está en la sección 8.

---

## 1. Inventario del esquema

`scripts/explore/01-inventario.sql`. Todo sale del catálogo; no escanea una sola
fila de datos.

H0 ya había contado las 22 tablas y las 93,8 M de filas, así que acá sólo anoto
lo que agrega el catálogo y no estaba.

### Los enums, leídos de los `CHECK`

El truco funcionó: el diccionario dice que los enums son `TEXT` con
`CHECK (... IN (...))`, así que los valores permitidos salen de
`pg_get_constraintdef` en vez de un `SELECT DISTINCT` sobre decenas de millones
de filas. **15 constraints `CHECK`**, y ninguna sorpresa: los valores son
exactamente los que documenta el diccionario, ni uno más.

| tabla.columna | valores |
|---|---|
| `alerts.status` | `OPEN` `IN_REVIEW` `ESCALATED` `CLOSED_TRUE_POSITIVE` `CLOSED_FALSE_POSITIVE` |
| `alerts.severity` | `LOW` `MEDIUM` `HIGH` `CRITICAL` |
| `cases.status` | `OPEN` `INVESTIGATING` `PENDING_INFO` `CLOSED` `REPORTED_UIF` |
| `clients.onboarding_status` | `PENDING` `APPROVED` `REJECTED` `MANUAL_REVIEW` |
| `clients.document_type` | `DNI` `CUIT` `PASSPORT` `CDI` |
| `screenings.result` | `NO_HIT` `POTENTIAL_HIT` `CONFIRMED_HIT` `DISCARDED` |
| `transactions.status` | `SETTLED` `PENDING` `REVERSED` |
| `transactions.currency` | `ARS` `USD` `EUR` `USDT` |
| `transactions.direction` | `IN` `OUT` · `channel` | `WIRE` `CASH` `CARD` `CRYPTO` |
| `tenants.kind` | `BANK` `ALYC` `FINTECH` `EMI` |
| `client_documents.status` | `UPLOADED` `VERIFIED` `EXPIRED` `REJECTED` |
| `sar_reports.status` | `DRAFT` `SUBMITTED` `ACKNOWLEDGED` |
| `watchlists.kind` | `SANCTION` `PEP` `ADVERSE_MEDIA` `INTERNAL` |
| `risk_assessments.score` | `>= 0 AND <= 100` (no es enum, es rango) |

**Pero el truco tiene un límite que no había previsto:** hay **siete columnas de
texto que se comportan como enum y no tienen ninguna `CHECK`**. Todas menos una
viven en tablas que el diccionario no documenta, así que ninguna lista las
cubría. Estas sí hubo que sacarlas de la data (`02-enums-sin-check.sql`):

| columna | valores | filas |
|---|---|---|
| **`cases.outcome`** | `CLEARED` `NO_ACTION` `SAR_FILED` | 21.430 de 35.722 (el resto es `NULL`) |
| `client_documents.doc_kind` | `DNI_FRONT` `DNI_BACK` `SELFIE` `PROOF_OF_ADDRESS` | 3.579.000 |
| `client_risk_overrides.reason` | `analyst_note` `model_drift` `legacy_flag` | 23.799 |
| `screening_runs.source` | `BATCH` `REALTIME` `MANUAL` | 200 |
| `audit_log.action` | `LOGIN` `VIEW_CLIENT` `RUN_SCREENING` `UPDATE_CASE` `EXPORT` | 5.965.000 |
| `audit_log.entity` / `notes.entity` | `client` `alert` `case` `screening` / **sólo `client`** | — |
| `users.role` | **sólo `COMPLIANCE_ANALYST`** | 93 |

`cases.outcome` es el único de la lista que importa para las preguntas, y es
además la única columna semánticamente relevante que el diccionario omite por
completo. La correspondencia con `status` es exacta y sin excepciones:

```
CLOSED       (16.074) → CLEARED (8.144) | NO_ACTION (7.930)
REPORTED_UIF  (5.356) → SAR_FILED (5.356)
los otros tres estados → outcome NULL, closed_at NULL
```

Es decir: **`outcome` no aporta información que `status` no tenga**, salvo la
distinción entre "se cerró porque no había nada" (`CLEARED`) y "se cerró sin
acción" (`NO_ACTION`), que es una distinción que ninguna de las ocho preguntas
del enunciado necesita. Anotado y descartado.

### Foreign keys: no hay ninguna, y no importa tanto como parecía

H0 lo dejó anotado como riesgo para H1: *"nada garantiza que un `client_id` de
`transactions` exista en `clients`. Los joins pueden perder filas o encontrar
huérfanos."* Lo medí sobre las ocho relaciones que existen
(`11-tablas-no-documentadas.sql`, 11.1), exigiendo además que el padre sea del
**mismo tenant**:

```
transactions.client_id       0 huérfanos de 71.974.632
screenings.client_id         0 de 4.844.951
risk_assessments.client_id   0 de 4.772.000
client_documents.client_id   0 de 3.579.000
notes.entity_id              0 de   954.261
alerts.client_id             0 de   202.556
client_risk_overrides        0 de    23.799
sar_reports.case_id          0 de     5.356
```

**Cero huérfanos y cero cruces de tenant en las ocho.** El riesgo no se
materializó: los joins del producto son seguros y no hace falta un `LEFT JOIN`
defensivo en ninguno.

Tres verificaciones más, del mismo tipo, que cierran agujeros de nullability que
el esquema deja abiertos y la data no usa:

- **`alerts.client_id` es nullable y no hay ni un `NULL`** en 202.556 filas. Toda
  alerta tiene cliente: el join `alerts → clients` no necesita ser `LEFT`.
- **`clients.document_type` y `document_number` son nullables y no hay ni un
  `NULL`** en 1,19 M de filas (importa para el dedup de D-09).
- **`clients.country` cae siempre en el catálogo `countries`**: 10 países usados
  sobre 10 disponibles, cero fuera de catálogo.

Lo mismo con el único catálogo que se joinea de verdad: los 8 `rule_code` de
`alerts` están los 8 en `alert_rules`, sin huérfanos. (Dato al margen que
contradice a la sección 5: existen las reglas `SANCTION_MATCH` (7.957 alertas) y
`PEP_ACTIVITY` (5.940), o sea que el monitoreo AML **sí** produce alertas de
sanciones aunque el screening contra listas no tenga un solo registro que no sea
`PEP_AR`. Son dos subsistemas distintos y no hay que confundirlos al responder.)

Con una excepción enorme, que es la sección 3.

### Índices

Los 12 del diccionario están, con esos nombres, más las PKs y `tenants_slug_key`.
Ninguno de más. Lo que sí conviene tener presente: **ninguna de las nueve tablas
no documentadas tiene índice por `tenant_id`**, así que cualquier filtro sobre
ellas es un seq scan. Medido (11.6):

| tabla | plan | costo | tiempo real |
|---|---|---:|---:|
| `client_documents` (3,5 M) | Seq Scan | 86.679 | 55 ms |
| `audit_log` (6 M) | Seq Scan | 161.572 | 92 ms |
| `notes` (954 k) | Seq Scan | 27.040 | 169 ms |
| `transaction_counterparties` (238 k) | Seq Scan | — | 41 ms |

O sea: **el seq scan sobre estas tablas es perfectamente pagable** (menos del
1,2 % del presupuesto de 15 s). Lo anoto porque tiene una consecuencia directa
sobre D-06: **el gate de `EXPLAIN` no puede rechazar `Seq Scan` a secas.** Para
estas cinco tablas no hay plan alternativo, y rechazarlo volvería incontestable
una pregunta que se responde en 55 ms. El gate tiene que mirar el costo (o el
tamaño de la tabla), no el tipo de nodo. NOTES/01 ya había llegado a la misma
conclusión por otro camino; ésta es la segunda razón independiente.

---

## 2. Las tablas no documentadas

Tarea 2 del mini-plan. La conclusión "esta tabla no la necesito" también se
anota: evita joins de más.

| tabla | filas | veredicto |
|---|---:|---|
| `alert_case_links` | 10.629 | **Inservible.** Sección 3 |
| `transaction_counterparties` | 238.600 | **Inservible y redundante.** Abajo |
| `client_risk_overrides` | 23.799 | **No sirve para definir riesgo.** Sección 4 |
| `sar_reports` | 5.356 | **Sirve.** 1 a 1 con los casos `REPORTED_UIF` |
| `users` | 93 | **Sirve a medias.** Abajo |
| `client_documents` | 3.579.000 | No la necesita ninguna de las 8 preguntas |
| `audit_log` | 5.965.000 | No la necesita ninguna. Ruido uniforme |
| `notes` | 954.261 | No la necesita ninguna. `body` tiene **4 valores distintos** en 954.261 filas: es relleno, no texto |
| `screening_runs` | 200 | No se puede unir a `screenings`: no hay `run_id` |

### `transaction_counterparties`: puntero al azar, y encima redundante

Dos razones independientes para no tocarla:

1. **El `transaction_id` no apunta a nada.** 202.600 de 238.600 filas (85 %)
   referencian una transacción de **otro** tenant. La tasa de filas "sanas" es
   **15,09 %**, y la cuota de transacciones del tenant 1 sobre el total es
   **15,10 %**: coinciden con tres decimales. El puntero acierta por azar.
2. **Aunque funcionara, no haría falta.** `transactions.counterparty_name` no es
   `NULL` en ninguna de las 72 M de filas: la contraparte ya está denormalizada
   en la transacción. La única columna que la tabla agregaría es `country`.

### `users`: existe, pero `cases.assigned_to` le miente

`assigned_to` es `TEXT` con el email del analista, y resuelve a un `users` del
mismo tenant en **33.632 de 35.722 casos (94,1 %)**. Los 2.090 que no resuelven
tienen un patrón: los tenants 1–13 tienen 3 analistas y los 14–40 tienen 2, pero
los casos de los chicos también se asignan a `analyst2@...`, que en esos tenants
no existe. Cero cruces de tenant, eso sí.

Consecuencia: "casos por analista" se puede responder agrupando por
`assigned_to` (el texto), y **no** joineando contra `users`, que perdería el
5,9 % de los casos sin avisar.

### Las `metadata` JSONB: seis de ocho están vacías

Tarea 4 del mini-plan. Esperaba encontrar estructura escondida en los JSONB que
el diccionario no muestra. Encontré lo contrario (`11-tablas-no-documentadas.sql`,
11.5):

```
alerts             202.556 de 202.556   vacías  ({})
cases               35.722 de 35.722    vacías
risk_assessments 4.772.000 de 4.772.000 vacías
transactions    71.974.632 de 71.974.632 vacías
notes              954.261 de 954.261   vacías
audit_log        5.965.000 de 5.965.000 vacías
sar_reports          5.356 de 5.356     vacías
clients          1.169.137 de 1.193.000 vacías (23.863 con contenido)
screenings                             ← la única con estructura real
```

**Seis columnas `metadata` son decoración pura.** Es una conclusión negativa
fuerte y me ahorra una línea entera de exploración: no hay nada escondido en el
JSONB de `alerts`, `cases`, `transactions` ni `risk_assessments`.

Las dos que sí tienen contenido, y en las dos las claves de primer nivel están
contadas sobre la tabla entera, no sobre una muestra:

- **`clients.metadata`**, con dos formas disjuntas y ninguna clave compartida:
  `{"source": "kyc_onboarding"}` en 11.943 filas y
  `{"manual_review_reason": "enhanced_due_diligence"}` en 11.920. El segundo
  número reaparece en la sección 4 y no es casualidad.
- **`screenings.metadata`**, con exactamente **dos** claves en 4,8 M de filas
  —`matches` (72.951) e `is_pep` (67.253)— y `{}` en las 4.772.000 restantes,
  que son los `NO_HIT`. No hay ninguna clave escondida. Es la sección 5.

---

## 3. El vínculo alerta↔caso: no existe

Es el entregable obligatorio del hito (*"Identificada la tabla que vincula
alertas con casos"*), y la respuesta honesta es que **no hay ninguna**.

El diccionario dice que `alerts.case_id` está "sin poblar; el vínculo alerta↔caso
vive en otra parte del esquema". La primera mitad es cierta —`count(case_id)`
sobre `alerts` da **0** en 202.556 filas, ya lo había visto H0—. La segunda es la
que hay que verificar, y la única candidata es `alert_case_links`.

No sirve. Tres mediciones (`09-alertas-y-casos.sql`, 09.2):

**1. `alert_id` es literalmente una copia de `case_id`.**

```
alert_id = case_id  →  10.629 de 10.629 filas (100 %)
```

Diez mil coincidencias exactas no son una coincidencia.

**2. El `tenant_id` del link sigue al caso, nunca a la alerta.**

```
link=caso ✓ · link=alerta ✗ · alerta=caso ✗   9.054
link=caso ✓ · link=alerta ✓ · alerta=caso ✓   1.575
```

Las 9.054 filas de arriba apuntan a una alerta **de otra institución**.

**3. Las 1.575 "sanas" son todas del tenant 1, y lo son por accidente.**

`alerts.id` va de 1 a 202.556 y `cases.id` de 1 a 35.722. El tenant 1 posee los
ids más bajos de las dos tablas, así que copiar el `case_id` en el `alert_id`
"acierta" mientras los rangos se superponen. Para los otros 39 tenants no acierta
nunca:

```
tenant  1 → 1.575 sanos de 1.575     tenant  4 → 0 de   407
tenant  2 →     0 sanos de 1.624     tenant  8 → 0 de   400
tenant  3 →     0 sanos de 1.605      (y así los 39)
```

Lo confirmé **bajo RLS**, con `agent_connection`, que es como lo va a ver el
producto:

| tenant | `alert_case_links` visibles | `⋈ alerts` | `⋈ cases` |
|---|---:|---:|---:|
| 1 | 1.575 | **1.575** | 1.575 |
| 2 | 1.624 | **0** | 1.624 |
| 8 | 400 | **0** | 400 |
| 20 | 66 | **0** | 66 |

> **Esto es lo que más me confundió del hito, y por un buen rato.** Vi los 9.054
> cruces de tenant y pensé que había encontrado una fuga de datos —una tabla que
> mezcla instituciones—. No es eso: RLS funciona perfecto, el link nunca se puede
> resolver hacia afuera del tenant. Es un dato **inventado**, no un dato filtrado.
> Tardé en darme cuenta porque estaba buscando problemas de aislamiento y éste
> tenía la forma de uno.

**Consecuencia para el producto.** Cualquier pregunta que necesite recorrer
alerta→caso o caso→alerta (*"¿qué alertas tiene este caso?"*, *"¿cuántas alertas
terminaron en un caso?"*, *"¿cuánto tarda una alerta en escalar a caso?"*) es
**`NO_SE_PUEDE_RESPONDER`**, y la explicación es concreta: la columna prevista
está vacía y la tabla puente tiene los identificadores mal.

Y hay una trampa dentro de la trampa: **en el tenant 1 el join devuelve 1.575
filas y parece funcionar.** Una golden query validada sólo ahí daría verde. Es el
argumento más fuerte a favor de la regla de `plan/testing.md` de correr todo en
dos instituciones — y, como se ve en la sección 8, también el argumento de por
qué el par no puede elegirse a dedo.

Lo que sí queda en pie: `cases.status = 'REPORTED_UIF'` ↔ `sar_reports` es una
relación **1 a 1 perfecta** (5.356 = 5.356, cero huérfanos, cero cruces). Es el
único vínculo no documentado que funciona.

---

## 4. Riesgo alto: las dos fuentes no se contradicen, son disjuntas

Trampa 15, la que el mini-plan marcaba como la más importante. La pregunta era
*cuánto* se contradicen `score >= umbral` y `manual_high_risk_flag`. La respuesta
no es un porcentaje (`06-riesgo-alto.sql`):

```
En las 40 instituciones, sobre clientes vivos con evaluación vigente viva:
    por score >= umbral vigente ......... 35.732
    por manual_high_risk_flag ........... 11.920
    en las dos a la vez ..................... 0
```

**Cero.** No es "se solapan poco": es que **ningún cliente marcado a mano supera
su umbral**. La verificación independiente: el score máximo entre los marcados es
**84**, y hay una institución (el tenant 3) con umbral **85**. Están construidos
para no tocarse.

En el par de trabajo:

| | tenant 3 `banco_andino` | tenant 14 `fintech_cuyo` |
|---|---:|---:|
| clientes vivos | 174.669 | 7.771 |
| por score (umbral 85 / 68) | 5.399 | 240 |
| por marca manual | 1.800 | 81 |
| **en los dos** | **0** | **0** |
| **riesgo alto (unión)** | **7.199** | **321** |
| lo que aporta la marca | **25,0 %** | 25,2 % |

Dos conclusiones que van derecho a la skill de H2:

1. **"Riesgo alto" es la suma, no la unión con intersección.** El `OR` sigue
   siendo la forma correcta de escribirlo (es robusto si mañana la data cambia),
   pero la derivación en cascada de D-07 puede mostrar los dos escalones sumando
   sin nota al pie, porque no hay doble conteo.
2. **Ignorar la marca manual no es un detalle.** Se pierde **uno de cada cuatro**
   clientes de riesgo alto, y la proporción es estable en las dos instituciones
   (25,0 % y 25,2 %). Es el peor error posible de esta pregunta y no da ninguna
   señal: el número que sale es plausible.

### Las otras dos fuentes candidatas, y por qué no entran

**`client_risk_overrides`** (23.799 filas, no documentada). Parecía una tercera
fuente. No lo es: sus columnas son `client_id`, `reason`, `created_at`,
`deleted_at` y nada más. **No tiene el valor al que se overridea** — ni un score
nuevo, ni un nivel de riesgo, ni una dirección. Registra que hubo un override,
no cuál. Y no se corresponde con la marca manual: de sus 23.799 clientes, sólo
**385** tienen `manual_high_risk_flag = true` (1,6 %, menos que el 1,6 % de base:
o sea, ninguna correlación).

Es un señuelo bien puesto: tiene el nombre exacto de lo que uno busca. La
conclusión —"esta tabla registra que hubo un override pero no cuál, así que no
puede definir riesgo"— es en sí misma una respuesta útil que el sistema tiene que
saber dar.

**`pep_is_high_risk`** (clave de `tenant_config` que el diccionario no menciona).
Ésta sí es una fuente real y es **configurable por institución**: 20 tenants en
`true`, 20 en `false`. Donde está en `true`, un PEP confirmado cuenta como riesgo
alto por sí solo, con independencia del score.

Lo medí (`06-riesgo-alto.sql`, 06.5) y **es una tercera fuente disjunta de las
otras dos**: de los 660 PEPs vigentes del tenant 3, los **660** agregan clientes
que ni el score ni la marca manual ya cubrían. Cero solapamiento otra vez.

| | tenant 3 (`pep_is_high_risk = true`) | tenant 14 (`false`) |
|---|---:|---:|
| por score **o** marca manual | 7.199 | 321 |
| PEPs vigentes, ninguno ya cubierto | +660 | +28 |
| **riesgo alto según la config del tenant** | **7.859** | **321** |

O sea que **"riesgo alto" tiene tres escalones, no dos**, y el tercero se prende
o se apaga por institución. Es exactamente la cascada que pide D-07, y como las
tres fuentes son disjuntas los escalones suman sin nota al pie.

Queda una decisión abierta que no es de data sino de producto: si la perilla del
tenant manda sola, o si igual conviene mostrar los dos números. Va a H2, anotada
en la sección 9.

### Trampa 13: sí, hay exactamente una evaluación vigente por cliente

```
1 fila is_current por cliente → 1.193.000 clientes (el 100 %)
```

Sin excepciones. Pero hay un detalle que el diccionario no dice y cambia el SQL:

**el borrado de un cliente sólo borra su evaluación vigente, no su historia.**
Las 34.382 filas borradas de `risk_assessments` son *todas* `is_current`, y
corresponden exactamente a los 34.382 clientes borrados. Sus evaluaciones
históricas siguen con `deleted_at IS NULL`.

Consecuencia: filtrar `risk_assessments.deleted_at IS NULL` **no** excluye a los
clientes borrados; sólo excluye su fila vigente. Quedan **103.146 evaluaciones
vivas de clientes borrados** dando vueltas. Si la consulta no joinea contra
`clients` con su propio `deleted_at IS NULL`, un cliente borrado reaparece con un
score viejo. Por eso el filtro correcto lleva las dos condiciones, y así están
escritas las consultas de esta nota.

---

## 5. PEP: tres definiciones, y un 7,9× entre la más floja y la más estricta

Trampa 7 y pregunta 6 del enunciado (`08-screenings-pep.sql`).

Forma real del `metadata` de `screenings`: la que muestra el diccionario, con
dos precisiones que no están.

**`is_pep` nunca vale `false`.** Aparece en 67.253 filas y en todas vale `true`;
cuando no aplica, la clave **no está**. O sea que `metadata->>'is_pep' = 'false'`
devuelve cero filas siempre, y `NOT (metadata->>'is_pep' = 'true')` no es lo
mismo que `metadata->>'is_pep' IS DISTINCT FROM 'true'`. Trampa de SQL, no de
negocio, pero rompe igual.

**`matches` siempre tiene exactamente un elemento, y siempre de la misma lista.**

```
matches con 1 elemento → 72.951 de 72.951
watchlist_code         → PEP_AR, en el 100 % de los matches
```

Existen 15 `watchlists` (`OFAC_SDN`, `UN_CONSOLIDATED`, `EU_SANCTIONS`,
`INTERPOL_REDNOTICE`, `PEP_GLOBAL`, cuatro internas de tenants, etc.) y **una
sola aparece en la data**. Eso vuelve **incontestable** cualquier pregunta sobre
sanciones (*"¿tenemos clientes en listas de sanciones?"*, *"¿alguien en OFAC?"*):
la tabla de listas existe, el campo existe, y no hay un solo registro. Es
exactamente el caso donde inventar es más tentador, porque todo el andamiaje está.

Cruzando `result` con la presencia de `is_pep`:

| `result` | filas | con `is_pep` | con `matches` |
|---|---:|---:|---:|
| `NO_HIT` | 4.772.000 | 0 | 0 |
| `POTENTIAL_HIT` | 29.350 | 29.350 | 29.350 |
| `DISCARDED` | 29.303 | 29.303 | 29.303 |
| `CONFIRMED_HIT` | 14.298 | **8.600** | 14.298 |

La fila de abajo es el hallazgo: **5.698 hits confirmados matchean contra
`PEP_AR` y no tienen la marca `is_pep`.** No es un descarte (esos son los
`DISCARDED`) ni un potencial: están confirmados contra una lista de PEPs y les
falta el flag.

De ahí salen tres definiciones defendibles, en clientes distintos:

| definición | tenant 3 | tenant 14 |
|---|---:|---:|
| (a) `is_pep = true`, sin mirar `result` | 10.237 | 440 |
| (b) `result = 'CONFIRMED_HIT'` (todos matchean PEP_AR) | 2.161 | 95 |
| (c) `result = 'CONFIRMED_HIT' AND is_pep = true` | 1.297 | 57 |

**(a) está mal y punto**: mete los 29.303 descartados por el analista, que es
literalmente la trampa 7 del diccionario. Entre (b) y (c) hay un **7,9×** contra
(a) y un **67 %** entre sí, y las dos son sostenibles: (c) es la que el
diccionario sugiere, (b) es la que dice que un hit confirmado contra una lista de
PEPs es un PEP aunque falte el flag.

### El eje que casi se me pasa: "alguna vez" no es "hoy"

Las tres definiciones de arriba comparten un supuesto que no había mirado, y es
el más grande de todos: **preguntan si el cliente dio hit alguna vez.**

`screenings` es una tabla historizada igual que `risk_assessments` —cada cliente
tiene **4 o 5 corridas**— pero, a diferencia de aquella, **no tiene `is_current`
ni nada que marque cuál vale hoy.** El diccionario no lo menciona, y como muestra
una sola forma de `metadata` es fácil leerla como si hubiera un screening por
cliente. Hay cinco.

De los clientes que alguna vez dieron `CONFIRMED_HIT`, esto dice su screening más
reciente:

```
su último screening dice NO_HIT ........... 1.568   (69,5 %)
su último screening dice CONFIRMED_HIT ....   688   (30,5 %)
```

**Siete de cada diez "PEPs" dejaron de serlo en su corrida más reciente.** Las
cuatro definiciones, entonces:

| definición | tenant 3 | tenant 14 |
|---|---:|---:|
| (a) `is_pep = true`, sin mirar `result` | 10.237 | 440 |
| (b) alguna vez `CONFIRMED_HIT` | 2.161 | 95 |
| (c) alguna vez `CONFIRMED_HIT AND is_pep` | 1.297 | 57 |
| **(d) su screening vigente es `CONFIRMED_HIT`** | **660** | **28** |
| (e) vigente `CONFIRMED_HIT AND is_pep` | 404 | 20 |

De (a) a (e) hay un **25×**. El eje temporal (b→d, un factor 3,3) pesa más que el
del flag `is_pep` (b→c, un factor 1,7), y es el que ninguna lectura del
diccionario sugiere.

Dos cosas que verifiqué antes de creerme esto:

- **Ningún cliente se contradice.** De los 2.256 que alguna vez dieron hit
  confirmado, **cero** tienen además un `DISCARDED`. Los que "dejan de ser PEP"
  pasan a `NO_HIT`, no a descartado: no es que el analista revirtió el hit, es
  que la corrida siguiente no lo encontró.
- **"El screening vigente" está bien definido.** Cero empates de `screened_at`
  dentro de un mismo cliente, así que el `DISTINCT ON (... ORDER BY screened_at
  DESC)` es determinístico y no hace falta desempatar por `id`.

**No la cierro acá.** Es el mejor candidato del dataset a
`NECESITO_QUE_ACLARES`: *"¿te referís a los clientes que hoy figuran como PEP
(660) o a los que alguna vez dieron positivo (2.161)?"* es una repregunta que un
oficial de compliance entiende y que cambia el número por tres. Va a H2 con el
eval de por medio (D-10). Lo que sí queda fijo es que (a) está descartada.

---

## 6. Las trampas restantes, con su número

### Trampa 1 · Soft-delete: sólo en la mitad de las tablas

`03-soft-delete.sql`. Ocho tablas tienen `deleted_at`. Cuatro lo usan:

| tabla | borradas | total | % |
|---|---:|---:|---:|
| `clients` | 34.382 | 1.193.000 | **2,88 %** |
| `transactions` | 1.487.179 | 71.974.632 | **2,07 %** |
| `client_documents` | 71.136 | 3.579.000 | 1,99 % |
| `risk_assessments` | 34.382 | 4.772.000 | 0,72 % |
| `alerts` | **0** | 202.556 | — |
| `cases` | **0** | 35.722 | — |
| `screenings` | **0** | 4.844.951 | — |
| `client_risk_overrides` | **0** | 23.799 | — |

Sigue siendo correcto escribir `deleted_at IS NULL` en las ocho —es gratis y
protege si el dump cambia—, pero cambia lo que hay que **decirle al oficial**: en
una respuesta sobre alertas, "no incluye alertas borradas" es ruido que no
excluye nada. La exclusión declarada de D-07 tiene que salir de la data, no de
una lista fija.

**Y hay un sesgo enorme escondido.** Los clientes marcados como riesgo alto se
borran 13 veces más que el promedio:

```
manual_high_risk_flag = true .......... 19.070
   de esos, vivos ..................... 11.920
   de esos, borrados ..................  7.150   ← 37,5 %
tasa de borrado de la base ...........   2,88 %
```

Olvidarse del `deleted_at IS NULL` en la pregunta de riesgo alto no infla el
número un 3 %: lo infla un **60 %**. (El `metadata.manual_review_reason` aparece
exactamente en los 11.920 vivos, lo cual es una forma barata de mostrar de dónde
salió la marca en la ficha de criterios de D-07.)

### Trampa 2 · El `AS_OF` es real, pero no en toda la base

`04-horizonte-temporal.sql`. H0 lo verificó sobre `transactions` y dio verde. Lo
corrí sobre las 15 columnas de fecha del esquema y hay dos excepciones:

| columna | máximo | filas después del AS_OF |
|---|---|---:|
| `clients.deleted_at` | **2026-06-29** | **733** |
| `client_documents.uploaded_at` | **2026-07-29** | **69.215** |
| `client_documents.expires_date` | 2027-… | 1.474.970 *(legítimo: vencen a futuro)* |
| todas las demás | ≤ 2026-06-01 | 0 |

Las dos primeras son inconsistencias del generador, no datos de negocio: un
documento no se puede haber subido dentro de dos meses. Son pocas (0,06 % de
`clients`, 1,9 % de `client_documents`) y ninguna de las 8 preguntas las toca,
pero desmienten la afirmación general. **`AS_OF` sigue siendo la fecha correcta
para interpretar "hoy"** —eso no cambia—; lo que cambia es que no se puede usar
"no hay datos posteriores" como invariante.

Un dato adicional que sí cambia respuestas: **cada tabla arranca en una fecha
distinta**.

```
transactions      2023-12-14 .. 2026-05-31    (2 años 5 meses)
risk_assessments  2023-09-04 .. 2026-05-30
alerts            2024-05-10 .. 2026-05-31    (2 años)
clients.onboarded 2024-05-11 .. 2026-05-31    (2 años)
screenings        2025-01-16 .. 2026-05-31    (17 meses)
cases             2025-08-04 .. 2026-05-30    (10 meses)
sar_reports       2025-11-13 .. 2026-05-31    (6 meses)
```

O sea: *"¿cuántos casos abrimos en 2024?"* tiene respuesta **cero**, y la
respuesta honesta no es "0" a secas sino "no hay casos anteriores a agosto de
2025 en la base". Lo mismo con screenings antes de 2025.

### Trampa 3 · El año fiscal es un distractor, y ahora se puede probar

`fiscal_year_start_month` toma 5 valores distintos (1, 3, 4, 7, 10) sobre 40
tenants. El diccionario es explícito en que **no** redefine los períodos. Lo que
importa es tener una institución donde `mes_fiscal <> 1` para poder *probar* que
no los redefine: el tenant 3 tiene mes fiscal **4**, y el 14 tiene **1**. El par
cubre los dos lados.

### Trampa 4 · Config versionada: sólo 3 de 40, y cambia el número 9,6×

`05-tenant-config.sql`. Las claves reales son **cinco**, tres más de las que
documenta el diccionario:

| clave | documentada | valores |
|---|---|---|
| `high_risk_score_threshold` | sí | 65 … 85 |
| `fiscal_year_start_month` | sí | 1, 3, 4, 7, 10 |
| `review_sla_hours` | mencionada al pasar | **24, 48, 72** |
| `pep_is_high_risk` | **no** | true / false (20 y 20) |
| `escalated_counts_as_finding` | **no** | true / false (20 y 20) |

203 filas = 5 claves × 40 tenants + 3 versiones extra. **Ninguna fila tiene
`effective_from_date` futura**, así que el filtro `<= AS_OF` no descarta nada
hoy — pero sigue siendo obligatorio, porque es lo único que hace correcta la
consulta si el dump cambia.

Las tres únicas filas versionadas, todas de `high_risk_score_threshold`:

| tenant | de | a |
|---|---|---|
| 1 `banco_norte` | 70 (2025-09-01) | **80** (2026-01-01) |
| 3 `banco_andino` | 80 (2025-10-15) | **85** (2026-02-01) |
| 6 `fintech_pampa` | 72 (2025-08-01) | **78** (2026-01-01) |

Cuánto cuesta equivocarse, medido en el tenant 1:

```
umbral 70 (la versión vieja) → 51.962 clientes
umbral 80 (la vigente)       →  5.399 clientes
```

**9,6×.** Es el error más caro de toda la exploración, y sólo se puede detectar
en tres instituciones de cuarenta.

Por qué duele tanto: los scores están generados **relativos al umbral vigente de
cada institución**, no en una escala absoluta. El 3,1 % de los clientes supera su
propio umbral, y da igual que el umbral sea 68, 80 u 85:

```
tenant  1 (umbral 80)   5.399 de 174.811   3,1 %
tenant  3 (umbral 85)   5.399 de 174.669   3,1 %
tenant 14 (umbral 68)     240 de   7.771   3,1 %
```

Es una propiedad útil para revisar una respuesta de un vistazo: "clientes de
riesgo alto por score" tiene que dar cerca del 3 % del padrón vivo. Un 30 %
significa que se tomó una versión vieja del umbral.

### Trampa 5 · No hay FX, y las cuatro monedas están en todos lados

`07-transacciones.sql`. **Los 40 tenants operan en las 4 monedas**, sin
excepción. No existe la institución mono-moneda donde un total único sería
inocente: D-08 (desglosar siempre por moneda) aplica al 100 % de las respuestas
de monto, no a un caso de borde.

El reparto es ~50 % ARS y ~17 % cada una de USD/EUR/USDT.

### Trampa 6 · Revertidas: el 20 % del volumen

```
SETTLED  43.277.625   60,1 %
REVERSED 14.375.874   20,0 %
PENDING  14.321.133   19,9 %
```

Contar todo en vez de sólo `SETTLED` **infla el volumen un 66 %**. Y hay una
segunda decisión escondida que el diccionario no toca: `PENDING` no es una
reversión, pero tampoco es movimiento efectivo todavía. `SETTLED` sola es la
lectura defendible, y las otras dos hay que declararlas como exclusión.

El soft-delete de `transactions` (2,07 %) es independiente y se suma.

Un detalle del signo, que importa para la pregunta 3 del enunciado: **`amount` es
siempre positivo** (de 1,00 a 5.000 en las `IN`, de 1,00 a 9.999 en las `OUT`),
sin ceros ni negativos. La dirección vive sólo en `direction`, así que un
`sum(amount)` a secas **suma entradas y salidas** en vez de netearlas. "Monto
total transado" es defendible como la suma bruta, pero hay que decir que lo es, y
el desglose por `direction` es tan obligatorio como el de moneda.

### Trampa 8 · Estados de alerta: el ciclo de vida es impecable

```
CLOSED_FALSE_POSITIVE  70.533   (34,8 %)   ← no son hallazgos
OPEN                   47.637   (23,5 %)
CLOSED_TRUE_POSITIVE   43.751   (21,6 %)
IN_REVIEW              28.712   (14,2 %)
ESCALATED              11.923    (5,9 %)
```

Verifiqué la coherencia del ciclo de vida y no hay una sola fila rara: cero
alertas cerradas sin revisar, cero cerradas antes de revisarse, y
`first_reviewed_at IS NULL` ⟺ `status = 'OPEN'` **exactamente** (47.637 = 47.637).
Esa equivalencia es útil: "sin revisar" y "abierta" son la misma población, y la
consulta puede usar el índice parcial `idx_alerts_tenant_unreviewed` o el de
status indistintamente.

Contar todas las alertas como hallazgos infla **2,3×** contra
`CLOSED_TRUE_POSITIVE`. Y falta decidir las escaladas, que es la trampa siguiente.

### Trampa 9 · Casos abiertos: el 40 %, y tres promedios distintos

`09-alertas-y-casos.sql`, 09.3. **El 40 % de los casos no está cerrado** — 40,0 %
en el tenant 3 y 40,3 % en el 14. La pregunta 7 del enunciado (*"tiempo promedio
de resolución"*) da tres números según qué se haga con ellos:

| forma de contar | tenant 3 (5.400 casos) | tenant 14 (243 casos) |
|---|---:|---:|
| **sólo los cerrados** (correcto) | **2,71 días** | **2,72 días** |
| contando los abiertos como "hasta hoy" | 25,97 días | 25,94 días |
| contando los abiertos como cero | 1,63 días | 1,63 días |

**9,6× de diferencia** entre la primera y la segunda. La respuesta correcta lleva
la aclaración obligatoria: *"promedio sobre los 3.239 casos cerrados; 2.161
siguen abiertos y no tienen tiempo de resolución"*.

Un detalle que cambia el `WHERE`: **`REPORTED_UIF` es un estado terminal**, no
uno abierto. Los 5.356 casos reportados a la UIF tienen `closed_at` y `outcome`
poblados igual que los `CLOSED`. "Casos cerrados" son los dos estados, no uno:
excluir `REPORTED_UIF` perdería el 25 % de los casos cerrados, y justo los más
graves.

### Trampa 11 · Documentos: mitad con guiones, mitad sin

`10-clientes-y-documentos.sql`. Sólo hay **dos** formatos, casi mitad y mitad:

```
con guiones (nn-nnnnnnnn-n)   597.179   50,1 %
sólo dígitos                  595.821   49,9 %
```

No hay puntos, ni espacios, ni prefijos de país; los cuatro tipos de documento
aparecen en los dos formatos. O sea que `regexp_replace(document_number,
'[^0-9A-Za-z]', '', 'g')` de D-09 alcanza y sobra.

Cuánto encuentra, en el par de trabajo:

| | tenant 3 | tenant 14 |
|---|---:|---:|
| clientes vivos | 174.669 | 7.771 |
| grupos por documento crudo | 174.579 | 7.766 |
| grupos por documento normalizado | **174.342** | **7.751** |
| filas duplicadas que se ven sin normalizar | 90 | 5 |
| **filas duplicadas totales** | **327** | **20** |

La normalización **multiplica por 3,6** lo que se detecta (327 contra 90 en el
tenant 3; 20 contra 5 en el 14). Es el número que justifica D-09 y el que hay que
poner en la respuesta.

Dato que el diccionario no da y hay que saber: `document_type` y
`document_number` son **nullable** en el esquema, aunque hoy no haya ni un `NULL`
en 1,19 M de filas. El `GROUP BY` tiene que ser `NULL`-safe igual.

### Trampa 12 · Aprobados sin fecha de alta: el 42 %

```
APPROVED ............................. 733.551
   de esos, sin onboarded_at ......... 307.444   ← 41,9 %
PENDING / REJECTED / MANUAL_REVIEW → onboarded_at NULL siempre (correcto)
```

**No es un caso de borde: son cuatro de cada diez aprobados.** La pregunta 1 del
enunciado (*"¿cuántos clientes onboardeamos este año?"*) tiene dos lecturas que
difieren en ese 42 %, y ninguna es obviamente mejor:

- contar `APPROVED` con `onboarded_at` en el período — precisa, pero deja afuera
  a los 307.444 sin fecha;
- contar `APPROVED` a secas — no se puede acotar a un período, así que no
  responde la pregunta.

Es un `RESPONDIDA_CON_SUPUESTO` de manual: la primera lectura es claramente la
más razonable (la pregunta pide un período, y sin fecha no hay período), pero el
supuesto hay que declararlo con el número de exclusión. Va a H2.

### Trampa 14 · Instituciones de baja: 2 de 40, con datos

Ya medido en H0 y sin cambios: `banco_nortte` (39) y `fintech_pampa_old` (40),
las dos con 1.500 clientes y 90.014 transacciones, las dos sin ningún caso. Con
D-03 (la institución se elige en la pantalla) esto deja de ser un problema de
consulta y pasa a ser uno de UI: el selector no debería ofrecerlas, o debería
marcarlas.

### Trampa 16 · Confirmada: 9 tablas y 3 claves de config sin documentar

Secciones 1 y 2. El diccionario avisó y cumplió: lo que está es correcto, lo que
falta es la mitad del trabajo.

---

## 7. Fuera de SLA: la definición tiene dos mitades y una estaba muerta

Pregunta 4 del enunciado. El SLA vive en `tenant_config.review_sla_hours` y toma
tres valores: 24 h (13 tenants), 48 h (14) y 72 h (13). La definición propuesta
en `DECISIONS.md` es *"sin revisar pasado el plazo, más las revisadas tarde"*.
Medí las dos mitades por separado (`09-alertas-y-casos.sql`, 09.4):

| SLA | tenants | sin revisar y vencidas | **revisadas tarde** |
|---|---:|---:|---:|
| 24 h | 13 | 9.483 | **10.219** |
| 48 h | 14 | 10.607 | **0** |
| 72 h | 13 | 9.672 | **0** |

**Las 10.219 alertas revisadas tarde viven íntegramente en los tenants de 24 h.**
La razón es simple: el tiempo máximo hasta la primera revisión en toda la base es
de **71 horas**, así que con un SLA de 48 o 72 h ninguna alerta llega tarde.

Y no es una mitad menor: en esos 13 tenants las revisadas tarde (10.219) son
**más** que las que siguen sin revisar y vencidas (9.483). Omitir esa mitad de la
definición no redondea el número, lo parte al medio.

Las dos mitades son reales y hay que implementar las dos. Pero la segunda **sólo
se puede ejercer en 13 de las 40 instituciones**, y eso tiene una consecuencia
que no es sobre la definición sino sobre cómo la validamos. Es la sección que
sigue.

---

## 8. El par de instituciones de trabajo: (1, 8) → (3, 14)

H0 eligió el par `1 banco_norte` / `8 emi_capital` con un criterio explícito, y
dejó escrita la regla para cambiarlo: *"si más adelante hace falta discriminar
[otro parámetro], hay que agregarlo al criterio y volver a correr la consulta, no
elegir otro tenant a dedo."* Es exactamente lo que hizo falta.

**El problema.** Ni el tenant 1 (SLA 48 h) ni el 8 (SLA 72 h) tienen alertas
revisadas tarde: las dos dan **cero**. Una golden query de "fuera de SLA" que se
olvidara de la mitad "revisadas tarde" **pasaría en las dos instituciones**. Es
justo el tipo de error que la regla de validar en dos tenants existe para
atrapar, y el par lo dejaba pasar.

Hay un segundo problema, más chico: el tenant 8 tiene 43.693 clientes contra
174.811 del tenant 1 — un factor 4. "Grande y chico" pedía más distancia: sobre
8.000 clientes los números se verifican a mano, sobre 43.000 no.

**El criterio ampliado** (`tests/criterio_fixture.py`, tres condiciones nuevas):

- **A** tiene el umbral versionado **y el `review_sla_hours` más corto de la
  base**. Lo segundo es lo nuevo: garantiza que la mitad "revisadas tarde" esté
  viva.
- **B** tiene el umbral en una sola versión, **a lo sumo un décimo de los
  clientes de A**, y contrasta con A en los **seis** parámetros de negocio —
  `kind`, umbral, SLA, mes fiscal, `pep_is_high_risk` y
  `escalated_counts_as_finding`. H0 sólo exigía tres y compartía
  `pep_is_high_risk` con A; ahora no queda ninguno compartido.

**El par que devuelve:**

```
tenant A: id=3  banco_andino  BANK     174.669 clientes  umbral 85 (2 versiones)
                              sla 24h  mes fiscal 4   pep_alto=true   escalada=true
tenant B: id=14 fintech_cuyo  FINTECH    7.771 clientes  umbral 68 (1 versión)
                              sla 72h  mes fiscal 1   pep_alto=false  escalada=false
```

| dimensión | A · 3 | B · 14 | qué ejerce |
|---|---|---|---|
| tamaño | 174.669 clientes · 10,9 M tx | 7.771 · 482 k | peor caso de performance / verificable a mano |
| umbral | **85, versionado** (era 80) | 68, una versión | la trampa del `effective_from_date` |
| SLA | **24 h** | 72 h | las dos mitades de "fuera de SLA" |
| mes fiscal | **4** | 1 | probar que el año fiscal *no* redefine el período |
| `pep_is_high_risk` | **true** | false | las dos ramas de "riesgo alto con PEP" |
| `escalated_counts_as_finding` | **true** | false | las dos ramas de "hallazgo real" |
| `kind` | BANK | FINTECH | — |

Lo que se **pierde** al soltar el tenant 1, y que quiero dejar dicho porque es un
costo real: el tenant 1 es el único donde `alert_case_links ⋈ alerts` devuelve
filas (sección 3). Tenerlo en el par significaba que una consulta que usara esa
tabla daría 1.575 en A y 0 en B, y la discrepancia la delataría sola. Con el par
nuevo da 0 en los dos y la consulta parece consistente.

Lo acepto porque el hallazgo ya está documentado y va a quedar codificado como
`NO_SE_PUEDE_RESPONDER` en H2 — no depende del fixture para redescubrirse —,
mientras que la mitad "revisadas tarde" del SLA es una definición que sí se puede
implementar mal en silencio. Entre un error ya atrapado y uno que todavía puede
entrar, el fixture cubre el segundo.

Los 47 tests de la suite pasan con el par nuevo, sin tocar ningún test: los IDs
no están escritos en ninguna parte, que era exactamente el punto.

### Un control que me debía: explorar sin RLS y responder con RLS

Toda esta exploración corrió como `postgres`, sin RLS, con un `WHERE tenant_id IN
(3, 14)` escrito a mano. El producto va a leer con `agent_ro` y el predicado de la
policy. Que los planes sean equivalentes ya lo había medido H0, pero **que los
números sean idénticos** no lo había verificado nunca. Lo comprobé con
`agent_connection` sobre cuatro cifras clave:

| | tenant 3 | tenant 14 |
|---|---|---|
| riesgo alto (unión) | 7.199 ✓ | 321 ✓ |
| casos sin cerrar | 2.161 ✓ | 98 ✓ |
| PEP alguna vez confirmado | 2.161 ✓ | 95 ✓ |

Coinciden las seis. No es una formalidad: si la policy tuviera un `NULL` mal
manejado o una tabla sin RLS, acá aparecería como una diferencia y no como un
error.

---

## 9. Las seis definiciones pendientes: cuatro cerradas, dos abiertas

Estado de la tabla "Definiciones a fijar" de `DECISIONS.md` después de explorar.

| concepto | estado | definición |
|---|---|---|
| **Riesgo alto** | ⚠️ **cerrada salvo la perilla** | `score >= umbral vigente al AS_OF` **o** `manual_high_risk_flag`, sobre clientes vivos con evaluación vigente viva; **más los PEP vigentes donde `pep_is_high_risk` está en `true`**. Las **tres** fuentes son disjuntas (0 solapamiento): la cascada suma sin nota al pie. La marca aporta el 25 % y el PEP otro 9 % |
| **Resolución de casos** | ✅ **cerrada** | `closed_at - opened_at` **sólo sobre casos con `closed_at`**, que son los de status `CLOSED` **y `REPORTED_UIF`**. Se reporta cuántos quedan fuera (el 40 %). Los abiertos son N/A, ni cero ni "hasta hoy" |
| **Fuera de SLA** | ✅ **cerrada** | Dos poblaciones, las dos necesarias: sin revisar con `AS_OF - triggered_at > sla`, más revisadas con `first_reviewed_at - triggered_at > sla`. El plazo es `tenant_config.review_sla_hours` |
| **Cliente onboardeado** | ⚠️ **con supuesto** | `APPROVED` con `onboarded_at` en el período. Los **307.444 aprobados sin fecha (41,9 %)** quedan fuera y hay que **declararlo con el número**. No es cerrarla: es elegir la única lectura que responde la pregunta y decir qué costó |
| **Hallazgo real** | 🔓 **abierta** | `CLOSED_TRUE_POSITIVE` seguro. Las `ESCALATED` dependen de `tenant_config.escalated_counts_as_finding`, que **existe y varía** (20/20). Falta decidir si la config manda o si se repregunta. En el tenant 3 la diferencia es **+50 %** (3.602 → 5.404 en el trimestre) |
| **PEP** | 🔓 **abierta** | Descartada la lectura floja (`is_pep` sin mirar `result`: mete los descartados). Quedan cuatro, de 2.161 a 404 en el tenant 3, sobre **dos ejes**: el flag `is_pep` (×1,7) y —el que pesa— si vale el screening **vigente** o cualquiera de los 4-5 históricos (×3,3). Se decide con el eval |

Las dos que quedan abiertas lo quedan por la misma razón, y es una buena razón:
**las dos tienen una perilla en `tenant_config` o una ambigüedad real en la data,
y son los mejores candidatos del dataset para probar los estados
`RESPONDIDA_CON_SUPUESTO` y `NECESITO_QUE_ACLARES`.** Cerrarlas a dedo ahora
sería tirar los dos casos de prueba más valiosos que tiene la base.

---

## 10. Qué queda pendiente

| Hallazgo | Va a |
|---|---|
| Las 8 definiciones/skills, con sus golden queries en los tenants 3 y 14 | H2 |
| **`screenings` está historizada sin `is_current`**: hay que decidir si "PEP" mira el screening vigente o cualquiera. Es el eje más pesado de esa definición (×3,3) | H2 |
| Decidir si `pep_is_high_risk` manda sola o si conviene mostrar el número con y sin PEPs (en el tenant 3 son 7.859 contra 7.199) | H2 / H3 · panel de D-07 |
| `sum(amount)` suma entradas y salidas: el desglose por `direction` es tan obligatorio como el de moneda | H2 |
| Decidir "hallazgo real" y "PEP" contra el eval | H2 / H4 |
| **El gate de `EXPLAIN` no puede rechazar `Seq Scan` a secas**: para las 5 tablas sin índice es el único plan, y cuesta 55–170 ms | H3 · gate de D-06 |
| Preguntas incontestables ya identificadas: alerta↔caso, sanciones/listas que no sean `PEP_AR`, conversión de monedas, "a qué se overrideó el riesgo", casos antes de ago-2025 | H4 · set de evals |
| La exclusión declarada de D-07 tiene que salir de la data (en `alerts` no hay borradas) y no de una lista fija | H3 |
| El selector de instituciones debería marcar o esconder las 2 dadas de baja | H3 · UI |
| `screening_runs` no se puede unir a `screenings`: no hay `run_id`. Otra incontestable | H4 |

---

## Anexo · Correcciones que amerita `DECISIONS.md`

Como en las notas anteriores: `DECISIONS.md` no se toca desde el código, así que
esto queda propuesto y lo escribe el usuario.

1. **Tabla de trampas** — pasar las 16 de "detectada leyendo" a confirmada o
   desmentida, con el número de esta nota. Las que cambian de lectura:
   - **#1** no es uniforme: 4 de 8 tablas, y con un sesgo de 13× en los marcados.
   - **#2** desmentida en parte: hay 70.000 filas posteriores al `AS_OF`.
   - **#10** es más fuerte de lo anotado: el vínculo **no existe**, y la tabla
     puente es un señuelo.
   - **#15** cambia de forma: no se contradicen, son **disjuntas**.
2. **D-09** puede citar el número que la justifica: la normalización multiplica
   por 3,6 los duplicados detectados (327 contra 90 en el tenant 3).
3. **D-06** necesita una precisión: el gate mira **costo**, no tipo de nodo. El
   `Seq Scan` sobre las tablas sin índice es legítimo y barato.
4. **Definiciones a fijar** — reemplazar la tabla por la de la sección 9.
5. Anotar que **`tenant_config` tiene tres claves más** que las documentadas, y
   que dos de ellas (`pep_is_high_risk`, `escalated_counts_as_finding`) son
   perillas de negocio que cambian el resultado de preguntas enteras.
