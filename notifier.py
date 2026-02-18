import logging
import time
from datetime import datetime, timezone

import aiohttp

import config
import database

logger = logging.getLogger("notifier")

# Alert cooldown tracker: {monitor_id: last_alert_timestamp}
_last_alert: dict[int, float] = {}


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f} detik"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f} menit"
    hours = minutes / 60
    return f"{hours:.1f} jam"


async def _get_telegram_credentials() -> tuple[str, str]:
    """Get Telegram credentials - DB settings override env vars."""
    token = await database.get_setting("telegram_bot_token", config.TELEGRAM_BOT_TOKEN)
    chat_id = await database.get_setting("telegram_chat_id", config.TELEGRAM_CHAT_ID)
    return token, chat_id


async def send_telegram(message: str):
    token, chat_id = await _get_telegram_credentials()

    if not token or not chat_id:
        logger.warning("Telegram not configured, skipping notification")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Telegram API error %d: %s", resp.status, body)
                else:
                    logger.info("Telegram notification sent")
    except Exception:
        logger.exception("Failed to send Telegram notification")


async def send_status_change(monitor: dict, new_status: str, downtime_duration: float | None = None):
    monitor_id = monitor["id"]

    # Alert cooldown check
    now = time.time()
    last = _last_alert.get(monitor_id, 0)
    if now - last < config.ALERT_COOLDOWN:
        logger.info("Alert cooldown active for %s, skipping notification", monitor["name"])
        return
    _last_alert[monitor_id] = now

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    name = monitor["name"]
    target = monitor["target"]
    mon_type = monitor.get("type", "ping").upper()

    if new_status == "DOWN":
        message = (
            f"\u26a0\ufe0f <b>MONITOR DOWN</b>\n\n"
            f"<b>Target:</b> {name}\n"
            f"<b>Alamat:</b> {target}\n"
            f"<b>Tipe:</b> {mon_type}\n"
            f"<b>Status:</b> DOWN\n"
            f"<b>Waktu:</b> {now_str}"
        )
    else:
        duration_str = _format_duration(downtime_duration)
        message = (
            f"\u2705 <b>MONITOR RECOVERED</b>\n\n"
            f"<b>Target:</b> {name}\n"
            f"<b>Alamat:</b> {target}\n"
            f"<b>Tipe:</b> {mon_type}\n"
            f"<b>Status:</b> UP\n"
            f"<b>Downtime:</b> {duration_str}\n"
            f"<b>Waktu:</b> {now_str}"
        )

    await send_telegram(message)
