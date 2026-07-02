"""
Abstract base for output drivers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OutputDriver(ABC):
    """Interface that every output driver must implement.

    Subclasses must set the ``name`` class attribute and implement
    ``put()`` and ``close()``.
    """

    name: str | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def put(self, output: str, **kwargs: Any) -> None:
        """Publish an output message."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release any held resources."""
        ...
