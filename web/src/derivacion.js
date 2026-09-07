// Una derivación no siempre es una resta: en `riesgo_alto` los primeros
// escalones descartan y los últimos suman tres fuentes, así que un `−X` entre
// cada par de filas produciría restas falsas.
//
// El contrato no trae dónde está ese corte. Se deduce de los `n`, que salieron
// de una consulta, y nunca del `texto`, que lo escribe el modelo: la fase de
// suma es la corrida final cuyos `n` suman **exactamente** el `n` del resultado.
// Si la identidad no cierra, no hay rótulo y queda una sola columna.

/** Con un solo sumando, "el resultado es igual al escalón anterior" es un empate
 * —el último filtro no descartó a nadie— y no una suma. */
const SUMANDOS_MINIMOS = 2;

/** **`valorFinal` es lo que autoriza a leer esto como una cascada.** Si el
 * último escalón no vale lo mismo que el número de la respuesta, los escalones
 * no son filtros encadenados sino hermanos —un conteo por categoría—, y las dos
 * secuencias son indistinguibles por sus números: las dos vienen en orden
 * decreciente. Restar entre hermanos daría una cifra verdadera como cuenta y
 * falsa como afirmación, así que ahí no se resta y no hay fase.
 */
export function leerDerivacion(derivacion, valorFinal = null) {
  const escalones = Array.isArray(derivacion) ? derivacion : [];
  if (escalones.length === 0) return { bloques: [], enTramos: false };

  const ultimo = escalones.length - 1;
  const tramos = partirPorUnidad(escalones);
  const esCascada =
    typeof valorFinal === "number" &&
    typeof escalones[ultimo].n === "number" &&
    Math.abs(escalones[ultimo].n - valorFinal) < 1e-9;

  if (!esCascada) {
    return {
      bloques: tramos.flatMap((tramo, i) => [
        ...(i > 0
          ? [{ tipo: "cambio-de-unidad", de: tramos[i - 1].unidad, a: tramo.unidad }]
          : []),
        armarEscalones(escalones, tramo, tramo.desde, tramo.hasta, null, null),
      ]),
      enTramos: tramos.length > 1,
    };
  }

  const suma = buscarLaFaseDeSuma(escalones, tramos[tramos.length - 1]);

  const bloques = [];
  tramos.forEach((tramo, i) => {
    if (i > 0) {
      bloques.push({
        tipo: "cambio-de-unidad",
        de: tramos[i - 1].unidad,
        a: tramo.unidad,
      });
    }
    // El rótulo de la fase no va entre tramos sino adentro de uno: es donde la
    // cascada cambia de operación sin cambiar de unidad.
    if (suma && suma.desde > tramo.desde && suma.desde <= tramo.hasta) {
      bloques.push(armarEscalones(escalones, tramo, tramo.desde, suma.desde - 1, ultimo, suma));
      bloques.push({ tipo: "fase", sumandos: suma.sumandos, total: suma.total });
      bloques.push(armarEscalones(escalones, tramo, suma.desde, tramo.hasta, ultimo, suma));
    } else {
      bloques.push(armarEscalones(escalones, tramo, tramo.desde, tramo.hasta, ultimo, suma));
    }
  });

  return { bloques, enTramos: tramos.length > 1 };
}

/** Corridas de escalones que cuentan la misma cosa. Un cambio de `unidad` es la
 * única señal que el contrato sí trae, y **entre tramos no se resta nunca**: la
 * resta entre unidades distintas da un número que no significa nada. */
function partirPorUnidad(escalones) {
  const tramos = [];
  escalones.forEach((escalon, i) => {
    const unidad = escalon.unidad ?? null;
    const abierto = tramos[tramos.length - 1];
    if (abierto && abierto.unidad === unidad) {
      abierto.hasta = i;
    } else {
      tramos.push({ unidad, desde: i, hasta: i });
    }
  });
  return tramos;
}

/** Se prueban las corridas finales de menor a mayor y gana la primera que
 * cierra: la afirmación más chica que explica el resultado. El tramo además
 * tiene que terminar en el resultado y tienen que quedar escalones antes de la
 * fase; sin eso, una suma que cierre es una coincidencia. */
function buscarLaFaseDeSuma(escalones, tramo) {
  const ultimo = escalones.length - 1;
  if (tramo.hasta !== ultimo) return null;

  const total = escalones[ultimo].n;
  if (typeof total !== "number") return null;

  for (let cantidad = SUMANDOS_MINIMOS; cantidad <= ultimo - tramo.desde - 1; cantidad += 1) {
    const desde = ultimo - cantidad;
    const sumandos = escalones.slice(desde, ultimo);
    if (sumandos.some((escalon) => typeof escalon.n !== "number")) continue;
    const suma = sumandos.reduce((acumulado, escalon) => acumulado + escalon.n, 0);
    // Exacta salvo el ruido del punto flotante: los escalones son conteos, pero
    // `resolucion_de_casos` responde en días con decimales.
    if (Math.abs(suma - total) < 1e-9) {
      return { desde, sumandos: sumandos.map((escalon) => escalon.n), total };
    }
  }
  return null;
}

function armarEscalones(escalones, tramo, desde, hasta, ultimo, suma) {
  // El tope se mide sobre el tramo entero y no sobre este bloque: la fase de
  // suma parte la cascada en dos bloques, y una escala por bloque haría que el
  // resultado y el universo dibujaran la misma barra.
  const tope = topeDelTramo(escalones, tramo);
  const filas = [];
  for (let i = desde; i <= hasta; i += 1) {
    const escalon = escalones[i];
    const enLaSuma = suma !== null && i >= suma.desde && i < ultimo;
    const esResultado = i === ultimo;
    filas.push({
      clave: `${i}-${escalon.escalon}`,
      texto: escalon.texto,
      n: escalon.n,
      esResultado,
      // Los sumandos no van sangrados: no cuelgan del anterior, son hermanos.
      sangria: !esResultado && !enLaSuma && i > tramo.desde,
      // Un sumando en cero se apaga y no se omite: que la configuración de la
      // institución lo haya dejado sin efecto es parte de la explicación.
      apagado: enLaSuma && escalon.n === 0,
      delta: calcularDelta(escalones, i, tramo, ultimo, enLaSuma, suma),
    });
  }
  return { tipo: "escalones", unidad: tramo.unidad, tope, filas };
}

/** Cero cuando ningún escalón del tramo trae número: ahí no hay proporción que
 * dibujar y la escala no se muestra. */
function topeDelTramo(escalones, tramo) {
  let tope = 0;
  for (let i = tramo.desde; i <= tramo.hasta; i += 1) {
    const n = escalones[i].n;
    if (typeof n === "number") tope = Math.max(tope, Math.abs(n));
  }
  return tope;
}

/** Cuántos quedaron afuera, o `null` si la resta no aplica: sólo contra el
 * escalón anterior del **mismo tramo**, sólo mientras la cadena viene bajando, y
 * nunca sobre el resultado ni sobre un sumando. En cualquier otro caso daría un
 * número verdadero como cuenta y falso como afirmación. */
function calcularDelta(escalones, i, tramo, ultimo, enLaSuma, suma) {
  // Sin resultado al final no es una cascada: la pregunta no tiene respuesta.
  if (ultimo === null) return null;
  if (i === tramo.desde || i === ultimo || enLaSuma) return null;
  // Restar contra un sumando es cruzar la frontera que la fase acaba de dibujar.
  if (suma !== null && i - 1 >= suma.desde) return null;

  const anterior = escalones[i - 1].n;
  const actual = escalones[i].n;
  if (typeof anterior !== "number" || typeof actual !== "number") return null;
  if (actual > anterior) return null;
  return anterior - actual;
}
