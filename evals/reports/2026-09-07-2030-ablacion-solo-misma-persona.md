# Ablación · sólo la definición de `misma_persona`

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 2 preguntas × 1 corridas = 2 llamadas
- Costo: US$ 0.27 · 33,309 tokens de entrada y 3,330 de salida
- Latencia: p50 23.0 s · p95 14.2 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 1 | 0% | 0% |
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
| `a-007` | legajo_versus_persona | banco_andino | 0/1 | eligió 107313, que no es ninguna de las lecturas (174669, 174342) |
| `c-011` | listado_ademas_del_conteo | banco_andino | 0/1 | valor 634, esperaba 307; contestó sin filas: la pregunta pedía el listado |
