"""Interactions and lifecycle management for spatial HUD windows.

The manager owns all :class:`SpatialWindow` instances and exposes the
operation methods the main loop drives from the two virtual cursors:
spawning cards, drag-with-flick, two-handed pinch scaling, and dismiss-on-
release animations.
"""

import os

from file_engine import FileEntry, get_drives, read_text_file, scan_directory
from spatial_window import (
    ALFRED_H,
    ALFRED_TITLE,
    ALFRED_W,
    CONTENT_DIRECTORY,
    CONTENT_TEXT,
    DEFAULT_LIST_H,
    DEFAULT_LIST_W,
    DEFAULT_TEXT_H,
    DEFAULT_TEXT_W,
    MAX_H,
    MAX_W,
    MIN_H,
    MIN_W,
    STATE_CLOSING,
    STATE_DRAGGING,
    STATE_OPEN,
    LayoutInfo,
    SpatialWindow,
    clamp,
    compute_window_layout,
    point_in_rect,
    screen_index_for_y,
)

MAX_CASCADE = 6
FLICK_CLOSE_THRESHOLD = 16.0
DRAG_LERP = 0.5
CLOSE_VELOCITY_DAMPING = 0.94

ASSISTANT_DRIVES = "assistant://drives"
ASSISTANT_HELP = "assistant://help"
ASSISTANT_ABOUT = "assistant://about"

ASSISTANT_HELP_LINES = [
    "# GETTING STARTED",
    "",
    "1. Raise a hand in front of the camera.",
    "2. Point your index finger to move the cursor.",
    "3. Pinch index + thumb to click a row or button.",
    "4. Pinch a window title bar and move to drag it.",
    "5. Two-handed pinch on a window grows or shrinks it.",
    "6. Press and hold thumb + middle to dismiss a window.",
    "7. Flick a window hard on release to throw it away.",
    "",
    "ENJOY YOUR HOLOGRAPHIC FILES.",
]

ASSISTANT_ABOUT_LINES = [
    "# ALFRED ASSISTANT",
    "",
    "A gesture-controlled spatial HUD for your files.",
    "",
    "Runs on MediaPipe hand tracking and OpenCV.",
    "Two virtual cursors and floating glass cards.",
    "",
    "INSPIRED BY JARVIS-STYLE AI INTERFACES.",
]


def _entry_from_drive(drive):
    return FileEntry(name=drive, path=drive, is_dir=True)


class WindowManager:
    """Owns all open spatial windows and resolves gestures into actions."""

    def __init__(self):
        self.windows = []
        self._next_id = 1
        self.frame_w = 1280
        self.frame_h = 720
        self._resize = {}
        self._close_anim = {}

    def set_viewport(self, frame_w, frame_h):
        self.frame_w = frame_w
        self.frame_h = frame_h

    # ------------------------------------------------------------- spawning
    def spawn_drives_card(self):
        """Open the 'This PC' card listing every mounted drive."""
        title = "THIS PC"
        win = SpatialWindow(
            id=self._next_id,
            title=title,
            path="",
            x=60,
            y=60,
            width=DEFAULT_LIST_W,
            height=DEFAULT_LIST_H,
            content_type=CONTENT_DIRECTORY,
            items=[_entry_from_drive(drive) for drive in get_drives()],
        )
        self._next_id += 1
        self._clamp_position(win)
        self.windows.append(win)
        return win

    def spawn_assistant_card(self):
        """Open the centered ALFRED assistant panel with section rows."""
        win = SpatialWindow(
            id=self._next_id,
            title=ALFRED_TITLE,
            path="assistant://",
            x=(self.frame_w - ALFRED_W) // 2,
            y=(self.frame_h - ALFRED_H) // 2,
            width=ALFRED_W,
            height=ALFRED_H,
            content_type=CONTENT_DIRECTORY,
            items=[
                FileEntry(
                    name="GETTING STARTED",
                    path=ASSISTANT_HELP,
                    is_dir=False,
                ),
                FileEntry(name="DRIVES", path=ASSISTANT_DRIVES, is_dir=True),
                FileEntry(name="ABOUT", path=ASSISTANT_ABOUT, is_dir=False),
            ],
        )
        self._next_id += 1
        self._clamp_position(win)
        self.windows.append(win)
        return win

    def open_assistant(self, action, parent=None):
        """Resolve an ALFRED section row into a card or a focus change.

        Returns the resulting window (or an existing card that was focused).
        """
        if action == ASSISTANT_DRIVES:
            existing = next(
                (w for w in self.windows if w.path == "" and w.state != STATE_CLOSING),
                None,
            )
            if existing is not None:
                self.focus(existing)
                return existing
            child = self.spawn_drives_card()
            self.focus(child)
            return child
        if action == ASSISTANT_HELP:
            title, lines = "GETTING STARTED", ASSISTANT_HELP_LINES
        elif action == ASSISTANT_ABOUT:
            title, lines = "ABOUT ASSISTANT", ASSISTANT_ABOUT_LINES
        else:
            return None
        parent = parent or (self.windows[-1] if self.windows else None)
        win = SpatialWindow(
            id=self._next_id,
            title=title,
            path=action,
            x=parent.x + (parent.width - DEFAULT_TEXT_W) // 2 if parent else 200,
            y=parent.y + (parent.height - DEFAULT_TEXT_H) // 2 if parent else 140,
            width=DEFAULT_TEXT_W,
            height=DEFAULT_TEXT_H,
            content_type=CONTENT_TEXT,
            items=lines,
        )
        self._next_id += 1
        self._cascade_spawn(win)
        self.windows.append(win)
        return win

    def spawn_directory_card(self, parent, entry):
        """Open a card showing the contents of a folder entry."""
        name = entry.name
        path = entry.path if entry.path else entry.name
        try:
            children = scan_directory(path)
            message = ""
        except (PermissionError, OSError, FileNotFoundError) as exc:
            children = []
            message = str(exc)
        win = SpatialWindow(
            id=self._next_id,
            title=name,
            path=path,
            x=parent.x + 40,
            y=parent.y + 40,
            width=DEFAULT_LIST_W,
            height=DEFAULT_LIST_H,
            content_type=CONTENT_DIRECTORY,
            items=[self._up_entry(), *children],
            message=message,
        )
        self._next_id += 1
        self._cascade_spawn(win)
        self.windows.append(win)
        return win

    def spawn_text_card(self, parent, entry):
        """Open a card rendering a supported text/markdown file."""
        name = entry.name
        path = entry.path if entry.path else entry.name
        try:
            lines = read_text_file(path)
            message = ""
        except (PermissionError, OSError, FileNotFoundError) as exc:
            lines = []
            message = str(exc)
        win = SpatialWindow(
            id=self._next_id,
            title=name,
            path=path,
            x=parent.x + 60,
            y=parent.y + 40,
            width=DEFAULT_TEXT_W,
            height=DEFAULT_TEXT_H,
            content_type=CONTENT_TEXT,
            items=lines,
            message=message,
        )
        self._next_id += 1
        self._cascade_spawn(win)
        self.windows.append(win)
        return win

    @staticmethod
    def _up_entry():
        return FileEntry(name="..", path="", is_dir=True)

    def _cascade_spawn(self, win):
        step = 0
        while step < MAX_CASCADE and self._any_overlap(win):
            win.x += 40
            win.y += 40
            step += 1
            self._clamp_position(win)
        if self._any_overlap(win):
            self._relocate_free(win)
        self._clamp_position(win)

    def _any_overlap(self, win):
        return any(
            w.state != STATE_CLOSING and _overlaps(w, win)
            for w in self.windows
        )

    def _relocate_free(self, win):
        """Try a light grid scan for the first non-overlapping placement."""
        step = 20
        for gy in range(10, max(11, self.frame_h - win.height + 1), step):
            for gx in range(10, max(11, self.frame_w - win.width + 1), step):
                probe = (gx, gy, gx + win.width, gy + win.height)
                if any(
                    w.state != STATE_CLOSING and _rect_hit(w, probe)
                    for w in self.windows
                ):
                    continue
                win.x, win.y = gx, gy
                return

    def _clamp_position(self, win):
        win.x = clamp(win.x, 0, max(0, self.frame_w - win.width))
        win.y = clamp(win.y, 0, max(0, self.frame_h - win.height))

    # -------------------------------------------------------------- queries
    @property
    def active_windows(self):
        return [w for w in self.windows if w.state != STATE_CLOSING]

    def topmost_at(self, px, py):
        for win in reversed(self.windows):
            if win.state != STATE_CLOSING and win.contains(px, py):
                return win
        return None

    def focus(self, win):
        if win in self.windows:
            self.windows.remove(win)
            self.windows.append(win)

    def layout_for(self, win):
        return compute_window_layout(win, self.frame_w, self.frame_h)

    # ----------------------------------------------------------------- drag
    def start_drag(self, win, cx, cy):
        if win.state != STATE_CLOSING:
            win.state = STATE_DRAGGING
            self.focus(win)

    def move_drag(self, win, cx, cy, dx, dy):
        """Follow the cursor smoothly and record instantaneous velocity."""
        win.x = int(round(win.x + (cx - win.x) * DRAG_LERP))
        win.y = int(round(win.y + (cy - win.y) * DRAG_LERP))
        win.velocity_x = dx
        win.velocity_y = dy

    def release_drag(self, win, vx, vy):
        """End a drag; a fast release flicks the window off-screen."""
        if win.state != STATE_DRAGGING:
            return
        speed = (vx * vx + vy * vy) ** 0.5
        if speed > FLICK_CLOSE_THRESHOLD:
            self.close_window(win, vx, vy)
        else:
            win.state = STATE_OPEN

    # ---------------------------------------------------------- two-hand grow
    def begin_resize(self, win, h1x, h1y, h2x, h2y):
        self.focus(win)
        self._resize[win.id] = {
            "base_w": win.width,
            "base_h": win.height,
            "dist": max(1.0, _dist(h1x, h1y, h2x, h2y)),
            "hx1": h1x - win.x,
            "hy1": h1y - win.y,
            "hx2": h2x - win.x,
            "hy2": h2y - win.y,
        }

    def is_resizing(self, win):
        return win.id in self._resize

    def apply_resize(self, win, h1x, h1y, h2x, h2y):
        data = self._resize.get(win.id)
        if data is None:
            self.begin_resize(win, h1x, h1y, h2x, h2y)
            return
        scale = clamp(_dist(h1x, h1y, h2x, h2y) / data["dist"], 0.5, 2.5)
        win.width = clamp(int(round(data["base_w"] * scale)), MIN_W, MAX_W)
        win.height = clamp(int(round(data["base_h"] * scale)), MIN_H, MAX_H)
        win.x = int(h1x - data["hx1"] * scale)
        win.y = int(h1y - data["hy1"] * scale)
        self._clamp_position(win)

    def end_resize(self, win):
        self._resize.pop(win.id, None)

    def end_all_resizes(self):
        self._resize.clear()

    # ----------------------------------------------------------------- close
    def close_window(self, win, vx=0.0, vy=0.0):
        if win.state == STATE_CLOSING:
            return
        win.state = STATE_CLOSING
        win.velocity_x = vx
        win.velocity_y = vy
        self.end_resize(win)
        self._close_anim[win.id] = {"alpha": 1.0}

    def step_closing(self):
        """Advance closing-window physics; reap cards that leave the frame."""
        for win in list(self.windows):
            if win.state != STATE_CLOSING:
                continue
            anim = self._close_anim.get(win.id)
            if anim is None:
                continue
            win.velocity_x *= CLOSE_VELOCITY_DAMPING
            win.velocity_y *= CLOSE_VELOCITY_DAMPING
            win.x += int(round(win.velocity_x))
            win.y += int(round(win.velocity_y))
            anim["alpha"] *= 0.93
            win.fade = anim["alpha"]
            if (
                win.x > self.frame_w
                or win.x + win.width < 0
                or win.y > self.frame_h
                or win.y + win.height < 0
            ):
                self.windows.remove(win)
                self._close_anim.pop(win.id, None)

    # ---------------------------------------------------------------- clicks
    def handle_pinch_start(self, win, px, py):
        """Resolve a new pinch inside ``win`` into an action dict."""
        layout = self.layout_for(win)
        if point_in_rect(px, py, layout.close_button):
            self.close_window(win)
            return {"kind": "close"}
        if point_in_rect(px, py, layout.title_bar):
            self.start_drag(win, px, py)
            return {"kind": "drag"}
        if point_in_rect(px, py, layout.pager_up):
            win.scroll_offset = max(0, win.scroll_offset - layout.visible_rows)
            return {"kind": "pager_up"}
        if point_in_rect(px, py, layout.pager_down):
            win.scroll_offset += layout.visible_rows
            return {"kind": "pager_down"}

        index = screen_index_for_y(layout, py)
        if index is None:
            return {"kind": "nothing"}
        item_index = win.scroll_offset + index
        if item_index >= len(win.items):
            return {"kind": "nothing"}
        item = win.items[item_index]

        if win.content_type == CONTENT_TEXT:
            return {"kind": "text_line"}
        if item.path.startswith("assistant://"):
            child = self.open_assistant(item.path, win)
            return {"kind": "assistant_action", "action": item.path, "window": child}
        if not item.is_dir:
            child = self.spawn_text_card(win, item)
            self.focus(child)
            return {"kind": "opened_file", "window": child, "item": item.name}
        if item.name == "..":
            self.close_window(win)
            return {"kind": "navigate_up"}
        if item.path and os.path.normcase(item.path) == os.path.normcase(win.path):
            return {"kind": "nothing"}
        child = self.spawn_directory_card(win, item)
        self.focus(child)
        return {"kind": "opened_directory", "window": child, "item": item.name}


def _overlaps(a, b):
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def _rect_hit(win, rect):
    return not (
        win.x + win.width <= rect[0]
        or rect[2] <= win.x
        or win.y + win.height <= rect[1]
        or rect[3] <= win.y
    )


def _dist(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5