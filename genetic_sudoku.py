
import random
import time
import sudoku_aco as sa


class GeneticSudoku:
    """Resuelve un Sudoku con un Algoritmo Genetico (encoding por bloque)."""

    # Conjuntos discretos de parametros para la auto-adaptacion (como el PDF)
    CROSSOVER_SET = [0.6, 0.8, 0.9]
    MUTATION_SET = [0.01, 0.1, 0.2]

    def __init__(self, puzzle_text, pop_size=200, elitism=6, tournament=3,
                 crossover_rate=0.8, mutation_rate=0.1, adaptive=False,
                 use_cp=True, max_gen=3000, restart_after=120):
        # --- Lectura, validacion y propagacion de restricciones ---
        self.original = sa.parse_puzzle(puzzle_text)
        if not sa.givens_are_valid(self.original):
            raise ValueError("El Sudoku de entrada es invalido (pistas repetidas).")
        if use_cp:
            self.fixed_board, self.n_fixed_by_cp = sa.constraint_propagation(self.original)
        else:
            self.fixed_board, self.n_fixed_by_cp = list(self.original), 0

        # --- Estructura por bloque: celdas libres y digitos faltantes ---
        self.free_cells, self.missing = [], []
        for b in range(sa.N):
            present = set(self.fixed_board[i] for i in sa.BLOCKS[b] if self.fixed_board[i] != 0)
            self.free_cells.append([i for i in sa.BLOCKS[b] if self.fixed_board[i] == 0])
            self.missing.append([d for d in range(1, sa.N + 1) if d not in present])

        # --- Parametros del AG ---
        self.pop_size = pop_size
        self.elitism = elitism
        self.tournament = tournament
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.adaptive = adaptive
        self.max_gen = max_gen
        self.restart_after = restart_after

    # ----------------------------------------------------------------
    def _random_individual(self):
        """Crea un tablero donde cada bloque es una permutacion aleatoria."""
        board = list(self.fixed_board)
        for b in range(sa.N):
            digits = list(self.missing[b])
            random.shuffle(digits)
            for cell, d in zip(self.free_cells[b], digits):
                board[cell] = d
        return board

    def _fitness(self, board):
        """Funcion objetivo: numero de conflictos en filas y columnas (0 = resuelto)."""
        return sa.count_conflicts(board)

    # ----------------------------------------------------------------
    def _tournament_select(self, pop, fits):
        """Seleccion por torneo: devuelve el mejor de 'tournament' individuos al azar."""
        best = random.randrange(len(pop))
        for _ in range(self.tournament - 1):
            i = random.randrange(len(pop))
            if fits[i] < fits[best]:
                best = i
        return pop[best]

    def _crossover(self, parent_a, parent_b):
        """Cruza por bloque: el hijo hereda cada bloque de uno u otro padre."""
        child = list(self.fixed_board)
        for b in range(sa.N):
            source = parent_a if random.random() < 0.5 else parent_b
            for cell in self.free_cells[b]:
                child[cell] = source[cell]
        return child

    def _mutate(self, board):
        """Mutacion: con prob. 'mutation_rate' intercambia 2 celdas libres de un bloque."""
        for b in range(sa.N):
            if random.random() < self.mutation_rate and len(self.free_cells[b]) >= 2:
                i, j = random.sample(self.free_cells[b], 2)
                board[i], board[j] = board[j], board[i]
        return board

    # ----------------------------------------------------------------
    def _adapt_rates(self, improved):
        """
        Auto-adaptacion: ajusta cruza y mutacion entre los conjuntos discretos
        segun haya o no mejora (casos de exito).
          - Si NO mejora (estancamiento): explorar -> subir mutacion y cruza.
          - Si mejora: explotar -> bajar mutacion.
        """
        ci = self.CROSSOVER_SET.index(min(self.CROSSOVER_SET,
                                          key=lambda x: abs(x - self.crossover_rate)))
        mi = self.MUTATION_SET.index(min(self.MUTATION_SET,
                                         key=lambda x: abs(x - self.mutation_rate)))
        if improved:
            mi = max(0, mi - 1)            # explotar: menos mutacion
        else:
            mi = min(len(self.MUTATION_SET) - 1, mi + 1)   # explorar: mas mutacion
            ci = min(len(self.CROSSOVER_SET) - 1, ci + 1)  # y mas cruza
        self.mutation_rate = self.MUTATION_SET[mi]
        self.crossover_rate = self.CROSSOVER_SET[ci]

    # ----------------------------------------------------------------
    def solve(self, time_limit=20.0, verbose=False):
        """Bucle principal del AG. Devuelve dict con la mejor solucion y estadisticas."""
        start = time.time()

        population = [self._random_individual() for _ in range(self.pop_size)]
        fits = [self._fitness(ind) for ind in population]

        best_idx = min(range(len(fits)), key=lambda i: fits[i])
        best_board, best_cost = list(population[best_idx]), fits[best_idx]

        generations, restarts, no_improve = 0, 0, 0
        window_improved = False   # ¿hubo mejora en la ventana de adaptacion?
        history = []              # mejor coste por generacion (para graficar)

        for gen in range(self.max_gen):
            generations += 1

            # Ordenar por aptitud para aplicar elitismo
            order = sorted(range(len(population)), key=lambda i: fits[i])
            new_pop = [list(population[order[k]]) for k in range(self.elitism)]

            # Generar descendencia
            while len(new_pop) < self.pop_size:
                p1 = self._tournament_select(population, fits)
                if random.random() < self.crossover_rate:
                    child = self._crossover(p1, self._tournament_select(population, fits))
                else:
                    child = list(p1)
                self._mutate(child)
                new_pop.append(child)

            population = new_pop
            fits = [self._fitness(ind) for ind in population]

            # Actualizar mejor global
            gen_best = min(range(len(fits)), key=lambda i: fits[i])
            if fits[gen_best] < best_cost:
                best_cost = fits[gen_best]
                best_board = list(population[gen_best])
                no_improve = 0
                window_improved = True
            else:
                no_improve += 1

            if verbose and generations % 50 == 0:
                print("  gen %4d | mejor coste = %d | cruza=%.2f mut=%.2f"
                      % (generations, best_cost, self.crossover_rate, self.mutation_rate))

            history.append(best_cost)   # registrar convergencia

            # Parada por solucion
            if best_cost == 0:
                break

            # Auto-adaptacion de parametros cada 20 generaciones
            if self.adaptive and generations % 20 == 0:
                self._adapt_rates(window_improved)
                window_improved = False

            # Reinicio ante estancamiento (conserva al mejor)
            if no_improve >= self.restart_after:
                population = [self._random_individual() for _ in range(self.pop_size - 1)]
                population.append(list(best_board))
                fits = [self._fitness(ind) for ind in population]
                no_improve = 0
                restarts += 1

            # Limite de tiempo
            if time.time() - start > time_limit:
                break

        return {
            "board": best_board,
            "solved": best_cost == 0 and sa.is_valid_solution(best_board),
            "cost": best_cost,
            "iterations": generations,   # generaciones (nombre comun con ACO)
            "restarts": restarts,
            "time": time.time() - start,
            "fixed_by_cp": self.n_fixed_by_cp,
            "history": history,
        }

# Demostracion por linea de comandos

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Solver de Sudoku con Algoritmo Genetico.")
    parser.add_argument("--puzzle", default="dificil", choices=list(sa.PUZZLES.keys()))
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--adaptive", action="store_true",
                        help="Activa la auto-adaptacion de cruza y mutacion.")
    parser.add_argument("--no-cp", action="store_true")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    puzzle = sa.PUZZLES[args.puzzle]
    print("=== Sudoku con Algoritmo Genetico (instancia: %s) ===" % args.puzzle)
    sa.print_board(sa.parse_puzzle(puzzle), "\nTABLERO INICIAL:")

    ga = GeneticSudoku(puzzle, adaptive=args.adaptive, use_cp=not args.no_cp)
    result = ga.solve(verbose=args.verbose)

    sa.print_board(result["board"], "\nRESULTADO:")
    print("\nResuelto    :", "SI" if result["solved"] else "NO")
    print("Conflictos  :", result["cost"])
    print("Generaciones:", result["iterations"])
    print("Reinicios   :", result["restarts"])
    print("Tiempo (s)  : %.3f" % result["time"])
