# Mutación · Tomar el `effective_from_date` más viejo en vez del vigente

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 3 preguntas × 1 corridas = 3 llamadas
- Costo: US$ 0.58 · 60,726 tokens de entrada y 9,053 de salida
- Latencia: p50 17.2 s · p95 17.2 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 3 | 67% | 67% |

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
| numero_no_trazable | 1 | la validación post-hoc (H3) |

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `c-002` | umbral_versionado_por_institucion | banco_andino | 1/1 | — |
| `c-004` | agregacion_con_desglose_obligatorio | banco_andino | 0/1 | estado `NO_SE_PUEDE_RESPONDER`, esperaba RESPONDIDA o RESPONDIDA_CON_SUPUESTO |
| `c-013` | sinonimo_del_dominio | banco_andino | 1/1 | — |
