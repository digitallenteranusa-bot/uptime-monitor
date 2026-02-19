import asyncio
import csv
import io
import json
import logging
import signal
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import RedirectResponse

import config
import database
import monitor
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("dashboard")

# === Session Store ===
_sessions: dict[str, str] = {}  # token -> username


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    await database.remove_monitor_by_target("192.168.1.1")
    await database.seed_monitors()
    task = asyncio.create_task(monitor.start_all_monitors())

    yield

    # Cleanup: cancel all monitor tasks + main task
    logger.info("Shutting down...")
    monitor.stop_all_tasks()
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=2)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    await database.close_pool()
    logger.info("Shutdown complete")


app = FastAPI(title="Uptime Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ============================
# Auth Helpers
# ============================

def verify_session(session_token: str | None = Cookie(None)):
    if session_token and session_token in _sessions:
        return _sessions[session_token]
    return None


def require_auth(session_token: str | None = Cookie(None)):
    user = verify_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# ============================
# Auth Pages
# ============================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


class LoginForm(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def api_login(data: LoginForm):
    if data.username == config.ADMIN_USERNAME and data.password == config.ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        _sessions[token] = data.username
        return {"ok": True, "token": token}
    return {"ok": False, "error": "Username atau password salah"}


@app.get("/logout")
async def logout(session_token: str | None = Cookie(None)):
    if session_token:
        _sessions.pop(session_token, None)
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session_token")
    return resp


# ============================
# Dashboard Pages (Protected)
# ============================

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, session_token: str | None = Cookie(None)):
    user = verify_session(session_token)
    if not user:
        return RedirectResponse("/login", status_code=302)

    monitors = await database.get_monitors()
    monitors_data = []
    for m in monitors:
        uptime = await database.get_uptime_7d(m["id"])
        monitors_data.append({**m, "uptime_7d": uptime})
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "monitors": monitors_data,
        "user": user,
    })


@app.get("/monitor/{monitor_id}", response_class=HTMLResponse)
async def monitor_detail_page(request: Request, monitor_id: int, session_token: str | None = Cookie(None)):
    user = verify_session(session_token)
    if not user:
        return RedirectResponse("/login", status_code=302)

    mon = await database.get_monitor(monitor_id)
    if not mon:
        raise HTTPException(status_code=404, detail="Monitor tidak ditemukan")

    stats = await database.get_monitor_stats(monitor_id)
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "monitor": mon,
        "stats": stats,
        "user": user,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session_token: str | None = Cookie(None)):
    user = verify_session(session_token)
    if not user:
        return RedirectResponse("/login", status_code=302)

    tg_token = await database.get_setting("telegram_bot_token", config.TELEGRAM_BOT_TOKEN)
    tg_chat = await database.get_setting("telegram_chat_id", config.TELEGRAM_CHAT_ID)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user,
        "tg_token": tg_token,
        "tg_chat": tg_chat,
        "cooldown": config.ALERT_COOLDOWN,
        "retention": config.LOG_RETENTION_DAYS,
    })


# ============================
# Public Status Page (No Auth)
# ============================

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    monitors = await database.get_monitors()
    monitors_data = []
    for m in monitors:
        uptime = await database.get_uptime_7d(m["id"])
        monitors_data.append({**m, "uptime_7d": uptime})
    return templates.TemplateResponse("status.html", {
        "request": request,
        "monitors": monitors_data,
    })


# ============================
# Public API (No Auth)
# ============================

@app.get("/api/public/heartbeat/{monitor_id}")
async def api_public_heartbeat(monitor_id: int):
    bar = await database.get_heartbeat_bar(monitor_id)
    return bar


# ============================
# Health Check (No Auth)
# ============================

@app.get("/health")
async def health_check():
    try:
        monitors = await database.get_monitors()
        return {
            "status": "healthy",
            "monitors_count": len(monitors),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return Response(
            content=json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=503,
            media_type="application/json",
        )


# ============================
# API Endpoints (Protected)
# ============================

@app.get("/api/monitors")
async def api_monitors(user: str = Depends(require_auth)):
    monitors = await database.get_monitors()
    result = []
    for m in monitors:
        uptime = await database.get_uptime_7d(m["id"])
        result.append({**m, "uptime_7d": uptime})
    return result


@app.get("/api/heartbeat/{monitor_id}")
async def api_heartbeat(monitor_id: int, user: str = Depends(require_auth)):
    bar = await database.get_heartbeat_bar(monitor_id)
    return bar


class MonitorCreate(BaseModel):
    name: str
    target: str
    type: str = "ping"
    port: int | None = None
    interval: int = 60


@app.post("/api/monitors")
async def api_add_monitor(data: MonitorCreate, user: str = Depends(require_auth)):
    if data.type not in ("ping", "http", "tcp", "dns"):
        return {"error": "Tipe tidak valid. Pilih: ping, http, tcp, dns"}
    try:
        mon = await database.add_monitor(data.name, data.target, data.type, data.port, data.interval)
    except Exception as e:
        if "UNIQUE" in str(e):
            return {"error": "Target sudah ada"}
        raise
    if mon:
        monitor.start_monitor_task(mon)
        return {"ok": True, "monitor": mon}
    return {"error": "Gagal menambahkan monitor"}


class MonitorEdit(BaseModel):
    name: str
    target: str
    type: str = "ping"
    port: int | None = None
    interval: int = 60


@app.put("/api/monitors/{monitor_id}")
async def api_edit_monitor(monitor_id: int, data: MonitorEdit, user: str = Depends(require_auth)):
    if data.type not in ("ping", "http", "tcp", "dns"):
        return {"error": "Tipe tidak valid. Pilih: ping, http, tcp, dns"}
    try:
        mon = await database.edit_monitor(monitor_id, data.name, data.target, data.type, data.port, data.interval)
    except Exception as e:
        if "UNIQUE" in str(e):
            return {"error": "Target sudah ada"}
        raise
    if mon:
        monitor.restart_monitor_task(mon)
        return {"ok": True, "monitor": mon}
    return {"error": "Monitor tidak ditemukan"}


@app.delete("/api/monitors/{monitor_id}")
async def api_delete_monitor(monitor_id: int, user: str = Depends(require_auth)):
    monitor.stop_monitor_task(monitor_id)
    deleted = await database.delete_monitor(monitor_id)
    if deleted:
        return {"ok": True}
    return {"error": "Monitor tidak ditemukan"}


@app.get("/api/logs/{monitor_id}")
async def api_logs(monitor_id: int, user: str = Depends(require_auth)):
    logs = await database.get_logs_24h(monitor_id)
    return logs


@app.get("/api/logs/{monitor_id}/all")
async def api_logs_all(monitor_id: int, user: str = Depends(require_auth)):
    logs = await database.get_logs_all(monitor_id)
    return logs


@app.get("/api/monitor/{monitor_id}/stats")
async def api_monitor_stats(monitor_id: int, user: str = Depends(require_auth)):
    stats = await database.get_monitor_stats(monitor_id)
    return stats


@app.get("/api/monitor/{monitor_id}/incidents")
async def api_monitor_incidents(monitor_id: int, user: str = Depends(require_auth)):
    incidents = await database.get_incidents_7d(monitor_id)
    return incidents


# === Export ===

@app.get("/api/export/{monitor_id}/json")
async def api_export_json(monitor_id: int, user: str = Depends(require_auth)):
    mon = await database.get_monitor(monitor_id)
    if not mon:
        raise HTTPException(status_code=404)
    logs = await database.get_logs_all(monitor_id, limit=10000)
    content = json.dumps({"monitor": mon, "logs": logs}, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="monitor_{monitor_id}.json"'},
    )


@app.get("/api/export/{monitor_id}/csv")
async def api_export_csv(monitor_id: int, user: str = Depends(require_auth)):
    mon = await database.get_monitor(monitor_id)
    if not mon:
        raise HTTPException(status_code=404)
    logs = await database.get_logs_all(monitor_id, limit=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "status", "latency", "downtime_duration"])
    for log in logs:
        writer.writerow([log["timestamp"], log["status"], log["latency"], log["downtime_duration"]])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="monitor_{monitor_id}.csv"'},
    )


# === Telegram Settings ===

class TelegramSettings(BaseModel):
    bot_token: str
    chat_id: str


@app.post("/api/settings/telegram")
async def api_save_telegram(data: TelegramSettings, user: str = Depends(require_auth)):
    await database.set_setting("telegram_bot_token", data.bot_token)
    await database.set_setting("telegram_chat_id", data.chat_id)
    return {"ok": True}


@app.post("/api/settings/telegram/test")
async def api_test_telegram(user: str = Depends(require_auth)):
    await notifier.send_telegram("\u2705 <b>Tes Notifikasi</b>\n\nKoneksi Telegram berhasil!")
    return {"ok": True}


# ============================
# Run
# ============================

if __name__ == "__main__":
    uvicorn.run(
        "dashboard:app",
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        reload=False,
    )
