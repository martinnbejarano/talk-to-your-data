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

### Contestables — una por clase (~18)


| Clase                                         | Pregunta representante                                               |
| --------------------------------------------- | -------------------------------------------------------------------- |
| Conteo simple con período                     | "¿Cuántos clientes onboardeamos este año?"                           |
| Definición que depende de config por tenant   | "¿Cuántos clientes de riesgo alto tenemos?"                          |
| Definición con dos fuentes que se contradicen | Riesgo alto en el tenant donde la marca manual y el score divergen   |
| Agregación con desglose obligatorio           | "¿Monto transado por los de riesgo alto el último trimestre?"        |
| Ciclo de vida con exclusiones                 | "¿Cuántos hallazgos reales tuvimos el último trimestre?"             |
| Filtro sobre JSONB                            | "¿Alguno de nuestros clientes es PEP?"                               |
| Agregación con denominador parcial            | "¿Tiempo promedio de resolución de casos?"                           |
| Cálculo temporal contra config                | "¿Qué alertas están fuera del SLA?"                                  |
| Inferencia sin columna                        | "¿Qué clientes son probablemente la misma persona?"                  |
| Listado en vez de conteo                      | "Los 10 clientes con más transacciones"                              |
| Serie temporal agrupada | "Onboardings mes a mes este año"                                     |
| Cruce de dos definiciones                     | "Clientes de riesgo alto que además son PEP"                         |
| Período no canónico                           | "¿Cuántas alertas se abrieron en marzo?"                             |
| Sinónimo del dominio                          | "¿Cuántos clientes riesgosos hay?" — misma respuesta que la canónica |


Cada una lleva el valor esperado **calculado a mano en H2 con dos queries
independientes**, y un campo `detecta:` que nombra qué falla atrapa — el paso 4 de la
heurística aplicado al eval.

### Ambiguas — una por tipo de ambigüedad (~10)

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


### Incontestables — una por motivo (~8)


| Motivo                        | Representante                                      |
| ----------------------------- | -------------------------------------------------- |
| No existe la columna          | "¿Cuál es la rentabilidad por cliente?"            |
| No existe el dato de contexto | "¿Por qué se rechazó a este cliente?"              |
| Falta data de conversión      | "¿Cuál es el total transado en dólares?"           |
| Fuera del snapshot            | "¿Cuántos onboardeamos en julio de 2026?"          |
| **Fuera del tenant**          | "¿Cómo nos comparamos con Banco Sur?"              |
| Fuera de dominio              | "¿Cuál es el clima en Buenos Aires?"               |
| Predicción, no consulta       | "¿Cuántas alertas vamos a tener el mes que viene?" |


La de comparación entre tenants es la más importante del set: es el peor bug posible del
sistema, expresado como pregunta. Tiene que **negarse**, no devolver cero.

## Formato

`evals/questions.yaml` — table-driven legítimo: sólo varían input y output esperado, no
la lógica (regla 5 de [`testing.md`](testing.md)).

```yaml
- id: c-002
  clase: definicion_depende_de_config
  categoria: contestable
  tenant: banco_norte
  pregunta: "¿Cuántos clientes de riesgo alto tenemos?"
  estado_esperado: RESPONDIDA
  valor_esperado: 1847
  debe_mencionar: [riesgo_alto]
  detecta: "Que use el umbral vigente del tenant y no uno hardcodeado ni uno viejo"

- id: a-003
  clase: unidad_no_agregable
  categoria: ambigua
  tenant: banco_norte
  pregunta: "¿Cuánto transamos el último trimestre?"
  estado_esperado: [NECESITO_QUE_ACLARES, RESPONDIDA_CON_SUPUESTO]
  detecta: "Que no invente un tipo de cambio para sumar ARS con USD"
```

## Runner y métricas

`evals/run.py` corre el set y escribe `evals/reports/<fecha>.md`.


| Métrica                      | Por qué                                                                                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Acierto por categoría        | Es el criterio de aceptación, desagregado por tipo de pregunta                                                                                                                  |
| **Pass@1 y Pass^3**          | Cada pregunta se corre 3 veces. Ramp reporta que *"Claude a veces se equivocaba incluso con el mismo prompt dos veces"*: la consistencia es una métrica aparte de la corrección |
| Fugas cross-tenant           | **Tiene que ser 0.** Cualquier otro valor bloquea la entrega                                                                                                                    |
| Falsa ambigüedad             | Repreguntas sobre preguntas que eran claras. No es un criterio obvio, pero un sistema que repregunta todo el tiempo se abandona                                                 |
| Timeouts y rechazos del gate | Salud de las queries generadas                                                                                                                                                  |
| Latencia y tokens            | Costo real de una respuesta                                                                                                                                                     |


La corrección de las contestables es **comparación exacta del número**, no un juez LLM:
metería ruido justo donde queremos determinismo.

## Validar que el set mide algo

El paso 5 de la heurística —romper el código a mano y confirmar que el test falla—
aplicado al eval: rompemos una skill a propósito y verificamos que el set lo detecte. La tabla de mutaciones está en [`testing.md`](testing.md).

**Si una mutación no rompe ninguna pregunta, el set tiene un agujero.** Esto se corre una
sola vez, al cerrar el hito, y es lo que separa un eval que mide de uno que da verde.

## Definition of done

- [ ] ~36 preguntas, una por clase de equivalencia, cada una con su campo `detecta`.
- [ ] Valores esperados calculados con dos queries independientes.
- [ ] Runner que corre todo y escribe el reporte.
- [ ] Tabla de mutaciones corrida: **toda mutación rompe al menos una pregunta**.
- [ ] Primera medición registrada como línea de base en `DECISIONS.md`.
- [ ] Fugas cross-tenant = 0.

## Riesgos


| Riesgo                                                 | Mitigación                                                                        |
| ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Escribir preguntas que sé que mi sistema contesta bien | Ambiguas e incontestables se escriben **antes** de ver cómo responde el agente    |
| El valor esperado está mal y el sistema tenía razón    | Dos queries independientes por valor                                              |
| Inflar el set con variantes de la misma clase          | La columna `clase` es obligatoria: dos preguntas con la misma clase, una se borra |
| El set da verde y no mide nada                         | La tabla de mutaciones                                                            |


