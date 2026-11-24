# SAFRONS — Paket Prompt Vibe Coding

Cara pakai: (1) taruh `AGENTS.md` di root repo, (2) kasih prompt di bawah **satu per satu, urut**, (3) jangan lanjut fase berikutnya sebelum test fase sebelumnya hijau, (4) commit tiap fase supaya gampang rollback.

## A. Yang harus lu kirim/siapkan ke AI

| Wajib | Kenapa |
|---|---|
| Repo asli (frontend + backend) terbuka di Claude Code/Cursor, bukan paste potongan | AI harus bisa baca & jalankan test sendiri |
| `AGENTS.md` (file ini di atas) | Guardrail "jangan ubah yang ada" |
| `backend/reference/data-hara-bogor/hara-bogor.geojson` atau akses DB lokal | Buat training K-Means & cek distribusi data |
| Ringkasan LKP P3-P5 (cukup 1 halaman: NFR, definisi confidence, alur expert review) — taruh di `docs/context/` | Supaya target mutu & narasi AI konsisten |
| Screenshot wireframe Figma per layar (PNG) di `docs/wireframe/` | Link Figma tidak bisa dibuka AI coding biasa. Kalau tool lu punya Figma MCP, kasih link + node-id layar yang dimaksud |
| Screenshot aplikasi sekarang (safrons.vercel.app) | Jadi acuan "jangan berubah" |
| Keputusan lu (isi di Bagian B) | Hal yang tidak boleh AI tebak |
| Sumber dosis/pemupukan dari pakar/dosen/Permentan (kalau ada) | Tanpa ini dosis tetap kualitatif (lihat aturan 5) |

Jangan kirim: file `.env`, kredensial DB/Railway, `node_modules`, `.git`.

## B. Keputusan yang perlu lu isi dulu (kalau kosong, AI pakai default di kolom kanan)

| Keputusan | Default |
|---|---|
| Jumlah cluster | K=3 (Subur Tinggi / Sedang / Rendah); coba K=4 hanya sebagai pembanding silhouette |
| Fitur clustering | pH, N, P, K (K di-log-transform, di-StandardScaler). Slope & tekstur TIDAK masuk cluster, dipakai di rekomendasi |
| Dosis pupuk | Kualitatif dulu; tabel dosis diisi pakar belakangan |
| Hortikultura | Di luar MVP (data kriteria belum ada), tetap 3 tanaman |
| Menu navigasi | Tetap 5 item sekarang; wireframe 4 menu tidak diterapkan sampai lu putuskan |
| Cuaca/histori panen/time series | Tidak dikerjakan (tahap lanjut) |

## C. Prompt per fase

### FASE 0 — Audit (tanpa mengubah kode)
```
Baca AGENTS.md dulu, lalu baca kode backend dan frontend yang relevan
(backend/app/services/hara_diagnosis.py, services/hara_lookup.py, api/hara.py,
schemas/diagnosis.py, database/migrations/007_land_suitability.sql, app/main.py;
frontend/src/components/map/DataPanel.tsx, CropSuitabilityList.tsx, MapLegend.tsx,
hooks/useHaraDiagnosis.ts, hooks/useMapState.ts, layouts/DashboardLayout.tsx, types/api.types.ts).

JANGAN ubah file apa pun. Jalankan test backend & build frontend untuk baseline.
Keluarkan:
1. Baseline: hasil pytest, ruff, npm run build, npm run lint.
2. Peta alur data: klik poligon -> DataPanel -> diagnosis (endpoint, hook, komponen).
3. Titik ekstensi yang AMAN untuk fitur baru (file baru vs file existing yang perlu disentuh tipis).
4. Risiko: apa yang bisa rusak (mis. kriteria kesesuaian ada di Python dan SQL, migration hanya jalan jika hara_bogor belum ada).
5. Pertanyaan yang harus gue jawab sebelum implementasi.
Tunggu persetujuan gue sebelum lanjut.
```

### FASE 1 — Pipeline K-Means (backend, offline)
```
Konteks: AGENTS.md. Tujuan: zona kesuburan tanah dengan K-Means.

Tambah (file baru, jangan ubah service lama):
- pyproject.toml: tambah scikit-learn, numpy, joblib (tanpa upgrade dependency lain).
- backend/app/ml/features.py: ambil pH, N, P, K dari hara_bogor; buang no-data
  (-9999, name 'water'/'no data'); log1p untuk K; StandardScaler; kembalikan juga id area yang dibuang + alasannya.
- backend/app/ml/clustering.py: KMeans(K=3, n_init=20, random_state=42). Hitung silhouette,
  Davies-Bouldin, ukuran tiap cluster, dan bandingkan K=3 vs K=4 (hanya dilaporkan).
  Urutkan cluster berdasarkan indeks kesuburan centroid (rata-rata z-score pH,N,P,K di ruang terstandar)
  -> label "Zona Subur Tinggi / Sedang / Rendah". Label bukan hasil cluster_id mentah.
- backend/scripts/train_clusters.py: training offline, simpan artefak (joblib scaler+model) dan
  metadata.json (model_version, k, silhouette, davies_bouldin, tanggal, jumlah data, centroid
  dalam skala asli) ke backend/app/ml/artifacts/. Training TIDAK jalan saat request.
- Tabel baru hara_zone_cluster(area_id PK/FK, cluster_id, zone_key, zone_label, dist_to_centroid,
  dist_to_second, model_version, trained_at) + hara_zone_label_override(area_id, zone_key, expert_id, note, created_at)
  untuk koreksi pakar. Buat lewat pola ensure_*_tables() DAN file database/migrations/008_zone_cluster.sql (idempotent).
- Script mengisi hara_zone_cluster untuk 191 area (no-data -> zone_key 'unknown').

Test (pytest, tanpa butuh Postgres untuk bagian murni ML; pakai fixture data kecil):
no-data dibuang, hasil deterministik (random_state), urutan label konsisten antar run,
tiap area tepat satu zona, centroid terurut.

Keluaran akhir: tabel metrik (silhouette, DB, ukuran cluster), centroid skala asli per zona,
dan ASSUMPTION/TODO(expert) yang muncul. Jangan lanjut ke endpoint.
```

### FASE 2 — Mesin rekomendasi + confidence (backend)
```
Konteks: AGENTS.md. Fase 1 selesai. Buat backend/app/services/recommendation.py (file baru).
Fungsi build_ai_analysis(area, db) yang MEMANGGIL build_hara_diagnosis & get_crop_suitability
(jangan salin ambang/kriteria), lalu menghasilkan:

1. zone: zone_key, zone_label, dari hara_zone_cluster (override pakar menang jika ada).
2. limiting_factors global lahan: faktor yang paling membatasi (pH/N/P/K/slope) diurutkan dari
   severity diagnosis, dengan penjelasan Bahasa Indonesia singkat (kenapa jadi pembatas).
3. crop_ranking: 3 tanaman diurutkan S1>S2>S3>N; tie-break: jumlah faktor pembatas lebih sedikit,
   lalu jumlah parameter berkelas S1 lebih banyak. Setiap item: kelas, limiting_factors,
   alasan 1 kalimat, dan flag 'not_recommended' bila N.
4. amendment_advice per faktor pembatas: jenis tindakan & kategori input
   (mis. pengapuran untuk tanah masam; sumber N/P/K; konservasi untuk slope curam; bahan organik).
   Dosis: baca dari backend/app/services/fertilizer_rules.py (file konfigurasi baru) yang nilainya
   default None + TODO(expert). Bila dosis None -> kirim teks kualitatif
   "Dosis ditentukan setelah uji tanah/arahan penyuluh". DILARANG mengarang angka kg/ha.
5. confidence (0..1) + kategori, dengan komposisi TRANSPARAN dan dikembalikan sebagai breakdown:
   - cluster_margin = 1 - d1/(d1+d2)   (seberapa jelas area masuk zonanya)
   - data_completeness (0..1; no-data -> 0 dan analisis ditolak)
   - rule_zone_agreement (zona subur-tinggi tapi semua tanaman N = tidak konsisten -> turun)
   - dekat batas kelas (nilai berjarak < 5% rentang dari ambang S) -> penalti
   confidence = rata-rata tertimbang (bobot di konstanta, bukan angka ajaib tersebar). Kategori:
   >=0.75 tinggi, 0.5-0.75 sedang, <0.5 rendah. needs_expert_review = True bila rendah,
   atau bila rekomendasi teratas bukan S1/S2, atau bila ada faktor 'critical'.
6. meta: model_version, rule_set_version, generated_at, disclaimer
   ("Rekomendasi indikatif berdasarkan data hara relatif; konfirmasi dengan uji tanah").
7. status 'insufficient_data' untuk no-data; jangan pernah menebak.

Schema Pydantic baru di app/schemas/analysis.py. Test: tiap cabang confidence, tie-break,
no-data, override pakar, dan test bahwa hasil kesesuaian == get_crop_suitability (tidak diubah).
Test lama harus hijau. Keluarkan ringkasan formula confidence supaya bisa masuk laporan.
```

### FASE 3 — Endpoint (additive)
```
Konteks: AGENTS.md. Tambah router baru backend/app/api/analysis.py, daftarkan di main.py
(tanpa mengubah router lain):
- GET /api/v1/hara/areas/{area_id}/analysis -> response schema analysis
- GET /api/v1/hara/point/analysis?lon=&lat=
- GET /api/v1/hara/zones -> ringan: [{area_id, zone_key, zone_label, confidence_category}] untuk layer peta
  (Cache-Control seperti /areas, gzip sudah aktif)
- GET /api/v1/ml/model-info -> versi model, metrik, tanggal latih (public)
- POST /api/v1/expert/areas/{area_id}/analysis-review (role expert/admin, pakai deps RBAC existing):
  body {decision: 'validated'|'overridden', zone_key?, note}; simpan ke tabel
  analysis_review(area_id, expert_id, decision, zone_key, note, created_at); override zona menulis ke
  hara_zone_label_override. Response analysis ikut menyertakan status review terakhir.
- GET /api/v1/expert/analysis-review/queue -> area needs_expert_review yang belum direview.
Target inferensi ≤ 1,5 dtk: baca zona dari tabel (bukan hitung ulang K-Means), tambahkan test waktu respons.
Test RBAC (user biasa 403, tanpa token 401) mengikuti pola test_admin_rbac.py.
Update README backend: daftar endpoint baru + cara menjalankan train_clusters.py.
```

### FASE 4 — Frontend (tampilan lama tidak berubah)
```
Konteks: AGENTS.md. WAJIB pertahankan semua tampilan & perilaku existing. Tambah saja:

1. types/api.types.ts: tambah tipe AiAnalysis, ZoneInfo, ConfidenceBreakdown, dll (tipe lama tidak diubah).
2. services/analysis.service.ts + hooks/useHaraAnalysis.ts (meniru pola useHaraDiagnosis.ts; batalkan request lama saat pilih area lain).
3. Komponen baru di components/map/: 
   - ZoneBadge (Zona Subur Tinggi/Sedang/Rendah, warna dari token existing/ turunan dari palet agronomyHelper)
   - ConfidenceMeter (bar + kategori + tooltip rincian komponen; tampilkan juga teks, bukan hanya warna)
   - AiRecommendationCard: ranking 3 tanaman, faktor pembatas utama, saran perbaikan lahan, badge
     "Perlu review pakar" bila needs_expert_review, disclaimer indikatif, loading skeleton & error state.
   - Bagian "Kenapa rekomendasi ini?" (accordion, pola FaqAccordion) yang menjelaskan zona + faktor pembatas dalam Bahasa Indonesia sederhana.
4. DataPanel.tsx: SISIPKAN <AiRecommendationCard/> tepat setelah <CropSuitabilityList/> dan sebelum
   <AdvisoriesSection/>. Tidak ada perubahan lain pada DataPanel.
5. Peta: tambah opsi filter 'Zona' ke MapFilterType + MapControls + MapLegend + useMapState
   (getPolygonStyle cabang baru; cabang lama tidak disentuh). Data zona dari /hara/zones, di-cache.
6. Expert (role expert/admin saja): di dalam AiRecommendationCard tampilkan aksi "Validasi" / "Koreksi zona" + catatan,
   dan di ExpertDashboardPage tambahkan tab/section "Antrean Review" (pola komponen yang sama dengan halaman existing).
7. SavedRecordsPage: tampilkan ZoneBadge kecil pada kartu lahan tersimpan (opsional, tidak mengubah layout kartu).
8. Mobile first: bottom sheet DataPanel tetap 70vh; hasil rekomendasi harus terjangkau ≤3 tap dari peta
   (pilih lahan -> panel terbuka -> rekomendasi tampak tanpa buka halaman lain).
9. Aksesibilitas: kontras AA, label ARIA, jangan andalkan warna saja.

Lakukan perubahan sekecil mungkin pada file existing; tunjukkan diff file existing yang disentuh
dan konfirmasi `npm run build` + `npm run lint` lolos. Sertakan screenshot sebelum/sesudah (Playwright) untuk
DataPanel dan peta — layar yang tidak berhubungan harus identik.
```

### FASE 5 — Evaluasi, QA, bahan laporan
```
Konteks: AGENTS.md. Buat backend/scripts/evaluate_model.py + docs/eval/REPORT.md berisi, dengan jujur:
- Metrik cluster: silhouette, Davies-Bouldin, stabilitas antar seed (10 seed, ARI).
- Precision/recall/F1: bandingkan zona hasil K-Means dengan label acuan. Jelaskan SECARA EKSPLISIT
  bahwa label acuan = turunan rules engine (dikoreksi pakar bila ada di tabel override), jadi angkanya
  = tingkat kesesuaian dengan acuan, bukan akurasi lapangan. Laporkan per kelas + confusion matrix.
  Jangan memoles angka agar mencapai target; kalau di bawah target (P≥90%, R≥85%) tulis apa adanya + saran perbaikan.
- Uji waktu: p50/p95 endpoint analysis dan render GeoJSON (target 1,5 dtk & 3 dtk).
- Daftar keterbatasan: data relatif bukan lab, bias spasial (Bogor saja), tanpa cuaca/histori panen, dosis belum tervalidasi.
- Checklist uji SUS & interpretability (kuesioner siap pakai, 10 item SUS + 3 item interpretability skala 1–5).
Pastikan seluruh pytest, ruff, build, lint hijau dan tulis ringkasan regresi: "yang tidak berubah".
```

## D. Prompt perbaikan cepat (pakai kalau hasil melenceng)
- Tampilan berubah: `Kamu mengubah tampilan existing. Revert perubahan pada <file> dan ulangi dengan menyisipkan komponen baru saja. Tunjukkan git diff untuk file itu sebelum lanjut.`
- AI mengarang angka: `Hapus semua angka dosis/ambang yang tidak bersumber dari repo atau dokumen yang gue kasih. Ganti dengan None + TODO(expert) dan teks kualitatif.`
- Terlalu banyak sekaligus: `Stop. Kerjakan hanya <butir X>. Jangan menyentuh file lain.`
- Sebelum merge tiap fase: `Review diff fase ini terhadap aturan keras AGENTS.md satu per satu, laporkan pelanggaran (kalau ada) lalu perbaiki.`

## E. Tips praktik
1. Commit per fase di tiap submodule (backend/frontend) lalu update pointer di repo induk.
2. Jalankan test sendiri sebelum percaya laporan AI ("test hijau" harus lu lihat).
3. Fase 1 dan 2 paling menentukan nilai; luangkan waktu review formula confidence dan label zona bareng pakar/dosen.
4. Satu sesi AI per fase (konteks bersih); `AGENTS.md` yang membawa memori antar sesi.
