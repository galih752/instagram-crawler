"""
Beanstalkd input driver.

Reads jobs from a Beanstalk tube, yielding JSON-deserialized dicts.
"""

from __future__ import annotations

import atexit
import json
from typing import Any

from greenstalk import (
    DEFAULT_TUBE,
    Client,
    TimedOutError,
    NotFoundError,
)

from helpers.input.driver import InputDriver


class BeanstalkInputDriver(InputDriver):
    """Read jobs from a Beanstalkd tube.

    Parameters
    ----------
    tube:
        Tube name to watch.
    host:
        Beanstalkd host.
    port:
        Beanstalkd port.
    """

    name: str = "beanstalk"

    def __init__(
        self,
        tube: str = DEFAULT_TUBE,
        host: str = "localhost",
        port: int = 11300,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.beanstalk = Client((host, port), use=tube, watch=tube)
        self.job: Any = None
        atexit.register(self.close)

    # -- Internal job actions ------------------------------------------

    def _delete(self) -> None:
        if self.job:
            self.beanstalk.delete(self.job)
            self.job = None

    def _bury(self, **kwargs: Any) -> None:
        if self.job:
            self.beanstalk.bury(self.job, **kwargs)
            self.job = None

    def _release(self, **kwargs: Any) -> None:
        if self.job:
            self.beanstalk.release(self.job, **kwargs)
            self.job = None

    def _put(self, **kwargs: Any) -> None:
        body = kwargs.get("body")
        if body:
            self.beanstalk.put(body, **kwargs)

    # -- Driver interface ----------------------------------------------

    def get(self):  # type: ignore[no-untyped-def]
        """Blocking iterator yielding jobs as parsed dicts."""
        while True:
            try:
                self.job = self.beanstalk.reserve(timeout=60)
                try:
                    yield json.loads(self.job.body)
                except (json.JSONDecodeError, TypeError):
                    self._delete()
                self._delete()
            except TimedOutError:
                yield None
            except BrokenPipeError:
                raise
            except Exception:
                raise

    def put_message(self, **kwargs: Any) -> None:
        """Re-publish a message to the tube."""
        self._put(**kwargs)

    def close(self) -> None:
        """Close the Beanstalk connection."""
        self.beanstalk.close()

    def exception_handler(self, e: Exception, **kwargs: Any) -> None:
        """Act on the current job based on the requested action."""
        action = kwargs.get("action", "bury")
        if action == "release":
            self._release()
        elif action == "delete":
            self._delete()
        else:
            self._bury()
