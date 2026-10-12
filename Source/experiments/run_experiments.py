"""Run every solver on every bundled stage and write the measurements.

    python experiments/run_experiments.py            tables and charts
    python experiments/run_experiments.py --no-charts   tables only (no matplotlib)

Output goes to experiments/results/:
    results.csv   one row per (stage, solver)
    results.md    the same numbers as Markdown tables, one per metric
    *.png         one chart per metric
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bloxorz.level import Level, load_levels  # noqa: E402
from bloxorz.problem import COST_MODELS, Problem  # noqa: E402
from bloxorz.solvers import SearchResult, solve  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# (column label, algorithm, heuristic)
SOLVERS = [
    ("BFS", "bfs", "relaxed"),
    ("DFS", "dfs", "relaxed"),
    ("UCS", "ucs", "relaxed"),
    ("A* (manhattan)", "astar", "manhattan"),
    ("A* (relaxed)", "astar", "relaxed"),
]

# (key, table title, chart axis label, value getter, formatter)
METRICS = [
    ("time", "Search time (ms)", "Search time (ms, log scale)",
     lambda r: r.time_s * 1000, lambda v: f"{v:.3f}"),
    ("memory", "Peak memory (KiB)", "Peak memory (KiB, log scale)",
     lambda r: r.peak_memory_bytes / 1024, lambda v: f"{v:.1f}"),
    ("expanded", "Expanded nodes", "Expanded nodes (log scale)",
     lambda r: r.expanded, lambda v: f"{v:,}"),
    ("length", "Solution length (moves)", "Solution length (moves, log scale)",
     lambda r: r.length, lambda v: f"{v:,}"),
    ("cost", "Path cost", "Path cost (log scale)",
     lambda r: r.cost, lambda v: f"{v:,}"),
]


def count_states(problem: Problem) -> int:
    """Number of states reachable from the start: the size of the search space."""
    seen = {problem.initial}
    stack = [problem.initial]
    while stack:
        for _action, child, _cost in problem.successors(stack.pop()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return len(seen)


def measure(levels: list[Level], cost_model, repeats: int):
    """results[stage index][solver label] -> SearchResult."""
    results = []
    for number, level in enumerate(levels, start=1):
        row = {}
        for label, algorithm, heuristic in SOLVERS:
            row[label] = solve(
                level, algorithm, cost_model=cost_model,
                heuristic=heuristic, repeats=repeats,
            )
        results.append(row)
        print(f"  {number:2}/{len(levels)}  {level.name}")
    return results


def write_csv(path: Path, levels, sizes, results) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "stage", "name", "group", "reachable_states", "solver", "solved",
            "time_ms", "peak_memory_kib", "expanded", "generated",
            "max_frontier", "length", "cost", "moves",
        ])
        for number, (level, size, row) in enumerate(zip(levels, sizes, results), 1):
            for label, _, _ in SOLVERS:
                r: SearchResult = row[label]
                writer.writerow([
                    number, level.name, level.group, size, label, r.solved,
                    f"{r.time_s * 1000:.4f}", f"{r.peak_memory_bytes / 1024:.2f}",
                    r.expanded, r.generated, r.max_frontier, r.length, r.cost,
                    r.moves,
                ])


def write_markdown(path: Path, levels, sizes, results, cost_model, repeats) -> None:
    labels = [label for label, _, _ in SOLVERS]
    lines = [
        "# Experiment results",
        "",
        f"Cost function: **{cost_model.name}** (roll {cost_model.roll}, "
        f"swap {cost_model.swap}, +{cost_model.fragile} per fragile tile landed on). "
        f"Search time is the best of {repeats} runs; peak memory is measured in "
        "a separate run with `tracemalloc`. A* times and memory include building "
        "the heuristic.",
        "",
        "## Test set",
        "",
        "| # | Stage | Group | Size | Bridges | Switches | Reachable states |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for number, (level, size) in enumerate(zip(levels, sizes), 1):
        lines.append(
            f"| {number} | {level.name} | {level.group} | "
            f"{level.rows} x {level.cols} | {len(level.bridges)} | "
            f"{len(level.switches)} | {size:,} |"
        )
    for _key, title, _axis, getter, fmt in METRICS:
        lines += [
            "",
            f"## {title}",
            "",
            "| # | Stage | " + " | ".join(labels) + " |",
            "| ---: | --- | " + " | ".join("---:" for _ in labels) + " |",
        ]
        for number, (level, row) in enumerate(zip(levels, results), 1):
            cells = [fmt(getter(row[label])) for label in labels]
            lines.append(f"| {number} | {level.name} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_charts(directory: Path, levels, results) -> None:
    """One dot plot per metric: a row per stage, a marker per solver.

    The values span several orders of magnitude, so the axis is logarithmic,
    and a log axis has no zero for bars to grow from; dots show position only.
    Each solver has its own colour and its own marker shape.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, muted, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de"
    styles = {
        "BFS": ("#2a78d6", "o"),
        "DFS": ("#eb6834", "s"),
        "UCS": ("#1baf7a", "^"),
        "A* (manhattan)": ("#eda100", "D"),
        "A* (relaxed)": ("#e87ba4", "X"),
    }
    labels = [label for label, _, _ in SOLVERS]
    plt.rcParams.update({
        "font.size": 10,
        "text.color": ink,
        "axes.labelcolor": muted,
        "xtick.color": muted,
        "ytick.color": ink,
    })
    rows = len(levels)
    for key, title, axis_label, getter, _fmt in METRICS:
        figure, axes = plt.subplots(figsize=(9, 0.52 * rows + 1.6), facecolor=surface)
        axes.set_facecolor(surface)
        for index in range(rows):
            if index % 2 == 0:
                axes.axhspan(index - 0.5, index + 0.5, color="#f3f2ee", zorder=0)
        for slot, label in enumerate(labels):
            color, marker = styles[label]
            # Spread the solvers inside a row so equal values stay visible.
            offset = (slot - (len(labels) - 1) / 2) * 0.17
            axes.scatter(
                [getter(row[label]) for row in results],
                [index + offset for index in range(rows)],
                s=72 if marker == "X" else 58, color=color, marker=marker, label=label,
                edgecolors=surface, linewidths=1.2, zorder=3,
            )
        axes.set_xscale("log")
        axes.set_yticks(range(rows))
        axes.set_yticklabels(
            [f"{number}. {level.name}" for number, level in enumerate(levels, 1)]
        )
        axes.set_ylim(rows - 0.5, -0.5)
        axes.set_xlabel(axis_label)
        axes.grid(axis="x", which="major", color=grid, linewidth=0.8, zorder=1)
        axes.tick_params(length=0)
        for spine in axes.spines.values():
            spine.set_visible(False)
        axes.set_title(title + " by stage and solver", loc="left", fontsize=12, pad=30)
        axes.legend(
            loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(labels),
            frameon=False, handletextpad=0.2, columnspacing=1.2, borderaxespad=0.2,
        )
        figure.tight_layout()
        figure.savefig(directory / f"{key}.png", dpi=160, facecolor=surface)
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=7,
                        help="timing runs per measurement; the best is kept")
    parser.add_argument("--cost", choices=sorted(COST_MODELS), default="risk-aware")
    parser.add_argument("--no-charts", action="store_true")
    args = parser.parse_args()

    levels = load_levels()
    cost_model = COST_MODELS[args.cost]
    print(f"Measuring {len(SOLVERS)} solvers on {len(levels)} stages...")
    results = measure(levels, cost_model, args.repeats)
    sizes = [count_states(Problem(level, cost_model)) for level in levels]

    RESULTS_DIR.mkdir(exist_ok=True)
    write_csv(RESULTS_DIR / "results.csv", levels, sizes, results)
    write_markdown(RESULTS_DIR / "results.md", levels, sizes, results,
                   cost_model, args.repeats)
    if not args.no_charts:
        try:
            write_charts(RESULTS_DIR, levels, results)
        except ImportError:
            print("matplotlib is not installed: skipped the charts.")
    print(f"Wrote {RESULTS_DIR}")


if __name__ == "__main__":
    main()
