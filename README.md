# Sistem Sertifikat Magang Otomatis — Kejaksaan Tinggi Jawa Tengah

Aplikasi web **full-stack** yang bisa langsung dijalankan, mengimplementasikan
alur verifikasi **Nama + NIM + No. WhatsApp → OTP via WhatsApp → Sertifikat
dikirim ke Email**. Backend: **Flask (Python)** + **SQLite**. Tampilan:
**Tailwind CSS + Alpine.js + Flatpickr** (di-build lokal, bukan lewat CDN
runtime — lihat penjelasan di bagian 6).

---

## 1. Alur Sistem (Ringkasan)

**Peserta magang:**
1. Buka portal `/ambil-sertifikat`, isi Nama, NIM, dan No. WhatsApp.
2. Sistem mencocokkan ke data yang diunggah admin, lalu mengirim kode OTP
   6-digit ke **WhatsApp** peserta.
3. Peserta memasukkan kode OTP.
4. Begitu benar, sertifikat PDF otomatis dibuat dan **dikirim sebagai
   lampiran ke email** peserta yang terdaftar (bukan diunduh langsung dari
   browser) — meniru pola pengiriman sertifikat bootcamp/seminar resmi.
5. Peserta hanya bisa mengklaim satu kali; percobaan berikutnya akan
   ditolak dengan pesan "sudah pernah diambil".

**Admin Kejati:**
1. Login ke panel admin.
2. Buat **Periode Magang** baru — isi nama, pilih tanggal mulai/selesai
   lewat kalender modern, pilih **Template Sertifikat**, lalu unggah data
   peserta (Excel) — semuanya dalam **satu form, satu tombol simpan**.
3. Setiap peserta otomatis mendapat **No. Ref** (nomor sertifikat) dan
   kode verifikasi begitu diunggah.
4. Pantau status tiap peserta (Sudah/Belum Diambil, jumlah percobaan
   gagal) langsung di tabel **Data Peserta** — tidak ada halaman "Log
   Aktivitas" terpisah, statusnya sudah cukup terlihat di sana.
5. Kelola **Template Sertifikat**: unggah desain baru kapan saja, kalibrasi
   posisi Nama/NIM/Fakultas/Universitas/QR lewat form angka + pratinjau
   langsung, lalu pilih template mana yang dipakai per periode.

---

## 2. Yang Perlu Sudah Terpasang

- **Python 3.10+**
- **VS Code** dengan extension Python (opsional tapi disarankan)
- **Poppler** — hanya diperlukan kalau Anda mengunggah template sertifikat
  dalam format **PDF** (dipakai untuk mengonversinya ke gambar resolusi
  tinggi). Kalau selalu mengunggah template dalam format **PNG/JPG**
  langsung, Poppler tidak diperlukan sama sekali.
  - Windows: `choco install poppler` (via [Chocolatey](https://chocolatey.org)), atau unduh binary dari
    https://github.com/oschwartz10612/poppler-windows/releases dan tambahkan folder `bin`-nya ke PATH.
  - macOS: `brew install poppler`
  - Linux (Debian/Ubuntu): `sudo apt install poppler-utils`
- **Tesseract OCR** — dipakai untuk fitur **Deteksi Otomatis** posisi
  field saat mengunggah template sertifikat baru (lihat Bagian 5). Kalau
  dilewati/tidak terpasang, fitur ini otomatis gagal dengan pesan jelas
  dan Anda tetap bisa kalibrasi manual sepenuhnya seperti biasa.
  - Windows: unduh installer dari https://github.com/UB-Mannheim/tesseract/wiki, lalu tambahkan folder instalasinya ke PATH.
  - macOS: `brew install tesseract`
  - Linux (Debian/Ubuntu): `sudo apt install tesseract-ocr`
- **Node.js** — **TIDAK WAJIB** untuk menjalankan aplikasi (file CSS/JS
  sudah di-build dan disertakan). Hanya diperlukan kalau Anda ingin
  mengubah tampilan (menambah kelas Tailwind baru) dan build ulang CSS-nya
  — lihat bagian 6.

## 3. Langkah Menjalankan di VS Code

```bash
# 1. Buka folder proyek di VS Code, lalu buka terminal (Ctrl+`)

# 2. Buat & aktifkan virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Install dependency Python
pip install -r requirements.txt

# 4. Siapkan file konfigurasi
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux

# 5. Siapkan database + data contoh (8 peserta, 1 template bawaan)
python scripts/seed.py

# 6. Jalankan server
python run.py
```

Buka `http://127.0.0.1:5000`:
- **Sisi peserta**: `http://127.0.0.1:5000/ambil-sertifikat` — gunakan
  salah satu data yang dicetak oleh `scripts/seed.py` di terminal.
- **Sisi admin**: `http://127.0.0.1:5000/admin` (login: `admin` / `admin123`)

---

## 4. Format File Excel Data Peserta

Kolom yang dibutuhkan (nama kolom di baris pertama, tidak peka besar-kecil huruf):

| Nama | NIM | Fakultas | Universitas | Email | No. WA |
|---|---|---|---|---|---|
| Muhammad Naufal Nashir | 2305110041 | Ilmu Komputer | Universitas Diponegoro | naufal@example.com | 081234567890 |

Bisa diunduh langsung dari panel admin (tombol "Unduh contoh file" di
halaman Buat Periode / Data Peserta), atau lewat `/admin/contoh-excel`.
Nomor WA format `08xxx` otomatis dinormalisasi ke `62xxx` oleh sistem.

---

## 5. Template Sertifikat: Cara Kerja & Tips Kualitas

Setiap desain sertifikat disimpan sebagai satu **TemplateSertifikat** —
gambar latar + konfigurasi posisi tiap elemen (disimpan sebagai **pecahan
0–1** relatif terhadap lebar/tinggi gambar, bukan koordinat piksel tetap —
supaya template resolusi berapa pun bisa dipakai dengan sistem kalibrasi
yang sama).

**Mengunggah template baru** (`/admin/template/baru`):
1. Unggah file PDF/PNG/JPG — **disarankan resolusi tinggi** (setara 300
   DPI, lebar ≥ 2400px untuk ukuran A4) supaya hasil cetak tajam (HD).
   Sistem otomatis memperingatkan kalau resolusi terlalu rendah.
2. Ada dua cara menyiapkan posisi teks, boleh pilih salah satu:
   - **Desain masih ada label placeholder** (mis. tertulis "Nama
     Mahasiswa", "NIM", "Fakultas", "Universitas") — sistem **otomatis
     mencoba mendeteksi posisinya** lewat OCR (Tesseract) begitu
     diunggah, sekaligus membersihkan areanya. Label berfont biasa
     (NIM/Fakultas/Universitas) biasanya terdeteksi andal (>90%
     confidence pada pengujian); label berfont kaligrafi/miring (umum
     dipakai untuk placeholder nama) sering tidak terbaca OCR - bagian
     yang tidak terdeteksi dilaporkan jelas ke admin dan tinggal diisi
     manual di halaman kalibrasi.
   - **Desain sudah polos** (tanpa teks apa pun) — deteksi otomatis
     tidak menemukan apa-apa (tidak masalah), langsung atur semua posisi
     manual di halaman kalibrasi.
3. (Opsional) Unggah font kustom (.ttf/.otf) untuk nama & identitas. Kalau
   dikosongkan, sistem memakai font bawaan (Pinyon Script + Cardo).

**Mengalibrasi posisi** (`/admin/template/<id>/kalibrasi`):
- Tombol **"🔍 Coba Deteksi Otomatis dari Label Placeholder"** — bisa
  dijalankan ulang kapan saja kalau ingin mencoba lagi (mis. setelah
  mengganti file gambar template).
- Form angka untuk tiap field (posisi X/Y, lebar maksimum, ukuran font,
  warna) — semua dalam pecahan 0–1.
- Tombol **"🧹 Bersihkan Area Ini"** per field — untuk field yang tidak
  (atau salah) terdeteksi otomatis, membersihkan area gambar di sekitar
  posisi X/Y yang sedang diisi di form (berguna khususnya untuk field
  Nama yang placeholder aslinya bergaya kaligrafi). **Perubahan ini
  permanen pada file gambar** - kalau area yang terhapus kurang/berlebih,
  perlu unggah ulang template dari awal dan coba lagi dengan posisi yang
  disesuaikan (belum ada fitur "undo").
- Tombol **"Render Uji Coba"** merender pratinjau langsung dengan data
  contoh (tanpa menyimpan) lewat AJAX, supaya Anda bisa menyesuaikan
  angka sambil melihat hasilnya real-time sebelum yakin untuk **"Simpan
  Kalibrasi"**.
- Nama & baris identitas otomatis mengecil ukurannya kalau teksnya
  terlalu panjang untuk lebar maksimum yang diatur (fitur auto-fit,
  warisan dari kalibrasi template pertama).

**Memilih template per periode**: dropdown "Template Sertifikat" saat
membuat periode baru, atau lewat "⚙ Pengaturan Periode" di halaman detail
periode kapan saja (berguna kalau ingin ganti desain di tengah periode
berjalan).

---

## 6. Kenapa Tailwind/Alpine/Flatpickr Di-build Lokal, Bukan CDN?

Versi awal prototipe ini memakai CDN langsung (`cdn.tailwindcss.com`,
`unpkg.com`, dst). Setelah dipikir ulang, ini **kurang cocok untuk sistem
instansi pemerintah**:

- Kalau jaringan kantor memblokir domain CDN eksternal (umum di firewall
  instansi), **seluruh tampilan aplikasi rusak total** — bukan cuma
  kurang cantik, tapi form/tombol bisa tidak berfungsi.
- `cdn.tailwindcss.com` ("Play CDN") **secara resmi tidak disarankan
  untuk produksi** oleh Tailwind sendiri — dia meng-compile CSS di
  browser setiap kali halaman dibuka, lebih lambat dari file CSS statis.
- Sistem jadi bergantung pada koneksi internet aktif untuk hal yang
  sebenarnya tidak perlu online sama sekali.

**Solusinya**: semua file CSS/JS (Tailwind, Alpine.js, Flatpickr) sudah
di-**build sekali** dan disimpan sebagai file statis di `app/static/` —
disertakan langsung di proyek ini. Aplikasi berjalan **100% tanpa
internet** untuk bagian tampilannya.

**Kalau ingin mengubah tampilan** (menambah class Tailwind baru di HTML)
dan build ulang CSS-nya:
```bash
npm install
npx tailwindcss -i app/static/css/tailwind_input.css -o app/static/css/tailwind.css --minify
```
(Hanya diperlukan sekali setiap kali mengubah class di file `app/templates/*.html` yang belum pernah dipakai sebelumnya.)

---

## 7. Solusi: Template Tidak Memiliki Field Nomor Sertifikat

Template resmi tidak mencantumkan field/baris khusus untuk nomor surat.
Solusinya (lihat `app/utils.py` → `buat_no_ref`):

1. Sistem tetap membuat **No. Ref** otomatis & berurutan (format
   `001/PTJT.6/Mag.6/VIII/2026`) begitu data peserta diunggah — bukan
   menunggu peserta mengklaim — sehingga selalu terlihat di tabel admin
   sejak awal.
2. Ditempel kecil & rapi di **pojok kanan atas** sertifikat bersama Kode
   Verifikasi, tanpa mengubah tata letak resmi.
3. Di-encode sebagai **QR code** di pojok kiri bawah, mengarah ke halaman
   `/cek-sertifikat` untuk verifikasi pihak ketiga (mis. HRD).
4. Penomoran bersifat **global** (lintas periode) supaya tidak ada dua
   sertifikat dengan nomor kembar meskipun dibuat di bulan yang sama pada
   periode berbeda.

---

## 8. Mengaktifkan OTP WhatsApp Sungguhan

Saat ini (`WA_DEMO_MODE=true`), kode OTP ditampilkan langsung di layar
karena belum terhubung ke WhatsApp API sungguhan. Untuk mengaktifkan:

1. Daftar **Meta Business Manager** → WhatsApp Business Platform (Cloud
   API resmi dari Meta), atau gunakan Business Solution Provider (BSP)
   lokal seperti **Api.co.id** yang mem-wrap Cloud API resmi dengan biaya
   langganan tetap tanpa markup per pesan (~Rp100rb/bulan) — **hindari
   layanan "unofficial" seperti Fonnte/Wablas** untuk sistem resmi
   instansi, karena melanggar ToS WhatsApp dan berisiko nomor diblokir
   sewaktu-waktu tanpa peringatan.
2. Buat template pesan WA (perlu disetujui Meta lebih dulu, proses
   1-2 hari kerja) untuk isi OTP.
3. Isi `.env`:
   ```
   WA_DEMO_MODE=false
   WA_PHONE_NUMBER_ID=...
   WA_ACCESS_TOKEN=...
   ```
4. Lengkapi isi fungsi `kirim_wa_otp()` di `app/utils.py` — sudah ada
   contoh kode pemanggilan Meta Cloud API di komentarnya.

## 9. Mengaktifkan Pengiriman Email Sertifikat Sungguhan

Saat ini (`EMAIL_DEMO_MODE=true`), file PDF disimpan ke `data/generated/`
dan bisa diunduh lewat tombol demo di halaman konfirmasi. Untuk
mengaktifkan pengiriman email sungguhan, isi `.env`:
```
EMAIL_DEMO_MODE=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=akun@domain.go.id
SMTP_PASSWORD=app-password-anda
SMTP_FROM=no-reply@kejati-jateng.go.id
```
Fungsi pengirimnya (`kirim_sertifikat_email` di `app/utils.py`) sudah
melampirkan file PDF secara otomatis — tidak perlu kode tambahan.
**Catatan Gmail**: perlu "App Password" (bukan password akun biasa),
dibuat lewat pengaturan keamanan akun Google.

---

## 10. Struktur Folder

```
sertifikat-magang-kejati/
├── run.py                       # jalankan ini untuk start server
├── config.py                    # semua pengaturan (baca dari .env)
├── requirements.txt
├── .env.example
├── package.json, tailwind.config.js   # hanya dipakai saat build ulang CSS
├── app/
│   ├── __init__.py               # app factory Flask
│   ├── models.py                 # Periode, TemplateSertifikat, Peserta, OtpCode
│   ├── utils.py                  # nomor sertifikat, OTP WA, email, import Excel
│   ├── routes_admin.py           # semua route /admin/...
│   ├── routes_public.py          # semua route publik (/ambil-sertifikat, dst.)
│   ├── certgen/generator.py      # inti penempelan teks (berbasis pecahan 0-1)
│   ├── assets/
│   │   ├── fonts/                 # font bawaan (PinyonScript, Cardo)
│   │   ├── template/               # template bawaan (clean_bg.png)
│   │   ├── template_uploads/       # template custom yang diunggah admin
│   │   └── font_uploads/           # font custom yang diunggah admin
│   ├── static/
│   │   ├── css/tailwind.css        # hasil build Tailwind (statis)
│   │   └── js/alpine.min.js, flatpickr.min.js  # vendor JS (statis)
│   └── templates/                 # halaman HTML (admin/ & public/)
├── scripts/
│   ├── data_contoh.py             # 8 data dummy peserta
│   └── seed.py                    # isi database awal + template bawaan
└── data/
    ├── sertifikat.db              # dibuat otomatis oleh seed.py
    └── generated/                 # PDF hasil generate (mode demo)
```

## 11. Keamanan yang Sudah Diimplementasikan

- Kombinasi Nama + NIM + No. WA harus **sama persis** dengan data admin
  sebelum OTP dikirim (mencegah tebak-NIM saja).
- Kode OTP di-hash (bukan teks polos), kedaluwarsa otomatis (default 5
  menit), maksimal 5x percobaan salah sebelum harus minta kode baru.
- Sertifikat hanya bisa diklaim **satu kali** per peserta.
- Nomor sertifikat & kode verifikasi bisa dicek publik lewat
  `/cek-sertifikat` untuk transparansi ke pihak ketiga.
- Login admin terpisah dari akses peserta (session-based).

**Catatan jujur soal keamanan produksi**: ganti `SECRET_KEY` di `.env`
dengan string acak panjang, aktifkan HTTPS, dan pertimbangkan menambah
CAPTCHA pada form klaim untuk mencegah percobaan otomatis oleh bot.

---

## 12. Migrasi ke Supabase (untuk Produksi)

SQLite dipakai untuk tahap demo/uji coba karena nol-konfigurasi. Begitu
sistem mau dipakai sungguhan oleh banyak admin dari lokasi berbeda,
berikut alur migrasi ke **Supabase** (PostgreSQL terkelola):

### Langkah 1 — Buat Project Supabase
1. Daftar di https://supabase.com, buat project baru (pilih region
   Singapore untuk latensi terbaik dari Indonesia).
2. Di **Project Settings → Database**, salin **Connection String** mode
   "Session pooler" (format `postgresql://postgres.xxxx:[PASSWORD]@...:5432/postgres`).

### Langkah 2 — Sesuaikan Kode
```bash
pip install psycopg2-binary
```
Update `.env`:
```
DATABASE_URL=postgresql://postgres.xxxx:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
```
Karena proyek ini sudah memakai **SQLAlchemy** sebagai lapisan database,
**tidak ada kode di `models.py`, `routes_admin.py`, dll. yang perlu
ditulis ulang** — cukup ganti baris `DATABASE_URL` ini saja.

### Langkah 3 — Buat Tabel di Supabase
```bash
python scripts/seed.py
```
`db.create_all()` di dalam `create_app()` otomatis membuat seluruh tabel
di database Supabase yang baru (sama seperti saat membuat `sertifikat.db`
lokal), lalu `seed.py` mengisi template bawaan + data contoh seperti
biasa.

### Langkah 4 — Pindahkan Penyimpanan File
File template & sertifikat yang diunggah (`app/assets/template_uploads/`,
`data/generated/`) tersimpan di **disk lokal server** — ini **tidak
cocok** untuk hosting cloud modern (mis. Render, Railway, Fly.io) yang
disk-nya bersifat sementara (hilang saat server restart/redeploy).
Untuk produksi, pindahkan penyimpanan file ke **Supabase Storage**:
1. Di dashboard Supabase, buat bucket baru (mis. `template-sertifikat`).
2. Ganti `file_desain.save(raw_path)` di `routes_admin.py` dengan
   pemanggilan Supabase Storage API (`supabase-py` — `pip install
   supabase`), lalu simpan **URL publik/signed URL**-nya di kolom
   `preview_path` alih-alih path lokal.
3. Modul `certgen/generator.py` perlu sedikit disesuaikan supaya
   `Image.open(preview_path)` bisa membaca dari URL (unduh dulu ke
   memori) alih-alih path file lokal langsung.

### Langkah 5 — Hosting Aplikasi Flask-nya Sendiri
Supabase menyediakan database, bukan hosting aplikasi Flask itu sendiri.
Pilihan yang umum dipakai untuk hosting Flask + Supabase:
- **Render.com** (ada free tier, mudah dari GitHub)
- **Railway.app**
- Server milik instansi sendiri (VPS internal), dengan Flask dijalankan
  lewat **Gunicorn** + reverse proxy **Nginx** (bukan `python run.py`
  langsung, yang hanya untuk pengembangan).

### Ringkasan Kapan Pindah ke Supabase
| Situasi | Rekomendasi |
|---|---|
| Uji coba/demo ke atasan, 1 admin | SQLite (sekarang) — cukup |
| Dipakai beberapa admin dari lokasi berbeda | Supabase — data perlu terpusat |
| Volume peserta sangat besar / banyak periode berjalan bersamaan | Supabase — SQLite tidak ideal untuk akses tulis bersamaan (concurrent write) |
| Perlu backup otomatis, dashboard monitoring | Supabase — sudah bawaan |

---

## 13. Tahapan Implementasi ke Depan

| Tahap | Status |
|---|---|
| Alur verifikasi Nama+NIM+WA → OTP WA → email sertifikat | ✓ Selesai & teruji |
| Manajemen periode + upload Excel dalam satu langkah | ✓ Selesai & teruji |
| Tabel Data Peserta ringkas (No.Ref/Nama/NIM/Akun/Waktu/Status/Aksi) | ✓ Selesai & teruji |
| Manajemen Template Sertifikat (upload + kalibrasi + live preview) | ✓ Selesai & teruji |
| Tampilan modern (Tailwind + Alpine + Flatpickr, build lokal) | ✓ Selesai |
| Integrasi WhatsApp API sungguhan | Menunggu akun WhatsApp Business instansi |
| Integrasi SMTP email sungguhan | Menunggu akses SMTP/App Password instansi |
| Migrasi ke Supabase (kalau dipakai multi-admin) | Menunggu keputusan skala pemakaian |
| Hosting produksi (Render/VPS instansi) | Menunggu keputusan lingkungan hosting |
