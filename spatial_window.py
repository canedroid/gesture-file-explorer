"""Spatial floating window cards for the holographic HUD.

Each ``SpatialWindow`` is an independent card positioned in camera space with
its own title bar, close button, content, and interaction state. A shared
layout calculator maps a window rectangle to hit-testable regions so the
renderer and the interaction manager stay perfectly aligned.
"""

import math
from dataclasses import dataclass, field

import cv2

CONTENT_DIRECTORY = "directory"
CONTENT_TEXT = "text_viewer"

STATE_OPEN = "open"
STATE_DRAGGING = "dragging"
STATE_CLOSING = "closing"

TITLE_BAR_H = 50
CLOSE_BTN_W = 30
CLOSE_BTN_MARGIN = 12
PAD = 18
ROW_H = 46
LIST_TOP_OFFSET = TITLE_BAR_H + 18
FOOTER_H = 46
PAGER_H = 24

CONTENT_FONT = cv2.FONT_HERSHEY_COMPLEX
CONTENT_SCALE = 0.5

MIN_W, MAX_W = 600, 1180
MIN_H, MAX_H = 400, 840

DEFAULT_LIST_W = 700
DEFAULT_LIST_H = 450
DEFAULT_TEXT_W = 700
DEFAULT_TEXT_H = 450


def clamp(value, low, high):
    return max(low, min(high, value))


def dotted_title(title):
    """Render a title in the reference's dot-spaced logo treatment.

    "ALFRED" -> "A.L.F.R.E.D."   "THIS PC" -> "T.H.I.S.  P.C."
    """
    words = str(title).split()
    if not words:
        return str(title)
    return "  ".join(".".join(word) + "." for word in words)


@dataclass
class SpatialWindow:
    """An independent floating holographic window card."""

    id: int
    title: str
    path: str
    x: int
    y: int
    width: int = DEFAULT_LIST_W
    height: int = DEFAULT_LIST_H
    content_type: str = CONTENT_DIRECTORY
    items: list = field(default_factory=list)
    message: str = ""
    fade: float = 1.0
    state: str = STATE_OPEN
    scroll_offset: int = 0
    velocity_x: float = 0.0
    velocity_y: float = 0.0

    def __post_init__(self):
        self.width = clamp(self.width, MIN_W, MAX_W)
        self.height = clamp(self.height, MIN_H, MAX_H)

    def contains(self, px, py):
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height


@dataclass
class LayoutInfo:
    x0: int
    y0: int
    x1: int
    y1: int
    title_bar: tuple
    close_button: tuple
    list_left: int
    list_right: int
    list_top: int
    row_height: int
    visible_rows: int
    pager_up: tuple
    pager_down: tuple


def compute_window_layout(win, frame_w, frame_h):
    """Compute hit-testable regions for a window clamped to the viewport."""
    x0 = clamp(win.x, 0, max(0, frame_w - 1))
    y0 = clamp(win.y, 0, max(0, frame_h - 1))
    x1 = clamp(win.x + win.width, x0 + 1, frame_w)
    y1 = clamp(win.y + win.height, y0 + 1, frame_h)

    title_bar = (x0, y0, x1, y0 + TITLE_BAR_H)
    close_button = (
        x1 - CLOSE_BTN_W - CLOSE_BTN_MARGIN,
        y0 + 10,
        x1 - CLOSE_BTN_MARGIN,
        y0 + TITLE_BAR_H - 10,
    )
    list_left = x0 + PAD
    list_right = x1 - PAD
    list_top = y0 + LIST_TOP_OFFSET
    avail = max(ROW_H * 2, (y1 - y0) - LIST_TOP_OFFSET - FOOTER_H)
    visible_rows = max(1, avail // ROW_H)
    pager_up = (
        x1 - 52,
        y1 - FOOTER_H + 4,
        x1 - 24,
        y1 - PAGER_H - 2,
    )
    pager_down = (
        x1 - 52,
        y1 - PAGER_H,
        x1 - 24,
        y1 - 2,
    )
    return LayoutInfo(
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        title_bar=title_bar,
        close_button=close_button,
        list_left=list_left,
        list_right=list_right,
        list_top=list_top,
        row_height=ROW_H,
        visible_rows=visible_rows,
        pager_up=pager_up,
        pager_down=pager_down,
    )


def row_rect(layout, screen_index):
    """Screen-space rectangle of list row ``screen_index`` (0-based)."""
    top = layout.list_top + screen_index * layout.row_height
    bottom = top + layout.row_height - 6
    return (layout.list_left, top, layout.list_right, bottom)


def screen_index_for_y(layout, y):
    """Return the visible row index at a pixel offset, or None outside the list."""
    if y < layout.list_top:
        return None
    index = (y - layout.list_top) // layout.row_height
    if index >= layout.visible_rows:
        return None
    return index


def wrap_text_line(text, max_px, font, scale, thickness):
    """Wrap a single text line into pixel-fitting segments."""
    width, _ = cv2.getTextSize(text, font, scale, thickness)[0]
    if width <= max_px:
        return [text]
    lines = []
    current = ""
    for word in text.split(" "):
        trial = f"{current} {word}".strip()
        tw = cv2.getTextSize(trial, font, scale, thickness)[0][0]
        if tw <= max_px:
            current = trial
        else:
            if current:
                lines.append(current)
            word_w = cv2.getTextSize(word, font, scale, thickness)[0][0]
            if word_w <= max_px:
                current = word
            else:
                chunk = ""
                for char in word:
                    if cv2.getTextSize(chunk + char, font, scale, thickness)[0][0] > max_px:
                        lines.append(chunk)
                        chunk = char
                    else:
                        chunk += char
                current = chunk
    if current:
        lines.append(current)
    return lines


def wrap_lines(lines, card_width):
    """Wrap document lines to fit a floating card's content width."""
    max_px = max(80, card_width - PAD * 2 - 16)
    wrapped = []
    for raw in lines:
        wrapped.extend(wrap_text_line(raw, max_px, CONTENT_FONT, CONTENT_SCALE, 1))
    return wrapped


def point_in_rect(px, py, rect):
    if rect is None:
        return False
    x0, y0, x1, y1 = rect
    return x0 <= px <= x1 and y0 <= py <= y1


def hypot_delta(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)