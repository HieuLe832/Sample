"""Heuristics for A*.

Each factory takes the Problem and returns a function h(state) that estimates
the cost of the cheapest path from `state` to the goal. Both heuristics below
are admissible for any CostModel: they never overestimate that cost.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable
from itertools import count

from .game import State
from .level import Cell, SwitchKind
from .problem import Problem

Heuristic = Callable[[State], float]

INFINITY = float("inf")


def manhattan(first: Cell, second: Cell) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def zero_heuristic(problem: Problem) -> Heuristic:
    """h = 0 everywhere; turns A* into UCS. Useful as a baseline."""
    return lambda state: 0


def manhattan_heuristic(problem: Problem) -> Heuristic:
    """Half the Manhattan distance of the block's far end to the goal.

    One roll puts every cell of the block at most two cells away from where
    any of its cells was, so the Manhattan distance from the goal to the
    farthest cell of the block shrinks by at most 2 per roll. It must reach 0,
    hence at least ceil(far / 2) rolls remain. A lying block is never at
    distance 0, so the "one more roll to stand up" penalty is included.

    Split switches teleport the block, which would break that argument, so
    the estimate also considers reaching a split switch first: the rolls to
    stand on it plus the moves the two cubes then need to meet again. While
    split, the cubes need distance - 1 moves to become adjacent, and the
    merged block (lying) needs at least one more roll.
    """
    level = problem.level
    goal = level.goal
    unit = problem.cost_model.min_cost
    # (split switch cell, minimum number of actions needed after using it)
    splitters = [
        (switch.cell, manhattan(*switch.targets))
        for switch in level.switches.values()
        if switch.kind is SwitchKind.SPLIT
    ]

    def rolls_to_stand_on(state: State, target: Cell) -> int:
        far = max(manhattan(state.a, target), manhattan(state.b, target))
        return (far + 1) // 2

    def h(state: State) -> float:
        if state.split:
            return manhattan(state.a, state.b) * unit
        steps = rolls_to_stand_on(state, goal)
        for cell, after in splitters:
            steps = min(steps, rolls_to_stand_on(state, cell) + after)
        return steps * unit

    return h


def relaxed_heuristic(problem: Problem) -> Heuristic:
    """Exact cost-to-goal in the stage with every bridge open.

    Opening all bridges removes the bridge configuration from the state, which
    leaves a much smaller problem (block placement only). Every move that is
    legal in the real stage is also legal there, with the same cost, so the
    cheapest relaxed path can only be cheaper than the real one: the heuristic
    is admissible. It is also consistent, because a real step s -> s' of cost
    c is a relaxed step too, giving h(s) <= c + h(s').

    The relaxed problem is solved once, backwards from the goal with
    Dijkstra's algorithm, and h(state) is then a table lookup. A placement
    missing from the table cannot reach the goal even with all bridges open,
    so its estimate is infinity.
    """
    relaxed = Problem(problem.level.relaxed(), problem.cost_model)

    def abstract(state: State) -> State:
        return State(state.a, state.b, state.split, 0)

    # Enumerate the relaxed states reachable from the start, keeping the
    # reversed edges for the backward pass.
    start = abstract(problem.initial)
    reverse: dict[State, list[tuple[State, int]]] = {start: []}
    stack = [start]
    while stack:
        state = stack.pop()
        for _action, child, cost in relaxed.successors(state):
            if child not in reverse:
                reverse[child] = []
                stack.append(child)
            reverse[child].append((state, cost))

    # Dijkstra from the goal over the reversed edges.
    goal = State(relaxed.level.goal, relaxed.level.goal, False, 0)
    distance: dict[State, int] = {}
    if goal in reverse:
        distance[goal] = 0
        tie = count()
        queue = [(0, next(tie), goal)]
        while queue:
            d, _, state = heapq.heappop(queue)
            if d > distance[state]:
                continue
            for previous, cost in reverse[state]:
                if d + cost < distance.get(previous, INFINITY):
                    distance[previous] = d + cost
                    heapq.heappush(queue, (d + cost, next(tie), previous))

    def h(state: State) -> float:
        return distance.get(abstract(state), INFINITY)

    return h


HEURISTICS: dict[str, Callable[[Problem], Heuristic]] = {
    "relaxed": relaxed_heuristic,
    "manhattan": manhattan_heuristic,
    "zero": zero_heuristic,
}
