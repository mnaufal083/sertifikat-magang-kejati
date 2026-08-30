"""
certgen/generator.py
=====================
Modul inti penempelan data peserta ke atas template sertifikat.

Berbeda dari versi sebelumnya (yang mengunci koordinat dalam satuan pt
untuk SATU template tertentu), versi ini bekerja di ruang PECAHAN
(fraction 0.0-1.0 relatif terhadap lebar/tinggi gambar). Ini artinya
template apa pun yang diunggah admin - berapa pun resolusinya - bisa
memakai sistem kalibrasi & generator yang sama persis, tanpa perlu
hitungan pt/DPI manual tiap kali ganti template.

DEFAULT_FIELD_CONFIG di bawah adalah hasil konversi dari kalibrasi
presisi template resmi Kejaksaan Tinggi Jawa Tengah yang sudah diukur
sebelumnya (lihat riwayat kalibrasi di README) - dipakai sebagai
template bawaan/contoh saat instalasi pertama (lihat scripts/seed.py).
"""
import os
import io
import qrcode
import img2pdf
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
FONT_DIR = os.path.join(ASSET_DIR, "fonts")

FONT_NAME_DEFAULT = os.path.join(FONT_DIR, "PinyonScript-Regular.otf")
FONT_BOLD_DEFAULT = os.path.join(FONT_DIR, "Cardo-Bold.ttf")
FONT_REG_DEFAULT = os.path.join(FONT_DIR, "Cardo-Regular.ttf")

# ---- Konfigurasi bawaan (hasil kalibrasi template resmi Kejati Jateng) ----
# Semua x/y/size dalam PECAHAN terhadap lebar (untuk x & ukuran font) atau
# tinggi (untuk y) gambar template.
DEFAULT_FIELD_CONFIG = {
    "nama": {
        "x": 0.5, "y": 0.4556,
        "max_width": 0.5461,
        "max_size": 0.05936, "min_size": 0.03087,
        "color": "#4a3728",
    },
    "nim": {
        "x": 0.5, "y": 0.5410,
        "max_width": 0.5698,
        "size": 0.02018, "tracking": 0.00273,
        "color": "#5e4426",
    },
    "fakultas": {
        "x": 0.5, "y": 0.5765,
        "max_width": 0.5698,
        "size": 0.02018, "tracking": 0.00273,
        "color": "#5e4426",
    },
    "universitas": {
        "x": 0.5, "y": 0.6109,
        "max_width": 0.5698,
        "size": 0.02018, "tracking": 0.00273,
        "color": "#5e4426",
    },
    "tanggal": {
        "x": 0.5, "y": 0.6844,
        "size": 0.01800,
        "color": "#5e4426",
        "tampilkan": True,
    },
    "nomor": {
        "x": 0.9235, "y1": 0.0302, "y2": 0.0504,
        "size": 0.01068, "align": "right",
        "color": "#786450",
        "tampilkan": False,
    },
    "qr": {
        "x": 0.0416, "y": 0.8730, "size": 0.05460,
        "label_y": 0.9519, "label_size": 0.00831,
        "color": "#5e4426",
    },
}


def _load_font(path, px_size):
    px_size = max(int(round(px_size)), 6)
    return ImageFont.truetype(path, px_size)


def _tracked_width(draw, text, font, tracking_px):
    if not text:
        return 0
    total = 0
    for ch in text:
        total += draw.textlength(ch, font=font) + tracking_px
    return total - tracking_px


def _draw_tracked(draw, xy, text, font, fill, tracking_px):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking_px


def _fit_font(draw, text, font_path, max_px, min_px, max_width_px):
    size = max_px
    while size > min_px:
        f = _load_font(font_path, size)
        w = draw.textbbox((0, 0), text, font=f)[2]
        if w <= max_width_px:
            return f
        size -= 1
    return _load_font(font_path, min_px)


def _draw_centered_line(draw, text, font, cx, cy, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1]), text, font=font, fill=fill)


def _draw_centered_label_value(draw, label, value, font_label, font_value, cx, cy, fill, tracking_px):
    label_text = f"{label} : "
    lw = _tracked_width(draw, label_text, font_label, tracking_px)
    vw = _tracked_width(draw, value, font_value, tracking_px)
    x_start = cx - (lw + vw) / 2

    bb_l = draw.textbbox((0, 0), "Ag", font=font_label)
    ly = cy - (bb_l[3] - bb_l[1]) / 2 - bb_l[1]
    _draw_tracked(draw, (x_start, ly), label_text, font_label, fill, tracking_px)

    bb_v = draw.textbbox((0, 0), "Ag", font=font_value)
    vy = cy - (bb_v[3] - bb_v[1]) / 2 - bb_v[1]
    _draw_tracked(draw, (x_start + lw, vy), value, font_value, fill, tracking_px)


def _tambahkan_watermark_keamanan(im, teks, warna_dasar="#4a3728"):
    """Tanam pola teks mikro berulang (tiled, diagonal, sangat transparan)
    di seluruh permukaan sertifikat sebagai penanda anti-pemalsuan.

    Kenapa ini membantu: kalau ada pihak mencoba mengedit nama/NIM di
    file hasil jadi (mis. pakai AI image-editing/inpainting) untuk
    menyalahgunakannya, mereka harus ikut merekonstruksi pola berulang
    ini persis di area yang diedit - sesuatu yang sangat sulit dilakukan
    mulus oleh tools AI/edit manual, sehingga area yang diotak-atik akan
    terlihat "pecah"/tidak menyambung dengan pola di sekitarnya saat
    diperbesar (zoom), meski tanpa perlu scan QR code.

    Isi teks memakai kode_verifikasi milik sertifikat itu sendiri (bukan
    teks generik yang sama untuk semua sertifikat) - supaya pola ini juga
    berfungsi sebagai penanda forensik yang unik per sertifikat.
    """
    W, H = im.size
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_layer = ImageDraw.Draw(layer)

    font_size = max(int(W * 0.0068), 10)
    font = _load_font(FONT_REG_DEFAULT, font_size)

    r, g, b = tuple(int(warna_dasar.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    alpha = 14  # dari 255 - sangat halus, hampir tak terlihat di pandangan sekilas

    label = f"  ASLI \u2022 KEJATI JATENG \u2022 {teks}  "
    bbox = draw_layer.textbbox((0, 0), label, font=font)
    tile_w = (bbox[2] - bbox[0]) + int(font_size * 2)
    tile_h = int(font_size * 3.2)

    # Kanvas kerja diperbesar (diagonal) supaya setelah dirotasi & dipotong
    # kembali ke ukuran asli, tetap penuh menutupi seluruh sertifikat
    diag = int((W ** 2 + H ** 2) ** 0.5) + tile_h * 2
    pattern = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw_pattern = ImageDraw.Draw(pattern)
    y = 0
    baris = 0
    while y < diag:
        offset_x = (tile_w // 2) if baris % 2 else 0
        x = -tile_w + offset_x
        while x < diag:
            draw_pattern.text((x, y), label, font=font, fill=(r, g, b, alpha))
            x += tile_w
        y += tile_h
        baris += 1

    pattern = pattern.rotate(28, expand=False, resample=Image.BICUBIC)
    left = (diag - W) // 2
    top = (diag - H) // 2
    pattern_crop = pattern.crop((left, top, left + W, top + H))

    im_rgba = im.convert("RGBA")
    hasil = Image.alpha_composite(im_rgba, pattern_crop)
    return hasil.convert("RGB")


def generate_certificate_image(preview_path, field_config, nama, nim, fakultas, universitas,
                                no_sertifikat, kode_verifikasi, verify_url,
                                tanggal_terbit=None,
                                font_nama_path=None, font_bold_path=None, font_reg_path=None,
                                font_tanggal_path=None,
                                watermark_keamanan=True):
    """Render satu sertifikat lengkap dan kembalikan PIL.Image (RGB).

    preview_path   : path gambar latar bersih template (PNG resolusi tinggi)
    field_config    : dict konfigurasi posisi (lihat DEFAULT_FIELD_CONFIG),
                       biasanya dari TemplateSertifikat.get_field_config()
    tanggal_terbit  : teks tanggal yang SUDAH diformat (mis. "30 Agustus
                       2026" - lihat utils.format_tanggal_indonesia).
                       Otomatis mengikuti tanggal_selesai periode magang
                       peserta, bukan bagian tetap dari desain template -
                       jadi kalau periode berikutnya beda tanggal, tidak
                       perlu bikin/unggah ulang template. None/kosong =
                       field ini tidak digambar sama sekali.
    font_*_path     : path font kustom milik template ybs; None = pakai bawaan
    watermark_keamanan : True = tanam pola anti-pemalsuan (lihat
                       _tambahkan_watermark_keamanan) sebelum teks
                       dinamis ditempel. Default aktif.
    """
    im = Image.open(preview_path).convert("RGB")
    W, H = im.size

    if watermark_keamanan:
        im = _tambahkan_watermark_keamanan(im, kode_verifikasi)

    draw = ImageDraw.Draw(im)

    f_nama_path = font_nama_path or FONT_NAME_DEFAULT
    f_bold_path = font_bold_path or FONT_BOLD_DEFAULT
    f_reg_path = font_reg_path or FONT_REG_DEFAULT
    f_tanggal_path = font_tanggal_path or FONT_REG_DEFAULT

    cfg = field_config

    # --- Nama ---
    c = cfg["nama"]
    f_nama = _fit_font(draw, nama, f_nama_path,
                        max_px=c["max_size"] * W, min_px=c["min_size"] * W,
                        max_width_px=c["max_width"] * W)
    _draw_centered_line(draw, nama, f_nama, c["x"] * W, c["y"] * H, c["color"])

    # --- NIM / Fakultas / Universitas: satu ukuran+tracking konsisten,
    #     mengecil bersama-sama sebagai fallback untuk input sangat panjang ---
    base_size_px = cfg["nim"]["size"] * W
    tracking_px = cfg["nim"]["tracking"] * W
    max_w_px = cfg["nim"]["max_width"] * W

    f_bold = _load_font(f_bold_path, base_size_px)
    f_reg = _load_font(f_reg_path, base_size_px)

    def widest_line(tr):
        widths = []
        for label, value in (("NIM", nim), ("Fakultas", fakultas), ("Universitas", universitas)):
            lw = _tracked_width(draw, f"{label} : ", f_bold, tr)
            vw = _tracked_width(draw, value, f_reg, tr)
            widths.append(lw + vw)
        return max(widths)

    while widest_line(tracking_px) > max_w_px and tracking_px > 0:
        tracking_px -= 0.3
    tracking_px = max(tracking_px, 0)

    for key, label, value in (("nim", "NIM", nim), ("fakultas", "Fakultas", fakultas),
                               ("universitas", "Universitas", universitas)):
        fc = cfg[key]
        _draw_centered_label_value(draw, label, value, f_bold, f_reg,
                                    fc["x"] * W, fc["y"] * H, fc["color"], tracking_px)

    # --- Tanggal terbit (dinamis, mengikuti tanggal_selesai periode - lihat
    # docstring param tanggal_terbit di atas). Field opsional: kalau
    # template lama belum punya konfigurasi "tanggal" sama sekali (dibuat
    # sebelum fitur ini ada), cfg.get() akan None dan baris ini dilewati
    # tanpa error. ---
    tc = cfg.get("tanggal")
    if tc and tc.get("tampilkan", True) and tanggal_terbit:
        f_tanggal = _load_font(f_tanggal_path, tc["size"] * W)
        _draw_centered_line(draw, tanggal_terbit, f_tanggal, tc["x"] * W, tc["y"] * H, tc["color"])

    # --- Nomor sertifikat + kode verifikasi (opsional - template resmi
    # Kejati Jateng tidak punya field nomor surat pada desainnya, jadi
    # secara default TIDAK ditampilkan; nomor & kode tetap tersimpan di
    # database dan tetap bisa dicek lewat QR code / halaman verifikasi) ---
    nc = cfg["nomor"]
    if nc.get("tampilkan", True):
        f_small = _load_font(f_reg_path, nc["size"] * W)
        line1 = f"No. Sertifikat: {no_sertifikat}"
        line2 = f"Kode Verifikasi: {kode_verifikasi}"
        right_x = nc["x"] * W
        bb1 = draw.textbbox((0, 0), line1, font=f_small)
        bb2 = draw.textbbox((0, 0), line2, font=f_small)
        draw.text((right_x - (bb1[2] - bb1[0]), nc["y1"] * H), line1, font=f_small, fill=nc["color"])
        draw.text((right_x - (bb2[2] - bb2[0]), nc["y2"] * H), line2, font=f_small, fill=nc["color"])

    # --- QR code verifikasi ---
    qc = cfg["qr"]
    if verify_url:
        qr = qrcode.QRCode(border=1, box_size=4)
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color=qc["color"], back_color="white").convert("RGBA")
        qr_size = int(qc["size"] * W)
        qr_img = qr_img.resize((qr_size, qr_size))
        im.paste(qr_img, (int(qc["x"] * W), int(qc["y"] * H)), qr_img)
        # Catatan: caption "Scan untuk verifikasi" di bawah QR sengaja
        # dihapus (permintaan desain) - QR code dibiarkan berdiri sendiri
        # tanpa label teks tambahan.

    return im


def generate_certificate_pdf_bytes(**kwargs):
    """Hasilkan PDF sertifikat dalam kualitas PENUH tanpa kompresi ulang
    (setara "Download as PDF Print" di Canva) - PENTING: metode PIL
    bawaan (im.save(..., "PDF")) diam-diam mengompres gambar dengan
    encoding mirip JPEG saat menyimpan ke PDF, menghasilkan sedikit
    blur/softness pada tepi teks & garis vektor dekorasi (sudah diuji
    langsung: ukuran file turun drastis dari ~8.8MB jadi ~900KB, tanda
    kompresi lossy diterapkan). img2pdf membungkus PNG lossless yang
    sudah jadi langsung ke dalam PDF tanpa decode-encode ulang sama
    sekali - hasilnya identik piksel demi piksel dengan gambar aslinya."""
    im = generate_certificate_image(**kwargs)
    buf_png = io.BytesIO()
    im.save(buf_png, format="PNG", dpi=(300, 300))
    buf_png.seek(0)
    return img2pdf.convert(buf_png.read())


def generate_certificate_png_bytes(**kwargs):
    im = generate_certificate_image(**kwargs)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return buf.read()
