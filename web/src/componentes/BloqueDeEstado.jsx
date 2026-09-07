import { Hueco, Marcador } from "./Iconos.jsx";
import { enMinuscula, numero } from "../formato.js";

/** El supuesto se lee como una oración sola —"Se asumió que ..."— y no como un
 * bloque con título: anunciar que hubo una elección antes de decir cuál fue
 * costaba una línea entera para no decir todavía nada.
 *
 * Con más de un supuesto la costura no cierra en una oración, así que el "Se
 * asumió que" pasa a encabezar la lista y cada supuesto queda entero. */
export function Supuesto({ supuestos }) {
  if (!supuestos || supuestos.length === 0) return null;

  const uno = supuestos.length === 1;

  return (
    <div className="marca supuesto">
      <span className="icono">
        <Marcador />
      </span>
      <div>
        {uno ? (
          <p>
            <b>Se asumió que</b> {enMinuscula(supuestos[0])}
          </p>
        ) : (
          <>
            <p>
              <b>Se asumió que:</b>
            </p>
            {supuestos.map((supuesto, i) => (
              <p key={i}>{supuesto}</p>
            ))}
          </>
        )}
      </div>
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
 * modelo. La causa queda donde está escrita: en la oración de arriba.
 */
export function SinNumero() {
  return (
    <div className="marca hueco">
      <span className="icono">
        <Hueco />
      </span>
      <p>
        <b>Acá no hay número, y no es cero.</b> Cero querría decir que la respuesta es ninguno, y
        eso sería una respuesta. Cualquier cifra que te diera sería inventada.
      </p>
    </div>
  );
}
