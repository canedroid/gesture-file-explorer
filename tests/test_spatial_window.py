"""Tests for the spatial window card model and layout math."""

import cv2

from spatial_window import (
    CONTENT_DIRECTORY,
    DEFAULT_LIST_H,
    DEFAULT_LIST_W,
    FOOTER_H,
    LIST_TOP_OFFSET,
    MIN_H,
    MIN_W,
    PAD,
    ROW_H,
    TITLE_BAR_H,
    SpatialWindow,
    clamp,
    compute_window_layout,
    dotted_title,
    point_in_rect,
    row_rect,
    screen_index_for_y,
    wrap_lines,
    wrap_text_line,
)

FRAME_W, FRAME_H = 960, 720


def make_window():
    return SpatialWindow(
        id=1,
        title="THIS PC",
        path="",
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
    )


def test_clamp_bounds_values():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(50, 0, 10) == 10


def test_window_contains_checks_bounds():
    win = make_window()
    assert win.contains(100, 100)
    assert win.contains(60, 60)
    assert win.contains(50, 100) is False
    assert win.contains(100, 60 + DEFAULT_LIST_H + 1) is False


def test_default_dimensions_are_wide_horizontal_panels():
    win = SpatialWindow(id=1, title="T", path="", x=0, y=0)
    assert win.width >= 600
    assert win.height >= 400
    assert win.width / win.height >= 1.4  # wide, not a narrow strip


def test_window_init_clamps_tiny_dimensions_to_minimum():
    win = SpatialWindow(
        id=1, title="T", path="", x=0, y=0, width=100, height=100
    )
    assert win.width == MIN_W
    assert win.height == MIN_H


def test_spawned_default_card_has_required_wide_ratio():
    win = SpatialWindow(
        id=1,
        title="THIS PC",
        path="",
        x=60,
        y=60,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
    )
    assert win.width == DEFAULT_LIST_W
    assert win.height == DEFAULT_LIST_H


def test_layout_title_bar_and_close_button():
    win = make_window()
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    assert layout.x0 == 60
    assert layout.y0 == 60
    assert layout.x1 == 60 + DEFAULT_LIST_W
    assert layout.y1 == 60 + DEFAULT_LIST_H
    x0, ty0, x1, ty1 = layout.title_bar
    assert (x0, ty0) == (60, 60)
    assert x1 == 60 + DEFAULT_LIST_W
    assert ty1 == 60 + TITLE_BAR_H
    cb = layout.close_button
    assert cb[0] <= layout.x1 - 6
    assert cb[3] <= 60 + TITLE_BAR_H


def test_title_area_reserves_close_button_space():
    win = make_window()
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    # The close button starts well to the right of the title origin, leaving
    # a full title lane so text never clips the button.
    assert layout.close_button[0] >= layout.x0 + 0.55 * (layout.x1 - layout.x0)
    assert layout.close_button[0] > layout.x0 + 200


def test_layout_list_rows_fit_between_title_and_footer():
    win = make_window()
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    assert layout.list_top == 60 + LIST_TOP_OFFSET
    assert layout.visible_rows >= 1
    rect = row_rect(layout, 0)
    assert rect[1] >= layout.list_top
    last = row_rect(layout, layout.visible_rows - 1)
    assert last[3] <= layout.y1 - FOOTER_H


def test_row_spacing_is_comfortable():
    assert ROW_H >= 32
    assert PAD >= 12


def test_screen_index_for_y_respects_list_bounds():
    win = make_window()
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    assert screen_index_for_y(layout, layout.list_top) == 0
    inside = screen_index_for_y(layout, layout.list_top + 5)
    assert inside == 0
    row_mid = screen_index_for_y(layout, layout.list_top + layout.row_height)
    assert row_mid == 1
    assert screen_index_for_y(layout, layout.list_top - 1) is None
    assert screen_index_for_y(layout, layout.y1 - 2) is None


def test_screen_index_for_y_accepts_float_coordinates():
    # The live pipeline hands float cursor positions to pinch handling;
    # the row index must come out as an int so win.items[i] never sees a float.
    win = make_window()
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    idx = screen_index_for_y(layout, float(layout.list_top + layout.row_height) + 0.5)
    assert idx == 1
    assert isinstance(idx, int)


def test_layout_clamps_window_into_viewport():
    win = SpatialWindow(
        id=2,
        title="X",
        path="",
        x=-400,
        y=-200,
        width=DEFAULT_LIST_W,
        height=DEFAULT_LIST_H,
        content_type=CONTENT_DIRECTORY,
    )
    layout = compute_window_layout(win, FRAME_W, FRAME_H)
    assert layout.x0 == 0
    assert layout.y0 == 0
    assert layout.x1 <= FRAME_W
    assert layout.y1 <= FRAME_H


def test_point_in_rect_none_guard():
    assert point_in_rect(10, 10, None) is False


def test_wrap_text_line_splits_long_line():
    long_line = "word " * 80
    lines = wrap_text_line(long_line, 240, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    assert len(lines) > 1
    assert "".join(lines).replace(" ", "") == long_line.strip().replace(" ", "")


def test_wrap_text_line_keeps_short_line_whole():
    lines = wrap_text_line("hello", 500, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    assert lines == ["hello"]


def test_wrap_lines_fits_card_width():
    result = wrap_lines(["alpha " * 40], DEFAULT_LIST_W)
    assert len(result) > 1


def test_dotted_title_single_word():
    assert dotted_title("ALFRED") == "A.L.F.R.E.D."


def test_dotted_title_multi_word():
    assert dotted_title("THIS PC") == "T.H.I.S.  P.C."


def test_dotted_title_empty_and_short():
    assert dotted_title("") == ""
    assert dotted_title("X") == "X."
    assert dotted_title("AB CD") == "A.B.  C.D."