# Sudoku con ACO (Ant Colony Optimization)

Solver de **Sudoku** mediante **optimización por colonia de hormigas (ACO)**, un
algoritmo bioinspirado. Proyecto final de la unidad de aprendizaje *Algoritmos
Bioinspirados* (Ing. en Inteligencia Artificial).

La idea central del diseño es el **encoding por permutación de bloque**: cada bloque
3×3 se construye como una permutación de {1..9}, de modo que la restricción de
bloque se cumple *por construcción* y el algoritmo solo minimiza los conflictos
(dígitos repetidos) en filas y columnas. Implementación **propia**; el paper de
Lloyd & Amos se usó solo como referencia conceptual.

---

## Requisitos
- **Python 3.8+** (probado en 3.13).
- El solver `sudoku_aco.py` y `genetic_sudoku.py` **no** requieren dependencias externas.
- Solo para generar las gráficas (`comparacion.py`): `matplotlib` y `numpy`:

Comprueba tu versión:
```bash
python --version
```

---

## Cómo ejecutar

Desde la carpeta del proyecto:

```bash
# Resuelve el sudoku "dificil" por defecto (propagación de restricciones + ACO)
python sudoku_aco.py

# Elegir instancia: facil | medio | dificil | extremo
python sudoku_aco.py --puzzle medio

# ACO puro (sin propagación ni búsqueda local): se ve la convergencia por feromona
python sudoku_aco.py --no-cp --no-ls --verbose

# Reproducible con semilla fija
python sudoku_aco.py --puzzle dificil --seed 7

# Resolver un sudoku propio (81 caracteres; usa 0 o . para celdas vacías)
python sudoku_aco.py --input "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79"
```

### Opciones de línea de comandos

| Opción | Descripción | Por defecto |
|---|---|---|
| `--puzzle` | Instancia de ejemplo: `facil`, `medio`, `dificil`, `extremo` | `dificil` |
| `--input`  | Sudoku propio como cadena de 81 caracteres (`0` o `.` = vacío) | — |
| `--seed`   | Semilla del generador aleatorio (reproducibilidad) | aleatoria |
| `--verbose`| Muestra el progreso (mejor coste) por iteraciones | desactivado |
| `--ants`   | Número de hormigas por iteración | 12 |
| `--no-cp`  | Desactiva la propagación de restricciones | activada |
| `--no-ls`  | Desactiva la búsqueda local (ACO puro) | activada |
| `--adaptive` | Auto-adaptación de parámetros (β, ρ) según éxito | desactivado |

### Algoritmo de comparación y experimentos (fase 2)

```bash
# Resolver con el Algoritmo Genético (mismo encoding); --adaptive ajusta cruza/mutación
python genetic_sudoku.py --puzzle dificil --adaptive --verbose

# Comparación ACO vs GA (30 corridas) + genera las gráficas en figuras/
python comparacion.py
```

---

## Estructura del proyecto

```
sudoku_aco/
├── sudoku_aco.py       # Solver ACO (comentado función por función)
├── genetic_sudoku.py   # Algoritmo Genético de comparación (mismo encoding)
├── comparacion.py      # 30 corridas ACO vs GA + genera las gráficas
├── experimentos.py     # Métricas y sensibilidad de parámetros
├── figuras/            # Gráficas generadas (convergencia, éxito, tiempos, parámetros)
└── README.md           # Este archivo
```

El archivo `sudoku_aco.py` está organizado en secciones numeradas:

1. Constantes y mapas de índices del tablero
2. Utilidades de tablero (parseo, impresión, conflictos, validación)
3. Propagación de restricciones (preprocesamiento)
4. Núcleo ACO (clase `AntColonySudoku`)
5. Sudokus de ejemplo
6. Demostración / programa principal

---

## ¿Cómo funciona? (resumen)

1. **Propagación de restricciones** (opcional): fija celdas forzosas (*naked singles*).
2. **Construcción (hormigas)**: cada hormiga rellena cada bloque 3×3 como una
   permutación, eligiendo dígitos con probabilidad ∝ `τ^α · η^β`, donde `τ` es la
   feromona y `η = 1/(1+conflictos)` la heurística.
3. **Búsqueda local** (opcional): intercambia dos celdas no fijas dentro de un
   bloque si reduce los conflictos (el bloque sigue siendo válido).
4. **Actualización de feromona**: se evapora (`τ *= 1-ρ`) y se refuerza la mejor
   solución de la iteración.
5. **Reinicios** ante estancamiento. Termina cuando los conflictos llegan a 0.

---

## Pruebas y fiabilidad

Cada instancia de ejemplo es un Sudoku **válido y de solución única** (verificado
con un backtracking que cuenta soluciones). Medición de la **tasa de éxito** sobre
múltiples semillas independientes (igual que pide el proyecto: 30 corridas con
distinta semilla en el artículo):

| Instancia | Configuración | Éxito | Iteraciones medias | Tiempo máx |
|---|---|---|---|---|
| facil   | ACO puro (`--no-cp --no-ls`) | 30/30 | ≈37 | 0.32 s |
| medio   | ACO puro (`--no-cp --no-ls`) | 30/30 | ≈14 | 0.04 s |
| dificil | propagación + ACO (por defecto) | 30/30 | ≈6 | 0.68 s |
| dificil | ACO puro (`--no-ls`) | 30/30 | ≈52 | 0.30 s |
| extremo | cualquiera | 0/30 | — | no resuelto |

> Medido sobre 30 semillas independientes (`random.seed(0..29)`), límite 15 s/intento.

**Conclusión:** el ACO resuelve por sí solo (incluso sin búsqueda local) los niveles
fácil/medio/difícil de forma fiable. La instancia `extremo` (estilo *world's
hardest*, 21 pistas) **no** se resuelve de forma fiable: es una limitación conocida
de los metaheurísticos por óptimos locales, y se discute como **trabajo a futuro**.

> Reproducir el experimento: las funciones del módulo permiten medir tasas de éxito
> creando `AntColonySudoku(puzzle, ...)` y llamando a `.solve()` con distintas
> semillas (`random.seed(i)`).

## Limitaciones y trabajo a futuro

- Instancias extremadamente difíciles (p. ej. *world's hardest*) pueden no
  resolverse por estancamiento en óptimos locales.
- Mejoras posibles: propagación de restricciones más fuerte (*hidden singles*,
  *naked pairs*), búsqueda local con aceptación tipo recocido simulado, listas
  tabú, y **auto-adaptación en línea de parámetros** (α, β, ρ) según casos de éxito
  (requisito del artículo final).
