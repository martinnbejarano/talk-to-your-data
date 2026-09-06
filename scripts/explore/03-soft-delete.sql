-- 03 · Trampa 1: cuánto pesa el soft-delete, tabla por tabla.
-- El diccionario dice que "las filas borradas siguen en la tabla" como si fuera
-- parejo. La pregunta es en cuáles, y cuánto.

\echo '--- 03.1 · proporción de borradas por tabla ---'
SELECT 'alerts' AS tabla, count(*) FILTER (WHERE deleted_at IS NOT NULL) AS borradas, count(*) AS total FROM alerts
UNION ALL SELECT 'cases', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM cases
UNION ALL SELECT 'client_documents', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM client_documents
UNION ALL SELECT 'client_risk_overrides', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM client_risk_overrides
UNION ALL SELECT 'clients', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM clients
UNION ALL SELECT 'risk_assessments', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM risk_assessments
UNION ALL SELECT 'screenings', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM screenings
UNION ALL SELECT 'transactions', count(*) FILTER (WHERE deleted_at IS NOT NULL), count(*) FROM transactions
ORDER BY 1;

\echo '--- 03.2 · el borrado de un cliente NO borra su historia de scoring ---'
-- De las 34.382 evaluaciones borradas, ¿cuántas son la vigente? Si son todas,
-- las evaluaciones históricas de un cliente borrado siguen vivas, y filtrar sólo
-- por `risk_assessments.deleted_at IS NULL` no alcanza para excluirlo.
SELECT count(*) AS ra_borradas,
       count(*) FILTER (WHERE is_current) AS de_esas_vigentes
FROM risk_assessments WHERE deleted_at IS NOT NULL;

SELECT count(*) AS ra_vivas_de_clientes_borrados
FROM risk_assessments r JOIN clients c ON c.id=r.client_id AND c.tenant_id=r.tenant_id
WHERE r.deleted_at IS NULL AND c.deleted_at IS NOT NULL;

\echo '--- 03.3 · los marcados a mano se borran 13 veces más que el promedio ---'
SELECT count(*) AS marcados,
       count(*) FILTER (WHERE deleted_at IS NULL) AS marcados_vivos,
       count(*) FILTER (WHERE metadata ? 'manual_review_reason') AS con_motivo_en_metadata
FROM clients WHERE manual_high_risk_flag;
