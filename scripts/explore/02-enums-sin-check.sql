-- 02 · Los enums que NO tienen CHECK, y por eso hay que leer de la data.
-- Complemento de 01.4: siete columnas de texto se comportan como enum sin que
-- ninguna constraint lo declare. Todas viven en tablas que el diccionario no
-- documenta, salvo `cases.outcome`.

\echo '--- 02.1 · valores reales ---'
SELECT 'cases.outcome' AS columna, outcome AS valor, count(*) FROM cases GROUP BY 2
UNION ALL SELECT 'users.role', role, count(*) FROM users GROUP BY 2
UNION ALL SELECT 'client_documents.doc_kind', doc_kind, count(*) FROM client_documents GROUP BY 2
UNION ALL SELECT 'client_risk_overrides.reason', reason, count(*) FROM client_risk_overrides GROUP BY 2
UNION ALL SELECT 'notes.entity', entity, count(*) FROM notes GROUP BY 2
UNION ALL SELECT 'screening_runs.source', source, count(*) FROM screening_runs GROUP BY 2
UNION ALL SELECT 'audit_log.action', action, count(*) FROM audit_log GROUP BY 2
UNION ALL SELECT 'audit_log.entity', entity, count(*) FROM audit_log GROUP BY 2
ORDER BY 1, 3 DESC;

\echo '--- 02.2 · watchlists: catálogo mixto (globales + internas de un tenant) ---'
SELECT id, tenant_id, code, kind FROM watchlists ORDER BY tenant_id NULLS FIRST, code;
