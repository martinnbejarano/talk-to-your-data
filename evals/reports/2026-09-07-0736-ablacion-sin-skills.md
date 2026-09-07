# Ablación · el agente sin definiciones curadas

- Modelo: `gpt-5.5-2026-04-23` · fecha de corte `2026-06-01`
- 3 preguntas × 1 corridas = 3 llamadas
- Costo: US$ 0.36 · 35,099 tokens de entrada y 6,059 de salida
- Latencia: p50 21.6 s · p95 21.6 s

## Acierto por categoría

| Categoría | Preguntas | Pass@1 | Pass^1 |
|---|---|---|---|
| contestable | 3 | 0% | 0% |

## Las que bloquean, y las que avisan

| Métrica | Valor | Qué significa |
|---|---|---|
| **Fugas cross-tenant** | **0** | Cualquier valor distinto de 0 bloquea la entrega |
| Falsa ambigüedad | 0 | Repreguntas sobre preguntas que eran claras |
| Timeouts | 0 | Consultas que no entraron en el plazo |
| Rechazos del gate | 1 | Planes malos reescritos; cada uno cuesta el 70 % de una pregunta |

## Fallas por tipo

| Tipo | Corridas | Dónde se arregla |
|---|---|---|
| skill_no_consultada | 3 | el prompt o la descripción de la tool |

## Pregunta por pregunta

| id | clase | inst. | acierto | qué pasó |
|---|---|---|---|---|
| `c-002` | umbral_versionado_por_institucion | banco_andino | 0/1 | valor 10590, esperaba 7859; la derivación no trae los escalones total, activos, con_evaluacion, por_score, por_marca, por_pep, riesgo_alto; no declaró las definiciones riesgo_alto |
| `c-003` | perilla_de_pep_apagada | fintech_cuyo | 0/1 | la derivación no trae los escalones total, activos, con_evaluacion, por_score, por_marca, por_pep, riesgo_alto; no declaró las definiciones riesgo_alto |
| `c-013` | sinonimo_del_dominio | banco_andino | 0/1 | valor 7221, esperaba 7859; la derivación no trae los escalones total, activos, con_evaluacion, por_score, por_marca, por_pep, riesgo_alto; no declaró las definiciones riesgo_alto |
