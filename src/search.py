from __future__ import annotations

import csv
import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .config import AppConfig, ensure_results_dir
from .database import DatabaseManager, SubredditRecord
from .reddit_client import RedditClient
from .telegram_client import TelegramClient


@dataclass
class SearchParams:
    mode: str
    seed: str
    depth: int
    posts_per_subreddit: int
    comments_per_user: int
    submissions_per_user: int
    per_depth_limit: int
    notify: bool
    send_results: bool


class SearchWorker(threading.Thread):
    def __init__(
        self,
        config: AppConfig,
        reddit_client: RedditClient,
        telegram_client: TelegramClient,
        db: DatabaseManager,
        params: SearchParams,
        on_progress: Callable[[str], None],
        on_finished: Callable[[List[dict]], None],
    ):
        super().__init__(daemon=True)
        self.config = config
        self.reddit_client = reddit_client
        self.telegram_client = telegram_client
        self.db = db
        self.params = params
        self.on_progress = on_progress
        self.on_finished = on_finished
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self) -> None:
        results: Dict[str, dict] = {}
        self.on_progress("Starting search…")
        try:
            if self.params.mode == "Subreddit":
                results = self._search_subreddit(self.params.seed)
            elif self.params.mode == "User":
                results = self._search_user(self.params.seed)
            elif self.params.mode == "Graph":
                results = self._search_graph(self.params.seed)
            elif self.params.mode == "Keyword":
                results = {r["name"]: r for r in self.reddit_client.search_keyword(self.params.seed)}
        finally:
            result_list = sorted(results.values(), key=lambda r: r["score"], reverse=True)
            self._persist_results(result_list)
            self.on_finished(result_list)
            if self.params.notify:
                self._notify(result_list)

    def _notify(self, results: List[dict]) -> None:
        summary = f"Search '{self.params.mode}' finished with {len(results)} candidates"
        if self.params.send_results and results:
            summary = self.telegram_client.format_results(results, limit=self.config.search.top_n)
            files = self._export(results, prefix="telegram")
            self.telegram_client.send_results(summary, files, to_channel=self.config.telegram.send_to_channel)
        else:
            self.telegram_client.broadcast(summary, to_channel=self.config.telegram.send_to_channel)

    def _persist_results(self, results: List[dict]) -> None:
        now = datetime.utcnow().isoformat()
        records = []
        for row in results:
            records.append(
                SubredditRecord(
                    name=row["name"],
                    nsfw=row.get("nsfw", False),
                    subscribers=row.get("subscribers", 0),
                    active_users=row.get("active_users", 0),
                    created_utc=row.get("created_utc", 0.0),
                    botbouncer_mod=row.get("botbouncer_mod", False),
                    discovered_at=now,
                    last_seen_at=now,
                    source=row.get("source", self.params.mode),
                    score=row.get("score", 0.0),
                    frequency=1,
                )
            )
        self.db.upsert_subreddits(records)

    def _export(self, results: List[dict], prefix: str = "results") -> List[str]:
        ensure_results_dir()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = Path("results") / f"{prefix}_{timestamp}.json"
        csv_path = Path("results") / f"{prefix}_{timestamp}.csv"
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(results, jf, ensure_ascii=False, indent=2)
        with open(csv_path, "w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(
                cf, fieldnames=["name", "score", "subscribers", "active_users", "nsfw", "botbouncer_mod", "source"]
            )
            writer.writeheader()
            for row in results:
                writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
        return [str(json_path), str(csv_path)]

    def _search_subreddit(self, name: str) -> Dict[str, dict]:
        collected: Dict[str, dict] = {}
        for post in self.reddit_client.subreddit_posts(name, limit=self.params.posts_per_subreddit):
            if self._stop_event.is_set():
                break
            author = post.author
            if not self.reddit_client.passes_user_filters(author):
                continue
            sub_name = str(post.subreddit.display_name)
            collected.setdefault(sub_name, self._baseline(sub_name, post.subreddit.over18))
            collected[sub_name]["post_count"] += 1
            self._process_author(author, collected)
        return self._finalize_scores(collected, source=f"seed:{name}")

    def _search_user(self, username: str) -> Dict[str, dict]:
        collected: Dict[str, dict] = {}
        comments, submissions = self.reddit_client.user_activity(username, self.params.comments_per_user, self.params.submissions_per_user)
        for comment in comments:
            if self._stop_event.is_set():
                break
            sub_name = str(comment.subreddit.display_name)
            collected.setdefault(sub_name, self._baseline(sub_name, comment.subreddit.over18))
            collected[sub_name]["comment_count"] += 1
        for submission in submissions:
            if self._stop_event.is_set():
                break
            sub_name = str(submission.subreddit.display_name)
            collected.setdefault(sub_name, self._baseline(sub_name, submission.subreddit.over18))
            collected[sub_name]["post_count"] += 1
        return self._finalize_scores(collected, source=f"user:{username}")

    def _search_graph(self, seed: str) -> Dict[str, dict]:
        collected: Dict[str, dict] = {}
        visited = set()
        queue = deque([(seed, 0)])
        while queue:
            if self._stop_event.is_set():
                break
            current, depth = queue.popleft()
            if current in visited or depth > self.params.depth:
                continue
            visited.add(current)
            self.on_progress(f"Scanning r/{current} depth {depth}")
            subs = self._search_subreddit(current)
            for name, data in subs.items():
                if name not in collected:
                    collected[name] = data
                else:
                    collected[name]["score"] += data["score"]
            if depth < self.params.depth:
                neighbors = list(subs.keys())[: self.params.per_depth_limit]
                for neigh in neighbors:
                    queue.append((neigh, depth + 1))
        return collected

    def _baseline(self, name: str, nsfw: bool) -> dict:
        return {"name": name, "nsfw": nsfw, "post_count": 0, "comment_count": 0, "moderator_hits": 0}

    def _process_author(self, author, collected: Dict[str, dict]) -> None:
        if not author:
            return
        comments, submissions = self.reddit_client.user_activity(
            author.name, self.params.comments_per_user, self.params.submissions_per_user
        )
        for comment in comments:
            sub_name = str(comment.subreddit.display_name)
            collected.setdefault(sub_name, self._baseline(sub_name, comment.subreddit.over18))
            collected[sub_name]["comment_count"] += 1
        for submission in submissions:
            sub_name = str(submission.subreddit.display_name)
            collected.setdefault(sub_name, self._baseline(sub_name, submission.subreddit.over18))
            collected[sub_name]["post_count"] += 1

    def _finalize_scores(self, collected: Dict[str, dict], source: str) -> Dict[str, dict]:
        results: Dict[str, dict] = {}
        for name, data in collected.items():
            meta = self.reddit_client.fetch_subreddit_meta(name)
            if not meta:
                continue
            if not self.reddit_client.passes_filters(meta):
                continue
            moderator_hits = data.get("moderator_hits", 0)
            score = self.reddit_client.score_subreddit(
                data.get("post_count", 0), data.get("comment_count", 0), moderator_hits, meta.get("botbouncer_mod", False)
            )
            meta.update(
                {
                    "score": score,
                    "post_count": data.get("post_count", 0),
                    "comment_count": data.get("comment_count", 0),
                    "moderator_hits": moderator_hits,
                    "source": source,
                }
            )
            results[name] = meta
        return results
