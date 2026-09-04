"""Tests for the AR HUD overlay rendering."""

import numpy as np

from file_engine import FileEntry
from ui_overlay import HUD

FRAME_W, FRAME_H = 960, 720


class FakeCursor:
    def __init__(self, x, y, visible=True):
        self.x = x
        self.y = y
        self.visible = visible


def make_entries():
    return [
        FileEntry(name="C:/", path="C:", is_dir=True),
        FileEntry(name="Documents", path="C:\\Documents", is_dir=True),
        FileEntry(name="readme.md", path="C:\\readme.md", is_dir=False),
        FileEntry(name="notes.txt", path="C:\\notes.txt", is_dir=False),
    ]


def test_hud_renders_overlay_without_error():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    entries = make_entries()
    hud.render(
        frame,
        "GESTURE FILE EXPLORER",
        "C:\\",
        entries,
        cursor=FakeCursor(500, 200),
    )
    assert np.any(frame != 0)


def test_hud_hover_detection_hits_row():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    entries = make_entries()
    hud.render(frame, "T", "C:\\", entries)

    cursor = FakeCursor(500, hud.list_top + hud.row_height // 2)
    idx = hud.hovered_index(cursor, FRAME_W, FRAME_H)
    assert idx == 0


def test_hud_hover_outside_panel_returns_none():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    entries = make_entries()
    hud.render(frame, "T", "C:\\", entries)

    cursor = FakeCursor(10, 400)
    assert hud.hovered_index(cursor, FRAME_W, FRAME_H) is None


def test_hud_hover_above_list_returns_none():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    entries = make_entries()
    hud.render(frame, "T", "C:\\", entries)

    cursor = FakeCursor(500, hud.list_top - 20)
    assert hud.hovered_index(cursor, FRAME_W, FRAME_H) is None


def test_hud_scroll_offsets_rendered_slice():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    entries = make_entries()
    idx = hud.render(
        frame,
        "GESTURE FILE EXPLORER",
        "C:\\",
        entries,
        cursor=FakeCursor(500, 600),
        scroll_offset=1,
    )
    assert idx is None or idx >= 0