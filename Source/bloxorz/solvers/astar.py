"""A* Search."""

from __future__ import annotations

import heapq
from itertools import count

from ..heuristics import Heuristic
from ..problem import Problem
from .base import Parents, SearchResult, reconstruct


def astar(problem: Problem, heuristic: Heuristic) -> SearchResult:
    """Expand states in order of f = g + h, where g is the cost so far and h
    estimates the remaining cost; with an admissible h the solution found has
    minimum cost.

    A state is re-queued whenever a cheaper path to it is found, so the result
    stays optimal even when h is admissible but not consistent. States with
    h = infinity cannot reach the goal and are dropped.
    """
    result = SearchResult("A*")
    start = problem.initial
    parents: Parents = {start: None}
    best_g = {start: 0}
    tie = count()
    # Entries are (f, h, tie, g, state): among equal f, prefer the smaller h,
    # i.e. the state that is closer to the goal.
    h = heuristic(start)
    frontier = [] if h == float("inf") else [(h, h, next(tie), 0, start)]
    while frontier:
        result.max_frontier = max(result.max_frontier, len(frontier))
        _f, _h, _, g, state = heapq.heappop(frontier)
        if g > best_g[state]:
            continue  # outdated entry: the state was reached more cheaply
        if problem.is_goal(state):
            result.solved = True
            result.actions = reconstruct(parents, state)
            result.cost = g
            return result
        result.expanded += 1
        for action, child, cost in problem.successors(state):
            result.generated += 1
            child_g = g + cost
            if child_g < best_g.get(child, float("inf")):
                h = heuristic(child)
                if h == float("inf"):
                    continue
                best_g[child] = child_g
                parents[child] = (state, action)
                heapq.heappush(frontier, (child_g + h, h, next(tie), child_g, child))
    return result
