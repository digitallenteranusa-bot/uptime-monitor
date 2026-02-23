import asyncio
import logging
import platform
import re
import socket
from datetime import datetime, timezone

import aiohttp

import config
import database
import notifier

logger = logging.getLogger("monitor")


# ============================
# Check Methods
# ============================

async def check_ping(target: str) -> tuple[bool, float | None]:
    """Ping target via subprocess. Returns (success, latency_ms)."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", param, "1", "-W", "3", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = stdout.decode(errors="ignore")
        if proc.returncode == 0:
            match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output, re.IGNORECASE)
            latency = float(match.group(1)) if match else None
            return True, latency
        return False, None
    except (asyncio.TimeoutError, OSError):
        return False, None


async def check_http(target: str) -> tuple[bool, float | None]:
    """HTTP check - expects status 2xx/3xx. Returns (success, latency_ms)."""
    url = target if target.startswith("http") else f"http://{target}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        start = asyncio.get_event_loop().time()
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15),
                                   ssl=False, allow_redirects=True) as resp:
                latency = (asyncio.get_event_loop().time() - start) * 1000
                return 200 <= resp.status < 400, round(latency, 2)
    except Exception:
        return False, None


async def check_tcp(target: str, port: int) -> tuple[bool, float | None]:
    """TCP port check. Returns (success, latency_ms)."""
    try:
        start = asyncio.get_event_loop().time()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port), timeout=10
        )
        latency = (asyncio.get_event_loop().time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return True, round(latency, 2)
    except Exception:
        return False, None


async def check_dns(target: str) -> tuple[bool, float | None]:
    """DNS resolution check. Returns (success, latency_ms)."""
    loop = asyncio.get_event_loop()
    try:
        start = loop.time()
        await loop.getaddrinfo(target, None)
        latency = (loop.time() - start) * 1000
        return True, round(latency, 2)
    except socket.gaierror:
        return False, None


async def run_check(mon: dict) -> tuple[bool, float | None]:
    """Run the appropriate check based on monitor type."""
    mon_type = mon.get("type", "ping")
    target = mon["target"]

    if mon_type == "http":
        return await check_http(target)
    elif mon_type == "tcp":
        port = mon.get("port") or 80
        return await check_tcp(target, port)
    elif mon_type == "dns":
        return await check_dns(target)
    else:
        return await check_ping(target)


# ============================
# Retry Logic
# ============================

async def check_with_retry(mon: dict) -> tuple[bool, float | None]:
    """Check with retry logic. Only mark DOWN after all retries fail."""
    success, latency = await run_check(mon)
    if success:
        return True, latency

    for attempt in range(config.MAX_RETRIES):
        logger.info("Retry %d/%d for %s", attempt + 1, config.MAX_RETRIES, mon["target"])
        await asyncio.sleep(config.RETRY_DELAY)
        success, latency = await run_check(mon)
        if success:
            return True, latency

    return False, None


# ============================
# Monitor Cycle
# ============================

async def check_monitor(monitor: dict):
    """Single monitoring cycle for one target."""
    target = monitor["target"]
    monitor_id = monitor["id"]
    old_status = monitor["status"]

    success, latency = await check_with_retry(monitor)
    new_status = "UP" if success else "DOWN"
    now = datetime.now(timezone.utc)

    downtime_duration = None

    if old_status != new_status:
        if new_status == "DOWN":
            await database.update_monitor_status(monitor_id, "DOWN", now.isoformat())
            logger.warning("%s (%s) is DOWN", monitor["name"], target)
        else:
            if monitor["last_down_at"]:
                down_since = datetime.fromisoformat(monitor["last_down_at"])
                downtime_duration = (now - down_since).total_seconds()
            await database.update_monitor_status(monitor_id, "UP")
            await database.clear_last_down_at(monitor_id)
            logger.info("%s (%s) is UP (downtime: %ss)", monitor["name"], target, downtime_duration)

        await notifier.send_status_change(monitor, new_status, downtime_duration)
    elif old_status == "UNKNOWN":
        await database.update_monitor_status(monitor_id, new_status)

    await database.add_log(monitor_id, new_status, latency, downtime_duration)


async def monitor_loop(monitor: dict):
    """Continuous monitoring loop for a single target."""
    interval = monitor.get("interval", 60)
    while True:
        try:
            monitors = await database.get_monitors()
            current = next((m for m in monitors if m["id"] == monitor["id"]), None)
            if current is None:
                logger.info("Monitor %d no longer exists, stopping loop", monitor["id"])
                return
            await check_monitor(current)
        except Exception:
            logger.exception("Error checking %s", monitor["name"])
        await asyncio.sleep(interval)


# ============================
# Cleanup Scheduler
# ============================

async def cleanup_loop():
    """Periodically clean up old logs."""
    while True:
        try:
            deleted = await database.cleanup_old_logs()
            if deleted:
                logger.info("Cleaned up %d old log entries", deleted)
        except Exception:
            logger.exception("Error during log cleanup")
        await asyncio.sleep(3600)  # Cek setiap 1 jam


# ============================
# Task Management
# ============================

_active_tasks: dict[int, asyncio.Task] = {}


def start_monitor_task(mon: dict):
    mid = mon["id"]
    if mid in _active_tasks and not _active_tasks[mid].done():
        return
    _active_tasks[mid] = asyncio.create_task(monitor_loop(mon))
    logger.info("Started monitoring task for %s (%s) [%s]", mon["name"], mon["target"], mon.get("type", "ping"))


def stop_monitor_task(monitor_id: int):
    task = _active_tasks.pop(monitor_id, None)
    if task and not task.done():
        task.cancel()
        logger.info("Stopped monitoring task for monitor_id=%d", monitor_id)


def stop_all_tasks():
    """Cancel all active monitoring tasks (used during shutdown)."""
    for mid, task in _active_tasks.items():
        if not task.done():
            task.cancel()
    _active_tasks.clear()
    logger.info("All monitoring tasks cancelled")


def restart_monitor_task(mon: dict):
    """Stop and restart monitoring task (used after edit)."""
    stop_monitor_task(mon["id"])
    start_monitor_task(mon)


async def start_all_monitors():
    await database.init_db()
    await database.seed_monitors()

    monitors = await database.get_monitors()
    logger.info("Starting monitoring for %d targets", len(monitors))

    for m in monitors:
        start_monitor_task(m)

    # Start cleanup scheduler
    asyncio.create_task(cleanup_loop())

    while True:
        await asyncio.sleep(3600)
