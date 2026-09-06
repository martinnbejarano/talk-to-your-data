# Plan de acción

## Qué construimos

Una aplicación web donde un oficial de compliance —no técnico— hace una pregunta en
castellano sobre los datos de **su** institución y recibe una respuesta que puede
auditar: el número, la definición de negocio que se aplicó, los filtros, el SQL
ejecutado y una muestra de las filas.

Cuando la pregunta es ambigua, repregunta. Cuando no se puede responder con la data
disponible, lo dice y explica qué falta. Nunca inventa.

## Alcance

### Adentro

- Chat multi-turno con selector de tenant fijo y visible.
- Agente con tools de exploración de esquema y ejecución de SQL, con barandas
estructurales (rol read-only, RLS por tenant, gate de `EXPLAIN`, timeout).
- Skills semánticas para los nueve conceptos ambiguos del dominio, con golden queries
verificadas a mano.
- Cuatro estados de respuesta (respondida / con supuesto / necesito que aclares /
no se puede responder).
- Panel de respuesta en dos lecturas (D-07): para el oficial de compliance, derivación
en cascada, criterios con el origen del parámetro, exclusiones explícitas y filas
reales con export; para IT, el SQL y el plan plegados en `▸ Detalle técnico`.
- Set de evaluación propio con runner y reporte.
- `README.md`, `DECISIONS.md`, `CONTEXT.md` (el glosario del dominio), `NOTES/` (log de
proceso), `AGENT_LOG.md`, `PRODUCT.md`.

### Afuera (decidido, no olvidado)


| Fuera de alcance                 | Por qué                                                                                                                                                   |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Autenticación y usuarios reales  | El selector de tenant simula el scope del login; construir auth no aporta señal                                                                           |
| Escrituras a la base             | El rol es read-only por diseño. Ramp: *"las tools de escritura pueden ser particularmente poco confiables"*                                               |
| Conversión de monedas            | No hay data de FX; inventar una tasa sería el peor error posible (D-08)                                                                                   |
| Dedup por email o nombre difuso  | Decisión D-09, con la limitación declarada en cada respuesta                                                                                              |
| Preguntas guardadas / dashboards | Compite con el tiempo del eval, que aporta más. Va a `PRODUCT.md` como propuesta                                                                          |
| Visualización de resultados      | No mejora la corrección, ni la detección de ambigüedad, ni la auditabilidad. El contrato deja el campo reservado; se suma al final si sobra tiempo |
| Caché de respuestas              | Optimización prematura: sin uso real no sabemos qué se repite                                                                                             |


## Arquitectura

```
infra/
  docker-compose.yml     la base, tal como viene
  bootstrap.sql          post-restore: rol read-only, RLS por tenant, grants
core/
  db/                    pool, SET app.tenant_id por sesión, EXPLAIN gate, timeout
  schema/                introspección: tablas, columnas, índices, valores reales de enums
  semantics/             las skills, una por concepto ambiguo
  matching/              dedup por documento normalizado
agent/
  tools.py               list_tables · describe_table · sample_values ·
                         get_definition · run_sql
  loop.py                orquestación y salida estructurada
api/                     FastAPI: POST /ask (streaming de pasos), GET /tenants,
                         GET /audit/{trace_id}
web/                     React + Vite: selector de tenant, chat, panel de derivación
evals/
  questions.yaml         preguntas golden, una por clase de equivalencia
  run.py                 runner
  reports/               resultados por corrida
tests/                   integración contra la base real, sin storage mockeado
NOTES/                   log de proceso: exploración, confusiones, supuestos descartados
```

### Flujo de una pregunta

1. El front manda `{tenant_id, pregunta, historial}`.
2. El backend abre una conexión con el rol read-only y hace `SET app.tenant_id`.
 **A partir de acá las filas de otros tenants no existen.**
3. El agente recibe el esquema (con los índices disponibles) y las skills relevantes.
4. Explora si le hace falta (`describe_table`, `sample_values`).
5. Propone SQL → `EXPLAIN` → si el plan es malo, vuelve con el error y reintenta.
6. Ejecuta, y arma la respuesta **sólo con valores presentes en los resultados**.
7. Devuelve estado + respuesta + **derivación** + definiciones usadas + exclusiones +
 filas + supuestos, y las queries ejecutadas para el detalle técnico.
8. El front muestra la respuesta y el trace completo en el panel.

## Hitos

Cada hito es entregable por sí solo y tiene su propio mini-plan en esta carpeta.
Se puede cortar en cualquiera.


| #   | Hito                   | Mini-plan                                      | Qué sale                                          |
| --- | ---------------------- | ---------------------------------------------- | ------------------------------------------------- |
| H0  | Base lista y blindada  | [`h0-base.md`](h0-base.md)                     | Base restaurada + `bootstrap.sql` con RLS         |
| H1  | Exploración de la data | [`h1-exploracion.md`](h1-exploracion.md)       | `NOTES/01-exploracion.md` + scripts reproducibles |
| H2  | Semántica del dominio  | [`h2-semantica.md`](h2-semantica.md)           | `core/semantics/*` con golden queries validadas   |
| H3  | Vertical slice         | [`h3-vertical-slice.md`](h3-vertical-slice.md) | Demo end-to-end con derivación auditable          |
| H4  | Set de evaluación      | [`h4-evals.md`](h4-evals.md)                   | `evals/` + primera medición                       |
| H5  | Iteración medida       | [`h5-iteracion.md`](h5-iteracion.md)           | Reportes con la evolución                         |
| H6  | Producto y entrega     | [`h6-entrega.md`](h6-entrega.md)               | README, PRODUCT.md, AGENT_LOG.md                  |


Documento transversal: [`testing.md`](testing.md) — cómo escribimos tests y evals, y
por qué son dos cosas distintas.

**Regla de avance:** no se pasa de hito sin cumplir su *definition of done*. La
excepción es H3, que se puede empezar en paralelo con H2 usando una sola skill.

## Cómo verificamos que funciona


| Criterio                                  | Cómo lo medimos                                                                     |
| ----------------------------------------- | ----------------------------------------------------------------------------------- |
| Contestables: ¿da el número correcto?     | Comparación contra la respuesta esperada del set golden                             |
| Ambiguas: ¿repregunta o declara supuesto? | El estado devuelto tiene que ser `NECESITO_QUE_ACLARES` o `RESPONDIDA_CON_SUPUESTO` |
| Incontestables: ¿reconoce que no puede?   | El estado tiene que ser `NO_SE_PUEDE_RESPONDER`                                     |
| Nunca cruza tenants                       | Test de integración: consultas sin filtro devuelven un solo `tenant_id`             |
| Performance                               | Ninguna query del set supera el `statement_timeout`                                 |
| Todo número es trazable                   | Test: cada cifra de la respuesta aparece en algún resultado del trace               |


## Referencias

Las decisiones de diseño del agente y de la interfaz se apoyan en material publicado, no
en intuición. Las tres que más pesaron:

- [Ramp · ramp-mcp](https://builders.ramp.com/post/ramp-mcp) — por qué conviene que el
modelo escriba SQL en vez de hacer aritmética, y por qué el límite de seguridad va
fuera de la query.
- [Ramp · How To Build Agents Users Can Trust](https://builders.ramp.com/post/how-to-build-agents-users-can-trust)  y [LangChain · Breakout Agents: Ramp](https://www.langchain.com/breakoutagents/ramp) —  
el paso a paso con justificación de cada acción, la posibilidad de interrumpir, y el  
rechazo a los niveles de confianza generados por el modelo.

