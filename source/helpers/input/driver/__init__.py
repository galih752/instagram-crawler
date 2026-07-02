"""
Abstract base for input drivers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class InputDriver(ABC):
    """Interface that every input driver must implement.

    Subclasses must set the ``name`` class attribute and implement
    ``get()``, which should be a generator yielding job dicts.
    """

    name: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def get(self):  # type: ignore[no-untyped-def]
        """Yield zero or more job dicts."""
        ...

    def close(self) -> None:
        """Release any held resources."""
        pass

    def exception_handler(self, e: Exception, **kwargs: Any) -> None:
        """Handle an exception on the current job (default: no-op)."""
        pass

    def put_message(self, **kwargs: Any) -> None:
        """Re-enqueue a message (default: no-op)."""
        pass

    def __iter__(self):  # type: ignore[no-untyped-def]
        yield from self.get()
