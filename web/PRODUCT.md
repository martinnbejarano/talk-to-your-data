# Producto

<!-- impeccable:product-schema 1 -->

Verdad de producto de **la pantalla del oficial** (`web/`). No decide nada visual:
eso vive en `DESIGN.md` cuando exista. El vocabulario es el de
[`../CONTEXT.md`](../CONTEXT.md) y las decisiones de arquitectura, el de
[`../DECISIONS.md`](../DECISIONS.md); acá no se redefine ningún término.

## Platform

web

## Users

**El oficial de cumplimiento.** Trabaja en una entidad financiera —banco, ALYC,
fintech, EMI—, **no es técnico y no lee SQL**. Pregunta en castellano rioplatense
sobre los datos de su propia institución. La escena real es **su jornada de
trabajo**: sesiones largas, muchas preguntas seguidas, no una demo. Densidad,
escaneabilidad y consistencia pesan más que la expresión visual.

**IT como segundo lector, fuera de la pantalla.** Nosotros, o el equipo de
sistemas de la institución, leemos el SQL, el plan de ejecución y los tiempos.
Ya **no** los lee en la interfaz: por decisión del usuario, esa parte salió de
la pantalla y se lee contra los logs de la API y `GET /auditoria/{traza_id}`.
Lo único que queda en pantalla es el `traza_id`, en prosa y al final del panel,
para que un problema que reporta el oficial se pueda encontrar. **Esto corrige
la pieza 7 de D-07**, que ponía el detalle técnico plegado dentro de la
pantalla.

**El analista no es usuario.** Aparece en los datos —revisa alertas, trabaja
casos— y nunca frente a la pantalla.

## Product Purpose

Que el oficial obtenga un número **en el que pueda confiar sin saber SQL**.

Hay tres tipos de pregunta y el sistema tiene que manejar los tres: contestable
(dar el número correcto), ambigua (repreguntar o declarar el supuesto que se
tomó) e incontestable (reconocer que la data no alcanza y decir qué falta). **Dos
de los tres modos de éxito consisten en no dar un número**, y la pantalla tiene
que hacer que esos dos se lean como rigor y no como falla.

Éxito es que el oficial pueda hacer las dos operaciones que sí sabe hacer:
**derivación** (entiendo cómo se llegó al número) y **reconciliación** (verifico
una muestra contra lo que ya conozco).

## Positioning

La confianza no se apoya en mostrar la consulta ni en un porcentaje de confianza,
sino en la derivación en cascada con su escala proporcional, la ficha de
definiciones con el origen del parámetro, las filas reales, y lo que quedó
afuera dicho explícito. D-07 enumeraba siete piezas; **dos ya no son de la
pantalla**: el detalle técnico plegado, que el usuario mandó a los logs de la
API, y cada cifra del texto enlazada a su escalón, que no se puede construir
mientras el contrato no marque las cifras — hacerlo hoy obligaría al front a
parsear la prosa del modelo, que es justo lo que `src/api.js` prohíbe. El
progreso paso a paso sigue pendiente del backend.

Dos consecuencias que un producto vecino no puede copiar sin adoptar la misma
postura: **nunca un cero donde la respuesta es que no se puede responder**, y
**ningún nivel de confianza en porcentaje** (D-05) — una categoría obliga a una
decisión con sentido, un "87 %" no significa nada accionable.

## Operating Context

- **La institución se elige en la pantalla**, nunca se deduce de la pregunta
  (D-03). El selector está siempre arriba y visible: es el scope de todo lo que
  se ve. Cambiar de institución vacía el historial.
- **Fecha de corte fija: 1 de junio de 2026.** Todo "hoy", "este año" y "último
  trimestre" se interpreta contra esa fecha y nunca contra el reloj. La pantalla
  la muestra siempre.
- **Cada respuesta tarda entre trece y veinte segundos**, porque se escriben y
  ejecutan consultas de verdad. La espera es parte del producto y tiene que
  leerse como evidencia de trabajo, no como una pantalla colgada.
- **El servidor no guarda sesiones**: el historial lo arrastra el front y viaja
  en cada pregunta. Una pregunta escrita a mano va siempre con historial vacío;
  sólo el clic en una opción de repregunta arrastra el turno previo.
- Español rioplatense, con voseo, en toda la interfaz.

## Capabilities and Constraints

**Lo que hay hoy** (React 19 + Vite, sin router ni librería de UI; una sola
pantalla): selector de institución, caja de pregunta con tres sugerencias —dos
de ellas contestan con una serie, para que el gráfico se descubra sin adivinar
qué preguntar—, estado de espera con contador, y los turnos apilados como
conversación. Cada respuesta se lee como **una sola oración**; el supuesto y las
opciones de repregunta van con ella, sin plegar. Detrás de un único botón,
**Mostrar más**, y en este orden: qué se contó con la procedencia del parámetro,
cómo se llegó al número con una escala proporcional por tramo, qué quedó afuera,
y las filas de la consulta un nivel más adentro.

**El contrato manda.** El front dibuja campo por campo lo que devuelve `POST
/ask` y **nunca parsea el texto libre del modelo**. Campos: `estado`, `valor`,
`respuesta`, `supuestos`, `opciones`, `definiciones_usadas`, `derivacion`,
`exclusiones`, `filas`, `grafico`, `traza_id`. Endpoints: `GET /instituciones`, `POST /ask`,
`GET /auditoria/{traza_id}` (este último, para IT).

**Restricciones que ninguna decisión de diseño puede romper:**

- El **nombre del estado nunca aparece en pantalla**. El estado decide qué se
  dibuja; lo que se ve es su consecuencia.
- **El supuesto y las opciones de repregunta nunca se pliegan.** No son detalle
  de respaldo: son condiciones de la oración que se está leyendo.
- **La escala de la derivación se calcula por tramo** y nunca cruza un cambio de
  unidad: comparar alertas contra clientes daría una proporción falsa.
- La palabra **"skill" no existe en la interfaz**: frente al oficial son
  **definiciones**. Tampoco **"tenant"**: es **institución**. Tampoco
  **"auditoría"** como rótulo de algo que ve el oficial: eso es **derivación**.
- **Todo número sale de una consulta ejecutada** (D-04). Ninguna cifra se calcula
  en el front.
- Los montos **se muestran desglosados por moneda y por sentido**, nunca sumados
  (D-08). No hay tipos de cambio.
- La respuesta es **sincrónica y sin streaming**: hoy no hay eventos del backend,
  así que el progreso paso a paso de D-07 todavía no se puede dibujar.
- **Hay gráfico sólo donde la respuesta es una serie** (D-19) —altas por mes,
  alertas por estado—. Va arriba, junto a la oración y no detrás de "Mostrar
  más", con su tabla desplegada debajo: el dibujo sirve para ver la forma, los
  números son para defenderlos ante un auditor. Una respuesta de un solo número
  no lleva gráfico ni lo ofrece, y **una serie por moneda tampoco se dibuja**:
  compartir el eje de valores sería sumar visualmente lo que D-08 no deja
  sumar.
- **Desktop y móvil**: la interfaz tiene que funcionar de verdad en teléfono, no
  sólo no romperse.

**Fuera de alcance, decidido y no olvidado**: autenticación, escrituras a la
base, conversión de monedas, dedup por nombre o correo, preguntas guardadas,
dashboards y caché de respuestas. La **visualización de resultados** salió de
esta lista con D-19, y con un alcance angosto: una serie se dibuja, un número no.

## Brand Commitments

No hay marca, logo ni identidad definida.

- **Convención elegida y vinculante.** Ante una mesa de direcciones visuales
  propias, el usuario tomó la salida estándar: la pantalla es un **asistente
  conversacional convencional, ejecutado en serio**. La vara de oficio son
  **ChatGPT** (columna central, aire, respuesta en texto bien tipografiado) y
  **Linear** (densidad justa, grises finos, cero decoración). No se contrabandea
  ninguna rareza de autor adentro de esa convención.
- **Modo claro únicamente.** Sin tema oscuro y sin seguir `prefers-color-scheme`.
- **Una sola columna, sin barra lateral.** Los turnos se apilan como
  conversación y las preguntas anteriores se ven scrolleando.
- Voz: castellano rioplatense, sobria, sin marketing. El sistema **declara dónde
  falla**; esa postura vale también para la interfaz.
- El sistema **no se disculpa ni dramatiza**: "no se puede responder" se escribe
  como rigor, y su color deliberadamente **no es rojo**.

## Evidence on Hand

- Valores esperados verificados a mano en [`../evals/valores_esperados.yaml`](../evals/valores_esperados.yaml);
  la pregunta de referencia da 7.859 en Banco Andino y 321 en Fintech Cuyo.
- Glosario cerrado del dominio en [`../CONTEXT.md`](../CONTEXT.md), decisiones en
  [`../DECISIONS.md`](../DECISIONS.md), log de proceso en [`../NOTES/`](../NOTES).
- Capturas de la pantalla en `../.capturas/`.
- **No hay** testimonios, clientes, benchmarks, precios ni instituciones reales:
  los nombres del dataset son de prueba y no se pueden presentar como clientes.
- El resultado del eval con sus números —incluidas las preguntas que falla— es
  material real y va al README (H6); no se puede anticipar ni redondear acá.

## Product Principles

1. **No contestar también es contestar bien.** Repreguntar y declarar que la data
   no alcanza son dos de los tres modos de éxito, no estados degradados.
2. **Un número sin su derivación no sirve.** La cadena de escalones es la
   explicación principal de una respuesta, no un anexo.
3. **La pantalla se escribe entera para el oficial.** El segundo lector, IT,
   se atiende fuera de ella: los logs de la API, contra el `traza_id`.
4. **La institución es el scope y se ve siempre.** Nada cruza de una a otra, y
   eso tiene que ser visible sin buscarlo.
5. **Nada se afirma sin poder mostrarlo.** Ni un número sin consulta, ni una
   certeza en porcentaje, ni un total que mezcle monedas.

## Accessibility & Inclusion

El oficial no es técnico: el lenguaje de la interfaz es el del glosario y ningún
término técnico aparece sin traducir. **La pantalla es de modo claro
únicamente**, por decisión del usuario: no hay tema oscuro y no se sigue
`prefers-color-scheme`. Hay una sola región viva para el anuncio de la
respuesta, y los blancos táctiles llegan a 44 px con puntero grueso. No se
estableció un estándar formal de accesibilidad como requisito del producto; el
piso de calidad de Impeccable aplica igual.
