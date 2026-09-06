-- 11 · Tarea 2: caracterizar las nueve tablas que el diccionario no documenta.
-- La conclusión "esta tabla no la necesito" también cuenta: evita joins de más.

\echo '--- 11.1 · integridad de facto: ¿los hijos apuntan a un padre del MISMO tenant? ---'
-- No hay ni una foreign key en el esquema (ver 01.4), así que nada lo garantiza.
SELECT 'transactions.client_id' AS relacion,
       count(*) FILTER (WHERE c.id IS NULL) AS huerfanos, count(*) AS total
  FROM transactions t LEFT JOIN clients c ON c.id=t.client_id AND c.tenant_id=t.tenant_id
UNION ALL SELECT 'alerts.client_id', count(*) FILTER (WHERE c.id IS NULL AND a.client_id IS NOT NULL), count(*)
  FROM alerts a LEFT JOIN clients c ON c.id=a.client_id AND c.tenant_id=a.tenant_id
UNION ALL SELECT 'screenings.client_id', count(*) FILTER (WHERE c.id IS NULL), count(*)
  FROM screenings s LEFT JOIN clients c ON c.id=s.client_id AND c.tenant_id=s.tenant_id
UNION ALL SELECT 'risk_assessments.client_id', count(*) FILTER (WHERE c.id IS NULL), count(*)
  FROM risk_assessments r LEFT JOIN clients c ON c.id=r.client_id AND c.tenant_id=r.tenant_id
UNION ALL SELECT 'client_documents.client_id', count(*) FILTER (WHERE c.id IS NULL), count(*)
  FROM client_documents d LEFT JOIN clients c ON c.id=d.client_id AND c.tenant_id=d.tenant_id
UNION ALL SELECT 'client_risk_overrides.client_id', count(*) FILTER (WHERE c.id IS NULL), count(*)
  FROM client_risk_overrides o LEFT JOIN clients c ON c.id=o.client_id AND c.tenant_id=o.tenant_id
UNION ALL SELECT 'notes.entity_id (entity=client)', count(*) FILTER (WHERE c.id IS NULL), count(*)
  FROM notes n LEFT JOIN clients c ON c.id=n.entity_id AND c.tenant_id=n.tenant_id WHERE n.entity='client'
UNION ALL SELECT 'sar_reports.case_id', count(*) FILTER (WHERE k.id IS NULL), count(*)
  FROM sar_reports s LEFT JOIN cases k ON k.id=s.case_id AND k.tenant_id=s.tenant_id
ORDER BY 1;

\echo '--- 11.2 · transaction_counterparties: el puntero es al azar ---'
-- Si la tasa de links "sanos" coincide con la cuota de transacciones del tenant,
-- el transaction_id no apunta a nada: acierta por azar.
SELECT round(100.0*(SELECT count(*) FROM transaction_counterparties tc
                    JOIN transactions t ON t.id=tc.transaction_id AND t.tenant_id=tc.tenant_id)
             /(SELECT count(*) FROM transaction_counterparties),2) AS pct_links_sanos,
       round(100.0*(SELECT count(*) FROM transactions WHERE tenant_id=1)
             /(SELECT count(*) FROM transactions),2)               AS pct_tx_del_tenant_1;

-- Además la tabla es redundante: `transactions.counterparty_name` nunca es NULL.
SELECT count(*) FILTER (WHERE counterparty_name IS NULL) AS tx_sin_contraparte,
       count(*) AS tx FROM transactions WHERE tenant_id=3;

\echo '--- 11.3 · sar_reports: 1 a 1 con los casos reportados a la UIF ---'
SELECT count(*) AS sar, count(DISTINCT case_id) AS casos_distintos FROM sar_reports;
SELECT c.status, count(*) FROM sar_reports s JOIN cases c ON c.id=s.case_id GROUP BY 1;

\echo '--- 11.4 · users: cases.assigned_to apunta a un analista que a veces no existe ---'
SELECT count(*) AS casos, count(assigned_to) AS con_asignado,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM users u
                                      WHERE u.email=c.assigned_to AND u.tenant_id=c.tenant_id))
           AS resuelve_a_un_user_del_tenant,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM users u WHERE u.email=c.assigned_to))
           AS resuelve_a_un_user_de_cualquier_tenant
FROM cases c;

SELECT count(*) AS users, count(DISTINCT tenant_id) AS tenants_con_users,
       count(DISTINCT role) AS roles, count(*) FILTER (WHERE NOT is_active) AS inactivos
FROM users;

\echo '--- 11.5 · todas las metadata JSONB salvo dos están vacías ---'
SELECT 'alerts' AS tabla, count(*) FILTER (WHERE metadata='{}'::jsonb) AS vacias, count(*) AS total FROM alerts
UNION ALL SELECT 'cases', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM cases
UNION ALL SELECT 'risk_assessments', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM risk_assessments
UNION ALL SELECT 'sar_reports', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM sar_reports
UNION ALL SELECT 'notes', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM notes
UNION ALL SELECT 'audit_log', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM audit_log
UNION ALL SELECT 'clients', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM clients
UNION ALL SELECT 'transactions', count(*) FILTER (WHERE metadata='{}'::jsonb), count(*) FROM transactions
ORDER BY 1;

\echo '--- 11.6 · costo de tocar las tablas sin índice por tenant ---'
-- Ninguna de las nueve tiene índice: cualquier filtro por tenant_id es seq scan.
-- El gate de EXPLAIN de D-06 no puede rechazar seq scan a secas.
EXPLAIN (COSTS) SELECT count(*) FROM client_documents WHERE tenant_id=3;
EXPLAIN (COSTS) SELECT count(*) FROM audit_log        WHERE tenant_id=3;
EXPLAIN (COSTS) SELECT count(*) FROM notes            WHERE tenant_id=3;

\echo '--- 11.7 · notes.body no es texto libre: es relleno ---'
SELECT count(DISTINCT body) AS bodies_distintos, count(*) AS filas FROM notes;

\echo '--- 11.8 · alert_rules sí funciona como catálogo ---'
-- El contraste con la sección de screenings: el monitoreo AML produce alertas de
-- sanciones y de PEP, aunque el screening contra listas sólo tenga PEP_AR.
SELECT a.rule_code, r.description IS NOT NULL AS esta_en_el_catalogo, count(*)
FROM alerts a LEFT JOIN alert_rules r ON r.rule_code = a.rule_code
GROUP BY 1,2 ORDER BY 3 DESC;
