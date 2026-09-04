"""Real-time hand landmark tracking built on MediaPipe Hands."""

import cv2
import mediapipe as mp


class HandTracker:
    """Detect and track hand landmarks on single video frames."""

    def __init__(
        self,
        max_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    ):
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_styles = mp.solutions.drawing_styles
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def find_hands(self, frame_rgb):
        """Process an RGB frame and return the MediaPipe hands result."""
        return self.hands.process(frame_rgb)

    def get_landmarks(self, results, index=0):
        """Return the landmark list for the nth detected hand, or None."""
        if not results.multi_hand_landmarks:
            return None
        if index >= len(results.multi_hand_landmarks):
            return None
        return results.multi_hand_landmarks[index]

    def draw_landmarks(self, frame, results):
        """Overlay the hand skeleton and landmarks on a BGR frame."""
        if not results.multi_hand_landmarks:
            return frame
        for hand_landmarks in results.multi_hand_landmarks:
            self.mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_styles.get_default_hand_landmarks_style(),
                self.mp_styles.get_default_hand_connections_style(),
            )
        return frame

    def close(self):
        self.hands.close()