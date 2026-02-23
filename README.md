# Uptime Monitor

Sistem monitoring jaringan dan website yang ringan, self-hosted, dan real-time. Dibangun dengan Python + FastAPI.

Dibuat oleh **Agus Setyono** — Trenggalek, Indonesia.

Dikembangkan bersama **Digital Lentera Nusa**.

---

## Fitur Utama

- **Multi-tipe monitoring** — Ping (ICMP), HTTP, TCP Port, DNS
- **Dua grup monitor** — Network (DNS, gateway) dan Web (Facebook, YouTube, dll)
- **Dashboard real-time** — Dark theme, heartbeat bar 24 jam, auto-refresh
- **Halaman status publik** — Bisa dibagikan tanpa login (`/status`, `/status/web`)
- **Notifikasi Telegram** — Alert saat DOWN/UP dengan cooldown anti-spam
- **Detail & statistik** — Uptime 24h/7d/30d, latency min/avg/max, tabel insiden
- **Export data** — CSV dan JSON per monitor
- **CRUD monitor** — Tambah, edit, hapus langsung dari dashboard
- **Notifikasi browser** — Push notification + bunyi alert
- **Auto-cleanup** — Hapus log lama otomatis (default 30 hari)
- **Deploy fleksibel** — Systemd service atau Docker

---

## Screenshot

| Dashboard | Status Publik |
|-----------|---------------|
| `http://server:8000/` | `http://server:8000/status` |

---

## Quick Start

### Persyaratan

- Python 3.11+
- Git
- Linux (Debian/Ubuntu recommended)

### Instalasi

```bash
# Clone
cd /opt
git clone https://github.com/digitallenteranusa-bot/uptime-monitor.git
cd uptime-monitor

# Setup Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Jalankan
mkdir -p data
python3 dashboard.py
```

Buka `http://<IP-SERVER>:8000` — login default: `admin` / `admin`

### Docker

```bash
cd /opt
git clone https://github.com/digitallenteranusa-bot/uptime-monitor.git
cd uptime-monitor
docker-compose up --build -d
```

---

## Arsitektur

```
uptime-monitor/
├── dashboard.py          # FastAPI app (entry point)
├── monitor.py            # Async monitoring engine
├── database.py           # SQLite + connection pooling
├── notifier.py           # Telegram notifications
├── config.py             # Konfigurasi & daftar monitor
├── requirements.txt      # Dependencies
├── Dockerfile
├── docker-compose.yml
├── uptime-monitor.service  # Systemd unit file
├── static/
│   └── style.css         # Dark theme UI
├── templates/
│   ├── login.html
│   ├── dashboard.html    # Dashboard (network & web)
│   ├── detail.html       # Detail monitor + statistik
│   ├── settings.html     # Konfigurasi Telegram
│   ├── status.html       # Status publik network
│   └── status_web.html   # Status publik web
└── data/
    └── uptime.db         # SQLite database (auto-created)
```

---

## Tipe Monitoring

| Tipe | Cara Kerja | Contoh Target |
|------|-----------|---------------|
| **Ping** | ICMP ping via subprocess | `1.1.1.1`, `8.8.8.8` |
| **HTTP** | GET request + TCP RTT untuk latency | `http://www.facebook.com` |
| **TCP** | Koneksi ke port tertentu | `mail.server.com:25` |
| **DNS** | Resolve hostname ke IP | `google.com` |

### Pengukuran Latency

- **Ping** — ICMP round-trip time (sama seperti MikroTik)
- **HTTP** — TCP connect time (SYN→SYN-ACK), bukan total waktu HTTP
- **TCP** — Waktu koneksi ke port
- **DNS** — Waktu resolusi DNS

### Retry Logic

Setiap check yang gagal akan di-retry hingga **3 kali** dengan jeda **5 detik**. Target baru dianggap DOWN setelah semua retry gagal.

---

## Grup Monitor

Monitor dibagi dua grup:

| Grup | Dashboard | Status Publik | Contoh |
|------|-----------|---------------|--------|
| **Network** | `/` | `/status` | Cloudflare DNS, Google DNS |
| **Web** | `/web` | `/status/web` | Facebook, YouTube, TikTok, dll |

Monitor bisa ditambah ke grup manapun via form di dashboard.

---

## Halaman Aplikasi

### Protected (Perlu Login)

| Route | Fungsi |
|-------|--------|
| `/` | Dashboard network monitors |
| `/web` | Dashboard web monitors |
| `/monitor/{id}` | Detail monitor + statistik + insiden |
| `/settings` | Konfigurasi Telegram |

### Publik (Tanpa Login)

| Route | Fungsi |
|-------|--------|
| `/status` | Status publik network |
| `/status/web` | Status publik web |
| `/health` | Health check endpoint |

---

## Konfigurasi

Semua konfigurasi via environment variable (opsional, ada default):

| Variable | Default | Keterangan |
|----------|---------|------------|
| `ADMIN_USERNAME` | `admin` | Username login |
| `ADMIN_PASSWORD` | `admin` | Password login |
| `SECRET_KEY` | `uptime-monitor-secret-change-me` | Kunci session |
| `DB_PATH` | `data/uptime.db` | Path database |
| `DASHBOARD_HOST` | `0.0.0.0` | Host binding |
| `DASHBOARD_PORT` | `8000` | Port web server |
| `TELEGRAM_BOT_TOKEN` | _(kosong)_ | Token Bot Telegram |
| `TELEGRAM_CHAT_ID` | _(kosong)_ | Chat ID tujuan |
| `ALERT_COOLDOWN` | `300` | Jeda antar alert per target (detik) |
| `LOG_RETENTION_DAYS` | `30` | Hapus log lebih lama dari X hari |

### Contoh `.env`

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=passwordKuat123
SECRET_KEY=random-secret-key-panjang
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ
TELEGRAM_CHAT_ID=-100123456789
```

---

## Menambah Monitor Default

Edit `config.py`:

```python
MONITORS = [
    {"name": "Cloudflare DNS", "target": "1.1.1.1", "type": "ping", "interval": 60, "group": "network"},
    {"name": "Google DNS", "target": "8.8.8.8", "type": "ping", "interval": 60, "group": "network"},
    {"name": "Facebook", "target": "http://www.facebook.com", "type": "http", "interval": 60, "group": "web"},
    # Tambahkan monitor baru:
    {"name": "Server Kantor", "target": "192.168.1.1", "type": "ping", "interval": 30, "group": "network"},
    {"name": "Web Perusahaan", "target": "http://example.com", "type": "http", "interval": 60, "group": "web"},
]
```

Monitor juga bisa ditambah/edit/hapus langsung dari dashboard tanpa edit file.

---

## Deploy sebagai Service (Systemd)

```bash
cp /opt/uptime-monitor/uptime-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable uptime-monitor
systemctl start uptime-monitor
```

### Perintah Berguna

| Perintah | Fungsi |
|----------|--------|
| `systemctl start uptime-monitor` | Jalankan |
| `systemctl stop uptime-monitor` | Matikan |
| `systemctl restart uptime-monitor` | Restart |
| `systemctl status uptime-monitor` | Cek status |
| `journalctl -u uptime-monitor -f` | Log realtime |

---

## Notifikasi Telegram

### Setup

1. Buat bot via **@BotFather** di Telegram → dapatkan token
2. Kirim pesan ke bot → dapatkan Chat ID via `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Masukkan di **Settings** (`/settings`) atau via environment variable
4. Klik **Tes Kirim** untuk verifikasi

### Perilaku

- Notifikasi dikirim saat status berubah: **UP → DOWN** atau **DOWN → UP**
- Cooldown 5 menit (default) per target untuk mencegah spam
- Jika Telegram tidak dikonfigurasi, sistem tetap jalan normal

---

## API Endpoints

### Publik

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/health` | Health check |
| GET | `/api/public/heartbeat/{id}` | Data heartbeat bar |
| POST | `/api/login` | Login |

### Protected

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/api/monitors` | Daftar semua monitor |
| POST | `/api/monitors` | Tambah monitor |
| PUT | `/api/monitors/{id}` | Edit monitor |
| DELETE | `/api/monitors/{id}` | Hapus monitor |
| GET | `/api/heartbeat/{id}` | Data heartbeat |
| GET | `/api/logs/{id}` | Log 24 jam |
| GET | `/api/logs/{id}/all` | Semua log |
| GET | `/api/monitor/{id}/stats` | Statistik detail |
| GET | `/api/monitor/{id}/incidents` | Insiden 7 hari |
| GET | `/api/export/{id}/json` | Export JSON |
| GET | `/api/export/{id}/csv` | Export CSV |

---

## Update Aplikasi

### Systemd

```bash
cd /opt/uptime-monitor && git pull && systemctl restart uptime-monitor
```

### Docker

```bash
cd /opt/uptime-monitor && git pull && docker-compose up --build -d
```

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI, Uvicorn
- **Database:** SQLite (aiosqlite) dengan connection pooling & WAL mode
- **HTTP Client:** aiohttp (async, shared session, SSL context)
- **Frontend:** Vanilla JS, CSS dark theme
- **Template:** Jinja2
- **Notifications:** Telegram Bot API

### Dependencies

```
fastapi==0.115.6
uvicorn==0.34.0
aiosqlite==0.20.0
aiohttp==3.11.11
jinja2==3.1.4
```

---

## Lisensi

MIT License

---

Dibuat dengan oleh **Agus Setyono** — Trenggalek, Indonesia

Dikembangkan bersama **Digital Lentera Nusa**
