import { fecha } from "../formato.js";

/** `origen` es texto libre: lo que no esté acá se muestra tal cual, porque el
 * modelo escribe "definición curada" tanto como `tenant_config` y callarlo
 * perdería la mitad de los orígenes reales. El filo es que un `tenant_*` sin
 * mapear pone la palabra "tenant" delante del oficial; el arreglo es que el
 * contrato acote `origen` a un enum. */
const ORIGENES = {
  tenant_config: "tu institución",
  sistema: "el sistema, igual para todas las instituciones",
};

/** Va primero adentro de "Mostrar más": el criterio es lo que decide si el
 * número está bien. La aritmética viene después y sólo importa si el criterio
 * ya convenció. */
export function Definicion({ definiciones }) {
  if (!definiciones || definiciones.length === 0) return null;

  return (
    <section className="seccion definicion">
      <h3>{definiciones.length === 1 ? "Qué se contó" : "Qué se contó, concepto por concepto"}</h3>
      {/* La clave es la posición y no el concepto: una respuesta puede traer el
          mismo concepto dos veces, una por cada parámetro. */}
      {definiciones.map((definicion, i) => (
        <div key={i} className="una-definicion">
          <p>{definicion.texto}</p>
          <dl className="procedencia">
            <div>
              <dt>Parámetro</dt>
              <dd>{definicion.parametro ?? "Ninguno de tu institución"}</dd>
            </div>
            <div>
              <dt>Lo fijó</dt>
              <dd>{ORIGENES[definicion.origen] ?? definicion.origen ?? "sin declarar"}</dd>
            </div>
            <Vigencia vigenteDesde={definicion.vigente_desde} />
          </dl>
        </div>
      ))}
    </section>
  );
}

/** `vigente_desde: null` se dice —"nunca cambió"— y no se omite la línea:
 * omitirla dejaría al oficial sin saber si el parámetro tiene una sola versión o
 * si nadie se fijó, y tomar la versión vieja de un umbral es el error más caro de
 * esta base. */
function Vigencia({ vigenteDesde }) {
  if (!vigenteDesde) {
    return (
      <div>
        <dt>Versiones</dt>
        <dd>Una sola: nunca cambió</dd>
      </div>
    );
  }
  return (
    <div>
      <dt>Rige desde</dt>
      <dd>{fecha(vigenteDesde)}</dd>
    </div>
  );
}
