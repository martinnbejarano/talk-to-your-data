# Mutación · Sacar `deleted_at IS NULL` de riesgo alto

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 3 preguntas × 1 corridas = 3 llamadas
- Costo: US$ 0.34 · 38,332 tokens de entrada y 4,839 de salida
- Latencia: p50 18.2 s · p95 18.2 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 3 | 100% | 100% |

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
| `c-002` | umbral_versionado_por_institucion | banco_andino | 1/1 | — |
| `c-003` | perilla_de_pep_apagada | fintech_cuyo | 1/1 | — |
| `c-013` | sinonimo_del_dominio | banco_andino | 1/1 | — |
