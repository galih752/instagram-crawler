"""
Instagram Comment controller.

Supports:
- get_comments: fetch comments for a given media_id with pagination.
- get_comment_replies: fetch replies to a specific comment.
"""

from __future__ import annotations

import copy
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
from models.instagram import InstagramComment


class InstagramCommentController(InstagramBaseController):
    """Handles comment-related crawl jobs."""

    key: str = "instagram:comments:hash"

    async def handler(self, job: dict[str, Any]) -> None:
        """Dispatch based on job type."""
        comment_type = job.get("type") or job.get("comment_type", "get_comments")

        if comment_type == "get_comments":
            await self.get_comments(job)
        elif comment_type == "get_comment_replies":
            await self.get_comment_replies(job)
        else:
            self.log.warning(f"Unknown comment type: {comment_type}")

    # ------------------------------------------------------------------
    # get_comments
    # ------------------------------------------------------------------

    async def get_comments(self, job: dict[str, Any]) -> None:
        """Fetch comments for a post (media_id), with pagination support."""
        media_id = job.get("media_id", "")
        code = job.get("code") or job.get("post_code", "")
        pagination_key = job.get("pagination_key")
        next_id = job.get("next_id")
        cache = job.get("cache", True)
        tags = job.get("media_tags", job.get("tags", []))
        post = job.get("post", {})
        amount = job.get("count", 30)

        if not media_id:
            self.log.warning("No media_id provided for comment fetch")
            return

        self.log.info(f"Fetching comments for media_id={media_id} (amount={amount})")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                if not account:
                    self.log.error("Failed to acquire session")
                    continue

                self.log.info(
                    f"Using session: {account.get('username_account', 'unknown')}"
                )

                comments, updated_post, next_id_out, pagination_key_out = (
                    self.client.media_comments_pagination(
                        media_id=str(media_id),
                        amount=amount,
                        pagination_key=pagination_key,
                        next_id=next_id,
                    )
                )

                has_more = bool(pagination_key_out)

                if not post and updated_post:
                    post = updated_post

                if comments:
                    for comment in comments:
                        raw = comment.dict() if hasattr(comment, "dict") else comment
                        raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                        comment_model = InstagramComment.from_instagrapi_comment(raw)
                        comment_data = comment_model.model_dump(mode="json")

                        # Dedup check
                        redis_key = f"instagram:comment:{comment_model.id}"
                        if self.use_cache and self.redis.exists(redis_key):
                            self.log.info(f"Skipping duplicate comment {comment_model.id}")
                            continue

                        comment_data["crawling_at"] = int(datetime.now().timestamp())
                        comment_data["post"] = post
                        comment_data["post_code"] = code
                        comment_data["type"] = "comment"
                        comment_data["media_tags"] = tags

                        self.output.put(json.dumps(comment_data, default=str))

                        if self.use_cache:
                            self.redis.setex(
                                redis_key,
                                time=86400 * 4,
                                value=json.dumps(comment_data, default=str),
                            )

                        self.log.info(f"Pushed comment {comment_model.id}")

                        # Chain reply job if needed
                        if comment_model.reply_count > 0:
                            reply_job = {
                                "post": post,
                                "comment": comment_data,
                                "media_id": media_id,
                                "comment_id": comment_model.id,
                            }
                            await self.pusher(
                                job=reply_job,
                                tube=self.tube_replies,
                                ids=comment_model.id,
                            )

                    # Re-enqueue for next page
                    if has_more and not cache:
                        next_job = copy.deepcopy(job)
                        next_job["next_id"] = next_id_out
                        next_job["pagination_key"] = pagination_key_out
                        self.input.put_message(body=json.dumps(next_job, default=str))
                        self.log.info(
                            f"Enqueued next page: pagination_key={pagination_key_out}"
                        )
                else:
                    self.log.info(f"No comments found for media_id={media_id}")

                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.log.warning(f"Session error: {type(e).__name__}")
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    continue
                self.log.error(f"Max retries exhausted for comments on {media_id}")

            except Exception as e:
                self.log.error(f"Error fetching comments for {media_id}: {e}")
                if "404" in str(e) or "Not Found" in str(e):
                    self.log.warning(f"Post {media_id} not found; skipping")
                    return
                if attempt < max_retries - 1:
                    continue
                raise

    # ------------------------------------------------------------------
    # get_comment_replies
    # ------------------------------------------------------------------

    async def get_comment_replies(self, job: dict[str, Any]) -> None:
        """Fetch child comments (replies) for a specific parent comment."""
        media_id = job.get("media_id", "")
        comment_id = job.get("comment_id", "")
        tags = job.get("media_tags", job.get("tags", []))
        post = job.get("post", {})
        parent_comment = job.get("comment", {})
        amount = job.get("count", 30)

        if not media_id or not comment_id:
            self.log.warning("media_id and comment_id are required for replies")
            return

        self.log.info(
            f"Fetching replies for comment {comment_id} on media {media_id}"
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                if not account:
                    self.log.error("Failed to acquire session")
                    continue

                replies: list[dict[str, Any]] = self.client.media_comment_replies(
                    media_id=str(media_id),
                    comment_id=str(comment_id),
                    amount=amount,
                )

                if not replies:
                    self.log.info(f"No replies found for comment {comment_id}")
                    return

                for reply in replies:
                    raw = reply.dict() if hasattr(reply, "dict") else reply
                    raw = raw if isinstance(raw, dict) else json.loads(json.dumps(raw, default=str))

                    reply_model = InstagramComment.from_instagrapi_comment(raw)
                    reply_data = reply_model.model_dump(mode="json")

                    # Dedup check
                    redis_key = f"instagram:comment:{reply_model.id}"
                    if self.use_cache and self.redis.exists(redis_key):
                        self.log.info(f"Skipping duplicate reply {reply_model.id}")
                        continue

                    reply_data["crawling_at"] = int(datetime.now().timestamp())
                    reply_data["post"] = post
                    reply_data["parent_comment"] = parent_comment
                    reply_data["type"] = "comment_reply"
                    reply_data["media_tags"] = tags

                    self.output.put(json.dumps(reply_data, default=str))

                    if self.use_cache:
                        self.redis.setex(
                            redis_key,
                            time=86400 * 4,
                            value=json.dumps(reply_data, default=str),
                        )

                    self.log.info(f"Pushed reply {reply_model.id}")

                self.log.info(f"Finished fetching {len(replies)} replies for comment {comment_id}")
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.log.warning(f"Session error: {type(e).__name__}")
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    continue
                self.log.error(f"Max retries exhausted for replies on {comment_id}")

            except Exception as e:
                self.log.error(f"Error fetching replies for {comment_id}: {e}")
                if "404" in str(e) or "Not Found" in str(e):
                    self.log.warning(f"Comment {comment_id} not found; skipping")
                    return
                if attempt < max_retries - 1:
                    continue
                raise
