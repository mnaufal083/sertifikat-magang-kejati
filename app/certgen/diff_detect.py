"""
certgen/diff_detect.py
=======================
Deteksi otomatis posisi SEMUA field teks (termasuk Nama yang biasanya
berfont kaligrafi/miring) dengan cara MEMBANDINGKAN dua gambar template
yang identik kecuali di bagian teksnya:
  - "versi contoh"  : desain dengan teks contoh terisi di semua field
  - "versi polos"   : desain yang sama persis, tapi teksnya sudah dihapus

Kenapa ini lebih andal daripada ocr_detect.py (yang mencari kata kunci
lewat OCR): OCR bergantung pada MEMBACA bentuk huruf, jadi gagal total
untuk font kaligrafi seperti Pinyon Script (dipakai field Nama pada
template resmi Kejati). Metode diff di modul ini sama sekali tidak perlu
membaca huruf - cukup cari piksel yang BERBEDA antara dua gambar, jadi
bekerja untuk font apa pun. OCR di sini HANYA dipakai sebagai "tebakan"
opsional untuk label kotak yang terdeteksi (best-effort, boleh kosong),
keputusan field yang sebenarnya tetap di tangan admin lewat dropdown.

>>> SYARAT AGAR AKURAT <<<
Kedua gambar harus diekspor dari file desain yang SAMA PERSIS (resolusi
sama, tidak ada elemen lain yang ikut bergeser) - satu-satunya beda cuma
teksnya dihapus/tidak. Kalau resolusi beda, gambar "polos" otomatis
di-resize menyamai "contoh" (dilaporkan lewat flag `diresize`).
"""
import os

import cv2
import numpy as np
import pytesseract

# Piksel dengan selisih grayscale di atas ini dianggap "berubah" (bukan
# sekadar noise kompresi JPG/anti-aliasing halus).
AMBANG_BEDA = 28

# Luas minimum satu kotak (pecahan dari luas total gambar) supaya tidak
# menganggap noise/debu sebagai field - disetel untuk teks seukuran
# sertifikat pada umumnya.
LUAS_MINIMUM_FRAC = 0.00025

# Maksimum jumlah kotak yang dikembalikan (mengurangi kalau ada
# false-positive berlebihan; kotak diurutkan dari yang terluas).
MAKS_KOTAK = 14


def _pastikan_ukuran_sama(im_contoh, im_kosong):
    """Kalau ukuran dua gambar beda, sesuaikan 'kosong' ke ukuran 'contoh'.
    Mengembalikan (im_kosong_baru, diresize: bool)."""
    h1, w1 = im_contoh.shape[:2]
    h2, w2 = im_kosong.shape[:2]
    if (h1, w1) == (h2, w2):
        return im_kosong, False
    im_kosong_resized = cv2.resize(im_kosong, (w1, h1), interpolation=cv2.INTER_AREA)
    return im_kosong_resized, True


def _ocr_tebakan(im_contoh_bgr, x0, y0, x1, y1):
    """Coba baca teks di area kotak (best-effort, dari gambar CONTOH yang
    isinya masih ada). Kembalikan string kosong kalau tidak terbaca sama
    sekali (mis. font kaligrafi) - ini NORMAL & sudah diantisipasi, bukan
    error."""
    try:
        crop = im_contoh_bgr[y0:y1, x0:x1]
        if crop.size == 0:
            return ""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        teks = pytesseract.image_to_string(thresh, lang="eng").strip()
        teks = " ".join(teks.split())  # rapikan spasi/baris berlebih
        return teks[:60]  # batasi panjang, cuma buat "petunjuk" di UI
    except Exception:
        return ""


def deteksi_dari_dua_gambar(path_contoh, path_kosong):
    """Bandingkan dua gambar, kembalikan (daftar_kotak, diresize).

    daftar_kotak: list of dict, tiap kotak:
        {
          "id": int,
          "x": float,  # pusat horizontal, pecahan 0-1
          "y": float,  # pusat vertikal, pecahan 0-1
          "w": float,  # lebar kotak, pecahan 0-1
          "h": float,  # tinggi kotak, pecahan 0-1
          "tebakan": str,  # hasil OCR best-effort, boleh ""
        }
      Diurutkan dari atas ke bawah (mengikuti urutan baca sertifikat pada
      umumnya: Nama di atas, lalu identitas, lalu tanggal di bawah).
    """
    im_contoh = cv2.imread(path_contoh)
    im_kosong = cv2.imread(path_kosong)
    if im_contoh is None or im_kosong is None:
        raise ValueError("Salah satu file gambar gagal dibaca. Pastikan formatnya PNG/JPG yang valid.")

    im_kosong, diresize = _pastikan_ukuran_sama(im_contoh, im_kosong)
    H, W = im_contoh.shape[:2]

    gray_contoh = cv2.cvtColor(im_contoh, cv2.COLOR_BGR2GRAY)
    gray_kosong = cv2.cvtColor(im_kosong, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(gray_contoh, gray_kosong)
    _, mask = cv2.threshold(diff, AMBANG_BEDA, 255, cv2.THRESH_BINARY)
    mask_asli = mask.copy()  # simpan SEBELUM dilasi - dipakai pengukuran ulang kotak biar presisi

    # Dilasi: gabungkan huruf/kata yang berdekatan jadi satu blok per
    # baris teks. Kernel lebih lebar horizontal (menyatukan kata dalam
    # satu baris) daripada vertikal (supaya baris berbeda tetap terpisah).
    lebar_kernel = max(int(W * 0.018), 8)
    tinggi_kernel = max(int(H * 0.006), 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (lebar_kernel, tinggi_kernel))
    mask = cv2.dilate(mask, kernel, iterations=2)

    kontur, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    luas_total = W * H
    kandidat = []
    for c in kontur:
        x, y, w, h = cv2.boundingRect(c)
        if (w * h) / luas_total < LUAS_MINIMUM_FRAC:
            continue
        # PENTING: (x,y,w,h) di atas diukur dari mask yang SUDAH didilasi
        # (sengaja digembungkan supaya kata-kata dalam satu baris nyatu
        # jadi satu blok). Kalau dipakai langsung, tinggi kotak jadi lebih
        # besar dari tinggi huruf sebenarnya - berakibat perkiraan ukuran
        # font di routes_admin.py (dihitung dari tinggi kotak) jadi
        # kegedean. Maka di sini kotaknya diukur ULANG memakai mask_asli
        # (SEBELUM dilasi, cuma piksel yang benar-benar beda) supaya
        # posisi & ukuran presisi, sementara mask hasil dilasi tetap
        # dipakai buat urusan MENEMUKAN & MENGGABUNGKAN blok kata saja.
        sub_asli = mask_asli[y:y + h, x:x + w]
        ys, xs = np.where(sub_asli > 0)
        if len(xs) == 0:
            continue  # murni hasil dilasi, tidak ada piksel beda asli di situ
        x_tight = x + xs.min()
        w_tight = xs.max() - xs.min() + 1
        y_tight = y + ys.min()
        h_tight = ys.max() - ys.min() + 1
        kandidat.append((x_tight, y_tight, w_tight, h_tight))

    # Urutkan dari yang terluas dulu (biar false-positive kecil terbuang
    # duluan kalau melebihi MAKS_KOTAK), baru potong ke batas maksimum,
    # BARU diurutkan ulang top-to-bottom untuk ditampilkan ke admin.
    kandidat.sort(key=lambda k: k[2] * k[3], reverse=True)
    kandidat = kandidat[:MAKS_KOTAK]
    kandidat.sort(key=lambda k: k[1])  # urut y (atas -> bawah)

    daftar_kotak = []
    for i, (x, y, w, h) in enumerate(kandidat):
        tebakan = _ocr_tebakan(im_contoh, x, y, x + w, y + h)
        daftar_kotak.append({
            "id": i,
            "x": round((x + w / 2) / W, 4),
            "y": round((y + h / 2) / H, 4),
            "w": round(w / W, 4),
            "h": round(h / H, 4),
            "tebakan": tebakan,
        })

    return daftar_kotak, diresize
