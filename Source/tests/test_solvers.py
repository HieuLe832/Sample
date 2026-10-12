"""Solvers: correctness on the bundled stages, optimality, and heuristics."""

import heapq
import unittest
from itertools import count

from bloxorz.game import is_goal, replay
from bloxorz.heuristics import HEURISTICS
from bloxorz.level import load_levels, parse_level
from bloxorz.problem import RISK_COST, UNIT_COST, Problem
from bloxorz.solvers import solve

LEVELS = load_levels()
CONFIGS = [
    ("bfs", "relaxed"),
    ("dfs", "relaxed"),
    ("ucs", "relaxed"),
    ("astar", "relaxed"),
    ("astar", "manhattan"),
]


def run(level, algorithm, heuristic="relaxed", cost_model=RISK_COST):
    return solve(
        level,
        algorithm,
        heuristic=heuristic,
        cost_model=cost_model,
        measure_memory=False,
    )


def true_costs(problem):
    """Cheapest cost to the goal from every state reachable from the start."""
    reverse = {problem.initial: []}
    stack = [problem.initial]
    goals = []
    while stack:
        state = stack.pop()
        if problem.is_goal(state):
            goals.append(state)
        for _action, child, cost in problem.successors(state):
            if child not in reverse:
                reverse[child] = []
                stack.append(child)
            reverse[child].append((state, cost))
    best = {goal: 0 for goal in goals}
    tie = count()
    queue = [(0, next(tie), goal) for goal in goals]
    while queue:
        d, _, state = heapq.heappop(queue)
        if d > best[state]:
            continue
        for previous, cost in reverse[state]:
            if d + cost < best.get(previous, float("inf")):
                best[previous] = d + cost
                heapq.heappush(queue, (d + cost, next(tie), previous))
    return reverse.keys(), best


class BundledStages(unittest.TestCase):
    def test_there_are_stages_in_every_group(self):
        groups = {level.group for level in LEVELS}
        self.assertEqual(groups, {"basic", "fragile", "switches", "combined"})

    def test_every_solver_solves_every_stage(self):
        for level in LEVELS:
            for algorithm, heuristic in CONFIGS:
                with self.subTest(level=level.name, algorithm=algorithm, h=heuristic):
                    result = run(level, algorithm, heuristic)
                    self.assertTrue(result.solved)
                    # The reported moves really lead to the goal...
                    final = replay(level, result.actions)
                    self.assertTrue(is_goal(level, final))
                    # ...and the reported cost is the cost of those moves.
                    self.assertEqual(result.cost, Problem(level).path_cost(result.actions))
                    self.assertGreater(result.expanded, 0)

    def test_bfs_finds_the_fewest_moves(self):
        for level in LEVELS:
            with self.subTest(level=level.name):
                shortest = run(level, "ucs", cost_model=UNIT_COST).cost
                self.assertEqual(run(level, "bfs").length, shortest)

    def test_ucs_and_astar_agree_on_the_optimal_cost(self):
        for cost_model in (RISK_COST, UNIT_COST):
            for level in LEVELS:
                with self.subTest(level=level.name, cost=cost_model.name):
                    optimal = run(level, "ucs", cost_model=cost_model).cost
                    for heuristic in ("relaxed", "manhattan", "zero"):
                        found = run(level, "astar", heuristic, cost_model).cost
                        self.assertEqual(found, optimal, heuristic)

    def test_no_solver_beats_the_optimal_cost(self):
        for level in LEVELS:
            optimal = run(level, "ucs").cost
            for algorithm in ("bfs", "dfs"):
                with self.subTest(level=level.name, algorithm=algorithm):
                    self.assertGreaterEqual(run(level, algorithm).cost, optimal)

    def test_risk_aware_cost_changes_the_chosen_path(self):
        # On "Risky Shortcut" the fewest-moves path crosses fragile tiles;
        # the cheapest path goes around them.
        level = next(level for level in LEVELS if level.name == "Risky Shortcut")
        shortest, cheapest = run(level, "bfs"), run(level, "ucs")
        self.assertLess(shortest.length, cheapest.length)
        self.assertLess(cheapest.cost, shortest.cost)

    def test_astar_expands_no_more_than_ucs(self):
        for level in LEVELS:
            with self.subTest(level=level.name):
                self.assertLessEqual(
                    run(level, "astar").expanded, run(level, "ucs").expanded
                )


class Heuristics(unittest.TestCase):
    def test_admissible_on_every_reachable_state(self):
        for cost_model in (RISK_COST, UNIT_COST):
            for level in LEVELS:
                problem = Problem(level, cost_model)
                states, best = true_costs(problem)
                for name in ("relaxed", "manhattan"):
                    h = HEURISTICS[name](problem)
                    with self.subTest(level=level.name, h=name, cost=cost_model.name):
                        for state in states:
                            self.assertLessEqual(h(state), best.get(state, float("inf")))

    def test_relaxed_heuristic_is_consistent(self):
        for level in LEVELS:
            problem = Problem(level)
            states, _ = true_costs(problem)
            h = HEURISTICS["relaxed"](problem)
            with self.subTest(level=level.name):
                for state in states:
                    for _action, child, cost in problem.successors(state):
                        self.assertLessEqual(h(state), cost + h(child))

    def test_heuristics_are_zero_at_the_goal(self):
        for level in LEVELS:
            problem = Problem(level)
            goal = replay(level, run(level, "bfs").actions)
            for name in ("relaxed", "manhattan"):
                with self.subTest(level=level.name, h=name):
                    self.assertEqual(HEURISTICS[name](problem)(goal), 0)

    def test_relaxed_heuristic_is_exact_without_bridges(self):
        level = LEVELS[0]
        problem = Problem(level)
        self.assertEqual(
            HEURISTICS["relaxed"](problem)(problem.initial), run(level, "ucs").cost
        )


class EdgeCases(unittest.TestCase):
    def test_unsolvable_stage_reports_no_solution(self):
        # The goal sits on an island the block cannot reach.
        level = parse_level({"grid": ["S##..G#", "###..##"]})
        for algorithm, heuristic in CONFIGS:
            with self.subTest(algorithm=algorithm, h=heuristic):
                result = run(level, algorithm, heuristic)
                self.assertFalse(result.solved)
                self.assertEqual(result.actions, [])

    def test_solving_from_a_mid_game_state(self):
        level = LEVELS[0]
        full = run(level, "bfs")
        midway = replay(level, full.actions[:3])
        for algorithm, heuristic in CONFIGS:
            with self.subTest(algorithm=algorithm, h=heuristic):
                result = solve(
                    level, algorithm, start=midway, heuristic=heuristic,
                    measure_memory=False,
                )
                self.assertTrue(is_goal(level, replay(level, result.actions, midway)))
        rest = solve(level, "bfs", start=midway, measure_memory=False)
        self.assertEqual(rest.length, full.length - 3)

    def test_measurements_are_recorded(self):
        result = solve(LEVELS[0], "astar")
        self.assertGreater(result.time_s, 0)
        self.assertGreater(result.peak_memory_bytes, 0)
        self.assertGreater(result.generated, result.expanded)
        self.assertGreater(result.max_frontier, 0)

    def test_unknown_names_are_rejected(self):
        with self.assertRaises(ValueError):
            solve(LEVELS[0], "greedy")
        with self.assertRaises(ValueError):
            solve(LEVELS[0], "astar", heuristic="euclid")


if __name__ == "__main__":
    unittest.main()
