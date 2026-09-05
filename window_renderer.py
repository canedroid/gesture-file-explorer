"""Holographic per-window rendering for the spatial HUD.

Draws each floating :class:`SpatialWindow` as an independent translucent sci-fi
card: angular cut-corner borders, glowing corner brackets, an animated energy
seam in the title bar, hover-ready list rows, and per-window footer status.
"""

import math
import time

import cv2
import numpy as np

from spatial_window import (
    CONTENT_DIRECTORY,
    STATE_CLOSING,
    STATE_DRAGGING,
    wrap_lines,
)

CYAN = (255, 240, 0)
CYAN_SOFT = (190, 225, 60)
AMBER = (30, 176, 255)
AMBER_BRIGHT = (120, 220, 255)
PANEL_BG = (10, 16, 32)
TEXT = (240, 248, 255)
DIM = (150, 180, 195)
HOVER_BG = (60, 70, 150)
HOVER_BORDER = (255, 240, 0)
SHADOW = (6, 10, 18)
RED = (60, 60, 255)

PANEL_ALPHA = 0.42
HOVER_ALPHA = 0.5
CORNER_CUT = 14
CORNER_ARM = 22
TEXT_LINE_H = 19


class WindowRenderer:
    """Renders all manager windows onto the camera frame, back to front."""

    def __init__(self):
        self._wrap_cache = {}

    def render(self, frame, manager, cursors=None):
        """Draw every window managed by ``manager`` onto ``frame``.

        ``cursors`` is an optional list of cursors used for hover highlights.
        """
        cursors = cursors or []
        frame_h, frame_w = frame.shape[:2]
        focus = manager.windows[-1] if manager.windows else None
        for win in manager.windows:
            self._draw_window(frame, win, manager, focus, cursors)
        return frame

    # ------------------------------------------------------------------ card
    def _draw_window(self, frame, win, manager, focus, cursors):
        frame_h, frame_w = frame.shape[:2]
        layout = manager.layout_for(win)
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        if x1 <= x0 or y1 <= y0:
            return

        active = win.state != STATE_CLOSING
        alpha = PANEL_ALPHA * win.fade
        if not active:
            alpha *= win.fade  # closing cards fade out even harder
        alpha = max(0.05, min(1.0, alpha))

        roi = frame[y0:y1, x0:x1]
        overlay = np.full_like(roi, PANEL_BG, dtype=np.uint8)
        frame[y0:y1, x0:x1] = cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0)

        hover = self._cursor_inside(cursors, win)
        is_focus = win is focus
        self._draw_frame_border(frame, x0, y0, x1, y1, hover, is_focus, win)
        self._draw_title_bar(frame, win, layout, hover, is_focus, manager, cursors)

        if win.content_type == CONTENT_DIRECTORY:
            self._draw_directory_rows(frame, win, manager, cursors)
            self._draw_footer(frame, win, layout)
        else:
            self._draw_text_rows(frame, win, manager, cursors)
            self._draw_footer(frame, win, layout)

        if win.message:
            cv2.putText(
                frame,
                win.message[:60],
                (x0 + 8, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                RED,
                1,
                cv2.LINE_AA,
            )

    def _cursor_inside(self, cursors, win):
        for cursor in cursors:
            if cursor.visible and win.contains(cursor.x, cursor.y):
                return cursor
        return None

    # -------------------------------------------------------------- borders
    def _draw_frame_border(self, frame, x0, y0, x1, y1, hover, is_focus, win):
        cut = CORNER_CUT
        pts = np.array(
            [
                [x0 + cut, y0],
                [x1 - cut, y0],
                [x1, y0 + cut],
                [x1, y1 - cut],
                [x1 - cut, y1],
                [x0 + cut, y1],
                [x0, y1 - cut],
                [x0, y0 + cut],
            ],
            np.int32,
        )
        edge = (10 * win.fade + 5,) * 3
        edge = (int(edge[0]), int(edge[1]), int(edge[2]))
        cv2.polylines(frame, [pts], True, edge, 1, cv2.LINE_AA)
        active = win.state != STATE_CLOSING
        if is_focus and active:
            cv2.polylines(frame, [pts], True, CYAN, 2, cv2.LINE_AA)
        elif hover is not None and active:
            cv2.polylines(frame, [pts], True, CYAN_SOFT, 2, cv2.LINE_AA)

        t = time.time()
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)
        bright = AMBER_BRIGHT
        if not active:
            bright = DIM
        for cx, cy, sx, sy in (
            (x0, y0, 1, 1),
            (x1, y0, -1, 1),
            (x0, y1, 1, -1),
            (x1, y1, -1, -1),
        ):
            arm = CORNER_ARM
            cv2.line(
                frame, (cx, cy + sy * cut), (cx, cy + sy * arm), bright, 2, cv2.LINE_AA
            )
            cv2.line(
                frame, (cx + sx * cut, cy), (cx + sx * arm, cy), bright, 2, cv2.LINE_AA
            )

    # ----------------------------------------------------------- title bar
    def _draw_title_bar(self, frame, win, layout, hover, is_focus, manager, cursors):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        t = time.time()
        seam_y = y0 + TITLE_BAR_H - 6
        color = CYAN if is_focus and win.state != STATE_CLOSING else CYAN_SOFT
        cv2.line(frame, (x0 + 8, seam_y), (x1 - 8, seam_y), color, 1, cv2.LINE_AA)
        cv2.line(frame, (x0 + 8, seam_y + 1), (x1 - 8, seam_y + 1), SHADOW, 1)

        if win.state != STATE_CLOSING:
            dot_x = x0 + 8 + int(((t * 0.3) % 1.0) * (x1 - x0 - 16))
            cv2.circle(frame, (dot_x, seam_y), 3, AMBER_BRIGHT, -1, cv2.LINE_AA)
            cv2.circle(frame, (dot_x, seam_y), 6, AMBER, 1, cv2.LINE_AA)

        state_tag = ""
        if win.state == STATE_DRAGGING:
            state_tag = "\\/LOCK"
        elif win.state == STATE_CLOSING:
            state_tag = "DISMISS"
        title_text = f"{state_tag} " + win.title if state_tag else win.title
        title_text = _truncate(title_text, layout.x1 - layout.x0 - 40, 0.6)
        self._text(frame, title_text, (x0 + 10, y0 + 21), 0.6, TEXT, bold=(is_focus and win.state != STATE_CLOSING))

        cb = layout.close_button
        cb_hover = _cursor_hover_rect(cursors, cb)
        bg = (40, 40, 120) if cb_hover and win.state != STATE_CLOSING else None
        if bg:
            cv2.rectangle(frame, (cb[0], cb[1]), (cb[2], cb[3]), bg, -1, cv2.LINE_AA)
        cv2.rectangle(frame, (cb[0], cb[1]), (cb[2], cb[3]), CYAN_SOFT, 1, cv2.LINE_AA)
        cx = cb[0] + 5
        cy1 = cb[1] + 4
        cy2 = cb[3] - 4
        cv2.line(frame, (cx, cy1), (cx + 10, cy2), CYAN if cb_hover else AMBER, 2, cv2.LINE_AA)
        cv2.line(frame, (cx + 10, cy1), (cx, cy2), CYAN if cb_hover else AMBER, 2, cv2.LINE_AA)

    # ----------------------------------------------------------------- rows
    def _draw_directory_rows(self, frame, win, manager, cursors):
        layout = manager.layout_for(win)
        start = win.scroll_offset
        end = min(len(win.items), start + layout.visible_rows)
        frame_h, frame_w = frame.shape[:2]

        for i in range(start, end):
            item = win.items[i]
            screen_index = i - start
            rect = row_rect(layout, screen_index)
            if rect[3] > layout.y1 - 34:
                break
            hovered = _cursor_hover_rect(cursors, rect)
            self._draw_row(
                frame,
                item,
                rect,
                hovered,
                is_focus=win is manager.windows[-1],
            )
        self._draw_pager(frame, win, layout, cursors, overflow=len(win.items) > layout.visible_rows)

    def _draw_row(self, frame, item, rect, hovered, is_focus):
        x0, y0, x1, y1 = rect
        t = time.time()
        if hovered:
            alpha = HOVER_ALPHA + 0.12 * (0.5 + 0.5 * math.sin(t * 6.0))
            roi = frame[y0:y1, x0:x1]
            overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
            frame[y0:y1, x0:x1] = cv2.addWeighted(overlay, min(alpha, 1.0), roi, 1.0 - min(alpha, 1.0), 0)
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            border = (int(255 - 120 * pulse), int(240), int(0 + 60 * pulse))
            cv2.rectangle(frame, (x0, y0), (x1, y1), border, 1, cv2.LINE_AA)
            cv2.rectangle(frame, (x0, y0), (x0 + 4, y1), HOVER_BORDER, -1)

        text_y = y1 - 9
        if not item.is_dir:
            self._text(frame, item.name, (x0 + 16, text_y), 0.5, TEXT)
            return

        if item.name == "..":
            self._text(frame, "<up>", (x0 + 12, text_y), 0.55, AMBER, bold=True)
            return

        self._text(frame, ">", (x0 + 6, text_y), 0.6, AMBER, bold=True)
        name = _truncate(item.name, x1 - x0 - 40, 0.5)
        color = AMBER_BRIGHT if hovered else AMBER
        self._text(frame, name, (x0 + 30, text_y), 0.5, color, bold=is_focus and hovered)

    # ----------------------------------------------------------------- text
    def _draw_text_rows(self, frame, win, manager, cursors):
        layout = manager.layout_for(win)
        wrapped = self._wrapped_for(win)
        start = win.scroll_offset
        text_rows = max(1, (layout.y1 - layout.list_top - 6) // TEXT_LINE_H)
        if len(wrapped) > 0:
            max_scroll = max(0, len(wrapped) - text_rows)
            if win.scroll_offset > max_scroll:
                win.scroll_offset = max_scroll

        y = layout.list_top + TEXT_LINE_H - 2
        frame_right = layout.x1 - 8
        for line in wrapped[start : start + text_rows]:
            if y > layout.y1 - 28:
                break
            stripped = line.lstrip()
            color = TEXT
            if stripped.startswith("#"):
                color = AMBER_BRIGHT
            elif stripped.startswith(("-", "*", "+", ">")) or stripped.startswith(("1.", "2.", "3.")):
                color = CYAN
            elif not stripped:
                y += TEXT_LINE_H
                continue
            self._text(frame, _truncate(line, frame_right - layout.x0 - 16, 0.5), (layout.x0 + 12, y), 0.5, color)
            y += TEXT_LINE_H

        self._draw_pager(frame, win, layout, cursors, overflow=len(wrapped) > text_rows)

    def _wrapped_for(self, win):
        key = (win.id, win.width)
        cached = self._wrap_cache.get(key)
        if cached is None:
            cached = wrap_lines(win.items, win.width)
            self._wrap_cache[key] = cached
        return cached

    # ---------------------------------------------------------------- pager
    def _draw_pager(self, frame, win, layout, cursors, overflow):
        if not overflow:
            return
        up, down = layout.pager_up, layout.pager_down
        hover_up = _cursor_hover_rect(cursors, up)
        hover_down = _cursor_hover_rect(cursors, down)
        for rect, go_up, hovered in ((up, True, hover_up), (down, False, hover_down)):
            x0, y0, x1, y1 = rect
            if hovered:
                roi = frame[y0:y1, x0:x1]
                overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
                frame[y0:y1, x0:x1] = cv2.addWeighted(overlay, HOVER_ALPHA, roi, 1.0 - HOVER_ALPHA, 0)
            cv2.rectangle(frame, (x0, y0), (x1, y1), HOVER_BORDER if hovered else CYAN_SOFT, 1, cv2.LINE_AA)
            cy = (y0 + y1) // 2
            tip_y = y0 + 7 if go_up else y1 - 7
            color = HOVER_BORDER if hovered else CYAN
            for dx in (-6, 6):
                cv2.line(frame, ((x0 + x1) // 2, tip_y), ((x0 + x1) // 2 + dx, cy), color, 2, cv2.LINE_AA)

    # ---------------------------------------------------------------- footer
    def _draw_footer(self, frame, win, layout):
        if win.content_type == CONTENT_DIRECTORY:
            total = len(win.items)
            label = f"FILES {total:03d}" if total else "EMPTY"
        else:
            total = len(self._wrapped_for(win))
            first = min(win.scroll_offset + 1, max(total, 1))
            last = min(win.scroll_offset + layout.visible_rows, total)
            label = f"LINES {first}-{last} / {total}"
        self._text(frame, label, (layout.x0 + 12, layout.y1 - 10), 0.45, CYAN_SOFT)

    # ----------------------------------------------------------------- utils
    @staticmethod
    def _text(frame, text, org, scale, color, bold=False):
        x, y = org
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, text, (x + 1, y + 1), font, scale, SHADOW, 2, cv2.LINE_AA)
        thickness = 2 if bold else 1
        cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def row_rect(layout, index):
    """Local copy hook (kept importable to match spatial_window naming)."""
    from spatial_window import row_rect as _rr

    return _rr(layout, index)


TITLE_BAR_H = 32


def _truncate(text, max_px, scale):
    font = cv2.FONT_HERSHEY_SIMPLEX
    if cv2.getTextSize(text, font, scale, 1)[0][0] <= max_px:
        return text
    while text and cv2.getTextSize(text + "...", font, scale, 1)[0][0] > max_px:
        text = text[:-1]
    return text + "..."


def _cursor_hover_rect(cursors, rect):
    if not rect:
        return False
    x0, y0, x1, y1 = rect
    for cursor in cursors:
        if cursor.visible and x0 <= cursor.x <= x1 and y0 <= cursor.y <= y1:
            return True
    return False