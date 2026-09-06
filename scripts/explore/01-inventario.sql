-- 01 · Inventario del esquema, sin escanear ni una fila de datos.
-- Todo sale del catálogo de Postgres, que es instantáneo. Tarea 1 de H1.

\echo '--- 01.1 · tablas: volumen aproximado y tamaño ---'
SELECT c.relname AS tabla,
       c.reltuples::bigint AS filas_aprox,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS tamano,
       EXISTS (SELECT 1 FROM pg_attribute a
               WHERE a.attrelid=c.oid AND a.attname='tenant_id' AND a.attnum>0) AS tiene_tenant_id,
       EXISTS (SELECT 1 FROM pg_attribute a
               WHERE a.attrelid=c.oid AND a.attname='deleted_at' AND a.attnum>0) AS tiene_soft_delete
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind='r'
ORDER BY pg_total_relation_size(c.oid) DESC;

\echo '--- 01.2 · columnas, tipos y nullability ---'
SELECT c.relname AS tabla, a.attname AS columna,
       format_type(a.atttypid, a.atttypmod) AS tipo,
       NOT a.attnotnull AS nullable
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
WHERE n.nspname='public' AND c.relkind='r'
ORDER BY c.relname, a.attnum;

\echo '--- 01.3 · índices reales ---'
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname='public' ORDER BY tablename, indexname;

\echo '--- 01.4 · constraints: los CHECK son los enums, las FK son los vínculos ---'
-- El diccionario dice que los enums son TEXT con CHECK (... IN (...)). Leer la
-- definición de la constraint da los valores permitidos sin un SELECT DISTINCT
-- sobre decenas de millones de filas.
SELECT rel.relname AS tabla, con.contype AS tipo, con.conname AS nombre,
       pg_get_constraintdef(con.oid) AS definicion
FROM pg_constraint con
JOIN pg_class rel ON rel.oid=con.conrelid
JOIN pg_namespace n ON n.oid=rel.relnamespace
WHERE n.nspname='public'
ORDER BY con.contype, rel.relname, con.conname;
