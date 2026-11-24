"""
K-Means clustering and soil fertility zone classification.
"""

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score

ZONE_DEFINITIONS_K3 = [
    {"rank": 0, "zone_key": "high", "zone_label": "Zona Subur Tinggi"},
    {"rank": 1, "zone_key": "medium", "zone_label": "Zona Subur Sedang"},
    {"rank": 2, "zone_key": "low", "zone_label": "Zona Subur Rendah"},
]

ZONE_DEFINITIONS_K4 = [
    {"rank": 0, "zone_key": "very_high", "zone_label": "Zona Sangat Subur"},
    {"rank": 1, "zone_key": "high", "zone_label": "Zona Subur"},
    {"rank": 2, "zone_key": "medium", "zone_label": "Zona Cukup Subur"},
    {"rank": 3, "zone_key": "low", "zone_label": "Zona Kurang Subur"},
]

UNKNOWN_ZONE = {
    "zone_key": "unknown",
    "zone_label": "Tidak Diketahui / Data Kurang",
}


def fit_kmeans(
    X_scaled: np.ndarray,
    n_clusters: int = 3,
    random_state: int = 42,
    n_init: int = 20,
) -> KMeans:
    """
    Train a deterministic KMeans model on scaled features.
    """
    kmeans = KMeans(
        n_clusters=n_clusters,
        n_init=n_init,
        random_state=random_state,
    )
    kmeans.fit(X_scaled)
    return kmeans


def evaluate_clustering(
    X_scaled: np.ndarray,
    labels: np.ndarray,
) -> dict[str, float]:
    """
    Calculate Silhouette and Davies-Bouldin metrics.
    """
    if len(np.unique(labels)) < 2:
        return {"silhouette": 0.0, "davies_bouldin": 0.0}

    sil = float(silhouette_score(X_scaled, labels))
    db = float(davies_bouldin_score(X_scaled, labels))
    return {
        "silhouette": round(sil, 4),
        "davies_bouldin": round(db, 4),
    }


def compute_cluster_fertility_mapping(
    centroids_scaled: np.ndarray,
    n_clusters: int = 3,
) -> dict[int, dict[str, Any]]:
    """
    Order clusters by the fertility index of their centroids in standardized space.
    Fertility index = average of z-scores [pH, N, P, log1p(K)].
    
    Returns mapping:
        cluster_id -> {
            "rank": int (0 is highest fertility),
            "fertility_index": float,
            "zone_key": str,
            "zone_label": str
        }
    """
    # Average z-score across all 4 standardized nutrients
    fertility_indices = np.mean(centroids_scaled, axis=1)
    
    # Sort cluster IDs by descending fertility index
    sorted_cluster_ids = np.argsort(-fertility_indices)

    zone_defs = ZONE_DEFINITIONS_K3 if n_clusters == 3 else ZONE_DEFINITIONS_K4

    mapping: dict[int, dict[str, Any]] = {}
    for rank, cluster_id in enumerate(sorted_cluster_ids):
        z_def = zone_defs[rank] if rank < len(zone_defs) else {
            "zone_key": f"cluster_{rank}",
            "zone_label": f"Zona {rank}",
        }
        mapping[int(cluster_id)] = {
            "rank": rank,
            "fertility_index": float(fertility_indices[cluster_id]),
            "zone_key": z_def["zone_key"],
            "zone_label": z_def["zone_label"],
        }

    return mapping


def calculate_distances_to_centroids(
    X_scaled: np.ndarray,
    centroids_scaled: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute for each sample:
      - closest cluster_id
      - distance to closest centroid (dist_to_centroid)
      - distance to second closest centroid (dist_to_second)
    """
    # Distances matrix: (N, K)
    # ||x - c||_2
    diff = X_scaled[:, np.newaxis, :] - centroids_scaled[np.newaxis, :, :]
    distances = np.linalg.norm(diff, axis=2)

    closest_clusters = np.argmin(distances, axis=1)
    
    # Sort distances along axis 1 to find d1 and d2
    sorted_dists = np.sort(distances, axis=1)
    dist_to_centroid = sorted_dists[:, 0]
    dist_to_second = sorted_dists[:, 1] if centroids_scaled.shape[0] > 1 else sorted_dists[:, 0]

    return closest_clusters, dist_to_centroid, dist_to_second


def compare_k3_vs_k4(
    X_scaled: np.ndarray,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Run clustering for both K=3 and K=4 and return comparative metrics.
    """
    results = {}
    for k in [3, 4]:
        model = fit_kmeans(X_scaled, n_clusters=k, random_state=random_state)
        eval_metrics = evaluate_clustering(X_scaled, model.labels_)
        counts = {int(c): int(np.sum(model.labels_ == c)) for c in range(k)}
        results[f"k_{k}"] = {
            "k": k,
            "silhouette": eval_metrics["silhouette"],
            "davies_bouldin": eval_metrics["davies_bouldin"],
            "inertia": round(float(model.inertia_), 4),
            "cluster_counts": counts,
        }
    return results
