// Dibujados acá y no tomados de una fuente de íconos: son cinco, todos con el
// mismo trazo de 1.5 y la misma caja de 16, y una dependencia entera para eso
// pesaría más que este archivo.

const base = {
  width: 16,
  height: 16,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export function Chevron({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M4 6.5 8 10.5l4-4" />
    </svg>
  );
}

export function Flecha() {
  return (
    <svg {...base} width="17" height="17" viewBox="0 0 17 17">
      <path d="M8.5 13.5v-10" />
      <path d="M4 8l4.5-4.5L13 8" />
    </svg>
  );
}

export function Baja() {
  return (
    <svg {...base} width="14" height="14" viewBox="0 0 16 16">
      <path d="M8 3v10" />
      <path d="M4 9l4 4 4-4" />
    </svg>
  );
}

export function Marcador() {
  return (
    <svg {...base}>
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.5v3.25" />
      <path d="M8 5.1v.6" />
    </svg>
  );
}

export function Hueco() {
  return (
    <svg {...base}>
      <circle cx="8" cy="8" r="6.25" strokeDasharray="2.6 2.2" />
      <path d="M5.6 8h4.8" />
    </svg>
  );
}

export function Alerta() {
  return (
    <svg {...base}>
      <path d="M8 2.6 14.2 13H1.8L8 2.6Z" />
      <path d="M8 6.6v3" />
      <path d="M8 11.2v.5" />
    </svg>
  );
}
