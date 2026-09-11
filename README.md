# Bot 1 — Render test

## Render setup
1. Upload this folder/repository to GitHub or deploy the ZIP contents to Render.
2. Create a **Background Worker** on Render.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python bot.py`
5. Add environment variable `BOT_TOKEN` with your BotFather token.
6. `ADMIN_ID`, `API_URL`, and `POLL_SECONDS` are already configured in `render.yaml`.

## Commands
- `/go` — starts the test layout and API polling.
- `/stop` — stops polling.
- `/setmessage` — choose 0–9 and then send the exact text. Emoji and Unicode are supported.
- `/setmessage 5` — shortcut to edit number 5.
- `/Clearchat` — deletes messages managed by this bot.
- `/changename New Name` — changes the bot's Telegram display name (not the @username).
- `/status` — shows current state.

## Current test behavior
The bot posts the header plus messages 0–9. It polls the supplied API. When a **new period/issue** is detected, it updates the header to the **last 3 digits** of the period and deletes **only the message belonging to the API's result number**. Other number messages are left untouched.

The API parser accepts common fields such as `issueNumber`, `issue`, `period`, `periodNumber` and result fields such as `number`/`result`. If the actual API JSON uses different field names, update `parse_api()` after seeing one real response.

## Important
Never put the BotFather token directly into source code or GitHub. Use Render's Environment Variables.
