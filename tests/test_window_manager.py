"""Tests for the spatial window manager: spawning, pinch actions, drag, and
two-handed scaling."""

import pytest

from file_engine import FileEntry
from spatial_window import (
    ALFRED_H,
    ALFRED_W,
    CONTENT_DIRECTORY,
    CONTENT_TEXT,
    MAX_H,
    MAX_W,
    TITLE_BAR_H,
    DEFAULT_LIST_H,
    DEFAULT_LIST_W,
    DEFAULT_TEXT_W,
    STATE_CLOSING,
    STATE_DRAGGING,
    SpatialWindow,
    row_rect,
)
from window_manager import (
    ASSISTANT_ABOUT,
    ASSISTANT_DRIVES,
    ASSISTANT_HELP,
    WindowManager,
)

FRAME_W, FRAME_H = 960, 720


def make_manager():
    manager = WindowManager()
    manager.set_viewport(FRAME_W, FRAME_H)
    return manager


def file_entry(name, path, is_dir):
    return FileEntry(name=name, path=path, is_dir=is_dir)


def row_point(layout, index):
    rect = row_rect(layout, index)
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    return cx, cy


# ---------------------------------------------------------------- spawning
def test_spawn_drives_card_lists_local_storage():
    manager = make_manager()
    win = manager.spawn_drives_card()
    assert win.title == "THIS PC"
    assert win.content_type == CONTENT_DIRECTORY
    assert len(win.items) >= 1
    assert all(e.is_dir for e in win.items)
    assert win in manager.windows


def test_spawn_directory_card_reads_children(tmp_path):
    manager = make_manager()
    docs = tmp_path / "docs"
    docs.mkdir()
    parent = SpatialWindow(
        id=99,
        title="T",
        path=str(tmp_path),
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[],
    )
    manager.windows.append(parent)
    child = manager.spawn_directory_card(parent, file_entry("docs", str(docs), True))
    assert child in manager.windows
    assert child.title == "docs"
    assert child.path == str(docs)
    assert child.items[0].name == ".."
    assert child.state != STATE_CLOSING


def test_spawn_text_card_reads_lines(tmp_path):
    manager = make_manager()
    notes = list(tmp_path.iterdir())
    md = tmp_path / "notes.md"
    md.write_text("# A\nBody\n", encoding="utf-8")
    parent = SpatialWindow(
        id=99,
        title="T",
        path=str(tmp_path),
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[],
    )
    manager.windows.append(parent)
    child = manager.spawn_text_card(parent, file_entry("notes.md", str(md), False))
    assert child.content_type == CONTENT_TEXT
    assert child.items == ["# A", "Body"]
    assert child.message == ""


def test_spawn_with_permission_error_sets_message(tmp_path, monkeypatch):
    def boom(path):
        raise PermissionError("Access is denied")

    monkeypatch.setattr("window_manager.scan_directory", boom)
    manager = make_manager()
    parent = SpatialWindow(
        id=4,
        title="T",
        path="",
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[],
    )
    manager.windows.append(parent)
    child = manager.spawn_directory_card(
        parent, file_entry("locked", "C:\\locked", True)
    )
    assert child.message
    assert "Access is denied" in child.message
    assert child.items == [manager._up_entry()]


def test_new_card_cascades_away_from_overlap(tmp_path):
    manager = make_manager()
    # Viewport large enough to hold two wide cards next to each other.
    manager.set_viewport(1600, 1000)
    docs = tmp_path / "docs"
    docs.mkdir()
    first = manager.spawn_drives_card()
    first.x = 100
    first.y = 100
    parent = first
    entry = file_entry("docs", str(docs), True)
    # A sibling spawned at the same spot must be nudged aside.
    second = manager.spawn_directory_card(parent, entry)
    assert second.state != STATE_CLOSING
    assert not _overlap(second, first)


def _overlap(a, b):
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


# ------------------------------------------------------------ ALFRED panel
def test_spawn_assistant_card_centered_with_sections():
    manager = make_manager()
    win = manager.spawn_assistant_card()
    assert win.title == "ALFRED"
    assert win.x == (FRAME_W - ALFRED_W) // 2
    assert win.y == (FRAME_H - ALFRED_H) // 2
    assert [i.name for i in win.items] == ["GETTING STARTED", "DRIVES", "ABOUT"]


def test_assistant_drives_row_focuses_or_opens_drives_card():
    manager = make_manager()
    alfred = manager.spawn_assistant_card()
    cx, cy = row_point(manager.layout_for(alfred), 1)
    result = manager.handle_pinch_start(alfred, cx, cy)
    assert result["kind"] == "assistant_action"
    assert result["action"] == ASSISTANT_DRIVES
    assert len([w for w in manager.windows if w.path == ""]) == 1
    # Pinching again focuses the existing drives card, no duplicate.
    manager.handle_pinch_start(alfred, cx, cy)
    assert len([w for w in manager.windows if w.path == ""]) == 1
    assert manager.windows[-1].path == ""


def test_assistant_help_row_opens_text_card():
    manager = make_manager()
    alfred = manager.spawn_assistant_card()
    cx, cy = row_point(manager.layout_for(alfred), 0)
    result = manager.handle_pinch_start(alfred, cx, cy)
    assert result["kind"] == "assistant_action"
    assert result["action"] == ASSISTANT_HELP
    child = result["window"]
    assert child is not None
    assert child.content_type == CONTENT_TEXT
    assert child.title == "GETTING STARTED"


def test_assistant_about_row_opens_text_card():
    manager = make_manager()
    alfred = manager.spawn_assistant_card()
    cx, cy = row_point(manager.layout_for(alfred), 2)
    result = manager.handle_pinch_start(alfred, cx, cy)
    assert result["kind"] == "assistant_action"
    assert result["action"] == ASSISTANT_ABOUT
    assert result["window"].title == "ABOUT ASSISTANT"


def test_pinch_with_float_cursor_position_hits_row():
    # Cursor positions arrive as floats (index.x * frame_width). Regression for
    # "list indices must be integers or slices, not float" on every pinch.
    manager = make_manager()
    win = manager.spawn_drives_card()
    cx, cy = row_point(manager.layout_for(win), 0)
    result = manager.handle_pinch_start(win, float(cx) + 0.5, float(cy) + 0.5)
    assert result["kind"] in ("opened_directory", "opened_file", "nothing")


# ---------------------------------------------------------------- queries
def test_topmost_at_and_focus():
    manager = make_manager()
    a = manager.spawn_drives_card()
    b = manager.spawn_drives_card()
    manager.focus(b)
    assert manager.topmost_at(b.x + 5, b.y + 5) is b
    assert manager.windows[-1] is b
    manager.focus(a)
    assert manager.windows[-1] is a


# --------------------------------------------------------- pinch actions
def test_pinch_close_button_closes_window():
    manager = make_manager()
    win = manager.spawn_drives_card()
    layout = manager.layout_for(win)
    cb = layout.close_button
    result = manager.handle_pinch_start(win, cb[0] + 6, cb[1] + 6)
    assert result["kind"] == "close"
    assert win.state == STATE_CLOSING


def test_pinch_title_bar_starts_drag():
    manager = make_manager()
    win = manager.spawn_drives_card()
    layout = manager.layout_for(win)
    result = manager.handle_pinch_start(win, layout.x0 + 30, layout.y0 + 10)
    assert result["kind"] == "drag"
    assert win.state == STATE_DRAGGING


def test_pinch_directory_row_spawns_child(tmp_path):
    manager = make_manager()
    docs = tmp_path / "docs"
    docs.mkdir()
    parent = SpatialWindow(
        id=1,
        title="T",
        path=str(tmp_path),
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[
            manager._up_entry(),
            file_entry("docs", str(docs), True),
            file_entry("notes.md", str(tmp_path / "notes.md"), False),
        ],
    )
    manager.windows.append(parent)
    layout = manager.layout_for(parent)
    x, y = row_point(layout, 1)
    result = manager.handle_pinch_start(parent, x, y)
    assert result["kind"] == "opened_directory"
    child = result["window"]
    assert child in manager.windows
    assert child.title == "docs"
    assert manager.windows[-1] is child  # focused


def test_pinch_file_row_spawns_text_card(tmp_path):
    manager = make_manager()
    md = tmp_path / "notes.md"
    md.write_text("hi\n", encoding="utf-8")
    parent = SpatialWindow(
        id=1,
        title="T",
        path=str(tmp_path),
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[manager._up_entry(), file_entry("notes.md", str(md), False)],
    )
    manager.windows.append(parent)
    layout = manager.layout_for(parent)
    x, y = row_point(layout, 1)
    result = manager.handle_pinch_start(parent, x, y)
    assert result["kind"] == "opened_file"
    assert result["window"].content_type == CONTENT_TEXT
    assert result["window"].items == ["hi"]


def test_pinch_navigate_up_closes_current_window(tmp_path):
    manager = make_manager()
    parent = SpatialWindow(
        id=1,
        title="T",
        path=str(tmp_path),
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[manager._up_entry()],
    )
    manager.windows.append(parent)
    layout = manager.layout_for(parent)
    x, y = row_point(layout, 0)
    result = manager.handle_pinch_start(parent, x, y)
    assert result["kind"] == "navigate_up"
    assert parent.state == STATE_CLOSING


def test_pinch_pager_down_scrolls_window(tmp_path):
    manager = make_manager()
    parent = SpatialWindow(
        id=1,
        title="T",
        path="",
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
        items=[manager._up_entry()] * 50,
    )
    manager.windows.append(parent)
    layout = manager.layout_for(parent)
    before = parent.scroll_offset
    result = manager.handle_pinch_start(parent, layout.pager_down[0] + 4, layout.pager_down[1] + 4)
    assert result["kind"] == "pager_down"
    assert parent.scroll_offset == before + layout.visible_rows


def test_pinch_above_list_does_nothing(tmp_path):
    manager = make_manager()
    win = manager.spawn_drives_card()
    layout = manager.layout_for(win)
    # Between the title seam and the first list row: inside the panel, above
    # the list, below the drag bar.
    click_y = layout.y0 + TITLE_BAR_H + 4
    assert click_y < layout.list_top
    result = manager.handle_pinch_start(win, layout.x0 + 40, click_y)
    assert result["kind"] == "nothing"


# -------------------------------------------------------------- drag/flick
def test_drag_moves_window_toward_cursor():
    manager = make_manager()
    win = manager.spawn_drives_card()
    start = (win.x, win.y)
    manager.start_drag(win, 300, 300)
    manager.move_drag(win, 300, 300, 10, 10)
    assert win.x > start[0]
    assert win.y > start[1]
    assert win.state == STATE_DRAGGING


def test_release_slow_settles_window():
    manager = make_manager()
    win = manager.spawn_drives_card()
    manager.start_drag(win, 200, 200)
    manager.move_drag(win, 220, 220, 2, 2)
    manager.release_drag(win, 2, 2)
    assert win.state != STATE_DRAGGING
    assert win.state != STATE_CLOSING


def test_release_fast_flicks_window_closing():
    manager = make_manager()
    win = manager.spawn_drives_card()
    manager.start_drag(win, 200, 200)
    manager.release_drag(win, 30, 20)
    assert win.state == STATE_CLOSING


def test_step_closing_reaps_offscreen_window():
    manager = make_manager()
    win = manager.spawn_drives_card()
    manager.close_window(win, vx=50, vy=50)
    assert win in manager.windows
    for _ in range(200):
        manager.step_closing()
    assert win not in manager.windows


# -------------------------------------------------------------- two-hand
def test_two_hand_resize_grows_and_clamps_window():
    manager = make_manager()
    win = manager.spawn_drives_card()
    h1 = (win.x + 30, win.y + 30)
    h2 = (win.x + win.width - 30, win.y + win.height - 30)
    manager.begin_resize(win, *h1, *h2)
    base_w, base_h = win.width, win.height
    wide1 = (win.x, win.y)
    wide2 = (win.x + 4000, win.y)
    manager.apply_resize(win, *wide1, *wide2)
    assert win.width > base_w
    assert win.height > base_h
    assert win.width <= MAX_W
    assert win.height <= MAX_H
    manager.end_all_resizes()
    assert not manager.is_resizing(win)


def test_apply_resize_auto_begins_then_scales():
    manager = make_manager()
    win = manager.spawn_drives_card()
    assert not manager.is_resizing(win)
    manager.apply_resize(win, win.x + 10, win.y + 10, win.x + win.width - 10, win.y + win.height - 10)
    assert manager.is_resizing(win)
    manager.end_all_resizes()