"""Virtual cursor mapping and pinch gesture detection.

Maps the index fingertip landmark to frame pixel coordinates to act as a
virtual cursor, tracks the thumb tip, and toggles a pinch state based on the
Euclidean distance between them.

The cursor is rendered as a clean, glowing reticle instead of a full hand
skeleton so the display stays uncluttered.
"""

import math
import time
from collections import deque

import cv2
import numpy as np

INDEX_TIP_LANDMARK = 8
THUMB_TIP_LANDMARK = 4
MIDDLE_TIP_LANDMARK = 12

PINCH_THRESHOLD_PX = 35.0
CLAMP_THRESHOLD_PX = 32.0

RETICLE_CYAN = (255, 240, 0)       # #00F0FF
RETICLE_AMBER = (30, 176, 255)     # #FFB000
RETICLE_GLOW = (120, 170, 255)     # soft cyan-white halo
RETICLE_CORE = (250, 250, 255)
RETICLE_DISMISS = (60, 60, 255)    # hot red for dismiss-clamp


class Cursor:
    """Tracks the virtual cursor position and pinch state per frame."""

    def __init__(
        self,
        pinch_threshold=PINCH_THRESHOLD_PX,
        min_hold_frames=4,
    ):
        self.pinch_threshold = pinch_threshold
        self.min_hold_frames = min_hold_frames

        self.x = 0.0
        self.y = 0.0
        self.visible = False
        self.is_pinched = False
        self.pinch_distance = float("inf")

        self.is_clamped = False
        self.clamp_distance = float("inf")

        self._trail = deque(maxlen=9)

        self._hold_counter = 0
        self._pinch_started = False
        self._was_pinched = False
        self._clamp_hold_counter = 0
        self._clamp_started = False
        self._was_clamped = False

    def update(self, landmarks, frame_width, frame_height):
        """Update cursor state from a hand landmarks result.

        Landmark positions are normalized, so they are scaled to frame pixel
        coordinates. The pinch state toggles when the index-tip to thumb-tip
        distance drops below the threshold; a separate thumb-to-middle clamp
        gesture is exposed for dismissing windows.
        """
        self.is_pinched = False
        self._pinch_started = False
        self.is_clamped = False
        self._clamp_started = False

        if landmarks is None:
            self.visible = False
            self.pinch_distance = float("inf")
            self.clamp_distance = float("inf")
            self._hold_counter = 0
            self._was_pinched = False
            self._clamp_hold_counter = 0
            self._was_clamped = False
            self._trail.clear()
            return self

        index = landmarks.landmark[INDEX_TIP_LANDMARK]
        thumb = landmarks.landmark[THUMB_TIP_LANDMARK]
        middle = landmarks.landmark[MIDDLE_TIP_LANDMARK]

        index_px = (index.x * frame_width, index.y * frame_height)
        thumb_px = (thumb.x * frame_width, thumb.y * frame_height)
        middle_px = (middle.x * frame_width, middle.y * frame_height)

        self.x = index_px[0]
        self.y = index_px[1]
        self.visible = True
        self._trail.append((self.x, self.y))
        self.pinch_distance = math.dist(index_px, thumb_px)
        self.clamp_distance = math.dist(thumb_px, middle_px)

        pressed = self.pinch_distance < self.pinch_threshold

        if pressed:
            self._hold_counter += 1
            if (
                self._hold_counter >= self.min_hold_frames
                and not self._was_pinched
            ):
                self._was_pinched = True
                self._pinch_started = True
                self.is_pinched = True
                self._hold_counter = 0
            elif self._was_pinched:
                self.is_pinched = True
        else:
            self._hold_counter = 0
            self._was_pinched = False

        clenched = self.clamp_distance < CLAMP_THRESHOLD_PX and not self.is_pinched
        if clenched:
            self._clamp_hold_counter += 1
            if (
                self._clamp_hold_counter >= self.min_hold_frames
                and not self._was_clamped
            ):
                self._was_clamped = True
                self._clamp_started = True
                self.is_clamped = True
                self._clamp_hold_counter = 0
            elif self._was_clamped:
                self.is_clamped = True
        else:
            self._clamp_hold_counter = 0
            self._was_clamped = False

        return self

    @property
    def pinch_started(self):
        """True only on the frame a new pinch activation begins."""
        return self._pinch_started

    @property
    def clamp_started(self):
        """True only on the frame a new thumb-middle clamp begins."""
        return self._clamp_started

    @staticmethod
    def _glow(frame, center, radius, color, alpha):
        """Blend a translucent halo around a point for a glow effect."""
        h, w = frame.shape[:2]
        cx, cy = center
        x0, y0 = max(0, cx - radius), max(0, cy - radius)
        x1, y1 = min(w, cx + radius), min(h, cy + radius)
        if x1 <= x0 or y1 <= y0:
            return
        roi = frame[y0:y1, x0:x1]
        overlay = np.zeros_like(roi)
        cv2.circle(
            overlay,
            (cx - x0, cy - y0),
            radius,
            color,
            -1,
            cv2.LINE_AA,
        )
        frame[y0:y1, x0:x1] = cv2.addWeighted(
            overlay, alpha, roi, 1.0 - alpha, 0
        )

    def draw(self, frame):
        """Draw a glowing targeting reticle with a smooth trailing halo."""
        if not self.visible:
            return frame

        cx, cy = int(round(self.x)), int(round(self.y))
        color = RETICLE_AMBER if self.is_pinched else RETICLE_CYAN
        pulse = 0.5 + 0.5 * math.sin(time.time() * 5.0)

        # Smooth comet trail: faint, small orbs fading with age.
        n = len(self._trail)
        for i, (px, py) in enumerate(self._trail):
            if px == self.x and py == self.y:
                continue
            f = (i + 1) / n
            self._glow(
                frame,
                (int(round(px)), int(round(py))),
                int(7 + 15 * f),
                RETICLE_GLOW,
                0.05 + 0.11 * f * pulse,
            )

        if self.is_pinched:
            self._glow(frame, (cx, cy), 34, (0, 40, 120), 0.45 + 0.15 * pulse)
            cv2.circle(frame, (cx, cy), 13, color, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 7, RETICLE_CORE, -1, cv2.LINE_AA)
        elif self.is_clamped:
            self._glow(frame, (cx, cy), 34, (40, 30, 220), 0.5 + 0.2 * pulse)
            cv2.rectangle(
                frame,
                (cx - 13, cy - 13),
                (cx + 13, cy + 13),
                RETICLE_DISMISS,
                2,
                cv2.LINE_AA,
            )
            cv2.circle(frame, (cx, cy), 4, RETICLE_CORE, -1, cv2.LINE_AA)
        else:
            self._glow(
                frame, (cx, cy), 30, RETICLE_GLOW, 0.18 + 0.12 * pulse
            )
            cv2.circle(frame, (cx, cy), 10, color, 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 3, RETICLE_CORE, -1, cv2.LINE_AA)
            arm = 15
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv2.line(
                    frame,
                    (cx + dx * 5, cy + dy * 5),
                    (cx + dx * arm, cy + dy * arm),
                    color,
                    2,
                    cv2.LINE_AA,
                )
        return frame