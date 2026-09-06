-- 04 · Trampa 2: ¿el AS_OF = 2026-06-01 se sostiene en TODA la base?
-- H0 lo verificó sobre `transactions` y dio verde. Acá se pregunta lo mismo
-- sobre cada columna de fecha del esquema, que es donde aparecen las excepciones.

\echo '--- 04.1 · rango real de cada columna de fecha ---'
SELECT 'alerts.triggered_at' AS columna, min(triggered_at)::date, max(triggered_at)::date FROM alerts
UNION ALL SELECT 'alerts.closed_at', min(closed_at)::date, max(closed_at)::date FROM alerts
UNION ALL SELECT 'cases.opened_at', min(opened_at)::date, max(opened_at)::date FROM cases
UNION ALL SELECT 'cases.closed_at', min(closed_at)::date, max(closed_at)::date FROM cases
UNION ALL SELECT 'clients.created_at', min(created_at)::date, max(created_at)::date FROM clients
UNION ALL SELECT 'clients.onboarded_at', min(onboarded_at)::date, max(onboarded_at)::date FROM clients
UNION ALL SELECT 'clients.deleted_at', min(deleted_at)::date, max(deleted_at)::date FROM clients
UNION ALL SELECT 'screenings.screened_at', min(screened_at)::date, max(screened_at)::date FROM screenings
UNION ALL SELECT 'risk_assessments.assessed_at', min(assessed_at)::date, max(assessed_at)::date FROM risk_assessments
UNION ALL SELECT 'sar_reports.reported_date', min(reported_date), max(reported_date) FROM sar_reports
UNION ALL SELECT 'audit_log.at', min(at)::date, max(at)::date FROM audit_log
UNION ALL SELECT 'client_documents.uploaded_at', min(uploaded_at)::date, max(uploaded_at)::date FROM client_documents
UNION ALL SELECT 'client_documents.expires_date', min(expires_date), max(expires_date) FROM client_documents
UNION ALL SELECT 'transactions.tx_date', min(tx_date), max(tx_date) FROM transactions
UNION ALL SELECT 'tenants.created_at', min(created_at)::date, max(created_at)::date FROM tenants
ORDER BY 1;

\echo '--- 04.2 · cuántas filas caen DESPUÉS del AS_OF ---'
SELECT 'clients.deleted_at' AS columna, count(*) FROM clients WHERE deleted_at > '2026-06-01'
UNION ALL SELECT 'client_documents.uploaded_at', count(*) FROM client_documents WHERE uploaded_at > '2026-06-01'
UNION ALL SELECT 'client_documents.expires_date', count(*) FROM client_documents WHERE expires_date > '2026-06-01'
UNION ALL SELECT 'clients.created_at', count(*) FROM clients WHERE created_at > '2026-06-01'
UNION ALL SELECT 'audit_log.at', count(*) FROM audit_log WHERE at > '2026-06-01'
ORDER BY 1;
