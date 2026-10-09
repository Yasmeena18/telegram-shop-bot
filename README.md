# NIVORA Shop Bot

A complete Telegram storefront bot for digital-service businesses — built in **pure Python (zero external libraries)** with SQLite.

## Features

- 🛒 Service catalog (4 categories / 13 services) with interactive inline buttons
- 📩 Full order flow: service → name → contact → project brief → order confirmation with number
- 💬 Smart inquiry mode with optional AI replies (Gemini) and safe static fallback
- 🔔 Instant owner notifications with a configurable delivery chain (WhatsApp desktop → Gmail → Telegram alerts bot)
- 🛠️ Owner admin commands: `/orders` `/stats` `/done` `/ban` `/unban` `/broadcast` `/ping`
- 🧠 Clean state machines for both order and inquiry flows — fully unit-testable
- 🛡️ Parameterized SQL, owner-only command gating, rate limiting, anti-spam bans, media receiving, order history
- 🔎 Free-text routing: client messages are matched to services, and catalog-intent phrases open the catalog directly

## Architecture

```
bot.py     # Telegram I/O + conversation engine
flow.py    # Pure order/inquiry state logic (testable, no I/O)
db.py      # SQLite data layer (catalog, orders, inquiries, bans)
ai.py      # Optional AI replies (Gemini) with safe fallback
tests/     # 25 unit tests
```

## Setup

```
1. Copy config.example.json → config.json
2. Fill: bot_token (from @BotFather) and owner_chat_id
3. (optional) ai_enabled: true + gemini_api_key
4. python bot.py
```

## Tests

```
python -m unittest discover -s tests
```

## Security

- `config.json` (tokens/keys) is git-ignored — a template is provided
- Parameterized SQL only; logs contain no sensitive data
- Admin commands restricted to the owner's chat_id
- Media files stored locally, never re-exposed

---

Built by **NIVORA** — professional digital services (automation, web, design, Notion systems).
