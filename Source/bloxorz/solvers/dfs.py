"""Depth-First Search (graph search with a visited set)."""

from __future__ import annotations

from ..problem import Problem
from .base import Parents, SearchResult, reconstruct


def dfs(problem: Problem) -> SearchResult:
    """Follow one branch as deep as possible before backtracking.

    Written iteratively: the stack holds one successor iterator per state on
    the current path, so it behaves exactly like the recursive version without
    hitting Python's recursion limit. `parents` is the visited set, which
    keeps the search out of cycles; the solution found is usually far from
    the shortest one.
    """
    result = SearchResult("DFS")
    start = problem.initial
    parents: Parents = {start: None}
    if problem.is_goal(start):
        result.solved = True
        return result

    stack = [iter(problem.successors(start))]
    path = [start]
    result.expanded = 1
    result.max_frontier = 1
    while stack:
        step = next(stack[-1], None)
        if step is None:
            # Every successor of the deepest state is explored: backtrack.
            stack.pop()
            path.pop()
            continue
        action, child, _cost = step
        result.generated += 1
        if child in parents:
            continue
        parents[child] = (path[-1], action)
        if problem.is_goal(child):
            result.solved = True
            result.actions = reconstruct(parents, child)
            result.cost = problem.path_cost(result.actions)
            return result
        stack.append(iter(problem.successors(child)))
        path.append(child)
        result.expanded += 1
        result.max_frontier = max(result.max_frontier, len(stack))
    return result
