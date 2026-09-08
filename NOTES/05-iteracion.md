# H5 · Iteración medida

Log de proceso del hito. Lo que se decidió está en `plan/h5-iteracion.md` y en
`DECISIONS.md` (D-16 a D-18); acá está lo que pasó, incluido lo que salió distinto de lo
planeado — que fue casi todo.

## 1. Buscar un modelo más barato costó más que no buscarlo

El motivo de arrancar por acá: H4 costó US$14 y la proyección era que H5 costara bastante
más, corriendo el set completo varias veces por cada cambio del loop.

Se probaron, en orden: `gpt-5.6-luna`, `gpt-5-mini`, `gpt-5.6-terra`, `gpt-5.4-mini`,
`o4-mini`. El resultado, resumido en D-16: los dos modelos de la familia `gpt-5.6` no
corren con tool calling y razonamiento en `/v1/chat/completions` — hubo que migrar
`agent/loop.py` y `agent/tools.py` a `/v1/responses` sólo para poder medirlos. Una vez
migrado, `gpt-5.4-mini` colapsó en ambiguas (79 % → 12 % Pass@1) y `gpt-5.6-terra` costó
lo mismo por llamada que `gpt-5.5` pese al precio de lista más bajo. `gpt-5-mini` nunca
llegó a correr (verificación de organización pendiente) y `o4-mini` chocó con un bug de
schema en `sample_values` que quedó sin arreglar porque no se llegó a necesitar.

**La exploración sola costó ~US$8**, incluyendo dos corridas que crashearon a mitad de
camino (un rate limit con `gpt-5.4-mini`, y más tarde el bug de `sample_values` con
`gpt-5.5`) y cuyas llamadas ya pagas se perdieron sin generar reporte. Se volvió a
`gpt-5.5` — el modelo con el que arrancó H4 — y la migración de API quedó como el único
resultado permanente de todo este tramo.

## 2. El loop se corrió sobre un subconjunto, no las 33 preguntas

Presupuesto acotado a US$10-15 en total para el resto del hito. Eso obligó a elegir: en
vez de correr el set completo en cada iteración (como pedía el plan original), se armó un
subconjunto de 13 preguntas elegido a mano para cubrir exactamente las clases que el loop
iba a atacar, y se lo corrió con 1 sola corrida por paso en vez de 3.

Es una desviación real del plan, y tiene un costo real: los deltas de este hito están
medidos con Pass@1, no Pass^3. La sección 4 muestra por qué eso importa.

## 3. Cinco arreglos, cinco causas distintas

El detalle completo con delta está en D-17. En resumen:

1. **`alerta_fuera_de_sla` y `misma_persona`** declaraban un `periodo_por_defecto` que su
   propio `golden_sql` nunca usa — exactamente el finding #1 de H4, que quedó pendiente
   para acá. Se sacó el campo de las dos skills.
2. **Institución ajena**: el prompt decía "contestá con el número propio, declaralo como
   supuesto" — el peor bug posible del sistema, expresado como instrucción. Se cambió a
   `NO_SE_PUEDE_RESPONDER` y se actualizó el test que verificaba la conducta vieja.
3. **Cero disfrazado**: se agregó una regla nueva al prompt pidiendo verificar, antes de
   publicar un 0, si el catálogo tiene más opciones que las que aparecieron, o si el
   período pedido es anterior al primer registro de la tabla.
4. **`misma_persona` contestaba el escalón equivocado**, y esto fue el hallazgo más
   interesante del hito: `get_definition` arma el texto que lee el modelo con todos los
   escalones de la cascada, pero **nunca menciona el campo `resultado`** — el que dice
   cuál de todos es la respuesta. En las otras ocho skills el resultado coincide con el
   último escalón de la lista, así que el modelo acierta por convención implícita.
   `misma_persona` es la única que rompe el patrón: `personas_repetidas` (el resultado
   real) va antes de `legajos_repetidos` (el último, pero auxiliar). El modelo seguía la
   convención y no el campo, porque el campo no se le mostraba. Se agregó una línea
   explícita en `get_definition` marcando qué escalón va en `valor`.
5. **`monto_transado` arrancaba la cascada del universo equivocado** (`clients`, 180.000,
   en vez de `transactions`, 1.080.005) — el mismo defecto que H4 ya había visto en la
   línea de base original. Una regla general en el prompt ("el primer escalón dice de qué
   tabla sale `total`") no alcanzó; hizo falta explicitarlo en la skill misma, como trampa
   y en el texto del escalón. Ahí sí funcionó.

El quinto arreglo es la lección repetida del hito: **cuando una regla general no alcanza,
el lugar correcto suele ser la skill, no el prompt.** Ya había pasado con el primer
arreglo (misma causa que H4) y volvió a pasar acá.

## 4. La corrida de cierre mostró lo que las corridas aisladas no podían ver

Con los cinco arreglos puestos, el set completo (33×1) dio una mejora agregada real:

| Categoría | D-14 (línea de base) | Cierre H5 |
|---|---|---|
| Contestable | 53 % | 80 % |
| Ambigua | 79 % | 88 % |
| Incontestable | 53 % | 90 % |

Pero tres de los cinco arreglos —`c-004`, `c-011`, `i-003`— **volvieron a fallar** en esa
misma corrida, después de haber pasado 1/1 en su remedición aislada. No es que el arreglo
no sirva: es que una sola corrida prueba que el arreglo es *posible*, no que sea *estable*.
Es la misma advertencia de D-14 sobre Pass@1 y Pass^3, y este hito la volvió a demostrar en
carne propia por no tener presupuesto para respetarla del todo.

También apareció una falsa ambigüedad nueva en `c-015`, que no estaba en ningún hallazgo
anterior. Sin confirmar la causa — candidato sospechoso es la regla del cero disfrazado,
que puede haber vuelto al modelo más cauteloso en general y no sólo en los casos que
apuntaba.

## 5. Un bug de costo real, encontrado por accidente

Durante la primera corrida de cierre (33×3), el sistema crasheó con un error de la API:
un string de entrada de **64 MB**. La causa: `sample_values` no tiene tope en su parámetro
`limite` ni en el texto que arma para el modelo — si el modelo pide una columna de alta
cardinalidad con un límite alto, la función junta todos los valores en una sola línea sin
cortar. Es un bug previo a esta sesión, agravado por que las 18 llamadas que ya se habían
pagado antes del crash se perdieron sin generar reporte (nada se persiste hasta el final
de la corrida). Se corrigió con el mismo tope que ya usa `run_sql` desde el vertical slice
(`FILAS_QUE_VE_EL_MODELO = 50`).

## 6. Ablación parcial

Sólo se ablacionaron los 4 conceptos que el subconjunto reducido ejercitaba:
`alerta_fuera_de_sla`, `riesgo_alto` y `cliente_onboardeado` sostienen solos. El dato más
interesante: **`misma_persona` no sostenía ni estando sola (0/2)**, aun antes de
encontrarse el bug del campo `resultado` — la señal ya estaba, faltaba leerla. Quedan sin
ablacionar `hallazgo_real`, `monto_transado`, `pep_confirmado`, `caso_reportado` y
`resolucion_de_casos`.

## 7. Lo que queda para que H5 esté realmente cerrado

- Pass^3 de los cinco arreglos (hoy sólo hay Pass^1).
- Ablación de las cinco skills que faltan.
- Correr `evals/questions_holdout.yaml` — 6 preguntas escritas con el mismo rigor del set
  oficial (reutilizando valores ya verificados por dos caminos en
  `valores_esperados.yaml`, nunca escritos a mano) y nunca ejecutadas.
- Confirmar o descartar la falsa ambigüedad de `c-015`.
- El Definition of Done del plan (ambiguas/incontestables ≥ 90 % Pass^3, las 8 preguntas
  de referencia en Pass^3) no está verificado.

## Costo total de la sesión: ~US$13,75

De los cuales ~US$8 se fueron en buscar un modelo más barato que terminó no usándose, y
~US$2,45 se perdieron en corridas que crashearon a mitad de camino. El costo de arreglar
los cinco bugs, una vez identificados, fue bajo (remedidas de 1-3 preguntas, no el set
completo). La lección de costo del hito: **el descubrimiento es caro, la verificación es
barata** — vale la pena invertir tiempo en diagnosticar bien antes de remedir, y remedir
lo mínimo necesario, no el set entero, en cada paso del loop.
