import { useState } from "react";

import { traerAuditoria } from "../api.js";
import { numero } from "../formato.js";

/** Plegado y rotulado, nunca escondido: el rótulo dice para quién es, para que
 * su ausencia en la lectura normal del oficial no parezca ocultamiento.
 *
 * La traza se pide recién al abrir el bloque: el contrato ya trae `queries` con
 * su plan y su tiempo, y `GET /auditoria/{traza_id}` no vale una llamada que
 * nadie pidió.
 */
export function DetalleTecnico({ contrato }) {
  const [traza, setTraza] = useState(null);
  const [seCayo, setSeCayo] = useState(null);

  async function alAbrir(evento) {
    if (!evento.target.open || traza || seCayo) return;
    try {
      setTraza(await traerAuditoria(contrato.traza_id));
    } catch (error) {
      // Una traza que ya no está no es una falla de la pantalla: viven en la
      // memoria del proceso. Se dice, y el resto del bloque se dibuja igual.
      setSeCayo(String(error.message ?? error));
    }
  }

  return (
    <details className="tecnico" onToggle={alAbrir}>
      <summary>
        <span className="titulo-it">Detalle técnico — para IT</span>
        <span className="para-quien">
          SQL, plan de ejecución y tiempos. Esta parte no está escrita para vos: es para tu equipo
          de sistemas.
        </span>
      </summary>
      <div className="cuerpo-it">
        <div>
          <h4>Identificador de la traza</h4>
          <div className="kv">
            <span>
              <b>{contrato.traza_id}</b>
            </span>
          </div>
        </div>

        {traza && (
          <div>
            <h4>Qué costó la respuesta</h4>
            <div className="kv">
              <span>
                pasos del agente <b>{traza.pasos}</b>
              </span>
              <span>
                rechazos del gate <b>{traza.rechazos_del_gate}</b>
              </span>
              <span>
                tokens <b>{numero(traza.tokens?.total ?? 0)}</b>
              </span>
              <span>
                punta a punta <b>{numero(Math.round(traza.ms))} ms</b>
              </span>
            </div>
          </div>
        )}

        {seCayo && (
          <div>
            <h4>La traza</h4>
            <p>
              No se pudo leer la traza: <code>{seCayo}</code>. Las trazas viven en la memoria del
              proceso y no sobreviven a un reinicio del servidor.
            </p>
          </div>
        )}

        {traza && <RechazosDelGate pasos={traza.detalle} />}

        {(contrato.queries ?? []).map((consulta, i) => (
          <div key={i}>
            <h4>
              Consulta ejecutada {i + 1} de {contrato.queries.length} · {numero(Math.round(consulta.ms))} ms
            </h4>
            <pre>{consulta.sql}</pre>
            <details>
              <summary>Plan de ejecución</summary>
              <pre>{JSON.stringify(consulta.plan, null, 2)}</pre>
            </details>
          </div>
        ))}

        <div>
          <h4>El contrato, tal como lo lee la pantalla</h4>
          <pre>{JSON.stringify(contrato, null, 2)}</pre>
        </div>
      </div>
    </details>
  );
}

/** El único lugar donde queda el SQL que no llegó a ejecutarse: `queries` lleva
 * sólo las que pasaron, y sin esto no se explica por qué una respuesta costó
 * tres pasos más de lo normal. */
function RechazosDelGate({ pasos }) {
  const rechazos = (pasos ?? []).flatMap((paso) =>
    (paso.tools ?? [])
      .filter((llamada) => llamada.resultado?.clase === "RECHAZADA")
      .map((llamada) => ({ paso: paso.paso, ...llamada })),
  );
  if (rechazos.length === 0) return null;

  return (
    <div>
      <h4>Rechazos del gate</h4>
      {rechazos.map((rechazo, i) => (
        <div key={i}>
          <p>
            Paso {rechazo.paso} · {rechazo.resultado.motivo}
          </p>
          <p className="ejemplo">Sugerencia devuelta al agente: {rechazo.resultado.sugerencia}</p>
          {rechazo.argumentos?.sql && <pre>{rechazo.argumentos.sql}</pre>}
        </div>
      ))}
    </div>
  );
}
