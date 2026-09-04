"""Futuristic translucent AR HUD rendered directly on the camera frame.

Styles the application as a sci-fi holographic interface: glowing cyan and
amber accents, angular tech corner brackets, drop-shadow typography, and
animated hover highlights.
"""

import math
import time

import cv2
import numpy as np

CYAN = (255, 240, 0)            # #00F0FF
CYAN_SOFT = (190, 225, 60)      # dimmer cyan for hairline details
AMBER = (30, 176, 255)          # #FFB000
AMBER_BRIGHT = (120, 220, 255)
PANEL_BG = (10, 16, 32)
TEXT = (240, 248, 255)
DIM = (150, 180, 195)
HOVER_BG = (60, 70, 150)
HOVER_BORDER = (255, 240, 0)
SHADOW = (6, 10, 18)

PANEL_ALPHA = 0.48
HOVER_ALPHA = 0.5
MAX_VISIBLE_ROWS = 6
CORNER_CUT = 16
CORNER_ARM = 26


class HUD:
    """Semi-transparent heads-up display laid out on the camera frame."""

    default_width = 960

    def __init__(
        self,
        panel_alpha=PANEL_ALPHA,
        margin_x=40,
        margin_top=76,
        margin_bottom=66,
        row_height=44,
        max_rows=MAX_VISIBLE_ROWS,
    ):
        self.panel_alpha = panel_alpha
        self.margin_x = margin_x
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.row_height = row_height
        self.max_rows = max_rows

        self.panel_x = 0
        self.panel_y = 0
        self.panel_w = 0
        self.panel_h = 0
        self.title_y = 0
        self.path_y = 0
        self.list_top = 0
        self.visible_rows = 0
        self.hover_index = None
        self.hovered_button = None
        self.pager_visible = False
        self.scroll_up_rect = None
        self.scroll_down_rect = None
        self.last_text_rows = 0

    # ------------------------------------------------------------------ layout
    def _layout(self, frame_w, frame_h):
        self.panel_x = self.margin_x
        self.panel_y = self.margin_top
        self.panel_w = frame_w - 2 * self.margin_x
        self.panel_h = frame_h - self.margin_top - self.margin_bottom
        self.title_y = self.panel_y + 42
        self.path_y = self.panel_y + 74
        self.list_top = self.panel_y + 108
        fit = (self.panel_h - 150) // self.row_height
        self.visible_rows = max(0, min(self.max_rows, fit))

    # ------------------------------------------------------------------- text
    def _draw_text(self, frame, text, org, scale, color, bold=False):
        """Draw text with an offset drop shadow for a layered glow look."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        x, y = org
        cv2.putText(
            frame, text, (x + 2, y + 2), font, scale, SHADOW, 3, cv2.LINE_AA
        )
        thickness = 2 if bold else 1
        cv2.putText(
            frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA
        )

    def _draw_hint(self, frame, text):
        self._draw_text(
            frame, text, (self.panel_x + 22, self.panel_y + self.panel_h - 14),
            0.45, DIM,
        )

    # ------------------------------------------------------------------ panel
    def _draw_panel(self, frame):
        x0, y0 = self.panel_x, self.panel_y
        x1, y1 = x0 + self.panel_w, y0 + self.panel_h
        cut = CORNER_CUT

        roi = frame[y0:y1, x0:x1]
        overlay = np.full_like(roi, PANEL_BG, dtype=np.uint8)
        blend = cv2.addWeighted(
            overlay, self.panel_alpha, roi, 1.0 - self.panel_alpha, 0
        )
        frame[y0:y1, x0:x1] = blend

        # Tinted edge aura for a soft holographic seam.
        edge = np.zeros_like(roi)
        cv2.rectangle(edge, (0, 0), (x1 - x0, y1 - y0), CYAN_SOFT, 2)
        frame[y0:y1, x0:x1] = cv2.addWeighted(edge, 0.25, frame[y0:y1, x0:x1], 0.75, 0)

        # Angular cut-corner border frame.
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
        cv2.polylines(
            frame, [pts], True, CYAN_SOFT, 1, cv2.LINE_AA
        )
        cv2.polylines(frame, [pts], True, CYAN, 2, cv2.LINE_AA)

        # Corner tech brackets.
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
                AMBER_BRIGHT,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * cut, cy),
                (cx + sx * arm, cy),
                AMBER_BRIGHT,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * arm // 2, cy + sy * 1),
                (cx + sx * arm, cy + sy * 1),
                AMBER,
                1,
                cv2.LINE_AA,
            )

        # Animated energy dot travelling the header seam.
        t = time.time()
        dot_x = x0 + int(((t * 0.28) % 1.0) * self.panel_w)
        seam_y = self.path_y + 26
        cv2.line(frame, (x0, seam_y), (x1, seam_y), CYAN_SOFT, 1)
        cv2.line(frame, (x0, seam_y + 1), (x1, seam_y + 1), SHADOW, 2)
        cv2.circle(frame, (dot_x, seam_y), 3, AMBER_BRIGHT, -1, cv2.LINE_AA)
        cv2.circle(frame, (dot_x, seam_y), 7, AMBER, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------- rows
    def _draw_row(self, frame, name, is_dir, row_rect, hovered):
        x0, y0, x1, y1 = row_rect
        t = time.time()

        if hovered:
            alpha = HOVER_ALPHA + 0.12 * (0.5 + 0.5 * math.sin(t * 6.0))
            roi = frame[y0:y1, x0:x1]
            overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
            frame[y0:y1, x0:x1] = cv2.addWeighted(
                overlay, alpha, roi, 1.0 - alpha, 0
            )
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            border = (
                int(255 - 120 * pulse),
                int(240),
                int(0 + 120 * pulse),
            )
            cv2.rectangle(frame, (x0, y0), (x1, y1), border, 1, cv2.LINE_AA)
            cv2.rectangle(
                frame,
                (x0, y0),
                (x0 + 4, y1),
                HOVER_BORDER if pulse > 0 else CYAN_SOFT,
                -1,
            )
            cv2.line(
                frame,
                (x0, y1 - 2),
                (x0 + int(0.5 * (x1 - x0)), y1 - 2),
                border,
                2,
                cv2.LINE_AA,
            )

        text_y = y1 - 12
        if is_dir:
            self._draw_text(
                frame,
                ">",
                (x0 + 14, text_y),
                0.6,
                AMBER,
                bold=True,
            )
            self._draw_text(
                frame,
                name,
                (x0 + 36, text_y),
                0.55,
                AMBER_BRIGHT if hovered else AMBER,
            )
        else:
            ext = name.rsplit(".", 1)[-1].upper() if "." in name else ""
            self._draw_text(
                frame, name, (x0 + 18, text_y), 0.55, TEXT
            )
            if ext:
                badge = ext[:3]
                bx = x1 - 12 - cv2.getTextSize(
                    badge, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
                )[0][0]
                self._draw_text(
                    frame, badge, (bx, text_y), 0.45, CYAN if hovered else CYAN_SOFT
                )

    # ------------------------------------------------------------------ hover
    def hovered_index(self, cursor, frame_w, frame_h):
        """Return the list row under the virtual cursor, or None."""
        self._layout(frame_w, frame_h)
        if cursor is None or not cursor.visible:
            return None
        index = int((cursor.y - self.list_top) // self.row_height)
        if index < 0:
            return None
        in_panel = (
            self.panel_x <= cursor.x <= self.panel_x + self.panel_w
        )
        if not in_panel:
            return None
        return index

    def _draw_header(self, frame, title, path_label, suffix=None):
        self._draw_text(
            frame,
            title,
            (self.panel_x + 26, self.title_y),
            0.7,
            TEXT,
            bold=True,
        )
        if len(path_label) > 56:
            path_label = "..." + path_label[-53:]
        self._draw_text(
            frame, path_label, (self.panel_x + 26, self.path_y), 0.55, DIM
        )
        if suffix:
            sw = cv2.getTextSize(
                suffix, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )[0][0]
            self._draw_text(
                frame,
                suffix,
                (self.panel_x + self.panel_w - sw - 26, self.path_y),
                0.5,
                CYAN_SOFT,
            )

    # -------------------------------------------------------------- pager
    def _pager_rects(self):
        x1 = self.panel_x + self.panel_w - 12
        up = (
            x1 - 30,
            self.panel_y + self.panel_h - 76,
            x1,
            self.panel_y + self.panel_h - 48,
        )
        down = (
            x1 - 30,
            self.panel_y + self.panel_h - 42,
            x1,
            self.panel_y + self.panel_h - 14,
        )
        return up, down

    @staticmethod
    def _in_rect(px, py, rect):
        if rect is None:
            return False
        x0, y0, x1, y1 = rect
        return x0 <= px <= x1 and y0 <= py <= y1

    def pager_button_at(self, x, y):
        """Return 'up', 'down', or None for a click position over the pager."""
        up, down = self._pager_rects()
        if self._in_rect(x, y, up):
            return "up"
        if self._in_rect(x, y, down):
            return "down"
        return None

    def _draw_pager(self, frame, cursor):
        self.pager_visible = True
        up, down = self._pager_rects()
        self.scroll_up_rect = up
        self.scroll_down_rect = down

        hover_up = hover_down = False
        if cursor is not None and cursor.visible:
            hover_up = self._in_rect(cursor.x, cursor.y, up)
            hover_down = self._in_rect(cursor.x, cursor.y, down)
        self.hovered_button = "up" if hover_up else "down" if hover_down else None

        for rect, hovered, go_up in ((up, hover_up, True), (down, hover_down, False)):
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
            cy = (y0 + y1) // 2
            tip_y = y0 + 8 if go_up else y1 - 8
            color = HOVER_BORDER if hovered else CYAN
            for dx in (-7, 7):
                cv2.line(
                    frame,
                    (x0 + 15, tip_y),
                    (x0 + 15 + dx, cy),
                    color,
                    2,
                    cv2.LINE_AA,
                )

    def _draw_pager_if_needed(self, frame, cursor, overflow):
        if overflow:
            self._draw_pager(frame, cursor)

    # ------------------------------------------------------------ list render
    def render(
        self,
        frame,
        title,
        directory_label,
        entries,
        cursor=None,
        scroll_offset=0,
        item_suffix=None,
    ):
        """Render the full HUD onto ``frame`` and return the hovered index."""
        frame_h, frame_w = frame.shape[:2]
        self._layout(frame_w, frame_h)

        self.hover_index = self.hovered_index(cursor, frame_w, frame_h)
        clamped_hover = None
        if self.hover_index is not None:
            visible_count = len(entries[scroll_offset:])
            if self.hover_index < visible_count:
                clamped_hover = self.hover_index

        self._draw_panel(frame)
        self._draw_header(
            frame, title, directory_label or "[ THIS PC ]", item_suffix
        )

        overflow = len(entries) > self.visible_rows
        self._draw_pager_if_needed(frame, cursor, overflow)
        hint = (
            "PINCH: OPEN   W/S: SCROLL   Q: QUIT"
            if overflow
            else "PINCH: OPEN   Q: QUIT"
        )
        self._draw_hint(frame, hint)

        start = scroll_offset
        end = min(len(entries), start + self.visible_rows)
        for i, entry in enumerate(entries[start:end]):
            abs_index = start + i
            top = self.list_top + abs_index * self.row_height
            bottom = top + self.row_height - 6
            if bottom > self.panel_y + self.panel_h - 90:
                break
            self._draw_row(
                frame,
                entry.name,
                entry.is_dir,
                (
                    self.panel_x + 10,
                    top,
                    self.panel_x + self.panel_w - 10,
                    bottom,
                ),
                clamped_hover == abs_index,
            )

        return self.hover_index

    # ------------------------------------------------------------ text render
    @staticmethod
    def _wrap_text_line(text, max_px, font, scale, thickness):
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
                        if (
                            cv2.getTextSize(
                                chunk + char, font, scale, thickness
                            )[0][0]
                            > max_px
                        ):
                            lines.append(chunk)
                            chunk = char
                        else:
                            chunk += char
                    current = chunk
        if current:
            lines.append(current)
        return lines

    def wrap_lines(self, lines, frame_w=None):
        """Return the list of lines wrapped to fit the HUD panel width."""
        if frame_w is None:
            frame_w = self.panel_w or self.default_width
        max_px = frame_w - 2 * self.margin_x - 60
        font = cv2.FONT_HERSHEY_SIMPLEX
        wrapped = []
        for raw_line in lines:
            wrapped.extend(
                self._wrap_text_line(raw_line, max_px, font, 0.5, 1)
            )
        return wrapped

    def render_text(
        self,
        frame,
        title,
        directory_label,
        lines,
        scroll_line=0,
        cursor=None,
        file_total=None,
    ):
        """Render a text/markdown document inside the HUD panel.

        Returns ``(hover_index, wrapped_line_count)``.
        """
        frame_h, frame_w = frame.shape[:2]
        self._layout(frame_w, frame_h)
        wrapped = self.wrap_lines(lines, frame_w)

        self.hover_index = self.hovered_index(cursor, frame_w, frame_h)
        hover_back = self.hover_index == 0

        self._draw_panel(frame)
        self._draw_header(
            frame,
            title,
            directory_label or "[ FILE ]",
            None,
        )
        self._draw_row(
            frame,
            "<-- BACK",
            True,
            (
                self.panel_x + 10,
                self.list_top,
                self.panel_x + self.panel_w - 10,
                self.list_top + self.row_height - 6,
            ),
            hover_back,
        )

        line_top = self.list_top + self.row_height + 8
        available_h = self.panel_y + self.panel_h - line_top - 40
        text_rows = max(1, available_h // (self.row_height - 18))
        self.last_text_rows = text_rows
        start = scroll_line
        end = min(len(wrapped), start + text_rows)

        for i, line in enumerate(wrapped[start:end]):
            y = line_top + 32 + i * (self.row_height - 18)
            if y > self.panel_y + self.panel_h - 40:
                break
            stripped = line.lstrip()
            if stripped.startswith("#"):
                self._draw_text(frame, line, (self.panel_x + 26, y), 0.5, AMBER_BRIGHT)
            elif stripped.startswith(("-", "*", "+", ">")) or stripped.startswith(
                ("1.", "2.", "3.")
            ):
                self._draw_text(frame, line, (self.panel_x + 26, y), 0.5, CYAN)
            elif not stripped:
                continue
            else:
                self._draw_text(frame, line, (self.panel_x + 26, y), 0.5, TEXT)

        total = file_total if file_total is not None else len(wrapped)
        status = f"LINES {min(start + 1, total)}-{min(end, total)} / {total}"
        self._draw_text(
            frame,
            status,
            (self.panel_x + 26, self.panel_y + self.panel_h - 34),
            0.5,
            CYAN_SOFT,
        )

        self._draw_pager_if_needed(frame, cursor, len(wrapped) > text_rows)
        self._draw_hint(frame, "DRAG: SCROLL   W/S: SCROLL   Q: QUIT")
        return self.hover_index, len(wrapped)