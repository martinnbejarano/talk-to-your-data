import { useState } from "react";

import { Definicion } from "./Definicion.jsx";
import { Derivacion } from "./Derivacion.jsx";
import { Exclusiones } from "./Exclusiones.jsx";
import { Filas } from "./Filas.jsx";
import { Grafico } from "./Grafico.jsx";
import { Opciones, Supuesto, SinNumero } from "./BloqueDeEstado.jsx";
import { Chevron } from "./Iconos.jsx";
import { numero } from "../formato.js";

/** **El nombre del estado no aparece nunca en pantalla.** El estado decide qué
 * se dibuja —el supuesto declarado, las opciones, o que no hay número— y ahí
 * termina su papel: lo que el oficial ve es la consecuencia, no la etiqueta.
 *
 * Sin tocar nada se lee **una sola oración**. Todo lo que la sostiene vive
 * detrás de "Mostrar más", y adentro va en el orden en que se audita: primero
 * **qué se contó**, que es lo que decide si el número está bien, y recién
 * después la aritmética que lo produjo.
 *
 * El SQL, el plan y los tiempos ya no están en la pantalla: viven en los logs
 * de la API, contra `traza_id`, que es lo único de esa parte que queda acá.
 */
export function Respuesta({ contrato, alElegirOpcion, bloqueado }) {
  const [mas, setMas] = useState(false);

  const hayDerivacion = (contrato.derivacion ?? []).length > 0;
  const hayMas =
    hayDerivacion ||
    (contrato.definiciones_usadas ?? []).length > 0 ||
    (contrato.exclusiones ?? []).length > 0 ||
    (contrato.filas?.muestra ?? []).length > 0;

  return (
    <div className="respuesta">
      <p className="frase">{contrato.respuesta}</p>

      {/* El supuesto no está detrás de ningún botón: es una condición de la
          oración de arriba, no un detalle de respaldo. */}
      <Supuesto supuestos={contrato.supuestos} />

      {/* Fuera de la gaveta y después del supuesto (D-19): hay gráfico sólo donde
          la respuesta ya era una serie, y el supuesto es una condición de la
          oración de arriba que no se puede separar de ella. */}
      <Grafico grafico={contrato.grafico} />

      {contrato.estado === "NO_SE_PUEDE_RESPONDER" && <SinNumero />}

      <Opciones opciones={contrato.opciones} alElegir={alElegirOpcion} bloqueado={bloqueado} />

      {hayMas && (
        <div className="acciones">
          <button type="button" className="boton" aria-expanded={mas} onClick={() => setMas(!mas)}>
            Mostrar más
            <Chevron className="caret" />
          </button>
        </div>
      )}

      {hayMas && (
        <Gaveta abierta={mas}>
          <Definicion definiciones={contrato.definiciones_usadas} />
          <Derivacion
            derivacion={contrato.derivacion}
            valorFinal={contrato.valor?.n ?? null}
            titulo={tituloDeLaDerivacion(contrato)}
          />
          <Exclusiones exclusiones={contrato.exclusiones} />
          {/* Un nivel más adentro: las filas son lo más pesado de leer. */}
          <Filas filas={contrato.filas} />
          {/* Lo único que sobrevive del bloque técnico: sin este número, un
              problema reportado por el oficial no se encuentra en los logs. */}
          <p className="traza">
            Si algo de esta respuesta no cierra, pasale este número a tu equipo de sistemas:{" "}
            <code>{contrato.traza_id}</code>
          </p>
        </Gaveta>
      )}
    </div>
  );
}

/** El alto se anima con `grid-template-rows: 0fr → 1fr`, que es la única forma
 * de hacerlo sin medir el contenido en JS. El contenido queda montado: plegarlo
 * y desmontarlo perdería el scroll de la tabla de filas y el estado del bloque
 * técnico, que pide la traza una sola vez. */
function Gaveta({ abierta, children }) {
  return (
    <div className={abierta ? "gaveta abierta" : "gaveta"}>
      <div>
        <div className="adentro" inert={abierta ? undefined : true}>
          {children}
        </div>
      </div>
    </div>
  );
}

function tituloDeLaDerivacion(contrato) {
  if (contrato.valor) return `Cómo se llegó a ${numero(contrato.valor.n)}`;
  if (contrato.estado === "NECESITO_QUE_ACLARES") return "Cómo se llegó a las opciones";
  return "Dónde se buscó";
}
