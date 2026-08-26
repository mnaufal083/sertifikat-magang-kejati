"""
certgen/ocr_detect.py
======================
Deteksi otomatis posisi field (Nama, NIM, Fakultas, Universitas) pada
template sertifikat yang diunggah - SELAMA desainnya masih menyertakan
teks label placeholder seperti pada template resmi (mis. "Nama
Mahasiswa", "NIM", "Fakultas", "Universitas").

Cara kerja: OCR (Tesseract) mencari kata kunci tsb di gambar, lalu:
  1. Posisi Y tiap field yang KETEMU diisi otomatis ke field_config
     (posisi X dibiarkan di tengah/0.5, mengikuti asumsi desain
     center-aligned yang umum dipakai sertifikat resmi).
  2. Area di sekitar teks yang terdeteksi dibersihkan otomatis (image
     inpainting) - jadi admin tidak perlu menyiapkan file yang sudah
     "polos tanpa teks" secara manual.
  3. Field yang TIDAK ketemu (misalnya karena fontnya kaligrafi/miring,
     atau tertutup elemen dekorasi) dibiarkan memakai nilai sebelumnya,
     dan dilaporkan supaya admin tahu bagian mana yang perlu diatur
     manual lewat form kalibrasi seperti biasa.

>>> KETERBATASAN YANG PERLU DIKETAHUI (diuji langsung, bukan asumsi) <<<
- Font tegak/serif biasa (seperti "NIM", "Fakultas", "Universitas" pada
  template resmi) terdeteksi sangat andal (>90% confidence).
- Font kaligrafi/miring (seperti "Nama Mahasiswa" yang memakai gaya
  serupa Pinyon Script) SERING TIDAK terbaca OCR sama sekali - ini
  keterbatasan teknologi OCR pada umumnya, bukan bug. Sebagai jalan
  tengah, modul ini juga mencoba mendeteksi kata "Mahasiswa" (kalau ada,
  biasanya ditulis normal meski "Nama"-nya sendiri kaligrafi) sebagai
  penanda posisi.
- Kalau field tertentu tidak terdeteksi sama sekali, kalibrasi manual
  (form angka + Render Uji Coba) tetap tersedia sebagai jalan pasti.
"""
import cv2
import numpy as np
import pytesseract
from PIL import Image

# Kata kunci yang dicari per field. Beberapa alternatif per field supaya
# tidak terlalu kaku pada satu ejaan/label saja.
KATA_KUNCI = {
    "nama": ["nama"],
    "nama_fallback": ["mahasiswa"],  # dipakai kalau "nama" sendiri tidak ketemu
    "nim": ["nim"],
    "fakultas": ["fakultas"],
    "universitas": ["universitas", "perguruan"],
}

CONF_MINIMUM = 40  # di bawah ini dianggap terlalu tidak yakin, diabaikan

# Rentang horizontal default untuk area yang dibersihkan (fraksi lebar
# gambar) - cukup lebar untuk menampung "Label : isi panjang" tapi masih
# aman dari border/dekorasi tepi pada desain sertifikat pada umumnya.
ERASE_X0, ERASE_X1 = 0.28, 0.72


def _jalankan_ocr(gray_arr):
    """gray_arr: numpy array grayscale. Preprocessing threshold sederhana
    terbukti signifikan meningkatkan akurasi OCR pada background
    bertekstur/watermark (diuji: <10% -> >90% confidence)."""
    _, thresh = cv2.threshold(gray_arr, 150, 255, cv2.THRESH_BINARY)
    return pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT, lang="eng")


def _cari_kata(data, daftar_kata):
    """Cari kata pertama yang cocok (confidence tertinggi) dari daftar
    alternatif. Mengembalikan dict {x,y,w,h,conf} atau None."""
    kandidat = []
    for i, word in enumerate(data["text"]):
        w = word.strip().lower().rstrip(":.,")
        if w in daftar_kata and data["conf"][i] >= CONF_MINIMUM:
            kandidat.append({
                "x": data["left"][i], "y": data["top"][i],
                "w": data["width"][i], "h": data["height"][i],
                "conf": data["conf"][i],
            })
    if not kandidat:
        return None
    return max(kandidat, key=lambda k: k["conf"])


def bersihkan_area(image_path, x_frac, y_frac, lebar_frac, tinggi_frac):
    """Bersihkan (inpaint) satu area persegi panjang secara manual di
    sekitar posisi x/y yang diberikan - dipakai tombol "Bersihkan Area
    Ini" di halaman kalibrasi, untuk field yang tidak (atau salah)
    terdeteksi otomatis oleh OCR. Koordinat dalam pecahan 0-1, sama
    seperti field_config. Menimpa langsung file di image_path."""
    im_cv = cv2.imread(image_path)
    H, W = im_cv.shape[:2]
    gray = cv2.cvtColor(im_cv, cv2.COLOR_BGR2GRAY)

    cx, cy = x_frac * W, y_frac * H
    half_w = (lebar_frac * W) / 2
    half_h = (tinggi_frac * H) / 2
    x0 = max(int(cx - half_w), 0)
    x1 = min(int(cx + half_w), W)
    y0 = max(int(cy - half_h), 0)
    y1 = min(int(cy + half_h), H)

    mask = np.zeros((H, W), dtype=np.uint8)
    roi_gray = gray[y0:y1, x0:x1]
    _, roi_mask = cv2.threshold(roi_gray, 165, 255, cv2.THRESH_BINARY_INV)
    mask[y0:y1, x0:x1] = roi_mask

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)
    hasil = cv2.inpaint(im_cv, mask, 9, cv2.INPAINT_TELEA)
    cv2.imwrite(image_path, hasil)


def deteksi_dan_bersihkan(image_path, field_config_sekarang):
    """Jalankan deteksi pada gambar template, kembalikan:
      - field_config baru (hasil update posisi Y field yang terdeteksi,
        field lain tidak diubah)
      - laporan: dict {field: True/False} menandai mana yang terdeteksi
      - gambar hasil pembersihan disimpan LANGSUNG menimpa image_path
    """
    im_cv = cv2.imread(image_path)
    H, W = im_cv.shape[:2]
    gray = cv2.cvtColor(im_cv, cv2.COLOR_BGR2GRAY)

    data = _jalankan_ocr(gray)

    config = {k: dict(v) for k, v in field_config_sekarang.items()}
    laporan = {"nama": False, "nim": False, "fakultas": False, "universitas": False}
    kotak_hapus = []

    # --- NIM / Fakultas / Universitas dulu (posisinya dipakai sebagai
    #     patokan batas bawah yang aman untuk validasi deteksi Nama) ---
    y_frac_terdeteksi = []
    for field in ("nim", "fakultas", "universitas"):
        hit = _cari_kata(data, KATA_KUNCI[field])
        if hit:
            y_frac = (hit["y"] + hit["h"] / 2) / H
            config[field]["y"] = round(y_frac, 4)
            laporan[field] = True
            kotak_hapus.append(hit)
            y_frac_terdeteksi.append(y_frac)

    # --- Nama: coba "nama" dulu, fallback ke "mahasiswa" ---
    # PENTING: kata "mahasiswa" hampir selalu juga muncul di paragraf isi
    # sertifikat (mis. "...sebagai peserta magang mahasiswa..."), BUKAN
    # cuma di placeholder "Nama Mahasiswa". Supaya tidak salah ambil posisi
    # dari paragraf itu, kandidat "mahasiswa" HANYA diterima kalau
    # posisinya jelas di ATAS field NIM/Fakultas/Universitas yang sudah
    # terdeteksi (nama semestinya baris paling atas dari keempatnya) -
    # kalau tidak ada satupun field lain yang terdeteksi sebagai patokan,
    # fallback ini tidak dipakai sama sekali (lebih aman melapor "tidak
    # terdeteksi" daripada diam-diam salah posisi).
    hit = _cari_kata(data, KATA_KUNCI["nama"])
    if not hit and y_frac_terdeteksi:
        batas_atas = min(y_frac_terdeteksi) - 0.02  # sedikit margin
        kandidat = _cari_kata(data, KATA_KUNCI["nama_fallback"])
        if kandidat and (kandidat["y"] + kandidat["h"] / 2) / H < batas_atas:
            hit = kandidat

    if hit:
        y_frac = (hit["y"] + hit["h"] / 2) / H
        config["nama"]["y"] = round(y_frac, 4)
        laporan["nama"] = True
        kotak_hapus.append(hit)

    # --- Bersihkan (inpaint) area di sekitar tiap teks yang terdeteksi ---
    if kotak_hapus:
        mask = np.zeros((H, W), dtype=np.uint8)
        for hit in kotak_hapus:
            y_center = hit["y"] + hit["h"] / 2
            pad = hit["h"] * 1.4
            y0 = max(int(y_center - pad), 0)
            y1 = min(int(y_center + pad), H)
            x0 = int(ERASE_X0 * W)
            x1 = int(ERASE_X1 * W)
            # threshold lokal supaya yang terhapus benar cuma coretan teks,
            # bukan seluruh kotak (menjaga tekstur latar tetap menyatu)
            roi_gray = gray[y0:y1, x0:x1]
            _, roi_mask = cv2.threshold(roi_gray, 165, 255, cv2.THRESH_BINARY_INV)
            mask[y0:y1, x0:x1] = roi_mask

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)
        hasil = cv2.inpaint(im_cv, mask, 9, cv2.INPAINT_TELEA)
        cv2.imwrite(image_path, hasil)

    return config, laporan
