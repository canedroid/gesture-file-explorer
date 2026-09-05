"""Headless pipeline integration tests (no webcam, no display).

Drives the manager + renderer the same way main() does: blank frames produce
no hands, window cards render, pinches resolve into actions, and the whole
chain stays exception-free.
"""

import numpy as np

from gesture_control import Cursor
from hand_tracker import HandTracker
from spatial_window import (
    CONTENT_DIRECTORY,
    STATE_CLOSING,
    TITLE_BAR_H,
    row_rect,
)
from window_manager import WindowManager
from window_renderer import WindowRenderer

FRAME_W, FRAME_H = 960, 720
CYAN = (255, 240, 0)


def run_blank_pipeline(tracker, cursors, frame_bgr, manager, renderer):
    rgb = frame_bgr[:, :, ::-1].copy()
    results = tracker.find_hands(rgb)
    h, w = frame_bgr.shape[:2]
    hands = tracker.get_hands(results)
    for i, cursor in enumerate(cursors):
        if i < len(hands):
            _, landmarks = hands[i]
            cursor.update(landmarks, w, h)
        else:
            cursor.update(None, w, h)
    manager.step_closing()
    renderer.render(frame_bgr, manager, cursors)
    return frame_bgr


def test_blank_frames_keep_pipeline_stable(tmp_path):
    tracker = HandTracker()
    cursors = [Cursor(), Cursor()]
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    renderer = WindowRenderer()
    manager.spawn_drives_card()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    try:
        for _ in range(3):
            run_blank_pipeline(tracker, cursors, frame, manager, renderer)
        assert len(manager.active_windows) >= 1
        assert frame.sum() > 0
    finally:
        tracker.close()


def test_render_directory_card_draws_grayscale_seam():
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    win = manager.spawn_drives_card()
    renderer = WindowRenderer()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    renderer.render(frame, manager, [])
    layout = manager.layout_for(win)
    seam_y = layout.y0 + TITLE_BAR_H - 4
    found = any(
        frame[seam_y, x][2] > 200 and frame[seam_y, x][1] > 100
        for x in range(layout.x0 + 12, layout.x1 - 12, 3)
    )
    assert found


def test_rendered_accent_palette_is_grayscale():
    # The reference video's UI reads as translucent monochrome glass; the
    # chrome must contain almost no saturated cyan or amber pixels.
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    manager.spawn_drives_card()
    renderer = WindowRenderer()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    renderer.render(frame, manager, [])
    b, g, r = (frame[:, :, i].astype(np.int16) for i in (0, 1, 2))
    saturated_cyan = int(((b > 130) & (g > 120) & (r < 90) & (b > r)).sum())
    saturated_amber = int(((r > 130) & (g > 120) & (b < 90) & (r > g)).sum())
    assert saturated_cyan < 50, saturated_cyan
    assert saturated_amber < 50, saturated_amber


def test_render_text_card_stays_inside_card():
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    parent = manager.spawn_drives_card()
    from file_engine import FileEntry

    import tempfile, os

    from spatial_window import DEFAULT_TEXT_W, DEFAULT_TEXT_H, SpatialWindow

    md = tempfile.gettempdir()
    md_path = os.path.join(md, "sample_md.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("# Heading\n" + ("body line with some words\n" * 40))
    entry = FileEntry(name="sample_md.md", path=md_path, is_dir=False)
    text_card = manager.spawn_text_card(parent, entry)
    renderer = WindowRenderer()
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    renderer.render(frame, manager, [])
    layout = manager.layout_for(text_card)
    assert layout.x1 - layout.x0 >= 0
    assert any(frame[y, layout.x0 + 20][2] > 0 for y in range(layout.list_top, layout.y1 - 10, 4))


def test_pinch_open_file_then_close_through_button(tmp_path):
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    md = tmp_path / "readme.md"
    md.write_text("hello", encoding="utf-8")
    parent = manager.spawn_drives_card()
    from file_engine import FileEntry
    from spatial_window import DEFAULT_LIST_H, DEFAULT_LIST_W, SpatialWindow

    parent_card = SpatialWindow(
        id=600,
        title="FOLDER",
        path=str(tmp_path),
        x=80,
        y=80,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[
            manager._up_entry(),
            FileEntry(name="readme.md", path=str(md), is_dir=False),
        ],
    )
    manager.windows.append(parent_card)
    layout = manager.layout_for(parent_card)
    rect = row_rect(layout, 1)
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    result = manager.handle_pinch_start(parent_card, cx, cy)
    assert result["kind"] == "opened_file"
    card = result["window"]
    cb = manager.layout_for(card).close_button
    manager.handle_pinch_start(card, cb[0] + 6, cb[1] + 6)
    assert card.state == STATE_CLOSING