"""Pieces shared by every solver: the result record and path reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..game import Action, State

# state -> (previous state, action that led here); the start maps to None.
Parents = dict[State, tuple[State, Action] | None]


@dataclass
class SearchResult:
    algorithm: str
    solved: bool = False
    actions: list[Action] = field(default_factory=list)
    cost: int = 0  # path cost under the problem's cost model
    expanded: int = 0  # states whose successors were generated
    generated: int = 0  # successor states produced
    max_frontier: int = 0  # largest size the frontier reached
    time_s: float = 0.0  # search time, filled in by `solve`
    peak_memory_bytes: int | None = None  # peak traced memory, filled in by `solve`

    @property
    def length(self) -> int:
        """Solution length: the number of actions."""
        return len(self.actions)

    @property
    def moves(self) -> str:
        return "".join(action.value for action in self.actions)


def reconstruct(parents: Parents, state: State) -> list[Action]:
    """Walk the parent links back from `state` to the start."""
    actions = []
    while (link := parents[state]) is not None:
        state, action = link
        actions.append(action)
    actions.reverse()
    return actions
