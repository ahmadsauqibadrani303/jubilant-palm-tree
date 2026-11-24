"""
Unit tests for SAFRONS soil fertility K-Means clustering pipeline (FASE 1).
Runs entirely offline without requiring a live PostgreSQL instance.
"""

import json
import os

import joblib
import numpy as np
import pytest

from app.ml.clustering import (
    calculate_distances_to_centroids,
    compute_cluster_fertility_mapping,
    fit_kmeans,
)
from app.ml.features import (
    extract_features,
    fit_scaler,
    inverse_transform_centroids,
)


@pytest.fixture
def small_synthetic_records():
    """
    Synthetic dataset with 5 valid areas (ranging in fertility) and 2 no-data areas.
    """
    return [
        {
            "id": 1,
            "name": "Area Subur",
            "ph_rata2": 6.2,
            "n_rata2": 8.0,
            "p_rata2": 35.0,
            "k_rata2": 450.0,
        },
        {
            "id": 2,
            "name": "Area Sedang",
            "ph_rata2": 5.6,
            "n_rata2": 3.5,
            "p_rata2": 12.0,
            "k_rata2": 250.0,
        },
        {
            "id": 3,
            "name": "Area Rendah",
            "ph_rata2": 4.8,
            "n_rata2": 1.8,
            "p_rata2": 6.5,
            "k_rata2": 110.0,
        },
        {
            "id": 4,
            "name": "Area Sedang 2",
            "ph_rata2": 5.4,
            "n_rata2": 3.2,
            "p_rata2": 10.5,
            "k_rata2": 220.0,
        },
        {
            "id": 5,
            "name": "Area Rendah 2",
            "ph_rata2": 4.6,
            "n_rata2": 2.0,
            "p_rata2": 5.9,
            "k_rata2": 95.0,
        },
        # No-data cases:
        {
            "id": 6,
            "name": "Water",
            "ph_rata2": -9999.0,
            "n_rata2": -9999.0,
            "p_rata2": -9999.0,
            "k_rata2": -9999.0,
        },
        {
            "id": 7,
            "name": "Unknown swamp",
            "ph_rata2": None,
            "n_rata2": 2.5,
            "p_rata2": 10.0,
            "k_rata2": 150.0,
        },
    ]


def test_extract_features_discards_no_data(small_synthetic_records):
    """Verify that records with sentinel values or missing metrics are properly excluded with reasons."""
    X, valid_ids, excluded_areas, raw_X = extract_features(small_synthetic_records)

    assert len(valid_ids) == 5
    assert valid_ids == [1, 2, 3, 4, 5]
    assert len(excluded_areas) == 2

    exc_ids = [e["area_id"] for e in excluded_areas]
    assert 6 in exc_ids
    assert 7 in exc_ids

    # Check reason strings
    exc_6 = next(e for e in excluded_areas if e["area_id"] == 6)
    assert "sentinel" in exc_6["reason"] or "Water" in exc_6["reason"]

    exc_7 = next(e for e in excluded_areas if e["area_id"] == 7)
    assert "missing" in exc_7["reason"]

    # Verify log1p applied to Kalium (4th column)
    assert np.isclose(X[0, 3], np.log1p(450.0))
    assert np.isclose(raw_X[0, 3], 450.0)


def test_clustering_deterministic_and_label_order():
    """Verify that KMeans training is deterministic and clusters are ordered strictly by fertility index."""
    # Create synthetic points in 3 clear clusters
    np.random.seed(42)
    c_low = np.random.normal(loc=[-1.5, -1.5, -1.5, -1.5], scale=0.2, size=(20, 4))
    c_med = np.random.normal(loc=[0.0, 0.0, 0.0, 0.0], scale=0.2, size=(20, 4))
    c_high = np.random.normal(loc=[1.5, 1.5, 1.5, 1.5], scale=0.2, size=(20, 4))
    X_synthetic = np.vstack([c_low, c_med, c_high])

    # Run 1
    m1 = fit_kmeans(X_synthetic, n_clusters=3, random_state=42)
    map1 = compute_cluster_fertility_mapping(m1.cluster_centers_, n_clusters=3)

    # Run 2
    m2 = fit_kmeans(X_synthetic, n_clusters=3, random_state=42)
    map2 = compute_cluster_fertility_mapping(m2.cluster_centers_, n_clusters=3)

    # Check deterministic labels and mappings
    assert np.array_equal(m1.labels_, m2.labels_)
    assert np.allclose(m1.cluster_centers_, m2.cluster_centers_)
    assert map1 == map2

    # Verify mapping order: rank 0 must have higher fertility index than rank 1, and rank 1 > rank 2
    rank0_info = next(info for info in map1.values() if info["rank"] == 0)
    rank1_info = next(info for info in map1.values() if info["rank"] == 1)
    rank2_info = next(info for info in map1.values() if info["rank"] == 2)

    assert rank0_info["zone_key"] == "high"
    assert rank0_info["zone_label"] == "Zona Subur Tinggi"
    assert rank1_info["zone_key"] == "medium"
    assert rank1_info["zone_label"] == "Zona Subur Sedang"
    assert rank2_info["zone_key"] == "low"
    assert rank2_info["zone_label"] == "Zona Subur Rendah"

    assert rank0_info["fertility_index"] > rank1_info["fertility_index"] > rank2_info["fertility_index"]


def test_distance_calculation_and_margin():
    """Verify that dist_to_centroid <= dist_to_second."""
    X = np.array([
        [1.0, 1.0, 1.0, 1.0],
        [-1.0, -1.0, -1.0, -1.0],
    ])
    centroids = np.array([
        [1.1, 1.1, 1.1, 1.1],
        [0.0, 0.0, 0.0, 0.0],
        [-1.1, -1.1, -1.1, -1.1],
    ])

    closest, d1, d2 = calculate_distances_to_centroids(X, centroids)
    assert closest[0] == 0  # Closer to first centroid
    assert closest[1] == 2  # Closer to third centroid
    assert np.all(d1 <= d2)


def test_inverse_transform_reverses_log1p_k():
    """Verify that inverse_transform_centroids restores original scale for all features including Kalium."""
    raw_data = np.array([
        [5.0, 3.0, 10.0, np.log1p(200.0)],
        [6.0, 6.0, 25.0, np.log1p(400.0)],
        [4.5, 2.0, 8.0, np.log1p(100.0)],
    ])
    scaler = fit_scaler(raw_data)
    scaled_data = scaler.transform(raw_data)

    restored = inverse_transform_centroids(scaler, scaled_data)
    assert np.isclose(restored[0, 0], 5.0)
    assert np.isclose(restored[0, 1], 3.0)
    assert np.isclose(restored[0, 2], 10.0)
    assert np.isclose(restored[0, 3], 200.0)


def test_artifacts_and_assignments_consistency():
    """Verify trained artifacts exist, load properly, and cover all 191 areas."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    artifacts_dir = os.path.join(base_dir, "app", "ml", "artifacts")

    meta_path = os.path.join(artifacts_dir, "metadata.json")
    assign_path = os.path.join(artifacts_dir, "zone_assignments.json")
    scaler_path = os.path.join(artifacts_dir, "scaler.joblib")
    model_path = os.path.join(artifacts_dir, "kmeans_k3.joblib")

    assert os.path.exists(meta_path)
    assert os.path.exists(assign_path)
    assert os.path.exists(scaler_path)
    assert os.path.exists(model_path)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    with open(assign_path, "r", encoding="utf-8") as f:
        assignments = json.load(f)

    # Exactly 191 areas
    assert len(assignments) == 191
    assert meta["dataset"]["total_areas"] == 191
    assert meta["dataset"]["valid_areas"] == 188
    assert meta["dataset"]["excluded_count"] == 3

    # Check that each area has exactly one valid zone_key
    valid_keys = {"high", "medium", "low", "unknown"}
    for info in assignments.values():
        assert info["zone_key"] in valid_keys
        if info["zone_key"] == "unknown":
            assert info["cluster_id"] == -1
        else:
            assert info["cluster_id"] in {0, 1, 2}
            assert info["dist_to_centroid"] is not None
            assert info["dist_to_second"] is not None
            assert info["dist_to_centroid"] <= info["dist_to_second"]

    # Verify scaler and model load cleanly with joblib
    scaler = joblib.load(scaler_path)
    model = joblib.load(model_path)
    assert scaler.n_features_in_ == 4
    assert model.n_clusters == 3
