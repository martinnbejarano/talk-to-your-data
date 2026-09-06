import { numero, fechaLarga } from "../formato.js";

// La institución y la fecha de corte se repiten acá, y no sólo en la barra,
// porque es el número lo que alguien va a copiar en un mail.
export function Cifra({ valor, institucion, fechaDeCorte }) {
  return (
    <div className="cifra">
      <span className={`n${String(numero(valor.n)).length > 7 ? " chica" : ""}`}>
        {numero(valor.n)}
      </span>
      <span className="unidad">{valor.unidad}</span>
      <span className="contexto">
        {institucion} · situación al {fechaLarga(fechaDeCorte)}
      </span>
    </div>
  );
}
