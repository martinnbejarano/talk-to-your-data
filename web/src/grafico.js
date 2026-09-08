// Qué se dibuja ya lo decidió el backend (`core/grafico.py`, D-19): si hay
// gráfico, si es de barras o de línea, y cuáles son los puntos. Acá no se decide
// nada de eso — se prepara lo que el componente necesita para pintarlo, igual que
// `derivacion.js` hace con la cascada.

import { numero } from "./formato.js";

// Seis rótulos entran en un teléfono sin encimarse. El resto de los puntos se
// dibuja igual: lo que se saltea es la etiqueta, no el dato.
const ROTULOS_EN_EL_EJE = 6;

export function leerGrafico(grafico) {
  if (!grafico || !Array.isArray(grafico.puntos) || grafico.puntos.length === 0) return null;

  const puntos = grafico.puntos.map(([bruto, valor]) => ({
    clave: String(bruto),
    etiqueta: etiquetaDe(bruto, grafico.marca),
    n: Number(valor),
    // El texto de la tabla se formatea en es-AR como cualquier otra cifra de la
    // pantalla. El dibujo usa `n`, que es aproximado porque un píxel lo es.
    texto: numero(Number(valor)),
  }));

  if (puntos.some((p) => Number.isNaN(p.n))) return null;

  const valores = puntos.map((p) => p.n);

  return {
    marca: grafico.marca,
    unidad: grafico.unidad,
    puntos,
    // **El eje de valores incluye siempre el cero.** Es la única forma de mentir
    // que el mapeo por columnas no previene: todos los números verdaderos y la
    // conclusión falsa.
    dominio: [Math.min(0, ...valores), Math.max(0, ...valores)],
    conRotulo: rotulados(puntos),
  };
}

/** Una fecha ISO se acorta —`2026-03-01` a `01/03`, `2026-03` a `03/2026`— porque
 * el rótulo entero no entra seis veces en el ancho de un teléfono. La tabla de
 * abajo muestra el valor completo. Cualquier otra cosa se muestra tal cual. */
function etiquetaDe(bruto, marca) {
  const texto = String(bruto);
  if (marca !== "linea") return texto;
  const [anio, mes, dia] = texto.slice(0, 10).split("-");
  if (!anio || !mes) return texto;
  return dia ? `${dia}/${mes}` : `${mes}/${anio}`;
}

/** Las claves que llevan rótulo en el eje horizontal. El primero y el último
 * entran siempre: son los que fijan de dónde a dónde va la serie. */
function rotulados(puntos) {
  if (puntos.length <= ROTULOS_EN_EL_EJE) return new Set(puntos.map((p) => p.clave));
  const paso = (puntos.length - 1) / (ROTULOS_EN_EL_EJE - 1);
  const claves = new Set([puntos[0].clave, puntos[puntos.length - 1].clave]);
  for (let i = 1; i < ROTULOS_EN_EL_EJE - 1; i++) claves.add(puntos[Math.round(i * paso)].clave);
  return claves;
}
