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
  configurado por su institución, si fue marcado manualmente, o —donde la
  institución así lo configuró— si es PEP vigente.
depende_de_config: [high_risk_score_threshold, pep_is_high_risk]
trampas:
  - El umbral varía por tenant y está versionado en tenant_config.
  - Las tres fuentes son DISJUNTAS, no se contradicen: la cascada suma.
  - Omitir la marca manual pierde 1 de cada 4; omitir el PEP, otro 9 %.
  - risk_assessments tiene historia; sólo vale is_current = true.
  - Borrar un cliente borra su evaluación vigente pero no su historia.
  - El escalón PEP usa "PEP vigente" y está congelado (D-13): la derivación
    tiene que declararlo, porque la pregunta directa por PEPs da otro número.
golden_sql: |
  ...
derivacion:
  - "Clientes de la institución"
  - "activos (no dados de baja)"
  - "con evaluación de riesgo vigente"
  - "score >= umbral configurado"
  - "+ marcados manualmente como alto"
  - "+ PEP vigentes (tu institución los cuenta como riesgo alto)"
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

**Una excepción, declarada:** `misma_persona` no tiene una cascada de esta forma. Sus
escalones **cambian de unidad** —174.669 clientes → 174.342 grupos por documento → 327
filas duplicadas— y los de D-07 se restan a la vista. Sigue siendo una sola pasada y
todos los números siguen saliendo de la base, pero la derivación no se lee como una
resta y la pantalla tiene que decir de qué está hablando en cada línea.

## Las nueve skills


| Skill                 | Qué resuelve                                                       | Decisión clave                                                                           |
| --------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `cliente_onboardeado` | "¿Cuántos clientes onboardeamos este año?"                         | Los `APPROVED` sin `onboarded_at` quedan fuera, y se declara con el número (41,9 %)      |
| `riesgo_alto`         | "¿Cuántos clientes de riesgo alto tenemos?"                        | **Tres** fuentes disjuntas: score vs umbral versionado, marca manual, y PEP vigente donde la perilla lo manda (D-13) |
| `monto_transado`      | "¿Monto total de los clientes de riesgo alto el último trimestre?" | Desglose por moneda **y por sentido**; sólo `SETTLED`. La respuesta son 8 números, no uno |
| `alerta_fuera_de_sla` | "¿Qué alertas están fuera del SLA de revisión?"                    | SLA en horas desde `tenant_config`; dos mitades disjuntas, y la de "revisadas tarde" sólo existe donde el plazo es de 24 h |
| `hallazgo_real`       | "¿Cuántos hallazgos reales tuvimos el último trimestre?"           | Alertas, no casos. Excluir `CLOSED_FALSE_POSITIVE`; `ESCALATED` según la perilla. Tres supuestos declarados (D-12) |
| `caso_reportado`      | "¿Cuántos casos reportamos a la UIF?"                              | Concepto propio, para que la pregunta no pase por la palabra "hallazgo" (D-12)           |
| `pep_confirmado`      | "¿Alguno de nuestros clientes es PEP?"                             | Vigente vs histórico (×3,3) es el eje que pesa, y sigue abierto al eval. **Sin** el flag `is_pep` (D-13) |
| `resolucion_de_casos` | "¿Tiempo promedio de resolución?"                                  | Sólo casos cerrados, y la **antigüedad** de los abiertos como escalón obligatorio        |
| `misma_persona`       | "¿Qué clientes son probablemente la misma persona?"                | Documento normalizado (D-09), con la limitación declarada                                |


**Los períodos no son una skill.** No tienen definición de negocio, ni golden query, ni
derivación, ni exclusiones, y **ninguno de los cinco criterios de validación de abajo les
aplica**. Son un resolvedor determinístico —`AS_OF = 2026-06-01`, "este año" = calendario
2026 hasta `AS_OF`, "último trimestre" = ene–mar 2026, y `fiscal_year_start_month` es un
distractor que **no** los redefine— que vive en el código, con el test rojo que ya pide
H3.4. El agente recibe esas reglas en su contexto de sistema, no pidiendo una definición.

## Validación de cada golden query

Ninguna skill se da por buena sin esto:

1. Corre en **los dos tenants** de trabajo elegidos en H1 y da resultados coherentes.
2. Corre **por debajo del `statement_timeout`** con el rol `agent_ro`.
3. Su `EXPLAIN` usa índice, no seq scan.
4. El resultado se cruza a mano contra una consulta escrita de otra forma — si dos
 caminos distintos dan el mismo número, el número es creíble.
5. Excluye soft-deletes **en todas las tablas del join, no sólo en la principal**, y
 está scopeada por tenant (aunque RLS ya lo garantice: la query tiene que ser
 correcta *también* leída sola). Lo primero no es celo: borrar un cliente **no**
 borra sus evaluaciones de riesgo, y quedan 103.146 vivas colgando de clientes
 borrados. Filtrar sólo por `risk_assessments.deleted_at IS NULL` los deja entrar
 con un score viejo (trampa 13, `NOTES/01-exploracion.md`).

## Cómo las usa el agente

La skill **no** es una jaula. El agente recibe la definición y la golden query como
contexto, y puede:

- ejecutarla tal cual, si la pregunta calza;
- adaptarla (agregar un filtro, cambiar el período, agrupar por otra dimensión);
- ignorarla y escribir la suya, si la pregunta es de otra cosa.

Lo que **no** puede es contradecir la definición sin decirlo. Si usa un criterio distinto
de riesgo alto, tiene que declararlo como supuesto.

## Entregables

- `core/semantics/*.yaml` — las nueve skills. Los períodos no van acá: son código.
- `NOTES/02-semantica.md` — para cada definición: qué alternativas había, cuál elegí,
y el número que da cada alternativa. *"Con la definición A dan 1.240 clientes, con la
B dan 1.890"* es exactamente el tipo de cosa que hace defendible una decisión.
- `CONTEXT.md` — el glosario del dominio, que es lo que impide que dos skills usen la
misma palabra con distinto significado.
- `DECISIONS.md`: las definiciones pendientes, cerradas salvo "PEP", que se decide con
el eval y por una razón escrita.

## Definition of done

- [x] Las 9 skills escritas y validadas con los 5 criterios —
  `scripts/validar_semantica.py`, que automatiza los cinco (el quinto también).
- [x] Cada definición ambigua documentada con el número de sus alternativas —
  `NOTES/02-semantica.md`, sección 1.
- [x] Ninguna skill supera ~2.000 caracteres (la disciplina de Ramp) — máximo
  2.019, medido sobre el texto que lee el agente.
- [x] Ninguna skill usa una palabra que `CONTEXT.md` no defina, ni con otro sentido.
- [x] Las 8 preguntas de referencia tienen respuesta correcta calculada a
  mano, para usar como valor esperado en H4 — `evals/valores_esperados.yaml`,
  cada una por dos caminos independientes. Son 9: `caso_reportado` se desprendió
  de "hallazgo real" al separarla en dos conceptos (D-12).

## Riesgos


| Riesgo                                                            | Mitigación                                                                                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Sobre-escribir skills "por las dudas"                             | Límite de tamaño y una skill por concepto. Si dudo, va a `NOTES/`, no a la skill                                                                |
| Elegir una definición y que el usuario esperara otra              | Por eso el sistema **declara** la definición aplicada en cada respuesta. Un número con su definición explícita es defendible aunque no coincida |
| Golden queries que andan en el tenant chico y mueren en el grande | Regla de validar en los dos                                                                                                                     |


