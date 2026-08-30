"""
scripts/migrasi_font_tanggal.py
================================
Migrasi SEKALI-JALAN untuk fitur "Tanggal Terbit" dinamis di sertifikat.

Kenapa perlu skrip ini: aplikasi memakai db.create_all() saat start, yang
HANYA membuat tabel yang belum ada - tidak mengubah struktur tabel yang
sudah ada. Karena kolom baru font_tanggal_path ditambahkan ke model
TemplateSertifikat (lihat app/models.py), database SQLite yang sudah
terlanjur jalan sebelumnya perlu di-ALTER manual satu kali supaya kolom
itu benar-benar ada di file .db, sebelum aplikasi bisa membaca/menulis
ke kolom tersebut.

Aman dijalankan berkali-kali (idempotent) - kalau kolom sudah ada,
skrip langsung berhenti tanpa melakukan apa-apa. Data template/periode/
peserta yang sudah ada TIDAK disentuh sama sekali.

Cara pakai (dari folder root project, venv aktif):
    python scripts/migrasi_font_tanggal.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

DB_PATH = Config.SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database belum ada di {DB_PATH} - tidak perlu migrasi, "
              f"jalankan aplikasi seperti biasa (db.create_all() akan "
              f"otomatis membuat semuanya dengan struktur terbaru).")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("PRAGMA table_info(template_sertifikat)")
    kolom_ada = {row[1] for row in cur.fetchall()}

    if "font_tanggal_path" in kolom_ada:
        print("Kolom font_tanggal_path sudah ada - tidak ada yang perlu dimigrasi.")
        con.close()
        return

    cur.execute("ALTER TABLE template_sertifikat ADD COLUMN font_tanggal_path VARCHAR(300)")
    con.commit()
    con.close()
    print("Berhasil: kolom font_tanggal_path ditambahkan ke tabel template_sertifikat.")
    print("Semua template yang sudah ada otomatis punya nilai NULL di kolom ini")
    print("(artinya pakai font bawaan/Cardo Regular untuk tanggal, sampai Anda")
    print("mengunggah font khusus lewat halaman Unggah Template Baru).")


if __name__ == "__main__":
    main()
