"""High-end sci-fi glassmorphism rendering for the spatial HUD.

Implements the Jarvis-style design system: translucent navy glass panels with
a vertical depth gradient, multi-layered rounded glowing GRAY_CORE tech borders with
GRAY_AMBER corner brackets, a polished header with a pulsing status indicator and a
pill-backed close button, backing-card list rows with subtle zebra striping and
a GRAY_CORE hover tint, and a clean footer with glow pagination controls.
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
    dotted_title,
    wrap_lines,
)

# ---- palette --------------------------------------------------------------
# Monochrome "hologram" ramp: ivory highlights over warm silver and soft
# grays, so the interface reads as translucent glass instead of neon wireframe.
GRAY_CORE = (252, 252, 250)         # hot ivory core / crisp edge
GRAY_BRIGHT = (238, 238, 235)       # bright accent highlight
GRAY_SOFT = (206, 206, 202)         # soft accent / non-focus state
GRAY_AMBER = (168, 168, 164)        # warm silver accent
GRAY_MID = (150, 150, 148)          # glow mid layer
GRAY_DEEP = (70, 70, 72)            # glow base layer
TEXT = (243, 245, 245)
DIM = (152, 152, 152)
SHADOW = (8, 12, 16)
RED = (70, 70, 255)
WHITE = (252, 253, 253)
PANEL_TOP = (46, 46, 48)            # lighter charcoal glass (top tint)
PANEL_BOT = (26, 26, 28)            # deeper charcoal glass (bottom tint)
ROW_TINT = (235, 235, 230)          # semi-transparent ivory hover backing
ZEBRA = (240, 241, 241)

# ---- typography -----------------------------------------------------------
TITLE_FONT = cv2.FONT_HERSHEY_TRIPLEX
BODY_FONT = cv2.FONT_HERSHEY_COMPLEX
TITLE_SCALE = 0.55
BODY_SCALE = 0.5
SMALL_SCALE = 0.42

PANEL_ALPHA = 0.2
HOVER_ALPHA = 0.32
CORNER_ARM = 18
CORNER_OFF = 7
RAD = 16
ROW_RAD = 10
TEXT_LINE_H = 30

TITLE_X = 48
STATUS_X = 22
STATUS_CY = 25
ACCCENT_X = 15
TITLE_BASELINE = 32
TITLE_UNDERLINE_Y = 41
ROW_CARD_INSET_X = 12
ROW_CARD_INSET_Y = 4
ICON_TILE_L = 18
ICON_TILE_R = 46
TEXT_LEFT = 58
TEXT_RIGHT_PAD = 22
ARC_STEPS = 12


class WindowRenderer:
    """Renders all manager windows onto the camera frame, back to front."""

    def __init__(self):
        self._wrap_cache = {}

    def render(self, frame, manager, cursors=None):
        """Draw every window managed by ``manager`` onto ``frame``."""
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

        closing = win.state == STATE_CLOSING
        fade = max(0.0, min(1.0, win.fade))
        k = fade if closing else 1.0
        is_focus = win is focus

        _blend_gradient(frame, x0, y0, x1, y1, PANEL_ALPHA * fade)
        self._draw_border(frame, layout, is_focus, k)
        self._draw_header(frame, win, layout, is_focus, k, cursors)

        if win.content_type == CONTENT_DIRECTORY:
            self._draw_directory_rows(frame, win, manager, cursors, k)
        else:
            self._draw_text_rows(frame, win, manager, cursors, k)
        self._draw_footer(frame, win, layout, k, cursors)

    # -------------------------------------------------------------- network
    def _draw_border(self, frame, layout, is_focus, k):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        path = _rounded_path(x0, y0, x1, y1, RAD)
        if k <= 0.02:
            cv2.polylines(
                frame, [path], True, _shade(GRAY_MID, k), 1, cv2.LINE_AA
            )
            return

        # Layered glow: wide dark base, mid bloom, crisp edge, hot core.
        if is_focus:
            cv2.polylines(frame, [path], True, _shade(GRAY_DEEP, k), 9, cv2.LINE_AA)
            cv2.polylines(frame, [path], True, _shade(GRAY_MID, k), 6, cv2.LINE_AA)
            cv2.polylines(frame, [path], True, _shade(GRAY_CORE, k), 3, cv2.LINE_AA)
            cv2.polylines(frame, [path], True, _shade(WHITE, k), 1, cv2.LINE_AA)
        else:
            cv2.polylines(frame, [path], True, _shade(GRAY_DEEP, k), 6, cv2.LINE_AA)
            cv2.polylines(frame, [path], True, _shade(GRAY_SOFT, k), 2, cv2.LINE_AA)
            cv2.polylines(frame, [path], True, _shade(GRAY_MID, k), 1, cv2.LINE_AA)

        self._draw_corners(frame, x0, y0, x1, y1, k, is_focus)

    def _draw_corners(self, frame, x0, y0, x1, y1, k, is_focus):
        off = CORNER_OFF
        arm = CORNER_ARM
        color = _shade(GRAY_BRIGHT if is_focus else GRAY_AMBER, k)
        soft = _shade(GRAY_AMBER, k)
        coords = (
            (x0, y0, 1, 1),
            (x1, y0, -1, 1),
            (x0, y1, 1, -1),
            (x1, y1, -1, -1),
        )
        for cx, cy, sx, sy in coords:
            # Ambient glow underlay then crisp GRAY_AMBER ticks.
            cv2.line(
                frame,
                (cx + sx * (off - 1), cy + sy * (off + 1)),
                (cx + sx * (off + arm), cy + sy * (off + 1)),
                _shade(GRAY_AMBER, k * 0.45),
                3,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * (off + 1), cy + sy * (off - 1)),
                (cx + sx * (off + 1), cy + sy * (off + arm)),
                _shade(GRAY_AMBER, k * 0.45),
                3,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * (off - 1), cy + sy * (off + 1)),
                (cx + sx * (off + arm), cy + sy * (off + 1)),
                color,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                frame,
                (cx + sx * (off + 1), cy + sy * (off - 1)),
                (cx + sx * (off + 1), cy + sy * (off + arm)),
                color,
                2,
                cv2.LINE_AA,
            )
        if is_focus and k > 0.4:
            cv2.circle(
                frame, (x0 + RAD, y0 + RAD), 3, _shade(WHITE, k), -1, cv2.LINE_AA
            )
            cv2.circle(
                frame, (x1 - RAD, y0 + RAD), 3, _shade(WHITE, k), -1, cv2.LINE_AA
            )

    # --------------------------------------------------------------- header
    def _draw_header(self, frame, win, layout, is_focus, k, cursors):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        t = time.time()
        pulse = 0.5 + 0.5 * math.sin(t * 5.0)
        dragging = win.state == STATE_DRAGGING

        # Glowing GRAY_AMBER accent bar docked to the far-left edge (vertical).
        accent_x = ACCCENT_X + x0
        accent_y0 = y0 + 11
        accent_y1 = y0 + TITLE_BAR_H - 13
        cv2.line(
            frame,
            (accent_x, accent_y0),
            (accent_x, accent_y1),
            _shade(GRAY_AMBER, k * 0.5),
            4,
            cv2.LINE_AA,
        )
        cv2.line(
            frame,
            (accent_x, accent_y0),
            (accent_x, accent_y1),
            _shade(GRAY_BRIGHT, k),
            2,
            cv2.LINE_AA,
        )

        # Pulsing status indicator dot.
        dot_c = (STATUS_X + x0, y0 + STATUS_CY)
        dot_color = (
            _shade(GRAY_BRIGHT, k)
            if dragging
            else _shade(GRAY_CORE if is_focus else GRAY_SOFT, k)
        )
        glow_r = int(9 + 3 * pulse)
        cv2.circle(frame, dot_c, glow_r + 4, _shade(dot_color, 0.18 * k), -1, cv2.LINE_AA)
        cv2.circle(frame, dot_c, 7, _shade(dot_color, 0.4 * k), -1, cv2.LINE_AA)
        cv2.circle(frame, dot_c, 4, _shade(dot_color, k), -1, cv2.LINE_AA)

# Bold tracked title; the focused (topmost) card uses the reference's
        # dot-spaced logo treatment, everyone else keeps a clean title.
        title_x = x0 + TITLE_X
        reserved = layout.close_button[0] - title_x - 14
        display_title = dotted_title(win.title) if is_focus else win.title
        title = _fit(display_title, max(60, reserved), TITLE_FONT, TITLE_SCALE)
        self._text(
            frame,
            title,
            (title_x, y0 + TITLE_BASELINE),
            TITLE_SCALE,
            _shade(TEXT, k),
            font=TITLE_FONT,
            shadow=True,
        )
        tw = cv2.getTextSize(title, TITLE_FONT, TITLE_SCALE, 1)[0][0]

        if win.state in (STATE_DRAGGING, STATE_CLOSING):
            tag = "LOCK" if win.state == STATE_DRAGGING else "DISMISS"
            self._text(
                frame,
                tag,
                (title_x + tw + 12, y0 + 20),
                SMALL_SCALE,
                _shade(GRAY_BRIGHT, k),
                font=BODY_FONT,
            )

        # Underline accent beneath the title for hierarchy.
        ux = title_x
        ux2 = min(layout.close_button[0] - 14, ux + tw + 6)
        uy = y0 + TITLE_UNDERLINE_Y
        cv2.line(frame, (ux, uy), (ux2, uy), _shade(GRAY_AMBER, k * 0.5), 3, cv2.LINE_AA)
        cv2.line(frame, (ux, uy), (ux2, uy), _shade(GRAY_BRIGHT, k), 1, cv2.LINE_AA)

        # Divider seam with a travelling energy pulse (GRAY_CORE signature line).
        seam_y = y0 + TITLE_BAR_H - 4
        cv2.line(frame, (x0 + 8, seam_y), (x1 - 8, seam_y), _shade(GRAY_CORE, k), 1, cv2.LINE_AA)
        cv2.line(frame, (x0 + 8, seam_y + 1), (x1 - 8, seam_y + 1), _shade(SHADOW, k), 1)
        if k > 0.2:
            dot_x = x0 + 10 + int(((t * 0.3) % 1.0) * (x1 - x0 - 20))
            cv2.circle(frame, (dot_x, seam_y), 3, _shade(GRAY_BRIGHT, k), -1, cv2.LINE_AA)
            cv2.circle(frame, (dot_x, seam_y), 6, _shade(GRAY_AMBER, k * 0.6), 1, cv2.LINE_AA)

        self._draw_close_button(frame, layout, cursors, k)

    def _draw_close_button(self, frame, layout, cursors, k):
        cb = layout.close_button
        hovered = bool(_cursor_hover_rect(cursors, cb))
        path = _rounded_path(cb[0], cb[1], cb[2], cb[3], 12)
        if hovered and k > 0.2:
            _blend_shape(frame, cb, GRAY_AMBER, 0.30, 12)
            cv2.polylines(frame, [path], True, GRAY_BRIGHT, 2, cv2.LINE_AA)
        else:
            _blend_shape(frame, cb, WHITE, 0.09, 12)
            cv2.polylines(frame, [path], True, _shade(GRAY_SOFT, k), 1, cv2.LINE_AA)
        cx = (cb[0] + cb[2]) // 2
        cy = (cb[1] + cb[3]) // 2
        pad = 5
        color = GRAY_BRIGHT if hovered else _shade(GRAY_AMBER, k)
        cv2.line(frame, (cx - pad, cy - pad), (cx + pad, cy + pad), color, 2, cv2.LINE_AA)
        cv2.line(frame, (cx + pad, cy - pad), (cx - pad, cy + pad), color, 2, cv2.LINE_AA)

    # ----------------------------------------------------------------- rows
    def _draw_directory_rows(self, frame, win, manager, cursors, k):
        layout = manager.layout_for(win)
        start = win.scroll_offset
        end = min(len(win.items), start + layout.visible_rows)
        for i in range(start, end):
            item = win.items[i]
            screen_index = i - start
            rect = row_rect(layout, screen_index)
            if rect[3] > layout.y1 - PAD:
                break
            hovered = bool(_cursor_hover_rect(cursors, rect))
            self._draw_row(frame, item, rect, hovered, screen_index, k)

    def _draw_row(self, frame, item, rect, hovered, screen_index, k):
        x0, y0, x1, y1 = rect
        t = time.time()
        card = (x0 + ROW_CARD_INSET_X, y0 + ROW_CARD_INSET_Y,
                x1 - ROW_CARD_INSET_X, y1 - ROW_CARD_INSET_Y)
        cy = (card[1] + card[3]) // 2

        if hovered:
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            _blend_shape(frame, card, ROW_TINT, HOVER_ALPHA + 0.12 * pulse, ROW_RAD)
            hpath = _rounded_path(*card, ROW_RAD)
            cv2.polylines(frame, [hpath], True, _shade(GRAY_CORE, k), 3, cv2.LINE_AA)
            cv2.polylines(frame, [hpath], True, _shade(WHITE, k), 1, cv2.LINE_AA)
            # GRAY_AMBER left accent rail.
            cv2.line(frame, (card[0] + 3, card[1] + 5), (card[0] + 3, card[3] - 5),
                     GRAY_BRIGHT, 2, cv2.LINE_AA)
        else:
            alpha = 0.055 if screen_index % 2 == 0 else 0.022
            _blend_shape(frame, card, ZEBRA, alpha, ROW_RAD)

        baseline = y1 - 16
        self._draw_icon(frame, item, x0, cy, k)
        text_left = x0 + TEXT_LEFT
        text_right = x1 - TEXT_RIGHT_PAD
        if not item.is_dir:
            self._draw_file_row(frame, item, text_left, text_right, baseline, hovered, k)
            return
        if item.name == "..":
            self._text(frame, "<", (text_left, baseline), BODY_SCALE,
                       _shade(GRAY_BRIGHT, k), font=BODY_FONT)
            self._text(frame, "PARENT", (text_left + 22, baseline), SMALL_SCALE,
                       _shade(DIM, k), font=BODY_FONT)
            return
        name = _fit(item.name, max(40, text_right - text_left - 28),
                    BODY_FONT, BODY_SCALE)
        self._text(
            frame,
            name,
            (text_left, baseline),
            BODY_SCALE,
            _shade(GRAY_BRIGHT if hovered else GRAY_AMBER, k),
            font=BODY_FONT,
            shadow=True,
        )

    def _draw_icon(self, frame, item, x0, cy, k):
        tile = (x0 + ICON_TILE_L, cy - 13, x0 + ICON_TILE_R, cy + 13)
        itp = _rounded_path(*tile, 9)
        _blend_shape(frame, tile, WHITE, 0.07, 9)
        cv2.polylines(frame, [itp], True, _shade(GRAY_MID, k), 1, cv2.LINE_AA)
        if item.is_dir:
            cv2.putText(
                frame, ">", (tile[0] + 8, cy + 5),
                cv2.FONT_HERSHEY_COMPLEX, 0.62, _shade(GRAY_AMBER, k),
                2, cv2.LINE_AA,
            )
        else:
            # Document glyph: rounded sheet with a folded corner.
            gx0, gx1 = tile[0] + 6, tile[2] - 6
            gy0, gy1 = cy - 9, cy + 10
            cv2.rectangle(frame, (gx0, gy0), (gx1, gy1), _shade(GRAY_CORE, k), 1, cv2.LINE_AA)
            cv2.line(frame, (gx0, gy0 + 6), (gx1, gy0 + 6), _shade(GRAY_CORE, k), 1, cv2.LINE_AA)
            cv2.line(frame, (gx0, gy0 + 12), (gx1, gy0 + 12), _shade(GRAY_CORE, k), 1, cv2.LINE_AA)

    def _draw_file_row(self, frame, item, text_left, text_right, baseline, hovered, k):
        dot = item.name.rfind(".")
        ext = item.name[dot + 1:].upper()[:3] if dot >= 0 else ""
        badge_x = text_right
        if ext:
            badge = f"{ext}"
            bw = _width(badge, BODY_FONT, SMALL_SCALE)
            badge_x = text_right - bw - 8
            self._text(frame, badge, (badge_x, baseline - 4), SMALL_SCALE,
                       _shade(GRAY_SOFT, k), font=BODY_FONT)
        name_max = max(40, badge_x - text_left - 14)
        self._text(frame, _fit(item.name, name_max, BODY_FONT, BODY_SCALE),
                   (text_left, baseline), BODY_SCALE,
                   _shade(WHITE if hovered else TEXT, k), font=BODY_FONT, shadow=True)

    # ----------------------------------------------------------------- text
    def _draw_text_rows(self, frame, win, manager, cursors, k):
        layout = manager.layout_for(win)
        wrapped = self._wrapped_for(win)
        start = win.scroll_offset
        text_rows = max(1, (layout.y1 - layout.list_top - 26) // TEXT_LINE_H)
        if wrapped:
            win.scroll_offset = min(win.scroll_offset, max(0, len(wrapped) - text_rows))

        content_left = layout.list_left + 8
        max_w = layout.list_right - content_left - 20
        y = layout.list_top + 30
        for line in wrapped[start:start + text_rows]:
            if y + 8 > layout.y1 - 22:
                break
            stripped = line.lstrip()
            color = TEXT
            if stripped.startswith("#"):
                color = GRAY_BRIGHT
            elif stripped.startswith(("-", "*", "+", ">")) or stripped.startswith(
                ("1.", "2.", "3.")
            ):
                color = GRAY_CORE
            if stripped:
                self._text(frame, _fit(line, max_w, BODY_FONT, BODY_SCALE),
                           (content_left, y), BODY_SCALE, _shade(color, k),
                           font=BODY_FONT)
            y += TEXT_LINE_H

        self._draw_pager(frame, layout, cursors, k, overflow=len(wrapped) > text_rows)

    def _wrapped_for(self, win):
        key = (win.id, win.width)
        cached = self._wrap_cache.get(key)
        if cached is None:
            cached = wrap_lines(win.items, win.width)
            self._wrap_cache[key] = cached
        return cached

    # ---------------------------------------------------------------- pager
    def _draw_pager(self, frame, layout, cursors, k, overflow):
        if not overflow:
            return
        for rect, go_up, hovered in (
            (layout.pager_up, True, bool(_cursor_hover_rect(cursors, layout.pager_up))),
            (layout.pager_down, False, bool(_cursor_hover_rect(cursors, layout.pager_down))),
        ):
            path = _rounded_path(rect[0], rect[1], rect[2], rect[3], 8)
            if hovered:
                _blend_shape(frame, rect, GRAY_AMBER, 0.28, 8)
                cv2.polylines(frame, [path], True, GRAY_BRIGHT, 2, cv2.LINE_AA)
            else:
                _blend_shape(frame, rect, WHITE, 0.07, 8)
                cv2.polylines(frame, [path], True, _shade(GRAY_SOFT, k), 1, cv2.LINE_AA)
            mid = (rect[0] + rect[2]) // 2
            cy = (rect[1] + rect[3]) // 2
            tip_y = rect[1] + 6 if go_up else rect[3] - 6
            color = GRAY_BRIGHT if hovered else _shade(GRAY_BRIGHT, k)
            for dx in (-5, 5):
                cv2.line(frame, (mid, tip_y), (mid + dx, cy), color, 2, cv2.LINE_AA)

    # ---------------------------------------------------------------- footer
    def _draw_footer(self, frame, win, layout, k, cursors):
        x0, y0, x1, y1 = layout.x0, layout.y0, layout.x1, layout.y1
        seam_y = y1 - 27
        cv2.line(frame, (x0 + 10, seam_y), (x1 - 64, seam_y), _shade(GRAY_SOFT, k * 0.7), 1, cv2.LINE_AA)
        cv2.line(frame, (x0 + 10, seam_y + 1), (x1 - 64, seam_y + 1), _shade(SHADOW, k), 1)

        baseline = y1 - 13
        if win.message:
            msg = "!" + win.message[:54]
            mw = _width(msg, BODY_FONT, SMALL_SCALE) + 24
            pill = (x0 + 4, y1 - 30, x0 + mw, y1 - 4)
            _blend_shape(frame, pill, RED, 0.28, 10)
            cv2.polylines(frame, [_rounded_path(*pill, 10)], True, RED, 1, cv2.LINE_AA)
            self._text(frame, msg, (x0 + 16, baseline), SMALL_SCALE,
                       _shade((150, 150, 255), k), font=BODY_FONT)
            return
        if win.content_type == CONTENT_DIRECTORY:
            total = len(win.items)
            label = f"FILES {total:03d}" if total else "EMPTY"
        else:
            total = len(self._wrapped_for(win))
            first = min(win.scroll_offset + 1, max(total, 1))
            last = min(win.scroll_offset + layout.visible_rows, total)
            label = f"LINES {first}-{last} / {total}"
        self._text(frame, label, (x0 + PAD, baseline), SMALL_SCALE,
                   _shade(GRAY_SOFT, k), font=BODY_FONT)

    # ----------------------------------------------------------------- utils
    @staticmethod
    def _text(frame, text, org, scale, color, font=BODY_FONT, shadow=True):
        """Draw text with an optional soft shadow for layering."""
        x, y = org
        if shadow:
            cv2.putText(frame, text, (x + 1, y + 1), font, scale, SHADOW, 2, cv2.LINE_AA)
        cv2.putText(frame, text, (x, y), font, scale, color, 1, cv2.LINE_AA)


def _width(text, font, scale):
    return cv2.getTextSize(text, font, scale, 1)[0][0]


def _fit(text, max_px, font, scale):
    if not text:
        return text
    if cv2.getTextSize(text, font, scale, 1)[0][0] <= max_px:
        return text
    while text and cv2.getTextSize(text + "...", font, scale, 1)[0][0] > max_px:
        text = text[:-1]
    return text + "..."


def _shade(color, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(c * k) for c in color) if k < 1.0 else color


def _rounded_path(x0, y0, x1, y1, r, steps=ARC_STEPS):
    """Rounded-rectangle polygon path (counter-clockwise, closed)."""
    r = max(1, min(float(r), (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    cx, cy = x0 + r, y0 + r
    dx, dy = x1 - r, y1 - r
    pts = []

    def arc(px, py, a0, a1):
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((px + r * math.cos(a), py + r * math.sin(a)))

    arc(cx, cy, math.pi, 1.5 * math.pi)
    arc(dx, cy, 1.5 * math.pi, 2.0 * math.pi)
    arc(dx, dy, 0.0, 0.5 * math.pi)
    arc(cx, dy, 0.5 * math.pi, math.pi)
    return np.array(pts, np.int32)


def _blend_gradient(frame, x0, y0, x1, y1, alpha):
    """Blend a vertical navy glass gradient over the card region."""
    h, w = y1 - y0, x1 - x0
    if h <= 0 or w <= 0:
        return
    grad = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top = np.array(PANEL_TOP, np.float32)
    bot = np.array(PANEL_BOT, np.float32)
    overlay = (top * (1.0 - grad) + bot * grad).astype(np.uint8)
    overlay = np.broadcast_to(overlay, (h, w, 3)) if overlay.shape[2] == 3 else overlay
    roi = frame[y0:y1, x0:x1]
    frame[y0:y1, x0:x1] = cv2.addWeighted(
        overlay, alpha, roi, 1.0 - alpha, 0
    )


def _blend_shape(frame, rect, color, alpha, radius):
    """Blend a translucent rounded-shape backing over a region."""
    x0, y0, x1, y1 = rect
    h, w = y1 - y0, x1 - x0
    if h <= 0 or w <= 0:
        return
    roi = frame[y0:y1, x0:x1]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [_rounded_path(0, 0, w, h, radius)], 255)
    overlay = np.full_like(roi, color, np.uint8)
    blended = cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0)
    out = roi.copy()
    out[mask > 0] = blended[mask > 0]
    frame[y0:y1, x0:x1] = out


def row_rect(layout, index):
    """Back-compat hook pointing at the shared spatial_window helper."""
    from spatial_window import row_rect as _rr

    return _rr(layout, index)


def _cursor_hover_rect(cursors, rect):
    if not rect:
        return False
    x0, y0, x1, y1 = rect
    for cursor in cursors:
        if cursor.visible and x0 <= cursor.x <= x1 and y0 <= cursor.y <= y1:
            return True
    return False
