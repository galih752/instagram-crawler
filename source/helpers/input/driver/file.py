"""
File input driver.

Reads a text file line-by-line, yielding each line as a job dict
under the ``keyword`` key.
"""

from __future__ import annotations

from typing import Any

from helpers.input.driver import InputDriver


class FileInputDriver(InputDriver):
    """Read jobs from a file (one keyword per line).

    Parameters
    ----------
    path:
        Absolute or relative path to the input file.
    """

    name: str = "file"

    def __init__(self, path: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.path = path

    def get(self):  # type: ignore[no-untyped-def]
        with open(self.path, "r") as f:
            for line in f:
                keyword = line.strip()
                if keyword:
                    yield {"keyword": keyword}
