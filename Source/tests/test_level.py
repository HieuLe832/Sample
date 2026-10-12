"""Stage loader: parsing and validation."""

import json
import tempfile
import unittest
from pathlib import Path

from bloxorz.level import (
    Effect,
    LevelError,
    SwitchKind,
    Tile,
    load_level,
    load_levels,
    parse_level,
)

FULL = {
    "name": "Demo",
    "group": "combined",
    "grid": ["S#1#aa#F", "#2....bG", "3#"],
    "bridges": {"b": "open"},
    "switches": {
        "1": {"type": "soft", "effects": {"a": "toggle", "b": "close"}},
        "2": {"type": "heavy", "effects": {"a": "open"}},
        "3": {"type": "split", "targets": [[0, 0], [0, 7]]},
    },
}


class Parsing(unittest.TestCase):
    def setUp(self):
        self.level = parse_level(FULL)

    def test_size_and_padding(self):
        # Short rows are padded with void cells.
        self.assertEqual((self.level.rows, self.level.cols), (3, 8))
        self.assertIs(self.level.tile((2, 5)), Tile.VOID)

    def test_tiles(self):
        level = self.level
        self.assertEqual(level.start, (0, 0))
        self.assertEqual(level.goal, (1, 7))
        self.assertIs(level.tile((0, 0)), Tile.FLOOR)
        self.assertIs(level.tile((1, 7)), Tile.GOAL)
        self.assertIs(level.tile((0, 7)), Tile.FRAGILE)
        self.assertIs(level.tile((0, 4)), Tile.BRIDGE)
        self.assertIs(level.tile((1, 3)), Tile.VOID)
        self.assertIs(level.tile((-1, 0)), Tile.VOID)
        self.assertIs(level.tile((0, 99)), Tile.VOID)

    def test_bridges(self):
        a, b = self.level.bridges
        self.assertEqual((a.id, a.cells, a.initially_open), ("a", ((0, 4), (0, 5)), False))
        self.assertEqual((b.id, b.cells, b.initially_open), ("b", ((1, 6),), True))
        self.assertEqual(self.level.initial_bridges, 0b10)

    def test_switches(self):
        soft = self.level.switches[(0, 2)]
        self.assertIs(soft.kind, SwitchKind.SOFT)
        self.assertEqual(soft.effects, ((0, Effect.TOGGLE), (1, Effect.CLOSE)))
        heavy = self.level.switches[(1, 1)]
        self.assertIs(heavy.kind, SwitchKind.HEAVY)
        self.assertEqual(heavy.effects, ((0, Effect.OPEN),))
        split = self.level.switches[(2, 0)]
        self.assertIs(split.kind, SwitchKind.SPLIT)
        self.assertEqual(split.targets, ((0, 0), (0, 7)))
        self.assertTrue(self.level.has_split)

    def test_switch_effects_on_the_mask(self):
        soft = self.level.switches[(0, 2)]
        self.assertEqual(soft.apply(0b10), 0b01)  # a toggled open, b closed
        self.assertEqual(soft.apply(0b01), 0b00)

    def test_relaxed_stage_has_every_bridge_open(self):
        relaxed = self.level.relaxed()
        self.assertIs(relaxed.tile((0, 4)), Tile.FLOOR)
        self.assertEqual(relaxed.bridges, ())
        self.assertEqual(list(relaxed.switches), [(2, 0)])  # only the split switch


class Validation(unittest.TestCase):
    def assert_rejected(self, message, **data):
        with self.assertRaisesRegex(LevelError, message):
            parse_level(data)

    def test_missing_pieces(self):
        with self.assertRaisesRegex(LevelError, "grid"):
            parse_level({})
        self.assert_rejected("no start", grid=["##G"])
        self.assert_rejected("no goal", grid=["S##"])
        self.assert_rejected("more than one start", grid=["SSG"])
        self.assert_rejected("more than one goal", grid=["SGG"])

    def test_unknown_character(self):
        self.assert_rejected("unknown grid character", grid=["S?G"])

    def test_switch_without_description(self):
        self.assert_rejected("no entry", grid=["S9G"])

    def test_description_without_switch(self):
        soft = {"type": "soft", "effects": {"a": "open"}}
        self.assert_rejected("switch '1' is not in the grid", grid=["SaG"], switches={"1": soft})
        self.assert_rejected("bridge 'a' is not in the grid", grid=["S#G"], bridges={"a": "open"})

    def test_bad_switch_fields(self):
        base = {"grid": ["S1aG"]}
        cases = {
            "type": {"type": "sticky", "effects": {"a": "open"}},
            "unknown bridge": {"type": "soft", "effects": {"z": "open"}},
            "effect must": {"type": "soft", "effects": {"a": "explode"}},
            "must name a bridge": {"type": "heavy"},
            "two cells": {"type": "split", "targets": [[0, 0]]},
            "must differ": {"type": "split", "targets": [[0, 0], [0, 0]]},
            "is void": {"type": "split", "targets": [[0, 0], [5, 5]]},
        }
        for message, spec in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(LevelError, message):
                    parse_level({**base, "switches": {"1": spec}})

    def test_bad_bridge_state(self):
        with self.assertRaisesRegex(LevelError, "open.*closed"):
            parse_level({"grid": ["SaG"], "bridges": {"a": "ajar"}})


class Files(unittest.TestCase):
    def test_bundled_stages_load(self):
        levels = load_levels()
        self.assertGreaterEqual(len(levels), 12)
        self.assertEqual(levels[0].name, "First Steps")

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.json"
            path.write_text(json.dumps(FULL), encoding="utf-8")
            level = load_level(path)
            self.assertEqual((level.name, level.group, level.path), ("Demo", "combined", path))

    def test_errors_name_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(LevelError, "broken.json"):
                load_level(path)
            path.write_text(json.dumps({"grid": ["S##"]}), encoding="utf-8")
            with self.assertRaisesRegex(LevelError, "broken.json: stage has no goal"):
                load_level(path)


if __name__ == "__main__":
    unittest.main()
