"""
Evaluation script for SAFRONS AI Soil Fertility & Recommendation Engine (FASE 5).

Measures:
1. Clustering quality: Silhouette score, Davies-Bouldin index.
2. Stability across seeds: Adjusted Rand Index (ARI) over 10 random seeds.
3. Classification metrics: Precision, Recall, F1 against rule-based reference labels + confusion matrix.
4. Response time benchmark: p50 and p95 latency for area analysis.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    adjusted_rand_score,
    confusion_matrix,
    davies_bouldin_score,
    precision_recall_fscore_support,
    silhouette_score,
)

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.session import SessionLocal
from app.ml.clustering import (
    compute_cluster_fertility_mapping,
    fit_kmeans,
)
from app.ml.features import (
    extract_features,
    extract_record_values,
    fit_scaler,
)
from app.schemas.hara import HaraFeature, HaraProperties
from app.services.hara_diagnosis import build_hara_diagnosis, get_crop_suitability
from app.services.recommendation import build_ai_analysis

GEOJSON_PATH = os.path.join(
    BACKEND_DIR, "reference", "data-hara-bogor", "hara-bogor.geojson"
)


def load_geojson_data(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"GeoJSON file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def to_hara_feature(record: Any) -> HaraFeature:
    area_id, name, ph, n, p, k = extract_record_values(record)
    return HaraFeature(
        geometry=None,
        properties=HaraProperties(
            id=area_id if area_id is not None else -1,
            name=name,
            ph_rata2=ph,
            n_rata2=n,
            p_rata2=p,
            k_rata2=k,
            slope__=None,
            texture_of=None,
        ),
    )


def get_rule_based_reference_label(record: Any) -> str:
    """
    Derive an objective agronomic reference label based on Liebig rule
    and average nutrient status.
    """
    feature = to_hara_feature(record)
    props = feature.properties
    ph = props.ph_rata2
    n = props.n_rata2
    p = props.p_rata2
    k = props.k_rata2
    if any(val is None or val < 0 for val in (ph, n, p, k)):
        return "unknown"

    diagnosis = build_hara_diagnosis(feature)
    limiting = [f for f in diagnosis.factors if f.severity in ("critical", "attention")]

    suitabilities = get_crop_suitability(feature)
    s1_count = sum(1 for s in suitabilities if s.suitability_class == "S1")
    s2_count = sum(1 for s in suitabilities if s.suitability_class == "S2")
    n_count = sum(1 for s in suitabilities if s.suitability_class == "N")

    # High: Setidaknya ada komoditas S1/S2 dan tidak ada pembatas berat
    # Low: Ada komoditas N atau pembatas berat >= 2
    # Medium: Sisanya
    if (s1_count >= 1 or s2_count >= 2) and len(limiting) <= 1:
        return "high"
    elif n_count >= 2 or len(limiting) >= 2:
        return "low"
    else:
        return "medium"


def run_evaluation() -> dict[str, Any]:
    raw_features = load_geojson_data(GEOJSON_PATH)
    total_count = len(raw_features)

    # 1. Extract Features
    X, valid_ids, excluded_areas, _ = extract_features(raw_features)
    valid_count = len(valid_ids)

    scaler = fit_scaler(X)
    X_scaled = scaler.transform(X)

    print(f"Total features: {total_count}, Valid features: {valid_count}, Excluded (no-data): {len(excluded_areas)}")

    # 2. Clustering Quality (k=3, seed=42)
    km_k3 = fit_kmeans(X_scaled, n_clusters=3, random_state=42, n_init=20)
    cluster_labels = km_k3.labels_

    sil = float(silhouette_score(X_scaled, cluster_labels))
    db_score = float(davies_bouldin_score(X_scaled, cluster_labels))
    print(f"\n[1] Clustering Metrics (k=3):")
    print(f"    Silhouette Score: {sil:.4f}")
    print(f"    Davies-Bouldin Index: {db_score:.4f}")

    # 3. Stability across 10 seeds (ARI)
    ari_scores = []
    for seed in range(1, 11):
        km_seed = fit_kmeans(X_scaled, n_clusters=3, random_state=seed, n_init=20)
        ari = float(adjusted_rand_score(cluster_labels, km_seed.labels_))
        ari_scores.append(ari)

    mean_ari = float(np.mean(ari_scores))
    min_ari = float(np.min(ari_scores))
    print(f"\n[2] Clustering Stability (10 Random Seeds):")
    print(f"    Mean Adjusted Rand Index (ARI): {mean_ari:.4f}")
    print(f"    Min ARI: {min_ari:.4f}")

    # 4. Map Clusters to Zone Keys
    mapping_k3 = compute_cluster_fertility_mapping(km_k3.cluster_centers_, n_clusters=3)
    pred_zones = [mapping_k3[c_id]["zone_key"] for c_id in cluster_labels]

    # Map raw features to dict by id for lookup
    feature_by_id = {}
    for feat in raw_features:
        f_id, _, _, _, _, _ = extract_record_values(feat)
        if f_id is not None:
            feature_by_id[f_id] = feat

    ref_zones = []
    for area_id in valid_ids:
        feat = feature_by_id.get(area_id, {})
        ref_zones.append(get_rule_based_reference_label(feat))

    # 5. Classification Metrics (against rule-based reference)
    target_names = ["low", "medium", "high"]
    prec, rec, f1, support = precision_recall_fscore_support(
        ref_zones, pred_zones, labels=target_names, zero_division=0
    )
    conf_mat = confusion_matrix(ref_zones, pred_zones, labels=target_names)

    print(f"\n[3] Classification against Agronomic Rule Reference:")
    class_metrics = {}
    for i, name in enumerate(target_names):
        class_metrics[name] = {
            "precision": float(prec[i]),
            "recall": float(rec[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        print(f"    Class '{name:6s}' -> Precision: {prec[i]:.4f}, Recall: {rec[i]:.4f}, F1: {f1[i]:.4f}, Support: {support[i]}")

    macro_f1 = float(np.mean(f1))
    macro_precision = float(np.mean(prec))
    macro_recall = float(np.mean(rec))
    print(f"    Macro Average   -> Precision: {macro_precision:.4f}, Recall: {macro_recall:.4f}, F1: {macro_f1:.4f}")
    print(f"\n    Confusion Matrix (Rows: Ref [low, med, high], Cols: Pred [low, med, high]):")
    print(f"    {conf_mat[0]}")
    print(f"    {conf_mat[1]}")
    print(f"    {conf_mat[2]}")

    # 6. Response Time Latency Benchmark
    print(f"\n[4] Latency Benchmark (100 runs):")
    db = SessionLocal()
    sample_feat = feature_by_id[valid_ids[0]]
    sample_feature_obj = to_hara_feature(sample_feat)

    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        _ = build_ai_analysis(sample_feature_obj, db=db)
        latencies.append((time.perf_counter() - t0) * 1000)

    db.close()

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    print(f"    Analysis Latency: p50 = {p50:.2f} ms, p95 = {p95:.2f} ms (Target: <= 1500 ms)")

    results = {
        "dataset": {
            "total_areas": total_count,
            "valid_areas": valid_count,
            "excluded_no_data": len(excluded_areas),
        },
        "clustering_metrics": {
            "silhouette_score": round(sil, 4),
            "davies_bouldin_index": round(db_score, 4),
            "stability_10_seeds": {
                "mean_ari": round(mean_ari, 4),
                "min_ari": round(min_ari, 4),
                "individual_ari": [round(s, 4) for s in ari_scores],
            },
        },
        "classification_metrics": {
            "classes": class_metrics,
            "macro_average": {
                "precision": round(macro_precision, 4),
                "recall": round(macro_recall, 4),
                "f1": round(macro_f1, 4),
            },
            "confusion_matrix": conf_mat.tolist(),
        },
        "latency_benchmark_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "runs": len(latencies),
            "target_ms": 1500,
        },
    }

    out_file = Path(BACKEND_DIR) / "app" / "ml" / "artifacts" / "evaluation_metrics.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nEvaluation metrics successfully written to {out_file}")
    return results


if __name__ == "__main__":
    run_evaluation()
