# 03 · El prototipo del loop, y la decisión sobre D-01

**Hito:** H3.2 · Medir si el agente converge, antes de escribir el producto encima.
**Fecha de la corrida:** 2026-09-06 · **Postgres:** 17.11 · **AS_OF:** 2026-06-01
**Modelo:** el de `OPENAI_MODEL` (`gpt-5.5-2026-04-23` en esta corrida), vía function
calling, sin framework de agentes.

> **Esta nota no es reproducible, y es a propósito.** El prototipo era descartable
> desde el día uno y ya no existe: lo que vuelve son las mediciones. Lo que sí queda
> es qué se midió y contra qué, que es lo que hace auditable la decisión.

**Conclusión, arriba de todo: D-01 queda confirmado.** El agente converge, y las cinco
mediciones dan por debajo de su umbral con margen. La alternativa registrada —"catálogo
primero, SQL de fallback"— no hace falta. Lo que la ablación agrega es más fuerte que lo
que el mini-plan esperaba: sin la definición curada el agente **no** inventa un `score >
80`, encuentra la configuración solo y aplica el umbral vigente correcto; lo que no puede
hacer solo es **componer las tres fuentes disjuntas** y **congelar la lectura de PEP**.
El error que queda sin las skills no es de aritmética, es de definición.

---

## 1. Qué era el prototipo

Un script de consola de ~530 líneas, corrido desde fuera del repo. Adentro, lo mínimo
para que la pregunta de diseño se pudiera contestar y nada más:

- Las **cinco tools** de la spec (`list_tables`, `describe_table`, `sample_values`,
  `get_definition`, `run_sql`), con el mismo reparto de responsabilidades del diseño.
- Un **`run_sql` que es el seam 1 en miniatura**: conexión `agent_ro` vía
  `core.db.agent_connection`, transacción de sólo lectura con `SET LOCAL app.tenant_id`
  —o sea, **bajo RLS**—, `EXPLAIN (FORMAT JSON)`, gate, y los errores de Postgres
  normalizados por SQLSTATE a `TIMEOUT` / `SINTAXIS` / `PERMISO` / `OTRO`.
- Un **gate mínimo**: rechazar un `Seq Scan` sobre una tabla de `reltuples >= 100k`, y
  nada más. El techo por costo es de H3/04 y no hacía falta acá.
- El **esquema con los índices en el system prompt** (6.107 caracteres para las 22 tablas,
  151 columnas y 35 índices), la fecha de corte, las reglas duras, y —sólo en el brazo
  "con skill"— el catálogo de conceptos en una línea.
- Los cuatro parámetros de siempre (`tenant`, `as_of`, `desde`, `hasta`) atados por el
  sistema: el agente escribe `%(tenant)s`, nunca un literal.

**18 corridas medidas contra la API real**, US$ 1,53 —más una corrida piloto y una sonda
de un token para ver el detalle de `usage`, que no entran en las tablas—. Ninguna tocó
psycopg desde el agente y ninguna vio una fila de otra institución.

---

## 2. Las cinco mediciones

| Medición | Umbral | Medido | |
|---|---|---|---|
| Pasos hasta la consulta correcta | ≤ 6 | **2** en las 10 corridas con skill sin rechazo | ✓ |
| Recuperación tras un rechazo del gate | ≤ 2 intentos | **1** intento, 2 de 2 — *con el rechazo inyectado, n=2* | ✓ * |
| Consistencia en 5 corridas del mismo prompt | el mismo número las 5 veces | **7.859 las cinco veces** | ✓ |
| Tokens por pregunta | costo tolerable | **10.859** (9.974 in + 885 out) ≈ **7,6 ¢** | ✓ |
| ¿Lee la skill o la ignora? | la lee sin que haya que rogarle | **12 de 12**, y siempre como **primer paso** | ✓ |

\* La única con asterisco. El gate mínimo no rechazó nunca por su cuenta, así que el
rechazo hubo que provocarlo y la sugerencia la escribió una persona. Está medido, pero con
dos corridas y una sonda armada a mano: leerlo con eso puesto. El detalle, más abajo.

Un **paso** es lo que [`CONTEXT.md`](../CONTEXT.md) define —cada cosa que hace el agente
mientras trabaja— y acá se materializa como una llamada a una tool, que es la unidad que
el tope de pasos del loop va a contar. Las llamadas al modelo fueron 3 en el caso normal
y 4 con un rechazo.

### Pasos

Las ocho corridas con skill sobre la pregunta canónica hicieron lo mismo:
`get_definition("riesgo_alto")` → `run_sql`, y el segundo paso ya devolvió 7.859 (tenant
3) o 321 (tenant 14). Las dos de la pregunta fuera de la canónica también llegaron en dos
pasos, y las dos con rechazo del gate en tres. El umbral de 6 estaba pensado para un
agente que tuviera que explorar; con el esquema en el prompt y la definición a un
llamado, la exploración no ocurre.

**`list_tables` y `describe_table` no se llamaron ni una vez en 18 corridas.** El esquema
con índices en el system prompt las vuelve innecesarias para esta pregunta. `sample_values`
se usó 6 veces, **todas en el brazo sin skill**, para descubrir los valores de
`screenings.result` y `onboarding_status`: son los siete enums sin `CHECK` de H1, y con la
definición curada esos valores ya vienen escritos.

### Recuperación tras el rechazo

El rechazo se **inyectó**: el gate mínimo no rechazaba nada por su cuenta, porque —como ya
había medido [`NOTES/01-limites-y-planes.md`](01-limites-y-planes.md) §2— con RLS el
planificador nunca elige por su cuenta un `Seq Scan` sobre una tabla grande.

La primera sonda estuvo mal elegida y el error vale escribirlo, porque es una lección para
el gate real: se rechazó con la sugerencia *"materializá el CTE de screenings"*, que la
consulta **ya cumplía**. El agente reintentó con un SQL idéntico salvo la indentación y el
gate lo dejó pasar. Recuperación de 1 intento, sí, pero hueca.

La segunda sonda pidió un cambio que la consulta no tenía: *"resolvé el escalón de PEP con
un `EXISTS` o un `LATERAL` correlacionado por cliente, y filtrá `clients` por `deleted_at
IS NULL` en el `FROM`"*. Ahí la recuperación fue real: las dos corridas reemplazaron el
`screening_vigente AS MATERIALIZED` por un `LEFT JOIN LATERAL … LIMIT 1`, movieron el
filtro de borrado al `FROM`, y **siguieron dando 7.859**. Un intento, las dos veces.

> **Lo que esto le exige al gate de H3/04:** la `sugerencia` tiene que ser específica de lo
> que *esta* consulta hizo mal. Una sugerencia genérica que la consulta ya satisface no
> produce una reescritura, produce un reenvío — y como el segundo envío pasa, el rechazo
> se vuelve un peaje de tokens que no compró nada.

### Consistencia

Cinco corridas del mismo prompt en el tenant 3, con skill: **7.859, 7.859, 7.859, 7.859,
7.859**. Los siete escalones de la derivación también coincidieron cuando aparecieron
(180.000 / 174.669 / 174.669 / 5.399 / 1.800 / 660 / 7.859), que son exactamente los de
[`evals/valores_esperados.yaml`](../evals/valores_esperados.yaml).

**Lo que no fue consistente es cuántos escalones vuelven.** De las ocho corridas con skill
sobre la canónica, tres devolvieron los siete, cuatro devolvieron seis (se comieron
`total`) y una devolvió cuatro. El número es estable; la derivación, no. Ver §5.

### Tokens y costo

A US$ 5 / 1M de entrada y US$ 30 / 1M de salida, que es lo que cotiza el modelo por debajo
de los 272K de contexto. Los tokens de salida incluyen los de razonamiento
(`completion_tokens_details.reasoning_tokens`), que son la mayor parte.

| escenario | n | entrada | salida | total | costo |
|---|---:|---:|---:|---:|---:|
| canónica, con skill | 8 | 9.974 | 885 | 10.859 | **7,6 ¢** |
| canónica, sin skill | 6 | 7.143 | 1.108 | 8.251 | 6,9 ¢ |
| canónica + 1 rechazo del gate | 2 | 14.810 | 1.835 | 16.644 | 12,9 ¢ |
| pregunta fuera de la canónica, con skill | 2 | 10.456 | 1.406 | 11.862 | 9,4 ¢ |

Medianas. Un rechazo del gate **cuesta el 70 % de una pregunta entera**: 5,3 ¢ de más, casi
todo en volver a mandar el contexto. Es el argumento económico de que el gate acierte la
sugerencia a la primera, y de que el tope de pasos sea bajo.

En esta corrida **`cached_tokens` fue 0**: no hubo cacheo de prompt. Las tres vueltas de
una pregunta comparten un prefijo de ~2.500 tokens (reglas + esquema + catálogo), así que
hay margen ahí y no hace falta usarlo todavía.

### Si lee la skill

**12 de 12**, y en las doce fue el **primer paso**, antes de mirar el esquema o escribir
una línea de SQL. No hubo que rogarle: alcanzó con listar los nueve conceptos por nombre en
el system prompt. Cuando el concepto no está en el catálogo, el brazo sin skill muestra que
el agente arranca por `sample_values` — busca los valores que no puede adivinar.

---

## 3. La ablación: qué inventa el agente cuando nadie le curó la definición

Tres rondas de la pregunta canónica, en las dos instituciones, con la tool
`get_definition` presente y ausente.

| | tenant 3 · banco_andino (esperado **7.859**) | tenant 14 · fintech_cuyo (esperado **321**) |
|---|---|---|
| **con skill** | 7.859 las **cinco** veces ✓ | 321 · 321 · 321 ✓ |
| **sin skill** | 7.199 · **9.360** · 7.199 ✗ | 321 · 321 · 321 ✓ *(por coincidencia)* |

**El brazo "con skill · tenant 3" no es evidencia aparte: son las mismas cinco corridas de
la medición de consistencia.** Se declara porque contarlas dos veces inflaría la muestra.
Las otras tres celdas sí son corridas propias, tres cada una.

**La definición que inventa, dos de cada tres veces:**

> *"Clientes vivos con evaluación de riesgo vigente, cuyo score es mayor o igual al umbral
> configurado, **o** que tienen marca manual de alto riesgo."*

Es exactamente la fila *"score **o** marca manual"* de
[`NOTES/02-semantica.md`](02-semantica.md) §1, que da **7.199 y 321**. Pierde el escalón
de PEP: **−660 clientes**, que es el **8,4 %** de la respuesta correcta (660/7.859) o el
**9,2 %** de la que da el agente (660/7.199) — el segundo es el que usa esa misma tabla de
H2, y son el mismo hallazgo con dos denominadores. La institución nunca se entera de que
ese escalón existía.

**Y la tercera vez inventa otra cosa distinta:** la corrida del **9.360** sí incluyó el
escalón de PEP, pero lo resolvió como *"alguna vez `CONFIRMED_HIT`"* —2.161 clientes— en
lugar de *"su screening vigente es `CONFIRMED_HIT`"* —660—. La aritmética lo confirma:
**7.199 + 2.161 = 9.360**, o sea que lo único que movió el número respecto de las otras dos
corridas es qué población alimentó el tercer escalón. (Su consulta además soltó el
requisito de tener evaluación vigente, pero eso no cambia nada acá: en el tenant 3
`con_evaluacion` y `activos` valen los dos 174.669.)

**9.360 es, al peso, el extremo superior del rango que
[`DECISIONS.md`](../DECISIONS.md) D-13 congeló** (*"el total del tenant 3 va de 7.603 a
9.360 según qué definición de PEP alimente el tercer escalón"*). El agente eligió sin
decirlo la punta más cara del rango que una decisión de negocio ya había cerrado del otro
lado.

**Tres cosas que esto prueba, y que no se sabían antes de medirlas:**

1. **El error sin skills no es de aritmética ni de umbral: es de definición.** El agente
   encontró `tenant_config` solo, aplicó `effective_from_date <= as_of ORDER BY … DESC` y
   sacó el umbral **85** (y **68** en el tenant 14) en las seis corridas. La trampa más
   cara del dataset —tomar la versión vieja del umbral, ×4,9 según
   [`NOTES/02-semantica.md`](02-semantica.md) §1— no la pisó nunca. La hipótesis del
   mini-plan (*"probablemente `score > 80` hardcodeado"*) queda **refutada**: el modelo es
   mejor de lo que suponíamos leyendo el esquema, y eso no lo salva.
2. **Sin skill el agente ni siquiera es consistente consigo mismo.** 7.199 contra 9.360 son
   un **30 % de dispersión** sobre la misma pregunta, la misma institución y el mismo
   prompt. Un sistema que contesta eso no falla: contesta distinto cada vez y las dos veces
   con seguridad.
3. **El acierto del tenant 14 es una coincidencia, y hay que leerlo como tal.** Ahí
   `pep_is_high_risk` está en `false`, así que el escalón que el agente se olvida vale 0 y
   la definición equivocada da el número correcto. Es el argumento más nítido de por qué el
   par de instituciones del fixture tiene que contrastar: **con el tenant 14 solo, la
   ablación habría dado que las skills no hacen falta.**

---

## 4. ¿Adapta la golden o la copia y pega?

El riesgo que la spec de H3 agregó por su cuenta: si `get_definition` devuelve la
`golden_sql` y el agente sólo la copia, D-01 quedó implementado como su alternativa —el
catálogo cerrado— sin que nadie lo decidiera.

**Adapta. Ninguna de las 12 corridas con skill mandó la golden textual.** Medido como
igualdad del SQL normalizado contra la `golden_sql` de
[`core/semantics/riesgo_alto.yaml`](../core/semantics/riesgo_alto.yaml): 0 de 12.

Sobre la pregunta canónica las modificaciones son chicas pero deliberadas: le agrega
`AND key IN ('high_risk_score_threshold', 'pep_is_high_risk')` al CTE de config, y devuelve
el umbral y la perilla como columnas para poder declararlos en la respuesta —algo que la
golden no hace y que el contrato sí necesita.

La prueba de fuego fue correr la pregunta **fuera** de la canónica: *"¿cuántos clientes de
riesgo alto tenemos **en cada país**?"*. Las dos corridas:

- conservaron el esqueleto semántico —umbral vigente, perilla, las tres fuentes disjuntas,
  los filtros de borrado en las dos tablas—,
- **agregaron un `JOIN countries` y un `GROUP BY`** que la golden no tiene,
- movieron `c.deleted_at IS NULL` del `FILTER` al `WHERE`, porque el escalón `total` ya no
  servía para nada,
- y llegaron a una apertura por país, diez filas que **suman 7.859**.

Es adaptación, no copia. La golden funcionó como referencia y no como catálogo, que es
exactamente lo que D-01 quería.

---

## 5. Lo que la medición encontró y hay que arreglar en el motor

Tres cosas que no son "el agente no converge" pero sí son requisitos que el loop y el
contrato tienen que cumplir, y que sin el prototipo se habrían descubierto en H5.

### 5.1 · El agente calculó un número solo, y el validador es lo único que lo atrapa

En **1 de las 2** corridas de la pregunta por país, la consulta devolvió las diez filas
por país **y ningún total**. El agente sumó los diez números él mismo y publicó
**"Total: 7.859"**. El resultado da bien —es un modelo que suma bien— y ése es justamente
el problema: es una cifra plausible que no salió de la base, en la única corrida donde
nadie la habría cuestionado.

La otra corrida sí lo hizo bien, con `sum(...) OVER ()` dentro de la misma consulta. Las
dos vienen del mismo prompt y de la misma regla dura escrita en el system prompt. **Pedirlo
en el prompt no alcanza.** El validador de trazabilidad de H3.4 no es una baranda de más:
es el único mecanismo que separa estas dos corridas, y `7.859` no está en ningún resultado
de la que falló.

### 5.2 · La derivación no se puede dejar a criterio del modelo

De las 8 corridas con skill sobre la canónica: 3 devolvieron los siete escalones, 4 se
comieron `total` (los 180.000 clientes con los borrados adentro) y 1 devolvió sólo cuatro.
Los valores nunca se contradicen —cuando `por_score` aparece, vale 5.399 siempre—: lo que
varía es cuáles aparecen. El escalón que más se pierde es el primero, que es el que le da
sentido a la exclusión *"clientes dados de baja"* de la pantalla: sin `total` y
`activos` juntos, la
resta que el oficial tiene que ver no existe.

La skill ya declara sus siete escalones en `derivacion`. El loop tiene que **exigirlos**,
no esperarlos.

### 5.3 · Obedecer al gate colapsa la derivación

Las dos reescrituras tras el rechazo por costo perdieron los escalones `total` y `activos`,
fusionados en un `activos_con_evaluacion`. Es consecuencia directa de la sugerencia: mover
`deleted_at IS NULL` al `FROM` hace que las filas borradas no lleguen a contarse nunca.

O sea: **el rechazo del gate y la forma de la derivación se pelean.** La sugerencia del
gate tiene que poder decir *"reescribí el plan, pero seguí devolviendo estas columnas"*, o
el reintento arregla el costo y rompe la respuesta.

> **Pendiente para el usuario.** Amerita una precisión de D-06 en
> [`DECISIONS.md`](../DECISIONS.md): el rechazo del plan tiene una segunda obligación que
> la decisión no preveía —además de decir por qué el plan es caro, tiene que decir qué
> columnas la respuesta necesita seguir teniendo—, porque obedecerlo a secas colapsa la
> derivación. Y una sugerencia que la consulta ya cumple no compra una reescritura, compra
> un reenvío que se paga en tokens (§2). `DECISIONS.md` no se toca desde el código; la
> escribe el usuario.

---

## 6. La decisión

**D-01 se confirma, sin corrección.** Un agente con las cinco tools y las definiciones
curadas converge a una consulta correcta e indexada en dos pasos, se recupera de un rechazo
del gate en uno, contesta el mismo número cinco de cinco veces, cuesta menos de diez
centavos por pregunta y lee la definición sin que haya que insistirle. No hace falta el
"catálogo primero, SQL de fallback".

Y las skills se ganaron el lugar con evidencia y no con argumento: **sin ellas, la
institución grande recibe dos respuestas distintas en tres corridas, y ninguna de las dos
es la correcta.**

Lo que la medición corrige no es la arquitectura, son tres supuestos sobre el loop:
el validador de trazabilidad es obligatorio (§5.1), la derivación se exige y no se espera
(§5.2), y la sugerencia del gate tiene que ser específica y compatible con la derivación
(§5.3 y §2). Los tres son de H3/04 y H3/05, y ninguno cambia un seam.

---

## 7. Qué queda pendiente

Estado tildado en H3/09, al cerrar el hito.

| Hallazgo | Va a | Estado |
|---|---|---|
| El validador de trazabilidad tiene que correr **siempre**: el agente suma por su cuenta cuando la consulta no trajo el total (§5.1) | H3.4 · validador | **cerrado** · `core/trazabilidad.py`, y el loop lo reclama antes de entregar |
| El loop tiene que exigir los escalones que la skill declara, no confiar en que el modelo los devuelva (§5.2) | H3.5 · loop | **cerrado** · `_lo_que_falta` en `agent/loop.py` |
| La `sugerencia` del gate tiene que ser específica de la consulta rechazada, y decir qué columnas hay que seguir devolviendo (§2, §5.3) | H3.4 · gate | **a medias → H5** · la del `Seq Scan` nombra las tablas; la de costo es una plantilla que la consulta puede ya cumplir, que es el reenvío que §2 advirtió. Y el *"seguí devolviendo las mismas columnas"* quedó en `agent/tools.py`, pegado a **todo** rechazo, no en el gate |
| `list_tables` y `describe_table` no se usaron nunca con el esquema en el prompt. Se quedan igual —hacen falta para las preguntas que no tienen skill— pero no son el camino caliente | H3.5 · tools | **cerrado** · se quedaron |
| `OPENAI_MODEL` y `OPENAI_API_KEY` viven sólo en el `.env` de cada máquina | H3.5 · config | **cerrado** · están en `.env.example` y se leen por `core/config.py` |
| La precisión de D-06 de §5.3, que la escribe el usuario | `DECISIONS.md` | abierto · redactada en el issue #15 para pegar |
| Nadie midió el cacheo de prompt: el prefijo de ~2.500 tokens se remanda en cada vuelta | H6 · costo | abierto |
| `fastapi` y `uvicorn` todavía no están en `requirements.txt` | H3.5 · API | **cerrado** |
