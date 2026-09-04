"""Synthetic-frame smoke tests that do not require a webcam or a display."""

import numpy as np
import pytest

from hand_tracker import HandTracker


def test_hand_tracker_processes_blank_frame():
    tracker = HandTracker(
        min_detection_confidence=0.7, min_tracking_confidence=0.7
    )
    try:
        frame_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        results = tracker.find_hands(frame_rgb)
        assert results.multi_hand_landmarks is None
        frame_bgr = frame_rgb[:, :, ::-1].copy()
        tracker.draw_landmarks(frame_bgr, results)
    finally:
        tracker.close()


def test_hand_tracker_processes_noisy_frame():
    tracker = HandTracker()
    try:
        rng = np.random.default_rng(42)
        frame_rgb = rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
        results = tracker.find_hands(frame_rgb)
        frame_bgr = frame_rgb[:, :, ::-1].copy()
        tracker.draw_landmarks(frame_bgr, results)
    finally:
        tracker.close()