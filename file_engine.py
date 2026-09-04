"""File system engine: drive discovery, directory scanning, and safe readers.

Pure backend logic used by the AR HUD. No OpenCV GUI code lives here so the
engine stays testable without a display.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = (".txt", ".md")

_READ_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


@dataclass(frozen=True)
class FileEntry:
    """A single filesystem item shown in the HUD file tree."""

    name: str
    path: str
    is_dir: bool

    @property
    def is_file(self):
        return not self.is_dir


def get_drives():
    """Return the root paths to display in the 'This PC' root view.

    On Windows every currently mounted drive letter is returned
    (e.g. ``C:/``, ``D:/``). On other platforms a single root ``/`` is used.
    """
    if sys.platform.startswith("win"):
        import string

        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            try:
                if Path(drive).exists():
                    drives.append(drive)
            except OSError:
                continue
        return drives
    return [os.path.abspath(os.sep)]


def scanned_key(entry):
    """Sort directories before files, then case-insensitively by name."""
    return (entry.is_dir is False, entry.name.lower())


def scan_directory(path):
    """List folders and supported text/markdown files inside ``path``.

    Raises:
        PermissionError: when the directory cannot be accessed or listed.
        FileNotFoundError: when the directory does not exist.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    if not path_obj.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    try:
        with os.scandir(str(path_obj)) as scanner:
            raw_items = list(scanner)
    except PermissionError as exc:
        raise PermissionError(f"Access denied listing directory: {path}") from exc
    except OSError as exc:
        raise OSError(f"Failed to list directory: {path} ({exc})") from exc

    for item in raw_items:
        try:
            is_dir = item.is_dir()
        except OSError:
            continue
        if is_dir:
            entries.append(FileEntry(name=item.name, path=item.path, is_dir=True))
            continue
        if item.name.lower().endswith(SUPPORTED_EXTENSIONS):
            entries.append(FileEntry(name=item.name, path=item.path, is_dir=False))

    entries.sort(key=scanned_key)
    return entries


def read_text_file(path):
    """Load a supported text file into a list of strings.

    The file is decoded with encoding fallbacks, so markdown and plain text
    files with different encodings are handled gracefully.

    Raises:
        PermissionError: when the file cannot be read due to access rights.
        FileNotFoundError: when the file does not exist.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"File not found: {path}")

    for encoding in _READ_ENCODINGS:
        try:
            with open(path_obj, "r", encoding=encoding, errors="strict") as fh:
                content = fh.read()
            break
        except PermissionError:
            raise PermissionError(f"Access denied reading file: {path}")
        except UnicodeDecodeError:
            continue
    else:
        content = path_obj.read_text(encoding="latin-1", errors="replace")

    return content.splitlines()