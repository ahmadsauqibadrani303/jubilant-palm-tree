#!/usr/bin/env python3
"""
Offline training script for SAFRONS soil fertility K-Means clustering.
Saves model artifacts and metadata to backend/app/ml/artifacts/.
Optionally populates the database hara_zone_cluster table.
"""

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

import joblib

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.ml.clustering import (
    UNKNOWN_ZONE,
    calculate_distances_to_centroids,
    compare_k3_vs_k4,
    compute_cluster_fertility_mapping,
    evaluate_clustering,
    fit_kmeans,
)
from app.ml.features import (
    extract_features,
    fit_scaler,
    inverse_transform_centroids,
)

MODEL_VERSION = "kmeans-v1.0.0"
ARTIFACTS_DIR = os.path.join(BACKEND_DIR, "app", "ml", "artifacts")
GEOJSON_PATH = os.path.join(
    BACKEND_DIR, "reference", "data-hara-bogor", "hara-bogor.geojson"
)


def load_geojson_data(path: str) -> list[dict[str, Any]]:
    """Load features from reference GeoJSON."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"GeoJSON file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def train_and_export(
    geojson_path: str = GEOJSON_PATH,
    artifacts_dir: str = ARTIFACTS_DIR,
    sync_to_db: bool = False,
) -> dict[str, Any]:
    """
    Train K-Means clustering model offline and export artifacts.
    """
    os.makedirs(artifacts_dir, exist_ok=True)
    trained_at = datetime.now(UTC).isoformat()

    # 1. Load GeoJSON features
    raw_features = load_geojson_data(geojson_path)
    total_count = len(raw_features)

    # 2. Extract features and discard no-data
    X, valid_ids, excluded_areas, _raw_X = extract_features(raw_features)
    valid_count = len(valid_ids)

    # 3. Fit scaler
    scaler = fit_scaler(X)
    X_scaled = scaler.transform(X)

    # 4. Train K=3 model (primary)
    kmeans_k3 = fit_kmeans(X_scaled, n_clusters=3, random_state=42, n_init=20)
    eval_k3 = evaluate_clustering(X_scaled, kmeans_k3.labels_)

    # 5. Compare with K=4 for evaluation reporting
    comparison = compare_k3_vs_k4(X_scaled, random_state=42)

    # 6. Map clusters to soil fertility zones (ordered by fertility index)
    mapping_k3 = compute_cluster_fertility_mapping(
        kmeans_k3.cluster_centers_, n_clusters=3
    )

    # 7. Inverse transform centroids to original physical scale
    centroids_orig = inverse_transform_centroids(scaler, kmeans_k3.cluster_centers_)

    # 8. Compute distances for valid areas
    closest_clusters, dist1, dist2 = calculate_distances_to_centroids(
        X_scaled, kmeans_k3.cluster_centers_
    )

    # 9. Build assignments map for all 191 areas
    zone_assignments: dict[int, dict[str, Any]] = {}
    cluster_counts = {0: 0, 1: 0, 2: 0}

    for idx, area_id in enumerate(valid_ids):
        c_id = int(closest_clusters[idx])
        cluster_info = mapping_k3[c_id]
        cluster_counts[c_id] += 1
        zone_assignments[area_id] = {
            "area_id": area_id,
            "cluster_id": c_id,
            "zone_key": cluster_info["zone_key"],
            "zone_label": cluster_info["zone_label"],
            "dist_to_centroid": round(float(dist1[idx]), 6),
            "dist_to_second": round(float(dist2[idx]), 6),
            "model_version": MODEL_VERSION,
            "trained_at": trained_at,
        }

    # Add no-data areas
    for exc in excluded_areas:
        a_id = exc["area_id"]
        if a_id is not None:
            zone_assignments[a_id] = {
                "area_id": a_id,
                "cluster_id": -1,
                "zone_key": UNKNOWN_ZONE["zone_key"],
                "zone_label": UNKNOWN_ZONE["zone_label"],
                "dist_to_centroid": None,
                "dist_to_second": None,
                "model_version": MODEL_VERSION,
                "trained_at": trained_at,
            }

    # 10. Format cluster summary
    cluster_summary = []
    # Sort zones by rank (0 = High, 1 = Medium, 2 = Low)
    sorted_by_rank = sorted(mapping_k3.items(), key=lambda item: item[1]["rank"])

    for c_id, info in sorted_by_rank:
        cluster_summary.append(
            {
                "cluster_id": c_id,
                "rank": info["rank"],
                "zone_key": info["zone_key"],
                "zone_label": info["zone_label"],
                "fertility_index": round(info["fertility_index"], 4),
                "count": cluster_counts[c_id],
                "centroid_original": {
                    "ph": round(float(centroids_orig[c_id, 0]), 2),
                    "n": round(float(centroids_orig[c_id, 1]), 2),
                    "p": round(float(centroids_orig[c_id, 2]), 2),
                    "k": round(float(centroids_orig[c_id, 3]), 2),
                },
                "centroid_scaled": {
                    "ph": round(float(kmeans_k3.cluster_centers_[c_id, 0]), 4),
                    "n": round(float(kmeans_k3.cluster_centers_[c_id, 1]), 4),
                    "p": round(float(kmeans_k3.cluster_centers_[c_id, 2]), 4),
                    "k_log1p": round(float(kmeans_k3.cluster_centers_[c_id, 3]), 4),
                },
            }
        )

    # 11. Compile metadata.json
    metadata = {
        "model_version": MODEL_VERSION,
        "algorithm": "KMeans",
        "k": 3,
        "random_state": 42,
        "trained_at": trained_at,
        "features": ["ph_rata2", "n_rata2", "p_rata2", "k_rata2"],
        "transformations": {
            "k_rata2": "np.log1p",
            "scaling": "StandardScaler",
        },
        "dataset": {
            "source": os.path.basename(geojson_path),
            "total_areas": total_count,
            "valid_areas": valid_count,
            "excluded_count": len(excluded_areas),
            "excluded_areas": excluded_areas,
        },
        "metrics": {
            "silhouette": eval_k3["silhouette"],
            "davies_bouldin": eval_k3["davies_bouldin"],
            "inertia": round(float(kmeans_k3.inertia_), 4),
        },
        "k4_comparison": comparison,
        "clusters": cluster_summary,
        "assumptions": [
            "ASSUMPTION: K is log1p-transformed prior to StandardScaler due to extreme positive skewness (range 75 - 3139).",
            "ASSUMPTION: Slope and texture are excluded from clustering to represent intrinsic chemical soil fertility; they are applied during suitability evaluation.",
            "ASSUMPTION: Zone sorting is determined by centroid fertility index (average z-score across standardized pH, N, P, K).",
        ],
        "expert_todos": [
            "TODO(expert): Validate cluster centroid boundaries against regional agronomic benchmarks for Bogor.",
            "TODO(expert): Calibrate fertilizer dosages per zone once laboratory soil test data is integrated.",
        ],
    }

    # 12. Save artifacts
    joblib.dump(scaler, os.path.join(artifacts_dir, "scaler.joblib"))
    joblib.dump(kmeans_k3, os.path.join(artifacts_dir, "kmeans_k3.joblib"))
    joblib.dump(mapping_k3, os.path.join(artifacts_dir, "cluster_mapping.joblib"))

    with open(os.path.join(artifacts_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    with open(os.path.join(artifacts_dir, "zone_assignments.json"), "w", encoding="utf-8") as f:
        json.dump(zone_assignments, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("SAFRONS K-Means Clustering Training Complete")
    print(f"Model Version: {MODEL_VERSION}")
    print(f"Trained at   : {trained_at}")
    print(f"Total Areas  : {total_count} (Valid: {valid_count}, Excluded: {len(excluded_areas)})")
    print("=" * 70)
    print("\n[Evaluation Metrics K=3 vs K=4]")
    print(f"{'Metric':<20} {'K=3 (Selected)':<20} {'K=4 (Comparison)':<20}")
    print("-" * 60)
    print(f"{'Silhouette':<20} {eval_k3['silhouette']:<20} {comparison['k_4']['silhouette']:<20}")
    print(f"{'Davies-Bouldin':<20} {eval_k3['davies_bouldin']:<20} {comparison['k_4']['davies_bouldin']:<20}")
    print(f"{'Inertia':<20} {round(float(kmeans_k3.inertia_), 2):<20} {comparison['k_4']['inertia']:<20}")

    print("\n[Cluster Centroids & Distribution (Original Scale)]")
    print(f"{'Zone Label':<22} {'Count':<8} {'pH':<8} {'N':<8} {'P':<8} {'K (ppm)':<10} {'Fertility Index'}")
    print("-" * 75)
    for c in cluster_summary:
        cent = c["centroid_original"]
        print(
            f"{c['zone_label']:<22} {c['count']:<8} {cent['ph']:<8} {cent['n']:<8} "
            f"{cent['p']:<8} {cent['k']:<10} {c['fertility_index']:+.4f}"
        )

    print("\n[Excluded Areas (No-Data)]")
    for exc in excluded_areas:
        print(f"  - Area ID {exc['area_id']} ({exc['name']}): {exc['reason']}")

    # 13. Optionally sync to database
    if sync_to_db:
        sync_assignments_to_db(zone_assignments)

    return metadata


def sync_assignments_to_db(zone_assignments: dict[int, dict[str, Any]]) -> None:
    """
    Sync zone assignments into hara_zone_cluster table.
    """
    from app.db.session import SessionLocal
    from app.models.zone_cluster import HaraZoneCluster, ensure_zone_cluster_tables

    print("\n[Syncing zone assignments to database...]")
    with SessionLocal() as db:
        ensure_zone_cluster_tables(db)
        # Upsert or merge assignments
        for area_id, rec in zone_assignments.items():
            existing = db.get(HaraZoneCluster, area_id)
            if existing:
                existing.cluster_id = rec["cluster_id"]
                existing.zone_key = rec["zone_key"]
                existing.zone_label = rec["zone_label"]
                existing.dist_to_centroid = rec["dist_to_centroid"]
                existing.dist_to_second = rec["dist_to_second"]
                existing.model_version = rec["model_version"]
                existing.trained_at = datetime.fromisoformat(rec["trained_at"])
            else:
                db.add(
                    HaraZoneCluster(
                        area_id=area_id,
                        cluster_id=rec["cluster_id"],
                        zone_key=rec["zone_key"],
                        zone_label=rec["zone_label"],
                        dist_to_centroid=rec["dist_to_centroid"],
                        dist_to_second=rec["dist_to_second"],
                        model_version=rec["model_version"],
                        trained_at=datetime.fromisoformat(rec["trained_at"]),
                    )
                )
        db.commit()
        print(f"Successfully synced {len(zone_assignments)} zone records to database.")


if __name__ == "__main__":
    do_sync = "--sync-db" in sys.argv
    train_and_export(sync_to_db=do_sync)
