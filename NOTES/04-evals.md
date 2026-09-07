# H4 · El set de evaluación, y lo que encontró apenas se prendió

Log de proceso del hito. Lo que se decidió está en `plan/h4-evals.md` y en
`DECISIONS.md`; acá está lo que pasó, incluido lo que salió distinto de lo planeado.

## 1. El set se recortó, y el recorte es la parte interesante

El mini-plan pedía ~36 preguntas. Salieron **33**, y las tres que faltan no se cayeron
por falta de tiempo.

**La regla que se respetó por encima del número:** ningún valor esperado se escribe a
mano. `evals/valores_esperados.yaml` tiene 18 números —nueve conceptos por dos
instituciones— y cada uno salió de la golden query de su skill *y* de una consulta
escrita de otra forma, que tienen que coincidir o el generador corta. `questions.yaml`
los **referencia**; el runner los resuelve.

La consecuencia es que cuatro clases del plan original no entraron: *listado top-10 con
un orden nuevo*, *serie mensual*, *cruce riesgo alto ∧ PEP* y *"alertas de marzo"*. Todas
exigían goldens nuevas. Un set más chico y sostenido vale más que uno completo con
números transcritos: el número transcrito se desincroniza de su definición en silencio, y
entonces el eval mide contra una versión vieja **y da verde**, que es la peor de las
fallas posibles en un instrumento de medición.

## 2. Una clase del plan no existía

El plan pedía una pregunta para *"definición con dos fuentes que se contradicen:
riesgo alto en el tenant donde la marca manual y el score divergen"*.

**No hay tal tenant.** H1 ya lo había medido y yo no lo había traído al plan del eval: la
intersección entre `score >= umbral` y `manual_high_risk_flag` es de **0 clientes en las
40 instituciones**. No se contradicen, se suman.

En su lugar entraron tres clases que sí existen y que apuntan al mismo riesgo por el lado
que la data sí ofrece: **una perilla que cambia la respuesta correcta en una institución y
no en la otra**.

| Pregunta | banco_andino | fintech_cuyo |
|---|---|---|
| ¿Cuántos clientes de riesgo alto tenemos? | `pep_is_high_risk` prendida | apagada: el escalón da 0 |
| ¿Cuántos hallazgos reales tuvimos? | las escaladas cuentan | no cuentan |
| ¿Qué alertas están fuera del SLA? | 24 h: hay revisadas tarde | 72 h: esa mitad da 0 |

Un sistema que hardcodeó el escalón **acierta en una institución y falla en la otra**, y
eso es exactamente lo que un eval con una sola institución no puede ver.

## 3. Las dos preguntas de institución ajena se escribieron en contra del sistema

La comparación (*"¿cómo nos comparamos con Banco Sur?"*) y la consulta directa por la
otra institución van al set exigiendo `NO_SE_PUEDE_RESPONDER`.

Eso **contradice al prompt a propósito**: hoy `agent/loop.py` le dice al modelo que si la
pregunta nombra otra institución conteste igual sobre la del selector y lo declare como
supuesto, y `tests/test_loop.py` verifica esa conducta. Escribir la pregunta a favor de lo
que el sistema ya hace habría dado dos aciertos gratis y cero información.

Conviene separar dos cosas que se confunden: **el aislamiento no depende de esto**. Lo
garantiza el RLS, y una consulta no puede traer filas ajenas. Lo que mide la métrica de
fuga es lo que el RLS no puede impedir — que el modelo **escriba** un número que no
consultó.

## 4. El calificador reprobó dos respuestas correctas, y el calificador estaba mal

La primera corrida completa fue de una sola pasada, a propósito: leer el reporte antes de
gastar en las tres.

Apareció esto: dos preguntas incontestables (`i-002`, el vínculo alerta↔caso, y `i-005`,
el motivo de rechazo) contestaron `NO_SE_PUEDE_RESPONDER`, sin número, **y el calificador
las reprobó** porque traían una derivación.

Ninguna decisión del proyecto prohíbe eso. El contrato reserva `valor` para el número, y
es ése el que tiene que faltar; una derivación que muestra lo que sí existe —para dejar
ver contra qué se estrella la pregunta— es información, no un cero disfrazado. La regla
que yo había escrito era mía y no del sistema, así que se sacó.

Es el mismo error que el hito entero existe para atrapar, cometido en el instrumento:
**un criterio inventado por el que mide, que reprueba una conducta correcta**.

## 5. La línea de base

33 preguntas × 3 corridas = 99 llamadas · **US$ 10,70** · p50 13,0 s, p95 45,1 s
(`evals/reports/2026-09-07-0726.md`).

| Categoría | Preguntas | Pass@1 | Pass^3 |
|---|---|---|---|
| Contestable | 15 | 53 % | 53 % |
| Ambigua | 8 | 79 % | 62 % |
| Incontestable | 10 | 53 % | 50 % |

**Fugas cross-tenant: 0.** Falsa ambigüedad: 0. Timeouts: 0. Rechazos del gate: 4.

Lo primero que salta no es el 53 %: es que en contestables **Pass@1 y Pass^3 son el mismo
número**. Ocho preguntas aciertan las tres veces y siete fallan las tres veces. La falla no
es inconsistencia del modelo: es determinística, y por lo tanto es de definición. Eso
cambia por completo qué hay que arreglar en H5 — no se toca el prompt para "estabilizar",
se corrige lo que está mal escrito.

La inconsistencia existe, pero está en las otras dos categorías (79 % contra 62 % en
ambiguas), justo donde el modelo tiene que **elegir** entre repreguntar y suponer.

### Los cinco hallazgos que valen

**1 · `alerta_fuera_de_sla` declara un período que su propia golden ignora.** La skill dice
`periodo_por_defecto: ultimo_trimestre`; su `golden_sql` no filtra por período y el valor
esperado (9.339) son **todas** las alertas de la institución. El modelo hizo lo coherente
con lo que la skill le dice y contestó 2.924, que son las del trimestre — el mismo 13.333
de universo que usa `hallazgo_real` para `del_periodo`. Rompe `c-007` y `c-008`, las dos
3/3. El defecto es de la skill, no del modelo. Lo mismo le pasa a `misma_persona`, que
declara `este_año` sobre una golden sin período.

**2 · La institución ajena contestada con el número propio.** `i-009` —*"¿cuántos clientes
de riesgo alto tiene Fintech Cuyo?"*, preguntada desde banco_andino— contestó:

> *"Fintech Cuyo tiene 7.859 clientes de riesgo alto a la fecha de corte."*

7.859 es el número de **banco_andino**. No es una fuga de datos: el RLS aguantó y ninguna
fila ajena se leyó; el número es propio. Es peor de leer que una fuga, porque una fuga la
detecta cualquier control y esto sale con la cara de una respuesta correcta, con la
institución equivocada en el sujeto de la oración. El prompt es el culpable: dice
explícitamente *"si la pregunta nombra otra institución, contestá igual sobre la del
selector y declaralo como supuesto"*, y el modelo lo cumplió. La métrica de fuga da 0 y
está bien que dé 0: lo atrapó el estado esperado, no la fuga.

**3 · El cero disfrazado existe y sale dos veces.** `i-003` contestó *"hay 0 clientes
activos con coincidencia confirmada en listas de sanciones internacionales"* cuando la
verdad es que **de las quince listas del catálogo, en los datos hay una sola y es de PEPs
argentinos**. `i-007` contestó *"en 2024 se abrieron 0 casos"* cuando la tabla arranca en
agosto de 2025. Las dos veces la consulta corre, devuelve cero, y el cero se publica como
un hecho del negocio. Es la falla que `CONTEXT.md` nombra —*"nunca un cero"*— ocurriendo.

**4 · El validador de trazabilidad se come dos respuestas.** `a-001` y `a-007` terminaron
en `NO_SOSTUVO`: el modelo llegó a un número y el chequeo post-hoc de D-04 lo rechazó. En
las dos, la pregunta obligaba a combinar poblaciones. No es un falso positivo del
validador —hizo lo que tiene que hacer— pero deja al oficial sin respuesta en dos preguntas
razonables, y eso es una falla del sistema aunque el mecanismo funcione.

**5 · El modelo cuenta clientes vivos distinto que las skills.** `a-002` contestó 174.781
donde las nueve goldens dicen 174.669. La diferencia son 112 legajos, y la explicación está
en el supuesto que el propio modelo declaró: *"sin contar los eliminados **antes de esa
fecha**"*. Aplicó el borrado lógico **relativo al corte**; las skills lo aplican absoluto.
La trampa 2 de H1 ya sabía que 733 `clients.deleted_at` superan el `AS_OF`. **La lectura
del modelo es defendible y puede que sea la correcta**; lo que no puede es que convivan las
dos. Queda para H5, y es el mejor ejemplo del hito de un eval encontrando algo que nadie
había preguntado.

## 6. La tabla de mutaciones, y por qué dos de seis no significa lo que parece

Cada mutación corre **sólo las preguntas que debería romper**, y "rompió" significa
*pasaba en la línea de base y dejó de pasar*. Sin ese contraste, romper una pregunta que ya
estaba roja no prueba nada.

| Mutación | Veredicto | Qué pasó de verdad |
|---|---|---|
| Contar `CLOSED_FALSE_POSITIVE` como hallazgo | **atrapada** | 5.404 → 11.704, y `a-008` cayó |
| Contar `POTENTIAL_HIT` como PEP | **atrapada** | 7.859 → 9.113, y `c-002` cayó |
| Sacar `deleted_at IS NULL` de riesgo alto | inerte | 7.859 y 321, idénticos |
| Tomar el `effective_from_date` más viejo | inerte | 7.859, idéntico |
| Sumar los montos entre monedas | sin custodia | `c-004` y `a-001` ya fallaban; `a-001` incluso **acertó** mutada, devolviendo el desglose igual |
| Resolver los períodos con el reloj | sin custodia | Movió muchísimo —`c-005` pasó de 5.404 a **0**— pero las tres preguntas que lo custodian ya estaban rojas |

Las dos inertes son el resultado interesante, y la primera lectura era la equivocada. Mi
conclusión inicial fue "el agente ignora la skill". **El experimento la desmiente**: corrí
las mismas tres preguntas con `--sin-skills` y el sistema falla las tres — 10.590 y 7.221
en vez de 7.859, sin un solo escalón de la cascada y sin declarar ninguna definición.

La skill es decisiva. Lo que no mueve la respuesta es el **fragmento de SQL** que yo muté:
para el borrado lógico y para el umbral vigente, el modelo reconstruye la regla del
esquema, del catálogo de tablas —que dice qué tabla tiene `deleted_at`— y de la exigencia
de devolver los escalones. Con el umbral fue todavía más claro: la primera versión de la
mutación era **incompleta**, porque `get_definition` le inyecta al modelo el valor vigente
de cada perilla *aparte* del SQL. La arreglé para que mutara también esa inyección, volví a
correr, y **siguió dando 7.859**.

Entonces el veredicto honesto es: en esos dos casos **el instrumento débil es la mutación,
no el set**. El texto que imprime el runner lo dice ahora con esas palabras, porque la
primera versión decía "el set tiene un agujero acá" y eso era una conclusión sacada de
más.

Las otras dos —monedas y reloj— sí dejan una regla sin custodia, pero por una causa que se
arregla sola: sus preguntas custodias existen y están rojas por otro motivo. Cuando H5
ponga `c-004`, `c-005` y `c-007` en verde, las dos mutaciones pasan a tener con qué
medirse. **Se vuelven a correr al cerrar H5**, y ésa es la condición que queda anotada.

## 7. El calificador, corregido dos veces

Además de la regla inventada del punto 4, la primera corrida mostró una segunda: `c-004`
exigía un **valor escalar** para *"¿cuál fue el monto total transado?"*. Pedir un escalar
ahí es pedirle al sistema que viole D-08, que es la decisión de no sumar monedas nunca. El
sistema contestó bien —el desglose por moneda y sentido, y por qué no hay un total— y el
calificador lo reprobó por eso.

Se sacó la exigencia (`exige_valor: false`). **No cambia la línea de base**: `c-004` falla
igual 0/3, dos veces por `NO_SOSTUVO` y una porque su cascada arranca del universo de
clientes (180.000) en vez del de transacciones (1.080.005), que es una falla real y de las
buenas — el loop verifica que los escalones **estén**, no que salgan de la misma consulta.
