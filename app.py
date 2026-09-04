"""Interactive state machine connecting gestures to filesystem navigation.

The controller owns the application state (ROOT / FOLDER_VIEW / FILE_VIEW),
resolves pinch activations against the HUD hover position, and keeps the UI
layer free of filesystem knowledge.
"""

import os
from enum import Enum, auto

from file_engine import FileEntry, get_drives, read_text_file, scan_directory

BACK_ENTRY = FileEntry(name="<-- BACK", path="", is_dir=True)


class ViewState(Enum):
    ROOT = auto()
    FOLDER_VIEW = auto()
    FILE_VIEW = auto()


def _drive_entries():
    return [
        FileEntry(name=drive, path=drive, is_dir=True) for drive in get_drives()
    ]


class ExplorerApp:
    """Gesture-driven filesystem explorer state machine."""

    def __init__(self):
        self.state = ViewState.ROOT
        self.current_path = ""
        self.history = []
        self.entries = []
        self.file_path = ""
        self.file_name = ""
        self.lines = []
        self.error_message = ""
        self.scroll_offset = 0
        self._wrapped_count = 0
        self._drag_anchor_y = None
        self._drag_start_scroll = 0
        self.reload()

    @property
    def directory_label(self):
        if self.state is ViewState.ROOT:
            return "THIS PC"
        if self.state is ViewState.FILE_VIEW:
            return self.file_name or "[ FILE ]"
        return self.current_path or "[ THIS PC ]"

    @property
    def friendly_label(self):
        """Human-friendly header for the current location."""
        if self.state is ViewState.ROOT:
            return "THIS PC"
        if self.state is ViewState.FILE_VIEW:
            return f"READING // {self.file_name or 'FILE'}"
        path = self.current_path or ""
        if not path:
            return "THIS PC"
        stripped = path.rstrip("\\/")
        if len(stripped) == 2 and stripped[1] == ":":
            return f"DRIVE: {stripped[0]}://"  # e.g. DRIVE: D://
        name = os.path.basename(stripped) or stripped
        return f"DIR: {name}"

    @property
    def is_file_view(self):
        return self.state is ViewState.FILE_VIEW

    def reload(self):
        """Rebuild the display list for the current state."""
        self.error_message = ""
        if self.state is ViewState.ROOT:
            self.entries = _drive_entries()
            return
        if self.state is ViewState.FOLDER_VIEW:
            try:
                children = scan_directory(self.current_path)
                self.entries = [BACK_ENTRY, *children]
            except (PermissionError, OSError, FileNotFoundError) as exc:
                self.error_message = str(exc)
                self.entries = [BACK_ENTRY]
            return

    def navigate_to(self, path):
        """Programmatic entry point used by tests/other views."""
        self.state = ViewState.FOLDER_VIEW
        self.current_path = path
        self.history = []
        self.scroll_offset = 0
        self.reload()

    def go_back(self):
        if self.state is ViewState.FILE_VIEW:
            self.state = ViewState.FOLDER_VIEW
            self.scroll_offset = 0
            self.reload()
            return
        if self.state is ViewState.FOLDER_VIEW:
            if self.history:
                self.current_path = self.history.pop()
            else:
                self.state = ViewState.ROOT
                self.current_path = ""
            self.scroll_offset = 0
            self.reload()
            return

    def activate_index(self, abs_index):
        """Handle a pinch activation on list row ``abs_index``."""
        if abs_index < 0:
            return False

        if self.state is ViewState.FILE_VIEW:
            if abs_index == 0:
                self.go_back()
            return True

        if abs_index >= len(self.entries):
            return False
        entry = self.entries[abs_index]

        if entry.name == BACK_ENTRY.name:
            self.go_back()
        elif entry.is_dir:
            self.history.append(self.current_path)
            self.current_path = entry.path
            self.state = ViewState.FOLDER_VIEW
            self.scroll_offset = 0
            self.reload()
        else:
            self.open_file(entry)
        return True

    def open_file(self, entry):
        try:
            lines = read_text_file(entry.path)
        except (PermissionError, OSError, UnicodeError) as exc:
            self.error_message = str(exc)
            return
        self.file_path = entry.path
        self.file_name = entry.name
        self.lines = lines
        self.file_error = ""
        self.scroll_offset = 0
        self.state = ViewState.FILE_VIEW

    def scroll_page(self, delta, total_rows, visible_rows):
        """Scroll the current view by ``delta`` rows within bounds."""
        max_offset = max(0, total_rows - visible_rows)
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + delta))

    def scroll_to(self, offset, total_rows, visible_rows):
        """Scroll the current view to an absolute row within bounds."""
        max_offset = max(0, total_rows - visible_rows)
        self.scroll_offset = max(0, min(max_offset, offset))

    def begin_drag(self, y):
        """Start a pinch-drag scroll anchored at pixel row ``y``."""
        self._drag_anchor_y = y
        self._drag_start_scroll = self.scroll_offset

    def drag_to(self, y, pixels_per_row, total_rows, visible_rows):
        """Apply drag scrolling by the anchored pixel delta.

        Dragging the finger upward (y decreases) reveals later content and
        increases the scroll offset.
        """
        if self._drag_anchor_y is None:
            self.begin_drag(y)
        delta_rows = int((self._drag_anchor_y - y) / max(1, pixels_per_row))
        self.scroll_to(
            self._drag_start_scroll + delta_rows, total_rows, visible_rows
        )

    def end_drag(self):
        self._drag_anchor_y = None