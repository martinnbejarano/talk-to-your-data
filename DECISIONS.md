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
| **Riesgo alto**         | ⚠️ cerrada salvo la perilla | `score >= umbral vigente al AS_OF` **o** `manual_high_risk_flag`, sobre clientes vivos con evaluación vigente viva; **más los PEP vigentes donde `pep_is_high_risk` está en `true`**. Las **tres** fuentes son disjuntas: la cascada suma sin nota al pie |
| **Resolución de casos** | ✅ cerrada          | `closed_at - opened_at` sólo sobre casos con `closed_at`, que son los de status `CLOSED` **y `REPORTED_UIF`** (los dos son terminales). Se reporta cuántos quedan fuera                             |
| **Fuera de SLA**        | ✅ cerrada          | Dos poblaciones, las dos necesarias: sin revisar con `AS_OF - triggered_at > sla`, más revisadas con `first_reviewed_at - triggered_at > sla`. El plazo es `tenant_config.review_sla_hours`         |
| **Cliente onboardeado** | ⚠️ con supuesto    | `APPROVED` con `onboarded_at` en el período. Los 307.444 aprobados sin fecha quedan fuera y **hay que declararlo con el número**                                                                    |
| **Hallazgo real**       | 🔓 abierta          | `CLOSED_TRUE_POSITIVE` seguro. Las `ESCALATED` dependen de `tenant_config.escalated_counts_as_finding`, que existe y varía 20/20. La diferencia es **+50 %**                                        |
| **PEP**                 | 🔓 abierta          | Descartada la lectura floja (`is_pep` sin mirar `result`). Quedan cuatro sobre **dos ejes**: el flag `is_pep` (×1,7) y si vale el screening **vigente** o cualquiera de los 4-5 históricos (×3,3). En el tenant 3 va de 2.161 a 404 |


Las dos abiertas lo están por la misma razón: **las dos tienen una perilla en
`tenant_config` o una ambigüedad real en la data, y son los mejores candidatos del
dataset para ejercer los estados `RESPONDIDA_CON_SUPUESTO` y `NECESITO_QUE_ACLARES`.**
Cerrarlas a dedo ahora sería tirar los dos casos de prueba más valiosos que hay.
Se deciden con el eval (D-10).

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

