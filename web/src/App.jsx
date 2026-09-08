import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { preguntar, traerInstituciones } from "./api.js";
import { FECHA_DE_CORTE } from "./config.js";
import { BarraInstitucion } from "./componentes/BarraInstitucion.jsx";
import { Respuesta } from "./componentes/Respuesta.jsx";
import { Alerta, Flecha } from "./componentes/Iconos.jsx";

// Un atajo, no una lista de preguntas permitidas: es la única con valor esperado
// conocido —7.859 en Banco Andino, 321 en Fintech Cuyo—.
const PREGUNTA_DE_REFERENCIA = "¿Cuántos clientes de riesgo alto tenemos?";

// La de referencia va primera: es la canónica del README y del eval, y su número
// —7.859 en Banco Andino— está verificado a mano. Las otras dos están elegidas
// porque **contestan con una serie**, que es lo único que se dibuja (D-19): sin
// una de ellas a mano, un oficial puede usar la pantalla entera sin enterarse de
// que hay gráficos.
const PARA_EMPEZAR = [
  PREGUNTA_DE_REFERENCIA,
  "¿Cuántos casos reportamos a la UIF por mes este año?",
  "¿Cuántos clientes onboardeamos por mes este año?",
];

export function App() {
  const [instituciones, setInstituciones] = useState([]);
  const [institucionId, setInstitucionId] = useState(null);
  const [texto, setTexto] = useState("");

  // `[{pregunta, contrato}]`. Los arrastra el front porque el servidor no
  // guarda sesiones.
  const [turnos, setTurnos] = useState([]);

  // El turno que está en vuelo, y su falla si se cayó. Vive separado de
  // `turnos` porque todavía no tiene contrato.
  const [enCurso, setEnCurso] = useState(null);
  const pensando = enCurso !== null && enCurso.error === null;

  const [arranque, setArranque] = useState(null);
  const fondo = useRef(null);

  useEffect(() => {
    traerInstituciones()
      .then((traidas) => {
        setInstituciones(traidas);
        if (traidas.length > 0) setInstitucionId(traidas[0].institucion_id);
      })
      .catch((error) => setArranque(String(error.message ?? error)));
  }, []);

  // El turno nuevo aparece abajo del todo: sin esto queda tapado por la caja de
  // preguntar, que es pegajosa.
  useLayoutEffect(() => {
    if (turnos.length === 0 && enCurso === null) return;
    fondo.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turnos.length, enCurso]);

  /** **Una pregunta escrita a mano siempre va con `turnos` vacío**, y sólo el
   * clic en una opción arrastra los turnos previos. Un número que dependa de una
   * pregunta que ya no está en pantalla no se puede defender ante un auditor: el
   * historial existe para cerrar una repregunta —ahí el turno previo sí está a la
   * vista— y no para convertir esto en un chat con memoria.
   */
  async function mandar(pregunta, historial) {
    if (!pregunta.trim() || institucionId === null || pensando) return;
    setEnCurso({ pregunta, error: null });
    setTexto("");
    try {
      const vuelta = await preguntar({ institucionId, pregunta, historial });
      setTurnos((previos) => [...previos, { pregunta, contrato: vuelta }]);
      setEnCurso(null);
    } catch (error) {
      setEnCurso({ pregunta, error: String(error.message ?? error) });
    }
  }

  // Vuelve al backend como pregunta nueva con el turno de la repregunta adjunto:
  // así se cierra la aclaración sin sesión en el servidor y sin que el oficial
  // reescriba la pregunta entera.
  function elegirOpcion(opcion) {
    mandar(
      opcion,
      turnos.map((turno) => ({ pregunta: turno.pregunta, respuesta: turno.contrato.respuesta })),
    );
  }

  // El historial no cruza de institución: arrastrarlo sería meter datos de una
  // en el contexto de otra.
  function elegirInstitucion(id) {
    setInstitucionId(id);
    setTurnos([]);
    setEnCurso(null);
  }

  const vacio = turnos.length === 0 && enCurso === null;

  // Una sola región viva para toda la pantalla. Ponerla en cada turno hacía que
  // abrir "Mostrar más" volviera a leer la respuesta entera, y que la llegada
  // del turno nuevo no se anunciara nunca: una región insertada junto con su
  // contenido no dispara.
  const anuncio = enCurso
    ? enCurso.error === null
      ? "Pensando. La respuesta tarda entre trece y veinte segundos."
      : "No se pudo hablar con el sistema. La pregunta no se contestó."
    : (turnos[turnos.length - 1]?.contrato.respuesta ?? "");

  return (
    <div className="app">
      <BarraInstitucion
        instituciones={instituciones}
        institucionId={institucionId}
        alElegir={elegirInstitucion}
        fechaDeCorte={FECHA_DE_CORTE}
        bloqueado={pensando}
      />

      <p className="sr-only" role="status" aria-live="polite">
        {anuncio}
      </p>

      <main className={vacio ? "hilo centrado" : "hilo"}>
        <div className="columna">
          {vacio && (
            <Vacio
              arranque={arranque}
              alSugerir={(pregunta) => mandar(pregunta, [])}
              bloqueado={institucionId === null}
            />
          )}

          {turnos.map((turno, i) => (
            <article className="turno" key={i}>
              <Dicho pregunta={turno.pregunta} />
              <Respuesta
                contrato={turno.contrato}
                alElegirOpcion={elegirOpcion}
                bloqueado={pensando}
              />
            </article>
          ))}

          {enCurso && (
            <article className="turno">
              <Dicho pregunta={enCurso.pregunta} />
              {enCurso.error === null ? <Pensando /> : <Falla error={enCurso.error} />}
            </article>
          )}

          <div ref={fondo} />
        </div>
      </main>

      <Preguntar
        texto={texto}
        alEscribir={setTexto}
        alMandar={() => mandar(texto, [])}
        bloqueado={pensando || institucionId === null}
        pensando={pensando}
      />
    </div>
  );
}

function Dicho({ pregunta }) {
  return (
    <div className="dicho">
      <p>{pregunta}</p>
    </div>
  );
}

function Vacio({ arranque, alSugerir, bloqueado }) {
  if (arranque) {
    return (
      <div className="vacio">
        <h1>No se pudo hablar con el sistema</h1>
        <p>
          No se pudieron traer las instituciones, así que todavía no hay nada que preguntar.
          Revisá que el backend esté levantado.
        </p>
        <div className="marca falla">
          <span className="icono">
            <Alerta />
          </span>
          <p>
            <code>{arranque}</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="vacio">
      <h1>Preguntá sobre los datos de tu institución</h1>
      <p>
        En castellano, como se lo preguntarías a un analista. La respuesta tarda entre trece y
        veinte segundos: se ejecutan consultas de verdad, y cada número que vas a ver salió de una
        de ellas.
      </p>
      <div className="sugerencia">
        <span>Para empezar</span>
        <div className="pastillas">
          {PARA_EMPEZAR.map((pregunta) => (
            <button
              key={pregunta}
              type="button"
              className="opcion"
              disabled={bloqueado}
              onClick={() => alSugerir(pregunta)}
            >
              <span className="titulo">{pregunta}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// Existe porque `POST /ask` es sincrónico: sin un contador que se mueva, los
// veinte segundos de espera parecen una pantalla colgada. El progreso paso a
// paso de D-07 necesita que el backend emita eventos y no es de este hito.
function Pensando() {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    const desde = Date.now();
    const reloj = setInterval(() => setSegundos(Math.floor((Date.now() - desde) / 1000)), 1000);
    return () => clearInterval(reloj);
  }, []);

  return (
    <div>
      <p className="pensando">
        <span className="punto" />
        Pensando
        {/* Fuera del anuncio: leído en vivo, el contador habla una vez por
            segundo durante veinte segundos. */}
        <span className="seg" aria-hidden="true">
          {" "}
          · {segundos} s
        </span>
      </p>
      <p className="pensando-glosa">
        Se están escribiendo y ejecutando consultas contra los datos de tu institución.
      </p>
    </div>
  );
}

function Falla({ error }) {
  return (
    <div className="marca falla" role="alert">
      <span className="icono">
        <Alerta />
      </span>
      <div>
        <p>
          <b>No se pudo hablar con el sistema.</b> La pregunta no se contestó, así que no hay
          ningún número que mirar. Probá de nuevo.
        </p>
        <code>{error}</code>
      </div>
    </div>
  );
}

/** Enter manda y Shift+Enter baja de línea, que es lo que el oficial ya espera
 * de cualquier caja de texto de este tipo. El alto lo fija el contenido: una
 * pregunta larga se ve entera antes de mandarla. */
function Preguntar({ texto, alEscribir, alMandar, bloqueado, pensando }) {
  const caja = useRef(null);

  useLayoutEffect(() => {
    const nodo = caja.current;
    if (!nodo) return;
    nodo.style.height = "auto";
    nodo.style.height = `${nodo.scrollHeight}px`;
  }, [texto]);

  return (
    <form
      className="preguntar"
      onSubmit={(evento) => {
        evento.preventDefault();
        alMandar();
      }}
    >
      <div className="columna">
        <div className="caja">
          <label className="sr-only" htmlFor="pregunta">
            Tu pregunta
          </label>
          <textarea
            id="pregunta"
            ref={caja}
            rows={1}
            value={texto}
            disabled={pensando}
            placeholder={pensando ? "Contestando la anterior…" : "Preguntá en castellano…"}
            onChange={(evento) => alEscribir(evento.target.value)}
            onKeyDown={(evento) => {
              if (evento.key === "Enter" && !evento.shiftKey) {
                evento.preventDefault();
                alMandar();
              }
            }}
          />
          <button
            type="submit"
            className="enviar"
            disabled={bloqueado || !texto.trim()}
            aria-label="Preguntar"
          >
            <Flecha />
          </button>
        </div>
        <p className="pie">
          Cada respuesta se calcula contra los datos de la institución elegida, a la fecha de
          corte.
        </p>
      </div>
    </form>
  );
}
