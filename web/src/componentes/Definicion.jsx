import { fecha } from "../formato.js";

/** `origen` es texto libre: lo que no esté acá se muestra tal cual, porque el
 * modelo escribe "definición curada" tanto como `tenant_config` y callarlo
 * perdería la mitad de los orígenes reales. El filo es que un `tenant_*` sin
 * mapear pone la palabra "tenant" delante del oficial; el arreglo es que el
 * contrato acote `origen` a un enum. */
const ORIGENES = {
  tenant_config: "lo fijó tu institución",
  sistema: "es una definición del sistema, igual para todas las instituciones",
};

export function Definicion({ definiciones }) {
  if (!definiciones || definiciones.length === 0) return null;

  return (
    <div className="definicion">
      <span className="rotulo">
        {definiciones.length === 1 ? "Definición aplicada" : "Definiciones aplicadas"}
      </span>
      {/* La clave es la posición y no el concepto: una respuesta puede traer el
          mismo concepto dos veces, una por cada parámetro. */}
      {definiciones.map((definicion, i) => (
        <div key={i} className="una-definicion">
          <p>{definicion.texto}</p>
          <div className="parametros">
            <span className="parametro">
              <b>{definicion.parametro ?? "sin parámetros de tu institución"}</b>
              {definicion.origen && (
                <span className="origen">· {ORIGENES[definicion.origen] ?? definicion.origen}</span>
              )}
              <span className="antes">{desdeCuando(definicion.vigente_desde)}</span>
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** `vigente_desde: null` se dice —"nunca cambió"— y no se omite la línea:
 * omitirla dejaría al oficial sin saber si el parámetro tiene una sola versión o
 * si nadie se fijó, y tomar la versión vieja de un umbral es el error más caro de
 * esta base. */
function desdeCuando(vigenteDesde) {
  if (!vigenteDesde) return "Nunca cambió: el parámetro tiene una sola versión.";
  return `Rige desde el ${fecha(vigenteDesde)}.`;
}
