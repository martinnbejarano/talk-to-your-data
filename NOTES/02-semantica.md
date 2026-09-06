# 02 · Semántica del dominio

**Hito:** H2 · Convertir los hallazgos de H1 en las skills que el agente consulta.
**Fecha de la corrida:** 2026-09-06 · **Postgres:** 17.11 · **AS_OF:** 2026-06-01

Reproducible con:

```
.venv/bin/python scripts/validar_semantica.py            # las nueve, los 5 criterios
.venv/bin/python scripts/validar_semantica.py riesgo_alto  # una sola
.venv/bin/python scripts/valores_esperados.py           # regenera el insumo de H4
```

Las dos instituciones son las que devuelve `Q_FIXTURE`: hoy **3 `banco_andino`**
(174.669 clientes, umbral versionado 85, SLA 24 h, las dos perillas en `true`) y
**14 `fintech_cuyo`** (7.771 clientes, umbral 68, SLA 72 h, las dos perillas en
`false`). Los IDs son un resultado, no una constante.

> **Nota de método.** Antes de escribir una sola definición hubo una sesión de
> modelado que cerró el vocabulario (`CONTEXT.md`) y dos decisiones (D-12 y
> D-13). Fue la mitad más barata del hito y la que más cambió el resultado: dos
> de las nueve skills existen porque esa sesión encontró que una palabra nombraba
> dos poblaciones distintas.

---

## 1. Qué da cada definición alternativa

El entregable del hito. Para cada concepto: qué otras lecturas había, cuál quedó,
y **el número de cada una** en las dos instituciones. Sin esta tabla, elegir una
definición es una opinión.

### `riesgo_alto` — 7.859 · 321

| lectura | tenant 3 | tenant 14 |
|---|---:|---:|
| sólo `score >= umbral` | 5.399 | 240 |
| score **o** marca manual | 7.199 | 321 |
| **las tres fuentes (elegida)** | **7.859** | **321** |
| con el umbral **viejo** (80 en vez de 85) | 38.306 | — |

Tres cosas que se leen de acá:

- **Olvidar la marca manual pierde el 25 %** en las dos instituciones.
- **La perilla `pep_is_high_risk` vale +660 (9,2 %)** en el tenant 3. En el 14
  está apagada; si estuviera prendida sumaría +28 (8,7 %). Las dos ramas quedan
  ejercidas por el par.
- **Tomar la versión vieja del umbral multiplica por 4,9.** Es el error más caro
  del dataset y sólo se puede cometer en tres instituciones de cuarenta.

Y el que motivó **D-13**: según qué definición de PEP alimente el tercer escalón,
el total del tenant 3 va de **7.603 a 9.360** — un 23 % — sobre la pregunta de
referencia de H3. Por eso el escalón está congelado en *PEP vigente*.

### `pep_confirmado` — 660 · 28 (la única que queda abierta)

| lectura | tenant 3 | tenant 14 |
|---|---:|---:|
| `is_pep` sin mirar `result` — **descartada** | 10.237 | 440 |
| alguna vez `CONFIRMED_HIT` (histórico) | 2.161 | 95 |
| **su screening vigente es `CONFIRMED_HIT`** | **660** | **28** |

La descartada mete los 29.303 hits que el analista rechazó, que es literalmente
la trampa 7. Entre las otras dos hay un **3,3×** y las dos son defendibles: es el
mejor `NECESITO_QUE_ACLARES` del dataset y se decide con el eval.

**No se filtra por `is_pep`.** Nunca vale `false` —cuando no aplica, la clave
falta— y hay 5.698 hits confirmados sin el flag. Filtrarlo descarta PEPs reales
por un campo ausente, no PEPs falsos. Como la única lista de la data es `PEP_AR`,
un hit confirmado ya es un match de PEP por construcción.

### `hallazgo_real` — 5.404 · 159

| lectura | tenant 3 | tenant 14 |
|---|---:|---:|
| todas las alertas del trimestre | 13.333 | 591 |
| sólo `CLOSED_TRUE_POSITIVE` | 3.602 | 159 |
| **+ `ESCALATED` según la perilla (elegida)** | **5.404** | **159** |
| *el otro eje*: casos reportados a la UIF | *355* | *12* |

La fila en itálica es la que **no** es una alternativa de la misma escala: es otra
población, quince veces más chica, y **no se puede reconciliar** con la de arriba
porque el vínculo alerta↔caso no existe. Va por `caso_reportado` (D-12).

La perilla `escalated_counts_as_finding` vale **+50 %** en el tenant 3 y está
apagada en el 14: las dos ramas ejercidas.

### `alerta_fuera_de_sla` — 9.339 · 199

| mitad | tenant 3 (SLA 24 h) | tenant 14 (SLA 72 h) |
|---|---:|---:|
| sin revisar y ya vencidas | 4.499 | 199 |
| **revisadas tarde** | **4.840** | **0** |
| total | **9.339** | **199** |

**Omitir la segunda mitad pierde el 51,8 % de la respuesta en el tenant 3 y el
0 % en el 14.** Es exactamente el error que el criterio ampliado del fixture
existe para atrapar, y sin el tenant A de 24 h una golden query incompleta habría
dado verde en las dos instituciones.

### `cliente_onboardeado` — 18.001 · 799

| lectura | tenant 3 | tenant 14 |
|---|---:|---:|
| aprobados vivos, sin período | 107.250 | 4.759 |
| de ésos, con fecha de alta | 62.669 | 2.803 |
| **con fecha, dentro del período (elegida)** | **18.001** | **799** |

Los aprobados **sin** fecha de alta son 44.581 (41,6 %) y 1.956 (41,1 %),
consistente con el 41,9 % global de H1. La segunda lectura no es peor: es que no
responde una pregunta con período. Por eso es `RESPONDIDA_CON_SUPUESTO` y el
supuesto viaja con su número.

### `resolucion_de_casos` — 2,73 · 2,75 días

| | tenant 3 | tenant 14 |
|---|---:|---:|
| casos abiertos en el trimestre | 2.062 | 92 |
| de ésos, ya cerrados | 997 | 44 |
| **tiempo promedio de los cerrados** | **2,73 d** | **2,75 d** |
| de ésos, todavía abiertos | 1.065 | 48 |
| **antigüedad promedio de los abiertos** | **91,37 d** | **90,13 d** |

Acotado al trimestre, el contraste es **33×** — más marcado todavía que el 22×
que se ve sobre todos los casos. Y **ningún caso de la base tardó más de 5,00
días en cerrar**: no es una distribución cortada, son dos poblaciones. Un caso
cierra rápido o no cierra.

Por eso la antigüedad es un **escalón obligatorio** y no un dato de color: el
promedio de 2,73 días, solo, le dice a un oficial que los casos se resuelven en
menos de tres días, cuando la mitad de los del trimestre lleva tres meses abierta.

Las otras dos formas de contar, medidas por H1: contar los abiertos "hasta hoy"
da 9,6× más; contarlos como cero, casi la mitad. Las dos están mal por la misma
razón: un caso abierto no tiene tiempo de resolución.

### `monto_transado` — 31.436 · 1.284 operaciones liquidadas

El resultado **no es un escalar**: es una tabla.

| | tenant 3 | tenant 14 |
|---|---:|---:|
| ARS entrante | 11.747 ops · 11.747.000,00 | 485 ops · 485.000,00 |
| ARS saliente | 11.830 ops · 11.830.000,00 | 478 ops · 478.000,00 |
| USD entrante | 7.859 ops · 1.571.800,00 | 321 ops · 64.200,00 |

Contar todos los estados en vez de sólo los liquidados infla **un 25 %** en este
segmento (39.295 contra 31.436), bastante menos que el 66 % global — y eso es en
sí mismo un hallazgo, en la sección 2.

### `caso_reportado` — 355 · 12

Concepto nuevo (D-12). La decisión propia de esta skill es **cuál fecha ubica el
caso en el período**:

| fecha | tenant 3 |
|---|---:|
| `sar_reports.reported_date` — **elegida** | **355** |
| `cases.opened_at` | 247 |

"Cuántos casos **reportamos** este trimestre" pregunta por la fecha del reporte.
Usar la de apertura contesta otra cosa —cuántos de los casos abiertos en el
trimestre terminaron reportados— y da un 30 % menos.

### `misma_persona` — 307 · 17 documentos repetidos

| | tenant 3 | tenant 14 |
|---|---:|---:|
| legajos duplicados **sin** normalizar | 90 | 5 |
| legajos duplicados **normalizando** | 327 | 20 |
| documentos que se repiten | **307** | **17** |
| legajos involucrados | 634 | 37 |

**Normalizar multiplica por 3,6 y por 4** lo que se detecta: es el número que
justifica D-09. La cascada de esta skill cambia de unidad entre escalones
—legajos, documentos, legajos— y por eso no se lee como una resta.

---

## 2. Lo que apareció escribiendo las skills, y no estaba en H1

Cuatro cosas. Las dos primeras cambian consultas; la tercera cambia una
respuesta; la cuarta es una herramienta.

### 2.1 Los clientes de riesgo alto tienen transacciones sintéticas

Los importes del segmento de riesgo alto no son datos plausibles: son un patrón.

| segmento | moneda · sentido | operaciones | montos distintos | rango |
|---|---|---:|---:|---|
| resto | ARS entrante | 153.110 | 129.663 | 1,02 – 4.999,91 |
| resto | ARS saliente | 153.356 | 129.685 | 1,00 – 4.999,95 |
| resto | las otras 6 combinaciones | ~50 k c/u | ~48 k | 1,05 – 5.000,00 |
| **riesgo alto** | ARS entrante | 10.753 | **1** | **1.000,00** |
| **riesgo alto** | ARS saliente | 10.844 | **1** | **1.000,00** |
| **riesgo alto** | USD entrante | 7.199 | **1** | **200,00** |

Tres consecuencias:

1. **El desglose no tiene ocho filas fijas, tiene tres.** El segmento no opera en
   EUR ni en USDT ni tiene USD saliente. Cuántas filas trae la respuesta sale de
   la data, no de una lista escrita — la misma regla que D-07 ya pide para las
   exclusiones declaradas.
2. **Hay una reconciliación gratis**: las operaciones USD entrantes son
   *exactamente* tantas como clientes de riesgo alto (7.859 y 321, contra los
   7.199 y 240 de la versión sin PEP). Una operación por cliente. Es el tipo de
   comprobación que un oficial puede hacer de un vistazo.
3. **La mezcla de estados del segmento es distinta**: el 80 % está liquidado,
   contra el 60 % de la base. Por eso excluir revertidas y pendientes acá cuesta
   un 25 % y no el 66 % global. El número general de H1 no aplica a un segmento.

Es un patrón de **estructuración** —importes repetidos y redondos, por debajo de
cualquier umbral de reporte— y está bien que el generador lo haya plantado. Lo
anoto porque una respuesta de monto sobre este segmento *parece* un error de
join la primera vez que se la ve, y no lo es.

### 2.2 `AS MATERIALIZED` no es cosmético: es la diferencia entre 100 ms y el timeout

El desglose de `monto_transado` **moría por `statement_timeout` en la
institución chica**, la de 7.771 clientes. El plan explicaba por qué: Postgres
inlinea un CTE referenciado una sola vez, y el `DISTINCT ON` del screening
vigente terminó como lado interno de un `Nested Loop`, **recalculado una vez por
fila del loop externo**:

```
Nested Loop Left Join
  Join Filter: (screenings.client_id = c.id)
  ->  Unique  (cost=1.77..46288.28 rows=33555)
        ->  Incremental Sort  ...
              ->  Index Scan using idx_screenings_tenant_client
```

Con `AS MATERIALIZED` el mismo desglose corre en **10 ms**, y la golden grande
bajó de 4.121 a 1.337 ms. Va anotado como trampa en las tres skills que arman el
screening vigente.

Lo que esto significa para H3 es más grande que la corrección: **el gate de D-06
no lo habría atrapado.** No hay ningún `Seq Scan` en ese plan — es un índice,
usado pésimo. El gate mira el tipo de nodo y el tamaño de la tabla; acá el
problema es el *costo estimado*, que era 46.288 en el lado interno. Es la tercera
razón independiente para que el gate mire costo y no forma, después de las dos de
`NOTES/01`.

### 2.3 La bimodalidad de los casos es peor acotada al trimestre

H1 midió 2,71 días contra 60,82 sobre todos los casos (22×). Acotado a los
abiertos en el trimestre da **2,73 contra 91,37: 33×**. Y el techo es duro:
**ningún caso de toda la base tardó más de 5,00 días en cerrar.**

El techo vale para **los 21.430 casos cerrados de toda la base**, no sólo para el
par de trabajo. Eso descarta la lectura de "censura estadística" —no es que los
casos largos sigan corriendo— y deja una sola: hay dos poblaciones distintas. Es lo que
convierte la antigüedad de los abiertos en un escalón y no en una nota al pie.

### 2.4 El criterio 5 se podía automatizar, y el primer intento marcaba al revés

El mini-plan daba por sentado que "excluir soft-deletes en todas las tablas del
join" se revisa leyendo. Se puede chequear, con una condición: **el filtro se
busca atado al alias de cada tabla, no por cercanía al nombre.**

El primer chequeo, escrito por cercanía de texto, marcó como rotas **siete de las
nueve** golden queries. Todas estaban bien. En una consulta de cascada el filtro
vive dentro de un `FILTER (WHERE vivo)` que aparece *antes* del `FROM`, porque el
primer escalón tiene que contar las borradas para poder decir cuántas se
excluyeron. Un chequeo por cercanía marca en falso justo a las consultas mejor
escritas — y la tentación, en ese momento, es "arreglar" la consulta.

Quedó una convención que lo hace exacto: **todo filtro de borrado se escribe
calificado** (`s.deleted_at IS NULL`, nunca `deleted_at IS NULL`). Cinco
consultas se reescribieron para cumplirla.

Probado rompiendo a propósito, que es el paso 5 de la heurística de
[`plan/testing.md`](../plan/testing.md): sacándole a `riesgo_alto` el
`ra.deleted_at IS NULL` —la trampa 13, la que deja entrar 103.146 evaluaciones
vivas de clientes borrados— el validador lo marca:

```
✗ golden_sql: sin filtro de borrado en risk_assessments (como ra)
```

---

## 3. Cómo quedó validada cada skill

Los cinco criterios, los cinco automatizados en
[`scripts/validar_semantica.py`](../scripts/validar_semantica.py). Corre con
`agent_ro` y bajo RLS **a propósito**: una golden query que anduviera como
`postgres` y muriera bajo la policy no sirve de nada.

| skill | tenant 3 | tenant 14 | plan | 2.º camino |
|---|---:|---:|---|---|
| `riesgo_alto` | 294 ms | 12 ms | índice | ✓ |
| `cliente_onboardeado` | 14 ms | 2 ms | índice | ✓ |
| `alerta_fuera_de_sla` | 22 ms | 3 ms | índice | ✓ |
| `hallazgo_real` | 8 ms | 1 ms | índice | ✓ |
| `caso_reportado` | 4 ms | 1 ms | índice | ✓ |
| `pep_confirmado` | 233 ms | 27 ms | índice | ✓ |
| `resolucion_de_casos` | 3 ms | 1 ms | índice | ✓ |
| `misma_persona` | 175 ms | 9 ms | índice | ✓ |
| `monto_transado` | 1.712 ms | 103 ms | índice | ✓ |

La última incluye su desglose (1.337 ms la cascada + 375 ms las tres cifras); las
demás son una sola consulta. La más cara usa el **11,4 % del presupuesto de
15 s**, en la institución grande — en línea con el ~1,6 s que `NOTES/01` había
estimado como techo real.

**El segundo camino no es una formalidad.** Cada skill trae un
`verificacion_sql` que llega al mismo número por otra forma —`EXISTS`
correlacionado contra `JOIN` + `FILTER`, función de ventana contra `DISTINCT ON`,
`IN` contra join, la lista de estados en un `ARRAY` contra un `FILTER` por
estado—. Los dieciocho pares coinciden. Es lo que hace creíble un número que
nadie puede contar a mano.

### Tamaño

La disciplina de Ramp, medida sobre **el texto que el agente lee** (todo menos el
SQL, que no compite por la atención del modelo de la misma manera):

```
caso_reportado 1.354 · misma_persona 1.604 · alerta_fuera_de_sla 1.620
cliente_onboardeado 1.641 · hallazgo_real 1.668 · resolucion_de_casos 1.760
riesgo_alto 1.925 · monto_transado 1.995 · pep_confirmado 2.019
```

Máximo 2.019 sobre un presupuesto de ~2.000. La primera versión llegaba a 3.106:
lo que se recortó no se perdió, está en la sección 1 de esta nota. Es la regla
del mini-plan aplicada — *si dudo, va a `NOTES/`, no a la skill*.

---

## 4. Los valores esperados de H4

[`evals/valores_esperados.yaml`](../evals/valores_esperados.yaml), con la cascada
completa de cada pregunta en las dos instituciones.

**No está escrito a mano, y es deliberado.** Un valor esperado transcrito se
desincroniza de su definición en silencio, y entonces el eval mide contra un
número viejo y da verde. Lo genera
[`scripts/valores_esperados.py`](../scripts/valores_esperados.py) desde las
mismas skills, y **corta si los dos caminos de una skill no coinciden**.

| pregunta | tenant 3 | tenant 14 |
|---|---:|---:|
| ¿Cuántos clientes onboardeamos este año? | 18.001 | 799 |
| ¿Cuántos clientes de riesgo alto tenemos? | 7.859 | 321 |
| ¿Monto de los de riesgo alto el último trimestre? | 3 cifras | 3 cifras |
| ¿Qué alertas están fuera del SLA? | 9.339 | 199 |
| ¿Cuántos hallazgos reales tuvimos el trimestre? | 5.404 | 159 |
| ¿Alguno de nuestros clientes es PEP? | 660 *(o 2.161)* | 28 *(o 95)* |
| ¿Tiempo promedio de resolución? | 2,73 d | 2,75 d |
| ¿Qué clientes son la misma persona? | 307 | 17 |
| ¿Cuántos casos reportamos a la UIF? | 355 | 12 |

La de PEP lleva los dos números a propósito: su valor esperado depende de la
decisión que todavía no está tomada, y el eval tiene que poder medir las dos.

---

## 5. Qué queda pendiente

| Hallazgo | Va a |
|---|---|
| **El gate de `EXPLAIN` tiene que mirar costo, no forma**: el plan que moría por timeout usaba índice y no tenía un solo `Seq Scan` (2.2) | H3 · gate de D-06 |
| **`monto_transado` no entra en el campo `valor` del contrato**: su respuesta es una tabla, no un escalar. O `valor` es nullable y la respuesta vive en `filas`, o el contrato le queda chico | H3.3 · contrato de salida |
| El resolvedor de períodos, con su test rojo. Hoy los literales viven en `scripts/validar_semantica.py` y hay que importarlos de ahí | H3.4 |
| La derivación de `misma_persona` cambia de unidad entre escalones y no se lee como una resta: la pantalla tiene que decirlo | H3.1 · mockup |
| Decidir `pep_confirmado` (vigente 660 contra histórico 2.161) | H4 · eval |
| Las preguntas incontestables ya identificadas en H1, más dos que confirmó H2: sanciones fuera de `PEP_AR`, y cruzar hallazgos con casos reportados | H4 · set de evals |
| `validar_semantica.py` es el candidato natural a `tests/test_semantica.py`: ya afirma lo observable y no toca el SQL generado por el agente | H3 · tests |
| El proyecto no tiene manifiesto de dependencias (`pyyaml` se instaló a mano en el venv) | H6 · entrega |

---

## Anexo · Correcciones que ameritan `DECISIONS.md`

Las dos grandes ya están escritas (D-12 y D-13). Quedan tres precisiones:

1. **D-06** — tercera razón independiente para que el gate mire costo: un plan
   por índice, sin `Seq Scan`, puede morir por timeout si un CTE inlineado se
   recalcula por fila (2.2).
2. **D-08** — se puede citar el número que lo justifica en este segmento: el
   desglose son tres cifras y no ocho, y cuántas son sale de la data.
3. **Trampa 6** — el 66 % de inflación por contar revertidas y pendientes es un
   número **global**; sobre el segmento de riesgo alto es 25 %, porque su mezcla
   de estados es distinta (2.1). Conviene que la trampa lo diga, porque el
   número global invita a usarlo como si aplicara a cualquier recorte.
