import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import aiohttp
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "8767998937"))
API_URL = os.getenv(
    "API_URL",
    "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json",
).strip()
POLL_SECONDS = max(2, int(os.getenv("POLL_SECONDS", "3")))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot1")

SET_NUMBER, SET_TEXT = range(2)

DEFAULT_MESSAGES = {
    "0": "BET ON ➡️ 0️⃣ NUMBER ALL WALLET",
    "1": "BET ON ➡️ 1️⃣ NUMBER ALL WALLET",
    "2": "BET ON ➡️ 2️⃣ NUMBER ALL WALLET",
    "3": "BET ON ➡️ 3️⃣ NUMBER ALL WALLET",
    "4": "BET ON ➡️ 4️⃣ NUMBER ALL WALLET",
    "5": "BET ON ➡️ 5️⃣ NUMBER ALL WALLET",
    "6": "BET ON ➡️ 6️⃣ NUMBER ALL WALLET",
    "7": "BET ON ➡️ 7️⃣ NUMBER ALL WALLET",
    "8": "BET ON ➡️ 8️⃣ NUMBER ALL WALLET",
    "9": "BET ON ➡️ 9️⃣ NUMBER ALL WALLET",
}


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"messages": DEFAULT_MESSAGES.copy(), "active": False, "last_issue": None, "last_number": None}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        log.exception("Could not read data.json; using defaults")
        data = {}
    data.setdefault("messages", DEFAULT_MESSAGES.copy())
    for n, text in DEFAULT_MESSAGES.items():
        data["messages"].setdefault(n, text)
    data.setdefault("active", False)
    data.setdefault("last_issue", None)
    data.setdefault("last_number", None)
    return data


def save_data(data: dict) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


async def deny(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("⛔ Admin only.")


def find_value(obj: Any, keys: set[str]) -> Optional[Any]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in keys and v not in (None, ""):
                return v
        for v in obj.values():
            found = find_value(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_value(item, keys)
            if found is not None:
                return found
    return None


def normalize_issue(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    return digits or s


def normalize_number(value: Any) -> Optional[int]:
    if value is None:
        return None
    m = re.search(r"(?<!\d)([0-9])(?!\d)", str(value))
    return int(m.group(1)) if m else None


def parse_api(payload: Any) -> tuple[Optional[str], Optional[int]]:
    issue = find_value(payload, {"issuenumber", "issue", "period", "periodno", "periodnumber"})
    number = find_value(payload, {"number", "result", "resultnumber", "winresult"})
    return normalize_issue(issue), normalize_number(number)


async def fetch_latest() -> tuple[Optional[str], Optional[int], Optional[str]]:
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "Mozilla/5.0 Bot1/1.0"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(API_URL) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return None, None, f"HTTP {resp.status}: {text[:200]}"
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    return None, None, "API did not return JSON"
                issue, number = parse_api(payload)
                if issue is None or number is None:
                    return issue, number, "Could not detect period/number from API response"
                return issue, number, None
    except Exception as exc:
        return None, None, f"API error: {exc}"


def period_last3(issue: str) -> str:
    digits = re.sub(r"\D", "", issue)
    if len(digits) >= 3:
        return digits[-3:]
    return issue[-3:]


async def send_test_layout(bot, chat_id: int, data: dict) -> dict:
    header = (
        "🚨 <b>DM WIN GAME</b> 🚨\n\n"
        "🔝 <b>WINGO 1 MIN</b> 🔝\n\n"
        "<b>PERIOD NO</b> ➡️ <code>---</code>\n\n"
        "<b>ONLY ALL WALLET BET</b> 📶"
    )
    sent = await bot.send_message(chat_id, header, parse_mode=ParseMode.HTML)
    data["header_message_id"] = sent.message_id
    data["number_message_ids"] = {}
    for n in range(10):
        msg = await bot.send_message(chat_id, data["messages"][str(n)])
        data["number_message_ids"][str(n)] = msg.message_id
        await asyncio.sleep(0.08)
    return data


async def update_header(bot, chat_id: int, data: dict, issue: str) -> None:
    mid = data.get("header_message_id")
    text = (
        "🚨 <b>DM WIN GAME</b> 🚨\n\n"
        "🔝 <b>WINGO 1 MIN</b> 🔝\n\n"
        f"<b>PERIOD NO</b> ➡️ <code>{period_last3(issue)}</code>\n\n"
        "<b>ONLY ALL WALLET BET</b> 📶"
    )
    try:
        if mid:
            await bot.edit_message_text(chat_id=chat_id, message_id=mid, text=text, parse_mode=ParseMode.HTML)
        else:
            sent = await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            data["header_message_id"] = sent.message_id
    except Exception as exc:
        log.warning("Header update failed: %s", exc)


async def delete_number_message(bot, chat_id: int, data: dict, number: int) -> bool:
    ids = data.setdefault("number_message_ids", {})
    mid = ids.get(str(number))
    if not mid:
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=mid)
        ids.pop(str(number), None)
        return True
    except Exception as exc:
        log.warning("Delete number %s failed: %s", number, exc)
        return False


async def poll_loop(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data.get("active"):
        return
    chat_id = data.get("chat_id")
    if not chat_id:
        return

    issue, number, error = await fetch_latest()
    if error:
        log.warning(error)
        return
    if not issue or number is None:
        return

    previous_issue = data.get("last_issue")
    if previous_issue == issue:
        return

    # A new API record is visible. Update the period and remove ONLY its number message.
    await update_header(context.bot, chat_id, data, issue)
    deleted = await delete_number_message(context.bot, chat_id, data, number)
    data["last_issue"] = issue
    data["last_number"] = number
    data["last_action"] = f"period={issue}, number={number}, deleted={deleted}"
    save_data(data)
    log.info("New issue=%s number=%s deleted_message=%s", issue, number, deleted)


async def go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    chat_id = update.effective_chat.id
    data = load_data()
    data["active"] = True
    data["chat_id"] = chat_id
    data["last_issue"] = None
    data["last_number"] = None
    data = await send_test_layout(context.bot, chat_id, data)
    save_data(data)
    await update.effective_message.reply_text("✅ Bot 1 started. API polling is active.")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    data = load_data()
    data["active"] = False
    save_data(data)
    await update.effective_message.reply_text("🛑 Bot 1 stopped.")


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    data = load_data()
    chat_id = update.effective_chat.id
    ids = []
    if data.get("header_message_id"):
        ids.append(data["header_message_id"])
    ids += list(data.get("number_message_ids", {}).values())
    deleted = 0
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id, mid)
            deleted += 1
        except Exception:
            pass
    data["header_message_id"] = None
    data["number_message_ids"] = {}
    save_data(data)
    await update.effective_message.reply_text(f"🧹 Cleared {deleted} managed messages.")


async def change_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    name = " ".join(context.args).strip()
    if not name:
        return await update.effective_message.reply_text("Use: /changename New Bot Name")
    try:
        await context.bot.set_my_name(name=name)
        await update.effective_message.reply_text(f"✅ Bot name changed to: {name}")
    except Exception as exc:
        await update.effective_message.reply_text(f"❌ Could not change bot name: {exc}")


async def set_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await deny(update)
        return ConversationHandler.END
    if context.args and len(context.args) >= 1 and context.args[0].isdigit() and 0 <= int(context.args[0]) <= 9:
        context.user_data["set_number"] = int(context.args[0])
        await update.effective_message.reply_text(
            f"✏️ Number {context.args[0]} selected. Now send the exact message (emoji/formatting included)."
        )
        return SET_TEXT
    await update.effective_message.reply_text("Send the number to edit (0-9):")
    return SET_NUMBER


async def set_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await deny(update)
        return ConversationHandler.END
    text = (update.effective_message.text or "").strip()
    if not text.isdigit() or not 0 <= int(text) <= 9:
        await update.effective_message.reply_text("❌ Enter only one number from 0 to 9.")
        return SET_NUMBER
    context.user_data["set_number"] = int(text)
    await update.effective_message.reply_text("✏️ Now send the exact message, including emojis and formatting.")
    return SET_TEXT


async def set_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update):
        await deny(update)
        return ConversationHandler.END
    n = context.user_data.get("set_number")
    if n is None:
        return ConversationHandler.END
    text = update.effective_message.text or update.effective_message.caption or ""
    if not text.strip():
        await update.effective_message.reply_text("❌ Empty message is not allowed. Send the message again.")
        return SET_TEXT
    data = load_data()
    data["messages"][str(n)] = text
    save_data(data)
    await update.effective_message.reply_text(f"✅ Message for number {n} saved.")
    return ConversationHandler.END


async def cancel_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("set_number", None)
    await update.effective_message.reply_text("❎ Cancelled.")
    return ConversationHandler.END


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update):
        return await deny(update)
    data = load_data()
    await update.effective_message.reply_text(
        "📊 <b>Bot 1 Status</b>\n"
        f"Running: <b>{data.get('active')}</b>\n"
        f"Last period: <code>{data.get('last_issue') or '-'}</code>\n"
        f"Last number: <b>{data.get('last_number') if data.get('last_number') is not None else '-'}</b>\n"
        f"Poll: <b>{POLL_SECONDS}s</b>",
        parse_mode=ParseMode.HTML,
    )


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("go", "Start Bot 1"),
        BotCommand("stop", "Stop Bot 1"),
        BotCommand("changename", "Change bot display name"),
        BotCommand("Clearchat", "Clear managed messages"),
        BotCommand("setmessage", "Set a 0-9 message"),
        BotCommand("status", "Show status"),
    ])
    app.job_queue.run_repeating(poll_loop, interval=POLL_SECONDS, first=1, name="api-poller")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    set_conv = ConversationHandler(
        entry_points=[CommandHandler("setmessage", set_message_start)],
        states={
            SET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_number)],
            SET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_set)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("go", go))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("changename", change_name))
    app.add_handler(CommandHandler("Clearchat", clear_chat))
    app.add_handler(set_conv)
    app.add_handler(CommandHandler("status", status))

    log.info("Bot 1 starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
