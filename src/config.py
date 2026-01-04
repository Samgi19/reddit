import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv


@dataclass
class RedditSettings:
    client_id: str = ""
    client_secret: str = ""
    username: str = ""
    password: str = ""
    user_agent: str = "RedditDiscoveryBot/0.1"


@dataclass
class TelegramSettings:
    bot_token: str = ""
    admin_ids: List[str] = field(default_factory=list)
    channel_id: str = ""
    send_to_channel: bool = False


@dataclass
class FilterSettings:
    nsfw_mode: str = "nsfw_only"
    karma_min: int = 0
    karma_max: int = 100000
    account_age_min: int = 0
    account_age_max: int = 4000
    subscribers_min: int = 0
    subscribers_max: int = 5000000
    active_users_min: int = 0
    active_users_max: int = 500000


@dataclass
class SearchSettings:
    default_posts_per_subreddit: int = 25
    default_comments_per_user: int = 10
    default_submissions_per_user: int = 5
    graph_depth: int = 2
    per_depth_limit: int = 15
    top_n: int = 20


@dataclass
class WeightSettings:
    post: float = 1.0
    comment: float = 0.5
    moderator: float = 3.0
    botbouncer_bonus: float = 2.0


@dataclass
class RateLimitSettings:
    sleep_seconds: int = 2
    cache_ttl_seconds: int = 900


@dataclass
class NotificationSettings:
    include_results: bool = True
    include_files: bool = False


@dataclass
class AppConfig:
    reddit: RedditSettings = field(default_factory=RedditSettings)
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    filters: FilterSettings = field(default_factory=FilterSettings)
    search: SearchSettings = field(default_factory=SearchSettings)
    weights: WeightSettings = field(default_factory=WeightSettings)
    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)


class ConfigManager:
    def __init__(self, path: Path | str = "config.yaml"):
        self.path = Path(path)
        load_dotenv(override=False)
        self.config = AppConfig()

    def load(self) -> AppConfig:
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._apply_dict(data)
        self._apply_env()
        return self.config

    def save(self) -> None:
        data = self.to_dict()
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reddit": vars(self.config.reddit),
            "telegram": {
                "bot_token": self.config.telegram.bot_token,
                "admin_ids": self.config.telegram.admin_ids,
                "channel_id": self.config.telegram.channel_id,
                "send_to_channel": self.config.telegram.send_to_channel,
            },
            "filters": {
                "nsfw_mode": self.config.filters.nsfw_mode,
                "karma": {"min": self.config.filters.karma_min, "max": self.config.filters.karma_max},
                "account_age_days": {
                    "min": self.config.filters.account_age_min,
                    "max": self.config.filters.account_age_max,
                },
                "subscribers": {
                    "min": self.config.filters.subscribers_min,
                    "max": self.config.filters.subscribers_max,
                },
                "active_users": {
                    "min": self.config.filters.active_users_min,
                    "max": self.config.filters.active_users_max,
                },
            },
            "search": vars(self.config.search),
            "weights": vars(self.config.weights),
            "rate_limit": vars(self.config.rate_limit),
            "notifications": vars(self.config.notifications),
        }

    def _apply_dict(self, data: Dict[str, Any]) -> None:
        reddit_data = data.get("reddit", {})
        telegram_data = data.get("telegram", {})
        filters_data = data.get("filters", {})
        search_data = data.get("search", {})
        weights_data = data.get("weights", {})
        rate_limit_data = data.get("rate_limit", {})
        notifications_data = data.get("notifications", {})

        self.config.reddit = RedditSettings(**{**vars(self.config.reddit), **reddit_data})
        self.config.telegram = TelegramSettings(**{**vars(self.config.telegram), **telegram_data})
        self.config.search = SearchSettings(**{**vars(self.config.search), **search_data})
        self.config.weights = WeightSettings(**{**vars(self.config.weights), **weights_data})
        self.config.rate_limit = RateLimitSettings(**{**vars(self.config.rate_limit), **rate_limit_data})
        self.config.notifications = NotificationSettings(
            **{**vars(self.config.notifications), **notifications_data}
        )

        self._apply_filters(filters_data)

    def _apply_env(self) -> None:
        env_map = {
            "CLIENT_ID": ("reddit", "client_id"),
            "CLIENT_SECRET": ("reddit", "client_secret"),
            "USERNAME": ("reddit", "username"),
            "PASSWORD": ("reddit", "password"),
            "USER_AGENT": ("reddit", "user_agent"),
            "BOT_TOKEN": ("telegram", "bot_token"),
            "CHANNEL_ID": ("telegram", "channel_id"),
            "SEND_TO_CHANNEL": ("telegram", "send_to_channel"),
            "ADMIN_IDS": ("telegram", "admin_ids"),
        }
        for env_key, (section, attr) in env_map.items():
            val = os.getenv(env_key)
            if val:
                if attr == "admin_ids":
                    parsed = [item.strip() for item in val.split(",") if item.strip()]
                    getattr(self.config, section).admin_ids = parsed
                elif attr == "send_to_channel":
                    getattr(self.config, section).send_to_channel = val.lower() == "true"
                else:
                    setattr(getattr(self.config, section), attr, val)

    def _apply_filters(self, filters_data: Dict[str, Any]) -> None:
        nsfw_mode = filters_data.get("nsfw_mode", self.config.filters.nsfw_mode)
        karma = filters_data.get("karma", {})
        account_age = filters_data.get("account_age_days", {})
        subs = filters_data.get("subscribers", {})
        active = filters_data.get("active_users", {})

        self.config.filters = FilterSettings(
            nsfw_mode=nsfw_mode,
            karma_min=karma.get("min", self.config.filters.karma_min),
            karma_max=karma.get("max", self.config.filters.karma_max),
            account_age_min=account_age.get("min", self.config.filters.account_age_min),
            account_age_max=account_age.get("max", self.config.filters.account_age_max),
            subscribers_min=subs.get("min", self.config.filters.subscribers_min),
            subscribers_max=subs.get("max", self.config.filters.subscribers_max),
            active_users_min=active.get("min", self.config.filters.active_users_min),
            active_users_max=active.get("max", self.config.filters.active_users_max),
        )

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        self._apply_dict(data)
        self.save()


def ensure_results_dir() -> Path:
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    return results_dir
