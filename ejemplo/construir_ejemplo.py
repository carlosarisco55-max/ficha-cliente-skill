"""Construye el ejemplo de punta a punta con datos INVENTADOS, ejecutando las herramientas reales.

1. Genera un negocio sintético (tienda de té con teteras que tienen versiones): clientes y tickets.
2. Prepara las entradas de cada herramienta y las ejecuta: rfm-333, lifecycle-segmentation,
   propension-cesta-afinidad (matriz + cesta) y medicion-incremental (control).
3. Junta todo con ficha_cliente.py.

Las salidas de cada herramienta quedan en ejemplo/entradas/ (son los fixtures del CI) y la ficha en ejemplo/salida/.
Rutas de las otras herramientas: variables de entorno o, por defecto, los repos hermanos en ../.
"""
import csv
import os
import random
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.abspath(os.path.join(AQUI, "..", ".."))
RFM = os.environ.get("RFM333", os.path.join(DEV, "rfm-segmentation-skill", "rfm-333", "scripts", "rfm_333.py"))
CICLO = os.environ.get("LIFECYCLE", os.path.join(DEV, "lifecycle-segmentation-skill", "scripts", "lifecycle_segmentation.py"))
PROP = os.environ.get("PROPENSION", os.path.join(DEV, "propension-cesta-afinidad-skill", "scripts", "propension_cesta_afinidad.py"))
MED = os.environ.get("MEDICION", os.path.join(DEV, "medicion-incremental-skill", "scripts", "medicion_incremental.py"))
FICHA = os.path.join(AQUI, "..", "scripts", "ficha_cliente.py")
ENT, SAL, TMP = (os.path.join(AQUI, d) for d in ("entradas", "salida", "_tmp"))
for d in (ENT, SAL, TMP):
    os.makedirs(d, exist_ok=True)

random.seed(11)
SEGS = {"Hombre <35": 0.2, "Hombre >=35": 0.3, "Mujer <35": 0.15, "Mujer >=35": 0.35}
PRECIO = {"Negro": 10.5, "Verde": 8.0, "Rojo": 8.75, "Tetera": 39.0}
HABITOS = [("Negro",), ("Verde",), ("Rojo",), ("Negro", "Verde"), ("Verde", "Rojo"), ("Negro", "Verde", "Rojo")]
FIN = date(2025, 12, 31)


def escribir(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


clientes, lineas, t = [], [], 0
for i in range(1, 1501):
    cid = f"CL{i:05d}"
    seg = random.choices(list(SEGS), list(SEGS.values()))[0]
    clientes.append([cid, seg])
    habito = random.choices(HABITOS, [30, 22, 8, 15, 15, 10])[0]
    ritmo = random.choice([30, 45, 60, 90, 120, 200])
    d = date(2024, 1, 1) + timedelta(days=random.randint(0, 600))
    for _ in range(random.choice([1, 1, 2, 3, 4, 5, 6, 8])):
        if d > FIN:
            break
        t += 1
        cats = habito if random.random() < 0.8 else random.sample(["Negro", "Verde", "Rojo"], random.randint(1, 2))
        for c in cats:
            lineas.append([f"K{t:06d}", cid, seg, d.isoformat(), c, random.choice([1, 1, 2]), PRECIO[c]])
        # los hombres compraron tetera sobre todo antes de la versión nueva (jun-2025): tenedores, mercado saturado
        p_tetera = (0.02 if d >= date(2025, 6, 1) else 0.14) if seg.startswith("Hombre") else 0.06
        if random.random() < p_tetera:
            lineas.append([f"K{t:06d}", cid, seg, d.isoformat(), "Tetera", 1, PRECIO["Tetera"]])
        d += timedelta(days=max(7, int(random.gauss(ritmo, ritmo / 3))))

escribir(os.path.join(TMP, "clientes.csv"), ["id_cliente", "segmento"], clientes)
escribir(os.path.join(TMP, "lineas.csv"), ["id_ticket", "id_cliente", "segmento", "fecha", "categoria", "unidades", "precio"], lineas)

# entradas agregadas para RFM (última fecha, nº tickets, gasto) y ciclo de vida (penúltima y última compra)
tk = defaultdict(lambda: [None, 0.0])
for tid, cid, _, f, _, u, pr in lineas:
    tk[(cid, tid)][0] = f
    tk[(cid, tid)][1] += u * pr
por_c = defaultdict(list)
for (cid, tid), (f, imp) in tk.items():
    por_c[cid].append((f, imp))
rfm_in, ciclo_in = [], []
for cid, lst in por_c.items():
    lst.sort()
    rfm_in.append([cid, lst[-1][0], len(lst), round(sum(i for _, i in lst), 2)])
    if len(lst) >= 2:
        ciclo_in.append([cid, lst[-2][0], lst[-1][0]])
escribir(os.path.join(TMP, "rfm_in.csv"), ["id_cliente", "ultima", "compras", "gasto"], rfm_in)
escribir(os.path.join(TMP, "ciclo_in.csv"), ["id_cliente", "penultima", "ultima"], ciclo_in)


def run(*args):
    print(">", os.path.basename(args[0]), *args[1:3])
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stdout + r.stderr)


T = lambda n: os.path.join(TMP, n)
run(RFM, "--input", T("rfm_in.csv"), "--output", os.path.join(ENT, "rfm.csv"), "--id-col", "id_cliente",
    "--date-col", "ultima", "--frequency-col", "compras", "--monetary-col", "gasto", "--window", "730")
run(CICLO, "--input", T("ciclo_in.csv"), "--output", os.path.join(ENT, "ciclo.csv"), "--id-col", "id_cliente",
    "--prev-date-col", "penultima", "--last-date-col", "ultima", "--date-format", "%Y-%m-%d")
run(PROP, "matriz", "--mode", "compras", "--input", T("lineas.csv"), "--base", T("clientes.csv"), "--id-col", "id_cliente",
    "--segment-col", "segmento", "--family-col", "categoria", "--date-col", "fecha", "--vigente-desde", "Tetera=2025-06-01",
    "--output", os.path.join(ENT, "prop"))
run(PROP, "cesta", "--input", T("lineas.csv"), "--ticket-col", "id_ticket", "--id-col", "id_cliente", "--date-col", "fecha",
    "--category-col", "categoria", "--amount-col", "precio", "--units-col", "unidades", "--aros", "Negro=1,Verde=2,Rojo=4",
    "--output", os.path.join(ENT, "cesta"))
run(MED, "control", "--input", T("clientes.csv"), "--id-col", "id_cliente", "--estratos", "segmento",
    "--hipotesis", "Si activamos la ficha, la conversión a 60 días sube 2 puntos", "--fracaso", "diferencia < 1 punto",
    "--autoriza", "Responsable de CRM", "--output", os.path.join(TMP, "med"))
ctrl = [f for f in os.listdir(TMP) if f.startswith("med_control_")][0]
os.replace(os.path.join(TMP, ctrl), os.path.join(ENT, "control.csv"))
escribir(os.path.join(ENT, "segmentos.csv"), ["id_cliente", "segmento"], clientes)
for n in ("prop_crecimiento.csv", "cesta_tickets.csv", "cesta_patrones.csv", "cesta_vs_azar.csv"):
    if os.path.exists(os.path.join(ENT, n)):
        os.remove(os.path.join(ENT, n))

E = lambda n: os.path.join(ENT, n)
run(FICHA, "--rfm", E("rfm.csv"), "--ciclo", E("ciclo.csv"), "--cesta", E("cesta_clientes.csv"),
    "--segmentos", E("segmentos.csv"), "--matriz", E("prop_matriz.csv"), "--cuadrantes", E("prop_cuadrantes.csv"),
    "--tenedores", E("prop_tenedores.csv"), "--control", E("control.csv"), "--output", os.path.join(SAL, "ejemplo"))
for f in os.listdir(TMP):
    os.remove(os.path.join(TMP, f))
os.rmdir(TMP)
print("OK: ejemplo/entradas (fixtures) y ejemplo/salida (ficha)")
