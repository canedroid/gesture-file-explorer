"""Tests for the file system navigation engine."""

import pytest

from file_engine import (
    FileEntry,
    get_drives,
    read_text_file,
    scan_directory,
)


def test_get_drives_returns_at_least_one_root():
    drives = get_drives()
    assert isinstance(drives, list)
    assert len(drives) >= 1


def test_scan_directory_lists_only_dirs_and_supported_files(tmp_path):
    (tmp_path / "notes.md").write_text("# Notes", encoding="utf-8")
    (tmp_path / "todo.txt").write_text("buy milk", encoding="utf-8")
    (tmp_path / "ignore.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "subfolder").mkdir()

    entries = scan_directory(str(tmp_path))
    names = {e.name for e in entries}

    assert "notes.md" in names
    assert "todo.txt" in names
    assert "subfolder" in names
    assert "ignore.py" not in names
    assert all(type(e) is FileEntry for e in entries)
    sub = next(e for e in entries if e.name == "subfolder")
    assert sub.is_dir
    notes = next(e for e in entries if e.name == "notes.md")
    assert notes.is_file


def test_scan_directory_sorts_folders_first_then_alpha(tmp_path):
    (tmp_path / "b_dir").mkdir()
    (tmp_path / "a_dir").mkdir()
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "a.txt").write_text("y", encoding="utf-8")

    entries = scan_directory(str(tmp_path))
    names = [e.name for e in entries]

    dirs = names[:2]
    files = names[2:]
    assert dirs == sorted(dirs, key=str.lower)
    assert files == sorted(files, key=str.lower)
    assert all(e.is_dir for e in entries[:2])
    assert all(e.is_file for e in entries[2:])


def test_scan_directory_raises_for_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_directory(str(tmp_path / "does_not_exist"))


def test_read_text_file_returns_list_of_lines(tmp_path):
    target = tmp_path / "notes.md"
    target.write_text("# Title\n\nSome body text\n", encoding="utf-8")
    lines = read_text_file(str(target))
    assert lines == ["# Title", "", "Some body text"]


def test_read_text_file_with_bom(tmp_path):
    target = tmp_path / "bom.txt"
    target.write_bytes(b"\xef\xbb\xbfhello world\nsecond line\n")
    lines = read_text_file(str(target))
    assert lines == ["hello world", "second line"]


def test_read_text_file_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_text_file(str(tmp_path / "missing.txt"))