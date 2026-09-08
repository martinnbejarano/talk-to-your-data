import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { scaleBand, scaleLinear, scalePoint } from "@visx/scale";
import { Bar, LinePath } from "@visx/shape";

import { numero } from "../formato.js";
import { leerGrafico } from "../grafico.js";
import "../grafico.css";

/** El dibujo de una serie (D-19), y sólo de una serie: si el backend no mandó
 * `grafico`, acá no hay nada que decidir ni que ofrecer.
 *
 * Va **fuera de la gaveta**, arriba y junto a la oración. El SVG es
 * `aria-hidden` y debajo va la misma serie en una tabla desplegada, que es el
 * precedente que ya sentó la derivación: la barra es decoración, el número es el
 * dato. La tabla no es una cortesía opcional — es la única forma de leer esto
 * con un lector de pantalla, y también es lo que se le muestra a un auditor.
 */
export function Grafico({ grafico }) {
  const serie = leerGrafico(grafico);
  if (!serie) return null;

  return (
    <section className="grafico">
      <p className="unidad">Se cuentan {serie.unidad}</p>
      <Lienzo serie={serie} />
      <Tabla serie={serie} />
    </section>
  );
}

// Coordenadas del `viewBox` y no píxeles: el SVG escala al ancho de la columna,
// así que en un teléfono se achica entero en vez de recortarse.
const ANCHO = 680;
const ALTO = 190;
// El margen derecho es el ancho de medio rótulo del eje: sin él, el último —"05/2026"—
// se corta contra el borde de la columna en un teléfono.
const MARGEN = { arriba: 12, derecha: 30, abajo: 30, izquierda: 62 };

const UTIL = {
  ancho: ANCHO - MARGEN.izquierda - MARGEN.derecha,
  alto: ALTO - MARGEN.arriba - MARGEN.abajo,
};

function Lienzo({ serie }) {
  const y = scaleLinear({ domain: serie.dominio, range: [UTIL.alto, 0], nice: true });
  const claves = serie.puntos.map((p) => p.clave);

  const escalaX =
    serie.marca === "barras"
      ? scaleBand({ domain: claves, range: [0, UTIL.ancho], padding: 0.3 })
      : scalePoint({ domain: claves, range: [0, UTIL.ancho] });

  const rotulo = (clave) => {
    const punto = serie.puntos.find((p) => p.clave === clave);
    return serie.conRotulo.has(clave) ? punto.etiqueta : "";
  };

  return (
    <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} aria-hidden="true">
      <Group left={MARGEN.izquierda} top={MARGEN.arriba}>
        <AxisLeft scale={y} numTicks={4} hideAxisLine tickLength={4} tickFormat={numero} />
        <AxisBottom scale={escalaX} top={UTIL.alto} tickFormat={rotulo} tickLength={4} />
        {serie.marca === "barras" ? (
          <Barras serie={serie} x={escalaX} y={y} />
        ) : (
          <Linea serie={serie} x={escalaX} y={y} />
        )}
      </Group>
    </svg>
  );
}

function Barras({ serie, x, y }) {
  const piso = y(0);
  return serie.puntos.map((punto) => (
    <Bar
      key={punto.clave}
      className="marca"
      x={x(punto.clave)}
      y={Math.min(piso, y(punto.n))}
      width={x.bandwidth()}
      height={Math.abs(piso - y(punto.n))}
    />
  ));
}

function Linea({ serie, x, y }) {
  return (
    <>
      <LinePath
        className="marca trazo"
        data={serie.puntos}
        x={(punto) => x(punto.clave)}
        y={(punto) => y(punto.n)}
      />
      {serie.puntos.map((punto) => (
        <circle key={punto.clave} className="marca" cx={x(punto.clave)} cy={y(punto.n)} r={3} />
      ))}
    </>
  );
}

/** Los mismos números, siempre desplegados. El dibujo sirve para ver la forma;
 * esto es lo que se defiende ante un auditor, y eso no se hace desde un tooltip.
 *
 * **Sin encabezados.** Los nombres que trae el contrato son los de las columnas
 * del SQL —`altas_del_periodo`— y el oficial no lee SQL. La categoría va como
 * `th` de fila, que es lo que la vuelve legible con un lector de pantalla sin
 * poner una palabra técnica en la pantalla; qué se cuenta ya lo dice el rótulo de
 * arriba. Es la misma decisión que toma la cascada de la derivación, que tampoco
 * encabeza sus filas. */
function Tabla({ serie }) {
  return (
    <div className="tabla-wrap">
      <table>
        <caption className="sr-only">Los {serie.unidad} de cada punto del gráfico</caption>
        <tbody>
          {serie.puntos.map((punto) => (
            <tr key={punto.clave}>
              <th scope="row">{punto.clave}</th>
              <td>{punto.texto}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
