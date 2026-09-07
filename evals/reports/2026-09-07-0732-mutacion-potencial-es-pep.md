# Mutación · Contar `POTENTIAL_HIT` como PEP

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 2 preguntas × 1 corridas = 2 llamadas
- Costo: US$ 0.22 · 25,444 tokens de entrada y 3,001 de salida
- Latencia: p50 19.1 s · p95 17.3 s

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
| `a-005` | umbral_de_confirmacion_indefinido | banco_andino | 1/1 | — |
| `c-002` | umbral_versionado_por_institucion | banco_andino | 0/1 | valor 9113, esperaba 7859; escalones con otro número: por_pep=1968 (esperaba 660), riesgo_alto=9113 (esperaba 7859) |
