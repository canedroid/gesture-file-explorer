"""Headless pipeline integration test (no webcam, no display)."""

import numpy as np

from app import ExplorerApp, ViewState
from gesture_control import Cursor
from hand_tracker import HandTracker
from ui_overlay import HUD


def run_frame_pipeline(tracker, cursor, frame_bgr, app, hud, pinch_index=None):
    """Mirror what main() does for one frame, minus imshow/waitKey."""
    frame = cv2_flip(frame_bgr)
    rgb = frame[:, :, ::-1].copy()
    results = tracker.find_hands(rgb)
    tracker.draw_landmarks(frame, results)

    height, width = frame.shape[:2]
    landmarks = tracker.get_landmarks(results)
    cursor.update(landmarks, width, height)

    if pinch_index is not None:
        app.activate_index(pinch_index)

    if app.is_file_view:
        hud.render_text(
            frame,
            "FILE VIEW",
            app.directory_label,
            app.lines,
            scroll_line=app.scroll_offset,
            cursor=cursor,
        )
    else:
        hud.render(
            frame,
            "TITLE",
            app.directory_label,
            app.entries,
            cursor=cursor,
            scroll_offset=app.scroll_offset,
        )
    return frame


def cv2_flip(frame):
    return frame[:, ::-1].copy()


def test_end_to_end_navigation_and_file_read(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text(
        "# Docs\nLine two\n", encoding="utf-8"
    )

    tracker = HandTracker()
    cursor = Cursor(min_hold_frames=1)
    hud = HUD()
    app = ExplorerApp()
    frame = np.zeros((720, 960, 3), dtype=np.uint8)

    try:
        # Blank frames: no hand tracked, pipeline stays stable.
        run_frame_pipeline(tracker, cursor, frame, app, hud)
        assert app.state is ViewState.ROOT

        # Navigate programmatically into the temp folder.
        app.navigate_to(str(tmp_path))
        run_frame_pipeline(tracker, cursor, frame, app, hud)
        assert app.state is ViewState.FOLDER_VIEW

        # Enter the docs folder.
        idx = next(
            i for i, e in enumerate(app.entries) if e.name == "docs"
        )
        run_frame_pipeline(tracker, cursor, frame, app, hud, pinch_index=idx)
        assert app.state is ViewState.FOLDER_VIEW

        # Open readme.md by its absolute row index.
        idx = next(
            i for i, e in enumerate(app.entries) if e.name == "readme.md"
        )
        run_frame_pipeline(tracker, cursor, frame, app, hud, pinch_index=idx)
        assert app.state is ViewState.FILE_VIEW
        assert app.lines == ["# Docs", "Line two"]

        # Back out via the back button row 0.
        run_frame_pipeline(tracker, cursor, frame, app, hud, pinch_index=0)
        assert app.state is ViewState.FOLDER_VIEW
    finally:
        tracker.close()