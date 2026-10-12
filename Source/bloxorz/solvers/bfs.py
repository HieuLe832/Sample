"""Breadth-First Search."""

from __future__ import annotations

from collections import deque

from ..problem import Problem
from .base import Parents, SearchResult, reconstruct


def bfs(problem: Problem) -> SearchResult:
    """Explore states level by level; finds a solution with the fewest actions.

    The frontier is a FIFO queue. A state is recorded in `parents` as soon as
    it is generated, which doubles as the visited set, and the goal test is
    done at generation time (safe for BFS: the first path to reach a state is
    a shortest one).
    """
    result = SearchResult("BFS")
    start = problem.initial
    parents: Parents = {start: None}
    if problem.is_goal(start):
        result.solved = True
        return result

    frontier = deque([start])
    result.max_frontier = 1
    while frontier:
        state = frontier.popleft()
        result.expanded += 1
        for action, child, _cost in problem.successors(state):
            result.generated += 1
            if child in parents:
                continue
            parents[child] = (state, action)
            if problem.is_goal(child):
                result.solved = True
                result.actions = reconstruct(parents, child)
                result.cost = problem.path_cost(result.actions)
                return result
            frontier.append(child)
        result.max_frontier = max(result.max_frontier, len(frontier))
    return result
