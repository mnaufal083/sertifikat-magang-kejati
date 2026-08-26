"""
app/routes_public.py
=====================
Sisi PESERTA MAGANG (v2):

  1. GET/POST /ambil-sertifikat            -> form Nama + NIM + No. WA
  2. POST     /ambil-sertifikat/kirim-otp  -> cocokkan data, kirim OTP ke WA
  3. GET/POST /ambil-sertifikat/otp        -> form OTP, verifikasi
  4. GET      /ambil-sertifikat/terkirim   -> konfirmasi sertifikat sudah
                                               dikirim ke email

  Tidak ada lagi tautan personal per-peserta (/s/<token>) - peserta cukup
  mengetahui data dirinya sendiri untuk mengklaim sertifikat, mengikuti
  pola portal klaim sertifikat bootcamp/seminar pada umumnya.

Ditambah halaman publik /cek-sertifikat untuk verifikasi keaslian oleh
pihak ketiga berdasarkan kode verifikasi (dicetak di sertifikat / QR code).
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, current_app
)

from app.extensions import db
from app.models import Peserta
from app.utils import (
    cari_peserta_untuk_verifikasi, buat_dan_kirim_otp, kirim_sertifikat_email,
)
from app.certgen.generator import generate_certificate_pdf_bytes

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("public/index.html")


# ------------------------------------------------------- 1. form klaim --
@public_bp.route("/ambil-sertifikat")
def ambil_sertifikat():
    return render_template("public/ambil_sertifikat.html")


# ---------------------------------------------------- 2. cocokkan + OTP -
@public_bp.route("/ambil-sertifikat/kirim-otp", methods=["POST"])
def kirim_otp():
    nama = request.form.get("nama", "").strip()
    nim = request.form.get("nim", "").strip()
    no_wa = request.form.get("no_wa", "").strip()

    if not nama or not nim or not no_wa:
        flash("Nama, NIM, dan No. WhatsApp wajib diisi.", "error")
        return redirect(url_for("public.ambil_sertifikat"))

    peserta = cari_peserta_untuk_verifikasi(nama, nim, no_wa)
    if not peserta:
        flash(
            "Data tidak ditemukan. Pastikan Nama, NIM, dan No. WhatsApp sesuai "
            "dengan yang terdaftar saat magang. Jika masih gagal, hubungi Bidang "
            "Pembinaan Kejaksaan Tinggi Jawa Tengah.", "error"
        )
        return redirect(url_for("public.ambil_sertifikat"))

    if peserta.status == "terkirim":
        return render_template("public/sudah_diambil.html", peserta=peserta)

    otp = buat_dan_kirim_otp(
        peserta,
        expiry_minutes=current_app.config["OTP_EXPIRY_MINUTES"],
        demo_mode=current_app.config["WA_DEMO_MODE"],
    )
    session["peserta_id_verifikasi"] = peserta.id
    session["otp_id_verifikasi"] = otp.id

    demo_kode = otp.kode_plain_demo if current_app.config["WA_DEMO_MODE"] else None
    return render_template(
        "public/otp.html", peserta=peserta, demo_kode=demo_kode,
        expiry_minutes=current_app.config["OTP_EXPIRY_MINUTES"],
    )


# --------------------------------------------------------- 3. cek OTP ---
@public_bp.route("/ambil-sertifikat/otp", methods=["GET", "POST"])
def verifikasi_otp():
    from app.models import OtpCode

    peserta_id = session.get("peserta_id_verifikasi")
    otp_id = session.get("otp_id_verifikasi")
    if not peserta_id or not otp_id:
        return redirect(url_for("public.ambil_sertifikat"))

    peserta = Peserta.query.get_or_404(peserta_id)
    otp = OtpCode.query.get_or_404(otp_id)

    if request.method == "GET":
        demo_kode = otp.kode_plain_demo if current_app.config["WA_DEMO_MODE"] else None
        return render_template("public/otp.html", peserta=peserta, demo_kode=demo_kode,
                                expiry_minutes=current_app.config["OTP_EXPIRY_MINUTES"])

    kode_input = "".join(request.form.getlist("digit")).strip() or request.form.get("kode", "").strip()

    if otp.terpakai:
        flash("Kode ini sudah pernah dipakai. Silakan minta kode baru.", "error")
        return redirect(url_for("public.ambil_sertifikat"))

    if otp.kedaluwarsa():
        flash("Kode OTP sudah kedaluwarsa. Silakan minta kode baru.", "error")
        return redirect(url_for("public.ambil_sertifikat"))

    if otp.percobaan_gagal >= current_app.config["OTP_MAX_ATTEMPTS"]:
        flash("Terlalu banyak percobaan salah. Silakan minta kode baru.", "error")
        return redirect(url_for("public.ambil_sertifikat"))

    if not otp.cek_kode(kode_input):
        otp.percobaan_gagal += 1
        peserta.percobaan_gagal += 1
        db.session.commit()
        sisa = current_app.config["OTP_MAX_ATTEMPTS"] - otp.percobaan_gagal
        flash(f"Kode OTP salah. Sisa percobaan: {max(sisa, 0)}.", "error")
        demo_kode = otp.kode_plain_demo if current_app.config["WA_DEMO_MODE"] else None
        return render_template("public/otp.html", peserta=peserta, demo_kode=demo_kode,
                                expiry_minutes=current_app.config["OTP_EXPIRY_MINUTES"])

    # --- sukses: generate PDF & kirim ke email ---
    otp.terpakai = True
    db.session.commit()

    periode = peserta.periode
    tpl = periode.template
    if not tpl:
        flash("Periode ini belum memiliki template sertifikat aktif. Hubungi admin.", "error")
        return redirect(url_for("public.ambil_sertifikat"))

    verify_url = url_for("public.cek_sertifikat", kode=peserta.kode_verifikasi, _external=True)
    pdf_bytes = generate_certificate_pdf_bytes(
        preview_path=tpl.preview_path,
        field_config=tpl.get_field_config(),
        nama=peserta.nama, nim=peserta.nim,
        fakultas=peserta.fakultas, universitas=peserta.universitas,
        no_sertifikat=peserta.no_ref, kode_verifikasi=peserta.kode_verifikasi,
        verify_url=verify_url,
        font_nama_path=tpl.font_nama_path, font_bold_path=tpl.font_bold_path, font_reg_path=tpl.font_reg_path,
    )

    demo_filename = kirim_sertifikat_email(peserta, pdf_bytes, demo_mode=current_app.config["EMAIL_DEMO_MODE"])

    from datetime import datetime
    peserta.status = "terkirim"
    peserta.waktu_diambil = datetime.utcnow()
    db.session.commit()

    session.pop("peserta_id_verifikasi", None)
    session.pop("otp_id_verifikasi", None)

    return render_template(
        "public/terkirim.html", peserta=peserta,
        demo_mode=current_app.config["EMAIL_DEMO_MODE"], demo_filename=demo_filename,
    )


# ------------------------------------------ cek keaslian (pihak ketiga) -
@public_bp.route("/cek-sertifikat")
def cek_sertifikat():
    kode = request.args.get("kode", "").strip()
    hasil_cek = None
    if kode:
        peserta = Peserta.query.filter_by(kode_verifikasi=kode).first()
        if peserta and peserta.status == "terkirim":
            hasil_cek = {
                "valid": True,
                "nama": peserta.nama, "nim": peserta.nim,
                "universitas": peserta.universitas,
                "no_sertifikat": peserta.no_ref,
                "tanggal_terbit": peserta.waktu_diambil,
                "periode": peserta.periode.nama_periode,
            }
        else:
            hasil_cek = {"valid": False}
    return render_template("public/cek_sertifikat.html", kode=kode, hasil_cek=hasil_cek)


# ------------------------------------ hanya aktif saat EMAIL_DEMO_MODE ---
@public_bp.route("/demo/unduh/<no_ref_flat>")
def demo_unduh(no_ref_flat):
    """Route bantu KHUSUS mode demo, supaya hasil generate sertifikat
    tetap bisa diperiksa tanpa SMTP asli (file disimpan oleh
    kirim_sertifikat_email() ke data/generated/). Otomatis nonaktif kalau
    EMAIL_DEMO_MODE=false."""
    import os
    from flask import abort, send_from_directory

    if not current_app.config["EMAIL_DEMO_MODE"]:
        abort(404)

    out_dir = os.path.join(current_app.root_path, "..", "data", "generated")
    filename = f"{no_ref_flat}.pdf"
    if not os.path.exists(os.path.join(out_dir, filename)):
        abort(404)
    return send_from_directory(out_dir, filename, as_attachment=True)
