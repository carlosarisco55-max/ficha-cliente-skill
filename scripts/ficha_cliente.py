#!/usr/bin/env python3
"""Ficha única por cliente: junta RFM, ciclo de vida, patrón de cesta, propensión de su segmento y grupo de control
en UNA fila con QUÉ ofrecerle, CUÁNDO, con qué PALANCA de comportamiento y con qué PRIORIDAD.

Solo librería estándar. Lee las salidas tal cual de:
  rfm-333 / rfm-segmentation        (--rfm)
  lifecycle-segmentation            (--ciclo)
  propension-cesta-afinidad cesta   (--cesta, el *_clientes.csv)
  propension-cesta-afinidad matriz  (--segmentos + --matriz [+ --cuadrantes])
  medicion-incremental control      (--control, la lista con fecha)
Basta con dos fuentes; cuantas más, más completa la decisión.
"""
import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

AVISOS = []


def aviso(msg):
    AVISOS.append(msg)
    print(f"AVISO: {msg}")


def leer(path, delim=","):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=delim))
    if not rows:
        sys.exit(f"{path}: fichero vacío")
    return rows


def pick(rows, path, *candidatas, obligatoria=True):
    for c in candidatas:
        if c and c in rows[0]:
            return c
    if obligatoria:
        sys.exit(f"{path}: no encuentro ninguna de {[c for c in candidatas if c]}. Columnas: {list(rows[0])}")
    return None


def num(s):
    s = (s or "").replace("€", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "")
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- traducción de cada modelo a un lenguaje común
# valor: alto / medio / bajo ; senal: lo que dice el modelo del cliente
RFM_MAP = {
    "1. Campeones": ("alto", "campeon"), "Champions": ("alto", "campeon"),
    "Clientes fieles": ("alto", "fiel"),
    "2. Recientes de una compra": ("bajo", "nuevo"), "Nuevos / prometedores": ("bajo", "nuevo"),
    "3. Valiosos enfriandose": ("alto", "enfriando"), "5. Valiosos en riesgo": ("alto", "riesgo"),
    "En riesgo (antes valiosos)": ("alto", "riesgo"),
    "4. Ocasionales en pausa": ("medio", "ocasional"), "Necesitan atencion": ("medio", "ocasional"),
    "6. A punto de perderse": ("bajo", "perdiendose"), "Perdidos": ("bajo", "perdiendose"),
}

# palancas de comportamiento: (clave, nombre, qué hacer, base teórica). Son HIPÓTESIS a probar con control.
PALANCAS = {
    "dotacion": ("Dotación + aversión a la pérdida",
                 "Valora lo que ya tiene (renove: 'tu X vale tanto') en vez de pedirle que compre uno nuevo",
                 "Kahneman, Knetsch y Thaler 1990 (efecto dotación); Kahneman y Tversky 1979 (aversión a la pérdida)"),
    "habito": ("Hábito",
               "Refuerza la rutina que ya tiene (formato mayor, reposición, suscripción). No le pidas cambiar de hábito",
               "Wood y Neal 2007 (los hábitos se disparan por contexto y se refuerzan, no se rompen con un mensaje)"),
    "progreso": ("Segunda compra: fricción mínima + progreso dotado",
                 "Haz fácil la 2ª compra y enséñale que ya ha empezado ('ya tienes 1 de 2'). Sin descuento grande que ancle su precio",
                 "Nunes y Drèze 2006 (efecto de progreso dotado); anclaje de precio (Tversky y Kahneman 1974)"),
    "estatus": ("Reconocimiento y acceso",
                "Novedades antes que nadie, trato, acceso. Nunca descuento general: iba a comprar igual",
                "Cap. 5 (supervivencia de la muestra): descontar a quien compra solo es pagar ventas que ya tenías"),
    "reciprocidad": ("Reciprocidad antes que descuento",
                     "Un gesto útil y personal (contenido, servicio, recordatorio de lo que usa) antes de cualquier rebaja",
                     "Cialdini 1984 (reciprocidad); el descuento repetido entrena a esperar descuentos"),
    "relevancia": ("Relevancia en su momento",
                   "Un recordatorio útil cuando le toca por su ciclo, con el atributo que le mueve (no más impactos)",
                   "Cap. 14 (afinidad al mensaje) + cap. 16 (ciclo de repetición)"),
    "reactancia": ("Evitar reactancia",
                   "Pocos impactos, incentivo claro y salida fácil. Si no responde en 2 picos, hibernar",
                   "Brehm 1966 (reactancia psicológica: la presión hace que el cliente defienda su libertad de no comprar)"),
}

PROX = {"1. Silencio": 0, "2. Disparadores": 1, "3. Prorroga": 2, "4. Fuera de ciclo": 3}


def momento_corto(m):
    for k in PROX:
        if m.startswith(k):
            return k
    return m or ""


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rfm", help="CSV de rfm-333 (Id, Codigo_RFM, Grupo, Gasto) o rfm-segmentation (ID, RFM_Segment, Monetary)")
    p.add_argument("--ciclo", help="CSV de lifecycle-segmentation (Subestado, Estado, Momento_del_ciclo)")
    p.add_argument("--ciclo-id", help="columna de id en --ciclo (por defecto, la primera)")
    p.add_argument("--cesta", help="*_clientes.csv de propension-cesta-afinidad cesta")
    p.add_argument("--segmentos", help="CSV id + segmento (el mismo usado en la matriz)")
    p.add_argument("--seg-id", default="id_cliente")
    p.add_argument("--seg-col", default="segmento")
    p.add_argument("--matriz", help="*_matriz.csv de propension-cesta-afinidad matriz")
    p.add_argument("--cuadrantes", help="*_cuadrantes.csv de propension-cesta-afinidad matriz")
    p.add_argument("--tenedores", help="*_tenedores.csv de propension-cesta-afinidad matriz (quién tiene versión antigua)")
    p.add_argument("--control", help="lista de control de medicion-incremental (primera columna = id)")
    p.add_argument("--fin-control", help="fecha hasta la que no se impacta al control (texto libre)")
    p.add_argument("--dias-segunda", type=int, default=243,
                   help="clientes de una sola compra: hasta cuántos días desde ella se empuja la 2ª (por defecto el corte R2 del RFM 333)")
    p.add_argument("--output", required=True, help="prefijo de salida")
    a = p.parse_args(argv)

    fuentes = {}
    if a.rfm:
        r = leer(a.rfm)
        idc = pick(r, a.rfm, "Id", "ID", "id", "id_cliente")
        gc = pick(r, a.rfm, "Grupo", "RFM_Segment")
        cc = pick(r, a.rfm, "Codigo_RFM", obligatoria=False)
        mc = pick(r, a.rfm, "Gasto", "Monetary", obligatoria=False)
        fc = pick(r, a.rfm, "Compras", "Frequency", obligatoria=False)
        dc = pick(r, a.rfm, "Dias", "Recency", obligatoria=False)
        fuentes["rfm"] = {x[idc].strip(): {"rfm_grupo": x[gc].strip(), "rfm_codigo": x[cc] if cc else "",
                                            "gasto": num(x[mc]) if mc else 0.0,
                                            "compras": num(x[fc]) if fc else None,
                                            "dias": num(x[dc]) if dc else None} for x in r}
        raros = {v["rfm_grupo"] for v in fuentes["rfm"].values()} - set(RFM_MAP)
        if raros:
            aviso(f"grupos RFM que no reconozco: {sorted(raros)}. Se tratan como valor medio sin señal")
    if a.ciclo:
        r = leer(a.ciclo)
        idc = a.ciclo_id or list(r[0])[0]
        pick(r, a.ciclo, "Subestado")
        fuentes["ciclo"] = {x[idc].strip(): {"subestado": x["Subestado"], "estado": x.get("Estado", ""),
                                              "momento": momento_corto(x.get("Momento_del_ciclo", ""))} for x in r}
    if a.cesta:
        r = leer(a.cesta)
        pick(r, a.cesta, "cliente")
        fuentes["cesta"] = {x["cliente"].strip(): x for x in r}
    seg_info, cuad = {}, defaultdict(dict)
    if a.segmentos:
        if not a.matriz:
            sys.exit("--segmentos necesita --matriz para saber qué familias son propensas en cada segmento")
        r = leer(a.segmentos)
        sid, sc = pick(r, a.segmentos, a.seg_id), pick(r, a.segmentos, a.seg_col)
        fuentes["segmento"] = {x[sid].strip(): x[sc].strip() for x in r}
        for x in leer(a.matriz):
            if x["segmento"] != "LINEA BASE":
                seg_info[x["segmento"]] = (x["tipo"], x["familias_por_encima"])
        if a.cuadrantes:
            for x in leer(a.cuadrantes):
                cuad[x["segmento"]][x["familia"]] = x["mercado"]
    antiguas = defaultdict(list)
    if a.tenedores:
        for x in leer(a.tenedores):
            if x["version"] == "antigua":
                antiguas[x["cliente"].strip()].append(x["familia"])
    elif a.cuadrantes:
        aviso("hay --cuadrantes pero no --tenedores: el cuadrante dice cómo está el SEGMENTO, no si este cliente tiene la "
              "versión antigua. No se asigna renove a nadie hasta pasar --tenedores (tener no es comprar, cap. 12)")
    control = set()
    if a.control:
        r = leer(a.control)
        control = {x[list(r[0])[0]].strip() for x in r}
        fuentes["control"] = {i: True for i in control}

    if len([k for k in fuentes if k != "control"]) < 2:
        sys.exit("pasa al menos dos fuentes (de --rfm, --ciclo, --cesta, --segmentos+--matriz): la ficha existe para cruzarlas")

    ids = set().union(*[set(v) for k, v in fuentes.items() if k != "control"])
    una = {i for i, v in fuentes.get("rfm", {}).items() if v["compras"] == 1}
    print(f"Clientes en la ficha: {len(ids)}" + (f" ({len(una)} con una sola compra)" if una else ""))
    for k, v in fuentes.items():
        if k == "control":
            continue
        esperados = ids - una if k == "ciclo" else ids
        cob = len(esperados & set(v)) / len(esperados) if esperados else 1
        print(f"- {k}: {len(v)} clientes, cubre el {cob:.0%} de "
              f"{'los clientes con 2+ compras (los de una sola compra no tienen ciclo)' if k == 'ciclo' and una else 'la ficha'}")
        if cob < 0.8:
            aviso(f"'{k}' solo cubre el {cob:.0%} de los clientes. Si deberían ser los mismos, revisa que los id coinciden "
                  "entre sistemas (formato, ceros a la izquierda, prefijos)")
    if control:
        fuera = control - ids
        if fuera:
            aviso(f"{len(fuera)} id del control no aparecen en ninguna fuente: el control tiene que salir de la misma base")

    filas, acciones = [], Counter()
    gasto_accion = Counter()
    for cid in sorted(ids):
        rf = fuentes.get("rfm", {}).get(cid, {})
        ci = fuentes.get("ciclo", {}).get(cid, {})
        ce = fuentes.get("cesta", {}).get(cid, {})
        seg = fuentes.get("segmento", {}).get(cid, "")
        valor, senal = RFM_MAP.get(rf.get("rfm_grupo", ""), ("medio" if rf else "", ""))
        sub, mom = ci.get("subestado", ""), ci.get("momento", "")
        sostenido = ce.get("patron_sostenido") == "sí"
        mono = ce.get("patron_actual") in ("1", "2", "4", "8")
        tipo, fams = seg_info.get(seg, ("", ""))
        mercados = cuad.get(seg, {})
        # renove solo para quien TIENE la versión antigua; el mercado del segmento solo ordena la prioridad
        saturadas = antiguas.get(cid, [])

        # QUÉ
        if saturadas:
            sat_seg = [f for f in saturadas if mercados.get(f) == "Saturado"]
            que = f"Renove de {', '.join(saturadas)}: tiene la versión antigua" + \
                  (" (y su segmento está saturado: prioridad de la campaña)" if sat_seg else "")
        elif ce:
            que = ce.get("instruccion", "")
        elif tipo == "Up selling":
            que = f"Profundizar en {fams}: las 4 casillas dentro de esa familia"
        elif tipo == "Cross selling":
            que = f"Casillas repartidas entre {fams.replace(' ', ' y ')}"
        else:
            que = "Sin dato de producto: añade --cesta o --segmentos+--matriz"

        # CUÁNDO (ciclo de vida, cap. 15-16) + criterio de prórroga con cesta (cap. 16 paso 7)
        if cid in control:
            cuando = f"NO IMPACTAR: grupo de control{' hasta ' + a.fin_control if a.fin_control else ''}"
        elif mom == "1. Silencio":
            cuando = "Esperar: está en silencio (iba a volver solo; impactarle ahora es pagar ventas hechas)"
        elif mom == "2. Disparadores":
            cuando = "Ahora: disparador de recompra"
        elif mom == "3. Prorroga":
            if valor == "alto" or (sostenido and mono):
                cuando = "Ya: prórroga con pieza de SU categoría (ventana de recuperación más rentable)"
            else:
                cuando = "Ya: prórroga ligera; si no responde, hibernar"
        elif mom == "4. Fuera de ciclo":
            if sub.startswith("Activo"):
                cuando = "Fuego lento: presencia sin descuento (fuera de ciclo pero activo)"
            elif "Congelado" in sub and "Ultra" not in sub:
                cuando = "Microondas: incentivo fuerte en el pico comercial del año, pocas veces"
            else:
                cuando = "Hibernar: como mucho 1 intento en el pico; tras 2 picos sin respuesta, fuera"
        elif cid in una:
            dias = rf.get("dias")
            if dias is None or dias <= a.dias_segunda:
                cuando = "Ahora: objetivo 2ª compra (aún no tiene ciclo)"
            else:
                cuando = f"Hibernar: una sola compra hace más de {a.dias_segunda} días"
        elif senal in ("riesgo", "enfriando"):
            cuando = "Pronto (sin dato de ciclo: lo dice el RFM)"
        else:
            cuando = "Sin dato de ciclo: añade --ciclo"

        # CÓMO: palanca de comportamiento (primera regla que se cumple)
        if saturadas:
            pal = "dotacion"
        elif sostenido:
            pal = "habito"
        elif senal == "nuevo" or (cid in una and cuando.startswith("Ahora")):
            pal = "progreso"
        elif senal in ("campeon", "fiel"):
            pal = "estatus"
        elif senal in ("riesgo", "enfriando"):
            pal = "reciprocidad"
        elif senal == "perdiendose" or "Iceberg" in sub or "Ultra" in sub:
            pal = "reactancia"
        else:
            pal = "relevancia"
        if cid in control:
            pal = ""

        # PRIORIDAD
        ventana = mom in ("2. Disparadores", "3. Prorroga") or cuando.startswith("Ahora: objetivo 2ª")
        if cid in control:
            prio = "-"
        elif mom == "1. Silencio":
            prio = "-"
        elif valor == "alto" and ventana:
            prio = "A"
        elif ventana or (valor == "alto" and sub.startswith("Activo")):
            prio = "B"
        elif cuando.startswith("Hibernar"):
            prio = "D"
        elif sub.startswith("Activo") or not sub:
            prio = "C"
        else:
            prio = "D"

        nombre, hacer, base = PALANCAS[pal] if pal else ("", "", "")
        fila = [cid, rf.get("rfm_codigo", ""), rf.get("rfm_grupo", ""), valor, sub, mom,
                ce.get("patron_actual", ""), ce.get("composicion", ""), "sí" if sostenido else ("no" if ce else ""),
                ce.get("siguiente_natural", ""), seg, tipo, fams, "; ".join(f"{f}: {m}" for f, m in sorted(mercados.items())),
                "sí" if cid in control else "no", prio, cuando, que, nombre, hacer, base]
        filas.append(fila)
        acciones[(prio, cuando.split(":")[0], nombre)] += 1
        gasto_accion[(prio, cuando.split(":")[0], nombre)] += rf.get("gasto", 0.0)

    head = ["id", "rfm_codigo", "rfm_grupo", "valor", "subestado_ciclo", "momento_ciclo", "patron_cesta", "composicion_cesta",
            "patron_sostenido", "siguiente_patron", "segmento", "tipo_propension", "familias_propensas", "mercado_por_familia",
            "en_control", "prioridad", "CUANDO", "QUE", "PALANCA", "COMO", "base_de_la_palanca"]
    orden = {"A": 0, "B": 1, "C": 2, "D": 3, "-": 4}
    filas.sort(key=lambda f: (orden[f[15]], f[0]))
    os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
    with open(f"{a.output}_ficha.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(filas)
    print(f"-> {a.output}_ficha.csv")
    with open(f"{a.output}_acciones.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prioridad", "cuando", "palanca", "clientes", "gasto_historico"])
        for k, v in sorted(acciones.items(), key=lambda kv: (orden[kv[0][0]], -kv[1])):
            w.writerow([*k, v, round(gasto_accion[k], 2)])
    print(f"-> {a.output}_acciones.csv")

    print("\n## Audiencias listas para activar (prioridad · cuándo · palanca)")
    for (pr, cu, pa), v in sorted(acciones.items(), key=lambda kv: (orden[kv[0][0]], -kv[1]))[:12]:
        g = gasto_accion[(pr, cu, pa)]
        print(f"- [{pr}] {cu} · {pa or '—'}: {v} clientes" + (f" (gasto histórico {g:,.0f})" if g else ""))
    n_ctrl = sum(1 for f in filas if f[14] == "sí")
    if not control:
        aviso("sin --control: ninguna de estas acciones podrá medirse. Aparta el control ANTES de segmentar "
              "(medicion-incremental control) y vuelve a generar la ficha")
    else:
        print(f"- Control: {n_ctrl} clientes marcados como NO IMPACTAR.")
    print("\nLas palancas son hipótesis de comportamiento, no verdades: cada una se prueba con su propio grupo de control.")
    if AVISOS:
        print(f"\n{len(AVISOS)} aviso(s): léelos antes de activar ninguna audiencia.")


if __name__ == "__main__":
    main()
