"""
app/utils.py
============
Fungsi bantu: penomoran sertifikat, OTP via WhatsApp, pengiriman
sertifikat via email, dan pembacaan file Excel data peserta.

>>> ALUR VERIFIKASI (v2) <<<
Peserta memasukkan Nama + NIM + No. WhatsApp pada portal publik. Kalau
cocok dengan data yang diunggah admin, kode OTP dikirim ke NOMOR
WHATSAPP tersebut. Begitu OTP benar, sertifikat PDF langsung dibuat dan
DIKIRIM SEBAGAI LAMPIRAN EMAIL ke alamat yang terdaftar (bukan diunduh
langsung dari browser) - meniru pola pengiriman sertifikat bootcamp/
seminar resmi, sekaligus memberi jejak pengiriman yang formal.

>>> SOLUSI NOMOR SERTIFIKAT <<<
Nomor referensi (No. Ref) & kode verifikasi dibuat SEKALI saat admin
mengunggah data peserta (lihat proses_upload_peserta di bawah), bukan
menunggu peserta mengklaim. Ini membuat "No. Ref" selalu terlihat di
tabel admin sejak data diunggah, dan nomor tersebut yang sama persis
dipakai sebagai "No. Sertifikat" begitu file PDF akhirnya dibuat.
"""
import random
import secrets
import string
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Peserta, OtpCode

ROMAWI_BULAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


# --------------------------------------------------------------- nomor --
def _nomor_urut_berikutnya(periode_id):
    """Penting: dihitung secara GLOBAL (bukan hanya dalam satu periode),
    karena format No. Ref menyertakan bulan+tahun yang sama untuk semua
    periode yang dibuat di bulan yang sama - kalau dihitung per periode
    saja, dua periode berbeda di bulan yang sama bisa menghasilkan No.
    Ref kembar (mis. dua-duanya "001/PTJT.6/Mag.6/VIII/2026") dan
    melanggar constraint UNIQUE di database."""
    jumlah = Peserta.query.count()
    return jumlah + 1


def buat_no_ref(periode_id, tanggal=None):
    tanggal = tanggal or datetime.utcnow()
    urut = _nomor_urut_berikutnya(periode_id)
    return f"{urut:03d}/PTJT.6/Mag.6/{ROMAWI_BULAN[tanggal.month]}/{tanggal.year}"


def buat_kode_verifikasi():
    tahun = str(datetime.utcnow().year)[-2:]
    acak = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"KT{tahun}-{acak}"


# ---------------------------------------------------------- import data --
KOLOM_WAJIB = ["nama", "nim", "fakultas", "universitas", "email", "no_wa"]

# Nama kolom alternatif yang diterima di file Excel (tidak peka huruf besar/kecil)
ALIAS_KOLOM = {
    "nama": ["nama", "nama lengkap", "nama peserta"],
    "nim": ["nim", "nomor induk", "nim/nomor induk", "no induk"],
    "fakultas": ["fakultas"],
    "universitas": ["universitas", "kampus", "perguruan tinggi"],
    "email": ["email", "email terdaftar", "alamat email"],
    "no_wa": ["no_wa", "no wa", "nomor wa", "whatsapp", "no whatsapp", "no. wa", "nomor whatsapp"],
}


def _cocokkan_kolom(header_baris):
    """header_baris: list nama kolom mentah dari baris pertama Excel.
    Mengembalikan dict {field_internal: index_kolom}."""
    header_bersih = [str(h).strip().lower() if h else "" for h in header_baris]
    hasil = {}
    for field, alias_list in ALIAS_KOLOM.items():
        for idx, h in enumerate(header_bersih):
            if h in alias_list:
                hasil[field] = idx
                break
    return hasil


def baca_excel_peserta(file_stream):
    """Baca file .xlsx dan kembalikan list dict {nama, nim, fakultas,
    universitas, email, no_wa}. Melempar ValueError dengan pesan jelas
    kalau ada kolom wajib yang tidak ditemukan.

    Baris header (Nama/NIM/dst.) TIDAK harus persis di baris pertama -
    fungsi ini memindai beberapa baris pertama untuk menemukannya, supaya
    file yang punya judul/keterangan di atas tabel (seperti contoh yang
    diunduh dari "Unduh contoh file") tetap terbaca dengan benar."""
    from openpyxl import load_workbook

    wb = load_workbook(file_stream, read_only=True, data_only=True)
    ws = wb.active
    semua_baris = list(ws.iter_rows(values_only=True))

    if not semua_baris:
        raise ValueError("File Excel kosong.")

    BATAS_PINDAI = 10  # cukup untuk menampung judul/keterangan di atas tabel
    kolom_map = None
    baris_header_ke = None
    for idx, baris in enumerate(semua_baris[:BATAS_PINDAI]):
        percobaan = _cocokkan_kolom(baris)
        if all(f in percobaan for f in KOLOM_WAJIB):
            kolom_map = percobaan
            baris_header_ke = idx
            break

    if kolom_map is None:
        raise ValueError(
            "Baris header (Nama, NIM, Fakultas, Universitas, Email, No. WA) tidak "
            "ditemukan di " + str(BATAS_PINDAI) + " baris pertama file Excel. "
            "Pastikan nama kolom tsb ada persis sebagai satu baris di dekat "
            "bagian atas file, lalu coba unggah ulang."
        )

    baris_iter = iter(semua_baris[baris_header_ke + 1:])

    hasil = []
    for baris in baris_iter:
        if baris is None or all(v is None or str(v).strip() == "" for v in baris):
            continue  # lewati baris kosong
        row = {
            field: (str(baris[idx]).strip() if baris[idx] is not None else "")
            for field, idx in kolom_map.items()
        }
        if not row["nama"] or not row["nim"]:
            continue
        hasil.append(row)
    return hasil


def proses_upload_peserta(periode, data_rows):
    """Simpan banyak baris peserta sekaligus ke satu periode, sekaligus
    membuatkan No. Ref & kode verifikasi untuk masing-masing. Melewati
    baris yang NIM-nya sudah ada di periode yang sama (mencegah duplikat
    kalau file diunggah dua kali).

    Mengembalikan (jumlah_ditambahkan, jumlah_dilewati)."""
    ditambahkan, dilewati = 0, 0
    nim_ada = {p.nim for p in periode.peserta}

    for row in data_rows:
        if row["nim"] in nim_ada:
            dilewati += 1
            continue
        p = Peserta(
            periode_id=periode.id,
            nama=row["nama"], nim=row["nim"],
            fakultas=row["fakultas"], universitas=row["universitas"],
            email=row["email"].lower(), no_wa=_normalisasi_no_wa(row["no_wa"]),
            no_ref=buat_no_ref(periode.id),
            kode_verifikasi=buat_kode_verifikasi(),
        )
        db.session.add(p)
        nim_ada.add(row["nim"])
        ditambahkan += 1

    db.session.commit()
    return ditambahkan, dilewati


def _normalisasi_no_wa(no_wa):
    """Rapikan format nomor WA: buang spasi/strip, ubah awalan 0 -> 62."""
    bersih = "".join(ch for ch in no_wa if ch.isdigit() or ch == "+")
    bersih = bersih.replace("+", "")
    if bersih.startswith("0"):
        bersih = "62" + bersih[1:]
    return bersih


# ------------------------------------------------------------------ OTP --
def cari_peserta_untuk_verifikasi(nama, nim, no_wa):
    """Cari peserta yang cocok Nama + NIM + No. WA di SEMUA periode
    (peserta tidak perlu tahu/pilih periode-nya sendiri). Pencocokan nama
    tidak peka besar-kecil huruf & spasi berlebih; NIM & No. WA harus
    identik setelah dinormalisasi."""
    nim_bersih = nim.strip()
    wa_bersih = _normalisasi_no_wa(no_wa)
    nama_bersih = " ".join(nama.strip().lower().split())

    kandidat = Peserta.query.filter_by(nim=nim_bersih).all()
    for p in kandidat:
        nama_p = " ".join(p.nama.strip().lower().split())
        if nama_p == nama_bersih and p.no_wa == wa_bersih:
            return p
    return None


def buat_dan_kirim_otp(peserta, expiry_minutes=5, demo_mode=True):
    """Buat kode OTP 6 digit baru untuk peserta, simpan hash-nya, dan
    kirim ke WhatsApp peserta (atau tampilkan di layar bila demo_mode)."""
    kode = f"{random.randint(0, 999999):06d}"

    otp = OtpCode(
        peserta_id=peserta.id,
        kedaluwarsa_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
    )
    otp.set_kode(kode)
    if demo_mode:
        otp.kode_plain_demo = kode
    db.session.add(otp)
    db.session.commit()

    if demo_mode:
        print(f"[DEMO] Kode OTP WhatsApp untuk {peserta.no_wa}: {kode} (berlaku {expiry_minutes} menit)")
    else:
        kirim_wa_otp(peserta.no_wa, kode, expiry_minutes)

    return otp


def kirim_wa_otp(no_wa_tujuan, kode, expiry_minutes):
    """Titik integrasi WhatsApp API. Ganti isi fungsi ini dengan
    pemanggilan API WhatsApp resmi (Meta Cloud API, langsung atau lewat
    Business Solution Provider) saat WA_DEMO_MODE=false. Contoh dengan
    Meta Cloud API (butuh WA_PHONE_NUMBER_ID & WA_ACCESS_TOKEN di .env):

        import requests
        url = f"https://graph.facebook.com/v20.0/{WA_PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": no_wa_tujuan,
            "type": "template",
            "template": {"name": "otp_sertifikat", "language": {"code": "id"}, ...}
        }
        requests.post(url, headers=headers, json=payload)

    Pesan WA berbasis template harus didaftarkan & disetujui lebih dulu
    di Meta Business Manager sebelum bisa dipakai - lihat README bagian
    "Mengaktifkan OTP WhatsApp Sungguhan" untuk langkah lengkapnya.
    """
    raise RuntimeError(
        "Integrasi WhatsApp API belum dikonfigurasi. Set WA_DEMO_MODE=true "
        "di .env untuk mode demo, atau lengkapi kirim_wa_otp() di app/utils.py "
        "dengan kredensial WhatsApp API instansi."
    )


# ------------------------------------------------------- kirim sertifikat --
def kirim_sertifikat_email(peserta, pdf_bytes, demo_mode=True):
    """Kirim file PDF sertifikat sebagai lampiran email resmi ke alamat
    terdaftar. Mode demo: file disimpan ke data/generated/ supaya tetap
    bisa diperiksa hasilnya tanpa SMTP asli (lihat route demo di
    routes_public.py)."""
    import os
    from flask import current_app

    if demo_mode:
        out_dir = os.path.join(current_app.root_path, "..", "data", "generated")
        os.makedirs(out_dir, exist_ok=True)
        filename = f"{peserta.no_ref.replace('/', '_')}.pdf"
        with open(os.path.join(out_dir, filename), "wb") as f:
            f.write(pdf_bytes)
        print(f"[DEMO] Sertifikat untuk {peserta.email} disimpan di data/generated/{filename}")
        return filename

    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication

    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        raise RuntimeError(
            "SMTP belum dikonfigurasi. Isi SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD "
            "di .env, atau set EMAIL_DEMO_MODE=true untuk mode demo."
        )

    pesan = MIMEMultipart()
    pesan["Subject"] = "Sertifikat Magang Resmi — Kejaksaan Tinggi Jawa Tengah"
    pesan["From"] = cfg["SMTP_FROM"]
    pesan["To"] = peserta.email

    isi = (
        f"Yth. {peserta.nama},\n\n"
        f"Selamat! Identitas Anda telah berhasil diverifikasi. Bersama email ini "
        f"kami lampirkan sertifikat resmi magang Anda di lingkungan Kejaksaan "
        f"Tinggi Jawa Tengah.\n\n"
        f"No. Sertifikat   : {peserta.no_ref}\n"
        f"Kode Verifikasi  : {peserta.kode_verifikasi}\n\n"
        f"Keaslian sertifikat ini dapat diverifikasi kapan saja melalui kode QR "
        f"pada sertifikat, atau melalui halaman resmi kami dengan memasukkan "
        f"kode verifikasi di atas.\n\n"
        f"Terima kasih atas kontribusi Anda selama masa magang.\n\n"
        f"Hormat kami,\n"
        f"Bidang Pembinaan\n"
        f"Kejaksaan Tinggi Jawa Tengah\n\n"
        f"--\n"
        f"Email ini dikirim otomatis oleh sistem, mohon tidak membalas ke alamat ini."
    )
    pesan.attach(MIMEText(isi, "plain"))

    lampiran = MIMEApplication(pdf_bytes, _subtype="pdf")
    lampiran.add_header("Content-Disposition", "attachment",
                         filename=f"Sertifikat_Magang_{peserta.nama.replace(' ', '_')}.pdf")
    pesan.attach(lampiran)

    with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
        server.starttls()
        server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
        server.sendmail(cfg["SMTP_FROM"], [peserta.email], pesan.as_string())
    return None
