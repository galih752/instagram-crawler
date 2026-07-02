"""
Output driver factory.

Chooses the appropriate output driver based on the ``destination`` kwarg.
"""

from __future__ import annotations

from typing import Any

from exception.exception import OutputDriverNotRecognizeException
from helpers.output.driver.beanstalk import BeanstalkOutputDriver
from helpers.output.driver.file import FileOutputDriver
from helpers.output.driver.kafka import KafkaOutputDriver
from helpers.output.driver.nsq import NsqOutputDriver
from helpers.output.driver.std import StdOutputDriver


class OutputDriverFactory:
    """Factory for output drivers.

    Supported destinations: ``kafka``, ``nsq``, ``beanstalk``, ``file``,
    ``std`` (default / fallback).
    """

    @staticmethod
    def create_output_driver(*args: Any, **kwargs: Any) -> StdOutputDriver | NsqOutputDriver | BeanstalkOutputDriver | KafkaOutputDriver | FileOutputDriver:
        destination = kwargs.get("destination", "std")
        assert destination, "Destination is required"

        if destination == "kafka":
            return OutputDriverFactory.create_kafka_output_driver(*args, **kwargs)
        elif destination == "nsq":
            return OutputDriverFactory.create_nsq_output_driver(*args, **kwargs)
        elif destination == "beanstalk":
            return OutputDriverFactory.create_beanstalk_output_driver(*args, **kwargs)
        elif destination == "file":
            return OutputDriverFactory.create_file_output_driver(*args, **kwargs)
        elif destination == "std":
            return OutputDriverFactory.create_std_output_driver(*args, **kwargs)
        else:
            raise OutputDriverNotRecognizeException()

    @staticmethod
    def create_std_output_driver(*args: Any, **kwargs: Any) -> StdOutputDriver:
        return StdOutputDriver(*args, **kwargs)

    @staticmethod
    def create_nsq_output_driver(*args: Any, **kwargs: Any) -> NsqOutputDriver:
        return NsqOutputDriver(
            topic=kwargs.pop("output"),
            nsqd_http_address=kwargs.pop("nsqd_http_address"),
            *args,
            **kwargs,
        )

    @staticmethod
    def create_beanstalk_output_driver(*args: Any, **kwargs: Any) -> BeanstalkOutputDriver:
        return BeanstalkOutputDriver(
            tube=kwargs.pop("output"),
            host=kwargs.pop("beanstalk_host"),
            port=kwargs.pop("beanstalk_port"),
            *args,
            **kwargs,
        )

    @staticmethod
    def create_kafka_output_driver(*args: Any, **kwargs: Any) -> KafkaOutputDriver:
        return KafkaOutputDriver(
            topic=kwargs.pop("output"),
            bootstrap_servers=kwargs.pop("bootstrap_servers").split(","),
            *args,
            **kwargs,
        )

    @staticmethod
    def create_file_output_driver(*args: Any, **kwargs: Any) -> FileOutputDriver:
        return FileOutputDriver(kwargs.pop("output"), *args, **kwargs)
