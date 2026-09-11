# Bot 1 Test — Render

This is the first test bot only.

## Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`python bot.py`

Environment variables:
- `BOT_TOKEN` = your BotFather token
- `ADMIN_ID` = `8767998937`
- `API_URL` = `https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json`
- `POLL_SECONDS` = `3`

## Commands
- `/go` — starts the managed message layout and API polling
- `/stop` — stops API actions
- `/clearchat` — deletes only messages managed by this bot
- `/changename New Name` — changes bot name
- `/setmessage` — select 0–9 and send the exact text/emoji message
- `/status` — status
- `/cancel` — cancel message editing

Note: Telegram command names are normally lowercase, so use `/clearchat` rather than `/Clearchat`.

## Behavior
The bot reads the latest API record. It extracts the issue/period and number (0–9), updates the period's last 3 digits in the header, and deletes only the saved message belonging to that number. It does not delete the other 0–9 messages.

The bot uses an explicit async Telegram lifecycle to avoid the `There is no current event loop in thread 'MainThread'` / `Updater.start_polling was never awaited` startup error.
