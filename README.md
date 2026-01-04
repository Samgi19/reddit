# Reddit Discovery GUI

PyQt6 desktop приложение для поиска тематических сабреддитов по активности пользователей Reddit с отправкой уведомлений в Telegram и регистрацией результатов в SQLite.

## Возможности
- Режимы поиска: Subreddit, User, Graph (BFS по соседним сабреддитам), Keyword.
- Фильтры: NSFW режим (по умолчанию `nsfw_only`), карма, возраст аккаунта, подписчики и активные пользователи.
- Подсветка сабреддитов с модератором **BotBouncer**.
- Экспорт CSV/JSON, уведомления в Telegram (админы и канал), опция отправки файлов.
- Кеширование и простая задержка при rate-limit, кнопки Stop/Cancel.

## Установка
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройка
1. Скопируйте `.env.example` в `.env` и заполните ключи Reddit/Telegram.
2. Отредактируйте `config.yaml` при необходимости (веса, лимиты, NSFW режим).
3. Все результаты сохраняются в `registry.db` и папке `results/`.

## Запуск
```bash
python -m src.gui
```

## Структура
```
.
├── .env.example
├── README.md
├── config.yaml
├── registry.db (создаётся автоматически)
├── requirements.txt
├── results/
└── src/
    ├── config.py
    ├── database.py
    ├── gui.py
    ├── main.py
    ├── reddit_client.py
    ├── search.py
    └── telegram_client.py
```

## Телеграм уведомления
- Чекбокс `Notify Telegram when finished` отправит уведомление.
- Чекбокс `Send results to Telegram` добавит краткий топ и файлы JSON/CSV.
- В настройках можно выбрать отправку в канал (`send_to_channel`) или только в личку администраторов.

## Параметры поиска
- **Graph**: BFS до `depth`, на каждом уровне берётся ограничение `per_depth_limit`.
- **Subreddit**: считывает N постов, затем активность авторов (комментарии/посты) и агрегирует сабреддиты.
- **User**: анализ активности пользователя по сабреддитам.
- **Keyword**: `reddit.subreddits.search(query)` с фильтрами.

## SQLite
Таблица `subreddits` обновляется через UPSERT с полями: `name, nsfw, subscribers, active_users, created_utc, botbouncer_mod, discovered_at, last_seen_at, source, score, frequency`.

## Требования
- Python 3.11+
- Доступ к Reddit API (PRAW) и Telegram Bot API.
