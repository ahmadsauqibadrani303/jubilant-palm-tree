# AGENTS.md — SAFRONS (konteks wajib dibaca AI sebelum ngoding)

> Taruh file ini di ROOT repo induk (yang punya submodule frontend/, backend/, docs/).
> Kalau pakai Claude Code, copy juga jadi `CLAUDE.md`. Kalau Cursor: `.cursor/rules/safrons.mdc`.
> Kalau Copilot: `.github/copilot-instructions.md`. Isinya sama.

## 1. Apa produk ini
SAFRONS (Smart Agriculture and Fertilizer Recommendation System) = WebGIS untuk wilayah Bogor.
Tujuan: bantu petani memutuskan **tanaman apa** dan **pupuk/amelioran apa** berdasarkan kondisi tanah.
Pengguna: user umum (petani), expert (pakar), admin.

Posisi "AI" produk (JANGAN diubah narasinya):
- **Hybrid**: K-Means clustering (zona kesuburan, unsupervised) + Rule-Based System Hukum Minimum Liebig (kesesuaian S1/S2/S3/N + faktor pembatas).
- **Augmented, bukan otomasi penuh**: setiap rekomendasi punya confidence score dan bisa direview/di-override pakar.
- Bukan deep learning, bukan LLM di runtime. Jangan menambah model lain tanpa diminta.

## 2. Arsitektur (SUDAH ADA, jangan dirombak)
| Bagian | Stack | Catatan |
|---|---|---|
| frontend/ | React 19, TS, Vite, Tailwind 3 (token warna custom: `primary`, `surface`, `on-surface`, `outline-variant`, `error`), React Router 7, react-leaflet 5, Turf, Axios, PWA | Teks UI **Bahasa Indonesia** |
| backend/ | FastAPI, SQLAlchemy 2, PostgreSQL 16 + PostGIS, psycopg3, pytest, ruff (line 100) | Teks respons lama **Bahasa Inggris** |
| Deploy | Vercel (FE), Railway (BE), Docker | |

Struktur penting backend: `app/api/{hara,saved_regions,expert,admin,auth,glossaries,expert_*}.py`, `app/services/{hara_diagnosis,hara_lookup}.py`, `app/schemas/*`, `app/models/*`, `database/migrations/001..007_*.sql`.
Struktur penting frontend: `src/pages/**`, `src/layouts/DashboardLayout.tsx` (peta hidup di sini; route `/dashboard` sengaja `<div />`), `src/components/map/{DataPanel,SpatialMap,CropSuitabilityList,SoilMetricsList,MapLegend,MapControls,...}`, `src/hooks/{useHaraDiagnosis,useMapState,useHaraAdvisories,...}`, `src/constants/{navigation,map}.ts`, `src/types/api.types.ts`, `src/utils/agronomyHelper.tsx`.

## 3. Data & logika yang SUDAH berjalan (sumber kebenaran)
- Tabel `hara_bogor`: 191 poligon. Kolom: `id, name, ph_rata2, n_rata2, p_rata2, k_rata2, lithology, soil_great, slope__, texture_of, geom`.
- Rentang nilai: pH ≈ 4.4–6.56; N ≈ 1.3–39; P ≈ 5.8–91; K ≈ 75–3139 (K sangat skewed).
- **No-data**: nilai `-9999` atau `name` ∈ {"water","no data"} → "insufficient_data" / kelas N. Wajib dihormati di semua fitur baru.
- `rule_set_version = "hara-general-v1"` di `services/hara_diagnosis.py`.
- Klasifikasi pH: <4.5 very_acid, <5.6 acid, <6.6 slightly_acid, <7.6 neutral, <8.6 slightly_alkaline, else alkaline.
- NPK = kelas RELATIF berbasis persentil dataset (20/40/60/80), BUKAN satuan lab. Artinya **dosis pupuk presisi (kg/ha) tidak bisa diklaim dari data ini**.
- Kesesuaian lahan: `CROP_CRITERIA` (jagung, kacang_tanah, kakao × ph/n/p/k) → kelas terburuk = kelas akhir (Liebig), `limiting_factors` = parameter dengan rank terburuk.
  ⚠ Kriteria ini ADA DUA TEMPAT dan harus sinkron: Python (`CROP_CRITERIA`) dan SQL (`007_land_suitability.sql`, tabel `crop_suitability_criteria` + view `hara_crop_suitability`).
- Endpoint existing (kontrak TIDAK boleh berubah): `GET /api/v1/hara/areas`, `/areas/{id}`, `/areas/{id}/diagnosis`, `/areas/{id}/advisories`, `/point`, `/point/diagnosis`, plus auth, saved_regions, expert, admin, glossaries, expert analytics.
- Startup backend menjalankan semua `database/migrations/*.sql` **hanya jika tabel `hara_bogor` belum ada**, lalu `ensure_*_tables()` untuk tabel lain. ⚠ Migration baru TIDAK otomatis jalan di DB yang sudah ada → tabel baru harus lewat pola `ensure_*_tables()` (idempotent `CREATE TABLE IF NOT EXISTS`) DAN dicatat sebagai file migration `008_*.sql`.
- Test existing: `backend/tests/test_*.py` (auth, hara, diagnosis, crop_suitability, expert, saved_regions, admin_rbac, health). Semuanya harus tetap hijau.

## 4. ATURAN KERAS (hard constraints)
1. **Additive only.** Dilarang menghapus/mengubah nama/mengubah bentuk respons endpoint, kolom DB, route, komponen, hook, atau tipe yang sudah ada. Boleh menambah field opsional dan file baru.
2. **Jangan ubah tampilan existing**: warna, layout, spacing, class Tailwind, copywriting, urutan section DataPanel, bottom nav (5 item), navbar. UI baru harus memakai token & pola yang sama (rounded-2xl/3xl, `font-display`, `bg-surface/95`, ikon Heroicons outline, cursor-pointer, animasi `animate-fade-in-up`).
3. Jangan refactor "sekalian". Jangan upgrade dependency existing. Jangan ganti state management/router/HTTP client.
4. Jangan menyentuh `CROP_CRITERIA`, ambang pH/NPK, atau `hara-general-v1` kecuali diminta eksplisit. Fitur baru MEMANGGIL logika itu, bukan menyalinnya.
5. **Jangan mengarang angka agronomi.** Dosis pupuk, ambang, dan sumber ilmiah yang belum ada di repo/dokumen → taruh sebagai konfigurasi bernilai `null` + `TODO(expert)`, UI menampilkan saran kualitatif ("dosis ditentukan setelah uji tanah/penyuluh"). Jangan pernah menampilkan "kg/ha presisi" dari data relatif ini.
6. Semua keluaran AI wajib: `confidence` (0–1 + kategori tinggi/sedang/rendah), `model_version`, `rule_set_version`, `needs_expert_review` (bool), dan disclaimer "indikatif, bukan pengganti uji tanah". Precision lebih diprioritaskan daripada recall: ragu → turunkan klaim / minta review pakar, jangan agresif merekomendasikan.
7. Hormati RBAC existing (`user`/`expert`/`admin`). Endpoint review hanya expert/admin. Data Save Region = data pribadi: tidak masuk training/analitik tanpa consent.
8. Tidak ada secret di kode. Env baru → tambahkan ke `.env.example`.
9. Setiap perubahan: test baru + test lama hijau (`pytest`, `ruff check`, `npm run build`, `npm run lint`).
10. Kalau instruksi bertentangan dengan file ini → BERHENTI dan tanya, jangan menebak.

## 5. Target mutu (dari LKP P4/P5)
Precision ≥ 90%, recall ≥ 85% (diukur terhadap label pakar/rules — laporkan jujur metodenya), inferensi ≤ 1,5 dtk, render peta ≤ 3 dtk, interpretability ≥ 4,2/5, SUS ≥ 75, maksimal 3 tap ke hasil di mobile.

## 6. Cara kerja yang diharapkan dari AI
- Mulai dengan membaca file terkait, bikin rencana singkat, tunggu OK untuk perubahan besar.
- Kerjakan per fase kecil, tiap fase bisa dijalankan & dites sendiri.
- Akhir tiap fase: daftar file diubah/ditambah, bukti test, dan "apa yang sengaja TIDAK disentuh".
- Tandai asumsi dengan `ASSUMPTION:` dan hal yang butuh pakar dengan `TODO(expert):`.
