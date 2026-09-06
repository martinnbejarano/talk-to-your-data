// La lista se muestra tal como viene y no se completa: `exclusiones` la escribe
// el modelo y ningún campo del contrato la sostiene —a diferencia de cada `n`,
// que se verifica contra una consulta ejecutada—, así que la pantalla no afirma
// que cada exclusión listada haya dejado algo afuera.
export function Exclusiones({ exclusiones }) {
  if (!exclusiones || exclusiones.length === 0) return null;

  return (
    <div className="afuera">
      <h3>Qué no está contado acá adentro</h3>
      <ul>
        {exclusiones.map((exclusion, i) => (
          <li key={i}>{exclusion}</li>
        ))}
      </ul>
    </div>
  );
}
