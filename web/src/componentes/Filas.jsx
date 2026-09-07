import { numero } from "../formato.js";

// `filas: null` es el caso normal de las cascadas, que devuelven los escalones
// en una sola fila: esa fila ya está dibujada, y es la derivación.
export function Filas({ filas }) {
  if (!filas || !filas.muestra || filas.muestra.length === 0) return null;

  return (
    <details className="filas">
      <summary>
        Ver las filas de la consulta
        <span className="glosa">
          muestra de {filas.muestra.length} sobre {numero(filas.total)}
        </span>
      </summary>
      <div className="tabla-wrap">
        <table>
          <thead>
            <tr>
              {filas.columnas.map((columna, i) => (
                <th key={i}>{columna}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.muestra.map((fila, i) => (
              <tr key={i}>
                {fila.map((celda, j) => (
                  <td key={j}>{celda === null ? "—" : String(celda)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pie-tabla">
        Mostrando {filas.muestra.length} de {numero(filas.total)} filas.
      </p>
    </details>
  );
}
