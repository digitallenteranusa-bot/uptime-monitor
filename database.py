import os
from datetime import datetime, timedelta, timezone

import aiosqlite

import config

# === Connection Pool ===
_pool: list[aiosqlite.Connection] = []
_pool_size = 5


async def get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    # Reuse idle connection from pool
    while _pool:
        db = _pool.pop()
        try:
            await db.execute("SELECT 1")
            return db
        except Exception:
            try:
                await db.close()
            except Exception:
                pass
    db = await aiosqlite.connect(config.DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def release_db(db: aiosqlite.Connection):
    if len(_pool) < _pool_size:
        _pool.append(db)
    else:
        await db.close()


async def close_pool():
    while _pool:
        db = _pool.pop()
        try:
            await db.close()
        except Exception:
            pass


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL DEFAULT 'ping',
                port INTEGER,
                interval INTEGER NOT NULL DEFAULT 60,
                status TEXT NOT NULL DEFAULT 'UNKNOWN',
                last_down_at TEXT
            );
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                latency REAL,
                downtime_duration REAL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (monitor_id) REFERENCES monitors(id)
            );
            CREATE INDEX IF NOT EXISTS idx_logs_monitor_ts
                ON logs(monitor_id, timestamp);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await db.commit()
    finally:
        await release_db(db)


async def seed_monitors():
    db = await get_db()
    try:
        for m in config.MONITORS:
            await db.execute(
                "INSERT OR IGNORE INTO monitors (name, target, type, interval) VALUES (?, ?, ?, ?)",
                (m["name"], m["target"], m.get("type", "ping"), m["interval"]),
            )
        await db.commit()
    finally:
        await release_db(db)


async def add_monitor(name: str, target: str, monitor_type: str = "ping",
                      port: int | None = None, interval: int = 60) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO monitors (name, target, type, port, interval) VALUES (?, ?, ?, ?, ?)",
            (name, target, monitor_type, port, interval),
        )
        await db.commit()
        monitor_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM monitors WHERE id=?", (monitor_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await release_db(db)


async def edit_monitor(monitor_id: int, name: str, target: str, monitor_type: str = "ping",
                       port: int | None = None, interval: int = 60) -> dict | None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE monitors SET name=?, target=?, type=?, port=?, interval=? WHERE id=?",
            (name, target, monitor_type, port, interval, monitor_id),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM monitors WHERE id=?", (monitor_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await release_db(db)


async def delete_monitor(monitor_id: int) -> bool:
    db = await get_db()
    try:
        await db.execute("DELETE FROM logs WHERE monitor_id=?", (monitor_id,))
        cursor = await db.execute("DELETE FROM monitors WHERE id=?", (monitor_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await release_db(db)


async def get_monitors() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM monitors")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await release_db(db)


async def get_monitor(monitor_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM monitors WHERE id=?", (monitor_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await release_db(db)


async def update_monitor_status(monitor_id: int, status: str, last_down_at: str | None = None):
    db = await get_db()
    try:
        if last_down_at is not None:
            await db.execute(
                "UPDATE monitors SET status=?, last_down_at=? WHERE id=?",
                (status, last_down_at, monitor_id),
            )
        else:
            await db.execute(
                "UPDATE monitors SET status=? WHERE id=?",
                (status, monitor_id),
            )
        await db.commit()
    finally:
        await release_db(db)


async def clear_last_down_at(monitor_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE monitors SET last_down_at=NULL WHERE id=?", (monitor_id,)
        )
        await db.commit()
    finally:
        await release_db(db)


async def add_log(monitor_id: int, status: str, latency: float | None, downtime_duration: float | None = None):
    db = await get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO logs (monitor_id, status, latency, downtime_duration, timestamp) VALUES (?, ?, ?, ?, ?)",
            (monitor_id, status, latency, downtime_duration, now),
        )
        await db.commit()
    finally:
        await release_db(db)


async def get_logs_24h(monitor_id: int) -> list[dict]:
    db = await get_db()
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cursor = await db.execute(
            "SELECT status, latency, timestamp FROM logs WHERE monitor_id=? AND timestamp>=? ORDER BY timestamp",
            (monitor_id, since),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await release_db(db)


async def get_logs_all(monitor_id: int, limit: int = 500) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT status, latency, downtime_duration, timestamp FROM logs "
            "WHERE monitor_id=? ORDER BY timestamp DESC LIMIT ?",
            (monitor_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        await release_db(db)


async def get_heartbeat_bar(monitor_id: int, slots: int = 90) -> list[dict]:
    """Get aggregated status data for the heartbeat bar (last 24h, divided into slots)."""
    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)
        slot_seconds = 86400 / slots  # 24h in seconds / slots

        cursor = await db.execute(
            "SELECT status, latency, timestamp FROM logs WHERE monitor_id=? AND timestamp>=? ORDER BY timestamp",
            (monitor_id, since.isoformat()),
        )
        rows = await cursor.fetchall()

        # Parse all log timestamps to epoch for reliable comparison
        parsed_logs = []
        for r in rows:
            row = dict(r)
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                row["_epoch"] = ts.timestamp()
            except (ValueError, TypeError):
                continue
            parsed_logs.append(row)

        since_epoch = since.timestamp()
        bar = []
        for i in range(slots):
            slot_start_epoch = since_epoch + (slot_seconds * i)
            slot_end_epoch = slot_start_epoch + slot_seconds
            slot_time = datetime.fromtimestamp(slot_start_epoch, tz=timezone.utc)

            slot_logs = [
                l for l in parsed_logs
                if slot_start_epoch <= l["_epoch"] < slot_end_epoch
            ]

            if not slot_logs:
                bar.append({"status": "none", "latency": None, "time": slot_time.strftime("%H:%M")})
            else:
                down_count = sum(1 for l in slot_logs if l["status"] == "DOWN")
                up_count = sum(1 for l in slot_logs if l["status"] == "UP")
                latencies = [l["latency"] for l in slot_logs if l["latency"] is not None]
                avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

                if down_count > 0 and up_count > 0:
                    status = "degraded"
                elif down_count > 0:
                    status = "down"
                else:
                    status = "up"

                bar.append({"status": status, "latency": avg_latency, "time": slot_time.strftime("%H:%M")})

        return bar
    finally:
        await release_db(db)


async def get_uptime_7d(monitor_id: int) -> float:
    db = await get_db()
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        cursor = await db.execute(
            "SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN status='UP' THEN 1 ELSE 0 END), 0) as up_count "
            "FROM logs WHERE monitor_id=? AND timestamp>=?",
            (monitor_id, since),
        )
        row = await cursor.fetchone()
        total = row["total"]
        if total == 0:
            return 100.0
        return round((row["up_count"] / total) * 100, 2)
    finally:
        await release_db(db)


async def get_monitor_stats(monitor_id: int) -> dict:
    """Statistik detail untuk halaman detail monitor."""
    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        stats = {}

        # Uptime 24h, 7d, 30d
        for label, days in [("uptime_24h", 1), ("uptime_7d", 7), ("uptime_30d", 30)]:
            since = (now - timedelta(days=days)).isoformat()
            cursor = await db.execute(
                "SELECT COUNT(*) as total, COALESCE(SUM(CASE WHEN status='UP' THEN 1 ELSE 0 END), 0) as up_count "
                "FROM logs WHERE monitor_id=? AND timestamp>=?",
                (monitor_id, since),
            )
            row = await cursor.fetchone()
            total = row["total"]
            stats[label] = round((row["up_count"] / total) * 100, 2) if total > 0 else 100.0

        # Average latency 24h
        since_24h = (now - timedelta(hours=24)).isoformat()
        cursor = await db.execute(
            "SELECT AVG(latency) as avg_latency, MIN(latency) as min_latency, MAX(latency) as max_latency "
            "FROM logs WHERE monitor_id=? AND timestamp>=? AND latency IS NOT NULL",
            (monitor_id, since_24h),
        )
        row = await cursor.fetchone()
        stats["avg_latency"] = round(row["avg_latency"], 2) if row["avg_latency"] else None
        stats["min_latency"] = round(row["min_latency"], 2) if row["min_latency"] else None
        stats["max_latency"] = round(row["max_latency"], 2) if row["max_latency"] else None

        # Total incidents (DOWN events) 7d
        since_7d = (now - timedelta(days=7)).isoformat()
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM logs WHERE monitor_id=? AND timestamp>=? AND downtime_duration IS NOT NULL",
            (monitor_id, since_7d),
        )
        row = await cursor.fetchone()
        stats["incidents_7d"] = row["cnt"]

        # Total checks
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM logs WHERE monitor_id=?", (monitor_id,))
        row = await cursor.fetchone()
        stats["total_checks"] = row["cnt"]

        return stats
    finally:
        await release_db(db)


async def cleanup_old_logs():
    """Hapus log lebih lama dari LOG_RETENTION_DAYS."""
    db = await get_db()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=config.LOG_RETENTION_DAYS)).isoformat()
        cursor = await db.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
        await db.commit()
        return cursor.rowcount
    finally:
        await release_db(db)


# === Settings (Telegram config from dashboard) ===

async def get_setting(key: str, default: str = "") -> str:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default
    finally:
        await release_db(db)


async def set_setting(key: str, value: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (key, value, value),
        )
        await db.commit()
    finally:
        await release_db(db)
