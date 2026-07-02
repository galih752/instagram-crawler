"""
Input facade.

Delegates to the appropriate input driver (beanstalk, file, or stdin)
based on constructor kwargs.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from helpers.input.driver.factory import InputDriverFactory


class Input:
    """Unified input interface for crawl jobs.

    Usage::

        inp = Input(input="my-tube", beanstalk_host="...", beanstalk_port=11300)
        for job in inp:
            process(job)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.driver = InputDriverFactory.create_input_driver(*args, **kwargs)
        logger.debug(f"Using {self.driver.name} input driver")

    def exception_handler(self, e: Exception, **kwargs: Any) -> None:
        """Delegate exception handling to the underlying driver."""
        self.driver.exception_handler(e, **kwargs)

    def put_message(self, **kwargs: Any) -> None:
        """Push a message back onto the input queue (re-enqueue)."""
        self.driver.put_message(**kwargs)

    def __iter__(self):  # type: ignore[no-untyped-def]
        yield from self.driver
