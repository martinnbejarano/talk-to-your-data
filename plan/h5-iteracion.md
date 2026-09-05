# H5 · Iteración medida

**Objetivo.** Subir el acierto en las tres categorías con cambios **justificados por el
delta en el reporte**, no por la impresión de que anda mejor.

## El loop

1. Correr el set completo (3 corridas por pregunta).
2. Clasificar cada falla en la taxonomía de abajo.
3. Atacar la categoría de falla más frecuente, **un cambio a la vez**.
4. Re-medir. Si el delta es negativo o nulo, revertir.
5. Anotar en `DECISIONS.md` sólo lo que cambió el número.

## Taxonomía de fallas


| Tipo                     | Ejemplo                                           | Dónde se arregla                                 |
| ------------------------ | ------------------------------------------------- | ------------------------------------------------ |
| Definición equivocada    | Contó los `CLOSED_FALSE_POSITIVE` como hallazgos  | Skill (H2)                                       |
| Skill no consultada      | Tenía la definición disponible y no la pidió      | Prompt / descripción de la tool                  |
| SQL ineficiente          | Rechazado por el gate tres veces seguidas         | Contexto de índices                              |
| Ambigüedad no detectada  | Respondió con un número donde debía repreguntar   | Prompt + ejemplos de ambigüedad                  |
| Falsa ambigüedad         | Repreguntó algo que era claro — **igual de malo** | Prompt: fricción innecesaria mata la confianza   |
| Incontestable respondida | Inventó una respuesta para data que no existe     | Prompt + explicitar qué **no** hay en el esquema |
| Número no trazable       | Citó una cifra que no está en ningún resultado    | Validación post-hoc (H3)                         |


Vale la pena remarcar la **falsa ambigüedad**: un sistema que repregunta todo el tiempo
es tan inútil como uno que inventa, y no aparece en ningún criterio obvio. Lo medimos
igual.

## Experimento de ablación de skills

Cuando el set esté estable, replicar el experimento de Ramp: correr el eval sin skills,
y después con una skill a la vez. Puede pasar perfectamente que alguna esté **empeorando**
el resultado — a Ramp le pasó con la mayoría. Las que no aportan, se sacan.

Este experimento es barato de correr y es material de primera para la charla de 30
minutos: muestra que el diseño se validó, no se supuso.

## Entregables

- `evals/reports/` con la serie de corridas.
- `NOTES/03-iteracion.md`: qué falló, qué probé, qué funcionó y qué no.
- Entradas nuevas en `DECISIONS.md` con el delta que justificó cada cambio.
- Tabla de ablación de skills.

## Definition of done

- [ ] Fugas cross-tenant = 0 en todas las corridas.
- [ ] Las 8 preguntas de referencia responden correctamente y de forma consistente

  (Pass^3).
- [ ] Ambiguas e incontestables por encima del umbral que fijemos como aceptable.
- [ ] Ablación corrida y skills negativas eliminadas.
- [ ] Cada cambio del hito tiene su delta documentado.

## Riesgos


| Riesgo                                           | Mitigación                                                                    |
| ------------------------------------------------ | ----------------------------------------------------------------------------- |
| Sobreajustar al set propio                       | Reservar 5-8 preguntas que no se miran hasta el final, como set de validación |
| Cambiar tres cosas juntas y no saber cuál sirvió | Un cambio por corrida. Es más lento y es la única forma de aprender algo      |
| Iterar sin fin                                   | Umbral de aceptación fijado antes de empezar; se corta al llegar              |


