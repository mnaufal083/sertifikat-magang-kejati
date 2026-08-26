"""
app/routes_admin.py
====================
Sisi ADMIN KEJATI (v2 - disederhanakan):

  - Login sederhana
  - Periode Magang: dibuat sekaligus dengan upload data peserta dalam
    SATU form (nama periode, tanggal mulai/selesai via date picker,
    pilih template sertifikat, unggah Excel) - lihat periode_baru().
  - Data Peserta: tabel ringkas (No.Ref, Nama, NIM, Akun/No.WA, Waktu
    Diambil, Status, Aksi) langsung di halaman detail periode, lengkap
    dengan ringkasan status di bagian atas (tanpa halaman "Ringkasan"
    terpisah).
  - Template Sertifikat: unggah desain baru (PDF/gambar resolusi
    tinggi), kalibrasi posisi tiap field lewat form angka + pratinjau
    langsung (live preview), pilih template mana yang aktif dipakai per
    periode.

  Halaman "Log Aktivitas" sengaja TIDAK dibuat sebagai menu terpisah -
  status peserta (sudah/belum diambil, jumlah percobaan gagal) sudah
  cukup terlihat langsung di tabel Data Peserta.
"""
import os
import io
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, current_app, send_file, jsonify
)
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Periode, Peserta, TemplateSertifikat
from app.auth import admin_required
from app.utils import baca_excel_peserta, proses_upload_peserta
from app.certgen.generator import generate_certificate_image, DEFAULT_FIELD_CONFIG

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------- login --
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if (username == current_app.config["ADMIN_USERNAME"]
                and password == current_app.config["ADMIN_PASSWORD"]):
            session["is_admin"] = True
            session["admin_username"] = username
            flash("Berhasil masuk.", "success")
            tujuan = request.args.get("next") or url_for("admin.periode_list")
            return redirect(tujuan)
        flash("Username atau password salah.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# --------------------------------------------------------- periode list --
@admin_bp.route("/")
@admin_required
def index():
    return redirect(url_for("admin.periode_list"))


@admin_bp.route("/periode")
@admin_required
def periode_list():
    periode_list_ = Periode.query.order_by(Periode.dibuat_at.desc()).all()
    ringkasan = []
    for pr in periode_list_:
        total = len(pr.peserta)
        sudah = sum(1 for x in pr.peserta if x.status == "terkirim")
        ringkasan.append({"periode": pr, "total": total, "sudah": sudah, "belum": total - sudah})
    return render_template("admin/periode_list.html", ringkasan=ringkasan)


@admin_bp.route("/periode/baru", methods=["GET", "POST"])
@admin_required
def periode_baru():
    if request.method == "GET":
        template_list = TemplateSertifikat.query.filter_by(aktif=True).order_by(TemplateSertifikat.nama_template).all()
        return render_template("admin/periode_form.html", template_list=template_list, periode=None)

    nama = request.form.get("nama_periode", "").strip()
    tgl_mulai = request.form.get("tanggal_mulai") or None
    tgl_selesai = request.form.get("tanggal_selesai") or None
    template_id = request.form.get("template_id") or None

    if not nama:
        flash("Nama periode tidak boleh kosong.", "error")
        return redirect(url_for("admin.periode_baru"))

    periode = Periode(
        nama_periode=nama,
        tanggal_mulai=datetime.strptime(tgl_mulai, "%Y-%m-%d").date() if tgl_mulai else None,
        tanggal_selesai=datetime.strptime(tgl_selesai, "%Y-%m-%d").date() if tgl_selesai else None,
        template_id=int(template_id) if template_id else None,
        aktif=True,
    )
    db.session.add(periode)
    db.session.commit()

    file_excel = request.files.get("file_excel")
    if file_excel and file_excel.filename:
        try:
            data_rows = baca_excel_peserta(file_excel)
            ditambahkan, dilewati = proses_upload_peserta(periode, data_rows)
            pesan = f"Periode '{nama}' dibuat dengan {ditambahkan} peserta."
            if dilewati:
                pesan += f" ({dilewati} baris dilewati karena NIM sudah ada)"
            flash(pesan, "success")
        except ValueError as e:
            flash(f"Periode '{nama}' dibuat, tapi upload Excel gagal: {e}", "error")
    else:
        flash(f"Periode '{nama}' dibuat. Belum ada data peserta - unggah lewat halaman detail periode.", "success")

    return redirect(url_for("admin.periode_detail", periode_id=periode.id))


# ------------------------------------------------------- detail periode --
@admin_bp.route("/periode/<int:periode_id>")
@admin_required
def periode_detail(periode_id):
    periode = Periode.query.get_or_404(periode_id)
    peserta_list = Peserta.query.filter_by(periode_id=periode_id).order_by(Peserta.no_ref).all()

    total = len(peserta_list)
    sudah = sum(1 for p in peserta_list if p.status == "terkirim")
    belum = total - sudah
    gagal = sum(p.percobaan_gagal for p in peserta_list)

    return render_template(
        "admin/periode_detail.html",
        periode=periode, peserta_list=peserta_list,
        total=total, sudah=sudah, belum=belum, gagal=gagal,
        template_list=TemplateSertifikat.query.filter_by(aktif=True).order_by(TemplateSertifikat.nama_template).all(),
    )


@admin_bp.route("/periode/<int:periode_id>/upload-tambahan", methods=["POST"])
@admin_required
def upload_tambahan(periode_id):
    periode = Periode.query.get_or_404(periode_id)
    file_excel = request.files.get("file_excel")
    if not file_excel or not file_excel.filename:
        flash("Pilih file Excel terlebih dahulu.", "error")
        return redirect(url_for("admin.periode_detail", periode_id=periode_id))

    try:
        data_rows = baca_excel_peserta(file_excel)
        ditambahkan, dilewati = proses_upload_peserta(periode, data_rows)
        pesan = f"{ditambahkan} peserta baru ditambahkan."
        if dilewati:
            pesan += f" ({dilewati} baris dilewati karena NIM sudah ada di periode ini)"
        flash(pesan, "success")
    except ValueError as e:
        flash(f"Upload gagal: {e}", "error")

    return redirect(url_for("admin.periode_detail", periode_id=periode_id))


@admin_bp.route("/periode/<int:periode_id>/edit", methods=["POST"])
@admin_required
def periode_edit(periode_id):
    periode = Periode.query.get_or_404(periode_id)
    periode.nama_periode = request.form.get("nama_periode", periode.nama_periode).strip()
    tgl_mulai = request.form.get("tanggal_mulai") or None
    tgl_selesai = request.form.get("tanggal_selesai") or None
    template_id = request.form.get("template_id") or None
    periode.tanggal_mulai = datetime.strptime(tgl_mulai, "%Y-%m-%d").date() if tgl_mulai else None
    periode.tanggal_selesai = datetime.strptime(tgl_selesai, "%Y-%m-%d").date() if tgl_selesai else None
    periode.template_id = int(template_id) if template_id else None
    db.session.commit()
    flash("Pengaturan periode diperbarui.", "success")
    return redirect(url_for("admin.periode_detail", periode_id=periode_id))


@admin_bp.route("/peserta/<int:peserta_id>/reset", methods=["POST"])
@admin_required
def reset_peserta(peserta_id):
    peserta = Peserta.query.get_or_404(peserta_id)
    peserta.status = "belum_diambil"
    peserta.waktu_diambil = None
    peserta.percobaan_gagal = 0
    db.session.commit()
    flash(f"Status '{peserta.nama}' direset ke Belum Diambil.", "success")
    return redirect(url_for("admin.periode_detail", periode_id=peserta.periode_id))


@admin_bp.route("/peserta/<int:peserta_id>/hapus", methods=["POST"])
@admin_required
def hapus_peserta(peserta_id):
    peserta = Peserta.query.get_or_404(peserta_id)
    periode_id = peserta.periode_id
    db.session.delete(peserta)
    db.session.commit()
    flash("Data peserta dihapus.", "success")
    return redirect(url_for("admin.periode_detail", periode_id=periode_id))


@admin_bp.route("/contoh-excel")
@admin_required
def unduh_contoh_excel():
    """Unduh file Excel contoh dengan kolom yang benar & tampilan rapi
    (lebar kolom pas, header berwarna, border jelas) supaya admin tidak
    perlu menebak-nebak format, dan hasilnya enak dibaca - bukan sekadar
    data mentah berdempetan seperti file CSV."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Data Peserta"

    kolom = ["Nama", "NIM", "Fakultas", "Universitas", "Email", "No. WA"]
    contoh_data = [
        ["Muhammad Naufal Nashir", "2305110041", "Ilmu Komputer", "Universitas Diponegoro",
         "naufal.nashir@example.com", "081234567890"],
        ["Clara Angelina Susanto Wijaya", "2305110048", "Ilmu Sosial dan Ilmu Politik",
         "Universitas Negeri Semarang", "clara.angelina@example.com", "081234567891"],
        ["Siti Aisyah Ramadhani", "2305110042", "Hukum", "Universitas Diponegoro",
         "siti.aisyah@example.com", "081234567892"],
    ]

    # --- Judul & petunjuk singkat di atas tabel ---
    ws.merge_cells("A1:F1")
    ws["A1"] = "Contoh Data Peserta Magang — Kejaksaan Tinggi Jawa Tengah"
    ws["A1"].font = Font(bold=True, size=13, color="2E1440")
    ws.merge_cells("A2:F2")
    ws["A2"] = "Hapus baris contoh di bawah, lalu isi dengan data peserta yang sebenarnya. Jangan mengubah nama kolom di baris 4."
    ws["A2"].font = Font(italic=True, size=9, color="6B7280")
    ws.row_dimensions[3].height = 6  # spasi kecil sebelum header tabel

    # --- Header tabel (baris 4) ---
    header_row = 4
    header_fill = PatternFill(start_color="5B2C82", end_color="5B2C82", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="D1D5DB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, judul in enumerate(kolom, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=judul)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # --- Baris data contoh ---
    for r, baris in enumerate(contoh_data, start=header_row + 1):
        for c, nilai in enumerate(baris, start=1):
            cell = ws.cell(row=r, column=c, value=nilai)
            cell.border = border
            cell.alignment = Alignment(horizontal="left", vertical="center")
            if r % 2 == 0:
                cell.fill = PatternFill(start_color="F5F3FB", end_color="F5F3FB", fill_type="solid")

    # --- Lebar kolom otomatis mengikuti isi terpanjang (tidak berdempetan) ---
    lebar_minimum = [26, 14, 26, 30, 28, 16]
    for col_idx, judul in enumerate(kolom, start=1):
        panjang_maks = max(
            [len(judul)] + [len(str(baris[col_idx - 1])) for baris in contoh_data]
        )
        lebar = max(panjang_maks + 4, lebar_minimum[col_idx - 1])
        ws.column_dimensions[get_column_letter(col_idx)].width = lebar

    ws.row_dimensions[header_row].height = 22
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)  # header tetap terlihat saat scroll

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="Contoh_Data_Peserta.xlsx",
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================ TEMPLATE ==
@admin_bp.route("/template")
@admin_required
def template_list():
    templates = TemplateSertifikat.query.order_by(TemplateSertifikat.dibuat_at.desc()).all()
    return render_template("admin/template_list.html", templates=templates)


@admin_bp.route("/template/<int:template_id>/gambar")
@admin_required
def template_preview_image(template_id):
    from flask import send_file as _send_file
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    return _send_file(tpl.preview_path)


ALLOWED_TEMPLATE_EXT = {"pdf", "png", "jpg", "jpeg"}
ALLOWED_FONT_EXT = {"ttf", "otf"}


def _ext_ok(filename, allowed):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


@admin_bp.route("/template/baru", methods=["GET", "POST"])
@admin_required
def template_baru():
    if request.method == "GET":
        return render_template("admin/template_form.html")

    nama = request.form.get("nama_template", "").strip()
    file_desain = request.files.get("file_desain")

    if not nama or not file_desain or not file_desain.filename:
        flash("Nama template dan file desain wajib diisi.", "error")
        return redirect(url_for("admin.template_baru"))

    if not _ext_ok(file_desain.filename, ALLOWED_TEMPLATE_EXT):
        flash("Format file desain harus PDF, PNG, atau JPG.", "error")
        return redirect(url_for("admin.template_baru"))

    os.makedirs(current_app.config["UPLOAD_TEMPLATE_DIR"], exist_ok=True)
    fname = secure_filename(file_desain.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw_path = os.path.join(current_app.config["UPLOAD_TEMPLATE_DIR"], f"{stamp}_{fname}")
    file_desain.save(raw_path)

    # Kalau PDF, render ke PNG resolusi tinggi (300 DPI) dulu.
    if raw_path.lower().endswith(".pdf"):
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(raw_path, dpi=300)
            preview_path = raw_path.rsplit(".", 1)[0] + ".png"
            pages[0].save(preview_path, "PNG")
        except Exception as e:
            flash(
                f"Gagal mengonversi PDF ke gambar ({e}). Pastikan Poppler sudah "
                f"terpasang (lihat README bagian Prasyarat), atau unggah file "
                f"PNG/JPG langsung sebagai alternatif.", "error"
            )
            return redirect(url_for("admin.template_baru"))
    else:
        preview_path = raw_path

    # Peringatan resolusi rendah, supaya hasil cetak tetap tajam (HD).
    from PIL import Image
    with Image.open(preview_path) as im:
        w, h = im.size
    if w < 2400:
        flash(
            f"Perhatian: lebar gambar hanya {w}px. Untuk hasil sertifikat yang "
            f"tajam saat dicetak, disarankan unggah desain dengan lebar minimal "
            f"~2400px (setara 300 DPI ukuran A4). Template tetap tersimpan dan "
            f"bisa dipakai.", "error"
        )

    # Font kustom (opsional)
    os.makedirs(current_app.config["UPLOAD_FONT_DIR"], exist_ok=True)
    font_paths = {}
    for field_name, form_key in [("font_nama_path", "font_nama"),
                                  ("font_bold_path", "font_bold"),
                                  ("font_reg_path", "font_reg")]:
        f = request.files.get(form_key)
        if f and f.filename:
            if not _ext_ok(f.filename, ALLOWED_FONT_EXT):
                flash(f"Font harus berformat .ttf atau .otf (dilewati: {f.filename}).", "error")
                continue
            fn = secure_filename(f.filename)
            fpath = os.path.join(current_app.config["UPLOAD_FONT_DIR"], f"{stamp}_{fn}")
            f.save(fpath)
            font_paths[field_name] = fpath

    tpl = TemplateSertifikat(
        nama_template=nama,
        preview_path=preview_path,
        font_nama_path=font_paths.get("font_nama_path"),
        font_bold_path=font_paths.get("font_bold_path"),
        font_reg_path=font_paths.get("font_reg_path"),
        aktif=True,
    )
    tpl.set_field_config(DEFAULT_FIELD_CONFIG)
    db.session.add(tpl)
    db.session.commit()

    # --- Deteksi otomatis posisi field dari teks placeholder (kalau ada) ---
    # Best-effort: field dengan label teks biasa (NIM/Fakultas/Universitas)
    # biasanya terdeteksi andal; field bergaya kaligrafi (Nama) kadang tidak.
    # Field yang tidak terdeteksi tetap memakai nilai bawaan dan bisa
    # diatur manual di halaman kalibrasi seperti biasa.
    try:
        from app.certgen.ocr_detect import deteksi_dan_bersihkan
        config_baru, laporan = deteksi_dan_bersihkan(tpl.preview_path, tpl.get_field_config())
        tpl.set_field_config(config_baru)
        db.session.commit()

        terdeteksi = [k for k, v in laporan.items() if v]
        tidak_terdeteksi = [k for k, v in laporan.items() if not v]
        if terdeteksi:
            pesan = f"Terdeteksi otomatis: {', '.join(terdeteksi)}."
            if tidak_terdeteksi:
                pesan += f" Perlu diatur manual: {', '.join(tidak_terdeteksi)}."
            flash(f"Template '{nama}' berhasil diunggah. {pesan}", "success")
        else:
            flash(
                f"Template '{nama}' berhasil diunggah. Tidak ada label placeholder "
                f"(Nama/NIM/Fakultas/Universitas) yang terdeteksi otomatis - silakan "
                f"atur posisi secara manual di halaman kalibrasi.", "success"
            )
    except Exception as e:
        flash(
            f"Template '{nama}' berhasil diunggah, tapi deteksi otomatis gagal dijalankan "
            f"({e}). Silakan atur posisi secara manual.", "error"
        )

    return redirect(url_for("admin.template_kalibrasi", template_id=tpl.id))


@admin_bp.route("/template/<int:template_id>/bersihkan-area", methods=["POST"])
@admin_required
def template_bersihkan_area(template_id):
    """Dipanggil tombol 'Bersihkan Area Ini' per field di halaman
    kalibrasi - untuk field yang tidak (atau salah) terdeteksi otomatis,
    supaya area teks lama tetap bisa dibersihkan tanpa perlu mengedit
    ulang file desain di luar sistem."""
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    data = request.get_json(force=True)
    try:
        from app.certgen.ocr_detect import bersihkan_area
        bersihkan_area(
            tpl.preview_path,
            x_frac=float(data["x"]), y_frac=float(data["y"]),
            lebar_frac=float(data["lebar"]), tinggi_frac=float(data["tinggi"]),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@admin_bp.route("/template/<int:template_id>/deteksi-ulang", methods=["POST"])
@admin_required
def template_deteksi_ulang(template_id):
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    try:
        from app.certgen.ocr_detect import deteksi_dan_bersihkan
        config_baru, laporan = deteksi_dan_bersihkan(tpl.preview_path, tpl.get_field_config())
        tpl.set_field_config(config_baru)
        db.session.commit()

        terdeteksi = [k for k, v in laporan.items() if v]
        tidak_terdeteksi = [k for k, v in laporan.items() if not v]
        if terdeteksi:
            pesan = f"Terdeteksi ulang: {', '.join(terdeteksi)}."
            if tidak_terdeteksi:
                pesan += f" Masih perlu manual: {', '.join(tidak_terdeteksi)}."
            flash(pesan, "success")
        else:
            flash("Tidak ada label placeholder yang terdeteksi. Silakan atur manual.", "error")
    except Exception as e:
        flash(f"Deteksi otomatis gagal dijalankan ({e}).", "error")
    return redirect(url_for("admin.template_kalibrasi", template_id=tpl.id))


@admin_bp.route("/template/<int:template_id>/kalibrasi", methods=["GET"])
@admin_required
def template_kalibrasi(template_id):
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    return render_template("admin/template_kalibrasi.html", tpl=tpl, config=tpl.get_field_config())


@admin_bp.route("/template/<int:template_id>/kalibrasi/simpan", methods=["POST"])
@admin_required
def template_kalibrasi_simpan(template_id):
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    data = request.get_json(force=True)
    tpl.set_field_config(data)
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.route("/template/<int:template_id>/kalibrasi/preview", methods=["POST"])
@admin_required
def template_kalibrasi_preview(template_id):
    """Render pratinjau langsung (belum disimpan) dengan data contoh,
    dipakai oleh tombol 'Render Uji Coba' di halaman kalibrasi."""
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    config = request.get_json(force=True)

    im = generate_certificate_image(
        preview_path=tpl.preview_path,
        field_config=config,
        nama="Contoh Nama Panjang Peserta", nim="0000000000",
        fakultas="Contoh Fakultas", universitas="Contoh Universitas Perguruan Tinggi",
        no_sertifikat="001/CONTOH/VIII/2026", kode_verifikasi="KT26-CONTOH",
        verify_url="http://127.0.0.1:5000/cek-sertifikat?kode=KT26-CONTOH",
        font_nama_path=tpl.font_nama_path, font_bold_path=tpl.font_bold_path, font_reg_path=tpl.font_reg_path,
    )
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg")


@admin_bp.route("/template/<int:template_id>/nonaktifkan", methods=["POST"])
@admin_required
def template_nonaktifkan(template_id):
    tpl = TemplateSertifikat.query.get_or_404(template_id)
    tpl.aktif = not tpl.aktif
    db.session.commit()
    flash(f"Template '{tpl.nama_template}' {'diaktifkan' if tpl.aktif else 'dinonaktifkan'}.", "success")
    return redirect(url_for("admin.template_list"))
