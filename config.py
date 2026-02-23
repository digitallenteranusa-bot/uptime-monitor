import os

# === Target Monitoring ===
MONITORS = [
    {"name": "Cloudflare DNS", "target": "1.1.1.1", "type": "ping", "interval": 60, "group": "network"},
    {"name": "Google DNS", "target": "8.8.8.8", "type": "ping", "interval": 60, "group": "network"},
    {"name": "Facebook", "target": "http://www.facebook.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "YouTube", "target": "http://www.youtube.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "TikTok", "target": "http://www.tiktok.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "WhatsApp", "target": "http://web.whatsapp.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "Instagram", "target": "http://www.instagram.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "Mobile Legends", "target": "http://m.mobilelegends.com", "type": "http", "interval": 60, "group": "web"},
    {"name": "Shopee", "target": "http://shopee.co.id", "type": "http", "interval": 60, "group": "web"},
    {"name": "Tokopedia", "target": "http://www.tokopedia.com", "type": "http", "interval": 60, "group": "web"},
]

# === Retry Settings ===
MAX_RETRIES = 3
RETRY_DELAY = 5  # detik

# === Database ===
DB_PATH = os.getenv("DB_PATH", "data/uptime.db")

# === Telegram Notification ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# === Alert Cooldown (detik) ===
# Jeda minimum antar notifikasi untuk target yang sama (anti-spam flapping)
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "300"))  # 5 menit

# === Data Retention ===
# Hapus log lebih lama dari X hari
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))

# === Dashboard ===
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))

# === Authentication ===
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
SECRET_KEY = os.getenv("SECRET_KEY", "uptime-monitor-secret-change-me")
