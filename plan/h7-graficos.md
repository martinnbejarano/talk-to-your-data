# H7 · Gráficos

**Objetivo.** Llenar el campo `grafico`, reservado desde H3 y en `null` desde entonces,
**sólo cuando la respuesta es una serie**. La decisión y su porqué están en D-19, y lo que
salió distinto al construirlo en [`../NOTES/07-graficos.md`](../NOTES/07-graficos.md); acá
está el orden en que se hizo y qué se verifica.

## El orden, y por qué ése

1. **Los documentos.** D-19 antes que una línea de código: esto reabre lo que
   `web/PRODUCT.md` tenía en *fuera de alcance*, y reabrir un alcance cerrado sin ADR es
   exactamente lo que el repo no hace.
2. **El contrato y su baranda, sin dibujar nada.** El campo se llena de verdad y viaja,
   con sus tests, antes de que exista un solo píxel. Un gráfico que no se puede dibujar
   tiene que morir en el backend y no en el front.
3. **La pantalla.** Recién ahí entra la primera dependencia visual del proyecto.

## Lo que se separó, y por qué

El pedido fue explícito: que esto no manche lo que ya hay. El repo ya tenía el
precedente —la baranda de D-04 vive en `core/trazabilidad.py` y no adentro del loop— así
que se siguió el mismo corte.

| Archivo | Qué lleva |
| --- | --- |
| `core/grafico.py` | La baranda, el fragmento del esquema estricto y el texto de la regla del prompt |
| `tests/test_grafico.py` | Sus 13 tests, puros: sin API y sin Postgres |
| `web/src/grafico.js` | El módulo puro del front, espejo de `derivacion.js` |
| `web/src/componentes/Grafico.jsx` | El componente |
| `web/src/grafico.css` | Importado por el componente; `estilos.css` quedó intacto |

De lo que ya existía se tocaron **cuatro cosas** en `agent/loop.py` —un import, el campo
en `CONTRATO`, un hueco en el prompt y una línea en `_completar`— más una línea en
`Respuesta.jsx`. `api/` no se tocó: `/ask` devuelve el contrato entero y a propósito no
declara `response_model`. `core/db/ejecucion.py` tampoco: la marca sale del valor de
Python y no de los tipos de Postgres.

## Criterio de aceptación

- La suite entera en verde, incluida la nueva.
- Una pregunta de serie contra la API real devuelve `grafico` con su marca y sus puntos,
  y `filas.muestra` sigue trayendo cinco.
- **La verificación que importa**: `"¿cuánto transamos el último trimestre?"` devuelve
  `grafico: null`. Es un desglose por moneda, y dibujarlo sería D-08 puesto en un eje.
- El bundle crece lo que tiene que crecer y no más. Medido: **23 KB gzip**.
- Una corrida `33×1` del set oficial al cerrar, comparada contra el cierre de H5 (D-17) y
  no contra la línea de base de D-14. Lo que se busca no es una mejora: es que agregar un
  campo al esquema estricto no haya movido las otras treinta y dos preguntas.

## Lo que este hito no hace

- **Paneles por moneda.** Una serie multi-unidad se contesta sin dibujo. La regla original
  de D-16 pedía un panel por moneda y estaba mal: si la única dimensión de la serie *es* la
  moneda, eso da cuatro paneles de una barra cada uno.
- **Calificar el gráfico.** No hay assert sobre él en ninguna pregunta. En producción no lo
  evalúa nadie, y la métrica que la academia inventó para esto está criticada por sus
  propios autores (`NOTES/06-graficos-en-la-industria.md` §6).
- **Torta**, y "otros" como bucket.
