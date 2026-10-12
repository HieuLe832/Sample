# Bloxorz Solver

A playable Bloxorz game with a GUI, and four search-based solvers: BFS, DFS,
UCS and A\*. Project 1 of CSC14003, Introduction to Artificial Intelligence.

## Setup

Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`pygame-ce` is the maintained fork of pygame and installs on current Python
versions; the code only uses API that the original `pygame` also provides.

## Run

```bash
python main.py                          # open the game
python main.py --level 5                # open the game on stage 5
python main.py --level my_stage.json    # open the game on your own stage
python main.py --list                   # list the bundled stages
python main.py --solve all --level 13   # run the solvers in the terminal
python main.py --solve astar --level 14 --heuristic relaxed --cost unit
```

### Controls

| Key | Action |
| --- | --- |
| Arrow keys / WASD | Roll the block (or the controlled cube) |
| Space | Switch control to the other cube while split |
| R / N | Restart the stage / New Game (back to stage 1) |
| `[` `]` or PageUp / PageDown | Previous / next stage |
| 1 2 3 4 | Solve with BFS / DFS / UCS / A\* from the current position |
| P, `.`, `-`, `+` | Play or pause the replay, single step, slower, faster |
| Enter | Next stage, after winning |
| Esc | Quit |

Every action also has a button in the side panel. A solver runs from the
current position, shows its measurements, and replays the moves it found.
Rolling off the board, over a closed bridge, or standing up on a fragile tile
loses the stage.

## Tests and experiments

```bash
python -m unittest                        # 70 tests, no extra dependencies
python experiments/run_experiments.py     # writes experiments/results/
```

The experiment script runs the five solver configurations on every bundled
stage and writes `results.csv`, `results.md` (one table per metric) and one
chart per metric. Timings depend on the machine; rerun it before quoting them.

## Layout

```text
main.py                  entry point: GUI, or --solve in the terminal
bloxorz/
  level.py               tiles, bridges, switches, JSON stage loader
  game.py                state, orientation transition table, move()
  problem.py             search problem: successors and cost functions
  heuristics.py          A* heuristics
  solvers/               bfs.py, dfs.py, ucs.py, astar.py, and solve()
  gui.py                 pygame front end
levels/                  14 stages in four groups
experiments/             experiment runner and its results
tests/                   unit tests
```

## Stage format

A stage is a JSON file; the same file is used by the game and by every solver.

```json
{
  "name": "Two Bridges",
  "group": "switches",
  "grid": [
    "####...####...####",
    "#S##aa##2##bb###G#",
    "#1##...####...####"
  ],
  "bridges": {"a": "closed", "b": "open"},
  "switches": {
    "1": {"type": "soft", "effects": {"a": "toggle", "b": "toggle"}},
    "2": {"type": "heavy", "effects": {"b": "open"}}
  }
}
```

| Character | Meaning |
| --- | --- |
| `.` or space | void |
| `#` | floor |
| `S` | start (the block stands here) |
| `G` | goal hole |
| `F` | fragile tile |
| `a`-`z` | tile of the bridge with that letter |
| `0`-`9` | switch with that digit |

- Bridge state is `"open"` or `"closed"` (default closed).
- Switch `type` is `soft`, `heavy` or `split`.
- Soft and heavy switches list `effects` per bridge: `toggle`, or the permanent
  `open` / `close`.
- A split switch lists the two `targets` as `[row, column]`, counted from 0.

The bundled stages were designed for this project, except stage 1, which uses
the layout of the first stage of the original game. Groups: `basic` (1-3),
`fragile` (4-6), `switches` (7-10), `combined` (11-14).

## Design notes

These are the decisions the report has to explain.

### Search problem

- **State**: `(a, b, split, bridges)`. `a` and `b` are the cells of the two
  halves: equal when standing, side by side when lying. While split, `a` is the
  cube under control. `bridges` is a bitmask with one bit per bridge, so two
  states with the same block placement and different bridges are different.
- **Actions**: Up, Down, Left, Right, plus Swap (change cube) while split.
- **Transition model**: `game.move`. Roll using `ROLL_TABLE`, reject the move if
  a cell is unsupported or the block stands on a fragile tile, apply the
  switches under the block, check support again (a switch may have closed a
  bridge under the block), then merge cubes that are adjacent.
- **Goal test**: the whole block standing on the goal hole.
- **Repeated states**: states are hashable tuples; every solver keeps a
  dictionary of reached states that doubles as the parent map.
- **Solution length** is the number of actions, Swap included.

Rules the assignment leaves open, and what this implementation does: a cube may
rest on a fragile tile and on the goal hole (it is light, and it cannot finish
the stage); a switch fires each time a roll ends on it; a move that drops any
part of the block is illegal, including the cube that is not being moved.

### Cost function (UCS and A\*)

`cost = 1 + 2 x (fragile tiles the moved piece lands on)`; a Swap costs 1.

Fragile tiles are where a single wrong roll loses the stage, so a careful
player accepts a detour of up to two extra moves per fragile tile avoided. With
this cost UCS is no longer BFS: on stage 5, BFS crosses the fragile tiles in 6
moves (cost 14) while UCS goes around them in 10 moves (cost 10). `--cost unit`
switches to cost 1 per action.

### DFS

Plain depth-first graph search with a visited set, not IDS. It is iterative
(an explicit stack of successor iterators) to avoid Python's recursion limit.

### Heuristics

Both are admissible for any cost function whose cheapest action costs at least
1; the unit tests check this against the true cost on every reachable state of
every bundled stage.

- **`manhattan`** (default): `ceil(d / 2)`, where `d` is the Manhattan distance
  from the goal to the farther half of the block. After a roll, every cell of
  the block is at most 2 cells from where any cell was, so `d` drops by at
  most 2 per roll. A lying block has `d >= 1`, which covers the extra roll
  needed to stand up. A split switch teleports the block, so the estimate is
  the minimum of that value and "rolls to stand on a split switch + moves the
  cubes then need to meet". While split, it is the Manhattan distance between
  the cubes. With split switches it is admissible but not always consistent;
  A\* re-queues a state when it finds a cheaper path, so the result is still
  optimal.
- **`relaxed`**: the exact cost to the goal in the same stage with every bridge
  open, found once by Dijkstra's algorithm backwards from the goal. Every real
  move is also a move in the relaxed stage at the same cost, which makes the
  heuristic admissible and consistent. It expands far fewer nodes, but building
  the table costs time and memory, and that cost is included in its
  measurements.

### Measurements

`solvers.solve` records search time (best of `repeats` runs, `perf_counter`),
peak memory (a separate run under `tracemalloc`, because tracing slows the
search), expanded nodes, generated nodes, the largest frontier, solution
length and path cost.
