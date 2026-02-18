# Panduan Instalasi Uptime Monitor

Sistem monitoring jaringan mandiri — dibuat oleh **Digital Lentera Nusa**

## Daftar Isi

- [Persyaratan Sistem](#persyaratan-sistem)
- [Instalasi di Linux Server (Debian/Ubuntu)](#instalasi-di-linux-server-debianubuntu)
- [Instalasi dengan Docker](#instalasi-dengan-docker)
- [Menjalankan sebagai Service (Systemd)](#menjalankan-sebagai-service-systemd)
- [Konfigurasi](#konfigurasi)
- [Penggunaan Dashboard](#penggunaan-dashboard)
- [Notifikasi Telegram](#notifikasi-telegram)
- [Tipe Monitoring](#tipe-monitoring)
- [API Endpoints](#api-endpoints)
- [Update Aplikasi](#update-aplikasi)
- [Troubleshooting](#troubleshooting)

---

## Persyaratan Sistem

### Linux Server (Rekomendasi)
- Debian 11+ / Ubuntu 20.04+
- Python 3.11+
- Git
- Akses root

### Docker (Alternatif)
- Docker Engine 20.10+
- Docker Compose v2+

---

## Instalasi di Linux Server (Debian/Ubuntu)

Jalankan perintah berikut satu per satu di terminal:

### 1. Install dependensi sistem

```bash
apt update && apt install -y python3 python3-pip python3-venv git iputils-ping
```

### 2. Clone repository

```bash
cd /opt
git clone https://github.com/digitallenteranusa-bot/uptime-monitor.git
cd uptime-monitor
```

### 3. Buat virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependensi Python

```bash
pip install -r requirements.txt
```

### 5. Buat folder data

```bash
mkdir -p data
```

### 6. Tes jalankan (foreground)

```bash
python3 dashboard.py
```

Jika berhasil, akan muncul:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
[monitor] INFO: Starting monitoring for 3 targets
```

Tekan `Ctrl+C` untuk berhenti, lalu lanjut ke bagian [Systemd](#menjalankan-sebagai-service-systemd).

### 7. Buka di browser

```
http://<IP-SERVER>:8000         → Dashboard (perlu login)
http://<IP-SERVER>:8000/status  → Status publik (tanpa login)
http://<IP-SERVER>:8000/health  → Health check
```

**Login default:** `admin` / `admin`

---

## Instalasi dengan Docker

### 1. Clone repository

```bash
cd /opt
git clone https://github.com/digitallenteranusa-bot/uptime-monitor.git
cd uptime-monitor
```

### 2. (Opsional) Buat file `.env`

```bash
cat > .env << 'EOF'
ADMIN_USERNAME=admin
ADMIN_PASSWORD=gantiPasswordKuat123
SECRET_KEY=kunci-rahasia-random-panjang
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_COOLDOWN=300
LOG_RETENTION_DAYS=30
EOF
```

### 3. Build dan jalankan

```bash
docker-compose up --build -d
```

### 4. Cek status

```bash
docker-compose ps
docker-compose logs -f
```

### Perintah Docker lainnya

```bash
docker-compose down              # Matikan
docker-compose restart           # Restart
docker-compose up --build -d     # Rebuild setelah update kode
```

Database tersimpan di `./data/` (volume mount), tidak hilang saat rebuild.

---

## Menjalankan sebagai Service (Systemd)

Supaya aplikasi **selalu online**, auto-start saat server boot, dan auto-restart jika crash:

### 1. Copy file service

```bash
cp /opt/uptime-monitor/uptime-monitor.service /etc/systemd/system/
```

### 2. Aktifkan dan jalankan

```bash
systemctl daemon-reload
systemctl enable uptime-monitor
systemctl start uptime-monitor
```

### 3. Cek status

```bash
systemctl status uptime-monitor
```

### Perintah systemd

| Perintah | Fungsi |
|---|---|
| `systemctl start uptime-monitor` | Jalankan |
| `systemctl stop uptime-monitor` | Matikan |
| `systemctl restart uptime-monitor` | Restart |
| `systemctl status uptime-monitor` | Cek status |
| `journalctl -u uptime-monitor -f` | Lihat log realtime |
| `journalctl -u uptime-monitor --since "1 hour ago"` | Log 1 jam terakhir |

---

## Konfigurasi

### Environment Variables

| Variable | Default | Keterangan |
|---|---|---|
| `DB_PATH` | `data/uptime.db` | Path file database SQLite |
| `DASHBOARD_HOST` | `0.0.0.0` | Host binding web server |
| `DASHBOARD_PORT` | `8000` | Port web server |
| `ADMIN_USERNAME` | `admin` | Username login dashboard |
| `ADMIN_PASSWORD` | `admin` | Password login dashboard |
| `SECRET_KEY` | `uptime-monitor-secret-change-me` | Kunci session |
| `TELEGRAM_BOT_TOKEN` | _(kosong)_ | Token Bot Telegram |
| `TELEGRAM_CHAT_ID` | _(kosong)_ | Chat ID tujuan notifikasi |
| `ALERT_COOLDOWN` | `300` | Jeda minimum antar alert per target (detik) |
| `LOG_RETENTION_DAYS` | `30` | Hapus log lebih lama dari X hari |

### Cara set environment variable di Linux

```bash
export ADMIN_PASSWORD=passwordKuat123
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF
export TELEGRAM_CHAT_ID=-100123456789
```

Atau buat file `.env` lalu restart service.

### Menambah Target Default di config.py

```python
MONITORS = [
    {"name": "Cloudflare DNS", "target": "1.1.1.1", "type": "ping", "interval": 60},
    {"name": "Google DNS", "target": "8.8.8.8", "type": "ping", "interval": 60},
    # Tambahkan di sini:
    {"name": "Web Server", "target": "https://example.com", "type": "http", "interval": 30},
    {"name": "Mail Server", "target": "mail.example.com", "type": "tcp", "port": 25, "interval": 120},
]
```

> Target juga bisa ditambah/edit/hapus langsung dari dashboard tanpa edit file.

---

## Penggunaan Dashboard

### Login

1. Buka `http://<IP-SERVER>:8000`
2. Masukkan username dan password (default: `admin` / `admin`)

### Halaman Utama (Dashboard)

- **Heartbeat bar** per monitor — 90 slot mewakili 24 jam terakhir
- **Warna bar**: hijau (UP), merah (DOWN), kuning (degraded), abu-abu (no data)
- **Tooltip** saat hover bar: waktu, status, latency
- **Summary bar**: jumlah monitor UP / DOWN / Unknown
- **Uptime 7 hari** dan **latency terakhir** per monitor

### Tambah Monitor

1. Klik **+ Tambah Monitor**
2. Isi nama, target (IP/hostname/URL), pilih tipe, atur interval
3. Untuk TCP, isi nomor port
4. Klik **Tambah** — monitoring langsung aktif

### Edit Monitor

1. Klik ikon pensil pada monitor
2. Ubah nama, target, tipe, port, atau interval
3. Klik **Simpan** — task monitoring otomatis di-restart

### Hapus Monitor

1. Klik tombol **X** pada monitor
2. Konfirmasi — semua log ikut terhapus

### Halaman Detail (`/monitor/{id}`)

- Klik nama monitor untuk membuka detail
- Statistik: uptime 24h/7d/30d, latency min/avg/max, jumlah insiden
- Grafik latency 24 jam (Chart.js)
- Tabel 100 log terakhir
- Tombol **Export CSV** dan **Export JSON**

### Halaman Status Publik (`/status`)

- **Tidak perlu login** — cocok dibagikan ke tim atau pelanggan
- Heartbeat bar per monitor dengan tooltip
- Auto-refresh setiap 10 detik
- IP dan tipe monitoring **disembunyikan** (hanya nama monitor)
- Waktu ditampilkan sesuai timezone browser

### Halaman Pengaturan (`/settings`)

- Konfigurasi Telegram (token & chat ID) dari browser
- Tombol **Tes Kirim** untuk verifikasi
- Info alert cooldown dan retensi log

---

## Notifikasi Telegram

### Membuat Bot Telegram

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot`
3. Ikuti instruksi, beri nama bot
4. Salin **token** (format: `123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ`)

### Mendapatkan Chat ID

**Chat pribadi:**
1. Kirim pesan ke bot kamu
2. Buka: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Cari `"chat":{"id":123456789}`

**Group chat:**
1. Tambahkan bot ke group, kirim pesan
2. Buka URL getUpdates
3. Chat ID group format `-100xxxxxxxxxx`

### Mengaktifkan

**Cara 1 — Dari dashboard:**
1. Buka `/settings`
2. Isi Bot Token dan Chat ID
3. Klik **Simpan**, lalu **Tes Kirim**

**Cara 2 — Via environment variable:**
```bash
export TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ
export TELEGRAM_CHAT_ID=-100123456789
systemctl restart uptime-monitor
```

### Perilaku Notifikasi

- Dikirim saat status berubah: **UP → DOWN** atau **DOWN → UP**
- **Alert cooldown** (default 5 menit) mencegah spam saat target flapping
- Jika Telegram tidak dikonfigurasi, sistem tetap jalan (notifikasi dilewati)
- **Notifikasi browser** juga aktif di dashboard (push notification + bunyi alert)

---

## Tipe Monitoring

| Tipe | Cara Kerja | Contoh Target | Port |
|---|---|---|---|
| **Ping** | ICMP ping via subprocess | `1.1.1.1`, `192.168.1.1` | - |
| **HTTP** | GET request, cek status 2xx/3xx | `https://google.com` | - |
| **TCP** | Cek port terbuka | `mail.example.com` | Wajib isi |
| **DNS** | Resolve hostname ke IP | `google.com` | - |

Semua tipe mengukur **latency** (milidetik).

---

## API Endpoints

### Publik (Tanpa Auth)

| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/status` | Halaman status publik |
| GET | `/health` | Health check |
| GET | `/login` | Halaman login |
| POST | `/api/login` | Proses login |
| GET | `/api/public/heartbeat/{id}` | Heartbeat bar data (untuk status publik) |

### Protected (Perlu Login)

| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/` | Dashboard utama |
| GET | `/monitor/{id}` | Halaman detail monitor |
| GET | `/settings` | Halaman pengaturan |
| GET | `/api/monitors` | Daftar semua monitor + uptime |
| POST | `/api/monitors` | Tambah monitor baru |
| PUT | `/api/monitors/{id}` | Edit monitor |
| DELETE | `/api/monitors/{id}` | Hapus monitor |
| GET | `/api/heartbeat/{id}` | Heartbeat bar data |
| GET | `/api/logs/{id}` | Log 24 jam |
| GET | `/api/logs/{id}/all` | Semua log (500 terakhir) |
| GET | `/api/monitor/{id}/stats` | Statistik detail |
| GET | `/api/export/{id}/json` | Export log ke JSON |
| GET | `/api/export/{id}/csv` | Export log ke CSV |
| POST | `/api/settings/telegram` | Simpan konfigurasi Telegram |
| POST | `/api/settings/telegram/test` | Tes kirim notifikasi |

### Contoh API Call

```bash
# Login
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Tambah monitor
curl -X POST http://localhost:8000/api/monitors \
  -H "Content-Type: application/json" \
  -b "session_token=TOKEN_DARI_LOGIN" \
  -d '{"name":"Web Server","target":"https://example.com","type":"http","interval":30}'
```

---

## Update Aplikasi

### Jika pakai Systemd

```bash
cd /opt/uptime-monitor
git pull
systemctl restart uptime-monitor
```

### Jika pakai Docker

```bash
cd /opt/uptime-monitor
git pull
docker-compose up --build -d
```

---

## Troubleshooting

### Aplikasi tidak bisa diakses

```bash
# Cek apakah port 8000 dipakai
ss -tlnp | grep 8000

# Cek status service
systemctl status uptime-monitor

# Lihat log error
journalctl -u uptime-monitor --since "10 min ago"
```

### Database error setelah update skema

Hapus database lama (data monitoring akan hilang):

```bash
rm /opt/uptime-monitor/data/uptime.db
systemctl restart uptime-monitor
```

### Telegram tidak mengirim notifikasi

1. Cek token dan chat ID di `/settings`
2. Klik **Tes Kirim**
3. Pastikan bot sudah diajak chat (kirim `/start`)
4. Untuk group: pastikan bot sudah ditambahkan
5. Cek log: `journalctl -u uptime-monitor | grep -i telegram`

### Ping tidak berfungsi

```bash
# Cek apakah ping tersedia
which ping

# Install jika belum
apt install -y iputils-ping
```

### Reset password admin

```bash
export ADMIN_PASSWORD=passwordBaru
systemctl restart uptime-monitor
```

Atau edit `.env` lalu restart.

### Proses tidak mau mati

```bash
pkill -9 -f dashboard.py
```
