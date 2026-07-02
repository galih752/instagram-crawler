"""
Kafka output driver.

Publishes messages to a Kafka topic using kafka-python.
"""

from __future__ import annotations

import atexit
from typing import Any

from kafka import KafkaProducer

from helpers.output.driver import OutputDriver


class KafkaOutputDriver(OutputDriver):
    """Publish messages to Apache Kafka.

    Parameters
    ----------
    topic:
        Kafka topic name.
    bootstrap_servers:
        Comma-separated list of Kafka bootstrap servers.
    """

    name: str = "kafka"

    def __init__(
        self,
        topic: str,
        bootstrap_servers: list[str],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.topic = topic
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            max_request_size=10485760,
            request_timeout_ms=60000,
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
        )
        atexit.register(self.close)

    def put(self, output: str, **kwargs: Any) -> None:
        """Send *output* to Kafka."""
        self._producer.send(self.topic, output)
        self._producer.flush()

    def close(self) -> None:
        """Close the Kafka producer."""
        self._producer.close()
