"""
Input driver factory.

Chooses the appropriate input driver based on the presence of
``beanstalk_host`` / ``beanstalk_port`` kwargs.
"""

from __future__ import annotations

from typing import Any

from helpers.input.driver.beanstalk import BeanstalkInputDriver
from helpers.input.driver.file import FileInputDriver
from helpers.input.driver.std import StdInputDriver


class InputDriverFactory:
    """Factory for input drivers.

    Priority:
    1. Beanstalk if ``beanstalk_host`` and ``beanstalk_port`` are provided.
    2. File if the ``input`` kwarg is a readable file path.
    3. Stdin (default).
    """

    @staticmethod
    def create_input_driver(*args: Any, **kwargs: Any) -> StdInputDriver | BeanstalkInputDriver | FileInputDriver:
        beanstalk_host = kwargs.get("beanstalk_host")
        beanstalk_port = kwargs.get("beanstalk_port")

        if beanstalk_host and beanstalk_port:
            return InputDriverFactory.create_beanstalk_input_driver(*args, **kwargs)

        # Try file detection
        input_value = kwargs.get("input", "")
        if isinstance(input_value, str) and input_value:
            import os
            if os.path.isfile(input_value):
                return InputDriverFactory.create_file_input_driver(*args, **kwargs)

        return InputDriverFactory.create_std_input_driver(*args, **kwargs)

    @staticmethod
    def create_std_input_driver(*args: Any, **kwargs: Any) -> StdInputDriver:
        return StdInputDriver(kwargs.pop("input", ""), *args, **kwargs)

    @staticmethod
    def create_beanstalk_input_driver(*args: Any, **kwargs: Any) -> BeanstalkInputDriver:
        return BeanstalkInputDriver(
            tube=kwargs.pop("input"),
            host=kwargs.pop("beanstalk_host"),
            port=kwargs.pop("beanstalk_port"),
            *args,
            **kwargs,
        )

    @staticmethod
    def create_file_input_driver(*args: Any, **kwargs: Any) -> FileInputDriver:
        return FileInputDriver(kwargs.pop("input"), *args, **kwargs)
