
import random
import statistics as st
import sudoku_aco as s

SEEDS = 30

def run30(p, **kw):
    """Corre 30 semillas y devuelve estadisticas."""
    ok = 0; iters = []; times = []
    for sd in range(SEEDS):
        random.seed(sd)
        r = s.AntColonySudoku(p, **kw).solve(time_limit=15.0)
        if r["solved"]:
            ok += 1; iters.append(r["iterations"]); times.append(r["time"])
    return ok, iters, times

print("(A) METRICAS SOBRE 30 CORRIDAS INDEPENDIENTES (semillas 0..29)")
configs = [
    ("facil   | ACO puro",      s.PUZZLES["facil"],   dict(use_cp=False, ls_steps=0)),
    ("medio   | ACO puro",      s.PUZZLES["medio"],   dict(use_cp=False, ls_steps=0)),
    ("dificil | CP+ACO+local",  s.PUZZLES["dificil"], dict()),
    ("dificil | ACO puro(+CP)", s.PUZZLES["dificil"], dict(ls_steps=0)),
]
print("%-26s %7s %16s %22s" % ("Config", "Exito", "Iter (min/med/max)", "Tiempo s (min/med/max)"))
for label, p, kw in configs:
    ok, iters, times = run30(p, **kw)
    it = "%d/%d/%d" % (min(iters), round(st.mean(iters)), max(iters))
    tm = "%.3f/%.3f/%.3f" % (min(times), st.median(times), max(times))
    print("%-26s %6d/%d %16s %22s" % (label, ok, SEEDS, it, tm), flush=True)

print()
print("(B) JUSTIFICACION DE LOS PESOS  (instancia: medio, ACO puro, SIN reinicios)")
print("    Sin reinicios para que se note el efecto del parametro.")

def sweep(p, alpha, beta):
    ok = 0; iters = []
    for sd in range(SEEDS):
        random.seed(sd)
        r = s.AntColonySudoku(p, use_cp=False, ls_steps=0, alpha=alpha,
                              beta=beta, max_iter=300).solve(max_restarts=0, time_limit=10.0)
        if r["solved"]: ok += 1; iters.append(r["iterations"])
    avg = round(st.mean(iters)) if iters else 0
    return ok, avg

P = s.PUZZLES["medio"]
print("\n-- Variando beta (peso de la HEURISTICA), con alpha=1 --")
print("%8s %8s %14s" % ("alpha", "beta", "Exito | iter.med"))
for beta in [0, 1, 2, 3, 5]:
    ok, avg = sweep(P, 1.0, beta)
    print("%8.1f %8.1f   %2d/%d | %d" % (1.0, beta, ok, SEEDS, avg), flush=True)

print("\n-- Variando alpha (peso de la FEROMONA), con beta=3 --")
print("%8s %8s %14s" % ("alpha", "beta", "Exito | iter.med"))
for alpha in [0, 1, 2, 3]:
    ok, avg = sweep(P, alpha, 3.0)
    print("%8.1f %8.1f   %2d/%d | %d" % (alpha, 3.0, ok, SEEDS, avg), flush=True)

print("\nNota: 'iter.med' = iteraciones medias de las corridas con exito.")
