"""
app/models.py
=============
Skema database v2 - disederhanakan sesuai penyesuaian:

  - Peserta tidak lagi punya token/link personal. Verifikasi memakai
    kombinasi Nama + NIM + No. WhatsApp yang dicocokkan ke data yang
    diunggah admin, lalu OTP dikirim ke EMAIL peserta yang terdaftar
    (No. WA hanya dipakai untuk mencocokkan identitas, bukan untuk
    mengirim apa pun - lihat app/utils.py).
  - Nomor referensi (No. Ref / nomor sertifikat) & kode verifikasi
    dibuat sekali saat data diunggah admin, bukan menunggu peserta klaim
    - supaya "No. Ref" selalu terlihat di tabel admin sejak awal.
  - Tabel Sertifikat & LogAkses terpisah dihapus dan digabung langsung
    ke Peserta (status, waktu_diambil) - lebih sederhana, sesuai
    permintaan untuk tidak perlu halaman Log Aktivitas terpisah.
  - Tabel baru: TemplateSertifikat, menyimpan desain sertifikat yang
    bisa diunggah ulang & dikalibrasi posisi teksnya lewat panel admin,
    lalu dipilih per periode.

Tabel:
  - Periode            : satu angkatan/batch magang
  - TemplateSertifikat  : desain sertifikat (bisa lebih dari satu, dipilih per periode)
  - Peserta             : data peserta + status pengambilan sertifikat
  - OtpCode             : kode OTP aktif untuk satu percobaan verifikasi
"""
import json
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class TemplateSertifikat(db.Model):
    __tablename__ = "template_sertifikat"

    id = db.Column(db.Integer, primary_key=True)
    nama_template = db.Column(db.String(150), nullable=False)

    # Gambar latar bersih (hasil upload, sudah dirender ke PNG resolusi
    # tinggi) yang dipakai sebagai kanvas dasar penempelan teks.
    preview_path = db.Column(db.String(300), nullable=False)

    # Font kustom (opsional). Kalau kosong, sistem memakai font bawaan
    # (PinyonScript untuk nama, Cardo Bold/Regular untuk identitas,
    # Cardo Regular untuk tanggal terbit).
    font_nama_path = db.Column(db.String(300), nullable=True)
    font_bold_path = db.Column(db.String(300), nullable=True)
    font_reg_path = db.Column(db.String(300), nullable=True)
    font_tanggal_path = db.Column(db.String(300), nullable=True)

    # Konfigurasi posisi tiap field, disimpan sebagai JSON text. Semua
    # posisi & ukuran disimpan sebagai PECAHAN (0.0-1.0) relatif terhadap
    # lebar/tinggi gambar - supaya template dengan resolusi berapa pun
    # tetap bisa dipakai tanpa hitungan pt/DPI manual. Lihat
    # certgen/generator.py -> DEFAULT_FIELD_CONFIG untuk contoh isinya.
    field_config_json = db.Column(db.Text, nullable=False)

    aktif = db.Column(db.Boolean, default=True)
    dibuat_at = db.Column(db.DateTime, default=datetime.utcnow)

    periode = db.relationship("Periode", backref="template")

    def get_field_config(self):
        return json.loads(self.field_config_json)

    def set_field_config(self, config_dict):
        self.field_config_json = json.dumps(config_dict, indent=2)

    def __repr__(self):
        return f"<TemplateSertifikat {self.nama_template}>"


class Periode(db.Model):
    __tablename__ = "periode"

    id = db.Column(db.Integer, primary_key=True)
    nama_periode = db.Column(db.String(100), nullable=False)
    tanggal_mulai = db.Column(db.Date, nullable=True)
    tanggal_selesai = db.Column(db.Date, nullable=True)

    template_id = db.Column(db.Integer, db.ForeignKey("template_sertifikat.id"), nullable=True)

    aktif = db.Column(db.Boolean, default=True)
    dibuat_at = db.Column(db.DateTime, default=datetime.utcnow)

    peserta = db.relationship("Peserta", backref="periode", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Periode {self.nama_periode}>"


class Peserta(db.Model):
    __tablename__ = "peserta"

    id = db.Column(db.Integer, primary_key=True)
    periode_id = db.Column(db.Integer, db.ForeignKey("periode.id"), nullable=False)

    nama = db.Column(db.String(150), nullable=False)
    nim = db.Column(db.String(30), nullable=False)
    fakultas = db.Column(db.String(100), nullable=False)
    universitas = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    no_wa = db.Column(db.String(20), nullable=False)   # akun verifikasi (tujuan OTP)

    # Nomor referensi & kode verifikasi dibuat begitu data diunggah admin,
    # sehingga langsung terlihat di tabel "Data Peserta" sejak awal.
    no_ref = db.Column(db.String(60), unique=True, nullable=False)
    kode_verifikasi = db.Column(db.String(20), unique=True, nullable=False)

    # belum_diambil -> terkirim (sertifikat sudah dikirim ke email)
    status = db.Column(db.String(20), default="belum_diambil")
    waktu_diambil = db.Column(db.DateTime, nullable=True)

    percobaan_gagal = db.Column(db.Integer, default=0)  # akumulasi seluruh percobaan OTP gagal

    dibuat_at = db.Column(db.DateTime, default=datetime.utcnow)

    otp_list = db.relationship("OtpCode", backref="peserta", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Peserta {self.nama} ({self.nim})>"


class OtpCode(db.Model):
    __tablename__ = "otp_code"

    id = db.Column(db.Integer, primary_key=True)
    peserta_id = db.Column(db.Integer, db.ForeignKey("peserta.id"), nullable=False)

    kode_hash = db.Column(db.String(255), nullable=False)
    dibuat_at = db.Column(db.DateTime, default=datetime.utcnow)
    kedaluwarsa_at = db.Column(db.DateTime, nullable=False)
    terpakai = db.Column(db.Boolean, default=False)
    percobaan_gagal = db.Column(db.Integer, default=0)

    # Hanya diisi & ditampilkan saat EMAIL_DEMO_MODE=True, supaya sistem
    # bisa dicoba tanpa SMTP sungguhan.
    kode_plain_demo = db.Column(db.String(10), nullable=True)

    def set_kode(self, kode):
        self.kode_hash = generate_password_hash(kode)

    def cek_kode(self, kode):
        return check_password_hash(self.kode_hash, kode)

    def kedaluwarsa(self):
        return datetime.utcnow() > self.kedaluwarsa_at


class AdminUser(db.Model):
    """Disiapkan untuk produksi. Demo memakai ADMIN_USERNAME/ADMIN_PASSWORD
    sederhana dari config.py supaya tidak perlu migrasi tambahan saat
    dicoba pertama kali (lihat app/auth.py)."""
    __tablename__ = "admin_user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
