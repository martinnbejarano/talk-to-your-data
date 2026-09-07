import { leerDerivacion } from "../derivacion.js";
import { numero } from "../formato.js";
import { Baja } from "./Iconos.jsx";

// Qué se dibuja lo decide `src/derivacion.js`, que es donde viven el corte
// resta→suma y el corte entre unidades. Acá sólo se pinta.
export function Derivacion({ derivacion, valorFinal, titulo }) {
  const { bloques, enTramos } = leerDerivacion(derivacion, valorFinal);
  if (bloques.length === 0) return null;

  return (
    <section className="seccion derivacion">
      <h3>{titulo}</h3>
      <div className={enTramos ? "tramos" : undefined}>
        {bloques.map((bloque, i) => (
          <Bloque key={i} bloque={bloque} enTramos={enTramos} />
        ))}
      </div>
      {enTramos && (
        <p className="no-es-resta">
          <b>Ojo con restar de arriba abajo.</b> Entre tramos los números no se restan, porque cada
          tramo cuenta otra cosa. Las barras tampoco se comparan de un tramo al otro: donde cambia
          lo que se cuenta, la escala vuelve a empezar.
        </p>
      )}
    </section>
  );
}

function Bloque({ bloque, enTramos }) {
  if (bloque.tipo === "cambio-de-unidad") {
    return (
      <p className="cambio-de-unidad">
        <span className="flecha">
          <Baja />
        </span>
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

  // `tope` lo trae el bloque y vale para el tramo entero: la escala nunca cruza
  // un cambio de unidad, porque comparar alertas contra clientes daría una
  // proporción que no significa nada.
  const escalones = (
    <div className="escalones">
      {bloque.filas.map((fila) => (
        <Escalon key={fila.clave} fila={fila} tope={bloque.tope} />
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

function Escalon({ fila, tope }) {
  const clases = ["escalon"];
  if (fila.sangria) clases.push("sangria");
  if (fila.esResultado) clases.push("resultado");
  if (fila.apagado) clases.push("apagado");

  // Un escalón que no es cero nunca se dibuja como cero: sin el piso, 660 sobre
  // 180.000 desaparece y el ojo lee "ninguno" donde hay 660. **El cero sí se
  // dibuja como cero**: el piso es para los chicos, no para los que no están.
  const proporcion =
    typeof fila.n !== "number" || tope <= 0
      ? null
      : fila.n === 0
        ? 0
        : Math.max(Math.abs(fila.n) / tope, 0.004);

  return (
    <div className={clases.join(" ")}>
      <span className="txt">{fila.texto}</span>
      <span className="num">{numero(fila.n)}</span>
      {fila.delta !== null && (
        <span className="delta">
          {fila.delta === 0 ? "no quedó ninguno afuera" : `−${numero(fila.delta)}`}
        </span>
      )}
      {proporcion !== null && (
        <span className="escala" aria-hidden="true">
          <span style={{ width: `${proporcion * 100}%` }} />
        </span>
      )}
    </div>
  );
}
