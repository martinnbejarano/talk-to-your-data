# H2 · Semántica del dominio

**Objetivo.** Convertir los hallazgos de H1 en las **skills** que el agente va a
consultar: pocas, chicas y verificadas. Es el corazón del sistema — sin esto el agente
inventa definiciones razonables pero equivocadas.

## Formato de una skill

Un archivo por concepto, corto y con estructura fija:

```yaml
concepto: riesgo_alto
nombre_humano: "Cliente de riesgo alto"
definicion: |
  Un cliente es de riesgo alto si su evaluación vigente supera el umbral
  configurado por su institución, o si fue marcado manualmente.
depende_de_config: [high_risk_score_threshold]
trampas:
  - El umbral varía por tenant y está versionado en tenant_config.
  - Hay dos fuentes que pueden contradecirse: score y marca manual.
  - risk_assessments tiene historia; sólo vale is_current = true.
golden_sql: |
  ...
derivacion:
  - "Clientes de la institución"
  - "activos (no dados de baja)"
  - "con evaluación de riesgo vigente"
  - "score >= umbral configurado"
  - "+ marcados manualmente como alto"
exclusiones:
  - "clientes dados de baja"
  - "evaluaciones históricas: sólo cuenta la vigente"
parametros: [periodo?]
no_aplica_cuando: |
  La pregunta se refiere al riesgo de una transacción o de un país, no de un cliente.
```

Los campos `trampas` y `no_aplica_cuando` son tan importantes como el SQL: le dicen al
agente **cuándo no usar esto**, que es donde más se equivocan los agentes.

`derivacion` y `exclusiones` son lo que después se ve en pantalla (D-07). Se escriben
acá, con la definición, y no los redacta el modelo en tiempo de respuesta: son el
vocabulario con el que el oficial va a auditar el número. El `golden_sql` tiene que
devolver **un escalón por línea de `derivacion`** —`count(*) FILTER (WHERE ...)` los da
todos en una sola pasada del índice— para que ningún número de la cascada sea calculado
fuera de la base.

## Las ocho skills


| Skill                 | Qué resuelve                                                       | Decisión clave                                                                           |
| --------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `cliente_onboardeado` | "¿Cuántos clientes onboardeamos este año?"                         | Qué hacer con los `APPROVED` sin `onboarded_at`                                          |
| `riesgo_alto`         | "¿Cuántos clientes de riesgo alto tenemos?"                        | Unión de score vs umbral versionado **y** marca manual                                   |
| `monto_transado`      | "¿Monto total de los clientes de riesgo alto el último trimestre?" | Desglose por moneda obligatorio; excluir `REVERSED`                                      |
| `alerta_fuera_de_sla` | "¿Qué alertas están fuera del SLA de revisión?"                    | SLA en horas desde `tenant_config`; incluye las revisadas tarde, no sólo las sin revisar |
| `hallazgo_real`       | "¿Cuántos hallazgos reales tuvimos el último trimestre?"           | Excluir `CLOSED_FALSE_POSITIVE`; decidir si `ESCALATED` cuenta                           |
| `pep_confirmado`      | "¿Alguno de nuestros clientes es PEP?"                             | Sólo `CONFIRMED_HIT` con `is_pep`; `DISCARDED` y `POTENTIAL_HIT` no                      |
| `resolucion_de_casos` | "¿Tiempo promedio de resolución?"                                  | Sólo casos cerrados; reportar cuántos quedaron fuera                                     |
| `misma_persona`       | "¿Qué clientes son probablemente la misma persona?"                | Documento normalizado (D-09), con la limitación declarada                                |


Más una **skill transversal de períodos**: `AS_OF = 2026-06-01`, "este año" = calendario
2026 hasta `AS_OF`, "último trimestre" = ene–mar 2026, y `fiscal_year_start_month` es un
distractor que **no** redefine estos períodos.

## Validación de cada golden query

Ninguna skill se da por buena sin esto:

1. Corre en **los dos tenants** de trabajo elegidos en H1 y da resultados coherentes.
2. Corre **por debajo del `statement_timeout`** con el rol `agent_ro`.
3. Su `EXPLAIN` usa índice, no seq scan.
4. El resultado se cruza a mano contra una consulta escrita de otra forma — si dos
 caminos distintos dan el mismo número, el número es creíble.
5. Excluye soft-deletes y está scopeada por tenant (aunque RLS ya lo garantice: la
 query tiene que ser correcta *también* leída sola).

## Cómo las usa el agente

La skill **no** es una jaula. El agente recibe la definición y la golden query como
contexto, y puede:

- ejecutarla tal cual, si la pregunta calza;
- adaptarla (agregar un filtro, cambiar el período, agrupar por otra dimensión);
- ignorarla y escribir la suya, si la pregunta es de otra cosa.

Lo que **no** puede es contradecir la definición sin decirlo. Si usa un criterio distinto
de riesgo alto, tiene que declararlo como supuesto.

## Entregables

- `core/semantics/*.yaml` — las ocho skills más la de períodos.
- `NOTES/02-semantica.md` — para cada definición: qué alternativas había, cuál elegí,
y el número que da cada alternativa. *"Con la definición A dan 1.240 clientes, con la
B dan 1.890"* es exactamente el tipo de cosa que hace defendible una decisión.
- `DECISIONS.md`: las 6 definiciones pendientes, cerradas.

## Definition of done

- [ ] Las 9 skills escritas y validadas con los 5 criterios.
- [ ] Cada definición ambigua documentada con el número de sus alternativas.
- [ ] Ninguna skill supera ~2.000 caracteres (la disciplina de Ramp).
- [ ] Las 8 preguntas de referencia tienen respuesta correcta calculada a

  mano, para usar como valor esperado en H4.

## Riesgos


| Riesgo                                                            | Mitigación                                                                                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Sobre-escribir skills "por las dudas"                             | Límite de tamaño y una skill por concepto. Si dudo, va a `NOTES/`, no a la skill                                                                |
| Elegir una definición y que el usuario esperara otra              | Por eso el sistema **declara** la definición aplicada en cada respuesta. Un número con su definición explícita es defendible aunque no coincida |
| Golden queries que andan en el tenant chico y mueren en el grande | Regla de validar en los dos                                                                                                                     |


