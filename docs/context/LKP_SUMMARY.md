# SAFRONS — Ringkasan LKP P3–P5 (konteks untuk AI agent)

> Simpan di `docs/context/LKP_SUMMARY.md`. Ini ringkasan keputusan tim (Kelompok 8). Kalau bertabrakan dengan kode yang ada, kode yang ada menang untuk perilaku saat ini; tandai konflik, jangan diam-diam menyamakan.

## P3 — Problem framing & pendekatan AI (Chapter 3)
- **Pengguna**: petani kecil / pengelola lahan di Bogor dan sekitarnya.
- **Masalah**: sulit memahami kondisi hara tanah dan menentukan komoditas yang sesuai.
- **Solusi (1 kalimat)**: SAFRONS menganalisis kondisi lahan dan memberi rekomendasi komoditas + pengelolaan lahan.
- **Data**: tabular (pH, N, P, K, slope, tekstur; 191 area Bogor), poligon (WGS84/SRID 4326), teks (kelas reaksi tanah Balittanah 2005, panduan FAO, glosarium).
- **Pendekatan AI**: Rule-Based dicentang. Diagnosis: pH kelas baku, NPK band persentil dataset. Kesesuaian: hukum minimum Liebig (kelas terburuk = kelas akhir). Predictive, Generative, Agentic: TIDAK dipakai (di P3).
- **UX**: Graphical; otomasi **Augmented** (AI rekomendasi, manusia/pakar review).
- **Blueprint**: Input (poligon + titik pilihan) → Intelligence (rule-based + Liebig bucket) → UX (WebGIS React+Leaflet) → Value (info kesuburan mudah dipahami; pakar punya kanal informasi terkontrol).
- **Keputusan**: GO. Checklist masalah/data/AI/UX lengkap.

## P4 — Strategi data & kelayakan (Chapter 4)
**Data & fitur**: pH, N, P, K, slope, tekstur (+ lokasi). Tahap lanjut: data lab/lapangan, cuaca, komoditas, histori panen. Pola perilaku yang dianggap penting: area dipilih, hara dilihat, komoditas disimulasikan, rekomendasi yang dipakai.

**Algoritma**: **K-Means** (alternatif evaluasi: Hierarchical). Alasan: 191 poligon, fitur numerik kontinu terstandarisasi, ringan di FastAPI/PostGIS, mudah dipetakan ke zona di Leaflet.
- **Jumlah cluster**: 3 (Rendah/Defisit, Sedang/Optimal, Tinggi/Kaya) atau 4 (selaras S1/S2/S3/N). Penentuan: Elbow (WCSS), Silhouette, Calinski-Harabasz + validasi domain agronomi.
- **Prioritas**: interpretability > akurasi. Contoh penjelasan target: "Lahan masuk cluster Defisit karena P sangat rendah dan pH asam, sehingga perlu fosfat dan pengapuran."

**Labeling**: semi-otomatis. Label awal dari sistem pakar (kelas pH, kesesuaian Liebig); pengguna **expert** memvalidasi/mengoreksi. QA: **audit trail** setiap perubahan label, definisi seragam antar-expert, pantau distribusi kelas berkala (anti-bias). Data diperkirakan tidak seimbang (kelas tengah dominan, ekstrem jarang). Dua fase yang disebut di materi: K-Means lalu classifier supervised dari label cluster.

**Metrik ML → metrik produk**:
- False positive lebih berbahaya (menyatakan "sangat sesuai" padahal tidak) → **precision diprioritaskan**.
- Precision kesesuaian komoditas → kepercayaan petani terhadap rekomendasi.
- Recall deteksi area kritis → jumlah area berisiko yang berhasil ditindak.
- Metrik produk lain: % petani yang mengikuti rekomendasi.
- Stakeholder prioritas: petani > expert > admin.

**Time series (tahap lanjut)**: cuaca harian (hujan, suhu) dan histori panen/komoditas; anomali yang dikhawatirkan: hara tidak wajar, cuaca ekstrem, perubahan lahan tidak wajar.

**Etika & privasi**:
- Data sensitif: koordinat presisi lahan pengguna dan identitas akun (Save Region).
- Minimisasi: hanya atribut biofisik tanah; koordinat privat diagregasi/dikaburkan di peta publik; identitas dipisah dari data spasial.
- Bias: **spasial** (lereng Salak/Gede-Pangrango kurang terwakili) → spatial weighting, tandai zona dengan confidence rendah, kanal data lapangan bersama penyuluh; **komoditas/aturan** (ambang Liebig terlalu kaku, hanya 3 tanaman) → panel pakar review berkala + fitur parameter kustom untuk ahli agronomi.
- Consent: banner transparansi + **opt-in eksplisit** (data anonim untuk validasi/kalibrasi), bisa **opt-out**, pengguna bisa lihat/hapus wilayah simpanan kapan saja, data lokasi dienkripsi; penjelasan di Glosarium/FAQ.

## P5 — SRS, IA, Sitemap
**Deskripsi**: sistem pendukung keputusan WebGIS + AI: analisis hara (pH, N, P, K, lereng) → rekomendasi kesesuaian komoditas + panduan dosis pemupukan, untuk petani/kelompok tani/PPL di Bogor. Output = **augmented advisory** (bukan otomasi mandiri). Asumsi pengguna: Android, browser modern, 3G/4G, literasi digital pemula–menengah; bahasa lugas tanpa jargon.

**In-scope MVP**: peta interaktif 191 poligon; diagnosis hara (rule-based); rekomendasi kesesuaian komoditas (Liebig + klasterisasi status hara); rekomendasi dosis/tindakan (Urea, SP-36, KCl, pengapuran); kartu ringkasan lahan yang bisa disimpan/diekspor ringkas.
**Out-of-scope**: IoT/sensor/stasiun cuaca, marketplace saprotan, computer vision hama/penyakit, voice bot (termasuk Sunda), prediksi panen.

**Fitur (user story ringkas)**
| # | Fitur | AI? | Prioritas |
|---|---|---|---|
| 1 | Peta WebGIS & pilih zona lahan | Non-AI | Must |
| 2 | Diagnosis status hara (Sangat Rendah–Sangat Tinggi) | AI rule-based | Must |
| 3 | Rekomendasi kesesuaian komoditas S1/S2/S3/N + ranking | AI Liebig + K-Means | Must |
| 4 | Panduan dosis pemupukan & pengapuran | AI rule-based advisory | Must |
| 5 | Simpan lahan & riwayat rekomendasi (Save Region), unduh kartu ringkas | Non-AI | Should |
Pendukung yang disebut: pencarian/filter wilayah (Kecamatan/Desa), profil, glosarium.

**NFR (terukur)**
| Kategori | Target | Cara ukur |
|---|---|---|
| Akurasi | Precision kesesuaian ≥90%; recall defisit kritis ≥85%; inferensi rule-based 100% deterministik | Confusion matrix + cross-validation pada 191 poligon berlabel pakar; audit penyuluh |
| Kecepatan | Inferensi ≤1,5 dtk setelah poligon dipilih; peta + layer ≤3 dtk (3G/4G) | Benchmark API p95; Lighthouse/WebPageTest |
| Privasi | Data minimization; koordinat privat & identitas terenkripsi **AES-256**; opt-in consent; hak hapus | Audit keamanan/DB, cek toggle consent |
| Explainability | Setiap rekomendasi menyertakan alasan/faktor pembatas eksplisit; tanpa black-box. Skor ≥4,2/5 | UAT petani + penyuluh |
| Usability | UI bersih; **teks penting ≥14pt**; warna kontras hijau/kuning/merah; buka peta → rekomendasi **maks. 3 tap** | SUS ≥75 |

**IA (4 menu, bottom navigation)**
1. Dashboard/Peta: peta WebGIS, pencarian wilayah
2. Rekomendasi: diagnosis hara, kesesuaian komoditas, rekomendasi pupuk
3. Riwayat Lahan: lahan tersimpan, riwayat rekomendasi, ekspor ringkasan
4. Profil & Panduan: profil, glosarium, pengaturan privasi
(Isian "pola navigasi yang dipilih & alasannya" di LKP masih kosong; jawaban diskusinya: bottom nav 4 menu karena sederhana & cocok smartphone.)

**Sitemap**: Entry = Login/Registrasi → Dashboard/Peta. Tamu boleh lihat peta & info dasar; simpan lahan butuh akun. Critical path: Dashboard → pilih poligon → diagnosis → rekomendasi komoditas → rekomendasi pupuk (≤3 tap).

---
## Catatan untuk agent: celah & konflik antara LKP dan kode saat ini
(Verifikasi sendiri di repo sebelum bertindak; jangan asumsikan.)

| Hal | LKP bilang | Kode (yang gue lihat) | Perlakuan |
|---|---|---|---|
| Posisi AI | P3: hanya rule-based; P4/P5: K-Means + precision/recall | Hanya rule-based, belum ada ML | Narasi final: hybrid K-Means (zona) + Liebig (kesesuaian). Jangan klaim "predictive" |
| Tanaman | P5 menyebut hortikultura | Hanya jagung, kacang tanah, kakao; kriteria hortikultura belum ada | Di luar MVP; jangan mengarang kriteria |
| Dosis | "dosis presisi/terukur" Urea/SP-36/KCl | NPK relatif (persentil), tanpa satuan lab/metode ekstraksi | Kualitatif + tabel dosis kosong untuk pakar (`TODO(expert)`); jangan klaim kg/ha presisi |
| Navigasi | 4 menu | 5 item (Beranda, Peta, Tersimpan, Tentang, Glosarium) | Jangan diubah tanpa keputusan tim |
| Filter Kecamatan/Desa | ada di fitur pendukung | tidak terlihat di kode | Belum ada data administratif; backlog |
| Consent opt-in/opt-out, hapus data | wajib | belum terlihat | Kandidat fitur kecil (Fase lanjut) |
| AES-256 untuk koordinat/identitas | NFR | belum terlihat | Verifikasi; jangan klaim sebelum ada |
| Ekspor kartu ringkasan | Should | belum terlihat | Backlog |
| Audit trail koreksi label | QA P4 | ada model `hara_area_change` (kemungkinan sudah mencatat perubahan data) | Verifikasi cakupan; perluas ke review analisis AI |
| Confidence level | zona minim sampel diberi confidence rendah | belum ada | Termasuk di fitur AI baru |
| Teks ≥14pt, kontras | NFR usability | belum diaudit | Cek di komponen baru |
