export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Copia de `core.config.AS_OF`, que es el valor verdadero: el contrato no trae
// la fecha de corte y la pantalla la muestra siempre. Se puede desincronizar; el
// arreglo es un campo del contrato.
export const FECHA_DE_CORTE = import.meta.env.VITE_FECHA_DE_CORTE ?? "2026-06-01";
