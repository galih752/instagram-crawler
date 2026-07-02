"""
Shared helper utilities for the Instagram crawler.

Exposes convenience factories for Beanstalk and NSQ producers,
plus a generic job-metadata extractor.

All connection parameters are passed explicitly — no global settings
or environment variables are read by these functions.
"""

from __future__ import annotations

from typing import Any

from greenstalk import Client

from helpers.eBnsq import Producer


def init_beanstalk_worker(
    tube: str,
    host: str = "localhost",
    port: int = 11300,
) -> Client:
    """Return a greenstalk Client configured as a worker on *tube*."""
    return Client((host, port), use=tube, watch=tube)


def init_beanstalk_pusher(
    tube: str,
    host: str = "localhost",
    port: int = 11300,
) -> Client:
    """Return a greenstalk Client configured as a pusher on *tube*."""
    return Client((host, port), use=tube)


def init_nsq_producer(
    nsqd_http_address: str = "localhost:4151",
) -> Producer:
    """Return an NSQ Producer pointing at the configured nsqd HTTP address."""
    return Producer(nsqd_http_address=nsqd_http_address)


def job_metadata(job: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Extract a subset of keys from *job*, returning only those present."""
    result: dict[str, Any] = {}
    for k in keys:
        if k in job:
            result[k] = job[k]
    return result
