# H6 · Producto y entrega

**Objetivo.** Que alguien que nunca vio el repo lo levante en cinco minutos, entienda
las decisiones, y confíe en el sistema al usarlo.

## Pulido de la interfaz

Sobre la estructura ya armada en H3:

- **Estados vacíos y de error** que un no-técnico entienda. "No pude encontrar una forma
  eficiente de consultar esto" en vez de un stack trace.
- **Pasos del agente en vivo** mientras piensa ("consultando la configuración de
  riesgo…"). La espera se vuelve evidencia de que fue a buscar el dato.
- **Repregunta con opciones clickeables**, no un campo de texto libre. Si el sistema
  detectó dos lecturas, que muestre las dos.
- **Supuestos arriba, no escondidos**. Si respondió con un supuesto, se lee antes que el
  número.

## README

Cinco secciones, en este orden:

1. **Cómo correrlo** — de cero: docker, restore, bootstrap, backend, front, variables de
   entorno. Probado en limpio, no de memoria.
2. **Qué interfaz elegí y por qué** — chat web con panel en dos lecturas: derivación,
   criterios, exclusiones y filas para el oficial de compliance; SQL y plan plegados para
   IT. Explicar por qué mostrarle SQL a un no técnico no lo habilita a auditar, y por qué
   sí lo habilitan la derivación y la reconciliación contra filas reales (D-07).
3. **Cómo modelé las definiciones de negocio** — las skills, con la tabla de qué
   significa cada concepto y qué alternativa descarté.
4. **Qué supuestos hice** — `AS_OF`, períodos calendario, monedas sin sumar, dedup por
   documento, `ESCALATED`, `APPROVED` sin fecha.
5. **Qué limitaciones tiene** — dedup incompleto (D-09), sin FX, cobertura acotada a lo
   medido en el eval, y **el resultado real del eval con sus números**, incluidas las
   preguntas que falla.

Poner las fallas en el README es deliberado: un sistema que declara dónde falla es más
confiable que uno que promete todo. Es la misma postura que toma el sistema cuando no
puede responder una pregunta.

## Documentos que acompañan

| Archivo | Contenido |
|---|---|
| `DECISIONS.md` | El cuadernito completo, ya escrito a lo largo de todos los hitos |
| `NOTES/` | El log de proceso: exploración, semántica, iteración |
| `AGENT_LOG.md` | Conversaciones con el coding agent durante el desarrollo |
| `PRODUCT.md` | Propuestas no implementadas y por qué valdrían la pena |

### `PRODUCT.md` — ideas a proponer

- **Aprobación de definiciones por el oficial de compliance**: que el propio usuario
  confirme o corrija la definición de "riesgo alto" de su institución, y que quede
  versionada. Es el *collaborative context* de Ramp: el usuario corrige el contexto en
  vez de pelearse con la respuesta.
- **Preguntas guardadas y alertas programadas**: "avisame si las alertas fuera de SLA
  pasan de 50".
- **Comparación entre períodos** con explicación de la variación.
- **Confianza progresiva** (Ramp: *sugerencias → actuar sobre subconjuntos → autonomía*):
  hoy el sistema sólo lee; el camino natural es que proponga acciones sobre casos, y
  recién después que las ejecute.
- **Expediente exportable**: PDF con el número, la derivación, la definición y el SQL
  embebidos, firmado y con fecha, para adjuntar a un legajo. El CSV de filas ya está en
  el producto; esto es la versión presentable ante un regulador.
- **Parámetros editables**: mover el umbral y ver el número recalcular — confianza por
  manipulación en vez de por lectura.
- **Cifras de control**: el porcentaje sobre el universo al lado del resultado, que es lo
  que detecta el disparate de orden de magnitud.
- **Doble verificación**: calcular el mismo número por dos caminos distintos y mostrar
  que coinciden. Es lo único honesto que se parece a un nivel de confianza sin ser un
  número inventado por el modelo.
- **Visualización de resultados**: el contrato ya reserva el campo. Línea para
  series, barras para rankings, número grande para escalares, nunca torta — siempre sobre
  las mismas filas que muestra el panel.

## Checklist final

- [ ] Clonar el repo en limpio y seguir el README al pie de la letra, sin usar nada que
      esté sólo en mi máquina.
- [ ] Verificar que el sistema arranca con la key de OpenAI en `.env` y no hay secretos
      commiteados.
- [ ] Última corrida del eval, con el reporte incluido en el repo.
- [ ] Historial de git legible: un commit por hito, con mensajes que cuenten la historia.
- [ ] Las 8 preguntas de referencia probadas a mano desde la UI, no sólo desde el runner.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El README funciona sólo en mi máquina | El paso 1 del checklist es clonar en limpio |
| Quedarme sin tiempo y entregar sin README | El README se empieza en H3, no en H6 |
| Pulir la UI y descuidar el eval | El eval tiene prioridad: mide si el sistema sirve; un botón lindo no |
