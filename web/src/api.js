// Las tres llamadas al backend. Ninguna interpreta lo que trae: el contrato
// llega entero, la pantalla lo dibuja campo por campo y **el front nunca parsea
// el texto libre que escribe el modelo**.

import { API_URL } from "./config.js";

export async function traerInstituciones() {
  return pedir("/instituciones");
}

/** Sincrónico y sin streaming: tarda entre 13 y 20 segundos, así que la pantalla
 * necesita su propio estado de "pensando" mientras esto está en vuelo. */
export async function preguntar({ institucionId, pregunta, historial }) {
  return pedir("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      institucion_id: institucionId,
      pregunta,
      historial,
    }),
  });
}

export async function traerAuditoria(trazaId) {
  return pedir(`/auditoria/${encodeURIComponent(trazaId)}`);
}

async function pedir(camino, opciones) {
  const respuesta = await fetch(`${API_URL}${camino}`, opciones);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    throw new Error(`${respuesta.status} ${respuesta.statusText} · ${cuerpo.slice(0, 300)}`);
  }
  return respuesta.json();
}
