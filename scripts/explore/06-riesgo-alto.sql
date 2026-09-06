-- 06 · Trampa 15, la más importante del hito: ¿cuánto se contradicen
-- `score >= umbral` y `manual_high_risk_flag`?
-- La respuesta define si "riesgo alto" es una unión de dos fuentes o si una es
-- residual. El número concreto va a la skill de H2 y a la respuesta del sistema.

\echo '--- 06.1 · solapamiento en el par de trabajo ---'
WITH umbral AS (
    SELECT DISTINCT ON (tenant_id) tenant_id, (value #>> '{}')::int AS v
    FROM tenant_config
    WHERE key='high_risk_score_threshold' AND effective_from_date <= '2026-06-01'
    ORDER BY tenant_id, effective_from_date DESC),
base AS (
    SELECT c.tenant_id, c.id, (r.score >= u.v) AS por_score, c.manual_high_risk_flag AS por_flag
    FROM clients c
    JOIN umbral u ON u.tenant_id=c.tenant_id
    JOIN risk_assessments r ON r.tenant_id=c.tenant_id AND r.client_id=c.id
                           AND r.is_current AND r.deleted_at IS NULL
    WHERE c.deleted_at IS NULL AND c.tenant_id IN (3, 14))
SELECT tenant_id,
       count(*)                                           AS clientes_vivos,
       count(*) FILTER (WHERE por_score)                  AS por_score,
       count(*) FILTER (WHERE por_flag)                   AS por_marca_manual,
       count(*) FILTER (WHERE por_score AND por_flag)     AS ambos,
       count(*) FILTER (WHERE por_score OR por_flag)      AS union_riesgo_alto,
       round(100.0*count(*) FILTER (WHERE por_flag)/count(*) FILTER (WHERE por_score OR por_flag),1)
                                                          AS pct_que_aporta_la_marca
FROM base GROUP BY 1 ORDER BY 1;

\echo '--- 06.2 · el solapamiento en las 40 instituciones ---'
-- Si el resultado es 0, las dos fuentes son disjuntas por construcción y
-- "riesgo alto" es literalmente la suma, no una unión con intersección.
WITH umbral AS (
    SELECT DISTINCT ON (tenant_id) tenant_id, (value #>> '{}')::int AS v
    FROM tenant_config
    WHERE key='high_risk_score_threshold' AND effective_from_date <= '2026-06-01'
    ORDER BY tenant_id, effective_from_date DESC)
SELECT count(*) FILTER (WHERE r.score >= u.v AND c.manual_high_risk_flag) AS ambos,
       count(*) FILTER (WHERE c.manual_high_risk_flag)                    AS por_marca_manual,
       count(*) FILTER (WHERE r.score >= u.v)                             AS por_score,
       max(r.score) FILTER (WHERE c.manual_high_risk_flag)                AS score_max_de_los_marcados,
       min(u.v) AS umbral_min, max(u.v) AS umbral_max
FROM clients c
JOIN umbral u ON u.tenant_id=c.tenant_id
JOIN risk_assessments r ON r.tenant_id=c.tenant_id AND r.client_id=c.id
                       AND r.is_current AND r.deleted_at IS NULL
WHERE c.deleted_at IS NULL;

\echo '--- 06.3 · la tercera fuente candidata: client_risk_overrides ---'
-- No documentada. La pregunta es si sirve para definir riesgo: tiene `reason`
-- pero ninguna columna con el valor al que se overridea.
SELECT reason, count(*) AS filas, count(DISTINCT client_id) AS clientes FROM client_risk_overrides
GROUP BY ROLLUP(reason) ORDER BY filas DESC;

SELECT c.manual_high_risk_flag, count(*) AS overrides
FROM client_risk_overrides o JOIN clients c ON c.id=o.client_id AND c.tenant_id=o.tenant_id
GROUP BY 1 ORDER BY 2 DESC;

\echo '--- 06.4 · trampa 13: ¿una sola evaluación vigente por cliente? ---'
SELECT vigentes_por_cliente, count(*) AS clientes FROM (
    SELECT client_id, count(*) FILTER (WHERE is_current) AS vigentes_por_cliente
    FROM risk_assessments GROUP BY tenant_id, client_id) t
GROUP BY 1 ORDER BY 1;
