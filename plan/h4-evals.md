# H4 · Set de evaluación

**Objetivo.** Tener un instrumento que diga si el sistema responde bien, y que sea
estable entre corridas. A partir de acá las decisiones se toman con números.



**Los evals no son los tests.** Ver [`testing.md`](testing.md) para la separación y para
las guidelines de código. Acá se mide un sistema no determinístico; allá, código.

## Diseño del set: clases de equivalencia, no cantidad

Aplicamos el paso 2 de la heurística de [`testing.md`](testing.md) —particionar los
inputs en clases de equivalencia donde el sistema se comporta idénticamente— y después el
paso 3, filtrar buscando razones para **no** escribir cada caso. Veinte variantes de "cuántos clientes de
riesgo alto tenemos" son una sola clase: aportan una observación, no veinte.

Cada pregunta del set existe porque **cubre una clase que ninguna otra cubre**.

### Contestables — una por clase (15)


| Clase                                    | Pregunta representante                                               |
| ---------------------------------------- | -------------------------------------------------------------------- |
| Conteo simple con período                | "¿Cuántos clientes onboardeamos este año?"                           |
| Umbral versionado por institución        | "¿Cuántos clientes de riesgo alto tenemos?" en el tenant versionado  |
| **Perilla apagada, misma pregunta**      | La misma, donde `pep_is_high_risk` está en `false`                   |
| Agregación con desglose obligatorio      | "¿Monto transado por los de riesgo alto el último trimestre?"        |
| Ciclo de vida con exclusiones            | "¿Cuántos hallazgos reales tuvimos el último trimestre?"             |
| **Perilla apagada, misma pregunta**      | La misma, donde `escalated_counts_as_finding` está en `false`        |
| Cálculo temporal contra config           | "¿Qué alertas están fuera del SLA?" con plazo corto                  |
| **Mitad vacía de la definición**         | La misma con plazo largo: "revisadas tarde" da cero y no es un error |
| Agregación con denominador parcial       | "¿Tiempo promedio de resolución de casos?"                           |
| Inferencia sin columna                   | "¿Qué clientes son probablemente la misma persona?"                  |
| Listado además del conteo                | "Mostrame los legajos repetidos, con su documento"                   |
| Concepto vecino que no es hallazgo       | "¿Cuántos casos reportamos a la UIF el último trimestre?"            |
| Sinónimo del dominio                     | "¿Cuántos clientes riesgosos hay?" — misma respuesta que la canónica |
| Reformulación sin la palabra del concepto| "¿Cuántas altas hubo en lo que va del año?"                          |
| Multiturno con historial                 | "¿Y cuántos reportamos a la UIF el último trimestre?"                |


Cada una lleva su valor esperado y un campo `detecta:` que nombra qué falla atrapa — el
paso 4 de la heurística aplicado al eval.

**Tres correcciones sobre lo que decía este documento antes de H4**, todas por lo que
midió H1:

1. *"Definición con dos fuentes que se contradicen"* **no es una clase**: la trampa 15
   resultó desmentida — hay **0 clientes** en la intersección de score y marca manual, en
   las 40 instituciones. No se contradicen, se suman. En su lugar entran las tres clases
   marcadas en negrita, que son la versión que sí existe del mismo riesgo: **una perilla
   que cambia la respuesta correcta en una institución y no en la otra**. Un sistema que
   hardcodeó el escalón acierta en una y falla en la otra, que es exactamente lo que un
   eval con una sola institución no puede ver.
2. **Ningún valor esperado se escribe a mano.** `evals/valores_esperados.yaml` tiene 18
   números generados por dos consultas independientes que tienen que coincidir o el script
   corta, y `questions.yaml` los **referencia**. La consecuencia es un recorte deliberado:
   quedaron afuera *listado top-10 con orden nuevo*, *serie mensual*, *cruce riesgo alto ∧
   PEP* y *"alertas de marzo"*, que exigirían goldens nuevas. Un set más chico y sostenido
   vale más que uno completo con números transcritos, que se desincronizan en silencio.
3. *"Filtro sobre JSONB · ¿Alguno de nuestros clientes es PEP?"* se mudó a **ambiguas**:
   D-13 dejó esa definición abierta a propósito para que la decida el eval, así que
   pedirle un número exacto sería pedirle que adivine cuál de las dos elegimos.

### Ambiguas — una por tipo de ambigüedad (8)

Dos lecturas razonables dan números distintos. El éxito es repreguntar o declarar el
supuesto, **no** acertar un número.


| Tipo de ambigüedad                | Representante                                                                                  |
| --------------------------------- | ---------------------------------------------------------------------------------------------- |
| Unidad imposible de agregar       | "¿Cuánto transamos el último trimestre?" (no hay FX)                                           |
| Universo indefinido               | "¿Cuántos clientes tenemos?" (¿todos? ¿aprobados? ¿activos?)                                   |
| Estado indefinido                 | "¿Cuántas alertas críticas hay abiertas?" (¿`OPEN` solo, o también `IN_REVIEW` y `ESCALATED`?) |
| Métrica indefinida                | "¿Cómo venimos este año?"                                                                      |
| Umbral de confirmación indefinido | "¿Cuántos PEPs tenemos?" (¿confirmados o potenciales?)                                         |
| Período relativo indefinido       | "¿Cómo estuvo el último mes?"                                                                  |


### Incontestables — una por motivo (10)


| Motivo                        | Representante                                      |
| ----------------------------- | -------------------------------------------------- |
| No existe la columna          | "¿Cuál es la rentabilidad por cliente?"            |
| No existe el dato de contexto | "¿Por qué se rechazó a este cliente?"              |
| Falta data de conversión      | "¿Cuál es el total transado en dólares?"           |
| Fuera del snapshot            | "¿Cuántos onboardeamos en julio de 2026?"          |
| **Fuera del tenant**          | "¿Cómo nos comparamos con Banco Sur?"              |
| Fuera de dominio              | "¿Cuál es el clima en Buenos Aires?"               |
| Predicción, no consulta       | "¿Cuántas alertas vamos a tener el mes que viene?" |


La de comparación entre instituciones es la más importante del set: es el peor bug posible
del sistema, expresado como pregunta. Tiene que **negarse**, no devolver cero.

Y va en dos versiones, porque son dos cosas distintas: la comparación (*"¿cómo nos
comparamos con Banco Sur?"*) y la consulta directa por la otra institución (*"¿cuántos
clientes de riesgo alto tiene Fintech Cuyo?"*). A las dos se les exige
`NO_SE_PUEDE_RESPONDER`.

**Esto contradice al prompt a propósito.** Hoy `agent/loop.py` le dice al modelo que si la
pregunta nombra otra institución conteste igual sobre la del selector y lo declare como
supuesto, y `tests/test_loop.py` verifica esa conducta. Esperamos que las dos preguntas
**fallen** en la línea de base: un eval que se acomoda a lo que el sistema ya hace no mide
nada. El arreglo —y revisar ese test— es trabajo de H5.

El aislamiento en sí no depende de esto: lo garantiza el RLS, y una consulta no puede traer
filas ajenas. Lo que mide la métrica de fuga es lo que el RLS no puede impedir, que el
modelo **escriba** un número que no consultó.

## Formato

`evals/questions.yaml` — table-driven legítimo: sólo varían input y output esperado, no
la lógica (regla 5 de [`testing.md`](testing.md)). `valor_esperado` es una **referencia** a
`valores_esperados.yaml`, no un número: el runner lo resuelve.

```yaml
- id: c-002
  clase: umbral_versionado_por_institucion
  categoria: contestable
  institucion: banco_andino
  pregunta: "¿Cuántos clientes de riesgo alto tenemos?"
  estado_esperado: [RESPONDIDA, RESPONDIDA_CON_SUPUESTO]
  valor_esperado: {concepto: riesgo_alto}
  exige_derivacion: true
  debe_mencionar: [riesgo_alto]
  detecta: "Que use el umbral vigente y no el viejo: la versión vieja infla 9,6 veces"

- id: a-001
  clase: unidad_no_agregable
  categoria: ambigua
  institucion: banco_andino
  pregunta: "¿Cuánto transamos el último trimestre?"
  estado_esperado: [NECESITO_QUE_ACLARES, RESPONDIDA_CON_SUPUESTO]
  detecta: "Que no invente un tipo de cambio para sumar ARS con USD"
```

Las instituciones de trabajo son **`banco_andino` (id 3)** y **`fintech_cuyo` (id 14)**, el
par que eligió H1 sobre los datos. El id no se escribe en el set: sale de
`valores_esperados.yaml`, que lo dejó junto a los números de cada una.

## Runner y métricas

`evals/run.py` corre el set y escribe `evals/reports/<fecha>.md` —el que se lee, y el que
cita el README de H6— junto a un `.json` con los datos crudos, para que H5 calcule deltas
sin reparsear markdown.

```
.venv/bin/python evals/run.py --corridas 3 --workers 4
.venv/bin/python evals/run.py --solo c-002,ambigua      # un subconjunto
.venv/bin/python evals/run.py --mutacion umbral_viejo   # validar el set
.venv/bin/python evals/run.py --sin-skills              # la ablación de H5
```

Entra por `responder(...)` y no por HTTP: medir la API sería medir una copia del sistema.
La instrumentación no se estima, se lee de la traza, que ya la produce el loop.


| Métrica                      | Por qué                                                                                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Acierto por categoría        | Es el criterio de aceptación, desagregado por tipo de pregunta                                                                                                                  |
| **Pass@1 y Pass^3**          | Cada pregunta se corre 3 veces. Ramp reporta que *"Claude a veces se equivocaba incluso con el mismo prompt dos veces"*: la consistencia es una métrica aparte de la corrección |
| Fugas cross-tenant           | **Tiene que ser 0.** Cualquier otro valor bloquea la entrega                                                                                                                    |
| Falsa ambigüedad             | Repreguntas sobre preguntas que eran claras. No es un criterio obvio, pero un sistema que repregunta todo el tiempo se abandona                                                 |
| Timeouts y rechazos del gate | Salud de las queries generadas                                                                                                                                                  |
| Latencia y tokens            | Costo real de una respuesta                                                                                                                                                     |


La corrección de las contestables es **comparación exacta del número**, no un juez LLM:
metería ruido justo donde queremos determinismo. Y no alcanza con el número: si la pregunta
lo pide, se comparan **todos los escalones de la cascada**. Dos caminos distintos llegan a
7.859 y sólo uno se puede explicar.

Cada falla se clasifica además en la taxonomía de [`h5-iteracion.md`](h5-iteracion.md)
—definición equivocada, skill no consultada, SQL ineficiente, ambigüedad no detectada,
falsa ambigüedad, incontestable respondida, número no trazable—, leyéndola de la traza. No
es un adorno del reporte: es lo que dice **dónde** se arregla cada cosa, y H5 empieza
atacando la fila más alta.

## Validar que el set mide algo

El paso 5 de la heurística —romper el código a mano y confirmar que el test falla—
aplicado al eval: rompemos una skill a propósito y verificamos que el set lo detecte. La
tabla de mutaciones está en [`testing.md`](testing.md) y vive en `evals/mutaciones.py`.

Se aplican **en memoria** sobre el diccionario de skills que el agente lee, y se deshacen
al salir: una mutación que edita `core/semantics/` es una que alguien se olvida de
revertir. Cada una declara a qué preguntas apunta y corre **sólo esas** — el set entero seis
veces costaría veinte dólares para contestar una pregunta de sí o no.

**Si una mutación no rompe ninguna pregunta, el set tiene un agujero.** Esto se corre una
sola vez, al cerrar el hito, y es lo que separa un eval que mide de uno que da verde.

## Definition of done

- [x] 33 preguntas, una por clase de equivalencia, cada una con su campo `detecta`.
- [x] Ningún valor esperado escrito a mano: todos referencian los 18 números que H2
  calculó por dos caminos independientes.
- [x] Runner que corre todo, califica, clasifica las fallas y escribe el reporte.
- [x] Tabla de mutaciones corrida. **Dos de seis atrapadas**, y las otras cuatro con su
  causa nombrada: dos resultaron inertes —el modelo reconstruye esas reglas sin el
  fragmento de SQL mutado, y con `--sin-skills` las mismas preguntas fallan— y dos quedaron
  sin custodia porque sus preguntas ya estaban rojas. **Se vuelven a correr al cerrar H5**
  (D-15).
- [x] Primera medición registrada como línea de base en `DECISIONS.md` (D-14).
- [x] Fugas cross-tenant = 0.

## Riesgos


| Riesgo                                                 | Mitigación                                                                        |
| ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Escribir preguntas que sé que mi sistema contesta bien | Ambiguas e incontestables se escriben **antes** de ver cómo responde el agente. Las dos de institución ajena se escriben contra lo que el prompt hoy hace, no a favor |
| El valor esperado está mal y el sistema tenía razón    | Dos queries independientes por valor                                              |
| Inflar el set con variantes de la misma clase          | La columna `clase` es obligatoria: dos preguntas con la misma clase, una se borra |
| El set da verde y no mide nada                         | La tabla de mutaciones                                                            |


