"""
Instagram authentication manager.

Handles session lifecycle via a token management HTTP API:

* ``GET  /api/v1/instagram/session`` — acquire a session
* ``PUT  /api/v1/instagram/session/release`` — release a session back to the pool
* ``PUT  /api/v1/instagram/session/report`` — report a faulty session

Also provides a helper to instantiate an authenticated instagrapi Client
from a sessionid string.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from instagrapi import Client
from loguru import logger


class InstagramAuth:
    """Manages Instagram session tokens via an external token management API.

    The token management service exposes three standardized endpoints
    under a configurable base URL::

        GET   {base_url}/api/v1/instagram/session
        PUT   {base_url}/api/v1/instagram/session/release
        PUT   {base_url}/api/v1/instagram/session/report

    Parameters
    ----------
    base_url:
        Base URL of the token management service (from
        ``[service] token_management`` in config.ini).
    """

    def __init__(self, base_url: str) -> None:
        self.base_url: str = base_url.rstrip("/")
        self.log = logger

    # ------------------------------------------------------------------
    # Session acquisition
    # ------------------------------------------------------------------

    def get_session(self) -> dict[str, Any]:
        """Request a new Instagram session from the token pool.

        Returns the full account dict including::

            {
                "username_account": "...",
                "session_id": {"session": "12345678%3A..."},
                ...
            }
        """
        url = f"{self.base_url}/api/v1/instagram/session"
        try:
            res = httpx.get(url, timeout=60)
            res.raise_for_status()
        except httpx.HTTPError as e:
            self.log.error(f"Failed to get session: {e}")
            raise

        data = res.json()
        if not data:
            raise Exception("Token management returned empty response")

        self.log.info(f"Acquired session for {data.get('username_account')}")
        return data

    # ------------------------------------------------------------------
    # Session release
    # ------------------------------------------------------------------

    def release_session(self, session_id: str) -> None:
        """Return a session to the pool so it can be reused.

        Parameters
        ----------
        session_id:
            The session identifier to release.
        """
        url = f"{self.base_url}/api/v1/instagram/session/release"
        try:
            res = httpx.put(
                url,
                timeout=60,
                json={"session_id": session_id},
            )
            res.raise_for_status()
            self.log.info(f"Session released: {session_id[:20]}...")
        except httpx.HTTPError as e:
            self.log.warning(f"Failed to release session: {e}")

    # ------------------------------------------------------------------
    # Session reporting
    # ------------------------------------------------------------------

    def report_session(self, session_id: str, error: str) -> None:
        """Report a session as unusable (challenged, banned, etc.).

        Parameters
        ----------
        session_id:
            The session identifier to report.
        error:
            Description of the error (e.g. "ChallengeRequired", "LoginRequired").
        """
        url = f"{self.base_url}/api/v1/instagram/session/report"
        payload = {
            "session_id": session_id,
            "error": error,
        }
        try:
            res = httpx.put(url, timeout=60, json=payload)
            res.raise_for_status()
            self.log.warning(f"Session reported: {session_id[:20]}... -- {error}")
        except httpx.HTTPError as e:
            self.log.error(f"Failed to report session: {e}")

    # ------------------------------------------------------------------
    # Client login from session
    # ------------------------------------------------------------------

    @staticmethod
    def login(session_id: str, user: dict[str, Any]) -> Client:
        """Create an instagrapi Client and authenticate using a sessionid."""
        cl = Client()
        try:
            cl.login_by_sessionid(sessionid=session_id, user=user)
            username = user.get("username", "unknown")
            logger.info(f"Logged in via sessionid: {username}")
        except Exception as e:
            logger.error(f"login_by_sessionid failed: {e}")
            raise
        return cl
