"""
Instagram client wrapper around instagrapi.

Provides proxy support, device spoofing, custom headers, and retry
logic with exponential backoff for all Instagram API calls.
"""

from __future__ import annotations

import random
import time
from typing import Any, Optional

from instagrapi import Client
from loguru import logger


# Default Instagram app identifiers (overridable via constructor)
DEFAULT_APP_ID = "936619743392459"
DEFAULT_APP_VERSION = "269.0.0.18.75"

# Default device profiles for spoofing via instagrapi
DEVICE_PROFILES = [
    {
        "manufacturer": "Samsung",
        "model": "SM-G991B",
        "android_version": 31,
        "android_release": "12.0",
        "dpi": "420dpi",
        "resolution": "1080x2400",
    },
    {
        "manufacturer": "Google",
        "model": "Pixel 6",
        "android_version": 31,
        "android_release": "12.0",
        "dpi": "411dpi",
        "resolution": "1080x2400",
    },
]


class InstagramClient:
    """High-level wrapper over instagrapi.Client with production defaults.

    Features
    --------
    - Proxy injection (static or Webshare)
    - Device profile spoofing (Samsung, Google Pixel)
    - Custom mobile headers (x-ig-app-id, sec-ch-ua, etc.)
    - Exponential-backoff retry decorator for API calls
    """

    def __init__(
        self,
        proxy: Optional[dict[str, str]] = None,
        device_profile: Optional[dict[str, Any]] = None,
        app_id: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> None:
        """
        Parameters
        ----------
        proxy:
            Dict of ``{"http://": url, "https://": url}``. If *None*,
            no proxy is set (direct connection).
        device_profile:
            Dict with ``manufacturer``, ``model``, ``android_version``,
            ``android_release``, ``dpi``, ``resolution``. Picked
            randomly from ``DEVICE_PROFILES`` if *None*.
        app_id:
            Instagram app ID for x-ig-app-id header. Defaults to
            ``DEFAULT_APP_ID``.
        app_version:
            Instagram app version for x-ig-app-version header. Defaults
            to ``DEFAULT_APP_VERSION``.
        """
        self.log = logger
        self._client: Optional[Client] = None

        # Proxy
        self._proxy: Optional[str] = None
        if proxy:
            self._proxy = proxy.get("http://") or proxy.get("https://")

        # Device
        self._device = device_profile or random.choice(DEVICE_PROFILES)

        # App metadata
        self._app_id = app_id or DEFAULT_APP_ID
        self._app_version = app_version or DEFAULT_APP_VERSION

    @property
    def client(self) -> Client:
        """Lazy-initialised instagrapi Client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> Client:
        """Create and configure a fresh instagrapi Client."""
        cl = Client()

        # Device spoofing
        cl.set_device(self._device)
        self.log.info(
            f"Device spoofed: {self._device.get('manufacturer')} "
            f"{self._device.get('model')}"
        )

        # Proxy
        if self._proxy:
            cl.set_proxy(self._proxy)
            self.log.info(f"Proxy set: {self._proxy[:40]}...")

        # Custom headers
        custom_headers = {
            "x-ig-app-id": self._app_id,
            "x-ig-app-version": self._app_version,
            "sec-ch-ua": (
                '"Google Chrome";v="119", "Chromium";v="119", '
                '"Not?A_Brand";v="24"'
            ),
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "user-agent": (
                "Mozilla/5.0 (Linux; Android 12; SM-G991B) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Mobile Safari/537.36"
            ),
        }
        # Inject custom headers by overriding the default headers dict
        if hasattr(cl, "settings"):
            cl.settings.update(custom_headers)  # type: ignore[attr-defined]
        else:
            # Fallback: stash on the client for reference
            cl._custom_headers = custom_headers  # type: ignore[attr-defined]

        self.log.debug("Custom headers applied")
        return cl

    def login_by_session(self, session_id: str, user: dict[str, Any]) -> Client:
        """Authenticate using an existing sessionid string."""
        cl = self.client
        cl.login_by_sessionid(sessionid=session_id, user=user)
        self.log.info(f"Logged in as {user.get('username', 'unknown')}")
        return cl

    def login_by_credentials(self, username: str, password: str) -> Client:
        """Authenticate using username + password."""
        cl = self.client
        cl.login(username=username, password=password)
        self.log.info(f"Logged in as {username}")
        return cl

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    @staticmethod
    def retry_with_backoff(
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ):
        """Decorator that wraps synchronous calls with exponential backoff.

        Usage::

            @InstagramClient.retry_with_backoff(max_retries=5)
            def my_api_call(self, *args, **kwargs):
                return self.client.some_method(...)
        """
        import functools

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Optional[Exception] = None
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exc = e
                        if attempt < max_retries - 1:
                            delay = min(base_delay * (backoff_factor**attempt), max_delay)
                            jitter = random.uniform(0, delay * 0.5)
                            total_sleep = delay + jitter
                            logger.warning(
                                f"Retry {attempt + 1}/{max_retries} after {total_sleep:.1f}s: {e}"
                            )
                            time.sleep(total_sleep)
                        else:
                            raise
                raise last_exc  # type: ignore[misc]

            return wrapper

        return decorator
