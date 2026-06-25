
import os
import random
import statistics as st

import matplotlib
matplotlib.use("Agg")          # backend sin ventana: guarda imagenes a archivo
import matplotlib.pyplot as plt

import sudoku_aco as sa
import genetic_sudoku as gg

os.makedirs("figuras", exist_ok=True)
SEEDS = 30
TL = 8.0   # limite de tiempo por corrida (s)


# ----------------------------------------------------------------
def aco_run(p, seed, adaptive, use_cp):
    random.seed(seed)
    return sa.AntColonySudoku(p, use_cp=use_cp, ls_steps=0,
                              adaptive=adaptive).solve(time_limit=TL)

def ga_run(p, seed, adaptive, use_cp):
    random.seed(seed)
    return gg.GeneticSudoku(p, use_cp=use_cp,
                            adaptive=adaptive).solve(time_limit=TL)

def summarize(runner, p, adaptive, use_cp):
    ok, times = 0, []
    for sd in range(SEEDS):
        r = runner(p, sd, adaptive, use_cp)
        if r["solved"]:
            ok += 1
            times.append(r["time"])
    return ok, times



# (1) TABLA COMPARATIVA 30 CORRIDAS

instancias = [
    ("medio (sin CP)",   sa.PUZZLES["medio"],   False),
    ("dificil (con CP)", sa.PUZZLES["dificil"], True),
]
metodos = [
    ("ACO",          aco_run, False),
    ("ACO adapt.",   aco_run, True),
    ("GA",           ga_run,  False),
    ("GA adapt.",    ga_run,  True),
]

print("=" * 64)
print("COMPARACION ACO vs GA  (%d corridas, limite %.0fs)" % (SEEDS, TL))
print("=" * 64)
print("%-18s %-12s %8s %12s" % ("Instancia", "Metodo", "Exito", "t.medio(s)"))

exito_data = {nombre: {} for nombre, _, _ in instancias}
tiempos_medio = {}   # para el boxplot (instancia 'medio')

for nombre, p, use_cp in instancias:
    for met_nombre, runner, adaptive in metodos:
        ok, times = summarize(runner, p, adaptive, use_cp)
        avt = st.mean(times) if times else 0.0
        exito_data[nombre][met_nombre] = ok
        if nombre.startswith("medio"):
            tiempos_medio[met_nombre] = times
        print("%-18s %-12s %6d/%d %12.3f" % (nombre, met_nombre, ok, SEEDS, avt),
              flush=True)


# (2) FIGURA: CONVERGENCIA (coste vs iteracion) ACO vs GA

P = sa.PUZZLES["medio"]
random.seed(0)
h_aco = sa.AntColonySudoku(P, use_cp=False, ls_steps=0).solve(time_limit=TL)["history"]
random.seed(0)
h_ga = gg.GeneticSudoku(P, use_cp=False).solve(time_limit=TL)["history"]

plt.figure(figsize=(7, 4.2))
plt.plot(range(1, len(h_aco) + 1), h_aco, label="ACO", linewidth=2)
plt.plot(range(1, len(h_ga) + 1), h_ga, label="Algoritmo Genetico", linewidth=2)
plt.xlabel("Iteracion / Generacion")
plt.ylabel("Mejor coste (conflictos)")
plt.title("Convergencia: ACO vs GA (instancia media)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("figuras/fig_convergencia.png", dpi=150)
plt.close()
print("\n[figura] figuras/fig_convergencia.png", flush=True)


# (3) FIGURA: TASA DE EXITO por algoritmo e instancia

labels = [m[0] for m in metodos]
x = range(len(labels))
ancho = 0.35
medio_vals = [exito_data["medio (sin CP)"][m] for m in labels]
dif_vals = [exito_data["dificil (con CP)"][m] for m in labels]

plt.figure(figsize=(7, 4.2))
plt.bar([i - ancho / 2 for i in x], medio_vals, ancho, label="medio")
plt.bar([i + ancho / 2 for i in x], dif_vals, ancho, label="dificil")
plt.xticks(list(x), labels)
plt.ylabel("Corridas resueltas (de %d)" % SEEDS)
plt.title("Tasa de exito por algoritmo e instancia")
plt.ylim(0, SEEDS + 1)
plt.legend()
plt.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("figuras/fig_exito.png", dpi=150)
plt.close()
print("[figura] figuras/fig_exito.png", flush=True)



# (4) FIGURA: BOXPLOT de tiempos (instancia media, donde ambos resuelven)

datos = [tiempos_medio.get(m, []) for m in labels]
datos = [d if d else [0] for d in datos]   # evitar listas vacias

plt.figure(figsize=(7, 4.2))
plt.boxplot(datos, showmeans=True)
plt.xticks(range(1, len(labels) + 1), labels)   # etiquetas (compatible con toda version)
plt.ylabel("Tiempo de resolucion (s)")
plt.title("Tiempos de resolucion (instancia media, 30 corridas)")
plt.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("figuras/fig_tiempos.png", dpi=150)
plt.close()
print("[figura] figuras/fig_tiempos.png", flush=True)



# (5) FIGURA: SENSIBILIDAD del peso beta (justifica su eleccion)

betas = [0, 1, 2, 3, 5]
exito_beta, iter_beta = [], []
for beta in betas:
    ok, its = 0, []
    for sd in range(SEEDS):
        random.seed(sd)
        r = sa.AntColonySudoku(P, use_cp=False, ls_steps=0, alpha=1.0,
                               beta=float(beta), max_iter=300).solve(max_restarts=0, time_limit=TL)
        if r["solved"]:
            ok += 1; its.append(r["iterations"])
    exito_beta.append(ok)
    iter_beta.append(st.mean(its) if its else 0)

fig, ax1 = plt.subplots(figsize=(7, 4.2))
ax1.bar([str(b) for b in betas], exito_beta, color="tab:blue", alpha=0.7)
ax1.set_xlabel("Valor de beta (peso de la heuristica)")
ax1.set_ylabel("Corridas resueltas (de %d)" % SEEDS, color="tab:blue")
ax1.set_ylim(0, SEEDS + 1)
ax2 = ax1.twinx()
ax2.plot([str(b) for b in betas], iter_beta, color="tab:red", marker="o", linewidth=2)
ax2.set_ylabel("Iteraciones medias (exito)", color="tab:red")
plt.title("Efecto de beta en exito e iteraciones (alpha=1)")
plt.tight_layout()
plt.savefig("figuras/fig_parametros.png", dpi=150)
plt.close()
print("[figura] figuras/fig_parametros.png", flush=True)

print("\nLISTO. 4 figuras guardadas en figuras/.")
