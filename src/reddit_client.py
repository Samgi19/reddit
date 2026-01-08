from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import praw
import prawcore

from .config import FilterSettings, RateLimitSettings, WeightSettings


class RedditClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        user_agent: str,
        filters: FilterSettings,
        weights: WeightSettings,
        rate_limit: RateLimitSettings,
    ):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=user_agent,
            check_for_async=False,
        )
        self.filters = filters
        self.weights = weights
        self.rate_limit = rate_limit
        self._cache: Dict[str, tuple[float, dict]] = {}

    def test(self) -> bool:
        try:
            _ = self.reddit.user.me()
            return True
        except Exception:
            return False

    def _cache_get(self, key: str) -> Optional[dict]:
        item = self._cache.get(key)
        if not item:
            return None
        ts, payload = item
        if time.time() - ts > self.rate_limit.cache_ttl_seconds:
            return None
        return payload

    def _cache_set(self, key: str, payload: dict) -> None:
        self._cache[key] = (time.time(), payload)

    def safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except prawcore.exceptions.RequestException:
            time.sleep(self.rate_limit.sleep_seconds)
            return func(*args, **kwargs)
        except prawcore.exceptions.ResponseException:
            time.sleep(self.rate_limit.sleep_seconds)
            return func(*args, **kwargs)

    def fetch_subreddit_meta(self, name: str) -> Optional[dict]:
        cache_key = f"sub:{name}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        try:
            subreddit = self.reddit.subreddit(name)
            subreddit._fetch()
            if not self._nsfw_allowed(subreddit.over18):
                return None
            moderators = [m.name for m in subreddit.moderator()]
            data = {
                "name": subreddit.display_name,
                "nsfw": subreddit.over18,
                "subscribers": subreddit.subscribers or 0,
                "active_users": subreddit.active_user_count or 0,
                "created_utc": subreddit.created_utc,
                "botbouncer_mod": "BotBouncer" in moderators,
            }
            self._cache_set(cache_key, data)
            return data
        except Exception:
            return None

    def search_keyword(self, query: str, limit: int = 25) -> List[dict]:
        results = []
        for sub in self.safe_call(self.reddit.subreddits.search, query, limit=limit):
            if not self._nsfw_allowed(sub.over18):
                continue
            results.append(
                {
                    "name": sub.display_name,
                    "nsfw": sub.over18,
                    "subscribers": sub.subscribers or 0,
                    "active_users": sub.active_user_count or 0,
                    "created_utc": sub.created_utc,
                    "botbouncer_mod": False,
                    "score": 0,
                }
            )
        return results

    def subreddit_posts(self, name: str, limit: int) -> Iterable:
        subreddit = self.reddit.subreddit(name)
        return self.safe_call(subreddit.hot, limit=limit)

    def user_activity(self, username: str, comments_limit: int, submissions_limit: int):
        user = self.reddit.redditor(username)
        comments = self.safe_call(user.comments.new, limit=comments_limit)
        submissions = self.safe_call(user.submissions.new, limit=submissions_limit)
        return comments, submissions

    def _nsfw_allowed(self, over18: bool) -> bool:
        if self.filters.nsfw_mode == "all":
            return True
        if self.filters.nsfw_mode == "nsfw_only":
            return over18
        if self.filters.nsfw_mode == "exclude_nsfw":
            return not over18
        return True

    def passes_filters(self, subreddit: dict) -> bool:
        if not self._nsfw_allowed(subreddit.get("nsfw", False)):
            return False
        subs = subreddit.get("subscribers", 0)
        active = subreddit.get("active_users", 0)
        return (
            self.filters.subscribers_min <= subs <= self.filters.subscribers_max
            and self.filters.active_users_min <= active <= self.filters.active_users_max
        )

    def score_subreddit(self, post_count: int, comment_count: int, moderator_hits: int, botbouncer: bool) -> float:
        score = (
            post_count * self.weights.post
            + comment_count * self.weights.comment
            + moderator_hits * self.weights.moderator
        )
        if botbouncer:
            score += self.weights.botbouncer_bonus
        return score

    def account_age_days(self, author) -> Optional[int]:
        try:
            created = datetime.utcfromtimestamp(author.created_utc)
            return (datetime.utcnow() - created).days
        except Exception:
            return None

    def passes_user_filters(self, author) -> bool:
        if not author:
            return False
        karma_ok = self.filters.karma_min <= getattr(author, "comment_karma", 0) <= self.filters.karma_max
        account_days = self.account_age_days(author)
        age_ok = account_days is None or (
            self.filters.account_age_min <= account_days <= self.filters.account_age_max
        )
        return karma_ok and age_ok
