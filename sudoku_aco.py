
import random
import time
import argparse



# 1. CONSTANTES Y MAPAS DE INDICES DEL TABLERO
# --------------------------------------------------------------------
# El tablero se representa como una lista plana de 81 enteros (0 = vacio).
# El indice de una celda va de 0 a 80:  indice = fila*9 + columna.
# Precalculamos, una sola vez, que celdas forman cada fila, columna y
# bloque, y los "peers" (vecinos) de cada celda. Asi el resto del codigo
# es mas claro y rapido.

N = 9          # dimension del Sudoku (9x9)
CELLS = N * N  # 81 celdas

# Indices de cada fila, columna y bloque 3x3
ROWS = [[r * N + c for c in range(N)] for r in range(N)]
COLS = [[r * N + c for r in range(N)] for c in range(N)]


def _block_indices(b):
    """Devuelve los 9 indices de celda del bloque 3x3 numero b (0..8)."""
    br, bc = (b // 3) * 3, (b % 3) * 3  # esquina superior-izquierda del bloque
    return [(br + i) * N + (bc + j) for i in range(3) for j in range(3)]


BLOCKS = [_block_indices(b) for b in range(N)]


def cell_block(idx):
    """Numero de bloque (0..8) al que pertenece la celda 'idx'."""
    r, c = idx // N, idx % N
    return (r // 3) * 3 + (c // 3)


# PEERS[idx] = conjunto de celdas que comparten fila, columna o bloque
# con 'idx' (sin incluirse a si misma). Sirve para la propagacion de
# restricciones y para contar conflictos.
PEERS = []
for idx in range(CELLS):
    peers = set(ROWS[idx // N]) | set(COLS[idx % N]) | set(BLOCKS[cell_block(idx)])
    peers.discard(idx)
    PEERS.append(peers)


# 2. UTILIDADES DE TABLERO: parseo, impresion, validacion, errores


def parse_puzzle(text):
    """
    Convierte una cadena de 81 caracteres en una lista de 81 enteros.
    Acepta '0' o '.' para representar celdas vacias.
    Lanza ValueError si la longitud no es 81 o hay caracteres invalidos.
    """
    text = text.strip().replace("\n", "").replace(" ", "")
    if len(text) != CELLS:
        raise ValueError("El sudoku debe tener exactamente 81 caracteres "
                         "(tiene %d)." % len(text))
    board = []
    for ch in text:
        if ch in ".0":
            board.append(0)
        elif ch in "123456789":
            board.append(int(ch))
        else:
            raise ValueError("Caracter invalido en el sudoku: %r" % ch)
    return board


def board_to_str(board):
    """Devuelve el tablero como cadena de 81 caracteres (0 = vacio)."""
    return "".join(str(v) for v in board)


def print_board(board, title=None):
    """Imprime el tablero 9x9 de forma legible, con separadores de bloque."""
    if title:
        print(title)
    line = "+-------+-------+-------+"
    print(line)
    for r in range(N):
        row_str = "| "
        for c in range(N):
            v = board[r * N + c]
            row_str += (str(v) if v != 0 else ".") + " "
            if c % 3 == 2:
                row_str += "| "
        print(row_str)
        if r % 3 == 2:
            print(line)


def givens_are_valid(board):
    """
    Verifica que las pistas iniciales no violen ya las reglas del Sudoku
    (que no haya un mismo digito repetido en una fila, columna o bloque).
    Devuelve True si las pistas son consistentes.
    """
    for unit in ROWS + COLS + BLOCKS:
        seen = set()
        for idx in unit:
            v = board[idx]
            if v != 0:
                if v in seen:
                    return False
                seen.add(v)
    return True


def count_conflicts(board):
    """
    Numero total de conflictos (digitos repetidos) en FILAS y COLUMNAS.
    Como cada bloque es siempre una permutacion valida (por construccion),
    no hace falta contar conflictos de bloque. Un tablero resuelto tiene
    count_conflicts == 0.

    Por cada fila/columna, los repetidos = 9 - (cantidad de valores distintos).
    """
    total = 0
    for unit in ROWS + COLS:
        distinct = len(set(board[idx] for idx in unit))
        total += (N - distinct)
    return total


def is_valid_solution(board):
    """True si el tablero esta completo y cumple TODAS las reglas del Sudoku."""
    if any(v == 0 for v in board):
        return False
    for unit in ROWS + COLS + BLOCKS:
        if len(set(board[idx] for idx in unit)) != N:
            return False
    return True


# 3. PROPAGACION DE RESTRICCIONES (preprocesamiento ligero)
# --------------------------------------------------------------------
# Antes de lanzar las hormigas, fijamos las celdas que tienen UN SOLO
# valor posible ("naked singles"): si para una celda vacia todos los
# digitos menos uno ya aparecen entre sus vecinos, ese unico digito es
# forzoso. Repetimos hasta que no haya cambios.
#
# Se mantiene LIGERA a proposito: reduce el espacio de busqueda pero NO
# resuelve el Sudoku por si sola en los casos medio/dificil, de modo que
# el trabajo real lo siga haciendo el ACO (que es lo que queremos mostrar).

def constraint_propagation(board):
    """
    Devuelve (nuevo_tablero, n_fijadas) tras aplicar 'naked singles'
    de forma repetida. No modifica la lista original.
    """
    board = list(board)
    n_fixed = 0
    changed = True
    while changed:
        changed = False
        for idx in range(CELLS):
            if board[idx] != 0:
                continue
            # Digitos que YA usan sus vecinos
            used = set(board[p] for p in PEERS[idx] if board[p] != 0)
            candidates = [d for d in range(1, N + 1) if d not in used]
            if len(candidates) == 1:          # valor forzoso
                board[idx] = candidates[0]
                n_fixed += 1
                changed = True
    return board, n_fixed


# 4. NUCLEO ACO  (encoding de permutacion por bloque)


class AntColonySudoku:
    """
    Resuelve un Sudoku con ACO usando nuestra solución.

    Parametros principales:
        n_ants       : numero de hormigas por iteracion (tamano de colonia)
        alpha        : peso de la feromona en la regla de transicion
        beta         : peso de la heuristica en la regla de transicion
        rho          : tasa de evaporacion de feromona (0..1)
        q            : cantidad base de feromona depositada
        max_iter     : maximo de iteraciones por intento
        stagnation   : iteraciones sin mejora antes de reiniciar feromona
        ls_steps     : presupuesto de pasos de busqueda local por hormiga
        use_cp       : aplicar propagacion de restricciones al inicio
    """

    def __init__(self, puzzle_text, n_ants=12, alpha=1.0, beta=3.0, rho=0.15,
                 q=1.0, max_iter=400, stagnation=40, ls_steps=60,
                 use_cp=True, tau_min=0.05, tau_max=10.0, tau0=1.0,
                 adaptive=False):
        # ---- Lectura y validacion del puzzle ----
        self.original = parse_puzzle(puzzle_text)
        if not givens_are_valid(self.original):
            raise ValueError("El Sudoku de entrada es invalido: las pistas "
                             "ya repiten un digito en una fila/columna/bloque.")

        # ---- Preprocesamiento: propagacion de restricciones ----
        self.use_cp = use_cp
        if use_cp:
            self.fixed_board, self.n_fixed_by_cp = constraint_propagation(self.original)
        else:
            self.fixed_board, self.n_fixed_by_cp = list(self.original), 0

        # 'fixed' marca las celdas que NO se pueden cambiar (pistas + deducidas)
        self.fixed = [v != 0 for v in self.fixed_board]

        # ---- Estructura por bloque: celdas libres y digitos que faltan ----
        # Para cada bloque guardamos:
        #   free_cells[b]    -> lista de indices de celda libres del bloque b
        #   missing[b]       -> lista de digitos que faltan por colocar en b
        self.free_cells = []
        self.missing = []
        for b in range(N):
            present = set(self.fixed_board[idx] for idx in BLOCKS[b] if self.fixed_board[idx] != 0)
            self.free_cells.append([idx for idx in BLOCKS[b] if self.fixed_board[idx] == 0])
            self.missing.append([d for d in range(1, N + 1) if d not in present])

        # ---- Parametros del algoritmo ----
        self.n_ants = n_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        self.max_iter = max_iter
        self.stagnation = stagnation
        self.ls_steps = ls_steps
        self.tau_min = tau_min
        self.tau_max = tau_max
        self.tau0 = tau0

        # ---- Auto-adaptacion de parametros (beta y rho) ----
        # Si adaptive=True, beta y rho varian entre estos conjuntos discretos
        # segun haya o no mejora (casos de exito), como pide el documento.
        self.adaptive = adaptive
        self.beta_set = [2.0, 3.0, 5.0]    # peso de la heuristica
        self.rho_set = [0.10, 0.15, 0.30]  # tasa de evaporacion
        self._bi = self.beta_set.index(beta) if beta in self.beta_set else 1
        self._ri = self.rho_set.index(rho) if rho in self.rho_set else 1

        # ---- Matriz de feromona  tau[celda][digito]  (digito 1..9) ----
        # Indice 0 de cada celda no se usa; simplifica el acceso por digito.
        self._init_pheromone()

    # ----------------------------------------------------------------
    def _adapt_params(self, improved):
        """
        Auto-adaptacion segun los casos de exito:
          - Si MEJORA (exito): explotar -> sube beta (mas codicioso), baja rho.
          - Si NO mejora (estancamiento): explorar -> baja beta, sube rho
            (mas evaporacion = mas olvido = mas diversidad).
        """
        if improved:
            self._bi = min(len(self.beta_set) - 1, self._bi + 1)
            self._ri = max(0, self._ri - 1)
        else:
            self._bi = max(0, self._bi - 1)
            self._ri = min(len(self.rho_set) - 1, self._ri + 1)
        self.beta = self.beta_set[self._bi]
        self.rho = self.rho_set[self._ri]

    # ----------------------------------------------------------------
    def _init_pheromone(self):
        """Inicializa toda la feromona al valor tau0."""
        self.tau = [[self.tau0] * (N + 1) for _ in range(CELLS)]

    # ----------------------------------------------------------------
    def _heuristic(self, board, idx, digit):
        """
        Heuristica eta(celda, digito) = 1 / (1 + conflictos_inmediatos),
        donde 'conflictos_inmediatos' = cuantos vecinos YA colocados de la
        fila y la columna contienen ese digito. Cuantos menos choques cree
        el digito, mas atractivo es.
        (Solo miramos fila y columna: el bloque se respeta por construccion.)
        """
        r, c = idx // N, idx % N
        conflicts = 0
        for cc in range(N):
            if board[r * N + cc] == digit:
                conflicts += 1
        for rr in range(N):
            if board[rr * N + c] == digit:
                conflicts += 1
        return 1.0 / (1.0 + conflicts)

    # ----------------------------------------------------------------
    def _construct_solution(self):
        """
        Una hormiga construye un tablero COMPLETO.

        Recorre los bloques en orden aleatorio (diversidad) y, dentro de
        cada bloque, asigna los digitos faltantes a las celdas libres. Para
        cada celda elige un digito (de los que aun no uso en ese bloque) con
        probabilidad proporcional a  tau^alpha * eta^beta  -> regla de
        transicion del ACO. El resultado siempre es un tablero donde cada
        bloque es una permutacion valida de 1..9.

        Devuelve (board, assignments) con assignments = [(celda, digito), ...]
        de todas las celdas libres (sirve para depositar feromona luego).
        """
        board = list(self.fixed_board)
        assignments = []

        block_order = list(range(N))
        random.shuffle(block_order)

        for b in block_order:
            free = list(self.free_cells[b])
            random.shuffle(free)                 # orden aleatorio de celdas
            remaining = list(self.missing[b])    # digitos por colocar en el bloque

            for idx in free:
                # Construimos los pesos tau^alpha * eta^beta para cada digito posible
                weights = []
                for d in remaining:
                    tau = self.tau[idx][d] ** self.alpha
                    eta = self._heuristic(board, idx, d) ** self.beta
                    weights.append(tau * eta)

                total = sum(weights)
                if total <= 0.0:
                    # Caso degenerado (no deberia ocurrir): elige al azar
                    choice = random.randrange(len(remaining))
                else:
                    # Seleccion por ruleta (probabilidad proporcional al peso)
                    r = random.random() * total
                    acc = 0.0
                    choice = len(remaining) - 1
                    for i, w in enumerate(weights):
                        acc += w
                        if acc >= r:
                            choice = i
                            break

                digit = remaining.pop(choice)
                board[idx] = digit
                assignments.append((idx, digit))

        return board, assignments

    # ----------------------------------------------------------------
    def _local_search(self, board):
        """
        Busqueda local por INTERCAMBIO DENTRO DE BLOQUE.

        Repite: busca, dentro de algun bloque, un par de celdas libres cuyo
        intercambio de valores reduzca el numero total de errores. Como
        ambas celdas pertenecen al mismo bloque, este sigue siendo una
        permutacion valida tras el intercambio. Es un "ascenso de colina":
        solo aceptamos intercambios que mejoran. Se detiene cuando no hay
        mejora posible o se agota el presupuesto de pasos.

        Modifica 'board' en el sitio y devuelve su coste final.
        """
        cost = count_conflicts(board)
        steps = 0
        improved = True
        while improved and steps < self.ls_steps and cost > 0:
            improved = False
            for b in range(N):
                free = self.free_cells[b]
                # Probar todos los pares de celdas libres del bloque
                for i in range(len(free)):
                    for j in range(i + 1, len(free)):
                        a, c = free[i], free[j]
                        board[a], board[c] = board[c], board[a]   # intercambio
                        new_cost = count_conflicts(board)
                        if new_cost < cost:                       # mejora -> aceptar
                            cost = new_cost
                            improved = True
                            steps += 1
                        else:
                            board[a], board[c] = board[c], board[a]  # deshacer
                        if cost == 0 or steps >= self.ls_steps:
                            return cost
        return cost

    # ----------------------------------------------------------------
    def _evaporate(self):
        """Evapora la feromona de todas las celdas libres: tau *= (1 - rho)."""
        keep = 1.0 - self.rho
        for b in range(N):
            for idx in self.free_cells[b]:
                row = self.tau[idx]
                for d in range(1, N + 1):
                    row[d] *= keep
                    if row[d] < self.tau_min:   # cota inferior (estilo MMAS)
                        row[d] = self.tau_min

    def _deposit(self, assignments, cost):
        """
        Deposita feromona en las asignaciones (celda, digito) de una buena
        solucion. Cuanto menor es el coste, mas feromona se deposita.
        """
        amount = self.q / (1.0 + cost)
        for (idx, digit) in assignments:
            self.tau[idx][digit] += amount
            if self.tau[idx][digit] > self.tau_max:   # cota superior (MMAS)
                self.tau[idx][digit] = self.tau_max

    # ----------------------------------------------------------------
    def solve(self, max_restarts=20, time_limit=20.0, verbose=False):
        """
        Bucle principal del ACO.

        En cada iteracion: cada hormiga construye una solucion, se le aplica
        busqueda local, se elige la mejor de la iteracion, se evapora la
        feromona y se refuerza la mejor. Si pasan muchas iteraciones sin
        mejorar (estancamiento), se reinicia la feromona. Termina al
        encontrar una solucion (coste 0), agotar los reinicios o el tiempo.

        Devuelve un diccionario con la solucion y estadisticas utiles.
        """
        start = time.time()
        best_board = list(self.fixed_board)
        best_cost = count_conflicts(best_board) if all(self.fixed_board) else float("inf")

        total_iters = 0
        no_improve = 0
        window_improved = False   # ¿hubo mejora en la ventana de auto-adaptacion?
        history = []              # mejor coste por iteracion (para graficar convergencia)
        self._history = history

        for restart in range(max_restarts + 1):
            if restart > 0:
                self._init_pheromone()      # reiniciar feromona
                no_improve = 0
                if verbose:
                    print("  [reinicio %d] feromona reiniciada (mejor coste = %d)"
                          % (restart, best_cost))

            for it in range(self.max_iter):
                total_iters += 1

                # --- Cada hormiga construye + busqueda local ---
                iter_best_board, iter_best_cost, iter_best_assign = None, float("inf"), None
                for _ in range(self.n_ants):
                    board, assignments = self._construct_solution()
                    cost = self._local_search(board)
                    if cost < iter_best_cost:
                        iter_best_board = board
                        iter_best_cost = cost
                        iter_best_assign = assignments

                # --- Actualizar mejor global ---
                if iter_best_cost < best_cost:
                    best_cost = iter_best_cost
                    best_board = list(iter_best_board)
                    no_improve = 0
                    window_improved = True
                else:
                    no_improve += 1

                # --- Actualizacion de feromona (evaporar + reforzar mejor) ---
                self._evaporate()
                # Las asignaciones reflejan el tablero TRAS la busqueda local
                final_assign = [(idx, iter_best_board[idx])
                                for b in range(N) for idx in self.free_cells[b]]
                self._deposit(final_assign, iter_best_cost)

                if verbose and total_iters % 10 == 0:
                    print("  iter %4d | mejor coste global = %d | coste iter = %d"
                          % (total_iters, best_cost, iter_best_cost))

                # --- Auto-adaptacion de parametros (cada 15 iteraciones) ---
                if self.adaptive and total_iters % 15 == 0:
                    self._adapt_params(window_improved)
                    window_improved = False

                history.append(best_cost)   # registrar convergencia

                # --- Condiciones de parada ---
                if best_cost == 0:
                    return self._result(best_board, best_cost, total_iters,
                                        restart, start)
                if time.time() - start > time_limit:
                    return self._result(best_board, best_cost, total_iters,
                                        restart, start, timed_out=True)
                if no_improve >= self.stagnation:
                    break   # estancado -> reiniciar feromona

        return self._result(best_board, best_cost, total_iters, max_restarts, start)

    # ----------------------------------------------------------------
    def _result(self, board, cost, iters, restarts, start, timed_out=False):
        """Empaqueta el resultado y las estadisticas en un diccionario."""
        return {
            "board": board,
            "solved": cost == 0 and is_valid_solution(board),
            "cost": cost,
            "iterations": iters,
            "restarts": restarts,
            "time": time.time() - start,
            "fixed_by_cp": self.n_fixed_by_cp,
            "timed_out": timed_out,
            "history": getattr(self, "_history", []),
        }


# 5. SUDOKUS DE EJEMPLO  (0 o '.' = celda vacia)

# Todas las instancias son Sudokus VALIDOS y de SOLUCION UNICA (verificado con
# un backtracking que cuenta soluciones). El difícil exige trabajo real al ACO;
# el "extremo" es un caso conocido como muy duro para metaheuristicos (ver guia).
PUZZLES = {
    # Facil: muchas pistas; la propagacion de restricciones suele resolverlo solo.
    "facil":
        "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79",
    # Medio: la propagacion lo completa; ideal para mostrar ACO puro con --no-cp.
    "medio":
        "...26.7.168..7..9.19...45..82.1...4...46.29...5...3.28..93...74.4..5..367.3.18...",
    # Dificil: la propagacion fija parte y el ACO resuelve el resto (pipeline completo).
    "dificil":
        "030600012602095308098040000009700000406003000700024000061507000280419600000280070",
    # Extremo: instancia muy dura (estilo "world's hardest"). El ACO NO la resuelve
    # de forma fiable: sirve para discutir limitaciones y trabajo a futuro.
    "extremo":
        "8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..",
}


# 6. DEMOSTRACION / PROGRAMA PRINCIPAL

def run_demo(puzzle_text, name="", seed=None, verbose=False, **params):
    """Resuelve un sudoku y muestra el proceso y el resultado de forma clara."""
    if seed is not None:
        random.seed(seed)

    print("=" * 56)
    print(" SOLVER DE SUDOKU CON ACO (permutacion por bloque)")
    if name:
        print(" Instancia: %s" % name)
    if seed is not None:
        print(" Semilla  : %d" % seed)
    print("=" * 56)

    solver = AntColonySudoku(puzzle_text, **params)

    print_board(solver.original, "\nTABLERO INICIAL:")
    print("\nPistas iniciales         : %d" % sum(1 for v in solver.original if v != 0))
    print("Celdas fijadas por CP    : %d" % solver.n_fixed_by_cp)
    print("Celdas a resolver por ACO: %d"
          % sum(len(fc) for fc in solver.free_cells))
    print("\nResolviendo con ACO...\n")

    result = solver.solve(verbose=verbose)

    print_board(result["board"], "\nRESULTADO:")
    print("\n--- ESTADISTICAS ---")
    print("Resuelto        : %s" % ("SI" if result["solved"] else "NO"))
    print("Conflictos final: %d" % result["cost"])
    print("Iteraciones     : %d" % result["iterations"])
    print("Reinicios       : %d" % result["restarts"])
    print("Tiempo (s)      : %.3f" % result["time"])
    if result["solved"]:
        print("\nVerificacion: la solucion cumple TODAS las reglas del Sudoku. [OK]")
    else:
        print("\nNo se alcanzo una solucion completa (prueba otra semilla o sube max_iter).")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Solver de Sudoku mediante ACO (Ant Colony Optimization).")
    parser.add_argument("--puzzle", default="dificil",
                        choices=list(PUZZLES.keys()),
                        help="Sudoku de ejemplo: facil|medio|dificil|extremo "
                             "(por defecto: dificil).")
    parser.add_argument("--input", default=None,
                        help="Sudoku propio: 81 caracteres (usa 0 o . para vacias).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Semilla para reproducibilidad.")
    parser.add_argument("--verbose", action="store_true",
                        help="Muestra el progreso por iteraciones.")
    parser.add_argument("--ants", type=int, default=12, help="Numero de hormigas.")
    parser.add_argument("--no-cp", action="store_true",
                        help="Desactiva la propagacion de restricciones "
                             "(las hormigas resuelven todo el tablero).")
    parser.add_argument("--no-ls", action="store_true",
                        help="Desactiva la busqueda local (ACO puro: solo "
                             "feromona + heuristica). Util para ver la "
                             "convergencia por iteraciones con --verbose.")
    parser.add_argument("--adaptive", action="store_true",
                        help="Activa la auto-adaptacion de parametros (beta, rho) "
                             "segun los casos de exito.")
    args = parser.parse_args()

    if args.input is not None:
        puzzle_text, name = args.input, "personalizada"
    else:
        puzzle_text, name = PUZZLES[args.puzzle], args.puzzle

    try:
        run_demo(puzzle_text, name=name, seed=args.seed, verbose=args.verbose,
                 n_ants=args.ants, use_cp=not args.no_cp,
                 ls_steps=(0 if args.no_ls else 60), adaptive=args.adaptive)
    except ValueError as e:
        # Entrada invalida (longitud != 81, caracteres raros o pistas que ya
        # violan las reglas): mensaje claro en vez de un traceback.
        print("\n[ERROR] Sudoku invalido: %s" % e)


if __name__ == "__main__":
    main()
