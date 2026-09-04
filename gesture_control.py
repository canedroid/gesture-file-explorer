"""Virtual cursor mapping and pinch gesture detection.

Maps the index fingertip landmark to frame pixel coordinates to act as a
virtual cursor, tracks the thumb tip, and toggles a pinch state based on the
Euclidean distance between them.

The cursor is rendered as a clean, glowing reticle instead of a full hand
skeleton so the display stays uncluttered.
"""

import math
import time

import cv2
import numpy as np

INDEX_TIP_LANDMARK = 8
THUMB_TIP_LANDMARK = 4

PINCH_THRESHOLD_PX = 35.0

RETICLE_CYAN = (255, 240, 0)       # #00F0FF
RETICLE_AMBER = (30, 176, 255)     # #FFB000
RETICLE_GLOW = (120, 170, 255)     # soft cyan-white halo
RETICLE_CORE = (250, 250, 255)


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

        self._hold_counter = 0
        self._pinch_started = False
        self._was_pinched = False

    def update(self, landmarks, frame_width, frame_height):
        """Update cursor state from a hand landmarks result.

        Landmark positions are normalized, so they are scaled to frame pixel
        coordinates. The pinch state toggles when the index-tip to thumb-tip
        distance drops below the threshold.
        """
        self.is_pinched = False
        self._pinch_started = False

        if landmarks is None:
            self.visible = False
            self.pinch_distance = float("inf")
            self._hold_counter = 0
            self._was_pinched = False
            return self

        index = landmarks.landmark[INDEX_TIP_LANDMARK]
        thumb = landmarks.landmark[THUMB_TIP_LANDMARK]

        index_px = (index.x * frame_width, index.y * frame_height)
        thumb_px = (thumb.x * frame_width, thumb.y * frame_height)

        self.x = index_px[0]
        self.y = index_px[1]
        self.visible = True
        self.pinch_distance = math.dist(index_px, thumb_px)

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

        return self

    @property
    def pinch_started(self):
        """True only on the frame a new pinch activation begins."""
        return self._pinch_started

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
        """Draw a minimal glowing target reticle onto a BGR frame."""
        if not self.visible:
            return frame

        cx, cy = int(round(self.x)), int(round(self.y))
        color = RETICLE_AMBER if self.is_pinched else RETICLE_CYAN
        pulse = 0.5 + 0.5 * math.sin(time.time() * 5.0)

        if self.is_pinched:
            self._glow(frame, (cx, cy), 34, (0, 40, 120), 0.45 + 0.15 * pulse)
            cv2.circle(frame, (cx, cy), 13, color, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 7, RETICLE_CORE, -1, cv2.LINE_AA)
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