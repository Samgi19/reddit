from __future__ import annotations

import sys
from datetime import datetime
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, ConfigManager
from .database import DatabaseManager
from .reddit_client import RedditClient
from .search import SearchParams, SearchWorker
from .telegram_client import TelegramClient


class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, db: DatabaseManager):
        super().__init__()
        self.config_manager = config_manager
        self.config = config_manager.load()
        self.db = db
        self.search_worker: SearchWorker | None = None
        self.setWindowTitle("Reddit Discovery Tool")
        self.resize(1100, 760)
        self._init_clients()
        self._build_ui()
        self._load_database()

    def _init_clients(self):
        self.reddit_client = RedditClient(
            client_id=self.config.reddit.client_id,
            client_secret=self.config.reddit.client_secret,
            username=self.config.reddit.username,
            password=self.config.reddit.password,
            user_agent=self.config.reddit.user_agent,
            filters=self.config.filters,
            weights=self.config.weights,
            rate_limit=self.config.rate_limit,
        )
        self.telegram_client = TelegramClient(
            bot_token=self.config.telegram.bot_token,
            admin_ids=self.config.telegram.admin_ids,
            channel_id=self.config.telegram.channel_id,
        )

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_settings_tab(), "Settings")
        tabs.addTab(self._build_search_tab(), "Search")
        tabs.addTab(self._build_results_tab(), "Results")
        tabs.addTab(self._build_database_tab(), "Database")
        self.setCentralWidget(tabs)

    # Settings
    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(self._settings_group())
        layout.addWidget(self._filters_group())
        layout.addWidget(self._test_buttons())

        widget.setLayout(layout)
        return widget

    def _settings_group(self) -> QWidget:
        group = QGroupBox("API keys")
        form = QFormLayout()

        self.client_id_input = QLineEdit(self.config.reddit.client_id)
        self.client_secret_input = QLineEdit(self.config.reddit.client_secret)
        self.username_input = QLineEdit(self.config.reddit.username)
        self.password_input = QLineEdit(self.config.reddit.password)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ua_input = QLineEdit(self.config.reddit.user_agent)

        self.bot_token_input = QLineEdit(self.config.telegram.bot_token)
        self.admin_ids_input = QLineEdit(",".join(self.config.telegram.admin_ids))
        self.channel_id_input = QLineEdit(self.config.telegram.channel_id)
        self.channel_checkbox = QCheckBox("Send to channel by default")
        self.channel_checkbox.setChecked(self.config.telegram.send_to_channel)

        form.addRow("CLIENT_ID", self.client_id_input)
        form.addRow("CLIENT_SECRET", self.client_secret_input)
        form.addRow("USERNAME", self.username_input)
        form.addRow("PASSWORD", self.password_input)
        form.addRow("USER_AGENT", self.ua_input)
        form.addRow(QLabel("Telegram"))
        form.addRow("BOT_TOKEN", self.bot_token_input)
        form.addRow("ADMIN_IDS (comma)", self.admin_ids_input)
        form.addRow("CHANNEL_ID", self.channel_id_input)
        form.addRow(self.channel_checkbox)

        save_btn = QPushButton("Save")
        load_btn = QPushButton("Load")
        save_btn.clicked.connect(self.save_settings)
        load_btn.clicked.connect(self.reload_settings)
        row = QHBoxLayout()
        row.addWidget(save_btn)
        row.addWidget(load_btn)
        form.addRow(row)

        group.setLayout(form)
        return group

    def _filters_group(self) -> QWidget:
        group = QGroupBox("Filters")
        form = QGridLayout()
        self.nsfw_combo = QComboBox()
        self.nsfw_combo.addItems(["nsfw_only", "all", "exclude_nsfw"])
        self.nsfw_combo.setCurrentText(self.config.filters.nsfw_mode)

        self.karma_min = QSpinBox(); self.karma_min.setMaximum(1_000_000); self.karma_min.setValue(self.config.filters.karma_min)
        self.karma_max = QSpinBox(); self.karma_max.setMaximum(10_000_000); self.karma_max.setValue(self.config.filters.karma_max)
        self.age_min = QSpinBox(); self.age_min.setMaximum(10000); self.age_min.setValue(self.config.filters.account_age_min)
        self.age_max = QSpinBox(); self.age_max.setMaximum(10000); self.age_max.setValue(self.config.filters.account_age_max)
        self.subs_min = QSpinBox(); self.subs_min.setMaximum(10_000_000); self.subs_min.setValue(self.config.filters.subscribers_min)
        self.subs_max = QSpinBox(); self.subs_max.setMaximum(20_000_000); self.subs_max.setValue(self.config.filters.subscribers_max)
        self.active_min = QSpinBox(); self.active_min.setMaximum(1_000_000); self.active_min.setValue(self.config.filters.active_users_min)
        self.active_max = QSpinBox(); self.active_max.setMaximum(5_000_000); self.active_max.setValue(self.config.filters.active_users_max)

        form.addWidget(QLabel("NSFW mode"), 0, 0); form.addWidget(self.nsfw_combo, 0, 1)
        form.addWidget(QLabel("Karma min"), 1, 0); form.addWidget(self.karma_min, 1, 1)
        form.addWidget(QLabel("Karma max"), 1, 2); form.addWidget(self.karma_max, 1, 3)
        form.addWidget(QLabel("Account age min"), 2, 0); form.addWidget(self.age_min, 2, 1)
        form.addWidget(QLabel("Account age max"), 2, 2); form.addWidget(self.age_max, 2, 3)
        form.addWidget(QLabel("Subscribers min"), 3, 0); form.addWidget(self.subs_min, 3, 1)
        form.addWidget(QLabel("Subscribers max"), 3, 2); form.addWidget(self.subs_max, 3, 3)
        form.addWidget(QLabel("Active users min"), 4, 0); form.addWidget(self.active_min, 4, 1)
        form.addWidget(QLabel("Active users max"), 4, 2); form.addWidget(self.active_max, 4, 3)

        group.setLayout(form)
        return group

    def _test_buttons(self) -> QWidget:
        row = QHBoxLayout()
        reddit_btn = QPushButton("Test Reddit")
        telegram_btn = QPushButton("Test Telegram")
        reddit_btn.clicked.connect(self.test_reddit)
        telegram_btn.clicked.connect(self.test_telegram)
        row.addWidget(reddit_btn)
        row.addWidget(telegram_btn)
        container = QWidget()
        container.setLayout(row)
        return container

    # Search tab
    def _build_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox(); self.mode_combo.addItems(["Subreddit", "User", "Graph", "Keyword"])
        self.seed_input = QLineEdit("r/python")
        mode_row.addWidget(QLabel("Mode")); mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(QLabel("Seed")); mode_row.addWidget(self.seed_input)

        params_row = QGridLayout()
        self.depth_spin = QSpinBox(); self.depth_spin.setValue(self.config.search.graph_depth); self.depth_spin.setMaximum(5)
        self.posts_spin = QSpinBox(); self.posts_spin.setValue(self.config.search.default_posts_per_subreddit); self.posts_spin.setMaximum(100)
        self.comments_spin = QSpinBox(); self.comments_spin.setValue(self.config.search.default_comments_per_user); self.comments_spin.setMaximum(200)
        self.submissions_spin = QSpinBox(); self.submissions_spin.setValue(self.config.search.default_submissions_per_user); self.submissions_spin.setMaximum(200)
        self.per_depth_spin = QSpinBox(); self.per_depth_spin.setValue(self.config.search.per_depth_limit); self.per_depth_spin.setMaximum(100)
        self.notify_check = QCheckBox("Notify Telegram when finished")
        self.notify_check.setChecked(True)
        self.send_results_check = QCheckBox("Send results to Telegram")
        self.send_results_check.setChecked(True)

        params_row.addWidget(QLabel("Depth"), 0, 0); params_row.addWidget(self.depth_spin, 0, 1)
        params_row.addWidget(QLabel("Posts / subreddit"), 0, 2); params_row.addWidget(self.posts_spin, 0, 3)
        params_row.addWidget(QLabel("Comments / user"), 1, 0); params_row.addWidget(self.comments_spin, 1, 1)
        params_row.addWidget(QLabel("Submissions / user"), 1, 2); params_row.addWidget(self.submissions_spin, 1, 3)
        params_row.addWidget(QLabel("Per depth limit"), 2, 0); params_row.addWidget(self.per_depth_spin, 2, 1)
        params_row.addWidget(self.notify_check, 2, 2); params_row.addWidget(self.send_results_check, 2, 3)

        buttons_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.start_btn.clicked.connect(self.start_search)
        self.stop_btn.clicked.connect(self.stop_search)
        buttons_row.addWidget(self.start_btn)
        buttons_row.addWidget(self.stop_btn)

        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.setVisible(False)
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)

        layout.addLayout(mode_row)
        layout.addLayout(params_row)
        layout.addLayout(buttons_row)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_area)
        widget.setLayout(layout)
        return widget

    # Results tab
    def _build_results_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels([
            "Subreddit",
            "Score",
            "Subscribers",
            "Active users",
            "NSFW",
            "BotBouncer",
            "Source",
        ])

        export_row = QHBoxLayout()
        export_json = QPushButton("Export JSON")
        export_csv = QPushButton("Export CSV")
        export_json.clicked.connect(lambda: self._export_results("json"))
        export_csv.clicked.connect(lambda: self._export_results("csv"))
        export_row.addWidget(export_json)
        export_row.addWidget(export_csv)

        layout.addWidget(self.results_table)
        layout.addLayout(export_row)
        widget.setLayout(layout)
        return widget

    def _build_database_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()
        self.db_table = QTableWidget(0, 7)
        self.db_table.setHorizontalHeaderLabels([
            "Subreddit",
            "Score",
            "Subscribers",
            "Active users",
            "NSFW",
            "BotBouncer",
            "Frequency",
        ])
        layout.addWidget(self.db_table)
        widget.setLayout(layout)
        return widget

    # Settings handlers
    def save_settings(self):
        data = {
            "reddit": {
                "client_id": self.client_id_input.text(),
                "client_secret": self.client_secret_input.text(),
                "username": self.username_input.text(),
                "password": self.password_input.text(),
                "user_agent": self.ua_input.text(),
            },
            "telegram": {
                "bot_token": self.bot_token_input.text(),
                "admin_ids": [s.strip() for s in self.admin_ids_input.text().split(",") if s.strip()],
                "channel_id": self.channel_id_input.text(),
                "send_to_channel": self.channel_checkbox.isChecked(),
            },
            "filters": {
                "nsfw_mode": self.nsfw_combo.currentText(),
                "karma": {"min": self.karma_min.value(), "max": self.karma_max.value()},
                "account_age_days": {"min": self.age_min.value(), "max": self.age_max.value()},
                "subscribers": {"min": self.subs_min.value(), "max": self.subs_max.value()},
                "active_users": {"min": self.active_min.value(), "max": self.active_max.value()},
            },
        }
        self.config_manager.update_from_dict(data)
        self.config = self.config_manager.load()
        self._init_clients()
        QMessageBox.information(self, "Saved", "Configuration saved")

    def reload_settings(self):
        self.config = self.config_manager.load()
        self.client_id_input.setText(self.config.reddit.client_id)
        self.client_secret_input.setText(self.config.reddit.client_secret)
        self.username_input.setText(self.config.reddit.username)
        self.password_input.setText(self.config.reddit.password)
        self.ua_input.setText(self.config.reddit.user_agent)
        self.bot_token_input.setText(self.config.telegram.bot_token)
        self.admin_ids_input.setText(",".join(self.config.telegram.admin_ids))
        self.channel_id_input.setText(self.config.telegram.channel_id)
        self.channel_checkbox.setChecked(self.config.telegram.send_to_channel)
        self.nsfw_combo.setCurrentText(self.config.filters.nsfw_mode)

    def test_reddit(self):
        ok = self.reddit_client.test()
        QMessageBox.information(self, "Reddit", "OK" if ok else "Failed")

    def test_telegram(self):
        ok = self.telegram_client.test()
        QMessageBox.information(self, "Telegram", "OK" if ok else "Failed")

    # Search handlers
    def start_search(self):
        if self.search_worker and self.search_worker.is_alive():
            QMessageBox.warning(self, "Search", "Search already running")
            return
        params = SearchParams(
            mode=self.mode_combo.currentText(),
            seed=self.seed_input.text().replace("r/", "").replace("u/", ""),
            depth=self.depth_spin.value(),
            posts_per_subreddit=self.posts_spin.value(),
            comments_per_user=self.comments_spin.value(),
            submissions_per_user=self.submissions_spin.value(),
            per_depth_limit=self.per_depth_spin.value(),
            notify=self.notify_check.isChecked(),
            send_results=self.send_results_check.isChecked(),
        )
        self.progress.setVisible(True)
        self.log_area.append(f"[{datetime.utcnow().isoformat()}] Starting {params.mode} search")
        self.search_worker = SearchWorker(
            config=self.config,
            reddit_client=self.reddit_client,
            telegram_client=self.telegram_client,
            db=self.db,
            params=params,
            on_progress=self._log,
            on_finished=self._render_results,
        )
        self.search_worker.start()

    def stop_search(self):
        if self.search_worker:
            self.search_worker.stop()
            self.log_area.append("Stop requested")
        self.progress.setVisible(False)

    def _log(self, message: str):
        self.log_area.append(f"[{datetime.utcnow().isoformat()}] {message}")

    def _render_results(self, results: List[dict]):
        self.progress.setVisible(False)
        self.results_table.setRowCount(0)
        for row_data in results:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            values = [
                row_data.get("name"),
                f"{row_data.get('score', 0):.2f}",
                str(row_data.get("subscribers", 0)),
                str(row_data.get("active_users", 0)),
                "Yes" if row_data.get("nsfw") else "No",
                "✅" if row_data.get("botbouncer_mod") else "",
                row_data.get("source", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 5 and row_data.get("botbouncer_mod"):
                    item.setBackground(QColor("#c0ffc0"))
                self.results_table.setItem(row, col, item)
        self._load_database()

    def _load_database(self):
        records = self.db.fetch_all()
        self.db_table.setRowCount(0)
        for rec in records:
            row = self.db_table.rowCount()
            self.db_table.insertRow(row)
            values = [
                rec.name,
                f"{rec.score:.2f}",
                str(rec.subscribers),
                str(rec.active_users),
                "Yes" if rec.nsfw else "No",
                "✅" if rec.botbouncer_mod else "",
                str(rec.frequency),
            ]
            for col, value in enumerate(values):
                self.db_table.setItem(row, col, QTableWidgetItem(value))

    def _export_results(self, fmt: str):
        results = []
        for row in range(self.results_table.rowCount()):
            results.append(
                {
                    "name": self.results_table.item(row, 0).text(),
                    "score": self.results_table.item(row, 1).text(),
                    "subscribers": self.results_table.item(row, 2).text(),
                    "active_users": self.results_table.item(row, 3).text(),
                    "nsfw": self.results_table.item(row, 4).text(),
                    "botbouncer_mod": self.results_table.item(row, 5).text(),
                    "source": self.results_table.item(row, 6).text(),
                }
            )
        from .config import ensure_results_dir

        ensure_results_dir()
        path = ensure_results_dir() / f"manual_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{fmt}"
        if fmt == "json":
            import json

            with open(path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        else:
            import csv

            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader(); writer.writerows(results)
        QMessageBox.information(self, "Export", f"Saved to {path}")


def run_app():
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    db = DatabaseManager()
    window = MainWindow(config_manager, db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
