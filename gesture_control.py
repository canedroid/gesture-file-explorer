"""Virtual cursor mapping and pinch gesture detection.

Maps the index fingertip landmark to frame pixel coordinates to act as a
virtual cursor, tracks the thumb tip, and toggles a pinch state based on the
Euclidean distance between them.
"""

import math

import cv2

INDEX_TIP_LANDMARK = 8
THUMB_TIP_LANDMARK = 4

PINCH_THRESHOLD_PX = 35.0


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

    def draw(self, frame):
        """Draw the virtual cursor with pinch feedback onto a BGR frame."""
        if not self.visible:
            return frame

        cx, cy = int(round(self.x)), int(round(self.y))

        if self.is_pinched:
            cv2.circle(frame, (cx, cy), 26, (0, 0, 255), 3)
            cv2.circle(frame, (cx, cy), 14, (0, 0, 255), -1)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 255), -1)
        else:
            cv2.circle(frame, (cx, cy), 14, (0, 200, 255), 3)
            cv2.line(
                frame,
                (cx - 18, cy),
                (cx - 5, cy),
                (0, 200, 255),
                2,
            )
            cv2.line(
                frame,
                (cx + 5, cy),
                (cx + 18, cy),
                (0, 200, 255),
                2,
            )
            cv2.line(
                frame,
                (cx, cy - 18),
                (cx, cy - 5),
                (0, 200, 255),
                2,
            )
            cv2.line(
                frame,
                (cx, cy + 5),
                (cx, cy + 18),
                (0, 200, 255),
                2,
            )
            cv2.circle(frame, (cx, cy), 4, (255, 255, 255), -1)

        tag = "PINCHED" if self.is_pinched else "MOVING"
        cv2.putText(
            frame,
            f"{tag}  d={self.pinch_distance:5.1f}px",
            (cx + 30, cy - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return frame