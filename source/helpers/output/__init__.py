"""
Output facade.

Delegates to the appropriate output driver (kafka, nsq, beanstalk,
file, or stdout) based on constructor kwargs.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from helpers.output.driver.factory import OutputDriverFactory


class Output:
    """Unified output interface for crawl results.

    Usage::

        out = Output(output="my-topic", destination="nsq",
                     nsqd_http_address="http://localhost:4151")
        out.put(json.dumps(post_data))
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.driver = OutputDriverFactory.create_output_driver(*args, **kwargs)
        logger.debug(f"Using {self.driver.name} output driver")

    def put(self, output: str, **kwargs: Any) -> None:
        """Publish *output* string to the configured destination."""
        self.driver.put(output, **kwargs)
