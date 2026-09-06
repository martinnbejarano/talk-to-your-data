# Contexto · Compliance conversacional

El vocabulario con el que un oficial de cumplimiento pregunta por los datos de su
institución, y con el que el sistema le contesta. **Este archivo es un glosario y
nada más**: el cómo vive en `core/semantics/`, el por qué en `DECISIONS.md`, y los
números que respaldan cada término en `NOTES/`.

Regla que lo hace útil: *si una palabra aparece en la interfaz y en el código con
distinto significado, una de las dos está mal.*

## Quiénes

**Institución**:
Una entidad financiera —banco, ALYC, fintech, EMI— dueña de sus datos. Es la unidad
de aislamiento: las filas de las demás no existen para una consulta.
_Evitar_: tenant (en la interfaz), cliente, organización, empresa.

**Oficial**:
La persona que pregunta. Trabaja en cumplimiento, no es técnica, y no lee SQL.
_Evitar_: usuario, analista (que acá es quien revisa alertas dentro de la
institución, otra persona).

**Analista**:
Quien revisa alertas y trabaja casos dentro de una institución. Aparece en los
datos, nunca frente a la pantalla.

## Cuándo

**Fecha de corte**:
El 1 de junio de 2026. Todo "hoy", "este año" y "último trimestre" se interpreta
contra esa fecha y nunca contra el reloj.
_Evitar_: hoy, ahora, snapshot.

**Este año** · **Último trimestre**:
Períodos de **calendario**: 1-ene-2026 a la fecha de corte, y ene–mar 2026. El año
fiscal de la institución es un atributo real del negocio que **no** los redefine.

**Vigente**:
Lo que está en vigor a la fecha de corte. Un mismo adjetivo, tres mecánicas
distintas según de qué se hable —la evaluación de riesgo lo trae marcado, el
screening es el más reciente y no lo trae marcado, la configuración es la última
que empezó a regir—, así que **"vigente" nunca se usa solo**: siempre acompañado
del sustantivo.
_Evitar_: actual, último, activo.

**Perilla**:
Un parámetro de configuración de la institución que cambia la respuesta de una
pregunta entera, no un detalle de formato. Hay cinco; tres no están documentadas.
_Evitar_: setting, flag, feature.

## Clientes y personas

**Cliente**:
Un legajo: una fila de alta en una institución. **No es una persona.** Todo conteo
de clientes cuenta legajos, y eso se dice cuando importa.
_Evitar_: cuenta, usuario, titular.

**Persona**:
El ser humano detrás de uno o más legajos. **No existe como dato**: se infiere por
documento normalizado y con una limitación declarada. Nunca es el sujeto de un
conteo sin decir que es una inferencia.
_Evitar_: entidad, individuo, persona física.

**Documento normalizado**:
Tipo y número de documento sin guiones, puntos ni espacios. Es la única base del
parecido entre legajos: no se comparan nombres ni correos.

**Alta**:
El evento fechado de incorporar un cliente. Es lo que se cuenta cuando la pregunta
tiene período.
_Evitar_: onboarding (en la interfaz), registro, apertura.

**Cliente aprobado**:
Un estado, no un evento: el legajo pasó el KYC. **Cuatro de cada diez aprobados no
tienen fecha de alta**, así que "aprobados" y "altas del período" son dos
poblaciones distintas y nombrarlas igual es el error a evitar.

**Dado de baja**:
Legajo con borrado lógico. Sigue en la tabla y no cuenta en ninguna respuesta
normal. Que quede afuera se declara **sólo donde efectivamente excluye algo**.
_Evitar_: eliminado, borrado, inactivo.

## Riesgo

**Riesgo alto**:
Un cliente vivo que cae en alguna de tres fuentes **disjuntas**: supera el umbral
de score de su institución, está marcado a mano, o —donde la institución así lo
configuró— es PEP. Ninguna se solapa con otra, así que los escalones suman.
_Evitar_: riesgoso, crítico, sospechoso (que apunta a otra cosa: la alerta).

**Umbral de score**:
El corte de riesgo alto de una institución, versionado en el tiempo. "El umbral"
siempre significa el vigente a la fecha de corte; tomar una versión vieja infla el
número casi diez veces.

**Evaluación de riesgo**:
El score de un cliente en un momento. Está historizada y hay exactamente una
vigente por cliente.
_Evitar_: assessment, rating, calificación.

**Marca manual de riesgo alto**:
La decisión de un humano de tratar a un cliente como riesgo alto, con independencia
del score. Aporta uno de cada cuatro clientes de riesgo alto: omitirla no redondea
el número, lo parte.
_Evitar_: override (que en esta base es otra cosa y no sirve).

**Override de riesgo**:
El registro de que alguien cambió el riesgo de un cliente **sin decir a qué valor**.
Existe como tabla, no puede definir riesgo, y la respuesta a "¿a qué se overrideó?"
es que no se puede responder.

## Listas y PEP

**Screening**:
Una corrida de un cliente contra listas. Está historizado —cuatro o cinco por
cliente— y, a diferencia de la evaluación de riesgo, **no trae marcado cuál vale
hoy**.

**Screening vigente**:
El más reciente de un cliente. Es una elección, no una columna.

**Hit confirmado**:
Un match que el analista dio por bueno. Distinto de **hit potencial** (sin
confirmar) y de **hit descartado** (el analista lo rechazó: no es un PEP real).
_Evitar_: match, positivo, coincidencia.

**PEP**:
Persona expuesta políticamente. **La palabra sola no se usa nunca en una definición**:
va siempre con `vigente` o con `histórico`, que difieren por tres. Cuál de las dos
contesta la pregunta directa *"¿tenemos PEPs?"* se decide con el eval.

**PEP vigente**:
Cliente cuyo screening más reciente es un hit confirmado. Es la definición que usa el
escalón de riesgo alto, y está congelada ahí aunque la pregunta directa siga abierta:
una perilla de configuración tiene que resolver a una población determinística.
**No lleva el flag `is_pep`**: la única lista presente en los datos es de PEPs, así que
un hit confirmado ya es un match de PEP, y el flag falta en 5.698 hits confirmados —
filtrarlo descarta PEPs reales por un campo ausente, no PEPs falsos.

**PEP histórico**:
Cliente que alguna vez dio hit confirmado. Siete de cada diez dejaron de figurar en su
corrida más reciente, y no porque un analista los descartara: la corrida siguiente
simplemente no los encontró.

**Lista**:
Un padrón contra el que se hace screening. El catálogo tiene quince; **en los datos
aparece una sola, de PEPs argentinos**. Cualquier pregunta por sanciones, OFAC o
listas internacionales no se puede responder, y decirlo es la respuesta correcta.
_Evitar_: watchlist, sanción (que nombra un tipo de lista, no la lista).

## Alertas y casos

**Alerta**:
Un disparo del monitoreo AML sobre un cliente. Tiene un ciclo de vida propio y
**ningún vínculo utilizable con los casos**: preguntar por uno desde el otro no se
puede responder.
_Evitar_: evento, señal.

**Sin revisar**:
Alerta que nunca tuvo primera revisión. Coincide exactamente con las abiertas: son
la misma población dicha de dos maneras.

**Fuera de SLA**:
Alerta que pasó el plazo de **primera revisión** de su institución. Son dos mitades
disjuntas y las dos cuentan: las que siguen sin revisar y ya vencieron, y las que se
revisaron tarde. La segunda sólo existe donde el plazo es corto.
_Evitar_: vencida, atrasada, incumplida (y "fuera de SLA" a secas cuando el plazo
del que se habla no es el de revisión).

**Caso**:
Una investigación. Es una entidad separada de las alertas, no su continuación.

**Caso cerrado**:
Un caso que llegó a un estado terminal. Son **dos**: cerrado y reportado a la UIF.
Dejar el segundo afuera pierde uno de cada cuatro casos cerrados, y justo los graves.

**Tiempo de resolución**:
Lo que tardó un caso cerrado desde que se abrió. **Un caso abierto no tiene tiempo
de resolución**: no es cero ni "hasta hoy", es N/A.

**Antigüedad**:
Lo que lleva abierto un caso que todavía no cerró. Es la contracara del tiempo de
resolución y acompaña a todo promedio: sin ella, un promedio de 2,71 días sobre casos
que nunca tardaron más de 5 esconde que hay cuatro de cada diez con dos meses encima.
_Evitar_: demora, tiempo abierto, edad.

**Caso reportado**:
Un caso que terminó en un reporte a la UIF. Es la salida más grave, uno a uno con el
reporte, y es un concepto por derecho propio: se pregunta y se contesta directo, sin
pasar por la palabra "hallazgo".
_Evitar_: SAR, ROS, denuncia, caso escalado (que es un estado de alerta, no de caso).

**Hallazgo**:
Una alerta que resultó cierta: cerrada como verdadero positivo. Que las escaladas
cuenten o no lo decide la configuración de la institución, y eso cambia el número un
50 %. **Es una palabra con supuesto**: nombra el ciclo de vida de las alertas y no
incluye los casos reportados a la UIF, que son otra población — quince veces más chica
y **imposible de cruzar** con ésta, porque el vínculo alerta↔caso no existe en la base.
Toda respuesta que use la palabra declara las tres cosas.
_Evitar_: verdadero positivo (en la interfaz), caso, incidente.

## Transacciones

**Liquidada**:
Movimiento efectivo. Lo pendiente y lo revertido no lo son, y juntos son el 40 % del
volumen.
_Evitar_: settled, efectiva, confirmada.

**Monto transado**:
Suma de montos liquidados, **siempre desglosada por moneda y por sentido**. No hay
tipos de cambio: un total único sería una cotización inventada. Y como los importes
son todos positivos, sumar entradas con salidas no netea nada, mezcla.
_Evitar_: volumen, total operado, monto total.

**Sentido**:
Si el dinero entra o sale. Vive en su propia columna: no está en el signo del importe.
_Evitar_: dirección, tipo de movimiento.

## Cómo se contesta

**Definición**:
El criterio de negocio que el sistema aplicó para producir un número, mostrado junto
al número. En el código estas definiciones son *skills*; frente al oficial son
**definiciones**, y la traducción es deliberada.
_Evitar_: regla, métrica, criterio (en la interfaz).

**Derivación**:
La cadena de escalones que lleva del universo al resultado. Es la explicación
principal de una respuesta, no un anexo.
_Evitar_: cálculo, breakdown, desglose (que es otra cosa: partir un total por moneda
o por sentido).

**Escalón**:
Cada línea de la derivación, con su número. Todo escalón sale de una consulta
ejecutada; ninguno se calcula fuera de la base.
_Evitar_: paso (que es lo que hace el agente mientras trabaja), fila.

**Exclusión**:
Lo que quedó afuera del número, dicho en castellano. Sale de los datos: donde no
excluye nada, no se declara.

**Supuesto**:
La lectura que el sistema eligió cuando la pregunta admitía más de una, dicha con el
número de lo que costó.

> El vocabulario del sistema —los cuatro estados, "auditoría" contra "detalle
> técnico", "trace"— se cierra en H3.0 y se agrega acá.
