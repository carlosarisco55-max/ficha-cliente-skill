# Ficha de cliente

Junta en **una fila por cliente** lo que dicen todos los modelos de segmentación y decide **qué ofrecerle, cuándo, con qué palanca de comportamiento y con qué prioridad**.

| Fuente | Qué aporta | Herramienta |
|---|---|---|
| RFM | Valor y movimiento | [`rfm-segmentation-skill`](https://github.com/carlosarisco55-max/rfm-segmentation-skill) (rfm-333) |
| Ciclo de vida | ¿Sigue vivo? ¿En qué momento de su ciclo está? | [`lifecycle-segmentation-skill`](https://github.com/carlosarisco55-max/lifecycle-segmentation-skill) |
| Cesta | Qué compra junto, si es un hábito | `propension-cesta-afinidad-skill` (cesta) |
| Propensión + tenedores | Qué es probable que compre; si tiene una versión antigua | `propension-cesta-afinidad-skill` (matriz) |
| Control | Si está apartado para medir | `medicion-incremental-skill` (control) |

Script de Python de librería estándar, empaquetado también como *skill* de Claude Code. Lee las salidas de esas herramientas tal cual.

## Qué devuelve

- `_ficha.csv`: una fila por cliente, ordenada por prioridad, con `CUANDO`, `QUE`, `PALANCA` y `COMO` (más la base teórica de la palanca).
- `_acciones.csv`: las audiencias listas para el CRM (prioridad × cuándo × palanca), con número de clientes y gasto histórico.

## Las reglas, a la vista

No es una caja negra: cada decisión es una regla que se puede discutir en una sala (ver `SKILL.md`).

- **Cuándo:** sale del momento del ciclo de repetición. En silencio no se impacta, en disparadores sí, y la prórroga es la ventana más rentable. Los inactivos van a microondas o a hibernar. Los clientes con una sola compra tienen como objetivo la segunda.
- **Qué:** si el cliente **tiene** la versión antigua, renove; si no, lo que diga su patrón de cesta; si no, la propensión de su segmento.
- **Cómo:** hábito, dotación y aversión a la pérdida, progreso dotado, reconocimiento, reciprocidad, evitar la reactancia o relevancia. Cada palanca tiene su fuente en [`references/palancas-conductuales.md`](references/palancas-conductuales.md) y se trata como **hipótesis a probar con control**, no como diagnóstico.

## Comprobaciones

- Cobertura de cada fuente: si los id no casan entre sistemas, avisa. Los clientes de una sola compra no cuentan como hueco del ciclo de vida.
- Sin la lista de quién tiene la versión antigua, **no asigna renove**: el cuadrante describe al segmento, no a la persona (tener no es comprar).
- Sin grupo de control, avisa de que ninguna acción se podrá medir.

## Uso

```bash
python scripts/ficha_cliente.py --rfm rfm.csv --ciclo ciclo.csv --cesta cesta_clientes.csv \
  --segmentos clientes.csv --matriz prop_matriz.csv --cuadrantes prop_cuadrantes.csv \
  --tenedores prop_tenedores.csv --control control.csv --output out/ficha
```

## Ejemplo de punta a punta

`python ejemplo/construir_ejemplo.py` genera una tienda de té **inventada** (1.500 clientes, con teteras que tienen versiones) y ejecuta de verdad las cinco herramientas: RFM, ciclo de vida, matriz, cesta y control. Después las junta en la ficha. Las salidas intermedias quedan en `ejemplo/entradas/` (son los fixtures del CI) y la ficha en `ejemplo/salida/`.

## Licencia

MIT
