# H7 · Gráficos

La decisión y su porqué están en D-19; la investigación contra fuentes primarias, en
[`06-graficos-en-la-industria.md`](06-graficos-en-la-industria.md). Acá está lo que pasó
al construirlo, que incluye **dos reglas que se escribieron mal y sólo se cayeron contra
la API real**.

## Lo primero: el merge había borrado tres ADRs

`DECISIONS.md` terminaba en D-15. El merge de `main` en la rama —`f72c58c`— resolvió el
conflicto borrando de los dos lados: se perdieron el ADR de gráficos que se había escrito
acá y los **D-16, D-17 y D-18 de H5** que venían de `main`. Cuatro archivos seguían
citando "(D-16)" y apuntaban a nada.

Se repusieron los tres de H5 verbatim desde `main` y el de gráficos entró renumerado como
**D-19**. Vale anotar el modo de falla: nada lo detectó. No hay test ni linter que note
que un ADR citado no existe, y el archivo compila igual porque es Markdown. Lo que lo
delató fue ir a leer D-16 para construir a partir de él.

## La regla que sonaba equivalente y no lo era

D-19 decía, para no mezclar unidades en un eje, que la consulta de la serie tenía que
tener **exactamente dos columnas**. Suena razonable: `mes, altas` sí, `mes, moneda, monto`
no. Pasó los trece tests.

Contra la API real, el gráfico salió en `null`. El motivo es propio de este sistema:
`_lo_que_falta` le exige al modelo todos los escalones de la cascada en una sola fila, así
que cuando la respuesta es una serie el modelo escribe **una sola consulta con las dos
cosas** —`mes, total, activos, aprobados, con_fecha_de_alta, altas_del_periodo,
aprobados_sin_fecha_de_alta`, siete columnas y una pasada por la tabla—. Eso es lo que
conviene que haga, y la regla lo mataba.

La regla correcta es más precisa y dice lo que uno quería decir desde el principio: **el
valor horizontal no se repite**. Una fila por mes es una serie; dos filas por mes es una
serie partida por otra dimensión, y ésa es la que no se dibuja. Sigue atrapando
`mes, moneda, monto` —`mes` aparece dos veces— y deja pasar la cascada.

Ningún test lo habría encontrado, porque los trece los escribí yo con la misma idea
equivocada en la cabeza. Lo encontró una pregunta de verdad.

## La regla 8 estaba escrita como permiso

Corregido lo anterior, el gráfico siguió saliendo en `null`. El prompt tenía la regla y el
modelo la leía; simplemente elegía no usarla. La regla decía *"**podés** nombrar en
`grafico`…"* y cerraba con *"si la serie no salió sola, va en `null`, **y eso está
bien**"*, y vivía adentro de una sección titulada **"Las reglas que no se negocian"**,
entre siete prohibiciones. Un modelo prudente leyendo siete prohibiciones y un permiso
opcional toma el camino seguro.

Reescrita como obligación —*"declarala en `grafico`"`* — sin dejar de ser pasiva: sigue
prohibido ejecutar una consulta de más. Funcionó en el primer intento.

**Lo que queda de esto**: en un prompt donde todo lo demás es una prohibición, un permiso
opcional no se ejerce. Si algo tiene que pasar, se pide; si no, no se escribe.

## Dos cosas más que aparecieron dibujando

- **`to_char(fecha, 'YYYY-MM')` llega como texto, no como fecha.** Deducir barras-o-línea
  del tipo de Python daba **barras sobre cinco meses**, que es justo lo que tapa la
  tendencia. `2026-01` es temporal igual, y ahora se lee así.
- **La tabla del gráfico mostraba `mes` y `altas_del_periodo`**: nombres de columna de SQL
  en la pantalla de alguien que, por definición del producto, no lee SQL. No hay de dónde
  sacar un nombre humano —el contrato sólo trae el del SQL—, así que la tabla se quedó
  **sin encabezados**, con la categoría como `th scope="row"`. Es la misma decisión que ya
  toma la cascada de la derivación, que tampoco encabeza sus filas.

## La medición de cierre

`33×1`, US$ 4,12, comparada contra el cierre de H5 (D-17) y no contra la línea de base de
D-14. Lo que se buscaba no era una mejora: era que agregar un campo al esquema estricto no
moviera las otras treinta y dos preguntas.

| Categoría | Cierre H5 (D-17) | Cierre H7 |
|---|---|---|
| Contestable | 80 % | **93 %** |
| Ambigua | 88 % | 88 % |
| Incontestable | 90 % | 90 % |

Cero fugas cross-tenant, cero falsa ambigüedad, cero timeouts, un rechazo del gate.

**Los trece puntos de contestable no se cuentan como mérito de este hito.** Son una
corrida contra otra corrida, y D-18 ya advirtió exactamente esto: de los cinco arreglos de
H5, tres volvieron a fallar en la medición de cierre después de haber pasado aislados. Lo
que esta corrida sí muestra es que **no hubo regresión**, que era la pregunta.

Las tres que fallaron son conocidas y ninguna tiene que ver con gráficos: `c-004` (arranca
la cascada del universo equivocado) e `i-003` (publica un número donde debería negarse)
son las dos que D-18 ya había visto reaparecer; `a-007` eligió 62.702, que no es ninguna
de las dos lecturas admisibles.

## Lo que no se hizo, a propósito

- **Paneles por moneda.** Una serie multi-unidad se contesta sin dibujo. La regla original
  pedía un panel por moneda y estaba mal: si la única dimensión de la serie *es* la
  moneda, eso da cuatro paneles de una barra cada uno.
- **Calificar el gráfico.** No hay ningún assert sobre él. `h-007` está en el holdout y lo
  que custodia es que una serie no rompa la derivación, no que el dibujo esté bien.
