"""
Standard-output output driver.

Prints messages to stdout (useful for testing / debugging).
"""

from __future__ import annotations

from typing import Any

from helpers.output.driver import OutputDriver


class StdOutputDriver(OutputDriver):
    """Print messages to stdout."""

    name: str = "std"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def put(self, output: str, **kwargs: Any) -> None:
        print(output)

    def close(self) -> None:
        pass
