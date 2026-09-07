import { fechaLarga } from "../formato.js";
import { Chevron } from "./Iconos.jsx";

// Institución y fecha de corte se ven en todos los estados, incluido el que no
// trae número: "este año" se interpreta contra la fecha de corte y no contra el
// calendario de quien mira.
export function BarraInstitucion({ instituciones, institucionId, alElegir, fechaDeCorte, bloqueado }) {
  return (
    <header className="barra">
      <div className="columna">
        <span className="institucion">
          <label className="sr-only" htmlFor="institucion">
            Institución
          </label>
          <select
            id="institucion"
            value={institucionId ?? ""}
            disabled={bloqueado || instituciones.length === 0}
            onChange={(evento) => alElegir(Number(evento.target.value))}
          >
            {instituciones.length === 0 && <option value="">Cargando…</option>}
            {instituciones.map((institucion) => (
              <option key={institucion.institucion_id} value={institucion.institucion_id}>
                {institucion.nombre}
              </option>
            ))}
          </select>
          <span className="chevron">
            <Chevron />
          </span>
        </span>
        <span className="corte">
          Datos al <b>{fechaLarga(fechaDeCorte)}</b>
        </span>
      </div>
    </header>
  );
}
