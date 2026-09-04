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


def test_hud_render_text_without_error():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    lines = ["# Heading", "", "some body text", "- bullet"]
    hud.render_text(frame, "FILE VIEW", "notes.md", lines, scroll_line=0)

    cursor = FakeCursor(500, hud.list_top + hud.row_height // 2)
    hover, wrapped = hud.render_text(
        frame,
        "FILE VIEW",
        "notes.md",
        lines,
        scroll_line=0,
        cursor=cursor,
    )
    assert hover == 0
    assert wrapped >= len(lines)


def test_hud_wrap_lines_splits_long_lines():
    hud = HUD()
    long_line = "word " * 200
    wrapped = hud.wrap_lines([long_line], frame_w=FRAME_W)
    assert len(wrapped) > 1
    assert "".join(wrapped).replace(" ", "") == long_line.strip().replace(
        " ", ""
    )


def many_entries(n):
    return [
        FileEntry(name=f"item_{i}", path=f"C:\\item_{i}", is_dir=(i % 2 == 0))
        for i in range(n)
    ]


def test_hud_pager_button_hit_testing():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    hud.render(frame, "T", "C:\\", many_entries(200))  # overflows panel

    assert hud.scroll_up_rect is not None
    assert hud.scroll_down_rect is not None
    up = hud.scroll_up_rect
    down = hud.scroll_down_rect
    assert hud.pager_button_at(up[0] + 5, up[1] + 5) == "up"
    assert hud.pager_button_at(down[0] + 5, down[1] + 5) == "down"
    assert hud.pager_button_at(300, 400) is None


def test_hud_render_text_pager_visible_for_long_document():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    long_lines = [f"line number {i} with some contents" for i in range(500)]
    hud.render_text(frame, "FILE VIEW", "long.md", long_lines)
    assert hud.last_text_rows >= 1
    assert hud.scroll_up_rect is not None
    assert hud.scroll_down_rect is not None


def test_hud_visible_rows_capped_at_six():
    frame = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    hud = HUD()
    hud.render(
        frame,
        "T",
        "THIS PC",
        many_entries(200),
        cursor=FakeCursor(500, hud.row_height * 20),
    )
    assert hud.visible_rows <= 6
    assert hud.visible_rows >= 1