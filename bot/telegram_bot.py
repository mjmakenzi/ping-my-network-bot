import os
import threading
from network.monitor import traceroute  
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import asyncio

from network.monitor import (
    Diagnosis,
    classify,
    format_snapshot,
    latest_snapshot,
    start_monitor,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALERT_COOLDOWN = timedelta(minutes=5)

_muted_until: datetime | None = None
_last_diagnosis: Diagnosis | None = None
_last_alert_time: datetime | None = None
_default_chat_id: int | None = None


def launch_monitor_thread() -> None:
    thread = threading.Thread(target=start_monitor, daemon=True)
    thread.start()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _default_chat_id
    _default_chat_id = update.effective_chat.id
    print(f"DEBUG: /start command received, chat_id set to {_default_chat_id}")
    await update.message.reply_text("Monitoring started. I'll alert you on changes.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    snap = latest_snapshot()
    if not snap:
        await update.message.reply_text("No measurements yet. Please wait a few seconds.")
        return

    diagnosis = classify(snap)
    message = (
        "**Network Status**\n"
        f"{format_snapshot(snap)}\n"
        f"Diagnosis: {diagnosis.value}"
    )
    await update.message.reply_text(message, parse_mode="Markdown")


async def set_target_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /set_target <ip_or_host>")
        return

    new_target = context.args[0]
    os.environ["TARGET_IP"] = new_target
    await update.message.reply_text(f"Target updated to {new_target}.\n"
                                    "Next cycle will use the new address.")


async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _muted_until
    _muted_until = datetime.utcnow() + timedelta(hours=1)
    await update.message.reply_text("Alerts muted for 1 hour.")


async def health_loop(app: Application) -> None:
    global _last_diagnosis, _last_alert_time

    print("DEBUG: health_loop started")
    while True:
        await app.bot.initialize()  # no-op after first call, keeps loop happy
        snap = latest_snapshot()
        if not snap:
            print("DEBUG: No snapshot yet, waiting...")
            await asyncio.sleep(5)
            continue

        diagnosis = classify(snap)
        print(f"DEBUG: Current diagnosis={diagnosis.value}, Last={_last_diagnosis}")
        
        # Send alert if diagnosis changed OR if this is the first check
        if diagnosis != _last_diagnosis or _last_diagnosis is None:
            print(f"DEBUG: Diagnosis changed or first run! Calling maybe_alert...")
            await maybe_alert(app, snap, diagnosis)
        else:
            print("DEBUG: Diagnosis unchanged, skipping alert")

        _last_diagnosis = diagnosis
        await asyncio.sleep(5)


async def maybe_alert(app: Application, snap, diagnosis: Diagnosis) -> None:
    global _last_alert_time

    print(f"DEBUG: maybe_alert called, chat_id={_default_chat_id}, diagnosis={diagnosis.value}")
    
    if _default_chat_id is None:
        print("DEBUG: No chat_id set! User must call /start command in Telegram")
        return

    if _muted_until and datetime.utcnow() < _muted_until:
        print("DEBUG: Alerts are muted")
        return

    now = datetime.utcnow()
    if _last_alert_time and now - _last_alert_time < ALERT_COOLDOWN:
        print(f"DEBUG: In cooldown period (last alert was {now - _last_alert_time} ago)")
        return
    
    print("DEBUG: Sending alert to Telegram...")
    extra = ""
    if diagnosis in (Diagnosis.TARGET_DOWN, Diagnosis.ROUTING):
        print("DEBUG: Running traceroute...")
        trace = traceroute(snap.target.ip)
        extra = f"\n\n**Traceroute:**\n```\n{trace[:1500]}\n```"  # trim if needed

    message = (
        f"**⚠️ Network Alert: {diagnosis.value}**\n\n"
        f"{format_snapshot(snap)}"
        f"{extra}"
    )
    try:
        await app.bot.send_message(
            chat_id=_default_chat_id,
            text=message,
            parse_mode="Markdown",
        )
        print("DEBUG: Alert sent successfully!")
        _last_alert_time = now
    except Exception as e:
        print(f"DEBUG: Error sending alert: {e}")

def run_bot() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing in environment")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("set_target", set_target_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))

    async def on_startup(app: Application) -> None:
        app.create_task(health_loop(app))

    app.post_init = on_startup  # Set the hook BEFORE run_polling
    launch_monitor_thread()
    app.run_polling()
    