"""The search problem handed to the solvers: initial state, goal test,
successor function, and step costs."""

from __future__ import annotations

from dataclasses import dataclass

from .game import (
    Action,
    MoveStatus,
    State,
    initial_state,
    is_goal,
    legal_actions,
    move,
)
from .level import Cell, Level, Tile


@dataclass(frozen=True)
class CostModel:
    """Step cost of one action.

    cost = `roll` for rolling the block or a cube, `swap` for switching
    control between cubes, plus `fragile` for every fragile tile the moved
    piece lands on.
    """

    name: str
    roll: int = 1
    swap: int = 1
    fragile: int = 0

    def __post_init__(self) -> None:
        if self.roll <= 0 or self.swap <= 0 or self.fragile < 0:
            raise ValueError("step costs must be positive")

    @property
    def min_cost(self) -> int:
        """Cheapest possible action; heuristics scale their step counts by it."""
        return min(self.roll, self.swap)

    def cost(self, level: Level, action: Action, landed: tuple[Cell, ...]) -> int:
        if action is Action.SWAP:
            return self.swap
        on_fragile = sum(level.tile(cell) is Tile.FRAGILE for cell in landed)
        return self.roll + self.fragile * on_fragile


# Every action costs 1: the cheapest path is the shortest one.
UNIT_COST = CostModel("unit")

# Fragile tiles are risky (one wrong roll on them loses the stage), so each
# fragile tile the block lands on adds 2 to the cost of the roll.
RISK_COST = CostModel("risk-aware", fragile=2)

COST_MODELS = {model.name: model for model in (RISK_COST, UNIT_COST)}


class Problem:
    def __init__(
        self,
        level: Level,
        cost_model: CostModel = RISK_COST,
        start: State | None = None,
    ) -> None:
        self.level = level
        self.cost_model = cost_model
        self.initial = start if start is not None else initial_state(level)

    def is_goal(self, state: State) -> bool:
        return is_goal(self.level, state)

    def successors(self, state: State) -> list[tuple[Action, State, int]]:
        """All legal (action, next state, step cost) triples from `state`."""
        level = self.level
        result = []
        for action in legal_actions(state):
            outcome = move(level, state, action)
            if outcome.status is MoveStatus.OK:
                cost = self.cost_model.cost(level, action, outcome.landed)
                result.append((action, outcome.state, cost))
        return result

    def path_cost(self, actions: list[Action]) -> int:
        """Total cost of an action sequence applied from the initial state."""
        state, total = self.initial, 0
        for action in actions:
            outcome = move(self.level, state, action)
            if outcome.status is not MoveStatus.OK:
                raise ValueError(f"illegal action {action.name} in path")
            total += self.cost_model.cost(self.level, action, outcome.landed)
            state = outcome.state
        return total
