"""Tests for the gesture-to-navigation state machine."""

from app import ExplorerApp, ViewState
from file_engine import FileEntry


def mkdir_scaffold(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "notes.md").write_text("# Title\n\nSome body\n", encoding="utf-8")
    (tmp_path / "plain.txt").write_text("hello world\n", encoding="utf-8")
    return tmp_path


def test_initial_state_is_root_with_drives():
    app = ExplorerApp()
    assert app.state is ViewState.ROOT
    assert len(app.entries) >= 1
    assert all(e.is_dir for e in app.entries)


def test_navigate_to_folder_lists_back_then_entries(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    assert app.state is ViewState.FOLDER_VIEW
    assert app.entries[0].name == "<-- BACK"
    names = {e.name for e in app.entries}
    assert "subdir" in names
    assert "notes.md" in names
    assert "plain.txt" in names


def test_pinch_on_folder_navigates_into_it(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    idx = next(
        i for i, e in enumerate(app.entries) if e.name == "subdir"
    )
    app.activate_index(idx)
    target = str(tmp_path / "subdir")
    assert app.state is ViewState.FOLDER_VIEW
    assert app.current_path.replace("/", "\\") == target.replace("/", "\\")
    assert app.history and app.history[-1].replace("/", "\\") == str(
        tmp_path
    ).replace("/", "\\")


def test_pinch_on_file_opens_file_view(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    idx = next(
        i for i, e in enumerate(app.entries) if e.name == "notes.md"
    )
    app.activate_index(idx)
    assert app.state is ViewState.FILE_VIEW
    assert app.is_file_view
    assert app.lines == ["# Title", "", "Some body"]
    assert app.file_name == "notes.md"


def test_back_entry_from_folder_returns_to_root_without_history(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    app.activate_index(0)
    assert app.state is ViewState.ROOT


def test_back_from_file_view_returns_to_folder(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    idx = next(
        i for i, e in enumerate(app.entries) if e.name == "notes.md"
    )
    app.activate_index(idx)
    app.activate_index(0)
    assert app.state is ViewState.FOLDER_VIEW
    assert app.entries[0].name == "<-- BACK"


def test_nested_back_navigates_history(tmp_path):
    inner = tmp_path / "inner"
    inner.mkdir(parents=True)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    app.activate_index(1)  # the inner folder
    app.activate_index(0)  # back
    assert app.current_path.replace("/", "\\") == str(tmp_path).replace(
        "/", "\\"
    )


def test_open_missing_file_sets_error_and_stays_in_folder(tmp_path):
    from app import BACK_ENTRY
    from file_engine import FileEntry

    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    missing = FileEntry(name="gone.txt", path=str(tmp_path / "gone.txt"), is_dir=False)
    app.open_file(missing)
    assert app.state is ViewState.FOLDER_VIEW
    assert app.error_message


def test_scroll_page_is_bounded(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))

    app.scroll_page(5, 100, 20)
    assert app.scroll_offset == 5

    app.scroll_page(-3, 100, 20)
    assert app.scroll_offset == 2

    app.scroll_page(-100, 100, 20)
    assert app.scroll_offset == 0

    app.scroll_page(1000, 100, 20)
    assert app.scroll_offset == 80


def test_pinch_drag_scrolls_relative_to_anchor(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))

    app.begin_drag(y=200)
    app.drag_to(y=140, pixels_per_row=30, total_rows=100, visible_rows=20)
    assert app.scroll_offset == 2

    app.drag_to(y=200, pixels_per_row=30, total_rows=100, visible_rows=20)
    assert app.scroll_offset == 0

    app.begin_drag(y=4000)
    app.drag_to(y=0, pixels_per_row=30, total_rows=100, visible_rows=20)
    assert app.scroll_offset == 80


def test_drag_without_explicit_begin_starts_implicitly(tmp_path):
    tmp_path = mkdir_scaffold(tmp_path)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))
    app.drag_to(y=40, pixels_per_row=20, total_rows=100, visible_rows=20)
    assert app.scroll_offset == 0
    app.drag_to(y=20, pixels_per_row=20, total_rows=100, visible_rows=20)
    assert app.scroll_offset == 1


def test_permission_error_opening_file_is_caught(tmp_path, monkeypatch):
    def boom(path):
        raise PermissionError("Access is denied")

    monkeypatch.setattr("app.read_text_file", boom)
    app = ExplorerApp()
    app.navigate_to(str(tmp_path))

    bad = FileEntry(
        name="locked.txt", path=str(tmp_path / "locked.txt"), is_dir=False
    )
    app.open_file(bad)
    assert app.state is ViewState.FOLDER_VIEW
    assert "Access is denied" in app.error_message