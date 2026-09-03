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


class OcrTidakTersedia(Exception):
    """Dilempar khusus kalau Tesseract memang tidak terpasang/tidak
    ketemu di PATH - beda dari kegagalan membaca font kaligrafi (yang
    NORMAL & sudah diantisipasi). UI perlu tahu beda ini supaya tidak
    salah bilang 'wajar untuk font kaligrafi' padahal OCR-nya sendiri
    tidak jalan sama sekali."""
    pass


def _ocr_tebakan(im_contoh_bgr, x0, y0, x1, y1):
    """Coba baca teks di area kotak (best-effort, dari gambar CONTOH yang
    isinya masih ada). Kembalikan string kosong kalau tidak terbaca sama
    sekali (mis. font kaligrafi) - ini NORMAL & sudah diantisipasi, bukan
    error. Kalau Tesseract sendiri tidak terpasang, lempar
    OcrTidakTersedia supaya pemanggil bisa kasih tahu admin dengan jelas
    (beda dari sekadar 'kaligrafi tidak terbaca')."""
    crop = im_contoh_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return ""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    try:
        teks = pytesseract.image_to_string(thresh, lang="eng").strip()
    except pytesseract.TesseractNotFoundError:
        raise OcrTidakTersedia(
            "Tesseract OCR tidak ditemukan di server/komputer ini. Deteksi "
            "posisi via perbandingan gambar tetap jalan normal (tidak "
            "butuh OCR), cuma 'tebakan' nama field per kotak tidak akan "
            "tersedia - beri label manual saja lewat dropdown."
        )
    except Exception:
        return ""  # kegagalan baca lain (mis. font kaligrafi) - normal, diam saja
    teks = " ".join(teks.split())  # rapikan spasi/baris berlebih
    return teks[:60]  # batasi panjang, cuma buat "petunjuk" di UI


def deteksi_dari_dua_gambar(path_contoh, path_kosong):
    """Bandingkan dua gambar, kembalikan (daftar_kotak, diresize, ocr_tersedia).

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
    ocr_tersedia: False kalau Tesseract tidak terpasang di server/komputer
      ini - deteksi POSISI tetap berjalan normal (tidak butuh OCR sama
      sekali), cuma kolom "tebakan" semua kotak jadi kosong. UI perlu
      tahu ini supaya bisa kasih pesan yang jelas ("OCR tidak terpasang")
      alih-alih menyiratkan semua kotak adalah font kaligrafi.
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
    ocr_tersedia = True
    for i, (x, y, w, h) in enumerate(kandidat):
        # Padding KHUSUS untuk keperluan OCR saja - Tesseract butuh sedikit
        # ruang kosong di sekeliling teks supaya bisa membaca dengan baik.
        # Posisi & ukuran KOTAK YANG DISIMPAN (x,y,w,h di bawah) TETAP
        # presisi tanpa padding, supaya perkiraan ukuran font di
        # routes_admin.py tidak ikut kegedean seperti sebelum diperbaiki.
        #
        # PENTING: padding vertikal DIBATASI ke persentase TINGGI GAMBAR
        # (bukan tinggi kotak itu sendiri) - kalau dulu dihitung dari
        # tinggi kotak, field seperti Nama (kaligrafi, kotaknya secara
        # alami tinggi karena ascender/descender huruf sambung) bisa
        # menghasilkan padding sangat besar sampai "menyerempet" baris
        # field lain di dekatnya (mis. NIM tepat di bawahnya) dan bikin
        # OCR salah baca kata kunci dari baris tetangga.
        pad_x = max(6, int(w * 0.15))
        pad_y = max(6, min(int(h * 0.6), int(H * 0.012)))
        ocr_x0 = max(0, x - pad_x)
        ocr_y0 = max(0, y - pad_y)
        ocr_x1 = min(W, x + w + pad_x)
        ocr_y1 = min(H, y + h + pad_y)

        if ocr_tersedia:
            try:
                tebakan = _ocr_tebakan(im_contoh, ocr_x0, ocr_y0, ocr_x1, ocr_y1)
            except OcrTidakTersedia:
                # Tesseract tidak terpasang - jangan diulang-ulang coba
                # untuk kotak berikutnya (cuma buang waktu, pasti gagal
                # lagi), tandai saja & lanjut tanpa tebakan sama sekali.
                ocr_tersedia = False
                tebakan = ""
        else:
            tebakan = ""
        daftar_kotak.append({
            "id": i,
            "x": round((x + w / 2) / W, 4),
            "y": round((y + h / 2) / H, 4),
            "w": round(w / W, 4),
            "h": round(h / H, 4),
            "tebakan": tebakan,
        })

    return daftar_kotak, diresize, ocr_tersedia


# ------------------------------------------------- pencocokan otomatis --
_KATA_KUNCI_FIELD = {
    "nim": ("nim",),
    "fakultas": ("fakultas",),
    "universitas": ("universitas",),
    # PENTING: kata kunci di sini harus FRASA SPESIFIK, bukan kata tunggal
    # generik. "sertifikat" saja, misalnya, akan salah cocok dengan JUDUL
    # sertifikat itu sendiri ("SERTIFIKAT") - bug nyata yang pernah terjadi
    # dan bikin judul disangka field "Nomor Sertifikat" (posisinya jadi
    # berantakan karena field nomor dianggap rata-kanan sementara judul
    # aslinya di tengah). Frasa "no. sertifikat"/"kode verifikasi" jauh
    # lebih spesifik - cuma cocok kalau memang ada template yang benar-benar
    # mencetak label itu, bukan judul biasa.
    "nomor": ("no. sertifikat", "no sertifikat", "nomor sertifikat", "kode verifikasi"),
}
# CATATAN: Tanggal SENGAJA tidak lagi ada di daftar kata kunci/deteksi
# otomatis. Tanggal terbit dianggap bagian TETAP dari desain template
# (ikut ter-bakar di gambar latar seperti teks statis lain: "Semarang,",
# nama & jabatan penandatangan, dst.) - bukan field yang berubah per
# peserta seperti Nama/NIM/Fakultas/Universitas. Kalau desain baru punya
# tanggal berbeda, cukup ganti/unggah template baru; sistem TIDAK lagi
# mencoba menebak & menempelkan tanggal dinamis secara otomatis. Field
# "tanggal" & seluruh infrastrukturnya (kalibrasi manual, generator)
# tetap ada di sistem untuk yang mau memakainya secara manual/opsional,
# cuma tidak lagi bagian dari alur deteksi otomatis ini.


def cocokkan_otomatis(kotak):
    """Tebak field yang cocok untuk tiap kotak terdeteksi TANPA campur
    tangan admin - dipakai alur "Unggah Template Baru (Otomatis)" supaya
    kalau hasilnya sudah pas, admin tidak perlu buka halaman kalibrasi
    sama sekali.

    Caranya:
      1. Field berlabel biasa (NIM/Fakultas/Universitas/No. Sertifikat)
         ditebak dari KATA KUNCI di hasil OCR (`tebakan`) - andal karena
         field-field ini memang selalu pakai font biasa (bukan kaligrafi).
      2. Field Nama (biasanya kaligrafi, OCR HAMPIR PASTI gagal total di
         sini) ditebak dari SISA kotak yang belum ketebak field lain:
         dipilih yang kotaknya PALING TINGGI (nama biasa dicetak dengan
         font terbesar di antara semua field) DAN posisinya di ATAS
         kluster field identitas (NIM/Fakultas/Universitas) - dua ciri
         ini cukup unik untuk Nama tanpa perlu membaca isinya sama sekali.

    Tanggal SENGAJA TIDAK ikut ditebak (lihat catatan di atas daftar kata
    kunci) - kotak yang isinya tanggal akan berakhir di tidak_dikenali,
    dan itu memang perilaku yang diinginkan.

    Mengembalikan (pemetaan, tidak_dikenali):
      pemetaan       : {"nama": [id,...], "nim": [id,...], ...}
      tidak_dikenali : [id,...] - kotak yang gagal ditebak field-nya,
                       dibiarkan begitu saja (tidak diterapkan otomatis),
                       admin bisa menugaskannya manual lewat halaman
                       Kalibrasi kalau memang diperlukan.
    """
    pemetaan = {}
    belum_ketebak = []

    for k in kotak:
        teks = (k.get("tebakan") or "").lower()
        field_ketemu = None

        if any(kw in teks for kw in _KATA_KUNCI_FIELD["nim"]):
            field_ketemu = "nim"
        elif any(kw in teks for kw in _KATA_KUNCI_FIELD["fakultas"]):
            field_ketemu = "fakultas"
        elif any(kw in teks for kw in _KATA_KUNCI_FIELD["universitas"]):
            field_ketemu = "universitas"
        elif any(kw in teks for kw in _KATA_KUNCI_FIELD["nomor"]):
            field_ketemu = "nomor"

        if field_ketemu:
            pemetaan.setdefault(field_ketemu, []).append(k["id"])
        else:
            belum_ketebak.append(k)

    if belum_ketebak:
        # Acuan "atas kluster identitas" = y terkecil di antara field
        # identitas yang SUDAH ketebak lewat kata kunci.
        y_acuan = None
        for f in ("nim", "fakultas", "universitas"):
            for idx in pemetaan.get(f, []):
                kk = next(x for x in kotak if x["id"] == idx)
                if y_acuan is None or kk["y"] < y_acuan:
                    y_acuan = kk["y"]

        kandidat_nama = [k for k in belum_ketebak if y_acuan is None or k["y"] < y_acuan]
        if not kandidat_nama:
            kandidat_nama = belum_ketebak  # fallback: tidak ada info posisi, pilih dari semua sisa

        nama_terpilih = max(kandidat_nama, key=lambda k: k["h"])
        pemetaan["nama"] = [nama_terpilih["id"]]
        belum_ketebak = [k for k in belum_ketebak if k["id"] != nama_terpilih["id"]]

    tidak_dikenali = [k["id"] for k in belum_ketebak]
    return pemetaan, tidak_dikenali
