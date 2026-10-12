"""Search algorithms and the `solve` entry point that measures them."""

from __future__ import annotations

import time
import tracemalloc

from ..game import State
from ..heuristics import HEURISTICS
from ..level import Level
from ..problem import RISK_COST, CostModel, Problem
from .astar import astar
from .base import SearchResult
from .bfs import bfs
from .dfs import dfs
from .ucs import ucs

ALGORITHMS = ("bfs", "dfs", "ucs", "astar")

__all__ = ["ALGORITHMS", "SearchResult", "astar", "bfs", "dfs", "solve", "ucs"]


def _run(problem: Problem, algorithm: str, heuristic: str) -> SearchResult:
    if algorithm == "bfs":
        return bfs(problem)
    if algorithm == "dfs":
        return dfs(problem)
    if algorithm == "ucs":
        return ucs(problem)
    if algorithm == "astar":
        # Building the heuristic is part of the search and is measured too.
        result = astar(problem, HEURISTICS[heuristic](problem))
        result.algorithm = f"A* ({heuristic})"
        return result
    raise ValueError(f"unknown algorithm {algorithm!r}; choose from {ALGORITHMS}")


def solve(
    level: Level,
    algorithm: str,
    *,
    start: State | None = None,
    cost_model: CostModel = RISK_COST,
    heuristic: str = "manhattan",
    repeats: int = 1,
    measure_memory: bool = True,
) -> SearchResult:
    """Run one solver on `level` and record time and peak memory.

    Time is the best of `repeats` runs. Memory is measured in a separate run
    under tracemalloc, because tracing slows the search down several times
    and would distort the timing.
    """
    if heuristic not in HEURISTICS:
        raise ValueError(f"unknown heuristic {heuristic!r}")
    problem = Problem(level, cost_model, start)

    best_time = float("inf")
    for _ in range(max(1, repeats)):
        began = time.perf_counter()
        result = _run(problem, algorithm, heuristic)
        best_time = min(best_time, time.perf_counter() - began)
    result.time_s = best_time

    if measure_memory:
        tracemalloc.start()
        try:
            _run(problem, algorithm, heuristic)
            result.peak_memory_bytes = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
    return result
