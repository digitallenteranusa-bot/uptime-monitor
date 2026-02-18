# Uptime Monitor - Catatan Pengembangan

## Fitur Inti

- [x] Monitoring ICMP Ping (multi-target, async)
- [x] Tambah monitor dari dashboard
- [x] Hapus monitor dari dashboard
- [x] Retry logic (3x percobaan sebelum DOWN)
- [x] Hitung durasi downtime (DOWN → UP)
- [x] Database SQLite + aiosqlite
- [x] Seed monitor default (Cloudflare, Google DNS, Router)
- [x] Edit monitor dari dashboard (ubah nama, IP, tipe, port, interval)
- [x] Monitoring HTTP (cek status code 2xx/3xx)
- [x] Monitoring TCP Port (cek port terbuka)
- [x] Monitoring DNS Resolution
- [x] Halaman detail per monitor (`/monitor/{id}`) - histori, statistik, timeline
- [x] Retensi data / auto-cleanup log lama (> 30 hari, bisa diatur)
- [x] Export data log ke CSV/JSON

## Dashboard & UI

- [x] Dashboard utama dengan kartu status (UP/DOWN/UNKNOWN)
- [x] Grafik latency 24 jam (Chart.js)
- [x] Persentase uptime 7 hari
- [x] Halaman status publik (`/status`) - ramah mobile, auto-refresh
- [x] Tema mode gelap (dark mode)
- [x] Responsive / mobile-friendly
- [x] Autentikasi dashboard (login/password, session-based)
- [x] Notifikasi browser (push notification + sound alert saat target down)
- [x] Konversi timezone UTC ke timezone lokal user di tampilan

## Notifikasi (Telegram)

- [x] Notifikasi Telegram saat status berubah (UP → DOWN, DOWN → UP)
- [x] Pesan berisi nama target, IP, tipe, waktu, durasi downtime
- [x] Fallback jika kredensial Telegram tidak diisi (log warning)
- [x] Konfigurasi token & chat ID Telegram dari dashboard (`/settings`)
- [x] Alert cooldown / throttling (jeda 5 menit default, anti-spam flapping)

## Infrastruktur

- [x] Dockerfile (Python 3.11-slim + iputils-ping)
- [x] docker-compose.yml (volume persist, env var, healthcheck)
- [x] Satu proses: monitor + dashboard di event loop yang sama
- [x] Health check endpoint (`/health`)
- [x] Graceful shutdown (penanganan sinyal SIGTERM)
- [x] Connection pooling database (pool 5 koneksi, reuse)
