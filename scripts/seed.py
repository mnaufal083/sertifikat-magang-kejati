"""
scripts/seed.py
================
Menyiapkan database demo dari nol:
  1. Membuat tabel-tabel database.
  2. Mendaftarkan template sertifikat bawaan (desain resmi Kejati Jateng
     yang sudah dikalibrasi presisi sebelumnya) sebagai TemplateSertifikat
     pertama.
  3. Membuat satu periode magang contoh yang memakai template tsb.
  4. Mengisi 8 peserta contoh (lengkap dengan No. Ref & kode verifikasi
     otomatis).

Jalankan sekali di awal:
    python scripts/seed.py

Aman dijalankan berulang - kalau periode contoh sudah ada, dilewati.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Periode, TemplateSertifikat
from app.certgen.generator import DEFAULT_FIELD_CONFIG
from app.utils import proses_upload_peserta
from scripts.data_contoh import DATA_CONTOH

NAMA_PERIODE_CONTOH = "Agustus 2026 (Contoh)"
NAMA_TEMPLATE_BAWAAN = "Sertifikat Resmi Kejati Jateng (Bawaan)"


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        # --- 1. Template bawaan ---
        tpl = TemplateSertifikat.query.filter_by(nama_template=NAMA_TEMPLATE_BAWAAN).first()
        if not tpl:
            preview_path = os.path.join(app.root_path, "assets", "template", "clean_bg.png")
            tpl = TemplateSertifikat(nama_template=NAMA_TEMPLATE_BAWAAN, preview_path=preview_path, aktif=True)
            tpl.set_field_config(DEFAULT_FIELD_CONFIG)
            db.session.add(tpl)
            db.session.commit()
            print(f"Template bawaan '{NAMA_TEMPLATE_BAWAAN}' didaftarkan.")
        else:
            print("Template bawaan sudah ada, dilewati.")

        # --- 2. Periode contoh ---
        periode = Periode.query.filter_by(nama_periode=NAMA_PERIODE_CONTOH).first()
        if periode:
            print("Periode contoh sudah ada, dilewati. (Hapus data/sertifikat.db untuk mulai ulang.)")
            return

        periode = Periode(nama_periode=NAMA_PERIODE_CONTOH, template_id=tpl.id, aktif=True)
        db.session.add(periode)
        db.session.commit()

        # --- 3. Peserta contoh ---
        ditambahkan, _ = proses_upload_peserta(periode, DATA_CONTOH)

        print(f"\nPeriode '{periode.nama_periode}' dibuat dengan {ditambahkan} peserta contoh.")
        print(f"Login admin : {app.config['ADMIN_USERNAME']} / {app.config['ADMIN_PASSWORD']}")
        print(f"Panel admin : {app.config['BASE_URL']}/admin")
        print(f"\nUntuk mencoba sisi peserta, buka {app.config['BASE_URL']}/ambil-sertifikat")
        print("lalu gunakan salah satu data berikut:\n")
        for p in periode.peserta:
            print(f"  Nama: {p.nama:32s} NIM: {p.nim:12s} No. WA: {p.no_wa}")


if __name__ == "__main__":
    main()
