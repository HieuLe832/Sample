# Experiment results

Cost function: **risk-aware** (roll 1, swap 1, +2 per fragile tile landed on). Search time is the best of 7 runs; peak memory is measured in a separate run with `tracemalloc`. A* times and memory include building the heuristic.

## Test set

| # | Stage | Group | Size | Bridges | Switches | Reachable states |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | First Steps | basic | 6 x 10 | 0 | 0 | 89 |
| 2 | Narrow Paths | basic | 8 x 14 | 0 | 0 | 95 |
| 3 | Open Field | basic | 10 x 14 | 0 | 0 | 290 |
| 4 | Thin Ice | fragile | 3 x 10 | 0 | 0 | 62 |
| 5 | Risky Shortcut | fragile | 4 x 10 | 0 | 0 | 81 |
| 6 | Orange Maze | fragile | 8 x 12 | 0 | 0 | 145 |
| 7 | Drawbridge | switches | 7 x 12 | 1 | 1 | 121 |
| 8 | Heavy Duty | switches | 3 x 12 | 1 | 1 | 110 |
| 9 | Two Bridges | switches | 3 x 18 | 2 | 2 | 223 |
| 10 | Clockwork | switches | 4 x 25 | 3 | 3 | 432 |
| 11 | Twins | combined | 4 x 14 | 0 | 1 | 393 |
| 12 | Teamwork | combined | 5 x 14 | 1 | 2 | 2,023 |
| 13 | Grand Tour | combined | 5 x 22 | 2 | 3 | 324 |
| 14 | Archipelago | combined | 5 x 20 | 3 | 3 | 7,359 |

## Search time (ms)

| # | Stage | BFS | DFS | UCS | A* (manhattan) | A* (relaxed) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | First Steps | 0.373 | 0.517 | 0.504 | 0.184 | 0.764 |
| 2 | Narrow Paths | 0.633 | 0.477 | 0.620 | 0.655 | 0.879 |
| 3 | Open Field | 1.434 | 2.298 | 1.616 | 0.961 | 2.417 |
| 4 | Thin Ice | 0.472 | 0.485 | 0.476 | 0.501 | 0.595 |
| 5 | Risky Shortcut | 0.331 | 0.606 | 0.589 | 0.351 | 0.705 |
| 6 | Orange Maze | 0.956 | 0.810 | 0.983 | 0.970 | 1.241 |
| 7 | Drawbridge | 0.807 | 0.803 | 0.834 | 0.814 | 0.926 |
| 8 | Heavy Duty | 0.712 | 0.591 | 0.753 | 0.684 | 0.952 |
| 9 | Two Bridges | 1.574 | 1.580 | 1.664 | 1.220 | 1.602 |
| 10 | Clockwork | 2.567 | 3.045 | 2.764 | 1.314 | 1.874 |
| 11 | Twins | 1.583 | 0.364 | 1.735 | 0.331 | 3.225 |
| 12 | Teamwork | 8.709 | 1.266 | 10.719 | 3.647 | 15.458 |
| 13 | Grand Tour | 1.529 | 1.394 | 1.736 | 0.776 | 1.964 |
| 14 | Archipelago | 33.071 | 28.943 | 37.343 | 11.526 | 40.092 |

## Peak memory (KiB)

| # | Stage | BFS | DFS | UCS | A* (manhattan) | A* (relaxed) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | First Steps | 10.1 | 19.7 | 12.1 | 7.1 | 23.6 |
| 2 | Narrow Paths | 15.6 | 17.1 | 19.0 | 19.8 | 24.4 |
| 3 | Open Field | 29.9 | 85.8 | 38.3 | 24.4 | 69.5 |
| 4 | Thin Ice | 9.2 | 16.3 | 10.6 | 11.4 | 13.7 |
| 5 | Risky Shortcut | 8.8 | 16.4 | 12.2 | 11.2 | 16.3 |
| 6 | Orange Maze | 18.5 | 30.3 | 21.7 | 22.0 | 33.1 |
| 7 | Drawbridge | 16.8 | 26.6 | 20.2 | 20.6 | 19.7 |
| 8 | Heavy Duty | 15.7 | 17.0 | 19.2 | 20.1 | 19.5 |
| 9 | Two Bridges | 30.5 | 56.0 | 38.2 | 25.3 | 34.0 |
| 10 | Clockwork | 57.9 | 99.5 | 75.1 | 39.0 | 51.6 |
| 11 | Twins | 39.2 | 13.6 | 47.2 | 11.2 | 113.2 |
| 12 | Teamwork | 241.1 | 53.7 | 320.3 | 100.5 | 987.1 |
| 13 | Grand Tour | 33.3 | 44.3 | 42.3 | 21.5 | 60.3 |
| 14 | Archipelago | 927.1 | 3089.7 | 1125.6 | 453.6 | 2634.3 |

## Expanded nodes

| # | Stage | BFS | DFS | UCS | A* (manhattan) | A* (relaxed) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | First Steps | 48 | 56 | 64 | 20 | 7 |
| 2 | Narrow Paths | 84 | 53 | 87 | 85 | 25 |
| 3 | Open Field | 185 | 251 | 203 | 109 | 15 |
| 4 | Thin Ice | 57 | 52 | 61 | 60 | 15 |
| 5 | Risky Shortcut | 42 | 76 | 77 | 41 | 10 |
| 6 | Orange Maze | 126 | 88 | 128 | 118 | 17 |
| 7 | Drawbridge | 110 | 100 | 114 | 102 | 36 |
| 8 | Heavy Duty | 92 | 69 | 99 | 84 | 47 |
| 9 | Two Bridges | 210 | 186 | 219 | 151 | 103 |
| 10 | Clockwork | 333 | 337 | 348 | 153 | 50 |
| 11 | Twins | 216 | 44 | 226 | 39 | 17 |
| 12 | Teamwork | 1,211 | 137 | 1,392 | 444 | 50 |
| 13 | Grand Tour | 206 | 165 | 233 | 91 | 36 |
| 14 | Archipelago | 4,560 | 3,347 | 4,780 | 1,305 | 196 |

## Solution length (moves)

| # | Stage | BFS | DFS | UCS | A* (manhattan) | A* (relaxed) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | First Steps | 7 | 45 | 7 | 7 | 7 |
| 2 | Narrow Paths | 25 | 45 | 25 | 25 | 25 |
| 3 | Open Field | 15 | 191 | 15 | 15 | 15 |
| 4 | Thin Ice | 15 | 35 | 15 | 15 | 15 |
| 5 | Risky Shortcut | 6 | 19 | 10 | 10 | 10 |
| 6 | Orange Maze | 17 | 75 | 17 | 17 | 17 |
| 7 | Drawbridge | 21 | 41 | 21 | 21 | 21 |
| 8 | Heavy Duty | 20 | 36 | 20 | 20 | 20 |
| 9 | Two Bridges | 26 | 104 | 26 | 26 | 26 |
| 10 | Clockwork | 19 | 220 | 19 | 19 | 19 |
| 11 | Twins | 17 | 23 | 17 | 17 | 17 |
| 12 | Teamwork | 17 | 121 | 17 | 17 | 17 |
| 13 | Grand Tour | 24 | 94 | 25 | 25 | 25 |
| 14 | Archipelago | 34 | 2,915 | 36 | 36 | 36 |

## Path cost

| # | Stage | BFS | DFS | UCS | A* (manhattan) | A* (relaxed) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | First Steps | 7 | 45 | 7 | 7 | 7 |
| 2 | Narrow Paths | 25 | 45 | 25 | 25 | 25 |
| 3 | Open Field | 15 | 191 | 15 | 15 | 15 |
| 4 | Thin Ice | 39 | 71 | 39 | 39 | 39 |
| 5 | Risky Shortcut | 14 | 23 | 10 | 10 | 10 |
| 6 | Orange Maze | 31 | 119 | 29 | 29 | 29 |
| 7 | Drawbridge | 21 | 41 | 21 | 21 | 21 |
| 8 | Heavy Duty | 20 | 36 | 20 | 20 | 20 |
| 9 | Two Bridges | 26 | 104 | 26 | 26 | 26 |
| 10 | Clockwork | 19 | 220 | 19 | 19 | 19 |
| 11 | Twins | 17 | 31 | 17 | 17 | 17 |
| 12 | Teamwork | 21 | 149 | 21 | 21 | 21 |
| 13 | Grand Tour | 40 | 148 | 33 | 33 | 33 |
| 14 | Archipelago | 40 | 3,205 | 36 | 36 | 36 |
