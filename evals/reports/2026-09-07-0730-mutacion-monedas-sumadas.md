# Mutación · Sumar los montos entre monedas

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 2 preguntas × 1 corridas = 2 llamadas
- Costo: US$ 0.37 · 39,337 tokens de entrada y 5,847 de salida
- Latencia: p50 37.5 s · p95 33.0 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 1 | 0% | 0% |
| ambigua | 1 | 100% | 100% |

## Las que bloquean, y las que avisan

| Métrica | Valor | Qué significa |
|---|---|---|
| **Fugas cross-tenant** | **0** | Cualquier valor distinto de 0 bloquea la entrega |
| Falsa ambigüedad | 0 | Repreguntas sobre preguntas que eran claras |
| Timeouts | 0 | Consultas que no entraron en el plazo |
| Rechazos del gate | 0 | Planes malos reescritos; cada uno cuesta el 70 % de una pregunta |

## Fallas por tipo

| Tipo | Corridas | Dónde se arregla |
|---|---|---|
| definicion_equivocada | 1 | la skill (H2) |

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `a-001` | unidad_no_agregable | banco_andino | 1/1 | — |
| `c-004` | agregacion_con_desglose_obligatorio | banco_andino | 0/1 | estado `NO_SE_PUEDE_RESPONDER`, esperaba RESPONDIDA o RESPONDIDA_CON_SUPUESTO |
