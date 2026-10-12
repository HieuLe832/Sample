"""Uniform-Cost Search."""

from __future__ import annotations

import heapq
from itertools import count

from ..problem import Problem
from .base import Parents, SearchResult, reconstruct


def ucs(problem: Problem) -> SearchResult:
    """Always expand the cheapest state reached so far; finds a minimum-cost
    solution under the problem's cost model.

    The frontier is a priority queue ordered by path cost g. Instead of
    decreasing a key in place, a cheaper path to a state pushes a new entry
    and the outdated one is skipped when it is popped. The goal test is done
    when a state is expanded, not when it is generated; only then is its
    cost known to be minimal.
    """
    result = SearchResult("UCS")
    start = problem.initial
    parents: Parents = {start: None}
    best_g = {start: 0}
    tie = count()  # breaks ties in insertion order so states are never compared
    frontier = [(0, next(tie), start)]
    while frontier:
        result.max_frontier = max(result.max_frontier, len(frontier))
        g, _, state = heapq.heappop(frontier)
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
                best_g[child] = child_g
                parents[child] = (state, action)
                heapq.heappush(frontier, (child_g, next(tie), child))
    return result
