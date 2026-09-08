# Decisiones

## De qué se trata

Un sistema donde un oficial de compliance pregunta en castellano sobre los datos de su
institución y recibe una respuesta en la que pueda confiar.

Lo que ordena todo el diseño: hay **tres tipos de pregunta** y el sistema tiene que
manejar los tres.


| Tipo              | Qué es responder bien                               |
| ----------------- | --------------------------------------------------- |
| **Contestable**   | Dar el número correcto                              |
| **Ambigua**       | Repreguntar, o declarar el supuesto que se tomó     |
| **Incontestable** | Reconocer que la data no alcanza, y decir qué falta |


Dos de los tres modos de éxito consisten en **no** dar un número. Un sistema que siempre
contesta falla dos de tres.

---

## D-01 · El agente escribe SQL, no elige de un catálogo cerrado

**Qué decidimos.** El agente explora el esquema con herramientas y escribe sus propias
consultas, pero recibe **definiciones de negocio curadas** ("skills") para los conceptos
ambiguos del dominio.

**Por qué.** Un catálogo cerrado de métricas es preciso pero no responde nada que no
esté previsto. El SQL libre cubre cualquier pregunta pero inventa definiciones. No
compiten en el mismo eje: el catálogo resuelve *qué significa* "riesgo alto" en esta
institución; el SQL libre resuelve *cobertura*. Un agente con las dos cosas no está
limitado, está informado.

**Qué cuesta.** El riesgo se mueve de "no puede responder" a "puede responder mal". Las
decisiones D-02 a D-06 son las barandas que hacen que eso sea aceptable.

## D-02 · El aislamiento entre instituciones lo garantiza la base, no el prompt

**Qué decidimos.** RLS: cada conexión declara a qué institución pertenece, y las filas de las demás **directamente no existen** para esa
conexión. El usuario del agente es de sólo lectura.

**Por qué.** Cruzar datos entre instituciones es el peor error posible acá. Pedirle al
modelo que "no se olvide del filtro" no es una garantía. Con esta protección, aunque el
agente escriba una consulta sin filtro, sigue viendo únicamente lo suyo. Es lo que hace
posible D-01.

**Qué cuesta.** Hay que modificar la base restaurada con un script, y verificar que la
protección no degrade la velocidad de las consultas.

## D-03 · La institución se elige en la pantalla, nunca se deduce de la pregunta

**Qué decidimos.** Un selector visible y fijo, equivalente al login del oficial. Si la
pregunta menciona otra institución, el sistema se niega y lo explica.

**Por qué.** Un oficial pertenece a una sola institución. Dejar que la elección salga
del texto convertiría una pregunta en una forma de acceder a datos ajenos.

## D-04 · Todo número tiene que salir de una consulta ejecutada

**Qué decidimos.** El agente sólo puede afirmar valores que estén en el resultado de una
consulta de esa misma conversación. Cero aritmética del modelo: si hay que dividir o
promediar, se hace en SQL.

**Por qué.** El riesgo central de un sistema así es una cifra plausible que nunca salió
de la base. Esta regla lo vuelve imposible por construcción, y hace que cada respuesta
sea verificable contra su propia evidencia.

**Qué cuesta.** Más idas y vueltas (una consulta para el numerador, otra para el
denominador) en vez de calcular de memoria. Es más lento y vale la pena.

## D-05 · Cuatro estados de respuesta, sin porcentajes de confianza


| Estado                    | Cuándo                                                          |
| ------------------------- | --------------------------------------------------------------- |
| `RESPONDIDA`              | La pregunta es unívoca y la data alcanza                        |
| `RESPONDIDA_CON_SUPUESTO` | Hay ambigüedad, pero una lectura es claramente la más razonable |
| `NECESITO_QUE_ACLARES`    | Dos lecturas razonables dan números distintos                   |
| `NO_SE_PUEDE_RESPONDER`   | La data no contiene lo que se pide                              |


**Por qué.** Los cuatro estados son la traducción directa de los tres tipos de pregunta.
**No usamos un porcentaje de confianza**: los que genera un modelo no son confiables y
dan una falsa precisión. Una categoría obliga a una decisión con sentido; un "87%" no
significa nada accionable.

## D-06 · Se revisa el plan de la consulta antes de ejecutarla

**Qué decidimos.** Antes de correr una consulta se pide su plan de ejecución, y se
rechaza si va a recorrer una tabla grande entera. El motivo del rechazo vuelve al agente
para que reintente.

**"Tabla grande" es `reltuples >= 100k`**, el mismo corte que ya usan
[`tests/test_planes.py`](tests/test_planes.py) y [`tests/test_aislamiento.py`](tests/test_aislamiento.py), uno de cada lado. Debajo de ese
corte el recorrido completo es legítimo: las cinco tablas sin índice por `tenant_id`
no tienen otro plan posible y cuestan entre 55 y 170 ms (`NOTES/01-exploracion.md`).

**Por qué.** La base corta cualquier consulta a los 15 segundos. Esperar el corte le da
al agente una señal pobre y tarde; el plan le dice *por qué* estuvo mal, en
milisegundos. Es, además, como trabaja un analista de verdad.

**Qué cuesta.** Hay que pasarle al agente la lista de índices disponibles como parte del
contexto, para que escriba buenas consultas de entrada.

## D-07 · La pantalla tiene dos lectores: el oficial y nosotros

**Corrección.** La primera versión de esta decisión ponía el SQL en el centro del panel.
Queda corregida: un oficial de compliance no lee SQL, así que mostrárselo no lo habilita
ni a confiar ni a auditar. El SQL sigue estando, pero cambia de destinatario.

**La distinción, dicha de una vez:** *"auditoría"* en sentido técnico —SQL, plan de
ejecución, tiempos— **es para nosotros, IT** (o para el equipo de sistemas del cliente).
Todo lo demás está escrito para el oficial, que no es técnico.

**Qué decidimos.** Aplicación web: institución arriba, chat en el centro, panel al
costado. La confianza se apoya en siete piezas, ninguna de ellas el SQL:

1. **Derivación en cascada** — la cadena de números que lleva al resultado:
  ```
   Clientes de la institución            12.340
     activos (no dados de baja)          11.980   −360
     con evaluación de riesgo vigente    11.902    −78
     score ≥ 75 (umbral de tu config)       389
     + marcados manualmente como alto        42
     = riesgo alto                          431
  ```
2. **Ficha de criterios** con el origen del parámetro: de dónde salió el 75 y desde
 cuándo rige.
3. **Filas reales**, con detalle y exportación: "ver los 431 clientes".
4. **Cada cifra del texto es un enlace** al escalón y a las filas que la produjeron.
5. **Lo que quedó afuera**, explícito: *no incluye clientes dados de baja ni
 evaluaciones históricas*.
6. **Progreso paso a paso** mientras el agente trabaja.
7. **Detalle técnico plegado** — SQL, plan, tiempos. Rotulado como lo que es.

**Por qué.** Confiar y auditar no se resuelven leyendo una consulta. Se resuelven con
**derivación** (entiendo cómo se llegó) y **reconciliación** (verifico una muestra contra
lo que ya conozco): las dos operaciones que esta persona sí sabe hacer.

**Qué cuesta.** La respuesta del agente necesita traer la derivación estructurada, y cada
consulta de referencia tiene que declarar sus escalones.

**Descartado por ahora,** a `PRODUCT.md`: parámetros editables que recalculan en vivo,
el porcentaje sobre el universo, y verificar el mismo número por dos caminos distintos.

## D-08 · Los montos en monedas distintas no se suman

**Qué decidimos.** Toda suma de montos se devuelve **desglosada por moneda**. Nunca un
total único.

**Por qué.** No hay tabla de tipos de cambio. Sumar pesos con dólares sería inventar una
cotización. La respuesta correcta a "¿cuánto se transó?" no es un número: son cuatro.

**Qué cuesta.** Si alguien pide explícitamente el total en una sola moneda, la respuesta
es que no se puede, explicando qué falta.

## D-09 · Detectar clientes repetidos: sólo por documento

**Qué decidimos.** Agrupar por tipo y número de documento, normalizando guiones, puntos
y espacios. Sin comparación de emails ni de nombres parecidos.

**Por qué.** Cubre el problema que el propio diccionario señala (el formato del documento
no está normalizado), usa un índice existente, y es completamente explicable: el sistema
puede decir "el mismo CUIT escrito distinto", y eso lo audita cualquiera.

**Limitación asumida, y declarada en cada respuesta.** No detecta a la misma persona
cargada con DNI en un registro y CUIT en otro, ni variantes del nombre.

## D-10 · Construimos nuestro propio set de evaluación, y decide él

**Qué decidimos.** Un conjunto de preguntas de referencia en las tres categorías, con un
programa que las corre y reporta. Las decisiones discutibles del motor se resuelven
midiendo contra ese set, y el número queda registrado acá.

**Por qué.** Sin esto, "el agente anda bien" es una opinión. Ramp construyó un benchmark
de 237 tareas para decidir qué definiciones conservar; el mismo criterio aplica en chico.

## D-11 · Tests y evaluaciones son dos instrumentos distintos

**Qué decidimos.**

- `tests/` — código determinístico, mayormente de integración, **nunca con la base
simulada**. Prohibido verificar el SQL exacto que generó el agente: se rompería con
cada ajuste de texto sin que el comportamiento cambie. Se verifica lo observable: el
número, el estado, las filas, la institución.
- `evals/` — el agente, que no es determinístico. Se mide con distribución (cuántas veces
de tres acierta), no con pasa/falla.

**Por qué.** Cuanto más se simula, menos se sabe de cómo funcionan las piezas de verdad.
Acá es literal: el sistema **es** la base de datos.

**Qué cuesta.** Los tests necesitan la base restaurada para correr. Más lentos y mucho
más útiles. El detalle de cómo escribimos cada uno está en
[`plan/testing.md`](plan/testing.md).

## D-12 · "Hallazgo" nombra alertas; los casos reportados son otro concepto

**Qué decidimos.** `hallazgo_real` cuenta **alertas cerradas como verdadero positivo**
(más las escaladas, según la perilla del tenant). Los casos que terminaron en un reporte
a la UIF se responden con una skill propia, `caso_reportado`, que nunca usa la palabra
"hallazgo".

**Por qué.** H2 descubrió que la palabra nombra dos poblaciones y que difieren por
**quince**: en el tenant 3, ene–mar 2026, hay 3.602 alertas ciertas contra 247 casos
reportados. Elegimos el lado de las alertas porque es el único que la consigna define
—*"un falso positivo cerrado no es un hallazgo real"* habla del ciclo de vida de una
alerta— y porque *"¿cuántos hallazgos reales tuvimos?"* es una de las ocho preguntas que
el sistema tiene que saber contestar: repreguntar siempre ahí sería **falsa ambigüedad**,
que es una métrica que medimos y que hace que un sistema se abandone.

**Estado de la respuesta: `RESPONDIDA_CON_SUPUESTO`.** Y el supuesto son tres cosas, las
tres declaradas: (a) que cuenta alertas cerradas como verdadero positivo; (b) si las
escaladas entran, según `escalated_counts_as_finding`; (c) que **no** incluye los casos
reportados a la UIF, y que las dos poblaciones **no se pueden cruzar** porque el vínculo
alerta↔caso no existe en la base (trampa 10).

**Qué cuesta.** La respuesta más chica —los 247— nunca sale sola de esta pregunta. Sale
de la otra skill, que existe para eso.

## D-13 · Una perilla de configuración resuelve a una población determinística

**Qué decidimos.** Donde `pep_is_high_risk` está en `true`, el tercer escalón de riesgo
alto usa **PEP vigente** (el screening más reciente del cliente es un hit confirmado) y
esa definición queda **congelada**, aunque la pregunta directa *"¿tenemos PEPs?"* siga
abierta al eval (D-10).

**Por qué.** El escalón heredaba la ambigüedad de "PEP" y eso movía la pregunta de
referencia de H3 un 23 % — de 7.603 a 9.360 clientes en el tenant 3. Una perilla de
configuración de la institución tiene que resolver a una población determinística: **un
padrón de riesgo que depende de una repregunta no es un padrón.**

**Por qué esa definición y no `CONFIRMED_HIT AND is_pep`.** La única lista presente en
los datos es `PEP_AR`, así que un hit confirmado ya es un match de PEP por construcción.
Y `is_pep` nunca vale `false`: cuando no aplica, la clave falta — hay **5.698 hits
confirmados contra `PEP_AR` sin el flag**. Filtrar por esa clave descarta PEPs reales por
un campo ausente, no PEPs falsos.

**Consecuencia que hay que manejar.** En una misma sesión, el escalón de riesgo alto va a
usar 660 PEPs y la pregunta directa puede contestar 2.161. No es una inconsistencia, pero
lo parece: **la derivación tiene que declarar qué definición de PEP usó el escalón.**


## D-14 · La línea de base del eval, y qué cuenta como acierto

**Qué decidimos.** El set de 33 preguntas de `evals/questions.yaml` es el instrumento con
el que se decide si un cambio mejora el sistema. Su primera medición queda acá como línea
de base, y todo cambio de H5 se justifica contra ella.

**La medición.** 33 preguntas × 3 corridas, US$ 10,70, p50 13,0 s
(`evals/reports/2026-09-07-0726.md`).

| Categoría | Preguntas | Pass@1 | Pass^3 |
| --------- | --------- | ------ | ------ |
| Contestable | 15 | 53 % | 53 % |
| Ambigua | 8 | 79 % | 62 % |
| Incontestable | 10 | 53 % | 50 % |

**Fugas cross-tenant: 0**, que es la única métrica que bloquea la entrega. Falsa
ambigüedad: 0. Timeouts: 0.

**El dato que ordena H5.** En contestables Pass@1 y Pass^3 son **el mismo número**: ocho
preguntas aciertan las tres veces y siete fallan las tres veces. La falla es
determinística, así que es de definición y no de estabilidad. La inconsistencia real está
en las ambiguas (79 % contra 62 %), justo donde el modelo tiene que elegir entre
repreguntar y suponer.

**Tres decisiones de calificación que el set fija.**

- **Ningún valor esperado se escribe a mano.** `questions.yaml` referencia los 18 números
  de `valores_esperados.yaml`, que salieron de dos consultas independientes. Un número
  transcrito se desincroniza de su definición en silencio y el eval da verde midiendo
  contra una versión vieja.
- **No alcanza con el número: se compara la cascada entera.** Dos caminos distintos llegan
  a 7.859 y sólo uno se puede explicar.
- **Una pregunta por institución sólo cuando una perilla cambia la respuesta correcta.**
  Donde no cambia nada, la segunda institución no es una clase nueva.

**Las dos preguntas que se escribieron en contra del sistema.** Nombrar otra institución
tiene que dar `NO_SE_PUEDE_RESPONDER`, y el prompt de hoy dice lo contrario (contestar
sobre la propia declarándolo como supuesto). Fallan las dos, a propósito. La peor es
`i-009`, que contestó *"Fintech Cuyo tiene 7.859 clientes de riesgo alto"* — el número de
**banco_andino**. No es una fuga (el RLS aguantó y el número es propio), y por eso mismo es
más difícil de ver: sale con la cara de una respuesta correcta y la institución equivocada
en el sujeto. Arreglarlo, y revisar
`tests/test_loop.py::test_la_institucion_no_se_deduce_del_texto_aunque_la_pregunta_nombre_otra`,
es de H5.

**Qué cuesta.** Una corrida completa son US$ 10,70 y unos doce minutos con cuatro hilos.
Es el precio de que "anda mejor" sea un número y no una impresión.

## D-15 · Las mutaciones se corren contra la línea de base, y una mutación inerte no es un agujero del set

**Qué decidimos.** Una mutación "rompe" una pregunta sólo si esa pregunta **pasaba** antes
y deja de pasar. Y cuando ninguna cae, no se concluye que el set tenga un agujero sin
antes separar las dos causas posibles: que el set no custodie la regla, o que la mutación
no haya movido al sistema.

**Por qué.** De las seis mutaciones de [`plan/testing.md`](plan/testing.md), dos fueron
atrapadas y dos resultaron **inertes**: sacarle el `deleted_at IS NULL` a riesgo alto y
tomar el umbral versionado más viejo devolvieron 7.859, exactamente el número correcto. La
lectura fácil era "el agente ignora la skill". Correr esas mismas preguntas con
`--sin-skills` la desmiente: sin definiciones el sistema falla las tres, con 10.590 y 7.221
en vez de 7.859 y sin un solo escalón de la cascada.

La skill es decisiva; lo que no mueve la respuesta es el **fragmento de SQL** mutado. Para
el borrado lógico y para el umbral, el modelo reconstruye la regla del esquema, del
catálogo —que declara qué tabla tiene `deleted_at`— y de la exigencia de devolver los
escalones. Con el umbral hizo falta además descubrir que `get_definition` inyecta el valor
vigente de la perilla **aparte** del SQL: la primera versión de la mutación no lo tocaba y
por eso era incompleta. Corregida, el número siguió siendo 7.859.

**Qué queda pendiente.** Dos mutaciones —sumar monedas, y resolver períodos con el reloj—
no tienen hoy ninguna pregunta en verde que las custodie: sus preguntas existen y están
rojas por otro motivo. La del reloj movió muchísimo al sistema (`c-005` pasó de 5.404
hallazgos a **0**) sin que nadie la atrapara. **Las dos se vuelven a correr al cerrar H5**,
cuando `c-004`, `c-005` y `c-007` estén en verde.

## D-16 · El loop migró a `/v1/responses`; el modelo de H5 se quedó en `gpt-5.5`

**Qué decidimos.** Buscando bajar el costo de H5 se probaron `gpt-5.6-luna`,
`gpt-5-mini`, `gpt-5.6-terra` y `gpt-5.4-mini`. Ninguno ganó, y en el camino hubo que
migrar `agent/loop.py` y `agent/tools.py` de `/v1/chat/completions` a `/v1/responses`
—esa parte sí queda, es independiente del modelo.

**Por qué.** `gpt-5.6-luna` y `gpt-5.6-terra` no soportan tool calling con razonamiento en
`/v1/chat/completions` (error 400 explícito del proveedor); la migración a `/v1/responses`
los destrabó a los dos y no le cambió el comportamiento a `gpt-5.5` (regresión verificada
antes y después). Pero ninguno de los dos modelos baratos convino:

- `gpt-5.4-mini`: ambiguas cayó de 79 % a 12 % Pass@1 — el colapso justo en la categoría
  que más le importa al sistema (declarar supuestos, no inventar).
- `gpt-5.6-terra`: calidad igual o mejor que `gpt-5.5` (ambiguas 100 % en una corrida),
  pero **el costo real por llamada salió igual** (US$0,109 contra US$0,108), no el 2,5×
  más barato que sugiere el precio de lista — la hipótesis es que gasta más en tokens de
  razonamiento invisibles, compensando el precio por token más bajo.
- `gpt-5-mini` y `o4-mini` ni llegaron a medirse: el primero por verificación de
  organización pendiente en OpenAI, el segundo por un bug de schema en la tool
  `sample_values` (le falta `type` en `limite`, sin arreglar: no se llegó a usar).

**Qué cuesta esto.** Sólo la exploración de modelos costó **~US$8** antes de tocar un
solo bug del taxonomy loop — más que el baseline completo de H4.

## D-17 · Tres arreglos de H5, con su delta

Loop de un cambio a la vez sobre un **subconjunto de 13-26 preguntas**, no las 33
completas, por presupuesto. Cada arreglo se remidió aislado antes de seguir.

| Arreglo | Causa | Dónde | Delta aislado |
|---|---|---|---|
| Período mal declarado | `alerta_fuera_de_sla` y `misma_persona` declaraban `periodo_por_defecto` que su propio `golden_sql` ignora (finding #1 de H4) | Se sacó el campo de las dos skills | `c-007`, `c-008`: 0/1 → 1/1 |
| Institución ajena | El prompt decía "contestá con el número propio y declaralo como supuesto" | `agent/loop.py` (prompt) + `tests/test_loop.py` actualizado | `i-008`, `i-009`: → 1/1 |
| Cero disfrazado | Nada le decía al modelo cómo distinguir "no hay nada" de "no hay dato para este recorte" | Regla 7 nueva en el prompt: verificar catálogo completo o `MIN`/`MAX` antes de publicar un 0 | `i-003`, `i-007`: → 1/1 |
| `misma_persona` contesta el escalón equivocado | `get_definition` nunca mostraba el campo `resultado` — el modelo asume que la respuesta es el **último** escalón, y acá el último (`legajos_repetidos`, 634) no es el resultado (`personas_repetidas`, 307) | `get_definition` ahora marca explícitamente cuál escalón va en `valor` | `c-010`, `c-011`: → 1/1 |
| `monto_transado` arranca del universo equivocado | El modelo arrancaba la cascada de `clients` (180.000) en vez de `transactions` (1.080.005) — una regla general en el prompt no alcanzó, hizo falta explicitarlo en la skill misma | Trampa nueva + texto del escalón `total` en `monto_transado.yaml` | `c-004`: → 1/1 |

**Medición de cierre, 33×1 con los cinco arreglos puestos:**

| Categoría | D-14 (línea de base) | Cierre H5 |
|---|---|---|
| Contestable | 53 % | **80 %** |
| Ambigua | 79 % | **88 %** |
| Incontestable | 53 % | **90 %** |

## D-18 · Lo que la corrida de cierre mostró que las corridas aisladas no vieron

**Tres de los cinco arreglos volvieron a fallar en la corrida de cierre** —`c-004`
(mismo universo equivocado), `c-011` (esta vez sin traer el listado) e `i-003` (volvió a
publicar un número)— pese a haber pasado 1/1 en su remedición aislada. El agregado mejoró
mucho igual, pero esto confirma lo que D-14 ya advertía: **una corrida prueba que un
arreglo es posible, no que sea estable.** Ninguno de los cinco tiene Pass^3 real todavía.

**Apareció una falsa ambigüedad nueva** en `c-015` (repreguntó donde la línea de base no
lo hacía), que no estaba en ningún hallazgo anterior. Candidato sospechoso: la regla 7
(cero disfrazado) puede haber vuelto al modelo más cauteloso en general. Sin confirmar,
queda anotado para vigilar si se sigue iterando.

**Se encontró y arregló un bug de costo real, ajeno a todo lo anterior:** `sample_values`
no tenía tope ni en `limite` ni en el texto que arma para el modelo. Una corrida real pidió
una columna de alta cardinalidad con un límite alto y el resultado, unido en una sola
línea, llegó a **64 MB** — la API lo rechazó y la corrida completa (con 18 llamadas ya
pagas) se perdió. Arreglado con el mismo tope que ya usa `run_sql` (`FILAS_QUE_VE_EL_MODELO
= 50`).

**Ablación, parcial.** Sólo se ablacionaron los 4 conceptos que el subconjunto reducido
ejercitaba: `alerta_fuera_de_sla`, `riesgo_alto` y `cliente_onboardeado` sostienen solos
(2/2 cada uno); **`misma_persona` no sostenía ni estando solo (0/2)** — confirma que su
problema no era sólo el período, ya lo mostraba antes de encontrar el bug de `resultado`.
Quedan sin ablacionar `hallazgo_real`, `monto_transado`, `pep_confirmado`,
`caso_reportado` y `resolucion_de_casos`.

**Qué queda pendiente para cerrar H5 de verdad:**
- Pass^3 de los cinco arreglos (hoy sólo Pass^1).
- Ablación de las 5 skills que faltan.
- Correr `evals/questions_holdout.yaml` (6 preguntas, escritas y nunca corridas).
- Confirmar o descartar la falsa ambigüedad nueva de `c-015`.
- El DoD del plan (ambiguas/incontestables ≥ 90 % Pass^3, las 8 preguntas de referencia en
  Pass^3) no está verificado — sólo hay Pass^1 parcial.

**Costo total de la sesión: ~US$13,75.** Explorar modelos costó más que arreglar bugs.

## D-19 · El gráfico es la forma de una respuesta que ya era una serie

**Qué decidimos.** El campo `grafico` del contrato, reservado en H3 y en `null` desde
entonces, se llena **sólo cuando la respuesta es una serie** —altas por mes, alertas por
estado—. No es un adorno que se le agrega a una respuesta escalar: es la forma que toma
una respuesta que ya venía siendo una serie, y por eso va **arriba, con la oración**, con
su tabla desplegada debajo. Donde la respuesta es un número, no hay gráfico ni ofrecido.

Esto reabre lo que [`web/PRODUCT.md`](web/PRODUCT.md) tenía en *fuera de alcance*, y ese
archivo queda corregido.

**Quién decide qué.**

| Decisión | Quién |
| --- | --- |
| Si la respuesta es una serie, y qué columnas la forman (`x`, `y`, `unidad`) | El modelo |
| Barras o línea | El sistema, por el tipo del valor de `x`: temporal → línea, cualquier otra cosa → barras |
| Si el mapeo es dibujable | [`core/grafico.py`](core/grafico.py), determinístico: cualquier duda es `null` |
| Los números | La base. El modelo no escribe ni uno |

**El modelo escribe un mapeo, nunca un número.** `{x, y, unidad}` nombra columnas que la
consulta ya devolvió; los `puntos` los copia el sistema de las filas que volvió Postgres.
Inventar un punto no queda prohibido por una instrucción del prompt ni atrapado por un
validador: queda **estructuralmente imposible**, que es la misma estrategia con la que se
defiende D-04. `cifras_sin_respaldo` no necesita aprender a mirar el gráfico.

**Y tampoco elige el tipo.** Nadie que publique su heurística deja esa decisión en el
LLM: Metabase la deriva del tipo semántico de la columna del `Group by` —temporal →
línea, categoría → barras— y Vanna pasó de que el modelo escribiera el gráfico entero a
que la tool ni siquiera acepte un parámetro de tipo
([`NOTES/06-graficos-en-la-industria.md`](NOTES/06-graficos-en-la-industria.md) §1.1). Como el gráfico no se califica,
cada decisión que se le saca al modelo es una menos que nada mide.

**El gráfico entero cabe en un módulo puro.** La baranda no vive en `agent/loop.py` sino
en [`core/grafico.py`](core/grafico.py), por la misma razón por la que D-04 vive en
`core/trazabilidad.py` y no en el loop: es una propiedad que se verifica sobre datos, se
prueba sin API y sin Postgres, y no tiene por qué crecer adentro del ciclo de function
calling. Del loop se tocan cuatro líneas.

**Las seis reglas que lo hacen no mentir.**

- **Sólo hay gráfico si las filas vinieron enteras.** `filas.muestra` son cinco sobre
  `filas.total`: la tabla puede ser una muestra, el gráfico nunca. Doce barras tienen que
  significar doce meses y no "los doce que entraron". Por eso los puntos viajan en
  `grafico` y no se leen de `muestra`. Es un problema propio —nadie grafica sobre una
  muestra— y la única fuente que al menos declara el truncado en su contrato es Genie, con
  `query_result_metadata.is_truncated`.
- **Barras y línea. Sin torta.** Una torta afirma que las partes son el todo, y acá casi
  nunca lo son: están los dados de baja, los aprobados sin fecha de alta, lo pendiente y
  lo revertido.
- **Una sola unidad por serie, y la moneda nunca es el eje.** Es D-08 dibujado. Compartir
  el eje de valores es sumar visualmente lo que los números no suman. La versión anterior
  de esta regla pedía un panel por moneda, y estaba mal: si la única dimensión de la serie
  *es* la moneda, un panel por moneda son cuatro paneles de una barra cada uno. Se descarta
  una serie cuyo eje `x` son códigos de moneda, y también una donde **el valor horizontal
  se repite**: si hay dos filas por mes, la serie está partida por otra dimensión —moneda,
  sentido— y las barras apilarían unidades distintas. Esa segunda prueba reemplazó a una
  anterior, "exactamente dos columnas", que sonaba equivalente y no lo era: en este sistema
  lo normal es que el modelo devuelva los escalones de la cascada **y** la serie en una
  sola consulta, porque `_lo_que_falta` le exige los escalones igual. La primera corrida
  contra la API real la mató por eso, y no se descubrió con un test. Los paneles quedan
  para cuando haya una serie que los pida de verdad.
- **El eje de valores arranca siempre en cero.** Es la única forma de mentir que el mapeo
  por columnas no previene: todos los números verdaderos y la conclusión falsa. Para
  barras el consenso es unánime, y Vega-Lite lo fuerza ignorando la config; para líneas
  está discutido, y acá igual se aplica.
- **Tope de treinta puntos, y si se pasa no hay gráfico.** Doscientas barras no son un
  gráfico, son una textura. Y "otros" queda prohibido: esa suma la haría el front y no una
  consulta, que es D-04 dibujado.
- **El gráfico cede ante la derivación.** Una respuesta con serie necesitaría dos
  consultas —la cascada que `_lo_que_falta` exige con todos los escalones en una fila, y
  la agrupada—, contra un tope de doce pasos y un gate que rechaza justo la forma agrupada.
  Por eso el prompt es **pasivo**: no pide ninguna consulta de más, y el modelo sólo puede
  declarar `grafico` sobre una serie que ya ejecutó por su cuenta. **El gráfico nunca puede
  costar la respuesta.**

**Qué cuesta.**

- Agregar `grafico` al esquema estricto lo cambia para las 33 preguntas y no sólo para las
  que grafican. Se revalidó con una corrida 33×1 al cerrar el hito —**US$4,12**— comparada
  contra el cierre de H5 (D-17) y no contra la línea de base de D-14, que ya quedó atrás:
  contestable **93 %** (venía de 80), ambigua 88 % y incontestable 90 % **sin cambio**, y
  cero fugas cross-tenant. Los trece puntos de contestable no se cuentan como mérito de
  este hito —es una corrida contra otra, y D-18 ya mostró que eso no prueba estabilidad—;
  lo que la corrida sí prueba es que **no hubo regresión**, que era la pregunta.
- Una librería, en un front que hoy no tiene ninguna dependencia visual: **visx**, la
  única donde el peso escala con lo que se usa. Recharts eran 114 KB gzip por los mismos
  dos tipos de gráfico, y su v3 no bajó respecto de la v2 (`NOTES/06-graficos-en-la-industria.md` §5).
  **Medido en este bundle: 23 KB gzip** —66,1 → 89,1— con `scale`, `axis`, `shape` y
  `group`, algo menos que los 27 que estimaba la investigación. Va la **v4**: la v3 no
  declara React 19 como peer y npm se planta.
- Lo que **no** cuesta: el seam. Una versión anterior de este ADR daba por hecho que
  deducir barras o línea obligaba a que `Ok` llevara los tipos de columna de Postgres.
  Alcanza con mirar el valor de Python antes de serializarlo, así que
  `core/db/ejecucion.py` y sus tests quedan intactos.

**Qué queda sin medir, dicho para que no aparezca después.** El gráfico **no se
califica**: no hay assert sobre él en ninguna pregunta del set. Con la baranda, uno
imposible no llega a la pantalla; uno innecesario sí, y va arriba de todo. En producción no
lo evalúa nadie —LangSmith, Ragas, DeepEval, promptfoo, Genie y Cortex miden SQL o texto—,
pero en investigación sí, y nvBench 2.0 abandonó *accuracy* por P/R/F1@K porque más del
60 % de los casos son ambiguos: el mismo problema que ya ordena este repo.

**Ninguna de las 33 preguntas del set produce hoy una serie dibujable.** Las de monto son
desgloses por moneda, que es justo lo que la tercera regla prohíbe dibujar; "¿qué alertas
están fuera del SLA?" y "mostrame los legajos repetidos" son listas y no series. La primera
pregunta que enciende esto —`h-007`, altas por mes— va al **holdout**, para no mover un set
oficial que ya tiene su medición de cierre.

**Y una asimetría deliberada.** Si el oficial pide un gráfico para una pregunta que
contesta con un número, recibe el número y **ningún comentario sobre el gráfico**. Es la
única pieza de este ADR que va en contra de la postura del resto del sistema, que declara
siempre lo que no puede.

Lo que salió distinto al construirlo —dos reglas que sonaban bien y sólo se cayeron contra
la API real— está en [`NOTES/07-graficos.md`](NOTES/07-graficos.md).


---

## Trampas del dataset

Detectadas leyendo el diccionario, **antes** de tocar la base. H1 las midió una por
una contra la data real; el detalle y las consultas están en
[`NOTES/01-exploracion.md`](NOTES/01-exploracion.md) y `scripts/explore/`.


| #   | Trampa                                                                      | Estado                | Lo que dice la data                                                                                             |
| --- | --------------------------------------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| 1   | Las filas borradas siguen en la tabla                                       | **matizada**          | Sólo 4 de las 8 tablas con `deleted_at` tienen borradas. Pero los marcados como riesgo alto se borran 13× más que el promedio: el 37,5 % contra el 2,88 % |
| 2   | "Hoy" es el 1-jun-2026, no la fecha real                                    | **confirmada, con excepción** | El `AS_OF` es la fecha correcta, pero "no hay datos posteriores" es falso: 733 `clients.deleted_at` y 69.215 `client_documents.uploaded_at` lo superan |
| 3   | "Último trimestre" es calendario; el año fiscal del tenant es un distractor | **confirmada**        | `fiscal_year_start_month` toma 5 valores (1, 3, 4, 7, 10) y no redefine nada                                    |
| 4   | La configuración por institución está versionada en el tiempo               | **confirmada**        | Sólo 3 tenants de 40 la tienen versionada. Tomar la versión vieja infla **9,6×** (5.399 → 51.962)               |
| 5   | No hay tipos de cambio                                                      | **confirmada**        | Y los **40** tenants operan en las 4 monedas: no existe el caso mono-moneda                                     |
| 6   | Las transacciones revertidas no son movimiento efectivo                     | **confirmada**        | `REVERSED` es el 20,0 % y `PENDING` otro 19,9 %. Contar todo infla el volumen **66 %**                          |
| 7   | Un match descartado por el analista no es un PEP real                       | **confirmada y peor** | `is_pep` nunca vale `false` (falta la clave), hay 5.698 `CONFIRMED_HIT` contra `PEP_AR` **sin** el flag, y `screenings` está historizada **sin `is_current`**: el 69,5 % de los que alguna vez dieron hit hoy dan `NO_HIT` |
| 8   | Una alerta cerrada como falso positivo no es un hallazgo                    | **confirmada**        | `CLOSED_FALSE_POSITIVE` es el 34,8 %. Contar todas infla **2,3×**                                               |
| 9   | Un caso abierto no tiene tiempo de resolución: es N/A, no cero              | **confirmada**        | El 40 % está sin cerrar. El promedio va de 2,71 a 25,97 días según qué se haga con ellos: **9,6×**              |
| 10  | El vínculo entre alertas y casos no está donde parece                       | **desmentida: no existe** | `alerts.case_id` está 100 % en NULL y `alert_case_links.alert_id` es **una copia de `case_id`** en las 10.629 filas. Sólo "funciona" en el tenant 1, por superposición de rangos de id |
| 11  | El número de documento no está normalizado                                  | **confirmada**        | Dos formatos, mitad y mitad. Normalizar multiplica por **3,6** los duplicados detectados (327 contra 90)        |
| 12  | Un cliente aprobado puede no tener fecha de alta                            | **confirmada, y grande** | **307.444 de 733.551 aprobados (41,9 %)** no tienen `onboarded_at`                                           |
| 13  | Hay exactamente una evaluación de riesgo vigente por cliente                | **confirmada**        | 1 por cliente, sin excepciones. Pero borrar un cliente sólo borra su fila vigente: quedan 103.146 evaluaciones vivas de clientes borrados |
| 14  | Hay instituciones dadas de baja                                             | **confirmada**        | 2 de 40, las dos con datos y las dos con nombre casi homónimo de una activa                                     |
| 15  | El riesgo alto vive en dos lugares que pueden contradecirse                 | **desmentida: son disjuntos** | **0 clientes** en la intersección, en las 40 instituciones. No se contradicen: se suman. La marca manual aporta el 25 % del total |
| 16  | Hay tablas y valores que el diccionario no documenta                        | **confirmada**        | 9 tablas, 7 enums sin `CHECK`, y 3 claves de `tenant_config` — dos de ellas perillas de negocio que cambian respuestas enteras |


### Las tres tablas puente que parecen servir y no sirven

Hallazgo de H1 que no estaba previsto en ninguna trampa: **el esquema no tiene ni
una foreign key**, y eso separa las relaciones en dos grupos nítidos. Las ocho
documentadas están perfectas —cero huérfanos, cero cruces de institución, sobre
84 millones de filas—. Las dos tablas puente **no** documentadas están rotas:

| tabla | qué le pasa |
| ----- | ----------- |
| `alert_case_links` | `alert_id` es una copia de `case_id`. El vínculo alerta↔caso no existe |
| `transaction_counterparties` | `transaction_id` apunta al azar (acierta el 15,09 %, que es la cuota del tenant 1). Y encima es redundante: `transactions.counterparty_name` nunca es NULL |
| `client_risk_overrides` | Registra que hubo un override pero **no a qué valor**: no tiene columna de score ni de nivel. No puede definir riesgo |

Las tres tienen el nombre exacto de lo que uno busca. Son señuelos, y la respuesta
correcta a las preguntas que las necesitan es `NO_SE_PUEDE_RESPONDER`.

## Definiciones a fijar

Estado después de H1. Cuatro cerradas, dos abiertas a propósito.


| Concepto                | Estado             | Definición                                                                                                                                                                                        |
| ----------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Riesgo alto**         | ✅ cerrada          | `score >= umbral vigente al AS_OF` **o** `manual_high_risk_flag`, sobre clientes vivos con evaluación vigente viva; **más los PEP vigentes donde `pep_is_high_risk` está en `true`**. Las **tres** fuentes son disjuntas: la cascada suma sin nota al pie. El escalón PEP queda congelado por D-13 |
| **Resolución de casos** | ✅ cerrada          | `closed_at - opened_at` sólo sobre casos con `closed_at`, que son los de status `CLOSED` **y `REPORTED_UIF`** (los dos son terminales). La **antigüedad de los abiertos** es un escalón obligatorio de la derivación, no sólo su conteo |
| **Fuera de SLA**        | ✅ cerrada          | Dos poblaciones, las dos necesarias: sin revisar con `AS_OF - triggered_at > sla`, más revisadas con `first_reviewed_at - triggered_at > sla`. El plazo es `tenant_config.review_sla_hours`         |
| **Cliente onboardeado** | ⚠️ con supuesto    | `APPROVED` con `onboarded_at` en el período. Los 307.444 aprobados sin fecha quedan fuera y **hay que declararlo con el número**                                                                    |
| **Hallazgo real**       | ⚠️ con supuesto    | Alertas `CLOSED_TRUE_POSITIVE`, más las `ESCALATED` según `tenant_config.escalated_counts_as_finding` (+50 %). **No** incluye los casos reportados a la UIF, y las dos poblaciones no se pueden cruzar. Los tres supuestos se declaran (D-12) |
| **Caso reportado**      | ✅ cerrada          | Casos con status `REPORTED_UIF`. Concepto propio, uno a uno con `sar_reports`. Existe para que la pregunta se conteste directo sin pasar por la palabra "hallazgo" (D-12)                           |
| **PEP**                 | 🔓 abierta **sólo para la pregunta directa** | Descartada la lectura floja (`is_pep` sin mirar `result`). El eje que pesa es si vale el screening **vigente** o cualquiera de los 4-5 históricos (×3,3): en el tenant 3, 660 contra 2.161. Como escalón de riesgo alto ya está congelada en "vigente" (D-13) |


**Queda una sola abierta, y por una buena razón.** "PEP" tiene una ambigüedad real en la
data —el screening está historizado y no trae marcado cuál vale hoy— y es el mejor
candidato del dataset para ejercer `NECESITO_QUE_ACLARES`: *"¿te referís a los que hoy
figuran como PEP (660) o a los que alguna vez dieron positivo (2.161)?"* es una
repregunta que un oficial entiende y que cambia el número por tres. Se decide con el
eval (D-10).

Las otras dos que estaban abiertas se cerraron en H2 y **no** por decisión de escritorio:
"hallazgo real" resultó tener un segundo eje 15× más grande que el conocido (D-12), y el
escalón PEP de "riesgo alto" resultó heredar una ambigüedad que una perilla de
configuración no puede tener (D-13). Las dos siguen ejerciendo
`RESPONDIDA_CON_SUPUESTO`, que era lo que se quería preservar; lo que se descartó es que
ejercieran `NECESITO_QUE_ACLARES`, porque en las dos **repreguntar sería falsa
ambigüedad**: son preguntas del enunciado que el sistema tiene que saber contestar.

### Preguntas incontestables que la exploración ya identificó

Insumo directo del set de evaluación de H4:

- Cualquier recorrido alerta→caso o caso→alerta (trampa 10).
- Sanciones o listas que no sean `PEP_AR`: existen 15 `watchlists` y **una sola
  aparece en la data**, con exactamente un match por screening.
- A qué valor se overrideó el riesgo de un cliente (`client_risk_overrides`).
- Cualquier total en una sola moneda (D-08).
- Casos anteriores a agosto de 2025 o screenings anteriores a enero de 2025: cada
  tabla arranca en una fecha distinta, y la respuesta honesta no es "0" a secas.
- Unir un screening con su corrida (`screening_runs` no tiene cómo: no hay `run_id`).


---

## Referencias

- [Ramp · ramp-mcp](https://builders.ramp.com/post/ramp-mcp) — por qué conviene que el
modelo escriba SQL en vez de hacer cuentas, y por qué el límite de seguridad va fuera
de la consulta.
- [Ramp · How To Build Agents Users Can Trust](https://builders.ramp.com/post/how-to-build-agents-users-can-trust)  
y [LangChain · Breakout Agents: Ramp](https://www.langchain.com/breakoutagents/ramp) — el paso a paso con justificación, y el rechazo a los niveles de confianza generados por el modelo.

