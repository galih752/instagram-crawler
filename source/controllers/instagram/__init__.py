"""
Instagram base controller extending the generic Controllers class.

Provides instagrapi Client lifecycle management, session/token handling,
proxy injection, and account state-machine operations.

Session management is delegated to ``InstagramAuth`` which talks to the
token management API using standardized v1 endpoints:

* ``GET  /api/v1/instagram/session``
* ``PUT  /api/v1/instagram/session/release``
* ``PUT  /api/v1/instagram/session/report``
"""

from __future__ import annotations

import re
from typing import Any, Optional

from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    LoginRequired,
    BadPassword,
    ReloginAttemptExceeded,
    FeedbackRequired,
    PleaseWaitFewMinutes,
    ClientChallengeRequiredError,
)

from controllers import Controllers
from library.instagram.auth import InstagramAuth


class InstagramBaseController(Controllers):
    """Shared base for all Instagram crawler controllers.

    Handles:
    * instagrapi Client creation with proxy + device spoofing.
    * Session acquisition, release, and reporting via the token
      management API (delegated to ``InstagramAuth``).
    * Login via sessionid string.
    * Account state machine (re-login, challenge, etc.).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.client: Optional[Client] = None
        self.account: Optional[dict[str, Any]] = None

        # Token management client -- base URL from config.ini [service] section
        token_url = self.config.get("service", "token_management", fallback="http://localhost:8000")
        self.auth = InstagramAuth(base_url=token_url)

        # Optional beanstalk tubes for comment/reply chaining
        self.tube_comment: str = kwargs.get("tube_comment", "instagram_comment")
        self.tube_comment_rapid: str = kwargs.get(
            "tube_comment_rapid", "instagram_comment"
        )
        self.tube_replies: str = kwargs.get("tube_replies", "instagram_replies")

        # Type of cookies to request from token management
        self.cookies_type: str = kwargs.get("cookies_type", "post")

        # Max posts per crawl -- from config.ini [count] section
        self.max_post: int = int(
            self.config.get("count", "max_post", fallback="30")
        )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def get_session(self) -> dict[str, Any]:
        """Fetch a fresh Instagram session from the token management API.

        Returns the full account dict including ``session_id`` and
        ``username_account``.
        """
        self.account = self.auth.get_session()
        return self.account

    def login_by_sessionid(self, session_id: str, user: dict[str, Any]) -> Client:
        """Create an authenticated instagrapi Client using a sessionid string."""
        cl = Client()
        try:
            cl.login_by_sessionid(sessionid=session_id, user=user)
            self.log.info(
                f"Logged in as {user.get('username', 'unknown')} "
                f"(pk={user.get('pk', '?')})"
            )
        except ChallengeRequired as e:
            self.log.error(f"ChallengeRequired during login: {e}")
            raise
        except LoginRequired as e:
            self.log.error(f"LoginRequired during login: {e}")
            raise
        except Exception as e:
            self.log.error(f"Unexpected login error: {e}")
            raise

        # Patch helper for resolving media PKs
        cl.media_user = lambda media_pk: cl.media_info_v1_raw(media_pk)["items"].pop()["user"]

        def _media_id(media_pk: str) -> str:
            mid = str(media_pk)
            if "_" not in mid:
                assert mid.isdigit(), f"media_id must be digit-only, got {mid}"
                user_data = cl.media_user(mid)
                mid = f"{mid}_{user_data['pk']}"
            return mid

        cl.media_id = _media_id  # type: ignore[attr-defined]

        self.client = cl
        return cl

    def logging_in(self) -> dict[str, Any]:
        """High-level: get session, instantiate client, and log in."""
        account = self.get_session()
        session_id = account["session_id"]["session"]
        user_id = re.search(r"^\d+", session_id).group()  # type: ignore[union-attr]
        user = {"username": account["username_account"], "pk": user_id}
        self.login_by_sessionid(session_id=session_id, user=user)
        return account

    def release_session(self) -> None:
        """Release the current session back to the token pool.

        Calls ``PUT /api/v1/instagram/session/release`` via InstagramAuth.
        """
        if not self.account:
            return
        session_id = self.account.get("session_id", {}).get("session")
        if not session_id:
            return
        try:
            self.auth.release_session(session_id=session_id)
            self.log.info(f"Session released: {self.account.get('username_account')}")
        except Exception as e:
            self.log.warning(f"Failed to release session: {e}")
        finally:
            self.account = None
            self.client = None

    def report_session(self, error_message: str) -> None:
        """Report a session as faulty (challenged, banned, expired).

        Calls ``PUT /api/v1/instagram/session/report`` via InstagramAuth.
        """
        if not self.account:
            self.log.warning("No account to report")
            return

        session_id = self.account.get("session_id", {}).get("session")
        if not session_id:
            self.log.warning("No session_id to report")
            return

        try:
            self.auth.report_session(session_id=session_id, error=error_message)
            self.log.warning(
                f"Session {self.account.get('username_account')} reported: {error_message}"
            )
        except Exception as e:
            self.log.error(f"Failed to report session: {e}")

    # ------------------------------------------------------------------
    # Proxy setup for instagrapi Client
    # ------------------------------------------------------------------

    def _setup_client_proxy(self, client: Client) -> None:
        """Inject proxy settings into the instagrapi Client."""
        proxy = self.get_proxy()
        if proxy:
            proxy_url = proxy.get("http://") or proxy.get("https://")
            if proxy_url:
                client.set_proxy(proxy_url)
                self.log.info(f"Client proxy set: {proxy_url}")

    # ------------------------------------------------------------------
    # Exception handling override
    # ------------------------------------------------------------------

    def exceptions_handler(self, e: Exception) -> None:
        """Instagram-aware exception handler with session reporting."""
        self.log.error(f"Instagram exception: {e}")
        err_str = str(e)

        # Report session on known fatal errors
        if self.message_exception.challenge().search(err_str):
            self.report_session("ChallengeRequired")
        elif self.message_exception.login_required().search(err_str):
            self.report_session("LoginRequired")

        super().exceptions_handler(e)
