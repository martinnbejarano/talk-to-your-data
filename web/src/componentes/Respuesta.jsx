import { Cifra } from "./Cifra.jsx";
import { Definicion } from "./Definicion.jsx";
import { Derivacion } from "./Derivacion.jsx";
import { DetalleTecnico } from "./DetalleTecnico.jsx";
import { Exclusiones } from "./Exclusiones.jsx";
import { Filas } from "./Filas.jsx";
import { Hueco, Opciones, Supuesto } from "./BloqueDeEstado.jsx";
import { numero } from "../formato.js";

/** **El nombre del estado no aparece nunca en pantalla.** El estado decide qué
 * se dibuja —el supuesto declarado, las opciones, o qué falta— y ahí termina su
 * papel: lo que el oficial ve es la consecuencia, no la etiqueta.
 */
export function Respuesta({ contrato, pregunta, institucion, fechaDeCorte, alElegirOpcion, bloqueado }) {
  const hayNumero = contrato.valor !== null && contrato.valor !== undefined;
  const hayDerecha =
    (contrato.derivacion ?? []).length > 0 || (contrato.exclusiones ?? []).length > 0;

  return (
    <>
      <h2 className="pregunta">{pregunta}</h2>

      <div className={hayDerecha ? "cols" : "cols sin-derecha"}>
        <div className="izq">
          {hayNumero ? (
            <>
              <Cifra valor={contrato.valor} institucion={institucion} fechaDeCorte={fechaDeCorte} />
              {contrato.respuesta && <p className="en-palabras">{contrato.respuesta}</p>}
            </>
          ) : (
            // Donde iría el número va una frase del mismo tamaño, nunca un cero.
            <p className="en-lugar-del-numero">{contrato.respuesta}</p>
          )}

          {contrato.estado === "NO_SE_PUEDE_RESPONDER" && <Hueco />}

          <Supuesto supuestos={contrato.supuestos} />

          <Opciones
            opciones={contrato.opciones}
            alElegir={alElegirOpcion}
            bloqueado={bloqueado}
          />

          <Definicion definiciones={contrato.definiciones_usadas} />

          <Filas filas={contrato.filas} />
        </div>

        {hayDerecha && (
          <div className="der">
            <Derivacion
              derivacion={contrato.derivacion}
              valorFinal={contrato.valor?.n ?? null}
              titulo={tituloDeLaDerivacion(contrato)}
            />
            <Exclusiones exclusiones={contrato.exclusiones} />
          </div>
        )}
      </div>

      <DetalleTecnico contrato={contrato} />
    </>
  );
}

function tituloDeLaDerivacion(contrato) {
  if (contrato.valor) return `Cómo se llegó a ${numero(contrato.valor.n)}`;
  if (contrato.estado === "NECESITO_QUE_ACLARES") return "Cómo se llegó a las opciones";
  return "Dónde se buscó";
}
