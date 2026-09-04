"""Interactive state machine connecting gestures to filesystem navigation.

The controller owns the application state (ROOT / FOLDER_VIEW / FILE_VIEW),
resolves pinch activations against the HUD hover position, and keeps the UI
layer free of filesystem knowledge.
"""

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
        self.reload()

    @property
    def directory_label(self):
        if self.state is ViewState.ROOT:
            return "This PC"
        if self.state is ViewState.FILE_VIEW:
            return self.file_name or "[ FILE VIEW ]"
        return self.current_path or "[ ROOT ]"

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