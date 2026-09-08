# Compliance conversacional

Compliance conversacional es un asistente para que un oficial de cumplimiento —que no
es técnico y no lee SQL— pregunte en castellano sobre los datos de **su** institución, y
reciba un número que puede defender.

La respuesta es **una sola oración** con la cifra adentro. Detrás de *Mostrar más* está
lo que la sostiene, en el orden en que se audita: qué se contó concepto por concepto,
con el parámetro que se aplicó, quién lo fijó y desde cuándo rige; cómo se llegó al
número, escalón por escalón y con la proporción de cada uno; qué quedó afuera; y las
filas reales.

Cuando la respuesta no es un número sino varios —altas por mes, alertas por estado— se
**dibuja**, arriba y junto a la oración, con su tabla desplegada debajo. Sólo ahí: una
respuesta de un solo número no lleva gráfico ni lo ofrece, y un desglose por moneda
tampoco, porque compartir un eje de valores sería sumar visualmente lo que los números no
suman.

Cuando la pregunta admite más de una lectura y la diferencia importa, **repregunta** con
opciones en vez de elegir. Cuando elige, **lo declara arriba del número** y no plegado.
Cuando la data no alcanza, **lo dice**: nunca disfraza un faltante de cero.

Todo se interpreta contra una fecha de corte fija —**1 de junio de 2026**—, que está
siempre a la vista: "este año" es enero-2026 a esa fecha, y nunca lo que diga el reloj.

## En producción

Hay una versión funcionando en [primo.martinbejarano.com](https://primo.martinbejarano.com).

## La pantalla

![La respuesta a "¿Cuántos clientes de riesgo alto tenemos?", con el supuesto declarado y la derivación abierta](docs/pantalla.png)

## Cómo levantarlo

Hace falta Docker (con **≥ 4 GB** de RAM asignados), Python 3.13, Node 24 y una key de
OpenAI. El dump de la base **no está en el repo**: el link de descarga va aparte.

```bash
# La base, con el dump adentro (~5-10 min)
mkdir -p dump && cp /donde/lo/hayas/bajado/compliance.dump dump/
docker compose up -d db
docker compose run --rm restore

# Las dependencias
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd web && npm install && cd ..

# El entorno
cp .env.example .env
```

En `.env` hay tres variables **sin default**, y el proceso no arranca si falta alguna:
`AGENT_RO_PASSWORD` (la elegís vos; el bootstrap se la aplica al rol de sólo lectura),
`OPENAI_API_KEY` y `OPENAI_MODEL`. El resto ya viene con los valores del
`docker-compose.yml`, que está versionado.

```bash
# El rol read-only, el aislamiento por institución y los grants
.venv/bin/python scripts/restaurar.py --solo-bootstrap
```

Este paso **no es opcional y hay que repetirlo después de cada restore**: `pg_restore
--clean` se lleva puestos los GRANT y las políticas de RLS.

Y a correr, en dos terminales:

```bash
.venv/bin/uvicorn api.main:app --reload --port 8000   # la API
cd web && npm run dev                                  # la pantalla, en :5173
```

## Lo que acompaña

| Archivo | Qué hay adentro |
|---|---|
| `CONTEXT.md` | El glosario del dominio: qué significa cada palabra en la pantalla y en el código |
| `DECISIONS.md` | Las decisiones, con lo que se descartó y por qué |
| `DATA_DICTIONARY.md` | Los datos, tal como vienen |
| `NOTES/` | El log del proceso, hito por hito |
| `web/DESIGN.md` | El sistema visual de la pantalla, tal como quedó construido |
