# 05 · Cuándo graficar, qué graficar, y cómo entregarlo

**Qué contesta esta nota.** `agent/loop.py` reserva un campo `grafico` en el `CONTRATO` y
hoy lo manda siempre en `null` ([`_completar`](../agent/loop.py)). Antes de llenarlo, qué
hacen los productos que ya resolvieron el problema, leído contra sus fuentes primarias.

**Fecha de la búsqueda:** 2026-09-07. Todo lo de acá sale de documentación oficial, código
fuente con SHA, o papers de los propios equipos. Donde no hay fuente primaria, lo digo.

**Esta nota no decide nada.** La última sección muestra qué caminos quedan abiertos y qué
cuesta cada uno, atado a los ADRs que ya existen.

---

## Lo que apareció, arriba de todo

Cinco cosas que no esperaba y que ordenan el resto:

1. **Casi nadie publica la heurística de "cuándo graficar".** Snowflake, Databricks,
   Microsoft, Amazon, OpenAI y Anthropic dicen alguna variante de *"elige el mejor
   visual"* y no bajan de ahí. Los **dos únicos** con la regla escrita y verificable son
   **Metabase** (árbol de decisión en código abierto **y** tabla en la doc) y **Vanna**
   (dos líneas de Python).

2. **La industria se movió de "el LLM elige el gráfico" a "una heurística elige el
   gráfico".** Vanna hizo exactamente ese viaje entre la v1 y la v2 y es el único caso con
   código de las dos épocas para compararlo.

3. **Snowflake Cortex Analyst —el producto más parecido a éste— no devuelve gráfico.**
   Devuelve SQL y el cliente ejecuta. El gráfico aparece recién en Cortex *Agents*, que es
   otro producto.

4. **Nadie previene graficar sobre una muestra truncada, porque nadie grafica sobre una
   muestra:** grafican el resultado completo. Es el hueco más grande para este repo, donde
   `filas.muestra` son 5 filas sobre `filas.total`.

5. **En producción no evalúa el gráfico absolutamente nadie.** Ni LangSmith, ni OpenAI
   Evals, ni Ragas, ni DeepEval, ni promptfoo, ni Genie, ni Cortex. Todos miden SQL,
   resultados o texto. En investigación sí, y bien, desde 2024.

---

## 1 · Quién decide que hay gráfico

Encontré cuatro respuestas distintas, y conviven en el mismo mercado.

### 1.1 · Heurística determinística sobre la forma del resultado

**Vanna v1** es el caso más chico y más citable. `should_generate_chart` es el método
entero ([`base.py#L254-L274`](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/base/base.py#L254-L274),
hoy sobreviviendo en `legacy/`):

```python
if len(df) > 1 and df.select_dtypes(include=['number']).shape[1] > 0:
    return True

return False
```

Dos condiciones: **más de una fila** y **al menos una columna numérica**. Sin LLM. El
docstring invita a pisarlo. La UI lo consume como flag: el server compone
`"should_generate_chart": self.chart and vn.should_generate_chart(df)`
([`flask/__init__.py#L518`](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/flask/__init__.py#L518))
y el front sólo entonces pide la figura.

**Metabase** es la versión adulta de lo mismo, y la única con la regla en la doc pública.
`defaultDisplay(query)` es un árbol de decisión sobre **cantidad de agregaciones × cantidad
de breakouts × tipo semántico de la columna**
([`display.ts#L13-L143`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/frontend/src/metabase-lib/query/display.ts#L13-L143)).
La doc lo publica como tabla, en
[data-modeling/semantic-types#visualizations](https://www.metabase.com/docs/latest/data-modeling/semantic-types#visualizations):

> "When you create a question in the query builder, Metabase will automatically choose the
> most suitable chart for you based on the data types and the semantic types of the field
> in the 'Group by' step."

| Group by | Gráfico |
| --- | --- |
| Text/Category | Bar |
| Temporal | Line |
| Numeric, binned | Bar |
| Numeric, sin binning | Table |
| Boolean | Bar |
| Sin agregación | Table |
| Latitude/Longitude binned · sin binning | Grid map · Pin map |
| Country · State | World region map · US region map |

Dos detalles que importan más que la tabla:

- **La decisión se toma sobre la consulta, no sobre las filas.** Y hay dos correcciones
  post-hoc sobre el resultado ya ejecutado: `maybeResetDisplay` y `_maybeSwitchToScalar`,
  que fuerza `scalar` si el resultado es **1 fila × 1 columna**
  ([`Question.ts#L265-L308`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/frontend/src/metabase-lib/v1/Question.ts#L265-L308)).
- **La cardinalidad casi nunca elige el *tipo* de gráfico: elige si el gráfico es
  legible.** En Metabase la única regla cardinalidad→tipo es `smart-row`, con umbral 10:
  hasta 10 valores distintos dibuja `row`, arriba de eso `table` con mini-barras
  ([`visualization_macros.clj#L9-L26`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/xrays/automagic_dashboards/visualization_macros.clj#L9-L26)).
  El motor nuevo (`metabase.explorations`, 2026) tiene las constantes comentadas, y los
  comentarios son la justificación entera
  ([`mechanical.clj`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/explorations/query_plan/mechanical.clj)):
  `time-facet-max-cardinality 20` *("Above this, a per-category line series would be
  unreadable")* y `default-max-cardinality 100` *("Above this the bar count is unreadable
  AND the serialized result risks blowing the cache budget")*.

En los **x-rays** de Metabase el mapeo no se computa: está escrito a mano en plantillas
YAML, con `max_cardinality` filtrando qué campo puede entrar
([`example.yaml`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/resources/automagic_dashboards/table/example.yaml)):

```yaml
- ProductCategory:
    field_type: ProductTable.Category
    max_cardinality: 10    # only capture fields with 10 or less distinct values
```

**Vanna v2** vuelve a la heurística después de haber pasado por el LLM. `PlotlyChartGenerator`
son 313 líneas deterministas, con las reglas en el docstring
([`chart_generator.py#L29-L36`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/integrations/plotly/chart_generator.py#L29-L36)):
`4+ columnas → table` (cortocircuita antes de mirar tipos), `1 numérica → histogram`,
`1 categórica + 1 numérica → bar`, `2 numéricas → scatter`, `3+ numéricas → heatmap`,
datetime gana sobre todo y va a `line`, capado a 5 series
(`# Limit to 5 lines for readability`).

### 1.2 · El LLM elige, de un enum cerrado

**Metabot**, el NL→query de Metabase, le expone al modelo una lista de 21 strings
([`shared.clj#L8-L14`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/metabot/tools/shared.clj#L8-L14)),
`visualization.chart_type` es un argumento **opcional** de la tool, y el fallback es
`table`. Hay validación explícita del lado servidor, con el motivo escrito en el docstring
([`agent_api/api.clj#L729-L733`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/agent_api/api.clj#L729-L733)):

> "Display types accepted by Card. Validates LLM-passed values so a bogus value (e.g.
> `"potato"`) gets a 400 rather than persisting junk."

Nada de esto está en la doc pública de Metabot, que sólo declara la limitación inversa:
*"Metabot can't change visualization settings like colors, axis labels, or number
formatting"* ([docs/ai/metabot](https://www.metabase.com/docs/latest/ai/metabot)).

**Vanna v2** parte la decisión en dos: **el LLM decide *cuándo*, la heurística decide
*qué*.** El mecanismo de "cuándo" es un empujón en texto dentro del resultado de `run_sql`
([`run_sql.py#L98-L106`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/tools/run_sql.py#L98-L106)):

```
(Results truncated to 1000 characters. FOR LARGE RESULTS YOU DO NOT NEED TO SUMMARIZE
THESE RESULTS OR PROVIDE OBSERVATIONS. THE NEXT STEP SHOULD BE A VISUALIZE_DATA CALL)
```

Y la tool que llama sólo acepta `filename` y `title`: **el modelo no puede pedir un tipo de
gráfico**. Se describe al modelo como *"The tool automatically selects an appropriate chart
type based on the data"*
([`visualize_data.py`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/tools/visualize_data.py)).

### 1.3 · El LLM escribe la spec entera

**Google Conversational Analytics API** es el caso más explícito, y encima documentado
([render-visualization](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/render-visualization)):

> "The agent identifies the relevant data result and passes it to a subagent. This subagent
> executes Python code to generate a Vega-Lite JSON configuration for the chart."

**Snowflake Cortex Agents** hace lo mismo con una tool llamada `data_to_chart`, y emite el
evento SSE `response.chart` con `chart_spec` = *"The vega-lite chart specification
serialized as a string"*
([cortex-agents-run](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)).
Snowflake CoWork agrega una perilla interesante: `vega_template`, *"A partial Vega-Lite JSON
spec that is deterministically merged into every generated chart"*
([chart-customization](https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-cowork/chart-customization))
— o sea, la institución fija lo que no quiere que el modelo decida.

**Vanna v1** es la versión sin baranda de esta familia: el LLM escribe código Python de
Plotly y se ejecuta con `exec(plotly_code, globals(), ldict)`
([`base.py#L2086-L2088`](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/base/base.py#L2086-L2088)),
sobre los `globals()` reales, sin sandbox. La única "sanitización" previa es un
`.replace("fig.show()", "")`. Si el `exec` falla, cae a un árbol de decisión con
`plotly.express` que es, de nuevo, una heurística
([L2091-L2110](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/base/base.py#L2091-L2110)).

Un detalle de Vanna v1 que sí vale copiar: **al LLM le pasa sólo los tipos, nunca filas**.
En los dos call sites, literal:
`df_metadata=f"Running df.dtypes gives:\n {df.dtypes}"`
([L1762](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/base/base.py#L1762)).
El modelo elige el tipo de gráfico a ciegas sobre los valores.

### 1.4 · Nadie: lo elige el usuario

**Apache Superset no tiene recomendación automática**, y esto es un negativo bien
auditado. El `VizTypeGallery` recibe `{onChange, onDoubleClick, selectedViz, className,
denyList}` — **el selector literalmente no puede ver los datos**. El default es estático:
`DEFAULT_VIZ_TYPE = "table"` (`superset/config.py:174`). La única aparición de
"recommended" en el frontend de Explore es `RECOMMENDED_TAGS`, usada para *sacar* esos tags
del sidebar. El único `chart_type_suggester.py` vive en el servicio MCP, **nunca lee el
dataset** (`dataset_id: int | str,  # noqa: ARG002`), clasifica ejes por **substring del
nombre de columna**, y su contrato dice `is_valid: Always True (warnings don't block
generation)`
([archivo](https://github.com/apache/superset/blob/574d121cd869194010757c8cc1de8a28c55b3200/superset/mcp_service/chart/validation/runtime/chart_type_suggester.py)).
Nada del frontend lo importa.

**LangChain y LlamaIndex no tienen ningún componente de visualización.** Cero hits de
`vega`/`plotly`/`altair`/`echarts` en el código de librería de los cuatro repos de
LangChain; en la doc, *todos* los "vega" eran `Las Vegas`. El camino bendecido es "Python
REPL + matplotlib + `plt.savefig`"
([deepagents/data-analysis](https://docs.langchain.com/oss/python/deepagents/data-analysis)),
y ni siquiera hay captura de la figura: `PythonAstREPLTool._run` devuelve **sólo stdout**.
El prompt del pandas agent no menciona gráficos en ninguna de sus 44 líneas
([`pandas/prompt.py`](https://github.com/langchain-ai/langchain-experimental/blob/f10d5c3247fb102d4d45d29a35a0266760288542/libs/experimental/langchain_experimental/agents/agent_toolkits/pandas/prompt.py)),
y el paquete entero está **sunset desde 2026-05-22**
([issue #87](https://github.com/langchain-ai/langchain-experimental/issues/87)).

En LlamaIndex el `PandasQueryEngine` stringifica el resultado
(`output_str = str(safe_eval(...))`), así que aunque el código generara una figura
devolvería su `repr`. El módulo se movió a experimental en 2024, se deprecó y se **borró
físicamente** del repo (commit `519142086c`, 2026-04-03). El detalle más elocuente: el
`VannaPack` de LlamaIndex **apaga la visualización de Vanna** con
`ask_kwargs = {"visualize": False, ...}`.

### 1.5 · El usuario lo pide en la pregunta

Es la única vía que documentan casi todos, y suele ser un **override**, no el camino
principal:

- **Power BI Q&A**: *"If you want to change the visualization type, enter 'as *chart type*'
  after the question."*
  ([q-and-a-intro](https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-intro)).
  Ojo: la misma página abre con el banner *"Q&A experiences are going away in December
  2026."*
- **Databricks Genie**: *"For many questions, Genie automatically generates a visualization
  and a result table"* y *"You can ask for a specific visualization to be included in a
  response"* ([talk-to-genie](https://docs.databricks.com/aws/en/genie-agents/talk-to-genie)).
- **Google**: `ChartQuery.instructions` está documentado como *"Natural language
  instructions for generating the chart"*, y el ejemplo de la propia doc es *"Create a bar
  graph that shows the top five states by the total number of airports."*
- **Vanna v1** tiene `chart_instructions`, que reinyecta el pedido y cachea el código para
  no volver a llamar al modelo
  ([flask L677-L688](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/flask/__init__.py#L677-L688)).
- **Anthropic**, sobre Claude.ai: *"Claude decides when a visual would help based on what
  you're asking. You can also ask directly."*
  ([custom visuals in chat](https://support.claude.com/en/articles/13979539-custom-visuals-in-chat)).
  Es la formulación más honesta que encontré: dice que decide, y no dice cómo.

### 1.6 · Lo que dice la investigación: enumerar y rankear

La línea de UW IDL contesta la pregunta desde otro lado: en vez de una regla por tipo de
dato, **enumeran todas las specs posibles y las ordenan por efectividad perceptual**.

**CompassQL** ([HILDA 2016, PDF](https://idl.cs.washington.edu/files/2016-CompassQL-HILDA.pdf))
extiende Vega-Lite con comodines: poner `M` en `mark` significa "enumerá todas las marcas
posibles". Y la parte que sirve acá es la tabla de efectividad, que está en el código y es
literalmente una tabla
([`typechannel.ts`](https://github.com/vega/compassql/blob/master/src/ranking/effectiveness/typechannel.ts),
comentario del archivo: *"Cleveland / Mackinlay based"*):

| canal | Q/T continuo | binned/ordinal | nominal |
| --- | ---: | ---: | ---: |
| x, y | 0 | 0 | 0 |
| size | −0,575 | −0,575 | −3 |
| color | −0,725 | −0,725 | −0,6 |
| shape | **−10** | −3,1 | −0,65 |
| row / column | **−10** | −0,75 | −0,7 |
| detail | −20 | −4 | −2 |

Cero es lo mejor. `TERRIBLE = -10` es la constante del archivo: forma y facetado son
directamente inaceptables para un cuantitativo.

**Draco** ([InfoVis 2018, PDF](https://idl.cs.washington.edu/files/2019-Draco-InfoVis.pdf))
lleva eso a *constraints* de Answer Set Programming, con pesos **aprendidos de experimentos
de percepción** (~1.100 pares de Kim et al., 10 de Saket et al.). Del abstract:

> "We propose modeling visualization design knowledge as a collection of constraints, in
> conjunction with a method to learn weights for soft constraints from experimental data."

Los duros que más importan acá, del propio
[`hard.lp`](https://github.com/uwdata/draco/blob/master/asp/hard.lp):

```prolog
% @constraint Bar and area mark requires scale of continuous to start at zero.
hard(bar_area_without_zero) :- mark(bar;area), channel(E,y), orientation(vertical), not zero(E).

% @constraint Size implies order so nominal is misleading.
hard(size_nominal) :- channel(E,size), type(E,nominal).

% @constraint Cannot aggregate nominal.
hard(aggregate_nominal,E) :- aggregate(E,_), type(E,nominal).

% @constraint At most 20 categorical colors.
hard(color_with_cardinality_gt_twenty,E,C) :- channel(E,color), discrete(E), enc_cardinality(E,C), C > 20.

% @constraint Do not use log for bar or area mark as they are often misleading.
hard(area_bar_with_log) :- mark(bar;area), log(E), channel(E,(x;y)).
```

Y los blandos de cardinalidad, de [`soft.lp`](https://github.com/uwdata/draco/blob/master/asp/soft.lp):
`shape_cardinality` sobre 5, `high_cardinality_nominal` sobre 12, `high_cardinality_ordinal`
sobre 30, `horizontal_scrolling` sobre 50 en x.

Dato de `weights.lp` que vale para nuestro caso: `c_d_bar_weight = 20` con solapamiento
contra `c_d_no_overlap_bar_weight = 0` sin él. **Draco prefiere barras sólo cuando los datos
ya vienen agregados.**

**Observable Plot** tiene la versión pragmática de esto, `Plot.auto`, y su doc se **niega
explícitamente a documentar las reglas**
([marks/auto](https://observablehq.com/plot/marks/auto)):

> "Because its heuristics are likely to evolve, they are not explicitly documented; see the
> source code for details."

En el fuente
([`auto.js`](https://github.com/observablehq/plot/blob/main/src/marks/auto.js)) la regla no
mira si el campo es temporal: mira si la serie es **monótona**. Fecha ordenada → `line`;
fecha desordenada → `dot`.

---

## 2 · Qué forma tiene el gráfico en el contrato

Cuatro formas, y la elección entre ellas es la decisión de arquitectura, no el tipo de
gráfico.

| Forma | Quién | Qué viaja | El riesgo propio de esa forma |
| --- | --- | --- | --- |
| **Nada** | Cortex Analyst | `sql` y ya; el cliente ejecuta | Ninguno. Y ningún gráfico |
| **Tipo + mapeo de columnas** | Metabase, QuickSight, Vanna v2 | `display` + qué columna va a qué canal | El renderer es propio; hay que escribirlo |
| **Spec declarativa** | Google CA API, Cortex Agents | Vega-Lite JSON completo, **con sus datos adentro** | El modelo puede escribir cualquier cosa, incluidos números |
| **Imagen renderizada** | OpenAI, Anthropic (code exec) | un `file_id` de PNG | No se audita, no se copia, no se lee con lector de pantalla |
| **Puntero opaco** | Genie | `viz: {title, query_attachment_id}` | El cliente no puede dibujar nada |

### 2.1 · El patrón "tipo + mapeo de columnas"

Es el que mejor encaja con D-04, y tiene dos implementaciones publicadas.

**Metabase** lo emite así, desde el generador de x-rays
([`populate.clj#L104-L122`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/xrays/automagic_dashboards/populate.clj#L104-L122)):

```clojure
{:display                display
 :visualization_settings (assoc visualization-settings
                                :graph.series_labels (map :name metrics)
                                :graph.metrics    (mapv first aggregation)
                                :graph.dimensions (seq viz-dims))}
```

`graph.dimensions` y `graph.metrics` son **nombres de columna**, no valores. El contrato
REST de `POST /api/card` exige los dos campos, con `display` como string y
`visualization_settings` como mapa libre
([`card.clj#L491-L494`](https://github.com/metabase/metabase/blob/33ebc8e671169a8c5c3eab057c7f28ac48ce21cb/src/metabase/queries_rest/api/card.clj#L491-L494)).

**QuickSight** hace lo mismo con tipos cerrados: `Visual` es un *union type* —*"only one of
the attributes can be defined"*— con miembros `BarChartVisual`, `LineChartVisual`,
`KPIVisual`, `TableVisual`…, y cada uno lleva `ChartConfiguration → FieldWells →
AggregatedFieldWells` con `Category` y `Values`
([API_Visual](https://docs.aws.amazon.com/quicksight/latest/APIReference/API_Visual.html)).

**Ninguno de los dos manda las filas dentro del gráfico**, y eso es exactamente la
propiedad que nos interesa: el gráfico es una instrucción de dibujo sobre datos que ya
están, no una copia de los datos.

**El matiz honesto:** en los dos casos las filas llegan por otro camino (el endpoint de
ejecución de la card, el dataset de SPICE), no en el mismo payload. **No encontré un
producto que devuelva "tipo + nombres de columna" apuntando a filas que viajan en la misma
respuesta.** Es un patrón que se deduce de dos precedentes, no uno que se copia de uno.

### 2.2 · La spec declarativa

El formato ganador cuando el LLM escribe la spec es **Vega-Lite**, y lo eligieron los dos
proveedores grandes que lo hacen. Una spec es `data` + `mark` + `encoding` con `field` y
`type`, y los tipos son cinco: `quantitative`, `temporal`, `ordinal`, `nominal`, `geojson`
([type](https://vega.github.io/vega-lite/docs/type.html)).

El riesgo de esta forma es directo: **la spec lleva los datos adentro**. En Google el path
es `systemMessage.chart.result.vegaConfig`; en Snowflake es un string con el JSON serializado.
Si el modelo escribe la spec, escribe los números.

### 2.3 · La imagen renderizada

OpenAI Code Interpreter devuelve el PNG como anotación `container_file_citation` en el
Responses API, o `{"type": "image_file", "image_file": {"file_id": "..."}}` en Assistants
([guides/tools-code-interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter)).
Anthropic lo mismo, por `file_id`, y su regla de captura está documentada: *"the files at
the top level of that directory are captured and returned as the `file_id` entries"*
([code-execution-tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool)).

Claude.ai es el único vendor que documenta haberse ido de ahí a propósito:

> "Claude builds them using HTML—the same building blocks as web pages—so they're
> interactive and specific to your question rather than static images."
> — [custom visuals in chat](https://support.claude.com/en/articles/13979539-custom-visuals-in-chat)

---

## 3 · Cómo evitan que el gráfico mienta

### 3.1 · Graficar sobre una muestra truncada

**Nadie lo previene, porque nadie grafica sobre una muestra.** Los productos grafican el
resultado completo y truncan sólo lo que le muestran al modelo o a la tabla de la UI.

En Vanna v1 esto es explícito y es al revés de lo que uno esperaría: el `df.head(10)` de
[flask L517](https://github.com/vanna-ai/vanna/blob/4da8dea0ce14a0d1db5a0692a7921d873be91c5f/src/vanna/flask/__init__.py#L517)
es **sólo el preview de la tabla**; el DataFrame entero se cachea una línea antes y es el
que llega a `get_plotly_figure`. El `fig.to_json()` que viaja al browser lleva **todas las
filas embebidas**. En v2 igual: `generate_chart` recibe el CSV completo, y lo que se trunca
a 1000 caracteres es lo que ve el LLM.

Lo único que encontré que *declara* el truncado en el contrato es **Databricks Genie**, que
mete `query_result_metadata: {row_count, is_truncated}` dentro del attachment `query`
([createmessage](https://docs.databricks.com/api/workspace/genie/createmessage)). No dice
qué hacer con eso, pero al menos el cliente puede saberlo.

**Es el hueco más filoso para este repo**, porque acá la relación es la inversa: `_filas`
devuelve `{"columnas", "muestra": filas[:5], "total": len(filas)}`
([`agent/loop.py`](../agent/loop.py), `MUESTRA_DE_FILAS = 5`), y la pantalla ya lo declara
en prosa —*"Mostrando 5 de 431 filas"*—. Un gráfico sobre `filas.muestra` sería un gráfico
de las cinco primeras filas presentado como si fuera el conjunto, y sería la falla más
difícil de ver de todas: sale bien dibujado.

### 3.2 · Mezclar unidades o monedas en un mismo eje

**No encontré una sola guía primaria que diga "no mezcles monedas en un mismo eje".** Lo
busqué en la guía del UK Analysis Function (grep sobre "unit": las apariciones son sobre
alineación de dígitos), en Statistics Canada y en las guías federales de EE.UU. Lo digo
así porque no aparece, no porque sea falso.

Lo que sí existe, y es lo más cerca, es la regla sobre **ejes duales**. Eurostat es la más
tajante ([tutorial de tablas y gráficos](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Tutorial:Insert_tables,_graphs_and_maps)):

> "Charts should not have 2 y-axes as this makes it difficult to interpret the data;
> instead make 2 graphs."

Y el UK Analysis Function
([data-visualisation-charts](https://analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts/)):

> "In general, we do not recommend using dual axis charts because: they can be easily
> misinterpreted; the way we display lines in relation to each other can manipulate the
> data story, even if it is not intentional."
> "Dual axis line charts can be manipulated to show almost any relationship."

### 3.3 · Ejes que no arrancan en cero

Acá hay **consenso unánime en barras y desacuerdo en líneas**, y conviene saberlo antes de
elegir una regla.

**En barras, todos dicen lo mismo.** UK Analysis Function:

> "Breaking the numerical axis is when you make the axis start from a number other than
> zero. […] In bar charts you perceive the bars being proportional to each other –
> breaking the numerical axis distorts these relative proportions."
> "If starting the numerical axis at zero stops you from telling the story clearly,
> consider an alternative chart, such as a Cleveland dot plot."

Las U.S. Data Visualization Standards
([bar-chart](https://xdgov.github.io/data-design-standards/visualizations/bar-chart)):
*"bar charts should always start at zero. When bar charts do not start at zero, it risks
users misjudging the difference between data values."*

**En líneas no hay acuerdo.** UK AF lo permite con condiciones —*"it is acceptable to break
a numerical y-axis on a line chart, when necessary. Line charts are not read in the same way
as bar charts"*—, exigiendo que el corte sea desde un número redondo y que se **mencione en
la descripción textual del gráfico** *("necessary for accessibility")*. Eurostat exige cero
en **todos** los gráficos. Las U.S. Standards, en los "Always" del line graph: *"Start the
y-axis at zero."* USWDS: *"Line charts origin should start at zero, unless clearly noted."*

**Vega-Lite ya lo hace por default y lo fuerza para barras.** La propiedad `zero` de la
escala ([scale#continuous](https://vega.github.io/vega-lite/docs/scale.html#continuous)):

> "If `true`, ensures that a zero baseline value is included in the scale domain.
> **Default value:** `true` for x and y channels if the quantitative field is not binned
> and no custom `domain` is provided; `false` otherwise."

Y en el compilador, para bar/area no rangeadas el `zero` **se fuerza a `true` ignorando el
config** ([`properties.ts#L418-L482`](https://github.com/vega/vega-lite/blob/main/src/compile/scale/properties.ts)).
Draco codifica la misma regla como constraint duro (§1.6).

**Observable Plot hace lo contrario, y hay que saberlo**
([features/scales](https://observablehq.com/plot/features/scales)): el dominio por default
es el **extent** de los datos; `zero` es una opción que hay que pedir, y en `Plot.auto` ni
siquiera extiende el dominio — dibuja una regla en cero (`rules = [xZero ? ruleX([0]) : null, ...]`).

### 3.4 · Agregación implícita que el usuario no pidió

Tres comportamientos distintos, y el tercero es el peligroso.

**Vega-Lite no agrega nada implícitamente.** La agregación se dispara sólo si algún canal la
declara ([aggregate](https://vega.github.io/vega-lite/docs/aggregate.html)):

> "If at least one fields in the specified encoding channels contain `aggregate`, the
> resulting visualization will show aggregate data. In this case, all fields without
> aggregation function specified are treated as group-by fields."

Pero **sí apila por default**: `STACK_BY_DEFAULT_MARKS = [BAR, AREA, ARC]` con
`offset = 'zero'` ([`stack.ts`](https://github.com/vega/vega-lite/blob/main/src/stack.ts)).
Una barra por fila, apiladas sobre cada categoría. No hay `groupby`, pero **se lee como una
suma**.

**Observable Plot sí agrega**: con una sola dimensión, `Plot.auto` inyecta `count` en el eje
libre (`xReduce = ... ? "count" : null`) y produce un histograma que el usuario no pidió.

**Vanna v2 agrega en silencio, sin declararlo**: el bar chart hace
`df.groupby(x_col)[y_col].sum()` adentro de `PlotlyChartGenerator`. Ese `.sum()` es
literalmente lo que D-08 prohíbe si la columna es un monto y hay más de una moneda en la
tabla.

---

## 4 · Accesibilidad y auditabilidad

### 4.1 · Los criterios que aplican, y los que no

De WCAG 2.2, aplican tres y **uno no**:

- **1.1.1 Non-text Content (A)** — el Understanding nombra los gráficos explícitamente, y
  su ejemplo es el patrón corto + largo:
  > "A bar chart compares how many widgets were sold in June, July, and August. The short
  > label says, 'Figure one - Sales in June, July and August.' The longer description
  > identifies the type of chart, provides a high-level summary of the data, trends and
  > implications comparable to those available from the chart."
  > — [Understanding 1.1.1](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html)
- **1.4.1 Use of Color (A)** — aplica por lectura directa del criterio; el Understanding
  **no** trae ningún ejemplo de gráfico (verificado por grep sobre "chart"/"graph"/"legend").
- **1.4.11 Non-text Contrast (AA)** — es el que cubre las barras y las líneas, no 1.4.3.
  > "The term 'graphical object' applies to stand-alone icons such as a print icon (with no
  > text), and the important parts of a more complex diagram such as each line in a graph."
  > — [Understanding 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

  Con una nota que sirve mucho para el diseño de acá: si los valores están disponibles de
  forma conforme —una tabla, por ejemplo— las partes del gráfico **dejan de ser** "required
  for understanding" y el 3:1 sobre ellas se relaja.
- **1.4.5 Images of Text (AA) NO aplica** a un gráfico rasterizado: el criterio excluye
  explícitamente *"text that is part of a picture that contains significant other visual
  content. Examples of such pictures include graphs, screenshots, and diagrams"*.

**El APG no tiene ningún patrón para gráficos.** Verificado sobre
[la lista de patrones](https://www.w3.org/WAI/ARIA/apg/patterns/): son 32 y ninguno es un
chart; grep de "chart"/"graph"/"visualiz" en la home del APG da cero. Lo que sí existe es la
**WAI-ARIA Graphics Module**, W3C Recommendation del 2 de octubre de 2018, con
`graphics-document`, `graphics-object` y `graphics-symbol`
([graphics-aria-1.0](https://www.w3.org/TR/graphics-aria-1.0/)).

### 4.2 · La tabla al lado del gráfico

El tutorial del W3C sobre imágenes complejas define el patrón de dos partes:

> "In these cases, a two-part text alternative is required. The first part is the short
> description to identify the image […] The second part is the long description – a textual
> representation of the essential information conveyed by the image."
> — [Complex Images](https://www.w3.org/WAI/tutorials/images/complex/)

Y recomienda que la descripción larga sea **visible para todos**: *"Make long descriptions
available to everyone to reach a wider audience with your content. For example, show the
description as part of the main content."*

**Corrección importante:** ese tutorial **no** dice explícitamente "acompañá el gráfico con
la tabla de datos". Usa una tabla dentro de un `<figcaption>` como *ejemplo* de descripción
larga estructurada, y advierte que si la descripción incluye una tabla **no** se puede
colgar de `aria-describedby`, porque *"the element referenced by `aria-describedby` is
treated as one continuous paragraph of text"*.

La recomendación explícita de la tabla está en otra fuente primaria, el
[U.S. Web Design System](https://designsystem.digital.gov/components/data-visualizations/):

> "Provide an screen-reader accessible data table of the information represented in your
> visualization using the class `usa-sr-only`."

…y el mismo documento dice, en la línea siguiente, por qué **la tabla no alcanza**:

> "Access to the underlying data provides an alternative affordance for consuming the same
> information, but a data table does not provide an equivalent narrative to a visualization."

Highcharts, que es la implementación más completa del mercado, dice lo mismo con otras
palabras: *"simply showing the chart data as a table is not considered a sufficient
accessible alternative to a chart"*
([accessibility/tables](https://www.highcharts.com/docs/accessibility/tables)). Y su
posición sobre las descripciones ocultas es la que más nos sirve:

> "Setting this option will expose the description to screen reader users, but keep it
> visually hidden. This is not generally recommended, since making the description visible
> will also improve cognitive accessibility, and make it easier for all users to understand
> the message of the chart."
> — [accessibility-module](https://www.highcharts.com/docs/accessibility/accessibility-module)

Highcharts publica además un **VPAT 2.4 / Accessibility Conformance Report**
([artículo](https://www.highcharts.com/article/highsoft-accessibility-conformance-report/)),
con una escala inusual porque reporta sobre la *capacidad de la librería*, no sobre el
contenido: *"Supports: A developer is able to produce charts that meet the criterion by
using functionality available in the Highcharts public API."*

### 4.3 · Qué trae cada librería

| Librería | `aria-label` por punto | Roles del Graphics Module | Tabla accesible | Nav. por teclado |
| --- | --- | --- | --- | --- |
| Vega / Vega-Lite | sí, por canal | **sí, automáticos** | no | no |
| Observable Plot | sí, `ariaLabel` es canal | no | no | no |
| Highcharts | sí, `descriptionFormat` | sí | **sí**, y sonificación | sí |
| Chart.js | no | no | no | no |

Vega genera los roles solo: `emit(ARIA_ROLE, item.ariaRole || (type === 'group' ? GRAPHICS_OBJECT : GRAPHICS_SYMBOL))`
([`aria.js`](https://github.com/vega/vega/blob/main/packages/vega-scenegraph/src/util/aria.js)).
**Ojo:** eso está en el código, no en la doc publicada, que sólo afirma que genera "role y
roleDescription" ([marks](https://vega.github.io/vega/docs/marks/)). Y la doc de Vega-Lite
describe su `description` de nivel superior como *"Description of this mark for commenting
purpose"* — **no** afirma que llegue al `aria-label`, a diferencia de la de Vega.

Chart.js es el extremo opuesto y su doc lo dice sin vueltas: renderiza sobre `<canvas>`, y
la accesibilidad es enteramente del integrador — poner `role="img"` y `aria-label` a mano
([accessibility](https://www.chartjs.org/docs/latest/general/accessibility.html)).

---

## 5 · Peso y librerías

Dos mediciones, y valen cosas distintas. **bundlephobia** mide el paquete entero; **esbuild
local** mide un import realista (un bar chart y un line chart, con ejes y tooltip, con
React externalizado). La segunda es la que importa para decidir.

| Librería | Versión | min | **min+gzip** | React-nativo | Nota |
| --- | --- | ---: | ---: | --- | --- |
| SVG a mano | — | 0 | **0** | sí | — |
| uPlot | 1.6.32 | 52,0 KB | **23,0 KB** | no | canvas; sin wrapper oficial |
| uPlot + `uplot-react` | 1.2.4 | 56,4 KB | **24,9 KB** | wrapper de terceros | CJS-only, no tree-shakea |
| visx (`scale`+`shape`+`axis`+`group`) | 4.0.0 | 77,8 KB | **27,1 KB** | sí, componentes SVG | tree-shaking real |
| Chart.js + `react-chartjs-2`, tree-shaken | 4.5.1 / 5.3.1 | 174,8 KB | **61,0 KB** | wrapper | canvas |
| Observable Plot (imports nombrados) | 0.6.17 | 274,1 KB | **92,7 KB** | no | arrastra d3 |
| Recharts | 3.10.1 | 391,8 KB | **114,0 KB** | sí | |
| Vega + Vega-Lite + vega-embed + react-vega | 6.4.0 / 6.4.3 / 7.2.0 / 8.0.0 | 890,0 KB | **302,5 KB** | wrapper oficial | |

Números individuales de visx, que son los que hacen la diferencia: `@visx/group` **0,96 KB
gzip**, `@visx/shape` (Bar + LinePath) **3,6 KB**, `@visx/scale` **12,3 KB**, `@visx/axis`
**17,2 KB**. Es el único de la lista donde el peso escala con lo que usás de verdad.

Cinco cosas que conviene tener escritas antes de elegir:

- **Recharts v3 no es más liviano que v2.** bundlephobia da 147,5 KB gzip contra 123,9; en
  el import realista quedan 114,0 contra 108,8. El refactor cambió las dependencias
  (`lodash` → `es-toolkit`, más toda la máquina de Redux/immer/reselect) y **no bajó el
  peso**. Además `react-is` es peer dep explícita: hay que instalarla.
- **Los 87 KB gzip que bundlephobia le da a `vega-lite` subestiman por ~3×**, porque
  excluyen el peer `vega`. La stack real de renderizar una spec en el browser son **~302 KB
  gzip**.
- **`react-vega` v8 cambió la API**: sólo exporta `VegaEmbed` y `useVegaEmbed`. Los
  componentes `<Vega>` y `<VegaLite>` ya no existen.
- **Observable Plot no es React** y su doc oficial documenta los dos caminos
  ([getting-started](https://observablehq.com/plot/getting-started#plot-in-react)): SSR con
  `toHyperScript()` —*"only practical for simple plots of small data"*— o `useEffect` +
  `containerRef.current.append(plot)`, tirando el gráfico entero y rehaciéndolo en cada
  cambio. No hay diffing.
- **uPlot y Chart.js son canvas**, no SVG: sin nodos DOM por dato, sin estilar con CSS, sin
  nada que un lector de pantalla pueda recorrer.

**Sobre el SVG a mano, el trade-off honesto.** No es una opción teórica en este repo: ya
está ejercida. `Derivacion.jsx` dibuja la escala proporcional de la cascada con un `<span>`
de ancho porcentual, con el piso explicado en el comentario —*"sin el piso, 660 sobre
180.000 desaparece y el ojo lee 'ninguno' donde hay 660"*—, `aria-hidden="true"` sobre la
barra porque el número ya está en el texto, y el tope calculado **por tramo** para no cruzar
un cambio de unidad ([`web/src/derivacion.js`](../web/src/derivacion.js)). Eso es un gráfico
de barras horizontales, con escala desde cero por construcción y accesibilidad resuelta, y
pesa cero.

Lo que **no** da el SVG a mano y sí dan las librerías: ejes con ticks bien espaciados
(`d3-scale` resuelve el "nice" que uno subestima siempre), formato de fechas, tooltips con
posicionamiento, responsive con `ResizeObserver`, y apilado. Para una serie temporal de doce
meses con un eje de fechas, escribirlo a mano es trabajo real; para una cascada de cinco
escalones, la librería es peso muerto.

---

## 6 · Cómo se evalúa un gráfico

**Respuesta corta: en investigación sí, y bastante bien desde 2024. En producción, nadie.**

### 6.1 · En producción, nadie. Con la evidencia de dónde busqué

| Framework / producto | Evaluador de gráficos | Qué mide, y dónde está el catálogo |
| --- | --- | --- |
| LangSmith / openevals | **no** | Los únicos prompts de imagen son de moderación de contenido ([prebuilt-evaluators](https://docs.langchain.com/langsmith/prebuilt-evaluators)) |
| OpenAI Evals | **no** | Hay un `simple-charting.yaml` y es *multiple choice* calificado por substring ([repo](https://github.com/openai/evals)) |
| Ragas | **no** | Tiene métricas de **SQL** (execution-based, equivalencia). De charts, nada ([available_metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)) |
| DeepEval | **no** | Sus cinco métricas multimodales son de *text-to-image* ([metrics](https://deepeval.com/docs/metrics-introduction)) |
| promptfoo | **no** | `is-sql` / `contains-sql` sí; charts no ([expected-outputs](https://www.promptfoo.dev/docs/configuration/expected-outputs/)) |
| Databricks Genie | **no** | *"The generated SQL and results are then compared against the SQL Answer"* ([benchmarks](https://docs.databricks.com/aws/en/genie/benchmarks)) |
| Snowflake Cortex Analyst | **no** | accuracy = *"the percentage of verified queries where the generated SQL was judged correct"* ([evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)) |
| Vertex AI Gen AI eval, Arize Phoenix | **no** | Phoenix tiene SQL Generation Eval; de gráficos, cero |

### 6.2 · En investigación, tres generaciones

**nvBench** (SIGMOD 2021) mide **exact match de la spec**. De ncNet, el modelo que lo
acompaña ([PDF](https://nantang.github.io/research/pubs/ncnet.pdf)):

> "To be conservative, the accuracy measures whether the output Vega-Zero sequence exactly
> matches the ground truth Vega-Zero sequence."

Y en su propio análisis de errores, los autores registran el problema: *"**(4) Vega-Zero
unmatched but visualization result match.** Some of predicted Vega-Zero sequences are
unmatched with the ground truth […] but their visualization results are in fact
equivalent."*

**VisEval** (Microsoft, IEEE VIS 2024, [arXiv 2407.00981](https://arxiv.org/abs/2407.00981))
es el que evalúa la **imagen renderizada**, y sus tres dimensiones son:

> "we define **validity** as the ability of the code to render a visualization, **legality**
> as the compliance of the visualization with the query requirements, and **readability** as
> the effectiveness of the visualization in clearly presenting information."

El *legality checker* no lee el código: **deconstruye el SVG renderizado** para extraer los
datos ploteados, el tipo de gráfico, los ejes y las leyendas, y después chequea *"chart
type, data, and order"*. La legibilidad la juzga GPT-4V, con **SRCC 0,843** contra expertos
— mejor que el acuerdo entre expertos (0,782). Sin el modelo de visión, te quedás igual con
validity + legality, que son deterministas.

Su crítica al exact match es la más citable que encontré:

> "Firstly, we adopted some rule-based automated methods, and found them unsatisfactory. For
> example, they often compared data along the x and y axes directly with the ground truth,
> but sometimes the suitable visual mapping can be non-unique."

**nvBench 2.0** (NeurIPS 2025, [arXiv 2503.12880](https://arxiv.org/abs/2503.12880)) es el
que más se parece a nuestro problema, porque trata la **ambigüedad** como ciudadana de
primera:

> "existing efforts often overlook this issue by adhering to the single-correct-answer
> paradigm, where each text query maps to exactly one valid visualization. For example,
> nvBench maps a text query to a unique visualization, ignoring more than 60% of real-world
> ambiguous cases."

La consecuencia metodológica: abandonan accuracy y miden **Precision/Recall/F1@K contra un
conjunto de gráficos válidos**, no contra uno solo. El conjunto dorado se sintetiza con un
solver ASP estilo Draco, o sea la ambigüedad es controlada por construcción.

**Text2Vis** (EMNLP 2025) da el número de costo: juez GPT-4o sobre la imagen, rúbrica 1-5 en
*readability* y *chart correctness*, **1.985 muestras en 5 minutos por US$ 2,0**.

**Draco no se usa como métrica.** Verificado por grep sobre los PDFs completos: la palabra
aparece 0 veces en VisEval, 0 en Text2Vis, 0 en PMVis; en nvBench 2.0 sólo en la
bibliografía, y usan ASP para *sintetizar* el set, no para puntuar. Draco sirve como
**linter de calidad** —"¿este gráfico viola una buena práctica?"—, que es una pregunta
distinta de "¿es el gráfico correcto?".

Y el dato que resume el estado del arte mejor que cualquier resumen: **LIDA** (Microsoft), lo
más usado de todo esto con 3.275 estrellas, califica *el código generado* con GPT-4 y **nunca
mira el gráfico**. VisEval, que sí lo mira, tiene 60.

---

## 7 · Implicancias para este repo

Nada de acá decide. Es qué caminos quedan abiertos, y qué cuesta cada uno.

**Sobre D-04 —todo número sale de una consulta ejecutada.** Es la decisión que más
restringe, y la que descarta más caminos sola:

- Una **spec declarativa con datos adentro** (Vega-Lite como la usan Google y Snowflake)
  pone números escritos por el modelo en el contrato. Hoy `cifras_sin_respaldo` recorre
  `respuesta`, `derivacion`, `valor` y `opciones`
  ([`core/trazabilidad.py`](../core/trazabilidad.py)); un `grafico` con datos adentro
  tendría que entrar a esa lista, o D-04 pasa a tener un agujero exactamente del tamaño del
  campo nuevo.
- El patrón **"tipo + nombres de columna"** (Metabase, QuickSight) no tiene ese problema:
  no hay ningún número que verificar porque no viaja ninguno. El costo es que el renderer
  es nuestro.
- **Código ejecutable** (Vanna v1, LangChain) está descartado por otras razones antes que
  por ésta, y el `exec(plotly_code, globals(), ldict)` de Vanna es la mejor ilustración de
  por qué.

**Sobre D-08 —los montos en monedas distintas no se suman.** Es donde el gráfico puede
mentir sin que nadie escriba un número falso. Dos cosas concretas:

- El bar chart de Vanna v2 hace `df.groupby(x_col)[y_col].sum()` en silencio. Si la
  respuesta es el desglose por moneda —que es la respuesta correcta a "¿cuánto se
  transó?"—, un gráfico de barras sobre esa tabla suma pesos con dólares en el eje sin
  decirlo.
- La pantalla **ya resolvió esto en la derivación**: `partirPorUnidad` corta la cascada en
  tramos y *"entre tramos no se resta nunca"*, con el tope de la escala calculado por tramo
  ([`web/src/derivacion.js`](../web/src/derivacion.js)). La regla existe y está probada; lo
  que no está es su equivalente para un gráfico. La regla primaria más cercana que
  encontré es la de ejes duales de Eurostat, y no es la misma regla.

**Sobre D-07 —la pantalla tiene dos lectores.** El oficial tiene que poder defender el
número frente a un auditor, y eso ya está resuelto sin gráficos: derivación en cascada,
ficha de definiciones, filas reales, exclusiones. Las fuentes de accesibilidad dicen las dos
cosas que hacen falta acá y se contradicen sólo en apariencia: USWDS pide la tabla
(`usa-sr-only`) **y** avisa que *"a data table does not provide an equivalent narrative to a
visualization"*; Highcharts dice que la tabla sola *"is not considered a sufficient
accessible alternative"* y prefiere la descripción **visible** antes que la oculta. Leídas
juntas: un gráfico acá no puede ser la única forma de leer el dato, y su descripción no
puede ser un `alt` que sólo escucha el lector de pantalla. La versión que ya existe —número
en texto, barra con `aria-hidden="true"`— cumple las dos por accidente feliz.

**Sobre D-05 —cuatro estados.** Los cuatro no piden gráfico por igual, y ninguna fuente
ayuda con esto porque ningún producto tiene estados: `NO_SE_PUEDE_RESPONDER` es el caso
donde un gráfico es directamente peligroso, porque *"nunca un cero"* (`CONTEXT.md`) y un
gráfico vacío **es** un cero dibujado. `NECESITO_QUE_ACLARES` con dos opciones y sus `n` es,
en cambio, el único caso del contrato donde un gráfico comparativo tendría algo que agregar
que el texto no dice. Vale anotar que nvBench 2.0 llegó a la misma conclusión desde la
investigación: la ambigüedad rompe el paradigma de una respuesta correcta.

**El problema nuevo, que no lo tiene ninguna de las fuentes.** `filas.muestra` son **5 filas
sobre `filas.total`** (`MUESTRA_DE_FILAS = 5`), y el modelo ve como máximo 50
(`FILAS_QUE_VE_EL_MODELO = 50`, `agent/tools.py`). Todos los productos que grafican, grafican
el resultado completo: nadie tuvo que resolver esto porque nadie se puso en esta situación.
Quedan tres salidas y las tres cuestan algo: graficar sólo cuando `total <= len(muestra)`
—o sea, casi nunca—; devolver un segundo conjunto de filas completo sólo para el gráfico
—que contradice la razón por la que la muestra es de cinco—; o declarar el truncado en el
contrato como hace Genie con `is_truncated` y que la pantalla dibuje el gráfico **rotulado
como muestra**. Ninguna es gratis y la tercera es la única que no rompe nada.

**Y el eval.** Si esto llega a evaluarse, no hay práctica industrial que copiar: hay que
inventarla o traerla de la academia. Lo más barato que encontré es el patrón VisEval **sin
el modelo de visión** —chequeos deterministas de tipo, datos y orden sobre la spec, que en
el patrón "tipo + mapeo de columnas" es trivial porque la spec es un objeto de tres
campos—. Lo más caro y más completo es el juez multimodal de Text2Vis, US$ 2 cada 2.000
muestras. Y hay una advertencia que vale más que las dos: la métrica de exact match está
publicadamente criticada **por los autores del benchmark que la inventó**, porque hay más de
un gráfico correcto para la misma pregunta. Un eval de gráficos escrito con esa métrica
reprobaría respuestas correctas, que es exactamente el error que H4 ya cometió una vez con
el calificador (`NOTES/04-evals.md`, §4).

---

## Lo que no pude averiguar

Lo anoto para que nadie lo dé por buscado:

- **Ninguna guía primaria dice "no mezcles monedas o unidades en un mismo eje."** Lo busqué
  en UK Analysis Function, Eurostat, Statistics Canada, USWDS y U.S. Data Visualization
  Standards. Lo más cerca es la regla de ejes duales, que es otra cosa.
- **Ningún vendor documenta su heurística de "cuándo graficar"**, salvo Metabase y Vanna.
  Snowflake, Databricks, Microsoft, Amazon, OpenAI, Anthropic y Perplexity dicen que deciden
  y no dicen cómo.
- **No hay ningún producto que devuelva "tipo + nombres de columna" apuntando a filas que
  viajan en la misma respuesta.** El patrón se deduce de Metabase y QuickSight; en los dos,
  las filas llegan por otro camino.
- La página de ayuda de OpenAI sobre análisis de datos
  (`help.openai.com/.../8437071`) devolvió **403**: es el único hueco de esa sección.
- Los valores `graphics-object` / `graphics-symbol` de Vega están **en el código, no en la
  doc publicada**. Y la doc de Vega-Lite no afirma que su `description` de nivel superior
  produzca un `aria-label`, a diferencia de la de Vega.
- **bundlephobia devolvió 429 persistente** para `vega`, `vega-embed`, `react-vega` y
  `@visx/group`: esos números salen de medición local con esbuild, no de la API.
- **Deprecaciones que conviene saber**: Power BI Q&A se apaga en diciembre de 2026; Data QnA
  de Google está deprecado desde junio de 2025 en favor de la Conversational Analytics API;
  las URLs "clásicas" de QuickSight Q están todas rotas por el rebrand a Amazon Quick;
  `langchain-experimental` está sunset desde mayo de 2026.
