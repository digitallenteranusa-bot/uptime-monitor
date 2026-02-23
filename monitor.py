import asyncio
import logging
import platform
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import ssl as _ssl

import aiohttp

import config
import database
import notifier

logger = logging.getLogger("monitor")

# ============================
# Shared HTTP Session
# ============================

_http_session: aiohttp.ClientSession | None = None

# SSL context yang skip verifikasi sertifikat
_ssl_ctx = _ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = _ssl.CERT_NONE


async def get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(
            limit=30,
            ttl_dns_cache=300,
            keepalive_timeout=60,
            ssl=_ssl_ctx,
        )
        _http_session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=15),
        )
    return _http_session


async def close_http_session():
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        _http_session = None


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
    """HTTP check. Latency = TCP connect time (network RTT murni, seperti ping)."""
    url = target if target.startswith("http") else f"http://{target}"
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # 1) Latency: TCP connect only (SYN→SYN-ACK = network RTT, sama seperti ping)
    latency = None
    try:
        start = asyncio.get_event_loop().time()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port), timeout=10
        )
        latency = round((asyncio.get_event_loop().time() - start) * 1000, 2)
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

    # 2) UP/DOWN: HTTP status check
    try:
        session = await get_http_session()
        async with session.get(url, allow_redirects=True, ssl=_ssl_ctx) as resp:
            return resp.status < 500, latency
    except Exception as e:
        logger.debug("HTTP check failed for %s: %s", target, e)
        return False, latency


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
    asyncio.ensure_future(close_http_session())
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
