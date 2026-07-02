"""
Pydantic models for Instagram data entities.

All models provide `model_validate` for standard Pydantic instantiation
and `from_instagrapi_*` class-method constructors that accept raw
instagrapi / API response dicts and normalise them.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# InstagramUser
# ---------------------------------------------------------------------------

class InstagramUser(BaseModel):
    """Normalised Instagram user / profile."""

    id: str = ""
    username: str = ""
    full_name: Optional[str] = None
    biography: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    media_count: int = 0
    is_verified: bool = False
    is_private: bool = False
    external_url: Optional[str] = None
    profile_pic_url: Optional[str] = None

    @classmethod
    def from_instagrapi_user(cls, raw: dict) -> InstagramUser:
        """Build an InstagramUser from a raw instagrapi user_info dict."""
        return cls(
            id=str(raw.get("pk", raw.get("id", ""))),
            username=raw.get("username", ""),
            full_name=raw.get("full_name"),
            biography=raw.get("biography"),
            follower_count=raw.get("follower_count", 0) or raw.get("followers", 0) or 0,
            following_count=raw.get("following_count", 0) or raw.get("follows", 0) or 0,
            media_count=raw.get("media_count", 0) or raw.get("posts", 0) or 0,
            is_verified=raw.get("is_verified", False),
            is_private=raw.get("is_private", False),
            external_url=raw.get("external_url"),
            profile_pic_url=raw.get("profile_pic_url"),
        )


# ---------------------------------------------------------------------------
# InstagramHashtag
# ---------------------------------------------------------------------------

class InstagramHashtag(BaseModel):
    """Instagram hashtag metadata."""

    name: str = ""
    post_count: int = 0

    @classmethod
    def from_instagrapi_hashtag(cls, raw: dict) -> InstagramHashtag:
        return cls(
            name=raw.get("name", ""),
            post_count=raw.get("media_count", 0),
        )


# ---------------------------------------------------------------------------
# InstagramPost
# ---------------------------------------------------------------------------

class InstagramPost(BaseModel):
    """Normalised Instagram post / media."""

    id: str = ""
    code: str = ""
    caption: Optional[str] = None
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    taken_at: Optional[datetime] = None
    media_type: int = 1
    carousel_media: list[dict] = Field(default_factory=list)
    video_url: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list)
    location: Optional[dict] = None
    user: Optional[InstagramUser] = None
    music: Optional[dict] = None

    @staticmethod
    def _extract_hashtags(text: Optional[str]) -> list[str]:
        if not text:
            return []
        return re.findall(r"#(\w+)", text)

    @staticmethod
    def _extract_mentions(text: Optional[str]) -> list[str]:
        if not text:
            return []
        return re.findall(r"@(\w+)", text)

    @classmethod
    def _extract_image_urls(cls, raw: dict) -> list[str]:
        """Pull all candidate image URLs from image_versions2."""
        urls: list[str] = []
        image_versions = raw.get("image_versions2") or {}
        candidates = image_versions.get("candidates") or []
        for c in candidates:
            url = c.get("url")
            if url:
                urls.append(url)
        # carousel media
        for cm in raw.get("carousel_media") or []:
            iv = cm.get("image_versions2") or {}
            for c in iv.get("candidates") or []:
                url = c.get("url")
                if url:
                    urls.append(url)
        return urls

    @classmethod
    def _extract_video_url(cls, raw: dict) -> Optional[str]:
        """Pull the best video URL if present."""
        video_versions = raw.get("video_versions") or []
        if video_versions:
            return video_versions[0].get("url")
        # carousel video
        for cm in raw.get("carousel_media") or []:
            vv = cm.get("video_versions") or []
            if vv:
                return vv[0].get("url")
        return None

    @classmethod
    def from_instagrapi_post(cls, raw: dict) -> InstagramPost:
        """Build InstagramPost from a raw instagrapi media_info / feed item dict."""

        user_raw = raw.get("user") or raw.get("owner") or {}
        caption_raw = raw.get("caption") or {}
        caption_text = caption_raw.get("text") if caption_raw else (raw.get("caption_text") or "")

        # taken_at is a Unix timestamp in instagrapi
        taken_at_raw = raw.get("taken_at")
        taken_at: Optional[datetime] = None
        if taken_at_raw:
            try:
                taken_at = datetime.fromtimestamp(int(taken_at_raw))
            except (TypeError, ValueError, OSError):
                pass

        return cls(
            id=str(raw.get("pk", raw.get("id", ""))),
            code=raw.get("code", ""),
            caption=caption_text or None,
            hashtags=cls._extract_hashtags(caption_text),
            mentions=cls._extract_mentions(caption_text),
            like_count=raw.get("like_count", 0) or raw.get("like_and_view_counts_disabled", 0) or 0,
            comment_count=raw.get("comment_count", 0) or 0,
            view_count=raw.get("view_count", 0) or raw.get("play_count", 0) or 0,
            taken_at=taken_at,
            media_type=raw.get("media_type", 1) or 1,
            carousel_media=raw.get("carousel_media") or [],
            video_url=cls._extract_video_url(raw),
            image_urls=cls._extract_image_urls(raw),
            location=raw.get("location"),
            user=InstagramUser.from_instagrapi_user(user_raw) if user_raw else None,
            music=raw.get("music_metadata") or raw.get("music"),
        )


# ---------------------------------------------------------------------------
# InstagramComment
# ---------------------------------------------------------------------------

class InstagramComment(BaseModel):
    """Normalised Instagram comment."""

    id: str = ""
    text: str = ""
    created_at: Optional[datetime] = None
    like_count: int = 0
    user: Optional[InstagramUser] = None
    reply_count: int = 0

    @classmethod
    def from_instagrapi_comment(cls, raw: dict) -> InstagramComment:
        user_raw = raw.get("user") or raw.get("owner") or {}

        created_at_raw = raw.get("created_at") or raw.get("created_at_utc")
        created_at: Optional[datetime] = None
        if created_at_raw:
            try:
                created_at = datetime.fromtimestamp(int(created_at_raw))
            except (TypeError, ValueError, OSError):
                pass

        return cls(
            id=str(raw.get("pk", raw.get("id", ""))),
            text=raw.get("text", ""),
            created_at=created_at,
            like_count=raw.get("comment_like_count", 0)
            or raw.get("like_count", 0)
            or 0,
            user=InstagramUser.from_instagrapi_user(user_raw) if user_raw else None,
            reply_count=raw.get("child_comment_count", 0)
            or raw.get("reply_count", 0)
            or 0,
        )
