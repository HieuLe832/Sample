"""Bloxorz Solver: entry point.

    python main.py                         play in the GUI
    python main.py --level 5               open the GUI on stage 5
    python main.py --level my_stage.json   open the GUI on a custom stage
    python main.py --solve astar --level 5 solve in the terminal, no GUI
    python main.py --list                  list the bundled stages
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bloxorz.heuristics import HEURISTICS
from bloxorz.level import LEVELS_DIR, Level, LevelError, load_level, load_levels
from bloxorz.problem import COST_MODELS
from bloxorz.solvers import ALGORITHMS, solve


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bloxorz game and solvers.")
    parser.add_argument(
        "--level",
        default="1",
        help="stage number (1-based) or path to a stage JSON file (default: 1)",
    )
    parser.add_argument(
        "--levels-dir",
        type=Path,
        default=LEVELS_DIR,
        help="directory of stage files (default: the bundled levels/)",
    )
    parser.add_argument(
        "--solve",
        choices=(*ALGORITHMS, "all"),
        help="solve the stage in the terminal instead of opening the GUI",
    )
    parser.add_argument(
        "--heuristic",
        choices=sorted(HEURISTICS),
        default="manhattan",
        help="heuristic used by A* (default: manhattan)",
    )
    parser.add_argument(
        "--cost",
        choices=sorted(COST_MODELS),
        default="risk-aware",
        help="cost function used by UCS and A* (default: risk-aware)",
    )
    parser.add_argument("--list", action="store_true", help="list the stages and exit")
    return parser.parse_args()


def pick_level(levels: list[Level], choice: str) -> int:
    """Index of the chosen stage; a file path is loaded and appended."""
    if choice.isdigit():
        index = int(choice) - 1
        if not 0 <= index < len(levels):
            sys.exit(f"--level must be between 1 and {len(levels)}")
        return index
    levels.append(load_level(choice))
    return len(levels) - 1


def print_result(result) -> None:
    memory = result.peak_memory_bytes
    print(f"{result.algorithm}")
    if result.solved:
        print(f"  solution length : {result.length} moves")
        print(f"  path cost       : {result.cost}")
    else:
        print("  no solution")
    print(f"  expanded nodes  : {result.expanded}")
    print(f"  generated nodes : {result.generated}")
    print(f"  search time     : {result.time_s * 1000:.3f} ms")
    print(f"  peak memory     : {memory / 1024:.1f} KiB")
    if result.solved:
        print(f"  moves           : {result.moves}")


def main() -> None:
    args = parse_args()
    try:
        levels = load_levels(args.levels_dir)
        index = pick_level(levels, args.level)
    except (LevelError, OSError) as error:
        sys.exit(f"Cannot load stage: {error}")
    if not levels:
        sys.exit(f"No stage files found in {args.levels_dir}")

    if args.list:
        for number, level in enumerate(levels, start=1):
            print(f"{number:2}  {level.name:18} {level.group}")
        return

    cost_model = COST_MODELS[args.cost]
    if args.solve:
        level = levels[index]
        print(f"Stage {index + 1}: {level.name}  (cost function: {cost_model.name})")
        print("Moves: U/D/L/R roll the block, S switches control between cubes.")
        algorithms = ALGORITHMS if args.solve == "all" else (args.solve,)
        for algorithm in algorithms:
            print_result(
                solve(level, algorithm, cost_model=cost_model, heuristic=args.heuristic)
            )
        return

    try:
        from bloxorz.gui import run_gui
    except ImportError:
        sys.exit("The GUI needs pygame. Install it with: pip install -r requirements.txt")
    run_gui(levels, index, heuristic=args.heuristic, cost_model=cost_model)


if __name__ == "__main__":
    main()
