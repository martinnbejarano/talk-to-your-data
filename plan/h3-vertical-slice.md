# H3 · Vertical slice

**Objetivo.** Una pregunta atravesando todo el sistema, punta a punta, con la derivación
a la vista. Valida la arquitectura **antes** de invertir en cobertura.

Pregunta de referencia: *"¿Cuántos clientes de riesgo alto tenemos?"* — toca casi todo lo
difícil: config por institución versionada, dos fuentes que se contradicen, índice
parcial.

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

## H3.0 · Fijar el lenguaje — **cerrado**

**Antes de escribir código**, porque estas palabras terminan en la pantalla de un usuario
y renombrarlas después es caro. El glosario vive en [`CONTEXT.md`](../CONTEXT.md); acá
queda el registro de qué se decidió y por qué.

- **Los cuatro estados quedan los de D-05, sin cambios.** `RESPONDIDA_CON_SUPUESTO` le
  gana a `RESPONDIDA_CON_CRITERIO` por precedencia y no por gusto: "supuesto" ya es un
  término cerrado del glosario desde H2, con definición propia y con el oficial como
  destinatario, y "criterio" está en el _evitar_ de "definición".
- **El nombre del estado no se muestra nunca.** El estado es del contrato —lo leen el
  front y el runner de evals— y la pantalla muestra su consecuencia: el supuesto
  declarado, las opciones para elegir, o qué falta en los datos.
- **Definición** frente al oficial, **skill** dentro del código y en `core/semantics/`.
  La traducción ocurre en un solo lugar: el contrato las entrega en
  `definiciones_usadas`, y de ahí en adelante la palabra "skill" no vuelve a aparecer.
- **Traza** es lo que guarda el backend, con su `traza_id`; **auditoría** es leerla y es
  nuestra, de IT; **detalle técnico** es el rótulo del bloque plegado de la pantalla. Al
  oficial no se le muestra una auditoría: se le muestra cómo se llegó al número.
- **Derivación** es la cascada, **escalón** cada línea con su número, **paso** lo que
  hace el agente mientras trabaja. Son tres cosas distintas y por eso el contrato lleva
  `derivacion: [{escalon, ...}]`: un tope de pasos evita el loop infinito, un tope de
  escalones no significaría nada.
- "Hallazgo real", "riesgo alto", "fuera de SLA" vienen de H2 y quedan congelados.

De cerrar el lenguaje salen tres correcciones, que este mini-plan ya incorpora. Dos son
a documentos que se habían corrido del código: la API pasa a hablar el idioma de la
pantalla (`GET /instituciones`, `GET /auditoria/{traza_id}`, y `institucion_id` en el
payload de `/ask`), y los períodos se escriben semiabiertos —`[2026-01-01, 2026-04-01)`
el trimestre, `[2026-01-01, 2026-06-01)` este año— como los filtran las nueve goldens.

La tercera es al revés: **el código se corrió del glosario**. La clave `paso:` de
`derivacion` en las nueve skills de `core/semantics/` nombra cada línea de la cascada,
que es exactamente el uso que el _evitar_ de "escalón" prohíbe desde H2. Era el único
término que quedaba con dos significados, y se resuelve del lado del glosario: la clave
pasa a `escalon:` en las nueve skills, en `scripts/validar_semantica.py` y en el
contrato. Se hace **antes** de que `agent/loop.py` la lea.

**Sale:** el glosario cerrado en [`CONTEXT.md`](../CONTEXT.md), con la decisión
registrada como ADR. Regla: *si una palabra aparece en la pantalla y en el código con
distinto significado, una de las dos está mal.*

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
derivacion: [{escalon, texto, n,    → el oficial: cómo se llegó, escalón por escalón;
              unidad}]                unidad avisa cuando el escalón no es una resta
definiciones_usadas: [{concepto, texto, parametro, origen, vigente_desde}]
exclusiones: [texto]                → el oficial: qué quedó afuera
filas: {columnas, muestra, total}   → el oficial: la verificación por reconciliación
supuestos, opciones                 → el oficial: cuando hubo ambigüedad
queries: [{sql, plan, ms}]          → IT: el detalle técnico, plegado
grafico: null                       → reservado, fuera del alcance inicial
traza_id                            → IT: con qué se recupera la traza después
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
| Validador de trazabilidad | Una respuesta que cita `1.847` sin que esté en la traza, falla |
| Resolución de períodos | "este año" → `[2026-01-01, 2026-06-01)` y "último trimestre" → `[2026-01-01, 2026-04-01)`, semiabiertos y sin tocar `now()` |

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
- `api/` — `GET /instituciones`, `POST /ask`, `GET /auditoria/{traza_id}`.
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
│   └───────────────────────────┘     │   score ≥ 80         389   │
│   Definición: score ≥ 80 (umbral    │   + marca manual      42   │
│   de tu institución, vigente desde  │   = riesgo alto      431   │
│   el 01/01/2026) o marca manual.    │                            │
│                                     │  No incluye: dados de      │
│   [ Ver los 431 clientes ]          │  baja · evaluaciones       │
│                                     │  históricas                │
│                                     │  ▸ Detalle técnico (IT)    │
└─────────────────────────────────────┴────────────────────────────┘
```

Los **conteos** del croquis son ilustrativos; los **parámetros** no: 80 vigente desde el
2026-01-01 es el umbral real de Banco Norte (`NOTES/01-exploracion.md`). Este documento
decía antes *"85 vigente desde el 01/03/2026"*, que no es el par de ninguna institución
—el 85 es de Banco Andino y rige desde el **2026-02-01**—, y ese error viajó al issue #6
y al #9. Los números medidos de verdad, punta a punta, están en `NOTES/03-prototipo.md`.

No negociables desde el primer commit: **institución siempre visible**, **fecha de corte
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

Tildado en H3/09 contra lo que efectivamente quedó, no contra la intención. Donde algo no
se cerró entero, está dicho qué falta y quién lo toma.

- [x] Glosario cerrado y usado de forma consistente en código y UI. `CONTEXT.md` fijó los
      nueve términos y los tres renombres (`cascada`→`derivación`, `paso`→`escalón`,
      `tenant`→`institución` en la cara al usuario) llegaron al código, a las nueve skills
      y a la pantalla. La última fuga —una rama de `core/trazabilidad.py` que todavía
      aceptaba `paso`— se borró en este ticket.
      **Queda abierto:** `origen` viaja como texto libre, así que un `tenant_*` que el
      front no mapee le muestra la palabra "tenant" al oficial. Acotarlo a un enum del
      contrato → **H5**.
- [x] Mockup validado con una persona no técnica que, sin ayuda, pudo explicar de dónde
      salió el número y qué quedó afuera. El usuario la corrió y aprobó el diseño;
      asentado en el issue #9.
- [x] La derivación en cascada se arma con escalones que salen de queries ejecutadas, no
      calculados en el modelo. El loop los **exige** —no los espera— contra los que la
      skill declara, y `cifras_sin_respaldo` verifica cada `n` contra una fila devuelta.
      **Queda abierto:** los `−X` entre escalones y la línea de la suma los calcula
      `web/src/derivacion.js`, así que son las dos únicas cifras de la pantalla invisibles
      para el validador. Riesgo residual real contra D-04 → **H5**.
- [x] **Prototipo corrido y las 5 mediciones anotadas en `NOTES/03-prototipo.md`**, con
      la conclusión sobre la convergencia del agente. D-01 queda confirmado con evidencia.
- [x] El experimento con y sin skill corrido: sabemos qué inventa el agente sin la skill
      (`NOTES/03-prototipo.md` §3). El error no es de aritmética ni de umbral: es de
      definición.
- [x] La pregunta de referencia se responde end-to-end desde el navegador, en las dos
      instituciones (issue #14).
- [ ] **Gate rechaza un caso de prueba y el agente se recupera.** Cerrado a medias. La
      recuperación está *medida* —`NOTES/03-prototipo.md` §2, dos corridas, un intento
      cada una, el número sostenido— pero con el rechazo **inyectado**: con RLS el
      planificador no elige por su cuenta un `Seq Scan` sobre una tabla grande, así que el
      peor caso hay que construirlo. En el sistema que corre hoy, la traza *cuenta* los
      rechazos y ningún test ni eval afirma que después de uno se llega igual al número.
      → **H4**, como una pregunta del set que provoque un rechazo real.
      Y el pendiente que el prototipo le dejó al gate (§7: *la sugerencia tiene que ser
      específica de la consulta rechazada*) aterrizó sólo a medias: la del `Seq Scan`
      nombra las tablas, la de costo sigue siendo una plantilla que la consulta puede ya
      cumplir → **H5**.
- [x] Tests: números no trazables detectados (`tests/test_trazabilidad.py`); dos
      instituciones no se filtran entre sí (`tests/test_aislamiento.py` en la base y
      `tests/test_api.py` cruzando la API).
- [x] Review del diff hecho, en los dos ejes (issue #15).

## Deuda que sale del review de H3/09

Lo que el review encontró y **no** se arregló acá, con destino explícito. El criterio fue
que este ticket cierra y no construye: lo chico y con valor se aplicó, lo demás se anota.

### Contrato — lo que descubrió dibujar la pantalla

| Deuda | Por qué duele | Va a |
|---|---|---|
| **La fecha de corte está duplicada**: `web/src/config.js` la copia de una env var de Vite contra `core.config.AS_OF`, y se desincronizan en silencio | La fecha de corte es un no negociable de esta pantalla; que mienta es peor que que falte | H5 · que viaje en el contrato |
| **`origen` es texto libre** | Un `tenant_*` que el front no mapee le muestra la palabra "tenant" al oficial, contra el glosario | H5 · enum del contrato |
| **`NO_SE_PUEDE_RESPONDER` cubre dos cosas distintas**: el dato no existe, y el sistema no pudo sostener el número | Son dos mensajes distintos para el oficial y dos señales distintas para el eval, con un solo estado y sin campo que las separe | H4 · el eval las tiene que poder distinguir |
| **Los `−X` y la línea de la suma los calcula el front** (`web/src/derivacion.js`) | Son las dos únicas cifras de la pantalla que `cifras_sin_respaldo` no ve. Riesgo residual contra D-04, con el mockup aprobado pidiéndolas | H5 |
| **`filas` casi nunca existe para la pregunta de referencia**: `_filas` toma la última consulta con más de una fila, y la cascada viene en una sola | La historia 15 pide la muestra para reconciliar. Hoy el oficial la ve sólo cuando la pregunta devuelve una tabla, como `monto_transado`. Es lo que el mockup aprobado dibuja, así que **el que está mal es el snippet del issue #6 §4** —corregido por comentario—, pero la historia 15 sigue sin camino en la pregunta canónica | H5 |
| **`filas.total` son las filas que devolvió la consulta**, no la población detrás del número | Con un `LIMIT` del agente, "Mostrando 5 de 50 filas" es cierto y engañoso a la vez | H5 |
| **`exclusiones` no está garantizado**: sale del modelo con una línea de prompt | El pie que lo afirmaba se sacó en este ticket. Sostenerlo de verdad pide un escalón `−X` medido | H5 |

### Código

| Deuda | Va a |
|---|---|
| El corte `reltuples >= 100000` vive en **cuatro** lugares (`core/db/ejecucion.py`, dos veces en `tests/conftest.py`, una en `scripts/validar_semantica.py`). `tablas_grandes_del_catalogo()` es el candidato a quedarse con la única copia; lo que lo frena es que dos de las cuatro conectan como admin y una necesita el otro lado del corte | H5 |
| `api/instituciones.py` abre psycopg **fuera de `core/db/`**: es el único SQL del repo fuera de esa costura. Declarado como deuda en su propio docstring, y la excusa ("`core/` quedó fuera del alcance del ticket") ya no vale, porque la misma serie de commits creó tres módulos en `core/` | H5 · mover a `core/db/` |
| `agent/loop.py` quedó en ~670 líneas y se edita por dos razones: el ciclo y el registro de traza. `agent/traza.py` es el corte natural. Contra la regla del hito —"el loop entra en una pantalla"— **`responder()` sí entra**: son 55 líneas y se lee de arriba abajo. Lo que no entra es el archivo | H5 · si el archivo vuelve a crecer |
| `responder()` **no envuelve** las excepciones del modelo (`chat.completions.create`) ni el `RuntimeError` de `_fichas()`: hoy salen como 500 de FastAPI en vez de `NO_SE_PUEDE_RESPONDER`. Ojo al arreglarlo: tragarse un `OPENAI_API_KEY` faltante y mostrarlo como "no pude sostener el número" sería peor que el 500 | H5 |
| `scripts/valores_esperados.py` importa `PERIODOS` de `scripts/validar_semantica.py` en vez de llamar a `resolver_periodo`. La prueba de que el cambio es sano: `evals/valores_esperados.yaml` tiene que regenerarse **byte a byte idéntico** | H4 · cuando se toque el eval |
| Cargar las nueve skills (`glob` + `safe_load`) está escrito **cinco** veces (`agent/tools.py`, `tests/criterios_semanticos.py`, `tests/test_gate.py`, `scripts/techo_de_costo.py`, `scripts/valores_esperados.py`), y `SEMANTICS` se define en tres archivos | H5 |
| La cascada `isinstance(… Ok / Rechazada / Fallo)` está dos veces: `texto_para_el_modelo` (`agent/tools.py`) y `_como_salio` (`agent/loop.py`) | H5 |
| `@cache _fichas(institucion_id)`: las tres consultas de catálogo no llevan `tenant`, así que la segunda institución paga tres viajes por una respuesta idéntica | H5 · menor |
| El loop **exige todos** los escalones que declara la skill que leyó. Es lo que §5.2 del prototipo pidió, pero una pregunta legítimamente segmentada podría no traerlos todos y salir como `NO_SE_PUEDE_RESPONDER` con el número bien | H4 · el eval lo mide |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El prototipo se convierte en el producto | Es descartable **desde el día uno**. Se guarda la medición en `NOTES/`, se borra el código |
| El agente entra en loop de reintentos | Tope de pasos; al agotarse, `NO_SE_PUEDE_RESPONDER` explicando que no logró una consulta eficiente |
| Pulir la UI en el hito equivocado | Acá la UI es estructura, no estética. El pulido es H6 |
| Saltearse H3.2 porque "seguro anda" | Es la fase que valida la decisión de arquitectura más cara del proyecto. Si se saltea una fase, que sea otra |
