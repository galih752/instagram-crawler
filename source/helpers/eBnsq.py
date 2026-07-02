"""
Minimal NSQ HTTP producer.

Publishes messages to NSQ via its HTTP pub endpoint. No external
NSQ client library required.
"""

from __future__ import annotations

from urllib.parse import urljoin

import httpx


class Producer:
    """NSQ producer that pushes messages to nsqd via HTTP.

    Parameters
    ----------
    nsqd_http_address:
        Base URL of the nsqd HTTP interface, e.g.
        ``http://localhost:4151``.
    """

    def __init__(self, nsqd_http_address: str) -> None:
        self._nsqd_http_address: str = nsqd_http_address.rstrip("/")
        self._client = httpx.Client(timeout=30)

    def publish(self, message: str, topic: str, defer: int = 0) -> httpx.Response:
        """Publish *message* to *topic*.

        Parameters
        ----------
        message:
            Raw message body (string).
        topic:
            NSQ topic name.
        defer:
            Defer duration in milliseconds (for deferred messages).
        """
        url = urljoin(f"{self._nsqd_http_address}/", "pub")
        response = self._client.post(
            url,
            content=message,
            params={"topic": topic, "defer": str(defer)},
        )
        response.raise_for_status()
        return response

    def mpublish(self, messages: list[str], topic: str) -> httpx.Response:
        """Publish multiple messages at once (mpub endpoint)."""
        url = urljoin(f"{self._nsqd_http_address}/", "mpub")
        body = "\n".join(messages)
        response = self._client.post(
            url,
            content=body,
            params={"topic": topic, "binary": "false"},
        )
        response.raise_for_status()
        return response

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
