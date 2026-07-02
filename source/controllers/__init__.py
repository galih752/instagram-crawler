"""
Base controller class providing shared infrastructure for all crawlers.

Every crawler controller inherits from ``Controllers`` and receives
proxy management, SSDB/Redis connectivity, input/output driver setup,
and a standard ``main()`` loop with exception handling.

Configuration is read from a ConfigParser-compatible INI file
(default: ``config.ini``).
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from abc import ABC, abstractmethod
from configparser import ConfigParser
from typing import Any, Optional

import redis
from httpx import AsyncClient
from loguru import logger
from stem import Signal
from stem.control import Controller

from exception.exception import MessageException
from helpers import init_beanstalk_pusher


class Controllers(ABC):
    """Abstract base for all crawler / pusher controllers.

    Responsibilities
    ----------------
    * Load configuration from a ConfigParser INI file (``config.ini``).
    * Initialise SSDB-backed dedup store (via Redis protocol).
    * Initialise Redis cache if caching is enabled.
    * Set up Input / Output drivers via ``helpers.input.Input`` and
      ``helpers.output.Output``.
    * Provide proxy rotation helpers (static list, Webshare API, Tor).
    * Run the standard ``main()`` loop: iterate input jobs, call
      ``handler()``, catch exceptions.
    * Offer ``pusher()`` (beanstalk) and ``store_to_ssdb()`` utilities.
    """

    job: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log = logger
        self.message_exception = MessageException()

        # ------------------------------------------------------------------
        # Configuration via ConfigParser (config.ini)
        # ------------------------------------------------------------------
        self.config = ConfigParser()
        config_path = kwargs.get("config", "config.ini")
        self.config.read(config_path)
        self.log.info(f"Loaded configuration from {config_path}")

        # Proxy -- static list from config, can be extended at runtime
        raw_proxy = self.config.get("proxy", "static_proxies", fallback="")
        if raw_proxy and raw_proxy.strip():
            self.static_proxies: list[str] = [
                p.strip() for p in raw_proxy.split(",") if p.strip()
            ]
        else:
            self.static_proxies: list[str] = []

        # Tor server address
        self.tor_server: str = self.config.get("service", "tor_server", fallback="localhost")

        # ------------------------------------------------------------------
        # Input driver
        # ------------------------------------------------------------------
        self.input = None
        if kwargs.get("source"):
            self.input_name = kwargs.get("input")
            self.source_name = kwargs.get("source")
            # Deferred import to avoid circular dependencies
            from helpers.input import Input

            self.input = Input(*args, **kwargs)

        # ------------------------------------------------------------------
        # Output driver
        # ------------------------------------------------------------------
        self.output = None
        if kwargs.get("destination"):
            self.output_name = kwargs.get("output")
            self.destination_name = kwargs.get("destination")
            from helpers.output import Output

            self.output = Output(*args, **kwargs)

        # ------------------------------------------------------------------
        # SSDB (dedup storage) -- config via [ssdb] section
        # ------------------------------------------------------------------
        ssdb_host = kwargs.get("ssdb_host") or self.config.get("ssdb", "host", fallback="localhost")
        ssdb_port = kwargs.get("ssdb_port") or self.config.get("ssdb", "port", fallback="8888")
        ssdb_password = kwargs.get("ssdb_password") or self.config.get("ssdb", "password", fallback="") or None

        self.ssdb = redis.StrictRedis(
            host=ssdb_host,
            port=int(ssdb_port),
            password=ssdb_password,
            max_connections=500,
            decode_responses=True,
        )

        # ------------------------------------------------------------------
        # Redis (general cache) -- config via [redis] section
        # ------------------------------------------------------------------
        redis_host = self.config.get("redis", "host", fallback="localhost")
        redis_port = self.config.get("redis", "port", fallback="6379")
        redis_db = self.config.get("redis", "db", fallback="0")
        redis_password = self.config.get("redis", "password", fallback="") or None

        self.redis = redis.StrictRedis(
            host=redis_host,
            port=int(redis_port),
            db=int(redis_db),
            password=redis_password,
            decode_responses=True,
        )

        # ------------------------------------------------------------------
        # Beanstalk pusher config -- config via [beanstalk] section
        # ------------------------------------------------------------------
        self.beanstalk_host = kwargs.get("beanstalk_host") or self.config.get(
            "beanstalk", "host", fallback="localhost"
        )
        self.beanstalk_port = kwargs.get("beanstalk_port") or int(
            self.config.get("beanstalk", "port", fallback="11300")
        )

        # ------------------------------------------------------------------
        # Caching toggle
        # ------------------------------------------------------------------
        cache_arg = kwargs.get("cache", "false")
        self.use_cache = str(cache_arg).lower() == "true"

        self.log.info(f"Controllers initialised | cache={self.use_cache}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def main(self) -> None:
        """Entry point: iterate input jobs and dispatch to ``handler()``."""
        if self.input:
            for job in self.input:
                if not job:
                    self.log.info("No jobs available")
                    continue
                self.job = job
                try:
                    await self.handler(job)
                except Exception as e:
                    self.exceptions_handler(e)
                finally:
                    self.release_session()
        else:
            try:
                await self.handler(job={})
            except Exception as e:
                self.exceptions_handler(e)
            finally:
                self.release_session()

    @abstractmethod
    async def handler(self, job: dict[str, Any]) -> None:
        """Override in subclass to implement crawl / push logic."""
        ...

    def release_session(self) -> None:
        """Override in subclass if sessions are acquired per job."""
        pass

    # ------------------------------------------------------------------
    # Exception handling
    # ------------------------------------------------------------------

    def exceptions_handler(self, e: Exception) -> None:
        """Classify the exception and decide whether to release, bury, or delete."""
        self.log.error(f"Exception: {e}")
        error_str = str(e)

        if self.input is None:
            self.log.error("No input driver; cannot handle exception further")
            return

        if self.message_exception.too_many_requests().search(error_str):
            self.input.exception_handler(e, action="bury")
        elif self.message_exception.connection_timeout().search(error_str):
            self.input.exception_handler(e, action="release")
        elif self.message_exception.challenge().search(error_str):
            self.input.exception_handler(e, action="release")
        elif self.message_exception.login_required().search(error_str):
            self.input.exception_handler(e, action="release")
        elif self.message_exception.media_not_available().search(error_str):
            self.input.exception_handler(e, action="delete")
        else:
            self.input.exception_handler(e, action="delete")

    # ------------------------------------------------------------------
    # Proxy helpers
    # ------------------------------------------------------------------

    def get_static_proxy(self) -> dict[str, str]:
        """Pick a random proxy from the static list."""
        if not self.static_proxies:
            return {}
        url = random.choice(self.static_proxies)
        self.log.info(f"Using static proxy: {url}")
        return {"http://": url, "https://": url}

    async def get_proxy_webshare(self) -> dict[str, str]:
        """Fetch a fresh proxy from Webshare's API.

        Reads the API token from ``[external_proxy] webshare_token``
        in config.ini.
        """
        token = self.config.get("external_proxy", "webshare_token", fallback="")
        if not token:
            self.log.warning("No webshare_token configured in [external_proxy]")
            return {}

        async with AsyncClient() as session:
            response = await session.request(
                "GET",
                url="https://proxy.webshare.io/api/v2/proxy/list/",
                timeout=60,
                headers={"Authorization": f"Token {token}"},
                params={"mode": "direct", "page": "1", "page_size": "25"},
            )
            data = response.json()
            proxy_list = data.get("results", [])
            if not proxy_list:
                return {}
            chosen = random.choice(proxy_list)
            url = (
                f"http://{chosen['username']}:{chosen['password']}"
                f"@{chosen['proxy_address']}:{chosen['port']}"
            )
            self.log.info(f"Webshare proxy: {url}")
            return {"http://": url, "https://": url}

    def get_proxy(self) -> dict[str, str]:
        """Primary proxy method: uses static list."""
        return self.get_static_proxy()

    def _change_tor_ip(self, password: str) -> None:
        """Request a new identity from the Tor control port."""
        controller = Controller.from_port(address=self.tor_server, port=32091)
        controller.authenticate(password=password)
        controller.signal(Signal.NEWNYM)
        wait = round(controller.get_newnym_wait())
        for i in range(wait, 0, -1):
            self.log.info(f"Waiting for Tor IP change... {i:>2d}s")
            time.sleep(1)
        self.log.success("Tor IP changed successfully")
        time.sleep(2)

    # ------------------------------------------------------------------
    # SSDB / Redis helpers
    # ------------------------------------------------------------------

    async def store_to_ssdb(
        self, post: dict[str, Any], key: str, value: str, job_type: str
    ) -> bool:
        """Dedup check + store in SSDB. Returns True if the item is new."""
        exists = self.ssdb.hexists(key, value)
        if not exists:
            self.ssdb.hset(key, value, "1")
            self.log.info(f"SSDB stored {job_type} {value} -> {key}")
            return True
        return False

    def set_data_to_redis(
        self, data: Any, key: str, default_ttl: int | None = None
    ) -> bool:
        """Store JSON-serialisable data in Redis with TTL (default 604800s / 7 days)."""
        try:
            ttl = default_ttl or 604800
            self.redis.setex(key, ttl, json.dumps(data, default=str))
            return True
        except Exception as e:
            self.log.error(f"Redis SET failed for {key}: {e}")
            return False

    def get_data_from_redis(self, key: str) -> Any:
        """Retrieve and JSON-decode data from Redis."""
        try:
            raw = self.redis.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception as e:
            self.log.error(f"Redis GET failed for {key}: {e}")
            return None

    def delete_data_redis(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            return self.redis.delete(key) == 1
        except Exception as e:
            self.log.error(f"Redis DELETE failed for {key}: {e}")
            return False

    # ------------------------------------------------------------------
    # Output pusher (beanstalk)
    # ------------------------------------------------------------------

    async def pusher(self, job: dict[str, Any], tube: str, ids: Optional[str] = None) -> None:
        """Push a job dict into a Beanstalk tube."""
        try:
            pusher_client = init_beanstalk_pusher(
                tube,
                host=self.beanstalk_host,
                port=int(self.beanstalk_port),
            )
            pusher_client.put(json.dumps(job, default=str), ttr=3600)
            self.log.info(f"Pushed job {ids} to tube {tube}")
        except Exception as e:
            self.log.error(f"Beanstalk push failed ({tube}): {e}")
