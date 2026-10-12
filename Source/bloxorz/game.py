"""Game rules: the state representation and the transition model.

Everything here is pure: `move` never mutates anything, it maps a state and an
action to a new state. The GUI and the solvers share this single
implementation of the rules.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from .level import Cell, Level, SwitchKind, Tile


class Action(Enum):
    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"
    # Hand control to the other cube. Only available while the block is split.
    SWAP = "S"


ROLLS = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)

DELTAS = {
    Action.UP: (-1, 0),
    Action.DOWN: (1, 0),
    Action.LEFT: (0, -1),
    Action.RIGHT: (0, 1),
}


class Orientation(Enum):
    STANDING = "standing"
    HORIZONTAL = "lying horizontally"
    VERTICAL = "lying vertically"
    SPLIT = "split"


STANDING = Orientation.STANDING
HORIZONTAL = Orientation.HORIZONTAL
VERTICAL = Orientation.VERTICAL

# Orientation transition table.
# (orientation, direction) -> (row offset, column offset, new orientation).
# The offsets move the anchor cell (r, c): the only cell of a standing block,
# the left cell of a horizontal block, the top cell of a vertical block.
ROLL_TABLE = {
    (STANDING, Action.UP): (-2, 0, VERTICAL),
    (STANDING, Action.DOWN): (1, 0, VERTICAL),
    (STANDING, Action.LEFT): (0, -2, HORIZONTAL),
    (STANDING, Action.RIGHT): (0, 1, HORIZONTAL),
    (HORIZONTAL, Action.UP): (-1, 0, HORIZONTAL),
    (HORIZONTAL, Action.DOWN): (1, 0, HORIZONTAL),
    (HORIZONTAL, Action.LEFT): (0, -1, STANDING),
    (HORIZONTAL, Action.RIGHT): (0, 2, STANDING),
    (VERTICAL, Action.UP): (-1, 0, STANDING),
    (VERTICAL, Action.DOWN): (2, 0, STANDING),
    (VERTICAL, Action.LEFT): (0, -1, VERTICAL),
    (VERTICAL, Action.RIGHT): (0, 1, VERTICAL),
}


class State(NamedTuple):
    """A complete game state; hashable, so it can go straight into a set.

    Whole block: `a` is the anchor cell and `b` the other half (`b == a` when
    standing, right of `a` when horizontal, below `a` when vertical).
    Split block: `a` is the cube being controlled and `b` the other cube.
    `bridges` is a bitmask with bit i set when bridge i is open.
    """

    a: Cell
    b: Cell
    split: bool
    bridges: int

    @property
    def orientation(self) -> Orientation:
        if self.split:
            return Orientation.SPLIT
        if self.a == self.b:
            return STANDING
        return HORIZONTAL if self.a[0] == self.b[0] else VERTICAL

    @property
    def cells(self) -> tuple[Cell, ...]:
        return (self.a,) if self.a == self.b else (self.a, self.b)


class MoveStatus(Enum):
    OK = "ok"
    FELL = "fell"  # part of the block ended up over a void or a closed bridge
    BROKE = "broke"  # the block stood up on a fragile tile
    INVALID = "invalid"  # the action does not apply (swap while not split)


class MoveResult(NamedTuple):
    status: MoveStatus
    state: State | None  # the new state when status is OK
    landed: tuple[Cell, ...]  # cells the moved piece rolled onto


def block_cells(anchor: Cell, orientation: Orientation) -> tuple[Cell, ...]:
    r, c = anchor
    if orientation is STANDING:
        return ((r, c),)
    if orientation is HORIZONTAL:
        return ((r, c), (r, c + 1))
    return ((r, c), (r + 1, c))


def initial_state(level: Level) -> State:
    return State(level.start, level.start, False, level.initial_bridges)


def is_goal(level: Level, state: State) -> bool:
    """Only a whole block standing upright on the goal hole wins."""
    return not state.split and state.a == state.b == level.goal


def move(level: Level, state: State, action: Action) -> MoveResult:
    """Apply `action` to `state` and report what happened."""
    if action is Action.SWAP:
        if not state.split:
            return MoveResult(MoveStatus.INVALID, None, ())
        swapped = State(state.b, state.a, True, state.bridges)
        return MoveResult(MoveStatus.OK, swapped, ())

    # 1. Roll the piece under control.
    if state.split:
        dr, dc = DELTAS[action]
        landed = ((state.a[0] + dr, state.a[1] + dc),)
        pieces = [landed[0], state.b]
        standing = False
    else:
        dr, dc, orientation = ROLL_TABLE[state.orientation, action]
        landed = block_cells((state.a[0] + dr, state.a[1] + dc), orientation)
        pieces = [landed[0], landed[-1]]
        standing = orientation is STANDING

    # 2. Every cell under the piece must carry it.
    bridges = state.bridges
    if not all(level.supports(cell, bridges) for cell in landed):
        return MoveResult(MoveStatus.FELL, None, landed)
    if standing and level.tile(landed[0]) is Tile.FRAGILE:
        return MoveResult(MoveStatus.BROKE, None, landed)

    # 3. Press the switches under the piece. Soft switches react to any
    #    weight, heavy and split switches only to the whole block standing.
    split = state.split
    for cell in landed:
        switch = level.switches.get(cell)
        if switch is None:
            continue
        if switch.kind is SwitchKind.SOFT or standing:
            if switch.kind is SwitchKind.SPLIT:
                pieces = list(switch.targets)
                split = True
            else:
                bridges = switch.apply(bridges)

    # 4. A switch may have closed a bridge under the block (or under the
    #    waiting cube), and split targets may sit on a closed bridge.
    if not all(level.supports(cell, bridges) for cell in pieces):
        return MoveResult(MoveStatus.FELL, None, landed)

    # 5. Two cubes on adjacent tiles merge back into one block.
    a, b = pieces
    if split and abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
        split = False
    if not split and a > b:
        a, b = b, a
    return MoveResult(MoveStatus.OK, State(a, b, split, bridges), landed)


def legal_actions(state: State) -> tuple[Action, ...]:
    return (*ROLLS, Action.SWAP) if state.split else ROLLS


def replay(level: Level, actions: list[Action], start: State | None = None) -> State:
    """Apply a sequence of actions; raise ValueError on the first illegal one."""
    state = start if start is not None else initial_state(level)
    for index, action in enumerate(actions):
        result = move(level, state, action)
        if result.status is not MoveStatus.OK:
            raise ValueError(
                f"action {index} ({action.name}) is illegal: {result.status.value}"
            )
        state = result.state
    return state
