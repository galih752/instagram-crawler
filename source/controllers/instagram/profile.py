"""
Instagram Profile controller.

Supports:
- get_profile: fetch detailed user profile by username.
- search_profile: search for users by query string.
"""

from __future__ import annotations

import json
from typing import Any

from controllers.instagram import InstagramBaseController
from instagrapi.exceptions import (
    ClientForbiddenError,
    LoginRequired,
    ChallengeRequired,
    ChallengeError,
)
from models.instagram import InstagramUser


class InstagramProfileController(InstagramBaseController):
    """Handles profile-related crawl jobs."""

    key: str = "instagram:profiles:hash"

    async def handler(self, job: dict[str, Any]) -> None:
        """Dispatch based on job type."""
        profile_type = job.get("type") or job.get("profile_type", "get_profile")

        if profile_type == "get_profile":
            await self.get_profile(job)
        elif profile_type == "search_profile":
            await self.search_profile(job)
        else:
            self.log.warning(f"Unknown profile type: {profile_type}")

    # ------------------------------------------------------------------
    # get_profile
    # ------------------------------------------------------------------

    async def get_profile(self, job: dict[str, Any]) -> None:
        """Fetch a single user profile by username."""
        username = job.get("username") or job.get("keyword", "").strip()
        tags = job.get("media_tags", [])

        if not username:
            self.log.warning("No username provided for profile fetch")
            return

        self.log.info(f"Fetching profile: {username}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                user_info = self.client.user_info_by_username(username)
                raw = user_info.dict() if hasattr(user_info, "dict") else user_info

                profile = InstagramUser.from_instagrapi_user(raw)
                profile_data = profile.model_dump(mode="json")

                # Enrich
                profile_data["type"] = "profile"
                profile_data["media_tags"] = tags
                profile_data["search_metadata"] = job

                # Output
                self.output.put(json.dumps(profile_data, default=str))

                # Cache in SSDB
                await self.store_to_ssdb(
                    post=profile_data,
                    key=self.key,
                    value=profile.id or username,
                    job_type="profile",
                )

                self.log.info(f"Fetched profile: {username} (id={profile.id})")
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for profile {username}")
                else:
                    self.log.error(f"Max retries reached for profile {username}")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error fetching profile {username}: {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise

    # ------------------------------------------------------------------
    # search_profile
    # ------------------------------------------------------------------

    async def search_profile(self, job: dict[str, Any]) -> None:
        """Search for Instagram users by query string."""
        query = job.get("query") or job.get("keyword", "").strip()
        count = job.get("count", 30)
        tags = job.get("media_tags", [])

        if not query:
            self.log.warning("No query provided for profile search")
            return

        self.log.info(f"Searching profiles for: {query} (max {count})")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self.logging_in()
                self.log.info(f"Using account: {account.get('username_account')}")

                results = self.client.search_users(query=query, count=count)

                if not results:
                    self.log.info(f"No profiles found for query: {query}")
                    return

                for user_info in results[:count]:
                    raw = user_info.dict() if hasattr(user_info, "dict") else user_info

                    profile = InstagramUser.from_instagrapi_user(raw)
                    profile_data = profile.model_dump(mode="json")

                    profile_data["type"] = "profile"
                    profile_data["media_tags"] = tags
                    profile_data["search_metadata"] = job

                    self.output.put(json.dumps(profile_data, default=str))

                    await self.store_to_ssdb(
                        post=profile_data,
                        key=self.key,
                        value=profile.id or profile.username,
                        job_type="profile",
                    )

                self.log.info(
                    f"Finished searching {min(len(results), count)} profiles for '{query}'"
                )
                break

            except (ClientForbiddenError, LoginRequired, ChallengeRequired, ChallengeError) as e:
                self.report_session(type(e).__name__)
                if attempt < max_retries - 1:
                    self.log.info(f"Retry {attempt + 1}/{max_retries} for search '{query}'")
                else:
                    self.log.error(f"Max retries reached for search '{query}'")
                continue

            except Exception as e:
                self.log.error(f"Unexpected error searching profiles '{query}': {e}")
                self.report_session(str(e))
                if attempt < max_retries - 1:
                    continue
                raise
