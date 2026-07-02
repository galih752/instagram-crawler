"""
Exception hierarchy for the Instagram crawler project.

Includes generic crawler exceptions, message-matching patterns,
and Instagram-specific exceptions from both instagrapi and custom logic.
"""

import re
from typing import ClassVar


# ---------------------------------------------------------------------------
# Generic / transport exceptions
# ---------------------------------------------------------------------------

class AccountNotFoundException(Exception):
    def __str__(self) -> str:
        return "Account not found"


class PrivateAccountException(Exception):
    def __str__(self) -> str:
        return "Account is private"


class NoProxiesAvailableException(Exception):
    def __str__(self) -> str:
        return "No proxies available"


class ChannelNotExists(Exception):
    def __str__(self) -> str:
        return "ChannelNotExists"


class ErrorRequestException(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


class ResponseException(Exception):
    def __init__(self, message: str = "internal server error", status: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class BadRequestResponseException(ResponseException):
    def __init__(self, message: str = "bad request") -> None:
        super().__init__(message, status=400)


class OutputDriverNotRecognizeException(Exception):
    def __str__(self) -> str:
        return "Destination not recognized"


# ---------------------------------------------------------------------------
# Instagram-specific exceptions (derived from instagrapi behaviour)
# ---------------------------------------------------------------------------

class ChallengeRequiredException(Exception):
    """Instagram requires a challenge (CAPTCHA, 2FA, etc.) to proceed."""

    def __str__(self) -> str:
        return "ChallengeRequired: Instagram requires a challenge to login"


class LoginRequiredException(Exception):
    """The current session has expired or is invalid."""

    def __str__(self) -> str:
        return "LoginRequired: Session expired or invalid"


class UserHasLoggedOutException(Exception):
    """The user explicitly logged out of this session."""

    def __str__(self) -> str:
        return "UserHasLoggedOut: The user logged out of this session"


class MediaNotAvailableException(Exception):
    """The requested media is unavailable (deleted, private, or geo-blocked)."""

    def __str__(self) -> str:
        return "Media not available"


class CommentIsUnavailableException(Exception):
    """Comments on this post cannot be fetched."""

    def __str__(self) -> str:
        return "Comment is unavailable"


class NotFoundException(Exception):
    def __str__(self) -> str:
        return "Link not found"


class TooManyRequestException(Exception):
    def __str__(self) -> str:
        return "Too Many Request"


class UnauthorizedException(Exception):
    def __str__(self) -> str:
        return "401 Unauthorized"


class NoCookiesAvailableException(Exception):
    def __str__(self) -> str:
        return "No Cookies Available"


class CookiesIncorrectException(Exception):
    def __str__(self) -> str:
        return "Cookies incorrect"


class SessionReportedException(Exception):
    """Raised when a session has already been reported and should not be reused."""

    def __str__(self) -> str:
        return "Session has been reported"


# ---------------------------------------------------------------------------
# MessageException -- regex-based error classifier
# ---------------------------------------------------------------------------

class MessageException:
    """Groups of regex patterns used to classify error strings for retry logic."""

    TOO_MANY_REQUEST: ClassVar[list[str]] = [
        "Too Many Requests",
        "Too Many Redirects",
        "Please wait a few minutes",
        "PleaseWaitFewMinutes",
    ]
    CONNECTION_TIMEOUT: ClassVar[list[str]] = [
        "ReadTimeout",
        "Read Timed out",
        "ConnectTimeout",
        "Connection Timed out",
        "Connect Timeout",
        "Timed Out",
        "Cannot connect to proxy",
        "httpx.ReadTimeout",
        "httpx.ConnectTimeout",
    ]
    CONNECTION_ERROR: ClassVar[list[str]] = [
        "Failed to establish a new connection",
        "Connection reset by peer",
        "httpx.NetworkError",
    ]
    PROXY_ERROR: ClassVar[list[str]] = [
        "Cannot connect to proxy",
        "ProxyError",
        "proxy",
    ]
    JSON_DECODE_ERROR: ClassVar[list[str]] = [
        "JSONDecodeError",
        "Expecting value",
    ]
    CHALLENGE: ClassVar[list[str]] = [
        "ChallengeRequired",
        "ChallengeError",
        "ChallengeChoice",
        "ChallengeResolve",
        "RecaptchaChallengeForm",
        "challenge_required",
    ]
    LOGIN_REQUIRED: ClassVar[list[str]] = [
        "LoginRequired",
        "login_required",
        "BadPassword",
        "ReloginAttemptExceeded",
    ]
    MEDIA_NOT_AVAILABLE: ClassVar[list[str]] = [
        "Media not available",
        "MediaNotAvailable",
        "NotFound",
        "Not Found",
        "404",
    ]

    def too_many_requests(self) -> re.Pattern:
        return re.compile("|".join(self.TOO_MANY_REQUEST), flags=re.I)

    def connection_timeout(self) -> re.Pattern:
        return re.compile("|".join(self.CONNECTION_TIMEOUT), flags=re.I)

    def connection_error(self) -> re.Pattern:
        return re.compile("|".join(self.CONNECTION_ERROR), flags=re.I)

    def proxy_error(self) -> re.Pattern:
        return re.compile("|".join(self.PROXY_ERROR), flags=re.I)

    def json_decode_error(self) -> re.Pattern:
        return re.compile("|".join(self.JSON_DECODE_ERROR), flags=re.I)

    def challenge(self) -> re.Pattern:
        return re.compile("|".join(self.CHALLENGE), flags=re.I)

    def login_required(self) -> re.Pattern:
        return re.compile("|".join(self.LOGIN_REQUIRED), flags=re.I)

    def media_not_available(self) -> re.Pattern:
        return re.compile("|".join(self.MEDIA_NOT_AVAILABLE), flags=re.I)
