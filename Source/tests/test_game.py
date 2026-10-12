"""Rules of the game: orientation transitions, illegal moves, tiles, switches."""

import unittest

from bloxorz.game import (
    Action,
    MoveStatus,
    Orientation,
    State,
    block_cells,
    initial_state,
    is_goal,
    move,
    replay,
)
from bloxorz.level import parse_level

UP, DOWN, LEFT, RIGHT, SWAP = (
    Action.UP,
    Action.DOWN,
    Action.LEFT,
    Action.RIGHT,
    Action.SWAP,
)
STANDING, HORIZONTAL, VERTICAL = (
    Orientation.STANDING,
    Orientation.HORIZONTAL,
    Orientation.VERTICAL,
)


def make(grid, **extra):
    return parse_level({"grid": grid, **extra})


def placed(anchor, orientation, bridges=0):
    cells = block_cells(anchor, orientation)
    return State(cells[0], cells[-1], False, bridges)


# 9x9 of floor with the start in the middle; the goal is out of the way.
OPEN = make(
    [
        "#########",
        "#########",
        "#########",
        "#########",
        "####S####",
        "#########",
        "#########",
        "#########",
        "########G",
    ]
)


class OrientationTransitions(unittest.TestCase):
    # (orientation, action) -> cells occupied afterwards, starting at (4, 4).
    EXPECTED = {
        (STANDING, UP): {(2, 4), (3, 4)},
        (STANDING, DOWN): {(5, 4), (6, 4)},
        (STANDING, LEFT): {(4, 2), (4, 3)},
        (STANDING, RIGHT): {(4, 5), (4, 6)},
        (HORIZONTAL, UP): {(3, 4), (3, 5)},
        (HORIZONTAL, DOWN): {(5, 4), (5, 5)},
        (HORIZONTAL, LEFT): {(4, 3)},
        (HORIZONTAL, RIGHT): {(4, 6)},
        (VERTICAL, UP): {(3, 4)},
        (VERTICAL, DOWN): {(6, 4)},
        (VERTICAL, LEFT): {(4, 3), (5, 3)},
        (VERTICAL, RIGHT): {(4, 5), (5, 5)},
    }

    def test_every_orientation_and_direction(self):
        for (orientation, action), cells in self.EXPECTED.items():
            with self.subTest(orientation=orientation, action=action):
                result = move(OPEN, placed((4, 4), orientation), action)
                self.assertIs(result.status, MoveStatus.OK)
                self.assertEqual(set(result.state.cells), cells)

    def test_new_orientation(self):
        expected = {
            (STANDING, UP): VERTICAL,
            (STANDING, RIGHT): HORIZONTAL,
            (HORIZONTAL, LEFT): STANDING,
            (HORIZONTAL, UP): HORIZONTAL,
            (VERTICAL, DOWN): STANDING,
            (VERTICAL, RIGHT): VERTICAL,
        }
        for (orientation, action), after in expected.items():
            with self.subTest(orientation=orientation, action=action):
                state = move(OPEN, placed((4, 4), orientation), action).state
                self.assertIs(state.orientation, after)

    def test_opposite_roll_undoes_a_roll(self):
        opposite = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}
        for orientation in (STANDING, HORIZONTAL, VERTICAL):
            for action, back in opposite.items():
                with self.subTest(orientation=orientation, action=action):
                    start = placed((4, 4), orientation)
                    there = move(OPEN, start, action).state
                    self.assertEqual(move(OPEN, there, back).state, start)

    def test_anchor_is_the_top_left_cell(self):
        state = move(OPEN, placed((4, 4), STANDING), LEFT).state
        self.assertEqual((state.a, state.b), ((4, 2), (4, 3)))
        state = move(OPEN, placed((4, 4), STANDING), UP).state
        self.assertEqual((state.a, state.b), ((2, 4), (3, 4)))


class IllegalMovesAndVictory(unittest.TestCase):
    LEVEL = make(["S#G", "#.#"])

    def test_rolling_off_the_board_is_illegal(self):
        start = initial_state(self.LEVEL)
        self.assertIs(move(self.LEVEL, start, UP).status, MoveStatus.FELL)
        self.assertIs(move(self.LEVEL, start, LEFT).status, MoveStatus.FELL)

    def test_half_over_a_void_is_illegal(self):
        # Lying on (0,1)-(0,2), rolling down would put one half over the void.
        lying = placed((0, 1), HORIZONTAL)
        self.assertIs(move(self.LEVEL, lying, DOWN).status, MoveStatus.FELL)

    def test_illegal_move_reports_no_state(self):
        result = move(self.LEVEL, initial_state(self.LEVEL), UP)
        self.assertIsNone(result.state)

    def test_only_standing_on_the_goal_wins(self):
        level = make(["S##G##"])
        lying_over_goal = placed((0, 2), HORIZONTAL)
        self.assertFalse(is_goal(level, lying_over_goal))
        standing = move(level, placed((0, 1), HORIZONTAL), RIGHT).state
        self.assertEqual(standing.cells, ((0, 3),))
        self.assertTrue(is_goal(level, standing))

    def test_start_is_standing_on_the_start_tile(self):
        state = initial_state(self.LEVEL)
        self.assertEqual(state, State((0, 0), (0, 0), False, 0))
        self.assertIs(state.orientation, STANDING)

    def test_swap_does_nothing_for_a_whole_block(self):
        result = move(self.LEVEL, initial_state(self.LEVEL), SWAP)
        self.assertIs(result.status, MoveStatus.INVALID)

    def test_replay_rejects_an_illegal_sequence(self):
        with self.assertRaises(ValueError):
            replay(self.LEVEL, [UP])


class FragileTiles(unittest.TestCase):
    #              01234567
    LEVEL = make(["S##FF##G"])

    def test_standing_on_a_fragile_tile_breaks_it(self):
        lying = replay(self.LEVEL, [RIGHT])  # on (0,1)-(0,2)
        result = move(self.LEVEL, lying, RIGHT)  # would stand up on (0,3)
        self.assertIs(result.status, MoveStatus.BROKE)
        self.assertIsNone(result.state)

    def test_lying_on_two_fragile_tiles_is_safe(self):
        result = move(self.LEVEL, placed((0, 2), STANDING), RIGHT)
        self.assertIs(result.status, MoveStatus.OK)
        self.assertEqual(result.state.cells, ((0, 3), (0, 4)))

    def test_lying_half_on_a_fragile_tile_is_safe(self):
        result = move(self.LEVEL, placed((0, 1), STANDING), RIGHT)
        self.assertIs(result.status, MoveStatus.OK)
        self.assertEqual(result.state.cells, ((0, 2), (0, 3)))


class Bridges(unittest.TestCase):
    def level(self, effect, initially="closed", kind="soft"):
        return make(
            ["S#1#aa##G"],
            bridges={"a": initially},
            switches={"1": {"type": kind, "effects": {"a": effect}}},
        )

    def test_closed_bridge_is_a_void(self):
        level = self.level("toggle")
        self.assertFalse(level.supports((0, 4), 0))
        self.assertTrue(level.supports((0, 4), 1))
        # Standing on (0,3) with the bridge closed, rolling right falls.
        result = move(level, placed((0, 3), STANDING), RIGHT)
        self.assertIs(result.status, MoveStatus.FELL)
        result = move(level, placed((0, 3), STANDING, bridges=1), RIGHT)
        self.assertIs(result.status, MoveStatus.OK)

    def test_bridge_configuration_is_part_of_the_state(self):
        closed = placed((0, 3), STANDING, bridges=0)
        opened = placed((0, 3), STANDING, bridges=1)
        self.assertNotEqual(closed, opened)
        self.assertEqual(len({closed, opened}), 2)

    def test_initial_bridge_state_comes_from_the_stage(self):
        self.assertEqual(initial_state(self.level("toggle", "open")).bridges, 1)
        self.assertEqual(initial_state(self.level("toggle", "closed")).bridges, 0)

    def test_soft_switch_fires_when_the_block_lies_on_it(self):
        level = self.level("toggle")
        state = replay(level, [RIGHT])  # lying on (0,1)-(0,2), switch at (0,2)
        self.assertEqual(state.bridges, 1)

    def test_soft_switch_fires_when_the_block_stands_on_it(self):
        level = self.level("toggle")
        result = move(level, placed((0, 0), HORIZONTAL), RIGHT)
        self.assertEqual(result.state.cells, ((0, 2),))
        self.assertEqual(result.state.bridges, 1)

    def test_heavy_switch_needs_the_block_standing(self):
        level = self.level("toggle", kind="heavy")
        lying = replay(level, [RIGHT])
        self.assertEqual(lying.bridges, 0)
        standing = move(level, placed((0, 0), HORIZONTAL), RIGHT).state
        self.assertEqual(standing.bridges, 1)

    def test_toggle_flips_on_every_activation(self):
        level = self.level("toggle")
        once = replay(level, [RIGHT])
        self.assertEqual(once.bridges, 1)
        twice = replay(level, [RIGHT, LEFT, RIGHT])
        self.assertEqual(twice.bridges, 0)

    def test_permanent_open_stays_open(self):
        level = self.level("open")
        self.assertEqual(replay(level, [RIGHT]).bridges, 1)
        self.assertEqual(replay(level, [RIGHT, LEFT, RIGHT]).bridges, 1)

    def test_permanent_close_stays_closed(self):
        level = self.level("close", initially="open")
        self.assertEqual(replay(level, [RIGHT]).bridges, 0)
        self.assertEqual(replay(level, [RIGHT, LEFT, RIGHT]).bridges, 0)

    def test_one_switch_can_drive_several_bridges(self):
        level = make(
            ["S#1#aabb#G"],
            bridges={"a": "closed", "b": "open"},
            switches={"1": {"type": "soft", "effects": {"a": "toggle", "b": "toggle"}}},
        )
        self.assertEqual(initial_state(level).bridges, 0b10)
        self.assertEqual(replay(level, [RIGHT]).bridges, 0b01)

    def test_closing_the_bridge_under_the_block_is_illegal(self):
        # Lying on the switch (0,2) and the open bridge tile (0,3).
        level = make(
            ["S#1a#G"],
            bridges={"a": "open"},
            switches={"1": {"type": "soft", "effects": {"a": "close"}}},
        )
        result = move(level, placed((0, 1), STANDING, bridges=1), RIGHT)
        self.assertEqual(result.landed, ((0, 2), (0, 3)))
        self.assertIs(result.status, MoveStatus.FELL)


class Splitting(unittest.TestCase):
    #          0123456
    GRID = [
        "S#1####",  # split switch at (0, 2)
        "#######",
        "##2#3#G",  # soft switch 2 at (2, 2), heavy switch 3 at (2, 4)
        "###a###",
    ]

    def level(self, targets=((1, 0), (1, 6))):
        return make(
            self.GRID,
            bridges={"a": "closed"},
            switches={
                "1": {"type": "split", "targets": [list(t) for t in targets]},
                "2": {"type": "soft", "effects": {"a": "toggle"}},
                "3": {"type": "heavy", "effects": {"a": "toggle"}},
            },
        )

    @staticmethod
    def split_state(level, a, b, bridges=0):
        return State(a, b, True, bridges)

    def test_split_switch_needs_the_block_standing(self):
        level = self.level()
        lying = replay(level, [RIGHT])  # lying on (0,1)-(0,2)
        self.assertFalse(lying.split)

    def test_standing_on_the_split_switch_teleports_two_cubes(self):
        level = self.level()
        state = move(level, placed((0, 0), HORIZONTAL), RIGHT).state
        self.assertTrue(state.split)
        self.assertIs(state.orientation, Orientation.SPLIT)
        self.assertEqual((state.a, state.b), ((1, 0), (1, 6)))

    def test_only_the_controlled_cube_moves(self):
        level = self.level()
        state = self.split_state(level, (1, 0), (1, 6))
        after = move(level, state, RIGHT).state
        self.assertEqual((after.a, after.b), ((1, 1), (1, 6)))

    def test_swap_changes_the_controlled_cube(self):
        level = self.level()
        state = self.split_state(level, (1, 0), (1, 6))
        swapped = move(level, state, SWAP).state
        self.assertEqual((swapped.a, swapped.b), ((1, 6), (1, 0)))
        after = move(level, swapped, LEFT).state
        self.assertEqual((after.a, after.b), ((1, 5), (1, 0)))

    def test_cube_falls_like_the_block(self):
        level = self.level()
        state = self.split_state(level, (1, 0), (1, 6))
        self.assertIs(move(level, state, LEFT).status, MoveStatus.FELL)

    def test_cubes_merge_side_by_side(self):
        level = self.level()
        state = self.split_state(level, (1, 2), (1, 4))
        merged = move(level, state, RIGHT).state
        self.assertFalse(merged.split)
        self.assertIs(merged.orientation, HORIZONTAL)
        self.assertEqual((merged.a, merged.b), ((1, 3), (1, 4)))

    def test_cubes_merge_one_above_the_other(self):
        level = self.level()
        state = self.split_state(level, (2, 5), (0, 4))
        apart = move(level, state, LEFT).state  # (2,4) is two rows from (0,4)
        self.assertTrue(apart.split)
        merged = move(level, self.split_state(level, (1, 5), (0, 4)), LEFT).state
        self.assertFalse(merged.split)
        self.assertIs(merged.orientation, VERTICAL)
        self.assertEqual((merged.a, merged.b), ((0, 4), (1, 4)))

    def test_diagonal_cubes_do_not_merge(self):
        level = self.level()
        state = self.split_state(level, (0, 3), (1, 5))
        after = move(level, state, RIGHT).state  # (0,4) and (1,5) touch by a corner
        self.assertTrue(after.split)

    def test_adjacent_targets_merge_immediately(self):
        level = self.level(targets=((1, 3), (1, 4)))
        state = move(level, placed((0, 0), HORIZONTAL), RIGHT).state
        self.assertFalse(state.split)
        self.assertEqual(state.cells, ((1, 3), (1, 4)))

    def test_cube_presses_soft_switch(self):
        level = self.level()
        state = self.split_state(level, (2, 1), (0, 6))
        self.assertEqual(move(level, state, RIGHT).state.bridges, 1)

    def test_cube_cannot_press_heavy_switch(self):
        level = self.level()
        state = self.split_state(level, (2, 3), (0, 6))
        after = move(level, state, RIGHT).state
        self.assertEqual(after.a, (2, 4))
        self.assertEqual(after.bridges, 0)

    def test_cube_cannot_use_split_switch(self):
        level = self.level()
        state = self.split_state(level, (0, 1), (2, 6))
        after = move(level, state, RIGHT).state
        self.assertEqual((after.a, after.b), ((0, 2), (2, 6)))

    def test_cube_on_the_goal_does_not_win(self):
        level = self.level()
        state = self.split_state(level, (2, 5), (0, 0))
        on_goal = move(level, state, RIGHT).state
        self.assertEqual(on_goal.a, (2, 6))
        self.assertFalse(is_goal(level, on_goal))

    def test_cube_may_rest_on_a_fragile_tile(self):
        level = make(
            ["S1#F#G"],
            switches={"1": {"type": "split", "targets": [[0, 2], [0, 5]]}},
        )
        state = State((0, 2), (0, 5), True, 0)
        self.assertIs(move(level, state, RIGHT).status, MoveStatus.OK)

    def test_waiting_cube_falls_when_its_bridge_closes(self):
        level = self.level()
        # The other cube waits on the open bridge tile (3, 3); pressing the
        # soft switch closes it.
        state = self.split_state(level, (2, 1), (3, 3), bridges=1)
        self.assertIs(move(level, state, RIGHT).status, MoveStatus.FELL)


if __name__ == "__main__":
    unittest.main()
