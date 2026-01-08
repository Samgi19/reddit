from __future__ import annotations

import json
from typing import Iterable, Optional

import requests


class TelegramClient:
    def __init__(self, bot_token: str, admin_ids: list[str] | None = None, channel_id: str | None = None):
        self.bot_token = bot_token
        self.admin_ids = admin_ids or []
        self.channel_id = channel_id or ""

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_message(self, chat_id: str, text: str) -> bool:
        if not self.bot_token or not chat_id:
            return False
        resp = requests.post(self._api_url("sendMessage"), json={"chat_id": chat_id, "text": text})
        return resp.ok

    def broadcast(self, text: str, to_channel: bool = False) -> bool:
        targets: list[str] = []
        if to_channel and self.channel_id:
            targets.append(self.channel_id)
        targets.extend(self.admin_ids)
        success = True
        for chat_id in targets:
            success = self.send_message(chat_id, text) and success
        return success

    def send_document(self, chat_id: str, file_path: str, caption: Optional[str] = None) -> bool:
        if not self.bot_token or not chat_id:
            return False
        with open(file_path, "rb") as f:
            resp = requests.post(
                self._api_url("sendDocument"),
                data={"chat_id": chat_id, "caption": caption or ""},
                files={"document": f},
            )
        return resp.ok

    def send_results(self, summary: str, files: Iterable[str], to_channel: bool = False) -> bool:
        success = self.broadcast(summary, to_channel=to_channel)
        targets: list[str] = []
        if to_channel and self.channel_id:
            targets.append(self.channel_id)
        targets.extend(self.admin_ids)
        for chat_id in targets:
            for path in files:
                success = self.send_document(chat_id, path) and success
        return success

    def test(self) -> bool:
        return self.broadcast("Telegram notifications are configured", to_channel=False)

    @staticmethod
    def format_results(results: list[dict], limit: int = 10) -> str:
        preview = results[:limit]
        lines = ["Top discovered subreddits:"]
        for idx, row in enumerate(preview, start=1):
            lines.append(
                f"{idx}. {row['name']} — score {row['score']:.2f}, subs {row['subscribers']}, active {row['active_users']}"
            )
        if len(results) > limit:
            lines.append(f"…and {len(results) - limit} more")
        return "\n".join(lines)

    @staticmethod
    def format_json(results: list[dict]) -> str:
        return json.dumps(results, indent=2)
