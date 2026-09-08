# Ablación · sólo la definición de `cliente_onboardeado`

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 2 preguntas × 1 corridas = 2 llamadas
- Costo: US$ 0.21 · 28,726 tokens de entrada y 2,319 de salida
- Latencia: p50 17.2 s · p95 9.2 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 1 | 100% | 100% |
| ambigua | 1 | 100% | 100% |

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
| `a-002` | universo_indefinido | banco_andino | 1/1 | — |
| `c-001` | conteo_simple_con_periodo | banco_andino | 1/1 | — |
