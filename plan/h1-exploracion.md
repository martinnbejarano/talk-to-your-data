# H1 · Exploración de la data

**Objetivo.** Completar los huecos que el diccionario deja **a propósito**, y confirmar
o desmentir las 16 trampas que anoté leyendo la documentación.



**Nota de método.** La exploración corre como `postgres` con `statement_timeout = 0`,
no como `agent_ro`. Explorar es un trabajo distinto de responder: acá quiero ver todo,
aunque tarde. Las consultas del producto sí viven bajo las restricciones.

## Tareas

### 1. Inventario del esquema — sin escanear nada

La mayor parte de lo que necesito está en el catálogo de Postgres, que es instantáneo:


| Qué busco                                          | De dónde sale                                     |
| -------------------------------------------------- | ------------------------------------------------- |
| Todas las tablas y su volumen aproximado           | `pg_class.reltuples`, `pg_total_relation_size`    |
| Columnas, tipos, nullability                       | `information_schema.columns`                      |
| **Los valores reales de los "enums"**              | `pg_get_constraintdef` de los `CHECK`             |
| **El vínculo alerta↔caso**                         | foreign keys en `pg_constraint` (`contype = 'f'`) |
| Índices reales (¿son sólo los 12 del diccionario?) | `pg_indexes`                                      |


El truco de los `CHECK` es importante: el diccionario dice que los enums son `TEXT` con
`CHECK (... IN (...))`, así que **puedo leer los valores permitidos de la definición de
la constraint** en vez de hacer un `SELECT DISTINCT` sobre decenas de millones de filas.
Y las foreign keys me dan el link alerta↔caso que el diccionario dice que "vive en otra
parte del esquema", sin adivinar.

### 2. Las tablas no documentadas

El diccionario menciona que hay tablas "de auditoría, documentos, contrapartes, etc.".
Para cada una que aparezca: cuántas filas, qué columnas, si tiene `tenant_id`, con qué
se relaciona, y **si sirve para alguna de las 8 preguntas de ejemplo**. La conclusión
"esta tabla no la necesito" también se anota — evita joins de más.

### 3. Confirmar las trampas, una por una


| #   | Qué mido                                                                                                           |
| --- | ------------------------------------------------------------------------------------------------------------------ |
| 1   | Qué proporción de filas tiene `deleted_at` no nulo, por tabla                                                      |
| 2   | `max(tx_date)`, `max(triggered_at)`, `max(created_at)` — ¿`AS_OF` es real?                                         |
| 4   | `SELECT DISTINCT key FROM tenant_config` y cuántos tenants tienen cada key versionada                              |
| 5   | Distribución de `currency`; ¿hay tenants multi-moneda?                                                             |
| 6   | Distribución de `transactions.status`                                                                              |
| 7   | Distribución de `screenings.result` y forma real del JSONB `metadata`                                              |
| 8   | Distribución de `alerts.status` y `severity`                                                                       |
| 9   | Cuántos casos están sin cerrar, por tenant                                                                         |
| 10  | ¿`alerts.case_id` está realmente todo en NULL? ¿cuál es la tabla puente?                                           |
| 11  | Formatos reales de `document_number` (con guiones, con puntos, mixtos) y cuántos duplicados aparecen al normalizar |
| 12  | Cuántos `APPROVED` tienen `onboarded_at IS NULL`                                                                   |
| 13  | ¿Hay exactamente un `is_current = true` por cliente, como promete el diccionario?                                  |
| 14  | Cuántos tenants hay, cuántos inactivos, y la volumetría de cada uno                                                |
| 15  | **Cuánto se contradicen `score >= umbral` y `manual_high_risk_flag`**                                              |


La 15 es la más importante: define si "riesgo alto" es una unión de dos fuentes o si
una es residual. El número concreto va a la skill y a la respuesta del sistema.

### 4. Claves de los JSONB

`metadata` aparece en varias tablas y el diccionario sólo muestra una forma de ejemplo.
Muestrear las claves de primer nivel con `jsonb_object_keys` sobre una muestra acotada,
y ver qué hay adentro de `matches` en `screenings`.

### 5. Elegir dos tenants de trabajo

Uno grande y uno chico, con configs distintas (idealmente uno con
`high_risk_score_threshold` versionado y otro no). Todas las golden queries de H2 se
validan contra los dos: si una definición sólo funciona en uno, está mal.

## Entregables

- `scripts/explore/*.sql` — cada consulta de exploración, versionada y reproducible.
Cualquiera puede correrlas y ver lo mismo que vi yo.
- `NOTES/01-exploracion.md` — los hallazgos en prosa: qué esperaba, qué encontré, qué
me confundió, qué supuesto tuve que tirar. Se escribe **mientras** exploro, no después:
reconstruir por qué algo confundía es imposible una vez que dejó de confundir.
- Actualización de `DECISIONS.md`: la tabla de trampas pasa de "detectada leyendo" a
"confirmada / desmentida", y las 6 definiciones pendientes quedan cerradas o se
documenta por qué siguen abiertas.

## Definition of done

- [ ] Inventario completo de tablas, con las no documentadas caracterizadas.
- [ ] Valores reales de todos los enums, extraídos de los `CHECK`.
- [ ] **Identificada la tabla que vincula alertas con casos.**
- [ ] Las 16 trampas confirmadas o desmentidas con un número.
- [ ] Dos tenants de trabajo elegidos y justificados.
- [ ] `NOTES/01-exploracion.md` escrito.

## Riesgos


| Riesgo                                                   | Mitigación                                                                               |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Perderme explorando (la base es grande y es entretenida) | La lista de arriba es cerrada. Lo que no está, no se explora en este hito                |
| Confundir "no encontré" con "no existe"                  | Cada conclusión negativa se apoya en el catálogo, no en un `SELECT` que no devolvió nada |


