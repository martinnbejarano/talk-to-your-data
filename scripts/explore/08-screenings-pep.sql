-- 08 · Trampa 7 y pregunta 6 del enunciado ("¿alguno de nuestros clientes es PEP?").
-- Forma real del JSONB `metadata` de screenings y las tres definiciones
-- candidatas de "PEP", que dan números muy distintos.

\echo '--- 08.1 · distribución de result y presencia de las claves del JSONB ---'
SELECT result, count(*) AS filas,
       count(*) FILTER (WHERE metadata ? 'is_pep')            AS tiene_is_pep,
       count(*) FILTER (WHERE metadata->>'is_pep' = 'true')   AS is_pep_true,
       count(*) FILTER (WHERE metadata->>'is_pep' = 'false')  AS is_pep_false,
       count(*) FILTER (WHERE metadata ? 'matches')           AS tiene_matches
FROM screenings GROUP BY ROLLUP(result) ORDER BY filas DESC;

\echo '--- 08.2 · qué listas aparecen adentro de matches ---'
-- El diccionario habla de sanciones y PEPs. La pregunta es cuáles existen en la data.
SELECT s.result, (s.metadata ? 'is_pep') AS tiene_is_pep,
       m->>'watchlist_code' AS lista, count(*)
FROM screenings s, jsonb_array_elements(s.metadata->'matches') m
WHERE s.metadata ? 'matches'
GROUP BY 1,2,3 ORDER BY 1,2,4 DESC;

SELECT jsonb_array_length(metadata->'matches') AS matches_por_screening, count(*)
FROM screenings WHERE metadata ? 'matches' GROUP BY 1 ORDER BY 1;

\echo '--- 08.3 · las tres definiciones candidatas, en clientes distintos ---'
SELECT tenant_id,
       count(DISTINCT client_id) FILTER (WHERE metadata->>'is_pep'='true')
           AS def_a_is_pep_suelto,
       count(DISTINCT client_id) FILTER (WHERE result='CONFIRMED_HIT')
           AS def_b_hit_confirmado,
       count(DISTINCT client_id) FILTER (WHERE result='CONFIRMED_HIT' AND metadata->>'is_pep'='true')
           AS def_c_confirmado_y_marcado
FROM screenings WHERE tenant_id IN (3, 14) GROUP BY 1 ORDER BY 1;
