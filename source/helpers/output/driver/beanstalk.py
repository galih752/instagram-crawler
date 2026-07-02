"""
Beanstalk output driver.

Publishes messages to a Beanstalkd tube via greenstalk.
"""

from __future__ import annotations

import atexit
from typing import Any

from helpers.input.driver.beanstalk import BeanstalkInputDriver
from helpers.output.driver import OutputDriver


class BeanstalkOutputDriver(OutputDriver):
    """Publish messages to Beanstalkd.

    Parameters
    ----------
    tube:
        Beanstalk tube name.
    host:
        Beanstalkd host.
    port:
        Beanstalkd port.
    """

    name: str = "beanstalk"

    def __init__(
        self,
        tube: str,
        host: str = "localhost",
        port: int = 11300,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._beanstalk = BeanstalkInputDriver(
            tube=tube, host=host, port=port, *args, **kwargs
        )
        atexit.register(self.close)

    def put(self, output: str, **kwargs: Any) -> None:
        """Put *output* into the beanstalk tube."""
        self._beanstalk.put_message(body=output, **kwargs)

    def close(self) -> None:
        """Close the Beanstalk connection."""
        self._beanstalk.close()
