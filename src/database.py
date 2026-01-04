from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class SubredditRecord:
    name: str
    nsfw: bool
    subscribers: int
    active_users: int
    created_utc: float
    botbouncer_mod: bool
    discovered_at: str
    last_seen_at: str
    source: str
    score: float
    frequency: int


class DatabaseManager:
    def __init__(self, path: Path | str = "registry.db"):
        self.path = Path(path)
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _ensure_tables(self) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subreddits (
                    name TEXT PRIMARY KEY,
                    nsfw INTEGER,
                    subscribers INTEGER,
                    active_users INTEGER,
                    created_utc REAL,
                    botbouncer_mod INTEGER,
                    discovered_at TEXT,
                    last_seen_at TEXT,
                    source TEXT,
                    score REAL,
                    frequency INTEGER
                )
                """
            )
        conn.close()

    def upsert_subreddits(self, records: Iterable[SubredditRecord]) -> None:
        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        with conn:
            for record in records:
                conn.execute(
                    """
                    INSERT INTO subreddits (name, nsfw, subscribers, active_users, created_utc, botbouncer_mod, discovered_at, last_seen_at, source, score, frequency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        nsfw=excluded.nsfw,
                        subscribers=excluded.subscribers,
                        active_users=excluded.active_users,
                        created_utc=excluded.created_utc,
                        botbouncer_mod=excluded.botbouncer_mod,
                        last_seen_at=?,
                        source=excluded.source,
                        score=excluded.score,
                        frequency=subreddits.frequency + 1
                    """,
                    (
                        record.name,
                        int(record.nsfw),
                        record.subscribers,
                        record.active_users,
                        record.created_utc,
                        int(record.botbouncer_mod),
                        record.discovered_at or now,
                        record.last_seen_at or now,
                        record.source,
                        record.score,
                        record.frequency,
                        now,
                    ),
                )
        conn.close()

    def fetch_all(self, limit: Optional[int] = None) -> List[SubredditRecord]:
        conn = self._get_conn()
        cursor = conn.cursor()
        query = "SELECT name, nsfw, subscribers, active_users, created_utc, botbouncer_mod, discovered_at, last_seen_at, source, score, frequency FROM subreddits ORDER BY score DESC"
        if limit:
            query += " LIMIT ?"
            cursor.execute(query, (limit,))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: tuple) -> SubredditRecord:
        return SubredditRecord(
            name=row[0],
            nsfw=bool(row[1]),
            subscribers=row[2] or 0,
            active_users=row[3] or 0,
            created_utc=row[4] or 0.0,
            botbouncer_mod=bool(row[5]),
            discovered_at=row[6],
            last_seen_at=row[7],
            source=row[8],
            score=row[9] or 0.0,
            frequency=row[10] or 0,
        )
