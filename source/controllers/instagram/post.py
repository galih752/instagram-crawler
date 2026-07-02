"""
Instagram Post controllers.

Supports:
- post_by_account: fetch recent posts for a given username.
- post_by_hashtag: fetch recent posts under a hashtag.
- post_by_keyword: search posts by keyword via Instagram search.
- post_detail: fetch a single post by ID or shortcode URL.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from controllers.instagram import InstagramBaseController
from instagrapi.exceptions import (
    ClientForbiddenError,
    LoginRequired,
    ChallengeRequired,
    ChallengeError,
)
from library.instagram.mapper import InstagramMapper
from models.instagram import InstagramPost


class InstagramPostController(InstagramBaseController):
    """Handles all post-related crawl jobs."""

    key: str = "instagram:posts:hash"

    async def handler(self, job: dict[str, Any]) -> None:
        """Dispatch based on job type."""
        post_type = job.get("type") or job.get("post_type", "post_by_account")

        dispatch = {
            "post_by_account": self.get_posts_by_account,
            "post_by_hashtag": self.get_posts_by_hashtag,
            "post_by_keyword": self.get_posts_by_keyword,
            "post_detail": self.get_post_detail,
        }

        handler_fn = dispatch.get(post_type)
        if handler_fn is None:
            self.log.warning(f"Unknown post type: {post_type}")
            return

        await handler_fn(job)

    # ------------------------------------------------------------------
    # post_by_account
    # ------------------------------------------------------------------

    async def get_posts_by_account(self, job: dict[str, Any]) -> None:
        """Fetch recent posts for a given Instagram username via instagrapi."""
        username = job.get("username") or job.get("keyword", "")
        count = job.get("count", self.max_post)
        tags = job.get("media_tags", [])

        self.log.info(f"Fetching posts for account: {username} (max {count})")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                # Fetch user info
                user_info = self.client.user_info_by_username(username)
                user_id = str(user_info.pk)

                # Fetch recent media
                medias, _ = self.client.user_medias_v1(user_id=int(user_id), amount=count)

                if not medias:
                    self.log.info(f"No posts found for {username}")
                    return

                for media in medias:
                    raw = media.dict() if hasattr(media, "dict") else media
                    raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                    post = InstagramPost.from_instagrapi_post(raw)
                    post_data = post.model_dump(mode="json")

                    # Enrich
                    post_data["type"] = "post"
                    post_data["media_tags"] = tags
                    post_data["search_metadata"] = job

                    # Output
                    self.output.put(json.dumps(post_data, default=str))

                    # Store to SSDB for dedup
                    await self.store_to_ssdb(
                        post=post_data,
                        key=self.key,
                        value=post.id,
                        job_type="post",
                    )

                    # Chain comment fetching if comments exist
                    if post.comment_count > 0:
                        comment_job = {
                            "code": post.code,
                            "post_code": post.code,
                            "media_id": post.id,
                            "cache": False,
                            "post": post_data,
                            "tags": tags,
                        }
                        await self.pusher(
                            job=comment_job,
                            tube=self.tube_comment,
                            ids=post.id,
                        )

                self.log.info(f"Finished fetching {len(medias)} posts for {username}")
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for {username}")
                else:
                    self.log.error(f"Max retries reached for {username}")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error fetching posts for {username}: {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise

    # ------------------------------------------------------------------
    # post_by_hashtag
    # ------------------------------------------------------------------

    async def get_posts_by_hashtag(self, job: dict[str, Any]) -> None:
        """Fetch recent posts for a given hashtag via instagrapi."""
        hashtag = job.get("hashtag") or job.get("keyword", "").replace("#", "").strip()
        count = job.get("count", self.max_post)
        tags = job.get("media_tags", [])

        if not hashtag:
            self.log.warning("No hashtag provided")
            return

        self.log.info(f"Fetching posts for hashtag: #{hashtag} (max {count})")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                medias = self.client.hashtag_medias_recent(
                    name=hashtag,
                    amount=count,
                )

                if not medias:
                    self.log.info(f"No posts found for #{hashtag}")
                    return

                for media in medias:
                    raw = media.dict() if hasattr(media, "dict") else media
                    raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                    post = InstagramPost.from_instagrapi_post(raw)
                    post_data = post.model_dump(mode="json")

                    post_data["type"] = "post"
                    post_data["media_tags"] = tags
                    post_data["search_metadata"] = job

                    self.output.put(json.dumps(post_data, default=str))

                    is_new = await self.store_to_ssdb(
                        post=post_data,
                        key=self.key,
                        value=post.id,
                        job_type="post",
                    )

                    if is_new and post.comment_count > 0:
                        comment_job = {
                            "code": post.code,
                            "post_code": post.code,
                            "media_id": post.id,
                            "cache": False,
                            "post": post_data,
                            "tags": tags,
                        }
                        await self.pusher(
                            job=comment_job,
                            tube=self.tube_comment,
                            ids=post.id,
                        )

                self.log.info(f"Finished fetching {len(medias)} posts for #{hashtag}")
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for #{hashtag}")
                else:
                    self.log.error(f"Max retries reached for #{hashtag}")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error for #{hashtag}: {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise

    # ------------------------------------------------------------------
    # post_by_keyword
    # ------------------------------------------------------------------

    async def get_posts_by_keyword(self, job: dict[str, Any]) -> None:
        """Search posts by keyword via instagrapi search_top / fbsearch."""
        keyword = job.get("keyword", "").strip()
        count = job.get("count", self.max_post)
        tags = job.get("media_tags", [])

        if not keyword:
            self.log.warning("No keyword provided")
            return

        self.log.info(f"Searching posts for keyword: {keyword} (max {count})")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                # Try fbsearch (topsearch_flat) first, fall back to search_top
                try:
                    search_results = self.client.fbsearch(keyword)
                    medias = search_results.get("items", []) if isinstance(search_results, dict) else []
                except Exception:
                    self.log.warning("fbsearch failed, trying search_top")
                    search_results = self.client.search_top(query=keyword)
                    medias = search_results if isinstance(search_results, list) else []

                if not medias:
                    self.log.info(f"No posts found for keyword: {keyword}")
                    return

                for media in medias[:count]:
                    raw = media.dict() if hasattr(media, "dict") else media
                    raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                    post = InstagramPost.from_instagrapi_post(raw)
                    post_data = post.model_dump(mode="json")

                    post_data["type"] = "post"
                    post_data["media_tags"] = tags
                    post_data["search_metadata"] = job

                    self.output.put(json.dumps(post_data, default=str))

                    is_new = await self.store_to_ssdb(
                        post=post_data,
                        key=self.key,
                        value=post.id,
                        job_type="post",
                    )

                    if is_new and post.comment_count > 0:
                        comment_job = {
                            "code": post.code,
                            "post_code": post.code,
                            "media_id": post.id,
                            "cache": False,
                            "post": post_data,
                            "tags": tags,
                        }
                        await self.pusher(
                            job=comment_job,
                            tube=self.tube_comment,
                            ids=post.id,
                        )

                self.log.info(f"Finished searching {min(len(medias), count)} posts for '{keyword}'")
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for keyword '{keyword}'")
                else:
                    self.log.error(f"Max retries reached for keyword '{keyword}'")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error for keyword '{keyword}': {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise

    # ------------------------------------------------------------------
    # post_detail
    # ------------------------------------------------------------------

    async def get_post_detail(self, job: dict[str, Any]) -> None:
        """Fetch a single post by media ID or shortcode URL."""
        media_id = job.get("media_id") or job.get("post_id", "")
        url = job.get("url") or job.get("link", "")
        code = job.get("code", "")
        tags = job.get("media_tags", [])

        # Resolve media_id from URL if needed
        if not media_id and url:
            code = InstagramMapper.url_to_shortcode(url)
            if code:
                media_id = str(InstagramMapper.shortcode_to_media_id(code))

        if not media_id:
            self.log.warning(f"Cannot determine media_id from job: {job}")
            return

        self.log.info(f"Fetching post detail for media_id={media_id}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                result = self.client.media_info_v1(media_pk=int(media_id))
                raw = result.dict() if hasattr(result, "dict") else result
                raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                post = InstagramPost.from_instagrapi_post(raw)
                post_data = post.model_dump(mode="json")

                post_data["type"] = "post"
                post_data["media_tags"] = tags
                post_data["search_metadata"] = job

                self.output.put(json.dumps(post_data, default=str))

                await self.store_to_ssdb(
                    post=post_data,
                    key=self.key,
                    value=post.id,
                    job_type="post",
                )

                self.log.info(f"Fetched post detail: {post.code}")

                # Chain comment job if needed
                if post.comment_count > 0:
                    comment_job = {
                        "code": post.code,
                        "post_code": post.code,
                        "media_id": post.id,
                        "cache": False,
                        "post": post_data,
                        "tags": tags,
                    }
                    await self.pusher(
                        job=comment_job,
                        tube=self.tube_comment,
                        ids=post.id,
                    )

                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for post {media_id}")
                else:
                    self.log.error(f"Max retries reached for post {media_id}")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error for post {media_id}: {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise
