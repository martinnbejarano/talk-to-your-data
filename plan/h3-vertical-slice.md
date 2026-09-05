# H3 · Vertical slice

**Objetivo.** Una pregunta atravesando todo el sistema, punta a punta, con auditoría.
Valida la arquitectura **antes** de invertir en cobertura.

Pregunta de referencia: *"¿Cuántos clientes de riesgo alto tenemos?"* — toca casi todo lo
difícil: config por tenant versionada, dos fuentes que se contradicen, índice parcial.

**Es el hito más importante y el que más incógnitas tiene que no se resuelven en papel.**
Por eso se parte en seis fases, cada una con su propósito.

Lo primero es el prototipo del loop (H3.2): con las 5 tools y una skill, el agente tiene
que llegar a una query correcta e indexada en pocos pasos y recuperarse cuando el gate se
la rechaza. Va antes que el resto porque es la medición que condiciona el diseño del
motor (D-01), y construir sobre ella sin tenerla es construir a ciegas.

El mockup (H3.1) comprueba lo otro que hoy no está probado: que un oficial de compliance,
mirando la pantalla, pueda decir **de dónde salió el número** y **qué quedó afuera**, sin
leer una línea de SQL. La pantalla tiene dos lectores y hay que dibujarlos separados: el
oficial, que necesita la derivación y las filas; y nosotros —IT, o el equipo de sistemas
del cliente— que necesitamos el SQL y el plan, plegados en `▸ Detalle técnico` (D-07).

---

## H3.0 · Fijar el lenguaje

**Antes de escribir código**, porque estas palabras terminan en la pantalla de un usuario
y renombrarlas después es caro.

Términos a cerrar:

- Los cuatro estados. ¿`RESPONDIDA_CON_SUPUESTO` o `RESPONDIDA_CON_CRITERIO`? El usuario
  no dice "supuesto".
- **"Definición"** vs "criterio" vs "regla" vs "skill". Adentro son skills; en la
  interfaz probablemente sean "definiciones". Que la traducción sea deliberada y esté en
  un solo lugar.
- **"Trace"** vs "auditoría" vs "detalle". Lo que ve el usuario y lo que guarda el
  backend no tienen por qué llamarse igual, pero tiene que estar escrito cuál es cuál.
  Con una regla ya fijada: **"auditoría" en sentido técnico es la nuestra, la de IT.**
  Al oficial no se le muestra una "auditoría", se le muestra **cómo se llegó al número**.
- **"Derivación"** — el nombre de la cascada de escalones que lleva al resultado. Es la
  pieza central del panel y no puede quedar sin nombre propio en el código.
- "Hallazgo real", "riesgo alto", "fuera de SLA" — vienen de H2, acá se congelan.

**Sale:** el glosario, con la decisión registrada como ADR. Regla: *si una palabra
aparece en la UI y en el código con distinto significado, una de las dos está mal.*

---

## H3.1 · Mockup estático · Artifact, sin backend

Una página HTML con datos falsos. **Sin agente, sin base, sin API.** Una a dos horas.

**Preguntas que responde:**

1. ¿La derivación en cascada se lee sola? Es la pieza que reemplaza al SQL como
   explicación principal: los escalones tienen que restarse a la vista y cada uno decir
   en castellano qué se descartó.
2. ¿La definición aplicada va **junto al número** o en el panel? La expectativa es junto
   al número; hay que verlo dibujado.
3. ¿Dónde entran las exclusiones ("no incluye clientes dados de baja") sin sonar a letra
   chica? Tienen que leerse como prolijidad, no como descargo de responsabilidad.
4. ¿Cómo se ve una repregunta? ¿Opciones clickeables o texto?
5. ¿Cómo se ve un `NO_SE_PUEDE_RESPONDER` sin que parezca un error del sistema? Es la
   pantalla más difícil: tiene que leerse como *rigor*, no como *falla*.
6. ¿Cómo se muestra la tabla de filas reales sin que tape el hallazgo principal?
7. ¿`▸ Detalle técnico` queda claramente rotulado como algo que **no** es para el
   oficial, sin que parezca escondido?

**Cómo se valida:** mostrárselo a alguien que no sea técnico y pedirle dos cosas mirando
la pantalla: que diga **de dónde salió el número** y **qué no está contado ahí adentro**.
Si no puede, el diseño está mal, no la persona. Prohibido ayudarlo explicándole.

Seis pantallas: una por estado, más una con la tabla de filas y una con el detalle
técnico abierto. Es la manera más barata de descubrir que el layout estaba equivocado.

---

## H3.2 · Prototipo del loop

**La fase más importante del hito.** Un script de consola, descartable, sin API ni UI.

Un programa chico que responde **una** pregunta de diseño. Descartable desde el día uno:
nos quedamos con la respuesta, borramos el código.

**La pregunta de diseño, precisa:**

> Dado el esquema real, las 5 tools y una skill de `riesgo_alto`, ¿un agente converge a
> una query correcta e indexada? ¿En cuántos pasos? ¿Se recupera cuando el gate le
> rechaza el plan? ¿Cuánto cuesta en tokens?

**Qué se mide, no qué se opina:**

| Medición | Umbral para seguir |
|---|---|
| Pasos hasta la query correcta | ≤ 6 |
| Recuperación tras rechazo del gate | Se recupera en ≤ 2 intentos |
| Consistencia en 5 corridas del mismo prompt | Mismo número las 5 veces |
| Tokens por pregunta | Costo tolerable por consulta |
| ¿Lee la skill o la ignora? | La lee sin que haya que rogarle |

**El experimento que más informa:** correr el mismo prompt con la skill de `riesgo_alto`
y sin ella. Si sin skill el agente inventa una definición razonable pero distinta —
probablemente `score > 80` hardcodeado — eso **prueba** que las definiciones curadas hacen falta, con evidencia
en vez de argumento. Es la ablación de Ramp, adelantada.

**Este es el punto de decisión sobre D-01.** Las mediciones se contrastan contra los
umbrales de la tabla y el diseño del motor queda confirmado o corregido acá, cuando
todavía cuesta barato: la alternativa registrada es "catálogo primero, SQL de fallback",
y el resto del plan sigue en pie con cualquiera de las dos. En H5 el cambio ya sería
carísimo.

**Lo que vuelve del prototipo son las cinco mediciones y la conclusión sobre la
convergencia, escritas en `NOTES/03-prototipo.md`. El código no vuelve.**

---

## H3.3 · Diseñar los seams

Dos interfaces que, si quedan mal, contaminan todo el resto del proyecto.

### Seam 1 — la ejecución de SQL

La tentación es que `run_sql` sea una función delgada que envuelve psycopg. Está mal: hay
que hacerla un **módulo profundo** — mucho comportamiento detrás de una interfaz chica.

```
ejecutar(sql) -> Ok(filas, plan, ms)
              |  Rechazada(motivo, sugerencia)
              |  Fallo(error_normalizado)
```

Adentro esconde: sesión con tenant, `EXPLAIN`, análisis del plan, timeout, normalización
de errores de Postgres a algo que un LLM pueda accionar. **El agente nunca ve psycopg.**

Por qué importa más de lo que parece: este seam es lo que permite testear sin mockear
storage ([`testing.md`](testing.md)). Si el agente hablara psycopg directo, el único test
posible sería un mock — justo lo que nuestras guidelines prohíben.

El caso `Rechazada` es de diseño, no de error: lleva **sugerencia**, porque su
destinatario es un agente que va a reintentar. Un mensaje de error para humanos acá sería
desperdiciar el canal.

### Seam 2 — el contrato de salida del agente

El JSON de la respuesta es lo que desacopla el LLM de la interfaz. Si queda bien, el
front se puede rehacer entero sin tocar el agente, y el runner de evals lee lo mismo que
la UI. Si queda mal, todo se pega.

Campos, agrupados por destinatario (D-07):

```
estado, respuesta, valor            → el oficial: qué contestamos
derivacion: [{paso, texto, n}]      → el oficial: cómo se llegó, escalón por escalón
definiciones_usadas: [{concepto, texto, parametro, origen, vigente_desde}]
exclusiones: [texto]                → el oficial: qué quedó afuera
filas: {columnas, muestra, total}   → el oficial: la verificación por reconciliación
supuestos, opciones                 → el oficial: cuando hubo ambigüedad
queries: [{sql, plan, ms}]          → IT: el detalle técnico, plegado
grafico: null                       → reservado, fuera del alcance inicial
```

`derivacion` no es cosmética: es la explicación principal, así que **cada escalón tiene
que traer su `n` de una query ejecutada**, igual que el valor final. Un escalón calculado
en el modelo sería exactamente el tipo de número inventado que D-04 prohíbe.

El campo `grafico` reservado hoy va siempre en `null`: dejar el hueco previsto cuesta
nada, agregarlo después cuesta un cambio de contrato.

**Regla:** el front **nunca** parsea texto libre del modelo. Todo lo que muestra sale de
campos del contrato.

---

## H3.4 · TDD de las barandas

Tres piezas que son funciones puras con resultado binario — los blancos ideales para
rojo-verde:

| Pieza | Primer test rojo |
|---|---|
| Gate de `EXPLAIN` | Un plan con seq scan sobre `transactions` es rechazado |
| Validador de trazabilidad | Una respuesta que cita `1.847` sin que esté en el trace, falla |
| Resolución de períodos | "este año" → `[2026-01-01, 2026-06-01]`, sin tocar `now()` |

Se escriben **antes** que la implementación. Y se cumple la prohibición de
[`testing.md`](testing.md): **nunca assertear el SQL que generó el agente** — sólo lo
observable.

---

## H3.5 · Armar el slice

Recién acá se escribe el producto, con todo lo anterior ya resuelto: el lenguaje fijado,
el layout validado, el loop medido, los seams diseñados, las barandas testeadas.

- `core/db/` — pool, sesión con tenant, el módulo profundo de H3.3.
- `agent/tools.py` — `list_tables`, `describe_table`, `sample_values`, `get_definition`,
  `run_sql`.
- `agent/loop.py` — orquestación y contrato de salida.
- `api/` — `GET /tenants`, `POST /ask`, `GET /audit/{trace_id}`.
- `web/` — React siguiendo el mockup de H3.1.

Layout ya validado en H3.1:

```
┌──────────────────────────────────────────────────────────────────┐
│  [ Banco Norte ▾ ]                  Datos al 1 de junio de 2026   │
├─────────────────────────────────────┬────────────────────────────┤
│   ¿Cuántos clientes de riesgo       │  CÓMO SE LLEGÓ             │
│   alto tenemos?                     │                            │
│   ┌───────────────────────────┐     │  Clientes         12.340   │
│   │          431              │     │   activos         11.980   │
│   │  clientes de riesgo alto  │     │   con evaluación  11.902   │
│   └───────────────────────────┘     │   score ≥ 75         389   │
│   Definición: score ≥ 75 (umbral    │   + marca manual      42   │
│   de tu institución, vigente desde  │   = riesgo alto      431   │
│   el 01/03/2026) o marca manual.    │                            │
│                                     │  No incluye: dados de      │
│   [ Ver los 431 clientes ]          │  baja · evaluaciones       │
│                                     │  históricas                │
│                                     │  ▸ Detalle técnico (IT)    │
└─────────────────────────────────────┴────────────────────────────┘
```

No negociables desde el primer commit: **tenant siempre visible**, **fecha de corte
siempre visible**, **definición aplicada junto al número** — no escondida en el panel —
y **el SQL plegado**, nunca como primera cosa que ve el oficial.

Primero `POST /ask` sincrónico; el streaming de pasos se suma cuando el resto anda.

---

## H3.6 · Review del diff

Dos ejes, antes de commitear y no después: **estándares** (¿respeta las reglas de
[`testing.md`](testing.md) y el estilo del resto?) y **alcance** (¿hace lo que este hito
pedía, ni más ni menos?).

---

## Definition of done

- [ ] Glosario cerrado y usado de forma consistente en código y UI.
- [ ] Mockup validado con una persona no técnica que, sin ayuda, pudo explicar de dónde
      salió el número y qué quedó afuera.
- [ ] La derivación en cascada se arma con escalones que salen de queries ejecutadas, no
      calculados en el modelo.
- [ ] **Prototipo corrido y las 5 mediciones anotadas en `NOTES/03-prototipo.md`**, con
      la conclusión sobre la convergencia del agente.
- [ ] El experimento con y sin skill corrido: sabemos qué inventa el agente sin la skill.
- [ ] La pregunta de referencia se responde end-to-end desde el navegador.
- [ ] Gate rechaza un caso de prueba y el agente se recupera.
- [ ] Tests: números no trazables detectados; dos tenants no se filtran entre sí.
- [ ] Review del diff hecho, en los dos ejes.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El prototipo se convierte en el producto | Es descartable **desde el día uno**. Se guarda la medición en `NOTES/`, se borra el código |
| El agente entra en loop de reintentos | Tope de pasos; al agotarse, `NO_SE_PUEDE_RESPONDER` explicando que no logró una consulta eficiente |
| Pulir la UI en el hito equivocado | Acá la UI es estructura, no estética. El pulido es H6 |
| Saltearse H3.2 porque "seguro anda" | Es la fase que valida la decisión de arquitectura más cara del proyecto. Si se saltea una fase, que sea otra |
