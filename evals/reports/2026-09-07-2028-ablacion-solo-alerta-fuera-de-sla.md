# Ablación · sólo la definición de `alerta_fuera_de_sla`

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 2 preguntas × 1 corridas = 2 llamadas
- Costo: US$ 0.2 · 24,798 tokens de entrada y 2,531 de salida
- Latencia: p50 17.3 s · p95 15.0 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 2 | 100% | 100% |

## Las que bloquean, y las que avisan

| Métrica | Valor | Qué significa |
|---|---|---|
| **Fugas cross-tenant** | **0** | Cualquier valor distinto de 0 bloquea la entrega |
| Falsa ambigüedad | 0 | Repreguntas sobre preguntas que eran claras |
| Timeouts | 0 | Consultas que no entraron en el plazo |
| Rechazos del gate | 0 | Planes malos reescritos; cada uno cuesta el 70 % de una pregunta |

## Fallas por tipo

Ninguna.

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `c-007` | calculo_temporal_contra_config | banco_andino | 1/1 | — |
| `c-008` | mitad_vacia_de_la_definicion | fintech_cuyo | 1/1 | — |
