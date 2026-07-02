"""
Standard-input input driver.

Reads a single keyword from the ``input`` kwarg, yielding one job dict.
"""

from __future__ import annotations

from typing import Any

from helpers.input.driver import InputDriver


class StdInputDriver(InputDriver):
    """Yield a single job dict from the ``input`` kwarg.

    Typically used for ad-hoc / testing runs::

        python main.py crawler --mode instagram --type post_by_hashtag -i travel
    """

    name: str = "std"

    def __init__(self, value: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._value = value

    def get(self):  # type: ignore[no-untyped-def]
        yield {"keyword": self._value}
