-- bootstrap.sql · el blindaje de la base
--
-- La superficie de permisos completa del agente en un solo script: rol de sólo
-- lectura con su propio `statement_timeout`, GRANT recortados, y RLS por
-- institución sobre toda tabla con `tenant_id`.
--
-- Se aplica DESPUÉS de cada restore y no una sola vez al instalar: el
-- `pg_restore --clean` se lleva puestos los GRANT y las policies. Por eso es
-- idempotente de punta a punta y se invoca como `core.db.apply_bootstrap()`,
-- que le pasa el password por `SET LOCAL bootstrap.agent_ro_password` — el
-- script no lleva credenciales.


-- 1. El rol del agente, y el límite de tiempo que viaja con él
--
-- NOBYPASSRLS es el default, pero se escribe: es la propiedad de la que depende
-- todo el hito. El ALTER corre siempre, no sólo cuando el rol se crea, para
-- volver a afirmar los atributos si alguien los aflojó a mano.
DO $bootstrap$
DECLARE
    password_del_rol text := NULLIF(current_setting('bootstrap.agent_ro_password', true), '');
BEGIN
    IF password_del_rol IS NULL THEN
        RAISE EXCEPTION
            'Falta el parámetro de sesión bootstrap.agent_ro_password. '
            'Este script no lleva credenciales: el llamador tiene que hacer '
            'SET LOCAL bootstrap.agent_ro_password = ... antes de aplicarlo '
            '(AGENT_RO_PASSWORD en el .env).';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
        EXECUTE format('CREATE ROLE agent_ro LOGIN PASSWORD %L', password_del_rol);
    END IF;

    EXECUTE format(
        'ALTER ROLE agent_ro WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB '
        'NOCREATEROLE NOREPLICATION PASSWORD %L',
        password_del_rol
    );
END
$bootstrap$;

-- El límite viaja con el rol y repite los 15s que el `docker-compose.yml` ya
-- pone en el servidor: así rige cualquier conexión de `agent_ro`, venga de donde
-- venga. Cuando muerde, la consulta muere con SQLSTATE 57014, que es el feedback
-- accionable de H3 (ver NOTES/01-limites-y-planes.md).
ALTER ROLE agent_ro SET statement_timeout = '15s';


-- 2. La superficie de permisos: leer, y nada más
--
-- El REVOKE va primero y no es ceremonia: sin él este bloque sólo puede
-- *agregar*, y un GRANT hecho a mano sobreviviría para siempre.
--
-- Lo que NO se otorga, porque la ausencia no se ve al leer: secuencias (sólo
-- sirven para escribir), funciones (`public` no define ninguna) y CREATE sobre
-- el esquema — sin él `agent_ro` no puede crear una tabla propia y volverse su
-- dueño, que es la forma silenciosa de saltearse las policies de la sección 3.
REVOKE ALL ON SCHEMA public FROM agent_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM agent_ro;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM agent_ro;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM agent_ro;

GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;


-- 3. Row Level Security sobre toda tabla con `tenant_id`
--
-- Las tablas se descubren por catálogo y nunca por una lista escrita a mano: 9
-- de las 17 con `tenant_id` de este dump no están documentadas
-- (ver NOTES/00-restore-y-humo.md).
--
-- En el predicado, el `true` de `current_setting` evita que la *ausencia* de la
-- variable levante excepción y el `NULLIF` convierte la cadena vacía en NULL.
-- Comparar contra NULL no da TRUE: sin institución declarada, cero filas.
--
-- Dos regímenes, según `is_nullable`. Un `tenant_id` nullable significa que la
-- tabla mezcla filas globales de referencia con filas de una institución —hoy
-- `watchlists`—, y ahí las dos salidas simples fallan: sin RLS se filtran a la
-- competencia sus listas internas, y con la estricta desaparecen las públicas
-- (ver NOTES/00-restore-y-humo.md).
DO $bootstrap$
DECLARE
    t record;
    predicado text;
BEGIN
    FOR t IN
        SELECT c.table_name AS tabla,
               c.is_nullable = 'YES' AS admite_filas_globales
        FROM information_schema.columns c
        JOIN information_schema.tables tab
          ON tab.table_schema = c.table_schema
         AND tab.table_name   = c.table_name
        WHERE c.table_schema = 'public'
          AND c.column_name  = 'tenant_id'
          AND tab.table_type = 'BASE TABLE'
        ORDER BY c.table_name
    LOOP
        IF t.admite_filas_globales THEN
            predicado := 'tenant_id IS NULL OR tenant_id = '
                      || 'NULLIF(current_setting(''app.tenant_id'', true), '''')::bigint';
        ELSE
            predicado := 'tenant_id = '
                      || 'NULLIF(current_setting(''app.tenant_id'', true), '''')::bigint';
        END IF;

        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tabla);
        EXECUTE format('DROP POLICY IF EXISTS aislamiento_por_institucion ON public.%I', t.tabla);
        EXECUTE format(
            'CREATE POLICY aislamiento_por_institucion ON public.%I FOR SELECT USING (%s)',
            t.tabla, predicado
        );
    END LOOP;
END
$bootstrap$;


-- 4. `tenants`: el registro de instituciones, scopeado por `id`
--
-- No tiene `tenant_id`, así que el descubrimiento de la sección 3 no la alcanza,
-- y sin policy un oficial vería la lista de sus competidores con sus nombres
-- legales. Es la única tabla que el script nombra a mano, y no hay alternativa:
-- este dump no tiene una sola foreign key (ver NOTES/00-restore-y-humo.md), así
-- que nada permite derivarla del catálogo. El IF EXISTS deja el resto del
-- blindaje en pie si un día el dump no la trae.
DO $bootstrap$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'tenants'
          AND table_type = 'BASE TABLE'
    ) THEN
        ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS aislamiento_por_institucion ON public.tenants;
        CREATE POLICY aislamiento_por_institucion ON public.tenants
            FOR SELECT
            USING (id = NULLIF(current_setting('app.tenant_id', true), '')::bigint);
    END IF;
END
$bootstrap$;


-- 5. Los catálogos quedan sin RLS, a propósito
--
-- `countries`, `document_types`, `channels` y `alert_rules` no pertenecen a
-- nadie y el agente las necesita para resolver códigos. Son el contrapeso del
-- fail-closed: una base donde *todo* devuelve cero filas estaría protegida y
-- sería inútil. `tenants` se excluye acá porque la maneja la sección 4;
-- `watchlists` parece catálogo pero tiene `tenant_id` y la maneja la 3.
--
-- El DISABLE explícito revierte un ENABLE puesto a mano, que las volvería
-- ilegibles y rompería en silencio cualquier consulta que resuelva un código.
DO $bootstrap$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT tab.table_name AS tabla
        FROM information_schema.tables tab
        WHERE tab.table_schema = 'public'
          AND tab.table_type = 'BASE TABLE'
          AND tab.table_name <> 'tenants'
          AND NOT EXISTS (
              SELECT 1
              FROM information_schema.columns c
              WHERE c.table_schema = tab.table_schema
                AND c.table_name   = tab.table_name
                AND c.column_name  = 'tenant_id'
          )
        ORDER BY tab.table_name
    LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.tabla);
    END LOOP;
END
$bootstrap$;
