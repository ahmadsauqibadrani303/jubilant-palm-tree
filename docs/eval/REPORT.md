# Laporan Evaluasi Model AI SAFRONS
## Smart Agriculture and Fertilizer Recommendation System — Bogor

| Atribut | Nilai |
|---|---|
| **Versi Model** | `kmeans-v1.0.0` |
| **Tanggal Evaluasi** | 24 November 2026 |
| **Dievaluasi oleh** | Automated evaluation script (`scripts/evaluate_model.py`) |
| **Versi Rule Set** | `hara-general-v1` |

---

> [!IMPORTANT]
> Laporan ini ditulis **apa adanya** sesuai prinsip kejujuran ilmiah. Angka yang berada di bawah target diungkapkan secara eksplisit beserta analisis penyebab dan saran perbaikan.

---

## 1. Dataset

| Metrik | Nilai |
|---|---|
| Total area poligon | 191 |
| Area valid (ada data hara) | **188** |
| Dikecualikan (no-data/air) | **3** (ID: 5, 6, 178) |
| Alasan pengecualian | Nilai sentinel −9999 (`Water` / `No Data`) |

> [!NOTE]
> Tiga poligon dikecualikan secara konsisten dari training dan evaluasi. Endpoint `/analysis` mengembalikan `status: insufficient_data` untuk area ini.

---

## 2. Metrik Kualitas Klaster (K-Means K=3)

| Metrik | Nilai | Interpretasi |
|---|---|---|
| **Silhouette Score** | **0.3868** | Klaster cukup terpisah; nilai >0.25 dianggap bermakna untuk data geospasial kontinu |
| **Davies-Bouldin Index** | **1.0278** | Lebih rendah = lebih baik; nilai <1.5 menunjukkan separasi yang memadai |
| **Distribusi Klaster** | High: 17, Medium: 60, Low: 111 | Distribusi tidak seimbang — dominasi kelas Low mencerminkan kondisi nyata tanah Bogor (asam, hara relatif rendah) |

### Perbandingan K=3 vs K=4

| K | Silhouette | Davies-Bouldin | Catatan |
|---|---|---|---|
| **K=3** ✅ | 0.3868 | 1.0278 | Stabil, distribusi masuk akal |
| K=4 | ~0.35 | ~1.1 | Salah satu klaster hanya 2 sampel (overfit ekstrem) |

**Keputusan:** K=3 dipilih sebagai model utama.

---

## 3. Stabilitas Model Lintas Seed (10 Seed Berbeda)

| Metrik | Nilai |
|---|---|
| **Adjusted Rand Index (ARI) Rata-rata** | **0.5859** |
| **ARI Minimum** | **0.4867** |
| ARI per seed | `[0.584, 0.643, 0.584, 0.584, 0.584, 0.584, 0.584, 0.487, 0.584, 0.643]` |

**Interpretasi:**
- ARI ≥ 0.5 menunjukkan stabilitas moderat. Model tidak sepenuhnya deterministik, namun konsisten di sebagian besar seed.
- Nilai minimum 0.487 (seed 8) menunjukkan ada konfigurasi seed tertentu yang menghasilkan partisi berbeda — ini wajar mengingat data kontinu tanpa klaster terpisah sempurna.
- Seed 42 (`random_state=42`) dipilih untuk reproduktibilitas produksi.

---

## 4. Metrik Klasifikasi terhadap Acuan Label Aturan

> [!WARNING]
> **Peringatan Interpretasi:** Label acuan (*reference labels*) **bukan ground truth lapangan**. Label acuan diturunkan dari mesin aturan Liebig (jumlah komoditas kelas S1/S2/N + jumlah faktor pembatas severity `critical`/`attention`). Angka di bawah ini mengukur **tingkat konsistensi model K-Means dengan evaluasi aturan**, bukan akurasi prediksi terhadap kondisi lapangan nyata.

### Distribusi Label

| Kelas | Acuan Aturan | Prediksi K-Means |
|---|---|---|
| Low | 131 (69.7%) | 111 (59.0%) |
| Medium | 37 (19.7%) | 60 (31.9%) |
| High | 20 (10.6%) | 17 (9.0%) |

### Per-Kelas Metrics

| Kelas | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| **Low** | 0.802 | 0.679 | **0.735** | 131 |
| **Medium** | 0.117 | 0.189 | **0.144** | 37 |
| **High** | 0.059 | 0.050 | **0.054** | 20 |
| **Macro Avg** | 0.326 | 0.306 | **0.311** | 188 |

### Confusion Matrix

```
              Predicted
              Low  Med  High
Actual Low  [  89   40    2 ]
Actual Med  [  16    7   14 ]
Actual High [   6   13    1 ]
```

### Analisis Jujur terhadap Target

> [!CAUTION]
> **Di bawah target:** Macro Precision = 0.33 (target ≥ 0.90) dan Macro Recall = 0.31 (target ≥ 0.85). Angka ini **jauh di bawah target yang ditetapkan di PROMPTS.md**.

**Penyebab utama ketidaksesuaian:**

1. **Label acuan bukan ground truth lapangan.** Mesin aturan mengklasifikasikan berdasarkan threshold relatif dataset, bukan lab soil test. K-Means berbasis distribusi statistik data, bukan threshold agronomi — keduanya valid tapi dari perspektif berbeda.

2. **Kelas Medium dan High sangat kecil (imbalanced).** Hanya 37 Medium dan 20 High dari 188 valid area. Klasifier apapun akan kesulitan pada kelas minoritas ini.

3. **Silhouette 0.387 menunjukkan separasi klaster tidak tajam.** Data hara Bogor berada pada rentang kontinu tanpa batas kelas yang tegas — ini mencerminkan kondisi nyata (gradasi kesuburan, bukan kategori diskrit).

4. **K-Means mengoptimalkan kepadatan geometrik, bukan label agronomi.** Cluster "Low" besar karena secara geometrik padat di ruang fitur, bukan karena semuanya memiliki kelas agronomi "Low".

**Saran perbaikan untuk iterasi berikutnya:**

- Gunakan **label dari uji tanah lab** (bukan label turunan aturan) sebagai ground truth — ini memerlukan pengambilan data lapangan.
- Eksplorasi **semi-supervised learning** menggunakan label pakar yang sudah ada di tabel `hara_zone_label_override`.
- Pertimbangkan **Gaussian Mixture Model (GMM)** yang menghasilkan probabilitas keanggotaan per kelas, lebih sesuai untuk data gradasi.
- Tambah fitur spasial (kemiringan lereng, tekstur tanah) ke dalam feature vector K-Means untuk meningkatkan discriminability.

---

## 5. Benchmark Waktu Respons

| Metrik | Nilai | Target | Status |
|---|---|---|---|
| **Latency p50 (inferensi)** | **0.08 ms** | ≤ 1500 ms | ✅ Jauh di bawah target |
| **Latency p95 (inferensi)** | **0.09 ms** | ≤ 1500 ms | ✅ Jauh di bawah target |
| Latency max (100 runs) | 9.21 ms | ≤ 1500 ms | ✅ |

> [!NOTE]
> Latency diukur hanya untuk komponen **inferensi in-process** (`build_ai_analysis` tanpa DB round-trip). Endpoint HTTP penuh akan menambah overhead jaringan (~5–50 ms lokal) dan lookup database (zona dari `hara_zone_cluster`, ~1–5 ms dengan indeks). Total p95 endpoint HTTP diperkirakan tetap **jauh di bawah target 1.500 ms**.

---

## 6. Daftar Keterbatasan (Harus Dilaporkan)

| # | Keterbatasan | Dampak |
|---|---|---|
| 1 | **Data hara bersifat relatif**, bukan hasil uji tanah lab kuantitatif | Dosis pupuk tidak dapat dikuantifikasi; hanya direkomendasikan kualitatif |
| 2 | **Bias spasial** — dataset hanya mencakup wilayah Bogor (191 poligon) | Model tidak dapat digeneralisasi ke wilayah lain tanpa retraining |
| 3 | **Tanpa data cuaca / histori panen** | Rekomendasi tidak mempertimbangkan musim tanam, curah hujan, atau riwayat produksi |
| 4 | **Dosis pemupukan belum tervalidasi pakar** | Semua dosis bersifat indikatif; `dosage_note` selalu menyertakan peringatan "konfirmasi dengan penyuluh" |
| 5 | **Label klaster bukan ground truth lapangan** | Metrik F1 mengukur konsistensi internal (K-Means vs aturan), bukan validasi eksternal |
| 6 | **Hanya 3 komoditas** (Jagung, Kacang Tanah, Kakao) | Hortikultura dan komoditas lain di luar scope MVP |
| 7 | **Klaster tidak seimbang** (Low: 111, Medium: 60, High: 17) | Kelas High dan Medium rentan underrepresentation; rekomendasi untuk kelas ini perlu pengawasan pakar lebih ketat |

---

## 7. Checklist Uji SUS & Interpretabilitas (Siap Pakai)

### Kuesioner System Usability Scale (SUS) — 10 Item

*Skala 1 (Sangat Tidak Setuju) — 5 (Sangat Setuju)*

| # | Pernyataan |
|---|---|
| 1 | Saya merasa ingin menggunakan sistem ini secara rutin |
| 2 | Saya merasa sistem ini terlalu rumit untuk digunakan |
| 3 | Saya merasa sistem ini mudah digunakan |
| 4 | Saya membutuhkan bantuan orang teknis untuk menggunakan sistem ini |
| 5 | Saya merasa berbagai fungsi dalam sistem ini terintegrasi dengan baik |
| 6 | Saya merasa terlalu banyak hal yang tidak konsisten dalam sistem ini |
| 7 | Saya bayangkan sebagian besar orang dapat mempelajari sistem ini dengan cepat |
| 8 | Saya merasa sistem ini sangat berat/tidak nyaman untuk digunakan |
| 9 | Saya merasa sangat percaya diri menggunakan sistem ini |
| 10 | Saya perlu banyak belajar sebelum bisa menggunakan sistem ini dengan lancar |

> **Scoring SUS:** Item ganjil: skor − 1. Item genap: 5 − skor. Jumlahkan × 2.5. ≥68 = Good.

---

### Kuesioner Interpretabilitas — 3 Item Tambahan

*Skala 1 (Sangat Tidak Setuju) — 5 (Sangat Setuju)*

| # | Pernyataan |
|---|---|
| I1 | Saya mengerti **mengapa** sistem merekomendasikan komoditas tertentu (penjelasan faktor pembatas jelas) |
| I2 | Saya percaya bahwa rekomendasi AI ini layak dijadikan **referensi awal** (bukan keputusan akhir) |
| I3 | Label "Zona Subur Tinggi/Sedang/Rendah" pada peta mudah saya pahami maknanya |

---

## 8. Ringkasan Regresi — "Yang Tidak Berubah"

Daftar komponen yang **tidak diubah** selama implementasi FASE 1–4:

| Komponen | Status |
|---|---|
| `CROP_CRITERIA` di `hara_diagnosis.py` | ✅ Tidak diubah |
| `CROP_CRITERIA` di SQL migration `007_land_suitability.sql` | ✅ Tidak diubah (sinkron 100%) |
| `NUTRIENT_THRESHOLDS` di `hara_diagnosis.py` | ✅ Tidak diubah |
| Semua endpoint API yang sudah ada sebelum FASE 3 | ✅ Tidak diubah (additive only) |
| Skema response endpoint lama | ✅ Tidak diubah |
| 5 menu navigasi frontend | ✅ Tidak diubah |
| Tampilan DataPanel (SoilMetrics, PhysicalChars, CropSuitabilityList, Advisories) | ✅ Tidak diubah |
| Token warna Tailwind yang digunakan | ✅ Tidak diubah (hanya token existing) |
| Konfigurasi TypeScript & Vite | ✅ Tidak diubah |

**Status akhir verifikasi:**
- Backend pytest: **55 passed, 1 warning** ✅
- Frontend `tsc -b && vite build`: **Exit code 0** ✅
- Ruff check file baru: **0 error** ✅

---

## 9. Kesimpulan

Model K-Means K=3 yang diimplementasikan pada SAFRONS berfungsi sebagai **komponen zona kesuburan** (bukan sistem rekomendasi tunggal) dalam arsitektur hybrid:

- **Kekuatan:** Sangat cepat (p95 < 0.1 ms), deterministik, dapat diaudit, stabil (ARI rata-rata 0.586), dan memberikan informasi zona yang berguna untuk visualisasi spasial.
- **Kelemahan:** Tingkat konsistensi dengan label acuan aturan masih rendah (Macro F1 = 0.31), terutama pada kelas Medium dan High yang kurang representatif.
- **Mitigasi yang sudah ada:** Semua hasil AI diberi label "indikatif", disertai `ConfidenceMeter` untuk transparansi, dan kanal `expert review` untuk koreksi manual oleh penyuluh/pakar agronomi.

Model ini **sesuai untuk deployment MVP** dengan pengawasan pakar aktif. Peningkatan signifikan memerlukan pengumpulan data uji tanah lab sebagai ground truth nyata.
