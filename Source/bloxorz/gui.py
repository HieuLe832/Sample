"""Pygame front end: play stages by hand and replay the solvers' solutions.

The view is a top-down board with a little depth: tiles are slabs and the
block is drawn as a box whose top face is shifted up by its height, so a
standing block looks taller than a lying one.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

import pygame

from .game import Action, MoveStatus, State, initial_state, is_goal, move
from .level import Cell, Level, SwitchKind, Tile
from .problem import RISK_COST, CostModel
from .solvers import SearchResult, solve

WINDOW_SIZE = (1200, 760)
SIDEBAR_WIDTH = 330
HEADER_HEIGHT = 64
STATUS_HEIGHT = 48
LEGEND_HEIGHT = 38
MAX_TILE = 64
SPEEDS = (1, 2, 4, 8, 16, 32, 64)  # solution replay speed, moves per second

BACKGROUND = (24, 28, 40)
PANEL = (33, 38, 54)
PANEL_LINE = (58, 66, 92)
TEXT = (232, 236, 244)
MUTED = (150, 160, 184)
ACCENT = (96, 165, 250)
GOOD = (74, 222, 128)
BAD = (248, 113, 113)

FLOOR_TOP, FLOOR_SIDE = (214, 219, 228), (128, 137, 156)
FRAGILE_TOP, FRAGILE_SIDE = (245, 158, 66), (171, 98, 28)
HOLE_OUTER, HOLE_INNER = (12, 14, 20), (0, 0, 0)
SYMBOL = (52, 58, 76)
BLOCK_TOP, BLOCK_SIDE = (66, 135, 245), (32, 78, 168)
IDLE_TOP, IDLE_SIDE = (124, 152, 204), (74, 96, 140)
LOST_TOP, LOST_SIDE = (239, 68, 68), (153, 27, 27)
# One colour per bridge, shared by the bridge tiles and the switches linked to it.
BRIDGE_COLORS = (
    (45, 212, 191),
    (167, 139, 250),
    (244, 114, 182),
    (163, 230, 53),
    (250, 204, 21),
    (56, 189, 248),
)

ROLL_KEYS = {
    pygame.K_UP: Action.UP,
    pygame.K_w: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_s: Action.DOWN,
    pygame.K_LEFT: Action.LEFT,
    pygame.K_a: Action.LEFT,
    pygame.K_RIGHT: Action.RIGHT,
    pygame.K_d: Action.RIGHT,
    pygame.K_SPACE: Action.SWAP,
}
SOLVER_KEYS = {
    pygame.K_1: "bfs",
    pygame.K_2: "dfs",
    pygame.K_3: "ucs",
    pygame.K_4: "astar",
}

# A box on the board: (top row, left column, bottom row, right column, height),
# in tile units. Fractional values appear while a roll is being animated.
Box = tuple[float, float, float, float, float]


def cell_box(cell: Cell, height: float = 1) -> Box:
    r, c = cell
    return (r, c, r + 1, c + 1, height)


def cells_box(cells: tuple[Cell, ...], whole_block: bool) -> Box:
    """Box covering one or two cells; a whole block on one cell stands 2 high."""
    (r0, c0), (r1, c1) = cells[0], cells[-1]
    height = 2 if whole_block and len(cells) == 1 else 1
    return (r0, c0, r1 + 1, c1 + 1, height)


def state_boxes(state: State) -> list[Box]:
    if state.split:
        return [cell_box(state.a), cell_box(state.b)]
    return [cells_box(state.cells, whole_block=True)]


def shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)


@dataclass
class Button:
    rect: pygame.Rect
    label: str | Callable[[], str]
    action: Callable[[], None]
    enabled: Callable[[], bool] = lambda: True

    @property
    def text(self) -> str:
        return self.label() if callable(self.label) else self.label


@dataclass
class Animation:
    start: list[Box]
    end: list[Box]
    began: float
    duration: float


class App:
    def __init__(
        self,
        levels: list[Level],
        level_index: int = 0,
        heuristic: str = "manhattan",
        cost_model: CostModel = RISK_COST,
    ) -> None:
        if not levels:
            raise ValueError("no stages to play")
        pygame.init()
        pygame.display.set_caption("Bloxorz Solver")
        self.screen = pygame.display.set_mode(WINDOW_SIZE)
        self.font = pygame.font.Font(None, 24)
        self.small = pygame.font.Font(None, 20)
        self.tiny = pygame.font.Font(None, 16)
        self.big = pygame.font.Font(None, 40)
        self.title = pygame.font.Font(None, 30)

        self.levels = levels
        self.heuristic = heuristic
        self.cost_model = cost_model
        self.now = 0.0  # seconds since start, advanced by update()
        self.running = True
        self.speed_index = 2

        self.solver_thread: threading.Thread | None = None
        self.solver_name = ""
        self.solver_output: list[SearchResult] = []
        self.result: SearchResult | None = None

        self.buttons = self._build_buttons()
        self.load_level(level_index)

    # ------------------------------------------------------------------ game

    def load_level(self, index: int) -> None:
        self.level_index = index % len(self.levels)
        self.level = self.levels[self.level_index]
        self.result = None
        self._layout_board()
        self.restart()

    def restart(self) -> None:
        self.state = initial_state(self.level)
        self.status = "playing"  # "playing", "won" or "lost"
        self.moves = 0
        self.lost_boxes: list[Box] = []
        self.finished_at = 0.0
        self.animation: Animation | None = None
        self.solution: list[Action] = []
        self.solution_pos = 0
        self.playing = False
        self.play_timer = 0.0
        self.message = "Roll the block into the hole. Arrow keys or WASD to move."
        self.message_color = MUTED

    def new_game(self) -> None:
        self.load_level(0)

    def apply(self, action: Action) -> None:
        """Play one action and update the win/lose status."""
        if self.status != "playing":
            return
        result = move(self.level, self.state, action)
        if result.status is MoveStatus.INVALID:
            return
        previous = self.state
        self.moves += 1

        if result.status is not MoveStatus.OK:
            self.status = "lost"
            self.finished_at = self.now
            self.playing = False
            self.lost_boxes = [cells_box(result.landed, not previous.split)]
            if previous.split:
                self.lost_boxes.append(cell_box(previous.b))
            self._animate(state_boxes(previous), self.lost_boxes)
            if result.status is MoveStatus.BROKE:
                text = "The fragile tile broke under the standing block!"
            else:
                text = "The block fell off the board!"
            self._say(f"{text} Press R to restart.", BAD)
            return

        self.state = result.state
        self._animate(state_boxes(previous), state_boxes(self.state))
        if is_goal(self.level, self.state):
            self.status = "won"
            self.finished_at = self.now
            self.playing = False
            self._say(
                f"Stage complete in {self.moves} moves! Press Enter for the next stage.",
                GOOD,
            )
        elif self.state.split and not previous.split:
            self._say("The block split in two. Press Space to switch cubes.", ACCENT)
        elif previous.split and not self.state.split:
            self._say("The cubes merged back into one block.", ACCENT)
        elif self.state.bridges != previous.bridges:
            changed = self.state.bridges ^ previous.bridges
            parts = [
                f"{bridge.id} {'opened' if self.state.bridges >> i & 1 else 'closed'}"
                for i, bridge in enumerate(self.level.bridges)
                if changed >> i & 1
            ]
            self._say("Switch pressed: bridge " + ", bridge ".join(parts) + ".", ACCENT)

    def player_move(self, action: Action) -> None:
        """A move made by hand cancels any solution being replayed."""
        if self.solver_thread is not None:
            return
        self.solution = []
        self.playing = False
        self.apply(action)

    def _say(self, message: str, color: tuple[int, int, int] = MUTED) -> None:
        self.message = message
        self.message_color = color

    def _animate(self, start: list[Box], end: list[Box]) -> None:
        # Splitting and merging change the number of boxes: no tween for those.
        if len(start) != len(end) or start == end:
            self.animation = None
            return
        duration = min(0.12, 0.6 / SPEEDS[self.speed_index]) if self.playing else 0.1
        self.animation = Animation(start, end, self.now, duration)

    # --------------------------------------------------------------- solvers

    def start_solver(self, algorithm: str) -> None:
        """Solve from the current position in a background thread."""
        if self.solver_thread is not None:
            return
        if self.status != "playing":
            self.restart()
        self.solution = []
        self.playing = False
        self.solver_name = "A*" if algorithm == "astar" else algorithm.upper()
        self.solver_output = []
        level, start = self.level, self.state

        def work() -> None:
            self.solver_output.append(
                solve(
                    level,
                    algorithm,
                    start=start,
                    cost_model=self.cost_model,
                    heuristic=self.heuristic,
                )
            )

        self.solver_thread = threading.Thread(target=work, daemon=True)
        self.solver_thread.start()
        self._say(f"Solving with {self.solver_name}...", ACCENT)

    def _collect_solver(self) -> None:
        thread = self.solver_thread
        if thread is None or thread.is_alive():
            return
        self.solver_thread = None
        if not self.solver_output:
            self._say(f"{self.solver_name} failed; see the console.", BAD)
            return
        self.result = self.solver_output.pop()
        if not self.result.solved:
            self._say(f"{self.solver_name}: no solution from this position.", BAD)
            return
        self.solution = list(self.result.actions)
        self.solution_pos = 0
        self.playing = True
        self.play_timer = 0.0
        self._say(
            f"{self.solver_name} found a solution of {self.result.length} moves. "
            "Replaying it...",
            GOOD,
        )

    def step_solution(self) -> None:
        if self.solution_pos < len(self.solution) and self.status == "playing":
            self.apply(self.solution[self.solution_pos])
            self.solution_pos += 1
        if self.solution_pos >= len(self.solution):
            self.playing = False

    def toggle_play(self) -> None:
        if self._has_solution_left():
            self.playing = not self.playing
            self.play_timer = 0.0

    def change_speed(self, delta: int) -> None:
        self.speed_index = max(0, min(len(SPEEDS) - 1, self.speed_index + delta))

    def _has_solution_left(self) -> bool:
        return self.status == "playing" and self.solution_pos < len(self.solution)

    def _idle(self) -> bool:
        return self.solver_thread is None

    # ------------------------------------------------------------- main loop

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = clock.tick(60) / 1000
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.rect.collidepoint(event.pos) and button.enabled():
                    button.action()
                    break
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
        elif not self._idle():
            return
        elif key in ROLL_KEYS:
            self.player_move(ROLL_KEYS[key])
        elif key in SOLVER_KEYS:
            self.start_solver(SOLVER_KEYS[key])
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_n:
            self.new_game()
        elif key in (pygame.K_RIGHTBRACKET, pygame.K_PAGEDOWN):
            self.load_level(self.level_index + 1)
        elif key in (pygame.K_LEFTBRACKET, pygame.K_PAGEUP):
            self.load_level(self.level_index - 1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.status == "won":
            self.load_level(self.level_index + 1)
        elif key == pygame.K_p:
            self.toggle_play()
        elif key == pygame.K_PERIOD:
            self.step_solution()
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.change_speed(1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_speed(-1)

    def update(self, dt: float) -> None:
        self.now += dt
        self._collect_solver()
        if self.playing:
            interval = 1 / SPEEDS[self.speed_index]
            self.play_timer += dt
            while self.playing and self.play_timer >= interval:
                self.play_timer -= interval
                self.step_solution()

    # --------------------------------------------------------------- layout

    def _build_buttons(self) -> list[Button]:
        left = WINDOW_SIZE[0] - SIDEBAR_WIDTH + 20
        width = SIDEBAR_WIDTH - 40
        half = (width - 10) // 2
        idle = self._idle

        def at(column: int, y: int, columns: int = 2, height: int = 36) -> pygame.Rect:
            w = half if columns == 2 else (width - 30) // 4
            return pygame.Rect(left + column * (w + 10), y, w, height)

        return [
            Button(at(0, 108), "< Prev stage", lambda: self.load_level(self.level_index - 1), idle),
            Button(at(1, 108), "Next stage >", lambda: self.load_level(self.level_index + 1), idle),
            Button(at(0, 152), "New Game (N)", self.new_game, idle),
            Button(at(1, 152), "Restart (R)", self.restart, idle),
            Button(at(0, 232), "Solve BFS (1)", lambda: self.start_solver("bfs"), idle),
            Button(at(1, 232), "Solve DFS (2)", lambda: self.start_solver("dfs"), idle),
            Button(at(0, 276), "Solve UCS (3)", lambda: self.start_solver("ucs"), idle),
            Button(at(1, 276), "Solve A* (4)", lambda: self.start_solver("astar"), idle),
            Button(
                at(0, 320, 4, 30),
                lambda: "Pause" if self.playing else "Play",
                self.toggle_play,
                self._has_solution_left,
            ),
            Button(at(1, 320, 4, 30), "Step", self.step_solution, self._has_solution_left),
            Button(at(2, 320, 4, 30), "Slower", lambda: self.change_speed(-1)),
            Button(at(3, 320, 4, 30), "Faster", lambda: self.change_speed(1)),
        ]

    def _layout_board(self) -> None:
        """Pick the tile size and origin so the stage is centred in its area."""
        area_w = WINDOW_SIZE[0] - SIDEBAR_WIDTH - 48
        area_h = WINDOW_SIZE[1] - HEADER_HEIGHT - STATUS_HEIGHT - LEGEND_HEIGHT - 32
        level = self.level
        # One spare row: the standing block rises above row 0, and the bottom
        # row of tiles has a visible side.
        self.tile = int(min(MAX_TILE, area_w / level.cols, area_h / (level.rows + 1.2)))
        self.lift = self.tile * 0.42  # pixels per unit of block height
        self.origin_x = 24 + (area_w - self.tile * level.cols) // 2
        used_h = self.tile * (level.rows + 1.2)
        self.origin_y = HEADER_HEIGHT + 16 + (area_h - used_h) // 2 + self.tile

    def _cell_rect(self, r: int, c: int) -> pygame.Rect:
        tile = self.tile
        return pygame.Rect(self.origin_x + c * tile, self.origin_y + r * tile, tile, tile)

    # -------------------------------------------------------------- drawing

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        self._draw_header()
        self._draw_board()
        self._draw_block()
        self._draw_status()
        self._draw_sidebar()

    def _text(self, text, pos, font=None, color=TEXT, right=False) -> pygame.Rect:
        surface = (font or self.font).render(text, True, color)
        rect = surface.get_rect()
        if right:
            rect.topright = pos
        else:
            rect.topleft = pos
        self.screen.blit(surface, rect)
        return rect

    def _draw_header(self) -> None:
        level = self.level
        self._text(
            f"Stage {self.level_index + 1}/{len(self.levels)}: {level.name}",
            (24, 18),
            self.title,
        )
        self._text(f"group: {level.group}", (24, 44), self.small, MUTED)
        right = WINDOW_SIZE[0] - SIDEBAR_WIDTH - 24
        self._text(f"Moves: {self.moves}", (right, 18), self.title, right=True)
        self._text(
            f"block: {self.state.orientation.value}", (right, 44), self.small, MUTED, right=True
        )

    def _draw_status(self) -> None:
        y = WINDOW_SIZE[1] - STATUS_HEIGHT
        width = WINDOW_SIZE[0] - SIDEBAR_WIDTH
        pygame.draw.rect(self.screen, PANEL, (0, y, width, STATUS_HEIGHT))
        pygame.draw.line(self.screen, PANEL_LINE, (0, y), (width, y))
        self._text(self.message, (24, y + 15), self.font, self.message_color)
        self._draw_legend(24, y - LEGEND_HEIGHT + 6)

    def _draw_board(self) -> None:
        level, tile = self.level, self.tile
        side = max(4, round(tile * 0.16))
        radius = max(2, tile // 10)
        open_mask = self.state.bridges
        switch_color = {}
        for cell, switch in level.switches.items():
            index = switch.effects[0][0] if switch.effects else None
            switch_color[cell] = (
                SYMBOL if index is None
                else shade(BRIDGE_COLORS[index % len(BRIDGE_COLORS)], 0.55)
            )

        for r in range(level.rows):
            for c in range(level.cols):
                kind = level.tiles[r][c]
                if kind is Tile.VOID:
                    continue
                rect = self._cell_rect(r, c)
                top = rect.inflate(-2, -2)
                label = None

                if kind is Tile.GOAL:
                    self._slab(top, FLOOR_TOP, FLOOR_SIDE, side, radius)
                    hole = top.inflate(-6, -6)
                    pygame.draw.rect(self.screen, HOLE_OUTER, hole, border_radius=radius)
                    pygame.draw.rect(
                        self.screen, HOLE_INNER, hole.inflate(-8, -8).move(0, 3),
                        border_radius=radius,
                    )
                    continue

                if kind is Tile.BRIDGE:
                    index = level.bridge_at[(r, c)]
                    color = BRIDGE_COLORS[index % len(BRIDGE_COLORS)]
                    label = level.bridges[index].id
                    if not open_mask >> index & 1:
                        # Closed bridge: only a faint outline of where it will be.
                        pygame.draw.rect(
                            self.screen, shade(color, 0.45), top.inflate(-6, -6), 2,
                            border_radius=radius,
                        )
                        self._tile_label(label, top, shade(color, 0.7))
                        continue
                    top_color, side_color = color, shade(color, 0.6)
                elif kind is Tile.FRAGILE:
                    top_color, side_color = FRAGILE_TOP, FRAGILE_SIDE
                else:
                    top_color, side_color = FLOOR_TOP, FLOOR_SIDE

                self._slab(top, top_color, side_color, side, radius)
                if kind is Tile.FRAGILE:
                    # A crack pattern so fragile tiles are not told apart by colour alone.
                    inner = top.inflate(-tile // 2, -tile // 2)
                    pygame.draw.line(self.screen, FRAGILE_SIDE, inner.topleft, inner.center, 2)
                    pygame.draw.line(self.screen, FRAGILE_SIDE, inner.center, inner.midright, 2)
                    pygame.draw.line(self.screen, FRAGILE_SIDE, inner.center, inner.midbottom, 2)
                if label:
                    self._tile_label(label, top, shade(top_color, 0.45))

                switch = level.switches.get((r, c))
                if switch is not None:
                    self._draw_switch(switch.kind, top, switch_color[(r, c)])
                    self._tile_label(switch.id, top, switch_color[(r, c)])

    def _slab(self, top: pygame.Rect, top_color, side_color, side: int, radius: int) -> None:
        """A tile: its front edge peeks out below the top face."""
        pygame.draw.rect(self.screen, side_color, top.move(0, side), border_radius=radius)
        pygame.draw.rect(self.screen, top_color, top, border_radius=radius)

    def _tile_label(self, label: str, rect: pygame.Rect, color) -> None:
        if self.tile >= 28:
            font = self.small if self.tile >= 48 else self.tiny
            self._text(label, (rect.x + 3, rect.y + 2), font, color)

    def _draw_switch(self, kind: SwitchKind, rect: pygame.Rect, color) -> None:
        """Soft: ring. Heavy: X. Split: a pair of brackets."""
        size = rect.width
        width = max(3, size // 10)
        centre = rect.center
        reach = round(size * 0.25)
        centre = (centre[0] + size // 16, centre[1] + size // 16)  # leave room for the label
        if kind is SwitchKind.SOFT:
            pygame.draw.circle(self.screen, color, centre, reach, width)
        elif kind is SwitchKind.HEAVY:
            x, y = centre
            for dy in (reach, -reach):
                pygame.draw.line(
                    self.screen, color, (x - reach, y - dy), (x + reach, y + dy), width + 1
                )
        else:
            box = pygame.Rect(0, 0, reach * 2, reach * 2)
            box.center = centre
            pygame.draw.arc(self.screen, color, box.move(-reach // 3, 0), 2.0, 4.28, width)
            pygame.draw.arc(self.screen, color, box.move(reach // 3, 0), -1.14, 1.14, width)

    def _current_boxes(self) -> list[Box]:
        target = self.lost_boxes if self.status == "lost" else state_boxes(self.state)
        animation = self.animation
        if animation is None:
            return target
        t = (self.now - animation.began) / animation.duration
        if t >= 1:
            self.animation = None
            return target
        return [
            tuple(a + (b - a) * t for a, b in zip(start, end))
            for start, end in zip(animation.start, animation.end)
        ]

    def _draw_block(self) -> None:
        boxes = self._current_boxes()
        split = len(boxes) == 2
        sink = 0.0
        if self.status == "won" and self.animation is None:
            # The block drops into the hole.
            sink = min(1.0, (self.now - self.finished_at - 0.1) / 0.35)
            if sink >= 1:
                return
        # Far boxes first so nearer ones overlap them.
        order = sorted(range(len(boxes)), key=lambda i: boxes[i][2])
        for i in order:
            r0, c0, r1, c1, height = boxes[i]
            if self.status == "lost":
                top_color, side_color = LOST_TOP, LOST_SIDE
            elif split and i == 1:
                top_color, side_color = IDLE_TOP, IDLE_SIDE
            else:
                top_color, side_color = BLOCK_TOP, BLOCK_SIDE
            tile, inset = self.tile, max(2, self.tile // 14)
            x0 = self.origin_x + c0 * tile + inset
            x1 = self.origin_x + c1 * tile - inset
            y0 = self.origin_y + r0 * tile + inset
            y1 = self.origin_y + r1 * tile - inset
            lift = height * self.lift * (1 - max(0.0, sink))
            radius = max(2, tile // 10)
            body = pygame.Rect(round(x0), round(y0 - lift), round(x1 - x0), round(y1 - y0 + lift))
            top = pygame.Rect(round(x0), round(y0 - lift), round(x1 - x0), round(y1 - y0))
            pygame.draw.rect(self.screen, side_color, body, border_radius=radius)
            pygame.draw.rect(self.screen, top_color, top, border_radius=radius)
            pygame.draw.rect(self.screen, shade(side_color, 0.7), body, 2, border_radius=radius)
            if split and i == 0 and self.status != "lost":
                # White frame marks the cube under control.
                pygame.draw.rect(self.screen, TEXT, top.inflate(-4, -4), 3, border_radius=radius)

    def _draw_sidebar(self) -> None:
        x = WINDOW_SIZE[0] - SIDEBAR_WIDTH
        pygame.draw.rect(self.screen, PANEL, (x, 0, SIDEBAR_WIDTH, WINDOW_SIZE[1]))
        pygame.draw.line(self.screen, PANEL_LINE, (x, 0), (x, WINDOW_SIZE[1]))
        left, right = x + 20, WINDOW_SIZE[0] - 20

        self._text("BLOXORZ", (left, 18), self.big)
        self._text("search-based solver", (left, 52), self.small, MUTED)
        self._text("GAME", (left, 84), self.small, MUTED)
        self._text("SOLVERS", (left, 208), self.small, MUTED)
        self._text(
            f"replay speed: {SPEEDS[self.speed_index]} moves/s",
            (right, 208), self.small, MUTED, right=True,
        )

        mouse = pygame.mouse.get_pos()
        for button in self.buttons:
            enabled = button.enabled()
            hover = enabled and button.rect.collidepoint(mouse)
            fill = (70, 84, 122) if hover else (52, 61, 88)
            if not enabled:
                fill = (40, 45, 62)
            pygame.draw.rect(self.screen, fill, button.rect, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_LINE, button.rect, 1, border_radius=6)
            label = self.small.render(button.text, True, TEXT if enabled else (104, 112, 136))
            self.screen.blit(label, label.get_rect(center=button.rect.center))

        result = self.result
        if self.solver_thread is not None:
            rows = [("Solver", f"{self.solver_name} running...")]
        elif result is None:
            rows = [("Solver", "none run yet")]
        else:
            memory = result.peak_memory_bytes
            rows = [
                ("Solver", result.algorithm),
                ("Solution length", f"{result.length} moves" if result.solved else "no solution"),
                ("Path cost", str(result.cost) if result.solved else "-"),
                ("Expanded nodes", f"{result.expanded:,}"),
                ("Generated nodes", f"{result.generated:,}"),
                ("Search time", f"{result.time_s * 1000:.2f} ms"),
                ("Peak memory", f"{memory / 1024:.1f} KiB" if memory is not None else "-"),
            ]
            if self.solution:
                rows.append(("Replay", f"{self.solution_pos}/{len(self.solution)}"))
        self._draw_rows("LAST SEARCH", rows, left, right, 370)
        controls = [
            ("Arrows / WASD", "roll the block"),
            ("Space", "switch cube"),
            ("R  /  N", "restart / new game"),
            ("[  ]", "previous / next stage"),
            ("1 2 3 4", "BFS / DFS / UCS / A*"),
            ("P  .  -  +", "play / step / speed"),
            ("Esc", "quit"),
        ]
        self._draw_rows("CONTROLS", controls, left, right, 572)

    def _draw_rows(self, heading: str, rows, left: int, right: int, y: int) -> int:
        self._text(heading, (left, y), self.small, MUTED)
        y += 22
        for name, value in rows:
            self._text(name, (left, y), self.small, MUTED)
            self._text(value, (right, y), self.small, TEXT, right=True)
            y += 21
        return y

    def _draw_legend(self, left: int, y: int) -> None:
        entries = [
            ("floor", Tile.FLOOR, None),
            ("fragile", Tile.FRAGILE, None),
            ("goal", Tile.GOAL, None),
            ("bridge", Tile.BRIDGE, None),
            ("soft switch", Tile.FLOOR, SwitchKind.SOFT),
            ("heavy switch", Tile.FLOOR, SwitchKind.HEAVY),
            ("split switch", Tile.FLOOR, SwitchKind.SPLIT),
        ]
        colors = {
            Tile.FLOOR: FLOOR_TOP,
            Tile.FRAGILE: FRAGILE_TOP,
            Tile.GOAL: HOLE_OUTER,
            Tile.BRIDGE: BRIDGE_COLORS[0],
        }
        x = left
        for name, kind, switch in entries:
            rect = pygame.Rect(x, y, 24, 24)
            pygame.draw.rect(self.screen, colors[kind], rect, border_radius=3)
            if kind is Tile.GOAL:
                pygame.draw.rect(self.screen, FLOOR_TOP, rect, 2, border_radius=3)
            if switch is not None:
                self._draw_switch(switch, rect, SYMBOL)
            label = self._text(name, (rect.right + 7, y + 5), self.small, MUTED)
            x = label.right + 18


def run_gui(levels: list[Level], level_index: int = 0, **options) -> None:
    App(levels, level_index, **options).run()
