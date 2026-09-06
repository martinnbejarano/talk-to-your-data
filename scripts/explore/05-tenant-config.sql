-- 05 · Trampa 4 (config versionada) y trampa 14 (instituciones de baja).
-- La matriz completa de parámetros de negocio por tenant: es la tabla que hay
-- que tener a mano para leer cualquier número del resto de la exploración.

\echo '--- 05.1 · las claves que existen de verdad ---'
SELECT key, count(*) AS filas, count(DISTINCT tenant_id) AS tenants,
       count(*) FILTER (WHERE effective_from_date > '2026-06-01') AS futuras,
       min(effective_from_date), max(effective_from_date),
       string_agg(DISTINCT value #>> '{}', ', ' ORDER BY value #>> '{}') AS valores
FROM tenant_config GROUP BY key ORDER BY key;

\echo '--- 05.2 · las únicas filas versionadas de toda la base ---'
SELECT tenant_id, key, effective_from_date, value #>> '{}' AS valor
FROM tenant_config
WHERE (tenant_id, key) IN (SELECT tenant_id, key FROM tenant_config GROUP BY 1,2 HAVING count(*) > 1)
ORDER BY tenant_id, key, effective_from_date;

\echo '--- 05.3 · matriz de configuración vigente al AS_OF, por institución ---'
SELECT t.id, t.slug, t.kind, t.is_active,
       max(CASE WHEN cv.key='high_risk_score_threshold' THEN cv.v END)::int  AS umbral,
       max(CASE WHEN cv.key='high_risk_score_threshold' THEN cv.versiones END) AS umbral_vers,
       max(CASE WHEN cv.key='review_sla_hours' THEN cv.v END)::int            AS sla_h,
       max(CASE WHEN cv.key='fiscal_year_start_month' THEN cv.v END)::int     AS mes_fiscal,
       max(CASE WHEN cv.key='pep_is_high_risk' THEN cv.v END)                 AS pep_alto,
       max(CASE WHEN cv.key='escalated_counts_as_finding' THEN cv.v END)      AS escalada_hallazgo
FROM tenants t
JOIN (SELECT DISTINCT ON (tenant_id,key) tenant_id, key, value #>> '{}' AS v,
             count(*) OVER (PARTITION BY tenant_id,key) AS versiones
      FROM tenant_config WHERE effective_from_date <= '2026-06-01'
      ORDER BY tenant_id, key, effective_from_date DESC) cv ON cv.tenant_id=t.id
GROUP BY 1,2,3,4 ORDER BY 1;

\echo '--- 05.4 · cuánto cambia el número si se toma el umbral viejo (tenant 1) ---'
SELECT u AS umbral, count(*) FILTER (WHERE r.score >= u) AS clientes_por_score
FROM (VALUES (70),(80)) AS t(u), clients c
JOIN risk_assessments r ON r.tenant_id=c.tenant_id AND r.client_id=c.id
                       AND r.is_current AND r.deleted_at IS NULL
WHERE c.tenant_id=1 AND c.deleted_at IS NULL
GROUP BY u ORDER BY u;
