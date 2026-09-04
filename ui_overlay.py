"""Sci-fi AR HUD overlay rendered directly on the camera frame."""

import cv2
import numpy as np

ACCENT = (255, 180, 0)          # BGR amber
ACCENT_BRIGHT = (255, 230, 120)
HEADER_COLOR = (240, 220, 140)
DIR_COLOR = (255, 210, 90)      # amber for folders
FILE_COLOR = (130, 230, 255)    # cyan for files
HOVER_BG = (40, 70, 120)
HOVER_BORDER = (255, 180, 0)
PANEL_BG = (12, 18, 38)
TEXT_DIM = (170, 180, 200)

PANEL_ALPHA = 0.45
HOVER_ALPHA = 0.6


class HUD:
    """Semi-transparent heads-up display laid out on the camera frame."""

    default_width = 960

    def __init__(
        self,
        panel_alpha=PANEL_ALPHA,
        margin_x=40,
        margin_top=80,
        margin_bottom=70,
        row_height=34,
    ):
        self.panel_alpha = panel_alpha
        self.margin_x = margin_x
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.row_height = row_height

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

    def _layout(self, frame_w, frame_h):
        self.panel_x = self.margin_x
        self.panel_y = self.margin_top
        self.panel_w = frame_w - 2 * self.margin_x
        self.panel_h = frame_h - self.margin_top - self.margin_bottom
        self.title_y = self.panel_y + 34
        self.path_y = self.panel_y + 62
        self.list_top = self.panel_y + 92
        self.visible_rows = max(
            0, (self.panel_h - 100) // self.row_height
        )

    def _pager_rects(self):
        x1 = self.panel_x + self.panel_w - 12
        up = (x1 - 30, self.panel_y + self.panel_h - 74, x1, self.panel_y + self.panel_h - 46)
        down = (x1 - 30, self.panel_y + self.panel_h - 40, x1, self.panel_y + self.panel_h - 12)
        return up, down

    @staticmethod
    def _in_rect(px, py, rect):
        if rect is None:
            return False
        x0, y0, x1, y1 = rect
        return x0 <= px <= x1 and y0 <= py <= y1

    def _draw_pager(self, frame, cursor):
        self.pager_visible = True
        up, down = self._pager_rects()
        self.scroll_up_rect = up
        self.scroll_down_rect = down
        self.hovered_button = None

        hover_up = hover_down = False
        if cursor is not None and cursor.visible:
            hover_up = self._in_rect(cursor.x, cursor.y, up)
            hover_down = self._in_rect(cursor.x, cursor.y, down)
        if hover_up:
            self.hovered_button = "up"
        elif hover_down:
            self.hovered_button = "down"

        for rect, hovered, up_dir in (
            (up, hover_up, True),
            (down, hover_down, False),
        ):
            x0, y0, x1, y1 = rect
            if hovered:
                roi = frame[y0:y1, x0:x1]
                overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
                frame[y0:y1, x0:x1] = cv2.addWeighted(
                    overlay, HOVER_ALPHA, roi, 1.0 - HOVER_ALPHA, 0
                )
            cv2.rectangle(frame, (x0, y0), (x1, y1), ACCENT_BRIGHT if hovered else ACCENT, 1)
            cy = (y0 + y1) // 2
            for dx in (-7, 7):
                tip_y = y0 + 8 if up_dir else y1 - 8
                cv2.line(
                    frame,
                    (x0 + 15, tip_y),
                    (x0 + 15 + dx, cy),
                    ACCENT_BRIGHT,
                    2,
                )

    def _draw_pager_if_needed(self, frame, cursor, overflow):
        if overflow:
            self._draw_pager(frame, cursor)

    def _draw_hint(self, frame, text):
        cv2.putText(
            frame,
            text,
            (self.panel_x + 22, self.panel_y + self.panel_h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            TEXT_DIM,
            1,
            cv2.LINE_AA,
        )

    def pager_button_at(self, x, y):
        """Return 'up', 'down', or None for a click position over the pager."""
        up, down = self._pager_rects()
        if self._in_rect(x, y, up):
            return "up"
        if self._in_rect(x, y, down):
            return "down"
        return None

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

    def _draw_panel(self, frame):
        x0, y0 = self.panel_x, self.panel_y
        x1, y1 = x0 + self.panel_w, y0 + self.panel_h
        roi = frame[y0:y1, x0:x1]
        overlay = np.full_like(roi, PANEL_BG, dtype=np.uint8)
        blended = cv2.addWeighted(
            overlay, self.panel_alpha, roi, 1.0 - self.panel_alpha, 0
        )
        frame[y0:y1, x0:x1] = blended

        cv2.rectangle(frame, (x0, y0), (x1, y1), ACCENT, 1)
        corner = 22
        for cx, cy, dir_x, dir_y in (
            (x0, y0, 1, 1),
            (x1, y0, -1, 1),
            (x0, y1, 1, -1),
            (x1, y1, -1, -1),
        ):
            cv2.line(frame, (cx, cy), (cx + corner * dir_x, cy), ACCENT_BRIGHT, 2)
            cv2.line(frame, (cx, cy), (cx, cy + corner * dir_y), ACCENT_BRIGHT, 2)

        line_y = y0 + 74
        cv2.line(frame, (x0, line_y), (x1, line_y), ACCENT, 1)

    def _draw_row(self, frame, name, is_dir, row_rect, hovered):
        x0, y0, x1, y1 = row_rect
        if hovered:
            roi = frame[y0:y1, x0:x1]
            overlay = np.full_like(roi, HOVER_BG, dtype=np.uint8)
            blended = cv2.addWeighted(
                overlay, HOVER_ALPHA, roi, 1.0 - HOVER_ALPHA, 0
            )
            frame[y0:y1, x0:x1] = blended
            cv2.rectangle(frame, (x0, y0), (x1, y1), HOVER_BORDER, 1)

        color = DIR_COLOR if is_dir else FILE_COLOR
        marker = ">>" if is_dir else "  "
        if is_dir:
            label = f"{marker} [{name}]"
        else:
            label = f"{marker}  {name}"

        cv2.putText(
            frame,
            label,
            (x0 + 18, y1 - 9),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            1,
            cv2.LINE_AA,
        )

    def _draw_header(self, frame, title, path_label, suffix=None):
        cv2.putText(
            frame,
            title,
            (self.panel_x + 22, self.title_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            HEADER_COLOR,
            2,
            cv2.LINE_AA,
        )
        if len(path_label) > 60:
            path_label = "..." + path_label[-57:]
        cv2.putText(
            frame,
            path_label,
            (self.panel_x + 22, self.path_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            TEXT_DIM,
            1,
            cv2.LINE_AA,
        )

        if suffix:
            cv2.putText(
                frame,
                suffix,
                (self.panel_x + self.panel_w - 210, self.path_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                ACCENT_BRIGHT,
                1,
                cv2.LINE_AA,
            )

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
            frame, title, directory_label or "[ ROOT ]", item_suffix
        )

        overflow = len(entries) > self.visible_rows
        self._draw_pager_if_needed(frame, cursor, overflow)
        if self.hovered_button is None and self.hover_index is not None:
            self.hovered_button = None

        hint = "PINCH: OPEN  W/S: SCROLL  Q: QUIT" if overflow else "PINCH: OPEN  Q: QUIT"
        self._draw_hint(frame, hint)

        start = scroll_offset
        end = min(len(entries), start + self.visible_rows)
        for i, entry in enumerate(entries[start:end]):
            abs_index = start + i
            top = self.list_top + abs_index * self.row_height
            bottom = top + self.row_height - 4
            if bottom > self.panel_y + self.panel_h - 10:
                break
            self._draw_row(
                frame,
                entry.name,
                entry.is_dir,
                (
                    self.panel_x + 8,
                    top,
                    self.panel_x + self.panel_w - 8,
                    bottom,
                ),
                clamped_hover == abs_index,
            )

        return self.hover_index

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
            directory_label or "[ FILE VIEW ]",
            None,
        )
        self._draw_row(
            frame,
            "<-- BACK",
            True,
            (
                self.panel_x + 8,
                self.list_top,
                self.panel_x + self.panel_w - 8,
                self.list_top + self.row_height - 4,
            ),
            hover_back,
        )

        line_top = self.list_top + self.row_height
        available_h = self.panel_y + self.panel_h - line_top - 24
        text_rows = max(1, available_h // (self.row_height - 16))
        self.last_text_rows = text_rows
        start = scroll_line
        end = min(len(wrapped), start + text_rows)
        font = cv2.FONT_HERSHEY_SIMPLEX

        for i, line in enumerate(wrapped[start:end]):
            y = line_top + 28 + i * (self.row_height - 16)
            if y > self.panel_y + self.panel_h - 30:
                break
            color = FILE_COLOR
            stripped = line.lstrip()
            if stripped.startswith("#"):
                color = HEADER_COLOR
            elif stripped.startswith(("-", "*", "+", ">")) or stripped.startswith(
                ("1.", "2.", "3.")
            ):
                color = ACCENT
            elif not stripped:
                continue
            cv2.putText(
                frame,
                line,
                (self.panel_x + 22, y),
                font,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

        total = file_total if file_total is not None else len(wrapped)
        status = f"LN {min(start+1, total)}-{min(end, total)} / {total}"
        cv2.putText(
            frame,
            status,
            (self.panel_x + 22, self.panel_y + self.panel_h - 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            TEXT_DIM,
            1,
            cv2.LINE_AA,
        )

        self._draw_pager_if_needed(
            frame, cursor, len(wrapped) > text_rows
        )
        self._draw_hint(
            frame,
            "DRAG: SCROLL  W/S: SCROLL  Q: QUIT",
        )
        return self.hover_index, len(wrapped)