# Mutación · Contar `CLOSED_FALSE_POSITIVE` como hallazgo

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 3 preguntas × 1 corridas = 3 llamadas
- Costo: US$ 0.29 · 36,272 tokens de entrada y 3,562 de salida
- Latencia: p50 14.8 s · p95 14.8 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 2 | 50% | 50% |
| ambigua | 1 | 0% | 0% |

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
| ambiguedad_no_detectada | 1 | el prompt y sus ejemplos de ambigüedad |

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `a-008` | palabra_con_dos_poblaciones | banco_andino | 0/1 | eligió 11704, que no es ninguna de las lecturas (5404, 355) |
| `c-005` | ciclo_de_vida_con_exclusiones | banco_andino | 0/1 | estado `RESPONDIDA`, esperaba RESPONDIDA_CON_SUPUESTO |
| `c-006` | perilla_de_escalado_apagada | fintech_cuyo | 1/1 | — |
