"""Stage description: tiles, bridges, switches, and the JSON stage loader.

A stage file is a JSON object::

    {
      "name": "Drawbridge",
      "group": "switches",
      "grid": ["####....###",
               "#S1#aa..#G#",
               "####....###"],
      "bridges":  {"a": "closed"},
      "switches": {"1": {"type": "soft", "effects": {"a": "toggle"}}}
    }

Grid legend:

    .  or space   void (no tile)
    #             floor tile
    S             start tile (the block starts standing here)
    G             goal hole
    F             fragile tile
    a-z           bridge tile belonging to the bridge with that letter
    0-9           switch with that digit, described under "switches"

Switch types are "soft", "heavy" and "split". Soft and heavy switches list
their "effects" as ``{bridge letter: "toggle" | "open" | "close"}``; "open" and
"close" are the permanent behaviours. A split switch lists the two "targets"
``[[row, col], [row, col]]`` the halves are teleported to.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

Cell = tuple[int, int]

LEVELS_DIR = Path(__file__).resolve().parent.parent / "levels"


class LevelError(ValueError):
    """Raised when a stage file is malformed."""


class Tile(Enum):
    VOID = "void"
    FLOOR = "floor"
    GOAL = "goal"
    FRAGILE = "fragile"
    BRIDGE = "bridge"


class SwitchKind(Enum):
    SOFT = "soft"
    HEAVY = "heavy"
    SPLIT = "split"


class Effect(Enum):
    TOGGLE = "toggle"
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True)
class Bridge:
    id: str
    cells: tuple[Cell, ...]
    initially_open: bool


@dataclass(frozen=True)
class Switch:
    id: str
    cell: Cell
    kind: SwitchKind
    # (bridge index, effect) pairs; empty for split switches.
    effects: tuple[tuple[int, Effect], ...] = ()
    # Where the two halves land; only set for split switches.
    targets: tuple[Cell, Cell] | None = None

    def apply(self, bridges: int) -> int:
        """Return the bridge bitmask after this switch is activated."""
        for index, effect in self.effects:
            bit = 1 << index
            if effect is Effect.TOGGLE:
                bridges ^= bit
            elif effect is Effect.OPEN:
                bridges |= bit
            else:
                bridges &= ~bit
        return bridges


@dataclass(eq=False)
class Level:
    name: str
    tiles: tuple[tuple[Tile, ...], ...]
    start: Cell
    goal: Cell
    bridges: tuple[Bridge, ...] = ()
    switches: dict[Cell, Switch] = field(default_factory=dict)
    group: str = "custom"
    path: Path | None = None

    def __post_init__(self) -> None:
        self.rows = len(self.tiles)
        self.cols = len(self.tiles[0])
        # Cell -> index of the bridge it belongs to (bit position in the mask).
        self.bridge_at: dict[Cell, int] = {
            cell: index
            for index, bridge in enumerate(self.bridges)
            for cell in bridge.cells
        }
        self.initial_bridges = sum(
            1 << index
            for index, bridge in enumerate(self.bridges)
            if bridge.initially_open
        )
        self.has_split = any(
            switch.kind is SwitchKind.SPLIT for switch in self.switches.values()
        )

    def tile(self, cell: Cell) -> Tile:
        r, c = cell
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.tiles[r][c]
        return Tile.VOID

    def supports(self, cell: Cell, bridges: int) -> bool:
        """True if `cell` can carry weight given the open bridges bitmask."""
        tile = self.tile(cell)
        if tile is Tile.VOID:
            return False
        if tile is Tile.BRIDGE:
            return bool(bridges >> self.bridge_at[cell] & 1)
        return True

    def relaxed(self) -> Level:
        """The same stage with every bridge permanently open.

        Bridge tiles become plain floor and bridge switches disappear, so the
        bridge configuration is no longer part of the state. Used to build the
        relaxed-problem heuristic.
        """
        tiles = tuple(
            tuple(Tile.FLOOR if tile is Tile.BRIDGE else tile for tile in row)
            for row in self.tiles
        )
        switches = {
            cell: switch
            for cell, switch in self.switches.items()
            if switch.kind is SwitchKind.SPLIT
        }
        return Level(
            name=f"{self.name} (relaxed)",
            tiles=tiles,
            start=self.start,
            goal=self.goal,
            switches=switches,
            group=self.group,
        )


def parse_level(data: dict, path: Path | None = None) -> Level:
    """Build a Level from the decoded JSON object, validating it on the way."""
    try:
        grid = data["grid"]
    except (KeyError, TypeError):
        raise LevelError('stage is missing the "grid" list') from None
    if not grid or not all(isinstance(line, str) for line in grid):
        raise LevelError('"grid" must be a non-empty list of strings')

    cols = max(len(line) for line in grid)
    tiles: list[list[Tile]] = []
    start = goal = None
    bridge_cells: dict[str, list[Cell]] = {}
    switch_cells: dict[str, Cell] = {}

    for r, line in enumerate(grid):
        row = []
        for c, char in enumerate(line.ljust(cols, ".")):
            cell = (r, c)
            if char in ". ":
                row.append(Tile.VOID)
            elif char == "#":
                row.append(Tile.FLOOR)
            elif char == "F":
                row.append(Tile.FRAGILE)
            elif char == "S":
                if start is not None:
                    raise LevelError("stage has more than one start tile (S)")
                start = cell
                row.append(Tile.FLOOR)
            elif char == "G":
                if goal is not None:
                    raise LevelError("stage has more than one goal hole (G)")
                goal = cell
                row.append(Tile.GOAL)
            elif char.islower():
                bridge_cells.setdefault(char, []).append(cell)
                row.append(Tile.BRIDGE)
            elif char.isdigit():
                if char in switch_cells:
                    raise LevelError(f"switch {char} appears twice in the grid")
                switch_cells[char] = cell
                row.append(Tile.FLOOR)
            else:
                raise LevelError(f"unknown grid character {char!r} at {cell}")
        tiles.append(row)

    if start is None:
        raise LevelError("stage has no start tile (S)")
    if goal is None:
        raise LevelError("stage has no goal hole (G)")

    bridge_states = data.get("bridges", {})
    for bridge_id, state in bridge_states.items():
        if bridge_id not in bridge_cells:
            raise LevelError(f"bridge {bridge_id!r} is not in the grid")
        if state not in ("open", "closed"):
            raise LevelError(f'bridge {bridge_id!r} must be "open" or "closed"')
    bridge_ids = sorted(bridge_cells)
    bridges = tuple(
        Bridge(
            id=bridge_id,
            cells=tuple(bridge_cells[bridge_id]),
            initially_open=bridge_states.get(bridge_id, "closed") == "open",
        )
        for bridge_id in bridge_ids
    )

    switch_specs = data.get("switches", {})
    for switch_id in switch_specs:
        if switch_id not in switch_cells:
            raise LevelError(f"switch {switch_id!r} is not in the grid")
    switches: dict[Cell, Switch] = {}
    for switch_id, cell in switch_cells.items():
        if switch_id not in switch_specs:
            raise LevelError(f'switch {switch_id} has no entry under "switches"')
        switches[cell] = _parse_switch(
            switch_id, cell, switch_specs[switch_id], bridge_ids, tiles
        )

    return Level(
        name=data.get("name", path.stem if path else "Untitled"),
        tiles=tuple(tuple(row) for row in tiles),
        start=start,
        goal=goal,
        bridges=bridges,
        switches=switches,
        group=data.get("group", "custom"),
        path=path,
    )


def _parse_switch(
    switch_id: str,
    cell: Cell,
    spec: dict,
    bridge_ids: list[str],
    tiles: list[list[Tile]],
) -> Switch:
    try:
        kind = SwitchKind(spec.get("type"))
    except ValueError:
        raise LevelError(
            f'switch {switch_id}: "type" must be soft, heavy or split'
        ) from None

    if kind is SwitchKind.SPLIT:
        targets = spec.get("targets")
        if not isinstance(targets, list) or len(targets) != 2:
            raise LevelError(f'switch {switch_id}: "targets" needs two cells')
        first, second = (tuple(target) for target in targets)
        if first == second:
            raise LevelError(f"switch {switch_id}: targets must differ")
        for r, c in (first, second):
            inside = 0 <= r < len(tiles) and 0 <= c < len(tiles[0])
            if not inside or tiles[r][c] is Tile.VOID:
                raise LevelError(f"switch {switch_id}: target {(r, c)} is void")
        return Switch(switch_id, cell, kind, targets=(first, second))

    effects = spec.get("effects")
    if not isinstance(effects, dict) or not effects:
        raise LevelError(f'switch {switch_id}: "effects" must name a bridge')
    parsed = []
    for bridge_id, effect in effects.items():
        if bridge_id not in bridge_ids:
            raise LevelError(f"switch {switch_id}: unknown bridge {bridge_id!r}")
        try:
            parsed.append((bridge_ids.index(bridge_id), Effect(effect)))
        except ValueError:
            raise LevelError(
                f"switch {switch_id}: effect must be toggle, open or close"
            ) from None
    return Switch(switch_id, cell, kind, effects=tuple(parsed))


def load_level(path: str | Path) -> Level:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LevelError(f"{path.name}: invalid JSON ({error})") from None
    try:
        return parse_level(data, path)
    except LevelError as error:
        raise LevelError(f"{path.name}: {error}") from None


def load_levels(directory: str | Path = LEVELS_DIR) -> list[Level]:
    """Load every ``*.json`` stage in `directory`, ordered by file name."""
    return [load_level(path) for path in sorted(Path(directory).glob("*.json"))]
