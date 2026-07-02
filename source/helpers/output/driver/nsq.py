"""
NSQ output driver.

Publishes messages to NSQ via its HTTP pub endpoint.
"""

from __future__ import annotations

import atexit
from typing import Any

from helpers.eBnsq import Producer
from helpers.output.driver import OutputDriver


class NsqOutputDriver(OutputDriver):
    """Publish messages to NSQ.

    Parameters
    ----------
    topic:
        NSQ topic name.
    nsqd_http_address:
        Base URL of the nsqd HTTP interface, e.g.
        ``http://localhost:4151``.
    """

    name: str = "nsq"

    def __init__(
        self,
        topic: str,
        nsqd_http_address: str = "http://localhost:4151",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.topic = topic
        self._nsq = Producer(nsqd_http_address=nsqd_http_address)
        atexit.register(self.close)

    def put(self, output: str, **kwargs: Any) -> None:
        """Publish *output* to NSQ."""
        self._nsq.publish(output, self.topic)

    def close(self) -> None:
        """Close the NSQ producer."""
        self._nsq.close()
