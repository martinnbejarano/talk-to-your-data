-- 09 · Trampas 8, 9 y 10, más las preguntas 4, 5 y 7 del enunciado.
-- El vínculo alerta↔caso es el entregable obligatorio del hito.

\echo '--- 09.1 · trampa 8: estados de alerta y su ciclo de vida ---'
SELECT status, count(*) AS filas,
       count(*) FILTER (WHERE first_reviewed_at IS NULL) AS sin_revisar,
       count(*) FILTER (WHERE closed_at IS NULL)         AS sin_cerrar,
       count(case_id)                                    AS case_id_poblado
FROM alerts GROUP BY ROLLUP(status) ORDER BY filas DESC;

SELECT severity, count(*) FROM alerts GROUP BY ROLLUP(severity) ORDER BY 2 DESC;

\echo '--- 09.2 · trampa 10: dónde vive (y dónde NO) el vínculo alerta↔caso ---'
-- `alerts.case_id` está 100% en NULL (arriba). La única candidata es
-- `alert_case_links`, que el diccionario no menciona.
SELECT count(*) AS links, count(DISTINCT alert_id) AS alertas_distintas,
       count(DISTINCT case_id) AS casos_distintos,
       count(*) FILTER (WHERE alert_id = case_id) AS con_alert_id_igual_a_case_id
FROM alert_case_links;

-- El tenant del link coincide con el del caso, nunca con el de la alerta.
SELECT (l.tenant_id = a.tenant_id) AS link_vs_alerta,
       (l.tenant_id = c.tenant_id) AS link_vs_caso,
       (a.tenant_id = c.tenant_id) AS alerta_vs_caso,
       count(*)
FROM alert_case_links l JOIN alerts a ON a.id=l.alert_id JOIN cases c ON c.id=l.case_id
GROUP BY 1,2,3 ORDER BY 4 DESC;

-- Los únicos links "sanos" son los del tenant que posee los ids más bajos de
-- las dos tablas. Es coincidencia de rangos de id, no un vínculo real.
SELECT l.tenant_id, count(*) FILTER (WHERE l.tenant_id = a.tenant_id) AS sanos, count(*) AS total
FROM alert_case_links l JOIN alerts a ON a.id=l.alert_id
GROUP BY 1 ORDER BY 1 LIMIT 12;

\echo '--- 09.3 · trampa 9: casos sin cerrar y las tres cuentas del promedio ---'
SELECT tenant_id,
       count(*) AS casos,
       count(*) FILTER (WHERE closed_at IS NULL) AS sin_cerrar,
       round(100.0*count(*) FILTER (WHERE closed_at IS NULL)/count(*),1) AS pct_sin_cerrar,
       round(avg(EXTRACT(epoch FROM closed_at-opened_at)/86400)::numeric,2)
           AS dias_solo_cerrados,
       round(avg(EXTRACT(epoch FROM coalesce(closed_at,'2026-06-01')-opened_at)/86400)::numeric,2)
           AS dias_contando_abiertos_hasta_hoy,
       round(avg(EXTRACT(epoch FROM coalesce(closed_at-opened_at, interval '0'))/86400)::numeric,2)
           AS dias_contando_abiertos_como_cero
FROM cases WHERE tenant_id IN (3, 14) GROUP BY 1 ORDER BY 1;

SELECT status, count(*) AS filas,
       count(*) FILTER (WHERE closed_at IS NULL) AS sin_closed_at,
       count(outcome) AS con_outcome
FROM cases GROUP BY ROLLUP(status) ORDER BY filas DESC;

SELECT outcome, count(*) FROM cases GROUP BY ROLLUP(outcome) ORDER BY 2 DESC;

\echo '--- 09.4 · pregunta 4: alertas fuera del SLA de revisión ---'
-- El SLA vive en tenant_config, en horas, y varía por institución. Son dos
-- poblaciones distintas: las que siguen sin revisar y vencieron, y las que se
-- revisaron pero tarde.
WITH sla AS (
    SELECT DISTINCT ON (tenant_id) tenant_id, (value #>> '{}')::int AS h
    FROM tenant_config WHERE key='review_sla_hours' AND effective_from_date <= '2026-06-01'
    ORDER BY tenant_id, effective_from_date DESC)
SELECT s.h AS sla_horas, count(DISTINCT a.tenant_id) AS tenants,
       count(*) FILTER (WHERE a.first_reviewed_at IS NULL
                          AND '2026-06-01'::timestamptz - a.triggered_at > (s.h||' hours')::interval)
           AS sin_revisar_vencidas,
       count(*) FILTER (WHERE a.first_reviewed_at IS NOT NULL
                          AND a.first_reviewed_at - a.triggered_at > (s.h||' hours')::interval)
           AS revisadas_tarde
FROM alerts a JOIN sla s ON s.tenant_id=a.tenant_id
GROUP BY 1 ORDER BY 1;

\echo '--- 09.5 · pregunta 5: hallazgos reales del último trimestre calendario ---'
SELECT tenant_id,
       count(*) FILTER (WHERE status='CLOSED_TRUE_POSITIVE')                        AS tp,
       count(*) FILTER (WHERE status='ESCALATED')                                   AS escaladas,
       count(*) FILTER (WHERE status IN ('CLOSED_TRUE_POSITIVE','ESCALATED'))       AS tp_mas_escaladas,
       count(*) FILTER (WHERE status='CLOSED_FALSE_POSITIVE')                       AS fp,
       count(*)                                                                     AS todas
FROM alerts
WHERE triggered_at >= '2026-01-01' AND triggered_at < '2026-04-01' AND tenant_id IN (3, 14)
GROUP BY 1 ORDER BY 1;
