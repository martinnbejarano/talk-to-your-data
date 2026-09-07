# Mutación · Resolver los períodos con `now()` en lugar del `AS_OF`

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 6 preguntas × 1 corridas = 6 llamadas
- Costo: US$ 0.83 · 95,336 tokens de entrada y 11,735 de salida
- Latencia: p50 12.3 s · p95 19.4 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 6 | 50% | 50% |

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
| definicion_equivocada | 2 | la skill (H2) |
| numero_no_trazable | 1 | la validación post-hoc (H3) |

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `c-001` | conteo_simple_con_periodo | banco_andino | 1/1 | — |
| `c-004` | agregacion_con_desglose_obligatorio | banco_andino | 0/1 | estado `NO_SE_PUEDE_RESPONDER`, esperaba RESPONDIDA o RESPONDIDA_CON_SUPUESTO |
| `c-005` | ciclo_de_vida_con_exclusiones | banco_andino | 0/1 | estado `RESPONDIDA`, esperaba RESPONDIDA_CON_SUPUESTO |
| `c-007` | calculo_temporal_contra_config | banco_andino | 0/1 | valor 2870, esperaba 9339; escalones con otro número: total=5570 (esperaba 30605), activas=5570 (esperaba 30605), sin_revisar=5570 (esperaba 7199), sin_revisar_vencidas=2870 (esperaba 4499), revisadas_tarde=0 (esperaba 4840), fuera_de_sla=2870 (esperaba 9339) |
| `c-012` | concepto_vecino_que_no_es_hallazgo | fintech_cuyo | 1/1 | — |
| `c-014` | reformulacion_sin_la_palabra_del_concepto | banco_andino | 1/1 | — |
