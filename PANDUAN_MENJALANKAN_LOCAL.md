# 🌾 SAFRONS — Smart Agriculture and Fertilizer Recommendation System
**Panduan Menjalankan Aplikasi Secara Lokal (Localhost)**

Proyek ini telah diperbaiki secara lengkap:
- Peta spasial poligon wilayah Bogor sudah dikonversi ke koordinat standar **WGS84 (EPSG:4326)** sehingga ter-render presisi.
- Basemap menggunakan **OpenStreetMap (OSM)** bersih tanpa watermark.
- Filter unsur hara interaktif: **Kadar pH**, **Nitrogen (N)**, **Fosfor (P)**, **Kalium (K)**, dan **Zona Kesuburan AI** (K-Means K=3).
- Sistem Rekomendasi Pemupukan berbasis **Hukum Minimum Liebig** dan kesesuaian tanaman (Padi, Jagung, Kedelai).
- Database SQLite lokal (`safrons.db`) sudah terisi data lengkap 191 wilayah hara Bogor dan 3 akun pengujian.

---

## 📋 Prasyarat Sistem
Pastikan laptop/komputer Anda sudah terpasang:
1. **Node.js** (Versi 18 atau 20+) & **npm**
2. **Python** (Versi 3.11 atau 3.12)
3. *(Opsional/Direkomendasikan)*: **uv** (paket manager Python cepat):
   ```bash
   pip install uv
   ```

---

## 🚀 Cara Menjalankan Aplikasi

Buka **2 jendela Terminal / PowerShell** terpisah:

### 1. Terminal 1: Jalankan Backend (FastAPI)
```powershell
# Masuk ke folder backend
cd backend

# OPSI A: Jika memiliki 'uv' (Sangat Cepat & Otomatis)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# OPSI B: Jika menggunakan Python standar biasa
python -m venv .venv
# Di Windows:
.venv\Scripts\activate
# Di Mac/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
> Server Backend akan aktif di: **`http://127.0.0.1:8000`**  
> Dokumentasi API Swagger dapat dibuka di: **`http://127.0.0.1:8000/docs`**

---

### 2. Terminal 2: Jalankan Frontend (React + Vite)
```powershell
# Masuk ke folder frontend
cd frontend

# Pasang dependensi (hanya perlu dijalankan pertama kali)
npm install

# Jalankan server pengembangan
npm run dev
```
> Server Frontend akan aktif di: **`http://127.0.0.1:5173`**

---

## 🔑 Akun untuk Masuk (Login)
Buka browser di **`http://127.0.0.1:5173/login`**, lalu masukkan salah satu akun berikut:

| Peran (Role) | Email | Password | Akses Fitur |
|---|---|---|---|
| **Pengguna / Petani** | `user@safrons.local` | `user123` | Peta Spasial, Diagnosis Liebig, Rekomendasi Pupuk, Simpan Riwayat |
| **Pakar Agronomi** | `expert@safrons.local` | `expert123` | Semua fitur di atas + Panel Pakar (Validasi AI, Review Queue) |
| **Administrator** | `admin@safrons.local` | `admin123` | Semua fitur di atas + Panel Admin (Kelola Pengguna, Audit Log) |

*(Anda juga bisa mendaftar akun baru sendiri melalui tombol **Daftar Akun**).*

---

## 🗺️ Fitur-Fitur Peta yang Tersedia
- **Filter Unsur Hara**: Klik tombol di panel samping kanan (Kadar pH, Nitrogen, Fosfor, Kalium, atau Zona Kesuburan AI) untuk melihat gradasi warna poligon sesuai legenda.
- **Klik Poligon**: Klik salah satu wilayah poligon pada peta untuk memunculkan analisis karakteristik tanah, diagnosis faktor pembatas Liebig, dan rekomendasi pupuk yang tepat.
- **Ganti Basemap**: Tersedia pilihan peta Standar (OSM), Satelit (ESRI), Jalan (HOT OSM), dan Topografi.
