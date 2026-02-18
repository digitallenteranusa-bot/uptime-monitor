# Panduan Instalasi Uptime Monitor

## Daftar Isi

- [Persyaratan Sistem](#persyaratan-sistem)
- [Cara 1: Instalasi Lokal (Tanpa Docker)](#cara-1-instalasi-lokal-tanpa-docker)
- [Cara 2: Instalasi Docker](#cara-2-instalasi-docker)
- [Konfigurasi](#konfigurasi)
- [Penggunaan Dashboard](#penggunaan-dashboard)
- [Notifikasi Telegram](#notifikasi-telegram)
- [Tipe Monitoring](#tipe-monitoring)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)

---

## Persyaratan Sistem

### Instalasi Lokal
- Python 3.11 atau lebih baru
- pip (package manager Python)
- Koneksi internet (untuk download dependensi)
- `ping` command tersedia di sistem (sudah bawaan di Windows/Linux/Mac)

### Instalasi Docker
- Docker Engine 20.10+
- Docker Compose v2+

---

## Cara 1: Instalasi Lokal (Tanpa Docker)

### Langkah 1: Clone atau Download Proyek

```bash
cd /path/ke/folder/kamu
git clone <repo-url> uptime-monitor
cd uptime-monitor
```

Atau jika sudah punya foldernya, langsung masuk:

```bash
cd uptime-monitor
```

### Langkah 2: Buat Virtual Environment (Opsional tapi Direkomendasikan)

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### Langkah 3: Install Dependensi

```bash
pip install -r requirements.txt
```

Dependensi yang akan terinstall:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `aiosqlite` - Async SQLite
- `aiohttp` - Async HTTP client (untuk Telegram & HTTP monitoring)
- `jinja2` - Template engine

### Langkah 4: Jalankan Aplikasi

```bash
python dashboard.py
```

Output yang diharapkan:
```
2026-02-18 10:00:00 [monitor] INFO: Starting monitoring for 3 targets
2026-02-18 10:00:00 [monitor] INFO: Started monitoring task for Cloudflare DNS (1.1.1.1) [PING]
2026-02-18 10:00:00 [monitor] INFO: Started monitoring task for Google DNS (8.8.8.8) [PING]
2026-02-18 10:00:00 [monitor] INFO: Started monitoring task for Router Gateway (192.168.1.1) [PING]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Langkah 5: Buka Dashboard

Buka browser dan akses:
- **Dashboard:** http://localhost:8000
- **Login default:** username `admin`, password `admin`
- **Status publik:** http://localhost:8000/status (tanpa login)
- **Health check:** http://localhost:8000/health

---

## Cara 2: Instalasi Docker

### Langkah 1: Siapkan File Environment (Opsional)

Buat file `.env` di folder proyek untuk konfigurasi:

```bash
# .env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=gantiPasswordKuat123
SECRET_KEY=kunci-rahasia-random-panjang
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_COOLDOWN=300
LOG_RETENTION_DAYS=30
```

### Langkah 2: Build dan Jalankan

```bash
docker-compose up --build -d
```

Penjelasan flag:
- `--build` : build image dari Dockerfile
- `-d` : jalankan di background (detached)

### Langkah 3: Cek Status Container

```bash
docker-compose ps
docker-compose logs -f
```

### Langkah 4: Buka Dashboard

Sama seperti instalasi lokal:
- **Dashboard:** http://localhost:8000
- **Login default:** username `admin`, password `admin`

### Menghentikan

```bash
docker-compose down
```

### Update Setelah Perubahan Kode

```bash
docker-compose up --build -d
```

### Data Persistent

Database SQLite tersimpan di folder `./data/` yang di-mount sebagai volume Docker. Data tidak hilang saat container di-restart atau di-rebuild.

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
| `SECRET_KEY` | `uptime-monitor-secret-change-me` | Kunci enkripsi session |
| `TELEGRAM_BOT_TOKEN` | _(kosong)_ | Token Bot Telegram |
| `TELEGRAM_CHAT_ID` | _(kosong)_ | Chat ID tujuan notifikasi |
| `ALERT_COOLDOWN` | `300` | Jeda minimum antar alert per target (detik) |
| `LOG_RETENTION_DAYS` | `30` | Hapus log lebih lama dari X hari |

### Mengatur via Environment Variable (Lokal)

**Linux/Mac:**
```bash
export ADMIN_PASSWORD=passwordKuat123
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF
export TELEGRAM_CHAT_ID=-100123456789
python dashboard.py
```

**Windows (CMD):**
```cmd
set ADMIN_PASSWORD=passwordKuat123
set TELEGRAM_BOT_TOKEN=123456:ABC-DEF
set TELEGRAM_CHAT_ID=-100123456789
python dashboard.py
```

**Windows (PowerShell):**
```powershell
$env:ADMIN_PASSWORD="passwordKuat123"
$env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF"
$env:TELEGRAM_CHAT_ID="-100123456789"
python dashboard.py
```

### Menambah Target Default

Edit file `config.py`, tambahkan entry di list `MONITORS`:

```python
MONITORS = [
    {"name": "Cloudflare DNS", "target": "1.1.1.1", "type": "ping", "interval": 60},
    {"name": "Google DNS", "target": "8.8.8.8", "type": "ping", "interval": 60},
    {"name": "Router Gateway", "target": "192.168.1.1", "type": "ping", "interval": 60},
    # Tambahkan target baru di sini:
    {"name": "Web Server", "target": "https://example.com", "type": "http", "interval": 30},
    {"name": "Mail Server", "target": "mail.example.com", "type": "tcp", "port": 25, "interval": 120},
]
```

> Target juga bisa ditambahkan langsung dari dashboard tanpa edit file.

---

## Penggunaan Dashboard

### Login

1. Buka http://localhost:8000
2. Masukkan username dan password (default: `admin` / `admin`)
3. Session tersimpan di cookie browser

### Halaman Utama

- **Kartu status** per monitor: hijau (UP), merah (DOWN), abu-abu (UNKNOWN)
- **Grafik latency** 24 jam di setiap kartu
- **Uptime 7 hari** dalam persen
- **Badge tipe** monitoring (PING, HTTP, TCP, DNS)

### Tambah Monitor

1. Isi form di bagian atas dashboard
2. Pilih tipe: Ping, HTTP, TCP Port, atau DNS
3. Untuk TCP, isi nomor port
4. Atur interval pengecekan (minimal 10 detik)
5. Klik **Tambah**
6. Monitoring langsung aktif tanpa restart

### Edit Monitor

1. Klik ikon pensil di kartu monitor
2. Ubah nama, target, tipe, port, atau interval
3. Klik **Simpan**
4. Task monitoring otomatis di-restart

### Hapus Monitor

1. Klik tombol **X** di kartu monitor
2. Konfirmasi penghapusan
3. Semua log monitor tersebut ikut terhapus

### Halaman Detail

1. Klik nama monitor di kartu untuk membuka halaman detail
2. Informasi yang tersedia:
   - Uptime 24 jam, 7 hari, 30 hari
   - Latency rata-rata, minimum, maksimum
   - Jumlah insiden 7 hari terakhir
   - Grafik latency 24 jam (lebih besar)
   - Tabel log 100 entry terakhir
3. Tombol **Export CSV** dan **Export JSON** untuk download data

### Halaman Status Publik

- Akses di http://localhost:8000/status
- **Tidak perlu login** - cocok untuk dibagikan ke tim atau publik
- Auto-refresh setiap 30 detik
- Menampilkan waktu lokal sesuai timezone browser

### Halaman Pengaturan

1. Klik **Pengaturan** di nav bar dashboard
2. Konfigurasi Telegram Bot Token dan Chat ID
3. Tombol **Tes Kirim** untuk verifikasi koneksi
4. Informasi alert cooldown dan retensi log

---

## Notifikasi Telegram

### Membuat Bot Telegram

1. Buka Telegram, cari **@BotFather**
2. Kirim `/newbot`
3. Ikuti instruksi, beri nama bot
4. Salin **token** yang diberikan (format: `123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ`)

### Mendapatkan Chat ID

**Untuk chat pribadi:**
1. Kirim pesan apapun ke bot kamu
2. Buka di browser: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Cari `"chat":{"id":123456789}` - angka itu adalah Chat ID kamu

**Untuk group chat:**
1. Tambahkan bot ke group
2. Kirim pesan di group
3. Buka URL getUpdates di atas
4. Chat ID group biasanya format `-100xxxxxxxxxx`

### Mengaktifkan Notifikasi

**Cara 1: Dari dashboard**
1. Buka http://localhost:8000/settings
2. Isi Bot Token dan Chat ID
3. Klik **Simpan**, lalu **Tes Kirim**

**Cara 2: Via environment variable**
```bash
export TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNO-pqrSTUvwxYZ
export TELEGRAM_CHAT_ID=-100123456789
python dashboard.py
```

### Perilaku Notifikasi

- Notifikasi dikirim saat **status berubah**: UP→DOWN atau DOWN→UP
- **Alert cooldown** (default 5 menit) mencegah spam jika target flapping
- Jika Telegram tidak dikonfigurasi, sistem tetap berjalan normal (notifikasi dilewati)

### Notifikasi Browser

- Dashboard otomatis meminta izin notifikasi browser
- Saat ada target DOWN, muncul notifikasi desktop + bunyi alert
- Polling status setiap 30 detik

---

## Tipe Monitoring

| Tipe | Cara Kerja | Contoh Target | Port |
|---|---|---|---|
| **Ping (ICMP)** | Kirim ping via subprocess, cek response | `1.1.1.1`, `192.168.1.1` | - |
| **HTTP** | Request GET, cek status code 2xx/3xx | `https://google.com`, `http://192.168.1.1:8080` | - |
| **TCP** | Buka koneksi TCP ke port, cek terbuka | `mail.example.com`, `192.168.1.50` | Wajib isi |
| **DNS** | Resolve hostname ke IP address | `google.com`, `example.com` | - |

Semua tipe mengukur **latency** (waktu respons dalam milidetik).

---

## API Endpoints

### Publik (Tanpa Auth)

| Method | Endpoint | Keterangan |
|---|---|---|
| GET | `/status` | Halaman status publik |
| GET | `/health` | Health check (untuk Docker/monitoring) |
| GET | `/login` | Halaman login |
| POST | `/api/login` | Proses login |

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
| GET | `/api/logs/{id}` | Log 24 jam (untuk grafik) |
| GET | `/api/logs/{id}/all` | Semua log (500 terakhir) |
| GET | `/api/monitor/{id}/stats` | Statistik detail |
| GET | `/api/export/{id}/json` | Export log ke JSON |
| GET | `/api/export/{id}/csv` | Export log ke CSV |
| POST | `/api/settings/telegram` | Simpan konfigurasi Telegram |
| POST | `/api/settings/telegram/test` | Tes kirim notifikasi |

### Contoh API Call

```bash
# Login dan dapatkan token
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Tambah monitor (sertakan cookie session)
curl -X POST http://localhost:8000/api/monitors \
  -H "Content-Type: application/json" \
  -b "session_token=TOKEN_DARI_LOGIN" \
  -d '{"name":"Web Server","target":"https://example.com","type":"http","interval":30}'
```

---

## Troubleshooting

### Aplikasi tidak bisa diakses

```bash
# Pastikan port 8000 tidak dipakai proses lain
# Linux/Mac:
lsof -i :8000

# Windows:
netstat -ano | findstr :8000
```

### Database error setelah update skema

Jika ada error karena kolom baru (misal `type`, `port`), hapus database lama:

```bash
rm data/uptime.db
python dashboard.py
```

> Data monitoring sebelumnya akan hilang. Backup dulu jika perlu.

### Ping tidak berfungsi di Docker

Pastikan Dockerfile menginstall `iputils-ping`:
```dockerfile
RUN apt-get update && apt-get install -y iputils-ping
```

### Telegram tidak mengirim notifikasi

1. Cek token dan chat ID sudah benar
2. Pastikan bot sudah diajak chat (kirim `/start` ke bot)
3. Untuk group: pastikan bot sudah ditambahkan ke group
4. Cek log aplikasi untuk error:
   ```bash
   docker-compose logs -f | grep -i telegram
   ```
5. Gunakan tombol **Tes Kirim** di halaman Pengaturan

### Permission denied saat ping (Linux)

Jika menjalankan tanpa Docker dan tanpa root:
```bash
# Berikan capability ping
sudo setcap cap_net_raw+ep $(which ping)
```

### Cara reset password admin

Ubah environment variable dan restart:
```bash
export ADMIN_PASSWORD=passwordBaru
python dashboard.py
```

Atau di Docker, edit `.env` lalu:
```bash
docker-compose up -d
```
