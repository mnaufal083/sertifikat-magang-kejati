"""
run.py
======
Entry point untuk menjalankan aplikasi secara lokal.

Cara pakai (lihat README.md untuk detail lengkap):
    python run.py

Lalu buka http://127.0.0.1:5000/admin (sisi admin) atau link personal
peserta di http://127.0.0.1:5000/s/<token> (sisi peserta).
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
