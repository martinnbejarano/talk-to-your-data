-- 07 · transactions: soft-delete, monedas, estados, canales.
-- Trampas 1 (borradas), 5 (no hay FX), 6 (REVERSED no es movimiento efectivo).
--
-- Un solo recorrido de la tabla de 72 M de filas con GROUPING SETS: cuatro
-- distribuciones marginales, el cruce tenant×moneda y el total. Cuatro consultas
-- separadas serían cuatro seq scans de 13 GB.

\echo '--- 07.1 · distribuciones marginales + tenants multi-moneda ---'
WITH g AS (
    SELECT status, currency, direction, channel, tenant_id,
           count(*)                                          AS filas,
           count(*) FILTER (WHERE deleted_at IS NOT NULL)     AS borradas,
           sum(amount) FILTER (WHERE deleted_at IS NULL)      AS monto_vivo
    FROM transactions
    GROUP BY GROUPING SETS ((status), (currency), (direction), (channel),
                            (tenant_id, currency), ())
)
SELECT CASE
           WHEN status    IS NOT NULL THEN 'status'
           WHEN direction IS NOT NULL THEN 'direction'
           WHEN channel   IS NOT NULL THEN 'channel'
           WHEN tenant_id IS NOT NULL THEN 'tenant×currency'
           WHEN currency  IS NOT NULL THEN 'currency'
           ELSE 'TOTAL'
       END AS dimension,
       coalesce(status, direction, channel, currency, '(todas)') AS valor,
       tenant_id,
       filas,
       borradas,
       round(100.0 * borradas / filas, 2) AS pct_borradas,
       monto_vivo
FROM g
WHERE tenant_id IS NULL OR tenant_id IN (1, 8)   -- el par de trabajo de H0
ORDER BY dimension, filas DESC;

\echo '--- 07.2 · ¿cuántas monedas distintas usa cada tenant? ---'
SELECT monedas_distintas, count(*) AS tenants
FROM (SELECT tenant_id, count(DISTINCT currency) AS monedas_distintas
      FROM transactions GROUP BY tenant_id) t
GROUP BY monedas_distintas ORDER BY monedas_distintas;
