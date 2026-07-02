"""
File output driver.

Appends messages to a local file (one JSON object per line).
"""

from __future__ import annotations

import atexit
import os
from typing import Any, Optional

from helpers.output.driver import OutputDriver


class FileOutputDriver(OutputDriver):
    """Append messages to a local file.

    Parameters
    ----------
    path:
        Absolute or relative path to the output file. Parent
        directories are created if they do not exist.
    """

    name: str = "file"

    def __init__(self, path: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.path: Optional[str] = None
        self._file: Optional[Any] = None

        if path:
            self._ensure_dir(path)
            self.path = path
            self._file = open(path, "a")

        atexit.register(self.close)

    @staticmethod
    def _ensure_dir(path: str) -> None:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def put(self, output: str, **kwargs: Any) -> None:
        """Write *output* to the file (appends newline)."""
        if kwargs.get("path"):
            # Switch target file
            new_path = kwargs["path"]
            self._ensure_dir(new_path)
            if self._file:
                self._file.close()
            self.path = new_path
            self._file = open(new_path, "a")

        if not self._file:
            raise RuntimeError("FileOutputDriver: no file path configured")

        self._file.write(output + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None
