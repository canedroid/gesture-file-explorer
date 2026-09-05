"""Holographic per-window rendering for the spatial HUD.

Draws each floating :class:`SpatialWindow` as an independent translucent sci-fi
card with generous padding: a docked title plus glowing accent bar on the top
left, a distinct [X] close button pinned to the top right (never overlapped by
text), evenly spaced list rows with clear icons, and a footer status strip.
"""

import math
import time

import cv2
import numpy as np

from spatial_window import (
    CONTENT_DIRECTORY,
    PAD,
    STATE_CLOSING,
    STATE_DRAGGING,
    TITLE_BAR_H,
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

PANEL_ALPHA = 0.55
HOVER_ALPHA = 0.55
CORNER_CUT = 16
CORNER_ARM = 20
TEXT_LINE_H = 24

TITLE_X = 30
TITLE_BASELINE = 30
ACCENT_X = 16
ROW_CHEVRON_X = 8
ROW_TEXT_X = 34
ROW_BASELINE_DOWN = 11


class WindowRenderer:
    """Renders all manager windows onto the camera frame, back to front."""

    def __init__(self):
        self._wrap_cache = {}

    def render(self, frame, manager, cursors=None):
        """Draw every window managed by ``manager`` onto ``frame``.

        ``cursors`` is an optional list of cursors used for hover highlights.
        """
        cursors = cursors or []
        focus = manager.windows[-1] if manager.windows else None
        for win in manager.windows:
            self._draw_window(frame, win, manager, focus, cursors)
        return frame

    # ------------------------------------------------------------------ card
    def _draw_window(self, frame, win, manager, focus, cursors):
        layout = manager.layout_for(win)
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        if x1 <= x0 or y1 <= y0:
            return

        # Shelve the original panel region so closing cards fade fully away.
        active = win.state != STATE_CLOSING
        alpha = max(0.05, min(1.0, PANEL_ALPHA * win.fade))

        roi = frame[y0:y1, x0:x1]
        overlay = np.full_like(roi, PANEL_BG, dtype=np.uint8)
        frame[y0:y1, x0:x1] = cv2.addWeighted(
            overlay, alpha, roi, 1.0 - alpha, 0
        )

        hover = self._cursor_inside(cursors, win)
        is_focus = win is focus
        self._draw_frame_border(frame, win, layout, is_focus)
        self._draw_title_bar(frame, win, layout, is_focus, cursors)

        if win.content_type == CONTENT_DIRECTORY:
            self._draw_directory_rows(frame, win, manager, cursors)
        else:
            self._draw_text_rows(frame, win, manager, cursors)
        self._draw_footer(frame, win, layout)

    def _cursor_inside(self, cursors, win):
        for cursor in cursors:
            if cursor.visible and win.contains(cursor.x, cursor.y):
                return cursor
        return None

    # -------------------------------------------------------------- borders
    def _draw_frame_border(self, frame, win, layout, is_focus):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
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

        active = win.state != STATE_CLOSING
        if active:
            # Soft outer aura then a crisp bright frame.
            cv2.polylines(
                frame, [pts], True, (0, 120, 190), 4, cv2.LINE_AA
            )
            color = CYAN if is_focus else CYAN_SOFT
            cv2.polylines(frame, [pts], True, color, 2, cv2.LINE_AA)
        else:
            dim_edge = int(60 * win.fade)
            cv2.polylines(frame, [pts], True, (dim_edge,) * 3, 1, cv2.LINE_AA)

        # Clean tech corner brackets in bright amber.
        t = time.time()
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)
        bright = AMBER_BRIGHT if active else DIM
        arm = CORNER_ARM
        for cx, cy, sx, sy in (
            (x0, y0, 1, 1),
            (x1, y0, -1, 1),
            (x0, y1, 1, -1),
            (x1, y1, -1, -1),
        ):
            cv2.line(
                frame,
                (cx, cy + sy * cut),
                (cx, cy + sy * arm),
                bright,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * cut, cy),
                (cx + sx * arm, cy),
                bright,
                2,
                cv2.LINE_AA,
            )
        if active:
            glow = int(120 + 80 * pulse)
            cv2.line(
                frame,
                (x0 + cut, y0),
                (x0 + cut, y0 + arm),
                (glow,) * 3,
                1,
                cv2.LINE_AA,
            )

    # ----------------------------------------------------------- title bar
    def _draw_title_bar(self, frame, win, layout, is_focus, cursors):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        t = time.time()
        active = win.state != STATE_CLOSING

        # Glowing accent bar docked beside the title.
        if active:
            accent_y = y0 + 13
            accent_h = TITLE_BAR_H - 24
            cv2.line(
                frame,
                (ACCENT_X + x0, accent_y),
                (ACCENT_X + 3 + x0, accent_y + accent_h),
                AMBER_BRIGHT,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (ACCENT_X + 1 + x0, accent_y),
                (ACCENT_X + 2 + x0, accent_y + accent_h),
                AMBER,
                1,
                cv2.LINE_AA,
            )

        state_tag = ""
        if win.state == STATE_DRAGGING:
            state_tag = "\\/LOCK"
        elif win.state == STATE_CLOSING:
            state_tag = "DISMISS"
        title_origin = x0 + TITLE_X
        # Reserve the close button so long titles never slide under it.
        reserved = layout.close_button[0] - title_origin - 10
        tag_advance = 0
        if state_tag:
            tag_advance = (
                cv2.getTextSize(state_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0]
                + 8
            )
            self._text(
                frame,
                state_tag,
                (title_origin, y0 + TITLE_BASELINE),
                0.6,
                AMBER_BRIGHT if active else DIM,
            )
        self._text(
            frame,
            _truncate(win.title, max(60, reserved - tag_advance), 0.7),
            (title_origin + tag_advance, y0 + TITLE_BASELINE),
            0.7,
            TEXT,
            bold=is_focus and active,
        )

        # Divider seam with a travelling energy pulse.
        seam_y = y0 + TITLE_BAR_H - 4
        seam_color = CYAN if is_focus and active else CYAN_SOFT
        cv2.line(frame, (x0 + 6, seam_y), (x1 - 6, seam_y), seam_color, 1, cv2.LINE_AA)
        cv2.line(frame, (x0 + 6, seam_y + 1), (x1 - 6, seam_y + 1), SHADOW, 1)
        if active:
            dot_x = x0 + 8 + int(((t * 0.3) % 1.0) * (x1 - x0 - 16))
            cv2.circle(frame, (dot_x, seam_y), 3, AMBER_BRIGHT, -1, cv2.LINE_AA)
            cv2.circle(frame, (dot_x, seam_y), 6, AMBER, 1, cv2.LINE_AA)

        self._draw_close_button(frame, layout, cursors, active)

    def _draw_close_button(self, frame, layout, cursors, active):
        cb = layout.close_button
        cb_hover = _cursor_hover_rect(cursors, cb)
        if cb_hover and active:
            bg = (40, 40, 120)
            cv2.rectangle(
                frame, (cb[0], cb[1]), (cb[2], cb[3]), bg, -1, cv2.LINE_AA
            )
        cv2.rectangle(
            frame,
            (cb[0], cb[1]),
            (cb[2], cb[3]),
            HOVER_BORDER if cb_hover else CYAN_SOFT,
            1,
            cv2.LINE_AA,
        )
        cx = (cb[0] + cb[2]) // 2
        pad = 5
        cy1 = cb[1] + pad
        cy2 = cb[3] - pad
        color = HOVER_BORDER if cb_hover else AMBER
        cv2.line(frame, (cx - pad, cy1), (cx + pad, cy2), color, 2, cv2.LINE_AA)
        cv2.line(frame, (cx + pad, cy1), (cx - pad, cy2), color, 2, cv2.LINE_AA)

    # ----------------------------------------------------------------- rows
    def _draw_directory_rows(self, frame, win, manager, cursors):
        layout = manager.layout_for(win)
        start = win.scroll_offset
        end = min(len(win.items), start + layout.visible_rows)
        for i in range(start, end):
            item = win.items[i]
            screen_index = i - start
            rect = row_rect(layout, screen_index)
            if rect[3] > layout.y1 - PAD:
                break
            hovered = _cursor_hover_rect(cursors, rect)
            self._draw_row(frame, item, rect, hovered)

    def _draw_row(self, frame, item, rect, hovered):
        x0, y0, x1, y1 = rect
        t = time.time()
        if hovered:
            alpha = HOVER_ALPHA + 0.12 * (0.5 + 0.5 * math.sin(t * 6.0))
            roi = frame[y0:y1, x0:x1]
            overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
            a = min(alpha, 1.0)
            frame[y0:y1, x0:x1] = cv2.addWeighted(overlay, a, roi, 1.0 - a, 0)
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            border = (
                int(255 - 120 * pulse),
                int(240),
                int(0 + 60 * pulse),
            )
            cv2.rectangle(frame, (x0, y0), (x1 - 6, y1), border, 1, cv2.LINE_AA)
            cv2.rectangle(frame, (x0, y0), (x0 + 4, y1), HOVER_BORDER, -1)

        text_y = y1 - ROW_BASELINE_DOWN
        if not item.is_dir:
            self._draw_file_row(frame, item, x0, x1, text_y, hovered)
            return
        if item.name == "..":
            self._text(frame, "<", (x0 + ROW_CHEVRON_X, text_y), 0.6, AMBER, bold=True)
            self._text(frame, "PARENT", (x0 + ROW_TEXT_X, text_y), 0.5, DIM)
            return
        self._text(
            frame,
            ">",
            (x0 + ROW_CHEVRON_X, text_y),
            0.62,
            AMBER_BRIGHT if hovered else AMBER,
            bold=True,
        )
        name = _truncate(item.name, (x1 - x0) - ROW_TEXT_X - 24, 0.5)
        self._text(
            frame,
            name,
            (x0 + ROW_TEXT_X, text_y),
            0.5,
            AMBER_BRIGHT if hovered else AMBER,
        )

    def _draw_file_row(self, frame, item, x0, x1, text_y, hovered):
        # Hollow square file icon, cleanly separated from the label.
        mid_y = int(text_y - 8)
        icon = (x0 + 12, mid_y)
        cv2.rectangle(
            frame,
            (icon[0] - 4, icon[1] - 4),
            (icon[0] + 4, icon[1] + 4),
            CYAN_SOFT,
            1,
            cv2.LINE_AA,
        )

        dot = item.name.rfind(".")
        ext = item.name[dot + 1 :].upper()[:3] if dot >= 0 else ""
        badge = ""
        if ext:
            badge = f"[{ext}]"
        badge_w = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
        badge_x = x1 - 8 - badge_w
        name_max = badge_x - (x0 + ROW_TEXT_X + 2) - 6
        self._text(
            frame,
            _truncate(item.name, max(40, name_max), 0.5),
            (x0 + ROW_TEXT_X, text_y),
            0.5,
            TEXT,
        )
        if badge:
            self._text(frame, badge, (badge_x, text_y), 0.42, CYAN_SOFT)

    # ----------------------------------------------------------------- text
    def _draw_text_rows(self, frame, win, manager, cursors):
        layout = manager.layout_for(win)
        wrapped = self._wrapped_for(win)
        start = win.scroll_offset
        text_rows = max(1, (layout.y1 - layout.list_top - 24) // TEXT_LINE_H)
        if wrapped:
            max_scroll = max(0, len(wrapped) - text_rows)
            win.scroll_offset = min(win.scroll_offset, max_scroll)

        content_left = layout.list_left + 6
        max_w = layout.list_right - content_left - 6
        y = layout.list_top + 22
        for line in wrapped[start : start + text_rows]:
            if y + 8 > layout.y1 - 20:
                break
            stripped = line.lstrip()
            color = TEXT
            if stripped.startswith("#"):
                color = AMBER_BRIGHT
            elif stripped.startswith(("-", "*", "+", ">")) or stripped.startswith(
                ("1.", "2.", "3.")
            ):
                color = CYAN
            if stripped:
                self._text(
                    frame,
                    _truncate(line, max_w, 0.5),
                    (content_left, y),
                    0.5,
                    color,
                )
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
        for rect, go_up, hovered in (
            (up, True, hover_up),
            (down, False, hover_down),
        ):
            x0, y0, x1, y1 = rect
            if hovered:
                roi = frame[y0:y1, x0:x1]
                overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
                frame[y0:y1, x0:x1] = cv2.addWeighted(
                    overlay, HOVER_ALPHA, roi, 1.0 - HOVER_ALPHA, 0
                )
            cv2.rectangle(
                frame,
                (x0, y0),
                (x1, y1),
                HOVER_BORDER if hovered else CYAN_SOFT,
                1,
                cv2.LINE_AA,
            )
            mid = (x0 + x1) // 2
            cy = (y0 + y1) // 2
            tip_y = y0 + 6 if go_up else y1 - 6
            color = HOVER_BORDER if hovered else CYAN
            for dx in (-6, 6):
                cv2.line(
                    frame,
                    (mid, tip_y),
                    (mid + dx, cy),
                    color,
                    2,
                    cv2.LINE_AA,
                )

    # ---------------------------------------------------------------- footer
    def _draw_footer(self, frame, win, layout):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        seam_y = y1 - 30
        cv2.line(frame, (x0 + 6, seam_y), (x1 - 58, seam_y), CYAN_SOFT, 1, cv2.LINE_AA)
        cv2.line(frame, (x0 + 6, seam_y + 1), (x1 - 58, seam_y + 1), SHADOW, 1)

        baseline = y1 - 10
        if win.message:
            self._text(
                frame,
                "!" + win.message[:54],
                (x0 + PAD, baseline),
                0.45,
                RED,
            )
            return
        if win.content_type == CONTENT_DIRECTORY:
            total = len(win.items)
            label = f"FILES {total:03d}" if total else "EMPTY"
        else:
            total = len(self._wrapped_for(win))
            first = min(win.scroll_offset + 1, max(total, 1))
            last = min(win.scroll_offset + layout.visible_rows, total)
            label = f"LINES {first}-{last} / {total}"
        self._text(frame, label, (x0 + PAD, baseline), 0.45, CYAN_SOFT)

    # ----------------------------------------------------------------- utils
    @staticmethod
    def _text(frame, text, org, scale, color, bold=False):
        """Draw shadowed text for a clean layered glow."""
        x, y = org
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, text, (x + 1, y + 1), font, scale, SHADOW, 2, cv2.LINE_AA)
        thickness = 2 if bold else 1
        cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def row_rect(layout, index):
    """Back-compat hook pointing at the shared spatial_window helper."""
    from spatial_window import row_rect as _rr

    return _rr(layout, index)


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