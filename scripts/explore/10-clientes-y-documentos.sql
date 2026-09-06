-- 10 · Trampas 11 y 12, y la pregunta 8 del enunciado
-- ("¿qué clientes son probablemente la misma persona?").

\echo '--- 10.1 · trampa 12: aprobados sin fecha de alta ---'
SELECT onboarding_status, count(*) AS filas,
       count(*) FILTER (WHERE deleted_at IS NOT NULL)   AS borradas,
       count(*) FILTER (WHERE onboarded_at IS NULL)     AS sin_onboarded_at,
       count(*) FILTER (WHERE manual_high_risk_flag)    AS marcados_a_mano
FROM clients GROUP BY ROLLUP(onboarding_status) ORDER BY filas DESC;

\echo '--- 10.2 · trampa 11: formatos reales de document_number ---'
SELECT CASE WHEN document_number ~ '^[0-9]+$'                 THEN 'sólo dígitos'
            WHEN document_number ~ '^[0-9]+-[0-9]+-[0-9]+$'   THEN 'con guiones (nn-nnnnnnnn-n)'
            WHEN document_number ~ '[.]'                      THEN 'con puntos'
            WHEN document_number ~ '[ ]'                      THEN 'con espacios'
            ELSE 'otro' END AS formato,
       count(*), count(DISTINCT document_type) AS tipos_de_doc
FROM clients GROUP BY 1 ORDER BY 2 DESC;

\echo '--- 10.3 · cuántos duplicados aparecen al normalizar, y cuántos ya se veían ---'
-- La diferencia entre las dos últimas columnas es exactamente lo que aporta la
-- normalización de D-09: los que sin ella no se detectan.
SELECT tenant_id,
       count(*) AS clientes_vivos,
       count(DISTINCT (document_type, document_number)) AS personas_sin_normalizar,
       count(DISTINCT (document_type, regexp_replace(document_number,'[^0-9A-Za-z]','','g')))
           AS personas_normalizadas
FROM clients WHERE deleted_at IS NULL AND tenant_id IN (3, 14) GROUP BY 1 ORDER BY 1;

\echo '--- 10.4 · el JSONB de clients: la única metadata con contenido real ---'
SELECT k, count(*) FROM clients, jsonb_object_keys(metadata) k GROUP BY 1 ORDER BY 2 DESC;

SELECT metadata->>'source' AS source, metadata->>'manual_review_reason' AS motivo,
       manual_high_risk_flag, count(*)
FROM clients WHERE metadata <> '{}'::jsonb GROUP BY 1,2,3 ORDER BY 4 DESC;
