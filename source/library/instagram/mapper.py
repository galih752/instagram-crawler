"""
Instagram data mapper.

Converts raw instagrapi / API response dicts into canonical Pydantic models.
Also provides utility helpers for shortcode <-> media_id conversion and
hashtag/mention extraction from caption text.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from models.instagram import InstagramPost, InstagramUser, InstagramComment, InstagramHashtag


# Shortcode alphabet (base-64 variant used by Instagram)
_SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


class InstagramMapper:
    """Static helper for mapping raw Instagram data to Pydantic models."""

    # ------------------------------------------------------------------
    # Post mapping
    # ------------------------------------------------------------------

    @staticmethod
    def post_to_model(raw: dict[str, Any]) -> InstagramPost:
        """Convert a raw instagrapi post dict into an InstagramPost model."""
        return InstagramPost.from_instagrapi_post(raw)

    # ------------------------------------------------------------------
    # User mapping
    # ------------------------------------------------------------------

    @staticmethod
    def user_to_model(raw: dict[str, Any]) -> InstagramUser:
        """Convert a raw instagrapi user dict into an InstagramUser model."""
        return InstagramUser.from_instagrapi_user(raw)

    # ------------------------------------------------------------------
    # Comment mapping
    # ------------------------------------------------------------------

    @staticmethod
    def comment_to_model(raw: dict[str, Any]) -> InstagramComment:
        """Convert a raw instagrapi comment dict into an InstagramComment."""
        return InstagramComment.from_instagrapi_comment(raw)

    # ------------------------------------------------------------------
    # Hashtag mapping
    # ------------------------------------------------------------------

    @staticmethod
    def hashtag_to_model(raw: dict[str, Any]) -> InstagramHashtag:
        """Convert a raw hashtag dict into an InstagramHashtag model."""
        return InstagramHashtag.from_instagrapi_hashtag(raw)

    # ------------------------------------------------------------------
    # Caption extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_hashtags(caption_text: Optional[str]) -> list[str]:
        """Extract all #hashtag tokens from caption text."""
        if not caption_text:
            return []
        return re.findall(r"#(\w+)", caption_text)

    @staticmethod
    def extract_mentions(caption_text: Optional[str]) -> list[str]:
        """Extract all @mention tokens from caption text."""
        if not caption_text:
            return []
        return re.findall(r"@(\w+)", caption_text)

    # ------------------------------------------------------------------
    # Shortcode / ID utilities
    # ------------------------------------------------------------------

    @staticmethod
    def shortcode_to_media_id(code: str) -> int:
        """Convert an Instagram shortcode (e.g. ``CzAbCdEfGh``) to a
        numeric media ID."""
        n = 0
        for ch in code:
            n = n * 64 + _SHORTCODE_ALPHABET.index(ch)
        return n

    @staticmethod
    def media_id_to_shortcode(media_id: int) -> str:
        """Convert a numeric media ID back to an Instagram shortcode."""
        n = int(media_id)
        result = ""
        while n > 0:
            remainder = n % 64
            n = (n - remainder) // 64
            result = _SHORTCODE_ALPHABET[remainder] + result
        return result

    @staticmethod
    def url_to_shortcode(url: str) -> Optional[str]:
        """Extract the shortcode from an Instagram post URL.

        Examples
        --------
        >>> InstagramMapper.url_to_shortcode("https://instagram.com/p/CzAbCdEfGh/")
        'CzAbCdEfGh'
        """
        import re as _re
        match = _re.search(r"instagram\.com/(?:p|reel|tv)/([^/?]+)", url)
        if match:
            return match.group(1)
        return None
