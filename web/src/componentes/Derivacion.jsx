import { leerDerivacion } from "../derivacion.js";
import { numero } from "../formato.js";

// Qué se dibuja lo decide `src/derivacion.js`, que es donde viven el corte
// resta→suma y el corte entre unidades. Acá sólo se pinta.
export function Derivacion({ derivacion, valorFinal, titulo }) {
  const { bloques, enTramos } = leerDerivacion(derivacion, valorFinal);
  if (bloques.length === 0) return null;

  return (
    <div className="derivacion">
      <h3>{titulo}</h3>
      <div className={enTramos ? "tramos" : undefined}>
        {bloques.map((bloque, i) => (
          <Bloque key={i} bloque={bloque} enTramos={enTramos} />
        ))}
      </div>
      {enTramos && (
        <p className="no-es-resta">
          <b>Ojo con restar de arriba abajo.</b> Entre tramos los números no se restan, porque cada
          tramo cuenta otra cosa.
        </p>
      )}
    </div>
  );
}

function Bloque({ bloque, enTramos }) {
  if (bloque.tipo === "cambio-de-unidad") {
    return (
      <p className="cambio-de-unidad">
        <span className="flecha">↓</span>
        <span>
          Acá <b>cambia lo que se cuenta</b>
          {bloque.de ? <>: se dejan de contar {bloque.de} y </> : <>: </>}
          se empiezan a contar {bloque.a ?? "otra cosa"}.
        </span>
      </p>
    );
  }

  // El rótulo dice la identidad que se verificó y nada más. No afirma que las
  // fuentes sean disjuntas: pasa en `riesgo_alto`, pero ningún campo del
  // contrato lo sostiene. La cuenta, en cambio, se puede rehacer a la vista.
  if (bloque.tipo === "fase") {
    return (
      <p className="fase">
        Hasta acá se descarta. <b>De acá para abajo se suma,</b> y la cuenta cierra:{" "}
        <span className="cuenta">
          {bloque.sumandos.map(numero).join(" + ")} = {numero(bloque.total)}
        </span>
      </p>
    );
  }

  const escalones = (
    <div className="escalones">
      {bloque.filas.map((fila) => (
        <Escalon key={fila.clave} fila={fila} />
      ))}
    </div>
  );

  if (!enTramos) return escalones;

  return (
    <div className="tramo">
      {bloque.unidad && <span className="unidad">Se cuentan {bloque.unidad}</span>}
      {escalones}
    </div>
  );
}

function Escalon({ fila }) {
  const clases = ["escalon"];
  if (fila.sangria) clases.push("sangria");
  if (fila.esResultado) clases.push("resultado");
  if (fila.apagado) clases.push("apagado");

  return (
    <div className={clases.join(" ")}>
      <span className="txt">{fila.texto}</span>
      <span className="num">{numero(fila.n)}</span>
      {fila.delta !== null && (
        <span className="delta">
          {fila.delta === 0 ? "no quedó ninguno afuera" : `−${numero(fila.delta)}`}
        </span>
      )}
    </div>
  );
}
