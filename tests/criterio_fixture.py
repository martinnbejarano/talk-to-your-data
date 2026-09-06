"""El criterio que elige las dos instituciones de prueba.

Módulo plano a propósito: lo importan tanto `tests/conftest.py` como
`scripts/smoke_check.py`, y no tiene que arrastrar ni pytest ni una conexión —
`conftest.py` resuelve catálogos en tiempo de import, y traerlo desde un script
suelto arrastraría esas consultas como efecto colateral.

Los IDs no se escriben en ningún lado. El criterio es la consulta; los tenants
que devuelve son un resultado, y cambian si cambia el dump.

Por qué el par se elige así, en detalle: NOTES/00-restore-y-humo.md (versión
original) y NOTES/01-exploracion.md (las tres condiciones que agregó H1). Las
que no se leen solas:

  · A tiene que tener el umbral VERSIONADO — sólo tres tenants lo tienen, y sin
    uno de ellos la trampa de "tomar la versión vigente al AS_OF" no se ejerce.
  · A tiene que tener el `review_sla_hours` MÁS CORTO de la base. Las alertas
    "revisadas tarde" existen únicamente en los tenants de 24 h: con un SLA más
    largo esa mitad de la definición de "fuera de SLA" queda en cero y una
    golden query que la omita pasa igual. Es la condición que agregó H1.
  · B tiene que ser CHICO de verdad (≤ 10 % de los clientes de A), no sólo
    distinto: sobre 8.000 clientes los números se verifican a mano.
  · `mes_fiscal <> a.mes_fiscal` no es porque el año fiscal redefina los
    períodos —no lo hace— sino para tener un tenant donde probar que NO.
"""

from __future__ import annotations

Q_FIXTURE = """
WITH activos_con_datos AS (
    SELECT t.id, t.slug, t.kind,
           (SELECT count(*) FROM clients x
            WHERE x.tenant_id = t.id AND x.deleted_at IS NULL) AS clientes
    FROM tenants t
    WHERE t.is_active
      AND EXISTS (SELECT 1 FROM clients          x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL)
      AND EXISTS (SELECT 1 FROM transactions     x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL)
      AND EXISTS (SELECT 1 FROM alerts           x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL)
      AND EXISTS (SELECT 1 FROM cases            x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL)
      AND EXISTS (SELECT 1 FROM screenings       x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL)
      AND EXISTS (SELECT 1 FROM risk_assessments x WHERE x.tenant_id = t.id AND x.deleted_at IS NULL AND x.is_current)
),
config_vigente AS (
    SELECT DISTINCT ON (tenant_id, key)
           tenant_id,
           key,
           value #>> '{}' AS vigente,
           count(*) OVER (PARTITION BY tenant_id, key) AS versiones
    FROM tenant_config
    WHERE effective_from_date <= %(as_of)s::date
    ORDER BY tenant_id, key, effective_from_date DESC
),
perfil AS (
    SELECT a.id, a.slug, a.kind, a.clientes,
           u.versiones      AS umbral_versiones,
           u.vigente::int   AS umbral_vigente,
           f.vigente::int   AS mes_fiscal,
           s.vigente::int   AS sla_horas,
           p.vigente::bool  AS pep_alto,
           e.vigente::bool  AS escalada_hallazgo
    FROM activos_con_datos a
    JOIN config_vigente u ON u.tenant_id = a.id AND u.key = 'high_risk_score_threshold'
    JOIN config_vigente f ON f.tenant_id = a.id AND f.key = 'fiscal_year_start_month'
    JOIN config_vigente s ON s.tenant_id = a.id AND s.key = 'review_sla_hours'
    JOIN config_vigente p ON p.tenant_id = a.id AND p.key = 'pep_is_high_risk'
    JOIN config_vigente e ON e.tenant_id = a.id AND e.key = 'escalated_counts_as_finding'
),
tenant_a AS (
    SELECT * FROM perfil
    WHERE umbral_versiones > 1
      AND sla_horas = (SELECT min(sla_horas) FROM perfil)
    ORDER BY id
    LIMIT 1
),
tenant_b AS (
    SELECT p.*
    FROM perfil p, tenant_a a
    WHERE p.umbral_versiones   = 1
      AND p.clientes          <= a.clientes / 10
      AND p.kind              <> a.kind
      AND p.umbral_vigente    <> a.umbral_vigente
      AND p.mes_fiscal        <> a.mes_fiscal
      AND p.sla_horas         <> a.sla_horas
      AND p.pep_alto          <> a.pep_alto
      AND p.escalada_hallazgo <> a.escalada_hallazgo
    ORDER BY p.id
    LIMIT 1
)
SELECT 'A' AS rol, * FROM tenant_a
UNION ALL
SELECT 'B' AS rol, * FROM tenant_b
ORDER BY rol;
"""
