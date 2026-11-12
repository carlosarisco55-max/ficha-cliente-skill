---
name: ficha-cliente
description: "Junta en UNA fila por cliente lo que dicen todos los modelos (RFM 333 o generico, ciclo de vida y momento del ciclo de repeticion, patron de cesta 1-2-4, propension de su segmento, si tiene la version antigua de un producto, y si esta en el grupo de control) y decide QUE ofrecerle, CUANDO, con que PALANCA de comportamiento (habito, dotacion/aversion a la perdida, progreso dotado, reconocimiento, reciprocidad, reactancia) y con que PRIORIDAD (A-D). Devuelve la ficha y las audiencias listas para activar. Usa este skill cuando el usuario quiera 'una vision unica del cliente', 'que hago con cada cliente', 'priorizar a quien impactar', 'juntar RFM y ciclo de vida', 'audiencias para el CRM', 'next best action', 'plan de contacto por cliente', o tenga ya salidas de rfm-segmentation, lifecycle-segmentation, propension-cesta-afinidad o medicion-incremental y quiera pasar a la accion."
---

# Ficha de cliente (todos los modelos en una fila que se puede ejecutar)

Cada modelo contesta una pregunta distinta. Por separado, nadie los usa a la vez; juntos dicen qué hacer con cada persona:

| Fuente | Pregunta que contesta | Herramienta |
|---|---|---|
| RFM | ¿Cuánto vale y cómo se está moviendo? | `rfm-segmentation` (rfm-333) |
| Ciclo de vida | ¿Sigue vivo? ¿En qué momento de su ciclo está? | `lifecycle-segmentation` |
| Patrón de cesta | ¿Qué compra junto y qué hábito tiene? | `propension-cesta-afinidad cesta` |
| Propensión + tenedores | ¿Qué es probable que compre? ¿Tiene una versión antigua? | `propension-cesta-afinidad matriz` |
| Control | ¿Está apartado para medir? | `medicion-incremental control` |

Script: `scripts/ficha_cliente.py`. Solo librería estándar. Lee las salidas de esas herramientas tal cual, sin retocarlas.

## Paso 1: genera las fuentes (en este orden)

1. **Control primero:** `medicion-incremental control` sobre la base COMPLETA. Si se aparta después de segmentar, no sirve.
2. RFM, ciclo de vida, matriz (con `--base` y `--vigente-desde` para las familias con versiones) y cesta sobre los mismos datos.
3. Comprueba que todas usan el **mismo id de cliente** (mismo formato, sin prefijos distintos). La ficha avisa si una fuente cubre menos del 80%.

Basta con dos fuentes; cuantas más, más fina la decisión.

## Paso 2: ejecuta

```bash
python scripts/ficha_cliente.py \
  --rfm rfm.csv --ciclo ciclo.csv --cesta cesta_clientes.csv \
  --segmentos clientes.csv --seg-id id_cliente --seg-col segmento \
  --matriz prop_matriz.csv --cuadrantes prop_cuadrantes.csv --tenedores prop_tenedores.csv \
  --control campana_control_2026-11-12.csv --fin-control 2027-01-31 \
  --output out/ficha
```

Salidas: `_ficha.csv` (una fila por cliente, ordenada por prioridad) y `_acciones.csv` (audiencias: prioridad × cuándo × palanca, con nº de clientes y gasto histórico). Lo segundo es lo que se lleva al CRM.

## Paso 3: cómo decide (explícalo; no es una caja negra)

**CUÁNDO** (ciclo de vida, cap. 15-16)
- Control → NO IMPACTAR, por encima de todo.
- Silencio (antes de la mitad de su ciclo) → esperar: iba a volver solo, e impactarle ahora es pagar ventas hechas.
- Disparadores → ahora. Prórroga → ya, la ventana más rentable. **Criterio de entrada a la prórroga (cap. 16 paso 7):** valor alto, o patrón de cesta estrecho y sostenido → pieza de SU categoría; si no, prórroga ligera y, si no responde, hibernar.
- Fuera de ciclo y activo → fuego lento (presencia sin descuento). Congelado → microondas (incentivo fuerte en el pico comercial, pocas veces). Ultra congelado o iceberg → hibernar.
- Una sola compra (no tiene ciclo) → objetivo 2ª compra si fue reciente (`--dias-segunda`, 243 por defecto); si no, hibernar.

**QUÉ** (cap. 12-13)
- Tiene la versión antigua de una familia (según `--tenedores`) → renove. El mercado de su segmento (saturado) solo sube la prioridad: **el cuadrante describe al segmento, no a la persona**. Sin `--tenedores` no se asigna renove a nadie.
- Si no, la instrucción de su patrón de cesta (monocategoría → 4 casillas dentro; dos categorías → 2+2; patrón 7 → novedades).
- Si no hay cesta, la propensión de su segmento (up selling → profundizar en la familia; cross selling → repartir entre familias).

**CÓMO: la palanca de comportamiento** (primera que se cumple). El detalle y las fuentes de cada una están en `references/palancas-conductuales.md`.

| Situación | Palanca | Qué hacer |
|---|---|---|
| Tiene versión antigua | Dotación + aversión a la pérdida | Valorar lo que ya tiene ("tu X vale tanto"), no "compra uno nuevo" |
| Patrón sostenido 3 veces | Hábito | Reforzar su rutina (formato mayor, reposición, suscripción); no pedirle que cambie |
| Nuevo / una compra reciente | Progreso dotado + fricción mínima | Hacer fácil la 2ª compra ("ya tienes 1 de 2"); sin descuento grande que ancle su precio |
| Campeón / fiel | Reconocimiento y acceso | Novedades, trato. Nunca descuento general: iba a comprar igual |
| Valioso enfriándose o en riesgo | Reciprocidad antes que descuento | Un gesto útil y personal antes de cualquier rebaja |
| Perdiéndose / iceberg | Evitar reactancia | Pocos impactos, incentivo claro, salida fácil; tras 2 picos sin respuesta, hibernar |
| Resto | Relevancia en su momento | Recordatorio útil cuando le toca, con el atributo que le mueve |

**El argumento concreto** (qué atributo va en la primera línea) sale de la matriz de afinidad de su patrón (cap. 14, `propension-cesta-afinidad`). La ficha decide la palanca; la afinidad decide las palabras.

**PRIORIDAD**: A = valor alto y en ventana (disparadores, prórroga). B = en ventana, o valor alto activo. C = resto de activos o sin dato. D = inactivos a hibernar. "-" = control o en silencio.

## Paso 4: lo que hay que decir siempre

1. **Las palancas son hipótesis, no diagnósticos.** Cada una se prueba con su propio control (90/10) antes de generalizarla. Un principio de psicología que funciona en laboratorio puede no mover a tus clientes.
2. **Una sola palanca por pieza.** Si se combinan reciprocidad + urgencia + descuento y funciona, no se sabrá qué funcionó.
3. **Nada de manipulación:** escasez o urgencia solo si son ciertas; salida fácil siempre; nada que explote a clientes vulnerables. Además de ético, protege la marca y cumple la normativa de consumo y de comunicaciones comerciales.
4. **La ficha va donde se decide** (cap. 9 paso 6): un campo en el CRM o una columna en el informe que ya se envía, no una presentación.
5. Regenera la ficha con la misma fecha de corte relativa cada periodo; el valor está en ver cómo se mueve cada cliente entre fichas.

## Límites

- Las reglas son deliberadamente simples y legibles (se pueden discutir en una sala). No es un modelo de next best action entrenado: es la versión que se entiende y se puede auditar, y la que conviene tener ANTES de entrenar uno.
- Si una fuente es de otra fecha de corte, la ficha mezcla momentos distintos. Genera todas con la misma.
