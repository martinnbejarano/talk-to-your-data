// es-AR en todos lados: es el formato contra el que el validador de
// trazabilidad del backend lee las cifras de `respuesta`.
const NUMEROS = new Intl.NumberFormat("es-AR");

export function numero(n) {
  if (typeof n !== "number" || Number.isNaN(n)) return "—";
  return NUMEROS.format(n);
}

/** Se parte el texto a mano y no con `new Date()`: `new Date("2026-03-01")` se
 * interpreta en UTC y al oeste de Greenwich retrocede un día, y una fecha de
 * vigencia corrida un día es el error que esta pantalla existe para no cometer. */
export function fecha(iso) {
  if (!iso) return null;
  const [anio, mes, dia] = String(iso).slice(0, 10).split("-");
  if (!anio || !mes || !dia) return String(iso);
  return `${dia}/${mes}/${anio}`;
}

const MESES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

export function fechaLarga(iso) {
  if (!iso) return null;
  const [anio, mes, dia] = String(iso).slice(0, 10).split("-");
  const nombre = MESES[Number(mes) - 1];
  if (!nombre) return String(iso);
  return `${Number(dia)} de ${nombre} de ${anio}`;
}
