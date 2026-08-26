import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class Config:
    # Ganti dengan string acak yang panjang saat deploy sungguhan.
    SECRET_KEY = os.environ.get("SECRET_KEY", "ganti-dengan-secret-key-acak-saat-produksi")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(PROJECT_ROOT, "data", "sertifikat.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Kredensial admin demo (username/password sederhana) ---
    # Untuk produksi, pindahkan ke tabel admin_user dengan password hash
    # (sudah disiapkan di models.py -> AdminUser).
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    # --- OTP dikirim via WhatsApp ---
    # MODE DEMO: kode OTP ditampilkan langsung di layar (tanpa WA API asli)
    # supaya sistem bisa dicoba tanpa akun WhatsApp Business.
    WA_DEMO_MODE = os.environ.get("WA_DEMO_MODE", "true").lower() == "true"
    OTP_EXPIRY_MINUTES = 5
    OTP_MAX_ATTEMPTS = 5

    WA_PHONE_NUMBER_ID = os.environ.get("WA_PHONE_NUMBER_ID", "")
    WA_ACCESS_TOKEN = os.environ.get("WA_ACCESS_TOKEN", "")

    # --- Sertifikat dikirim via Email (setelah OTP WA berhasil) ---
    # MODE DEMO: email tidak benar-benar terkirim; file PDF disimpan ke
    # data/generated/ supaya hasilnya tetap bisa diperiksa.
    EMAIL_DEMO_MODE = os.environ.get("EMAIL_DEMO_MODE", "true").lower() == "true"

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@kejati-jateng.go.id")

    # Dipakai untuk membangun URL verifikasi (isi QR code) & tautan lain
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")

    # --- Upload berkas (template sertifikat & font kustom) ---
    UPLOAD_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "app", "assets", "template_uploads")
    UPLOAD_FONT_DIR = os.path.join(PROJECT_ROOT, "app", "assets", "font_uploads")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB, cukup untuk PDF/gambar HD + font
