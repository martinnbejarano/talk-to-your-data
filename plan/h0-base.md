# H0 · Base lista y blindada

**Objetivo.** Tener la base restaurada y una conexión de agente de la que sea
*imposible* leer datos de otro tenant, aunque el SQL que escriba no tenga filtros.

**Bloquea:** todo. Sin base no hay exploración, sin exploración no hay semántica.

## Precondiciones

- Docker Desktop corriendo con **≥ 4 GB** asignados (lo pide el `docker-compose.yml`).
- `docker-compose.yml` y `DATA_DICTIONARY.md` en el repo, el compose sin tocar.
- El dump enlazado en `dump/compliance.dump` (symlink; 1,7 GB no van al repo, `dump/`
  está en `.gitignore`).

## Tareas

### 1. Restaurar

```
docker compose up -d db
docker compose run --rm restore      # ~5-10 min
```

Verificación de humo: conectar a `localhost:55432` (`postgres` / `compliance` /
`compliance`), listar tablas, contar tenants, y confirmar que `max(tx_date)` no supera
`2026-06-01` — o sea, que el `AS_OF` del diccionario es real.

### 2. Escribir `infra/bootstrap.sql`

Script **idempotente** que se puede correr las veces que haga falta:

1. Rol `agent_ro`: `LOGIN`, `NOSUPERUSER`, **sin `BYPASSRLS`**, password de entorno.
2. `REVOKE ALL` sobre el esquema, después `GRANT USAGE` + `GRANT SELECT` sobre las
   tablas. Ninguna escritura, nunca.
3. `ALTER ROLE agent_ro SET statement_timeout = '15s'` — el límite viaja con el rol,
   no depende de que el backend se acuerde de setearlo.
4. `ENABLE ROW LEVEL SECURITY` en toda tabla que tenga `tenant_id`, con la policy:

   ```sql
   USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::bigint)
   ```

   El `NULLIF` es deliberado: si nadie seteó la variable, la comparación da `NULL`,
   que no es `TRUE`, y la consulta devuelve **cero filas**. *Fail-closed*: el modo
   inseguro no existe.
5. `tenants` también lleva RLS, con `id = app.tenant_id` — el agente ve su institución,
   no la lista de competidores.
6. Los catálogos (`countries`, `document_types`, `channels`, `alert_rules`,
   `watchlists`) quedan sin RLS: no tienen `tenant_id` y son de referencia.

### 3. Verificar el blindaje

Estos tres tests son el entregable real del hito y se dejan escritos como test de
integración, no como una prueba a mano que se hace una vez:

| Test | Resultado esperado |
|---|---|
| `SELECT count(*) FROM clients` como `agent_ro` **sin** setear `app.tenant_id` | `0` |
| `SET app.tenant_id = '<A>'` y `SELECT DISTINCT tenant_id FROM clients` | exactamente `<A>` |
| Intentar `UPDATE`/`DELETE`/`INSERT` en cualquier tabla | permiso denegado |

### 4. Verificar que el timeout muerde

Correr a propósito una query que fuerce seq scan sobre `transactions` y confirmar que
muere a los 15 s. Sirve para dos cosas: confirmar que la restricción es real, y tener
el mensaje de error exacto que después le vamos a devolver al agente como feedback.

### 5. Medir el costo de RLS

`EXPLAIN` de dos o tres queries típicas con y sin RLS. El predicado de la policy se
agrega al plan, y hay que confirmar que sigue usando los índices —
`idx_tx_tenant_date` y compañía tienen `tenant_id` como primera columna, así que
debería componer bien, pero hay que verlo, no suponerlo.

## Definition of done

- [ ] `docker compose up -d db` levanta la base con la data restaurada.
- [ ] `infra/bootstrap.sql` corre limpio dos veces seguidas (idempotente).
- [ ] Los tres tests de aislamiento pasan.
- [ ] Documentado el plan de una query representativa con RLS activo, confirmando uso
      de índice.
- [ ] Entrada en `DECISIONS.md` si algo obligó a corregir D-02.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| RLS degrada los planes y todo empieza a dar timeout | Se mide en el paso 5. Plan B: vistas por tenant con `security_barrier` |
| Alguna tabla no documentada tiene `tenant_id` y se me escapa | El bootstrap descubre las tablas por catálogo (`information_schema`), no por lista escrita a mano |
| El restore falla por RAM | Subir la asignación de Docker Desktop; el compose ya avisa que pide ≥ 4 GB |
