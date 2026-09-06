import { numero } from "../formato.js";

export function Supuesto({ supuestos }) {
  if (!supuestos || supuestos.length === 0) return null;

  return (
    <div className="bloque supuesto">
      <h3>Eligió por vos</h3>
      {supuestos.map((supuesto, i) => (
        <p key={i}>{supuesto}</p>
      ))}
    </div>
  );
}

export function Opciones({ opciones, alElegir, bloqueado }) {
  if (!opciones || opciones.length === 0) return null;

  return (
    <div className="opciones">
      {opciones.map((opcion, i) => (
        <button
          type="button"
          className="opcion"
          key={i}
          disabled={bloqueado}
          onClick={() => alElegir(opcion.texto)}
        >
          <span className="titulo">{opcion.texto}</span>
          {/* El `n` va sólo si vino: el contrato lo trae únicamente cuando las
              dos lecturas se ejecutaron, y un número sin consulta detrás es lo
              que D-04 prohíbe. */}
          {typeof opcion.n === "number" && <span className="n">{numero(opcion.n)}</span>}
        </button>
      ))}
    </div>
  );
}

/** El bloque es deliberadamente calmo —indigo pizarra, **sin rojo y sin ícono de
 * alerta**—: no es un error del programa y se tiene que leer como rigor.
 *
 * Tampoco dice cuál es la causa. `NO_SE_PUEDE_RESPONDER` cubre dos cosas —que el
 * dato no exista, y que el sistema no haya podido sostener el número contra la
 * traza—, llegan con el mismo `estado`, y separarlas pediría leer la prosa del
 * modelo. La causa queda donde está escrita: en `respuesta`, arriba.
 */
export function Hueco() {
  return (
    <div className="bloque hueco">
      <h3>No es cero</h3>
      <p>
        Cero querría decir que la respuesta es ninguno, y eso sería una respuesta. Acá no hay
        número, y arriba está el porqué: cualquier cifra que te diera sería inventada.
      </p>
    </div>
  );
}
