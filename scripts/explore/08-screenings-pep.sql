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

\echo '--- 08.4 · el eje que faltaba: PEP "alguna vez" vs. PEP "vigente" ---'
-- Cada cliente tiene 4 o 5 screenings a lo largo del tiempo y NO hay un
-- `is_current` como en risk_assessments. Un cliente puede haber dado
-- CONFIRMED_HIT en 2025 y NO_HIT en su screening más reciente.
SELECT screenings_por_cliente, count(*) AS clientes FROM (
    SELECT client_id, count(*) AS screenings_por_cliente
    FROM screenings WHERE tenant_id = 3 GROUP BY 1) t
GROUP BY 1 ORDER BY 1;

-- De los que alguna vez dieron hit confirmado, ¿qué dice el screening vigente?
SELECT ultimo_result, count(*) FROM (
    SELECT tenant_id, client_id, (array_agg(result ORDER BY screened_at DESC))[1] AS ultimo_result
    FROM screenings WHERE tenant_id IN (3, 14) GROUP BY 1,2
    HAVING bool_or(result = 'CONFIRMED_HIT')) t
GROUP BY 1 ORDER BY 2 DESC;

-- Ningún cliente se contradice (hit confirmado y descartado a la vez), y no hay
-- empates de fecha: "el screening vigente" está bien definido.
SELECT count(*) AS clientes_con_empate_en_la_fecha_mas_reciente FROM (
    SELECT tenant_id, client_id FROM screenings s
    WHERE tenant_id IN (3, 14)
      AND screened_at = (SELECT max(screened_at) FROM screenings x
                         WHERE x.tenant_id = s.tenant_id AND x.client_id = s.client_id)
    GROUP BY 1,2 HAVING count(*) > 1) t;

-- Las cuatro definiciones, en clientes distintos.
WITH ultimo AS (
    SELECT DISTINCT ON (tenant_id, client_id) tenant_id, client_id, result, metadata
    FROM screenings WHERE tenant_id IN (3, 14)
    ORDER BY tenant_id, client_id, screened_at DESC, id DESC)
SELECT tenant_id,
       count(*) FILTER (WHERE result = 'CONFIRMED_HIT') AS vigente_confirmado,
       count(*) FILTER (WHERE result = 'CONFIRMED_HIT' AND metadata->>'is_pep' = 'true')
           AS vigente_confirmado_y_marcado
FROM ultimo GROUP BY 1 ORDER BY 1;
