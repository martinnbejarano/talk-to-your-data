import { useEffect, useRef, useState } from "react";

import { preguntar, traerInstituciones } from "./api.js";
import { FECHA_DE_CORTE } from "./config.js";
import { BarraInstitucion } from "./componentes/BarraInstitucion.jsx";
import { Respuesta } from "./componentes/Respuesta.jsx";

// Un atajo, no una lista de preguntas permitidas: es la única con valor esperado
// conocido —7.859 en Banco Andino, 321 en Fintech Cuyo—.
const PREGUNTA_DE_REFERENCIA = "¿Cuántos clientes de riesgo alto tenemos?";

export function App() {
  const [instituciones, setInstituciones] = useState([]);
  const [institucionId, setInstitucionId] = useState(null);
  const [texto, setTexto] = useState(PREGUNTA_DE_REFERENCIA);

  // Distinta de `texto`: si el oficial empieza a escribir la siguiente, la
  // pregunta de arriba tiene que seguir siendo la que se contestó.
  const [preguntaContestada, setPreguntaContestada] = useState(null);
  const [contrato, setContrato] = useState(null);

  // `[{pregunta, respuesta}]`. Los arrastra el front porque el servidor no
  // guarda sesiones.
  const [historial, setHistorial] = useState([]);

  const [pensando, setPensando] = useState(false);
  const [seCayo, setSeCayo] = useState(null);

  useEffect(() => {
    traerInstituciones()
      .then((traidas) => {
        setInstituciones(traidas);
        if (traidas.length > 0) setInstitucionId(traidas[0].institucion_id);
      })
      .catch((error) => setSeCayo(String(error.message ?? error)));
  }, []);

  /** **Una pregunta escrita a mano siempre va con `turnos` vacío**, y sólo el
   * clic en una opción arrastra los turnos previos. Un número que dependa de una
   * pregunta que ya no está en pantalla no se puede defender ante un auditor: el
   * historial existe para cerrar una repregunta —ahí el turno previo sí está a la
   * vista— y no para convertir esto en un chat con memoria.
   */
  async function mandar(pregunta, turnos) {
    if (!pregunta.trim() || institucionId === null) return;
    setPensando(true);
    setSeCayo(null);
    setPreguntaContestada(pregunta);
    setContrato(null);
    try {
      const vuelta = await preguntar({ institucionId, pregunta, historial: turnos });
      setContrato(vuelta);
      setHistorial([...turnos, { pregunta, respuesta: vuelta.respuesta }]);
    } catch (error) {
      setSeCayo(String(error.message ?? error));
    } finally {
      setPensando(false);
    }
  }

  // Vuelve al backend como pregunta nueva con el turno de la repregunta adjunto:
  // así se cierra la aclaración sin sesión en el servidor y sin que el oficial
  // reescriba la pregunta entera.
  function elegirOpcion(opcion) {
    setTexto(opcion);
    mandar(opcion, historial);
  }

  // El historial no cruza de institución: arrastrarlo sería meter datos de una
  // en el contexto de otra.
  function elegirInstitucion(id) {
    setInstitucionId(id);
    setHistorial([]);
    setContrato(null);
    setPreguntaContestada(null);
    setSeCayo(null);
  }

  const institucion = instituciones.find((i) => i.institucion_id === institucionId);

  return (
    <div className="page">
      <div className="frame">
        <BarraInstitucion
          instituciones={instituciones}
          institucionId={institucionId}
          alElegir={elegirInstitucion}
          fechaDeCorte={FECHA_DE_CORTE}
          bloqueado={pensando}
        />

        <div className="cuerpo">
          <form
            className="preguntar"
            onSubmit={(evento) => {
              evento.preventDefault();
              mandar(texto, []);
            }}
          >
            <input
              type="text"
              value={texto}
              disabled={pensando}
              placeholder="Preguntá en castellano, como se lo preguntarías a un analista"
              aria-label="Tu pregunta"
              onChange={(evento) => setTexto(evento.target.value)}
            />
            <button type="submit" className="plena" disabled={pensando || institucionId === null}>
              {pensando ? "Pensando…" : "Preguntar"}
            </button>
            {texto !== PREGUNTA_DE_REFERENCIA && (
              <p className="sugerencia">
                <button type="button" onClick={() => setTexto(PREGUNTA_DE_REFERENCIA)}>
                  {PREGUNTA_DE_REFERENCIA}
                </button>
              </p>
            )}
          </form>

          {pensando && <Pensando pregunta={preguntaContestada} />}

          {seCayo && (
            <div className="se-cayo">
              <p>No se pudo hablar con el sistema. La pregunta no se contestó.</p>
              <code>{seCayo}</code>
            </div>
          )}

          {!pensando && !seCayo && !contrato && (
            <p className="vacio">
              Escribí una pregunta sobre los datos de tu institución. La respuesta tarda entre
              quince y veinte segundos: se ejecutan consultas de verdad, y cada número que vas a
              ver salió de una de ellas.
            </p>
          )}

          {!pensando && contrato && (
            <Respuesta
              contrato={contrato}
              pregunta={preguntaContestada}
              institucion={institucion?.nombre ?? ""}
              fechaDeCorte={FECHA_DE_CORTE}
              alElegirOpcion={elegirOpcion}
              bloqueado={pensando}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// Existe porque `POST /ask` es sincrónico: sin un contador que se mueva, los
// veinte segundos de espera parecen una pantalla colgada. El progreso paso a
// paso de D-07 necesita que el backend emita eventos y no es de este hito.
function Pensando({ pregunta }) {
  const [segundos, setSegundos] = useState(0);
  const arranque = useRef(Date.now());

  useEffect(() => {
    arranque.current = Date.now();
    const reloj = setInterval(
      () => setSegundos(Math.floor((Date.now() - arranque.current) / 1000)),
      1000,
    );
    return () => clearInterval(reloj);
  }, [pregunta]);

  return (
    <div className="pensando">
      <span className="que">Pensando… {segundos} s</span>
      <p className="cuanto">
        Se están escribiendo y ejecutando consultas contra los datos de tu institución. Suele
        tardar entre quince y veinte segundos.
      </p>
    </div>
  );
}
