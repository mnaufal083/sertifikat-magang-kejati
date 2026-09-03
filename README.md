# Sistem Sertifikat Magang Otomatis — Kejaksaan Tinggi Jawa Tengah

Aplikasi web **full-stack** yang bisa langsung dijalankan, mengimplementasikan
alur verifikasi **Nama + NIM + Email (pencocokan identitas) → OTP via
Email → Sertifikat dikirim ke Email**. Kode OTP dan file sertifikat
sama-sama dikirim ke **email** peserta, karena satu jalur SMTP yang sama
bisa dipakai untuk keduanya (lebih murah & lebih sederhana dibanding
kanal lain yang berbayar per pesan). Backend: **Flask (Python)** +
**SQLite**. Tampilan: **Tailwind CSS + Alpine.js + Flatpickr** (di-build
lokal, bukan lewat CDN runtime — lihat penjelasan di bagian 6).

> **Catatan revisi dokumentasi**: versi README ini ditulis ulang
> berdasarkan pembacaan langsung kode di `app/routes_public.py` dan
> `app/utils.py` per Sep 2026, karena draf sebelumnya sempat tidak
> sinkron dengan kode (masih menyebut "No. WhatsApp" sebagai field
> verifikasi, padahal kode sudah dipindah ke Email — lihat Bagian 4b
> untuk detail status field `no_wa` yang masih tersisa di database).

---

## 1. Alur Sistem (Ringkasan)

**Peserta magang:**
1. Buka portal `/ambil-sertifikat`, isi **Nama, NIM, dan Email**.
2. Sistem mencocokkan ketiganya ke data yang diunggah admin (NIM dicari
   persis, Nama & Email dicocokkan tanpa peka besar-kecil huruf/spasi
   berlebih), lalu mengirim kode OTP 6-digit ke **email** peserta yang
   terdaftar.
3. Peserta memasukkan kode OTP (kedaluwarsa 5 menit, maksimal 5x
   percobaan salah sebelum harus minta kode baru).
4. Begitu benar, sertifikat PDF otomatis dibuat dan **dikirim sebagai
   lampiran ke email** yang sama (bukan diunduh langsung dari
   browser) — meniru pola pengiriman sertifikat bootcamp/seminar resmi.
5. Peserta hanya bisa mengklaim satu kali; percobaan berikutnya akan
   ditolak dengan pesan "sudah pernah diambil", dan tersedia tombol
   "Kembali ke Beranda" di halaman hasil supaya alur tidak nyangkut di
   step OTP yang sudah tidak valid.

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
  salah satu data (Nama, NIM, Email) yang dicetak oleh `scripts/seed.py`
  di terminal.
- **Sisi admin**: `http://127.0.0.1:5000/admin` (login: `admin` / `admin123`)

---

## 4. Format File Excel Data Peserta

Kolom yang dibutuhkan (nama kolom di baris pertama, tidak peka besar-kecil huruf):

| Nama | NIM | Fakultas | Universitas | Email | No. WA |
|---|---|---|---|---|---|
| Muhammad Naufal Nashir | 2305110041 | Ilmu Komputer | Universitas Diponegoro | naufal@example.com | 081234567890 |

Bisa diunduh langsung dari panel admin (tombol "Unduh contoh file" di
halaman Buat Periode / Data Peserta), atau lewat `/admin/contoh-excel`.
Nomor WA format `08xxx` otomatis dinormalisasi ke `62xxx` oleh sistem
saat disimpan.

**Kolom `No. WA` tetap wajib diisi di file Excel** (baris upload akan
ditolak kalau kosong) — tapi lihat **Bagian 4b** di bawah untuk
penjelasan kenapa ini sekarang murni data pelengkap, bukan lagi bagian
dari alur verifikasi peserta.

### 4b. Catatan Penting: Status Field "No. WA" (Legacy, Non-Fungsional)

Sistem ini sebelumnya memakai **Nama + NIM + No. WhatsApp** sebagai
kombinasi verifikasi identitas peserta. Ini **sudah diganti ke Nama +
NIM + Email** di kode (`app/routes_public.py` → `kirim_otp()` dan
`app/utils.py` → `cari_peserta_untuk_verifikasi()`), supaya field yang
diminta di awal konsisten dengan email yang memang jadi tujuan
pengiriman OTP & sertifikat.

Namun proses migrasi ini **belum tuntas dibersihkan** dari beberapa
tempat lain:

- Kolom `no_wa` di model `Peserta` (`app/models.py`) **masih ada dan
  wajib diisi** (`nullable=False`).
- Kolom `No. WA` di format Excel **masih wajib** (`KOLOM_WAJIB` di
  `app/utils.py`) — upload akan gagal kalau kolom ini tidak ada.
- Tabel Data Peserta di panel admin masih menampilkannya sebagai kolom
  "Akun/No.WA".
- **Yang penting**: fungsi pencocokan `cari_peserta_untuk_verifikasi()`
  **tidak pernah membaca `no_wa` sama sekali** — hanya query by NIM,
  lalu cocokkan Nama & Email. Jadi No. WA sekarang **tidak berfungsi
  apa pun** dalam alur verifikasi maupun pengiriman; sepenuhnya data
  pasif yang ikut tersimpan dari proses upload Excel.

Ini bagus untuk diketahui sebelum menyesuaikan sistem ke kebutuhan Anda
— kalau institusi Anda tidak butuh mencatat nomor WA peserta sama
sekali, kolom ini aman dihapus dari model, form Excel, dan tampilan
admin tanpa memengaruhi alur verifikasi/OTP/pengiriman sertifikat yang
sudah berjalan lewat Email.

---

## 5. Template Sertifikat: Cara Kerja & Tips Kualitas

Setiap desain sertifikat disimpan sebagai satu **TemplateSertifikat** —
gambar latar + konfigurasi posisi tiap elemen (disimpan sebagai **pecahan
0–1** relatif terhadap lebar/tinggi gambar, bukan koordinat piksel tetap —
supaya template resolusi berapa pun bisa dipakai dengan sistem kalibrasi
yang sama).

**Kualitas PDF (setara "Download PDF Print" di Canva)**: PDF akhir dibuat
lewat `img2pdf`, yang membungkus gambar hasil generate **tanpa kompresi
ulang sama sekali** (lossless). Sebelumnya sistem sempat memakai metode
bawaan Pillow (`Image.save(..., "PDF")`) yang ternyata diam-diam menerapkan
kompresi mirip JPEG saat menyimpan ke PDF — kurang tajam di tepi teks/garis
dekorasi dan ukuran file jadi tidak wajar kecil (~900 KB untuk gambar
3510×2482px). Setelah diganti ke img2pdf, ukuran file naik ke ~8-9 MB
(sesuai kualitas asli yang dipertahankan penuh) dan hasilnya identik piksel
demi piksel dengan gambar yang dirender - tidak ada kompresi tambahan di
tahap mana pun.

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

## 7b. Watermark Anti-Pemalsuan (Perlindungan dari Edit AI/Photoshop)

Selain QR code untuk verifikasi (yang perlu discan secara aktif), sistem
juga menanam **pola teks mikro berulang** di seluruh permukaan sertifikat
(lihat `_tambahkan_watermark_keamanan` di `app/certgen/generator.py`),
sangat transparan (alpha ~14/255) sehingga nyaris tidak terlihat pada
pandangan normal, tapi jelas terbaca kalau dizoom dekat atau kontrasnya
ditingkatkan.

**Kenapa ini membantu**: kalau ada pihak mencoba mengedit nama/NIM pada
file PDF/gambar hasil jadi (mis. pakai AI image-editing atau inpainting
Photoshop) untuk menyalahgunakannya, mereka harus ikut merekonstruksi
pola berulang ini persis di area yang diedit. Ini sangat sulit dilakukan
mulus oleh tools AI/edit manual pada umumnya — hasilnya, area yang
diotak-atik akan terlihat "pecah"/tidak menyambung dengan pola di
sekitarnya saat diperbesar, memberi bukti visual pemalsuan **meski tanpa
perlu scan QR**.

Isi teks pola memakai **kode_verifikasi milik sertifikat itu sendiri**
(bukan teks generik yang sama untuk semua sertifikat) — jadi kalau ada
yang mencoba menyalin pola "bersih" dari satu sertifikat asli untuk
menyamarkan sertifikat palsu lain, kode yang terbaca dalam pola tersebut
tidak akan cocok dengan kode yang tertulis besar di sertifikat itu -
ketidakcocokan ini sendiri jadi bukti forensik tambahan.

Fitur ini otomatis aktif untuk semua sertifikat, termasuk yang dibuat
dari template kustom (bukan cuma template bawaan). Bisa dimatikan per
panggilan lewat parameter `watermark_keamanan=False` di
`generate_certificate_image()` kalau suatu saat diperlukan (tidak ada
kontrol lewat UI untuk ini, karena sifatnya keamanan bawaan sistem).

**Batasan yang perlu diketahui secara jujur**: ini bukan enkripsi atau
tanda tangan digital — sifatnya lebih ke "jejak forensik yang sulit
dipalsukan dengan cepat", bukan "mustahil dipalsukan". Pemalsu yang
sangat teliti dan berdedikasi tinggi (bukan sekadar minta AI generate
ulang) berpotensi tetap bisa merekonstruksinya dengan usaha ekstra. Untuk
perlindungan tingkat lebih tinggi (tanda tangan kriptografi pada file
PDF itu sendiri, yang akan terdeteksi invalid oleh Adobe Acrobat dkk.
kalau file diubah sedikit pun), bisa didiskusikan sebagai pengembangan
lanjutan menggunakan library seperti `pyHanko`.

---

## 8. Mengaktifkan OTP & Pengiriman Email Sertifikat Sungguhan

Kode OTP dan file PDF sertifikat sama-sama dikirim lewat **Email** (SMTP)
— satu jalur pengiriman yang sama dipakai untuk keduanya. No. WhatsApp
peserta **tidak dipakai untuk mengirim apa pun** (lihat Bagian 4b soal
statusnya yang sekarang murni data pelengkap, bukan bagian dari
verifikasi ataupun pengiriman).

Saat ini (`EMAIL_DEMO_MODE=true`), kode OTP ditampilkan langsung di
layar dan file PDF sertifikat disimpan ke `data/generated/` (bisa
diunduh lewat tombol demo di halaman konfirmasi), karena belum
terhubung ke SMTP sungguhan. Untuk mengaktifkan pengiriman email
sungguhan (OTP maupun sertifikat), isi `.env`:
```
EMAIL_DEMO_MODE=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=akun@domain.go.id
SMTP_PASSWORD=app-password-anda
SMTP_FROM=no-reply@kejati-jateng.go.id
```
Fungsi pengirimnya (`kirim_email_otp` untuk kode OTP, `kirim_sertifikat_email`
untuk lampiran PDF — keduanya di `app/utils.py`) sudah lengkap dan
memakai SMTP yang sama — tidak perlu kode tambahan.
**Catatan Gmail**: perlu "App Password" (bukan password akun biasa),
dibuat lewat pengaturan keamanan akun Google.

---

## 9. Struktur Folder

```
sertifikat-magang-kejati/
├── run.py                       # jalankan ini untuk start server
├── config.py                    # semua pengaturan (baca dari .env)
├── requirements.txt
├── .env.example
├── package.json, tailwind.config.js   # hanya dipakai saat build ulang CSS
├── app/
│   ├── __init__.py               # app factory Flask
│   ├── models.py                 # Periode, TemplateSertifikat, Peserta, OtpCode, AdminUser
│   ├── utils.py                  # nomor sertifikat, OTP Email, kirim sertifikat, import Excel
│   ├── routes_admin.py           # semua route /admin/...
│   ├── routes_public.py          # semua route publik (/ambil-sertifikat, dst.)
│   ├── certgen/generator.py      # inti penempelan teks + watermark (berbasis pecahan 0-1)
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

### Peta Endpoint (ringkas)

**Publik** (`routes_public.py`):
| Route | Fungsi |
|---|---|
| `GET /ambil-sertifikat` | Form Nama + NIM + Email |
| `POST /ambil-sertifikat/kirim-otp` | Cocokkan data, kirim OTP ke email |
| `GET/POST /ambil-sertifikat/otp` | Form & verifikasi kode OTP |
| `GET /ambil-sertifikat/terkirim` | Konfirmasi sertifikat sudah dikirim |
| `GET /cek-sertifikat` | Verifikasi keaslian publik via kode verifikasi |
| `GET /demo/unduh/<no_ref_flat>` | Unduh manual hasil generate (khusus `EMAIL_DEMO_MODE=true`) |

**Admin** (`routes_admin.py`, prefix `/admin`, butuh login session):
| Route | Fungsi |
|---|---|
| `GET/POST /login`, `/logout` | Autentikasi admin |
| `GET /periode` | Daftar periode + ringkasan status |
| `GET/POST /periode/baru` | Buat periode + upload Excel peserta (satu form) |
| `GET /periode/<id>` | Detail periode + tabel Data Peserta |
| `POST /periode/<id>/upload-tambahan` | Tambah peserta susulan ke periode yang sudah ada |
| `GET/POST /periode/<id>/edit`, `POST /periode/<id>/hapus` | Kelola periode |
| `POST /peserta/<id>/reset`, `POST /peserta/<id>/hapus` | Kelola peserta individual |
| `GET /template` | Daftar Template Sertifikat |
| `GET/POST /template/baru` | Unggah desain baru (+ deteksi OCR otomatis) |
| `GET /template/<id>/kalibrasi`, `POST .../kalibrasi/simpan` | Kalibrasi posisi field |
| `POST /template/<id>/kalibrasi/preview` | Render uji coba (AJAX, tanpa simpan) |
| `POST /template/<id>/bersihkan-area` | Hapus area gambar (permanen) untuk field tertentu |
| `POST /template/<id>/deteksi-ulang` | Jalankan ulang deteksi OCR |
| `GET /arsip`, `/arsip/<id>` | Arsip periode selesai + unduh sertifikat per peserta |
| `GET /contoh-excel` | Unduh contoh format Excel peserta |

---

## 10. Keamanan yang Sudah Diimplementasikan

- Kombinasi Nama + NIM + Email harus **cocok** dengan data admin sebelum
  OTP dikirim (NIM dicari persis; Nama & Email dicocokkan tanpa peka
  besar-kecil huruf/spasi berlebih) — mencegah tebak-NIM saja.
- Kode OTP di-hash (bukan teks polos), kedaluwarsa otomatis (default 5
  menit), maksimal 5x percobaan salah sebelum harus minta kode baru.
- Sertifikat hanya bisa diklaim **satu kali** per peserta.
- Nomor sertifikat & kode verifikasi bisa dicek publik lewat
  `/cek-sertifikat` untuk transparansi ke pihak ketiga.
- Watermark forensik tertanam di setiap sertifikat (lihat Bagian 7b).
- Login admin terpisah dari akses peserta (session-based).

**Catatan jujur soal keamanan produksi**: ganti `SECRET_KEY` di `.env`
dengan string acak panjang, aktifkan HTTPS, dan pertimbangkan menambah
CAPTCHA pada form klaim untuk mencegah percobaan otomatis oleh bot.

---

## 11. Migrasi ke Supabase (untuk Produksi)

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

## 12. Tahapan Implementasi & Status Dokumentasi

| Tahap | Status |
|---|---|
| Alur verifikasi Nama+NIM+Email (cocokkan) → OTP Email → email sertifikat | ✓ Selesai & teruji |
| Manajemen periode + upload Excel dalam satu langkah | ✓ Selesai & teruji |
| Tabel Data Peserta ringkas (No.Ref/Nama/NIM/Akun/Waktu/Status/Aksi) | ✓ Selesai & teruji |
| Manajemen Template Sertifikat (upload + kalibrasi + live preview) | ✓ Selesai & teruji |
| Watermark forensik anti-pemalsuan | ✓ Selesai |
| Tampilan modern (Tailwind + Alpine + Flatpickr, build lokal) | ✓ Selesai |
| Navigasi "Kembali ke Beranda" di halaman hasil (sukses/sudah diambil) | ✓ Selesai |
| Bersihkan sisa field `no_wa` (model/Excel/tampilan admin) yang sudah tidak dipakai verifikasi | ⚠ Belum — lihat Bagian 4b |
| Integrasi SMTP email sungguhan (OTP & sertifikat) | Menunggu akses SMTP/App Password instansi |
| Migrasi ke Supabase (kalau dipakai multi-admin) | Menunggu keputusan skala pemakaian |
| Hosting produksi (Render/VPS instansi) | Menunggu keputusan lingkungan hosting |
