# Testing · cómo escribimos los tests

Documento transversal: aplica a todos los hitos, no a uno.

Escribir tests con un agente de código sale barato, y ese es el problema: por defecto
salen muchos tests que no son particularmente buenos. Mocks de más, detectores de cambio
que rompen ante cualquier refactor, y ninguna decisión sobre qué vale la pena testear.

La máxima que seguimos es la de Guillermo Rauch: **"Write tests. Not too many. Mostly
integration"**. Cuanto más se mockea, menos se sabe sobre cómo interactúan las piezas
de verdad.

## Dos instrumentos distintos, que no hay que confundir

| | Tests (`tests/`) | Evals (`evals/`) |
|---|---|---|
| Qué prueban | Código determinístico | El agente, que no es determinístico |
| Resultado | Pasa o falla | Distribución: Pass@1, Pass^3 |
| Costo | Milisegundos | Tokens y minutos |
| Cuándo corren | En cada cambio | Por hito |

Mezclarlos produce dos errores típicos: tests *flaky* que dependen del humor del LLM, y
evals binarios que esconden la inconsistencia entre corridas.

## Reglas adoptadas

1. **Nunca mockear el storage.** Todos los tests de datos corren contra el Postgres real
   del `docker compose`. Es la regla que más aplica acá: nuestro sistema *es* la base.
   Un test de RLS contra un mock no prueba absolutamente nada.
2. **Mayormente integración.** Es el default, no la excepción. Un test unitario se
   justifica cuando la pieza es una función pura; si toca datos, es de integración.
3. **Tests cortos**, 30-45 líneas.
4. **Nada de change detectors.** Concretamente para este proyecto: **prohibido assertear
   el SQL exacto que generó el agente.** Ese test rompería con cada ajuste de prompt sin
   que el comportamiento haya cambiado. Se assertea lo observable: el número, el estado,
   las filas devueltas, el `tenant_id`.
5. **DAMP, no DRY.** Cada test se lee solo, aunque repita setup.
6. **Table-driven sólo cuando varía input/output**, no la lógica. El runner de evals
   califica: sólo cambian pregunta y respuesta esperada.

## Cómo se corre la suite

```
.venv/bin/pytest -m "not lento"   # ciclo rápido, ~2 s: es el de cada cambio
.venv/bin/pytest                  # completa, ~17 s: antes de cerrar un ticket
```

El marker `lento` está declarado en `pytest.ini` y hoy lo lleva un solo test: el que
espera los 15 segundos del `statement_timeout` para confirmar que muerde. Un test lento
no es un test de segunda —ése demuestra un límite de recursos real— pero tiene que poder
excluirse **sin** excluir los de aislamiento, que son los que tienen que sonar en cada
cambio. Marcar por lentitud y no por carpeta es lo que lo permite.

## Heurística para decidir qué testear

1. **Clasificar**: unitario (sin dependencias) · localizado (con storage real) ·
   integración (default).
2. **Particionar** los inputs en clases de equivalencia.
3. **Filtrar**: buscar razones para *no* escribir cada test.
4. **Nombrar**: qué cambio de código haría fallar este test.
5. **Validar a mano**: romper el código y confirmar que el test falla.

## Qué testeamos

Partición por clase de equivalencia, con el paso 4 explícito en cada fila:

| Clase | Tipo | Qué verifica | Qué cambio lo haría fallar |
|---|---|---|---|
| Aislamiento por tenant | Integración | Sin `app.tenant_id` → 0 filas; con → un solo tenant; escrituras denegadas | Sacar la policy de RLS o darle `BYPASSRLS` al rol |
| Gate de `EXPLAIN` | Localizado | Rechaza **recorrer entera una tabla grande** (`reltuples >= 100k`, el corte de D-06), multi-statement y no-`SELECT`; acepta index scan, y también el seq scan sobre una tabla chica —para las cinco sin índice por `tenant_id` es el único plan posible y cuesta 55-170 ms | Aflojar el umbral de costo o sacar el chequeo de plan |
| Trazabilidad de números | Unitario | Toda cifra de la respuesta está en el trace | Permitir que el modelo calcule |
| Resolución de períodos | Unitario | "este año" → `[2026-01-01, 2026-06-01]`; "último trimestre" → `[2026-01-01, 2026-03-31]` | Usar `now()`, o dejar que `fiscal_year_start_month` corra el período |
| Golden queries | Integración | Cada una corre en los 2 tenants, bajo timeout, usando índice | Cambiar una definición sin actualizar su golden |
| Normalización de documento | Unitario | `20-12345678-9` y `20123456789` colapsan al mismo grupo | Sacar la normalización |
| Contrato de la API | Integración | `/ask` con tenant A y con tenant B dan resultados distintos y ninguno filtra al otro | Tomar el tenant del texto de la pregunta |

**Lo que NO testeamos con tests:** el prompt, el wording de la respuesta, el orden en que
el agente llama las tools. Eso es trabajo del eval. Un test sobre esas cosas es un change
detector con otro nombre.

## Validar el propio set de evals (paso 5 aplicado a H4)

El paso 5 —romper el código a mano y confirmar que el test falla— aplicado al eval:
rompemos una skill a propósito y confirmamos que el set lo detecta. Si una mutación no rompe ninguna
pregunta, **el set tiene un agujero**.

| Mutación deliberada | Debe romper |
|---|---|
| Sacar `deleted_at IS NULL` de `riesgo_alto` | El conteo de riesgo alto |
| Incluir `CLOSED_FALSE_POSITIVE` en `hallazgo_real` | Los hallazgos del trimestre |
| Tomar el `effective_from_date` más viejo en vez del vigente | Riesgo alto en el tenant con umbral versionado |
| Sumar montos entre monedas | La pregunta ambigua de monto total |
| Usar `now()` en lugar de `AS_OF` | Todas las preguntas con período |
| Contar `POTENTIAL_HIT` como PEP | La pregunta de PEPs |

Esta tabla se corre una vez, al cerrar H4. Es barata y es la única forma de saber si el
eval mide algo o simplemente da verde.
