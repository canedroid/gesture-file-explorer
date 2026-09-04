"""Tests for virtual cursor mapping and pinch gesture detection."""

from types import SimpleNamespace

import numpy as np

from gesture_control import Cursor

FRAME_W = 640
FRAME_H = 480


def build_landmarks(index_xy, thumb_xy):
    """Build fake MediaPipe-style landmark objects with 21 joints."""
    landmarks = []
    for i in range(21):
        if i == 8:
            x, y = index_xy
        elif i == 4:
            x, y = thumb_xy
        else:
            x, y = (i * 10 % FRAME_W, (i * 7) % FRAME_H)
        landmarks.append(
            SimpleNamespace(
                x=x / FRAME_W,
                y=y / FRAME_H,
                z=0.0,
            )
        )
    return SimpleNamespace(landmark=landmarks)


def test_cursor_absent_when_no_hand():
    cursor = Cursor()
    cursor.update(None, FRAME_W, FRAME_H)
    assert not cursor.visible
    assert not cursor.is_pinched
    assert not cursor.pinch_started


def test_cursor_position_maps_index_fingertip():
    cursor = Cursor()
    landmarks = build_landmarks((320, 240), (100, 100))
    cursor.update(landmarks, FRAME_W, FRAME_H)
    assert cursor.visible
    assert cursor.x == 320
    assert cursor.y == 240


def test_pinch_not_triggered_when_far_apart():
    cursor = Cursor()
    landmarks = build_landmarks((500, 100), (100, 300))
    cursor.update(landmarks, FRAME_W, FRAME_H)
    assert not cursor.is_pinched
    assert cursor.pinch_distance > 200


def test_pinch_triggers_when_close_and_edge_fires_once():
    cursor = Cursor(min_hold_frames=2)
    landmarks = build_landmarks((320, 240), (330, 245))

    cursor.update(landmarks, FRAME_W, FRAME_H)
    assert not cursor.is_pinched
    assert not cursor.pinch_started

    cursor.update(landmarks, FRAME_W, FRAME_H)
    assert cursor.is_pinched
    assert cursor.pinch_started
    assert cursor.pinch_distance < 35

    # Continuing to hold should not re-fire the edge, but stay pinched.
    cursor.update(landmarks, FRAME_W, FRAME_H)
    assert cursor.is_pinched
    assert not cursor.pinch_started


def test_release_after_hold_allows_repinch():
    cursor = Cursor(min_hold_frames=1)
    close_landmarks = build_landmarks((320, 240), (330, 245))
    far_landmarks = build_landmarks((500, 100), (100, 300))

    cursor.update(close_landmarks, FRAME_W, FRAME_H)
    assert cursor.pinch_started

    cursor.update(far_landmarks, FRAME_W, FRAME_H)
    assert not cursor.is_pinched

    cursor.update(close_landmarks, FRAME_W, FRAME_H)
    assert cursor.pinch_started


def test_cursor_draw_renders_without_error():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    cursor = Cursor(min_hold_frames=1)
    landmarks = build_landmarks((320, 240), (330, 245))
    cursor.update(landmarks, FRAME_W, FRAME_H)
    out = cursor.draw(frame.copy())
    assert out.shape == (FRAME_H, FRAME_W, 3)
    assert out.sum() > 0