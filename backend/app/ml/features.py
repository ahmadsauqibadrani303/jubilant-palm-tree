"""
Feature extraction and preprocessing for soil fertility clustering.
"""

from typing import Any

import numpy as np
from sklearn.preprocessing import StandardScaler

NO_DATA_THRESHOLD = -9000
NO_DATA_NAMES = {"water", "no data"}
FEATURE_NAMES = ["ph_rata2", "n_rata2", "p_rata2", "k_rata2"]
TRANSFORMED_FEATURE_NAMES = ["ph_rata2", "n_rata2", "p_rata2", "k_rata2_log1p"]


def extract_record_values(record: Any) -> tuple[int | None, str, float | None, float | None, float | None, float | None]:
    """
    Extract id, name, ph, n, p, k from a dict, GeoJSON feature, or ORM object.
    """
    if isinstance(record, dict):
        props = record.get("properties", record)
        area_id = props.get("id") or props.get("OBJECTID") or record.get("id")
        name = str(props.get("name") or props.get("NAME") or "").strip()
        ph = props.get("ph_rata2") if "ph_rata2" in props else props.get("pH_rata2")
        n = props.get("n_rata2") if "n_rata2" in props else props.get("N_rata2")
        p = props.get("p_rata2") if "p_rata2" in props else props.get("P_rata2")
        k = props.get("k_rata2") if "k_rata2" in props else props.get("K_rata2")
    else:
        # Object / ORM / Pydantic
        props = getattr(record, "properties", record)
        area_id = getattr(props, "id", None) or getattr(record, "id", None)
        name = str(getattr(props, "name", "") or "").strip()
        ph = getattr(props, "ph_rata2", None)
        n = getattr(props, "n_rata2", None)
        p = getattr(props, "p_rata2", None)
        k = getattr(props, "k_rata2", None)

    # Convert to float if Decimal or other numeric type
    def _to_float(v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    return (
        int(area_id) if area_id is not None else None,
        name,
        _to_float(ph),
        _to_float(n),
        _to_float(p),
        _to_float(k),
    )


def check_no_data(
    name: str,
    ph: float | None,
    n: float | None,
    p: float | None,
    k: float | None,
) -> tuple[bool, list[str]]:
    """
    Check if a record is no-data and return reasons if so.
    """
    reasons: list[str] = []
    norm_name = name.strip().lower()
    if norm_name in NO_DATA_NAMES:
        reasons.append(f"Name '{name}' matches excluded no-data categories")

    metrics = [("pH", ph), ("N", n), ("P", p), ("K", k)]
    for m_name, val in metrics:
        if val is None:
            reasons.append(f"{m_name} is missing (None)")
        elif val <= NO_DATA_THRESHOLD:
            reasons.append(f"{m_name} contains sentinel value ({val})")

    return (len(reasons) > 0, reasons)


def extract_features(
    records: list[Any],
) -> tuple[np.ndarray, list[int], list[dict[str, Any]], np.ndarray]:
    """
    Extract features from records, discarding no-data.
    Applies np.log1p on K.
    
    Returns:
        X: np.ndarray of shape (N, 4) with [pH, N, P, log1p(K)]
        area_ids: list of int area IDs corresponding to rows in X
        excluded_areas: list of dicts with area_id, name, and reason
        raw_values: np.ndarray of shape (N, 4) with original [pH, N, P, K]
    """
    x_rows = []
    raw_rows = []
    area_ids = []
    excluded_areas = []

    for rec in records:
        area_id, name, ph, n, p, k = extract_record_values(rec)
        is_bad, reasons = check_no_data(name, ph, n, p, k)

        if is_bad:
            excluded_areas.append(
                {
                    "area_id": area_id,
                    "name": name,
                    "reason": "; ".join(reasons),
                }
            )
        else:
            assert ph is not None and n is not None and p is not None and k is not None
            # Log1p on Kalium (K) to handle extreme positive skewness
            k_log = float(np.log1p(max(0.0, k)))
            x_rows.append([ph, n, p, k_log])
            raw_rows.append([ph, n, p, k])
            if area_id is not None:
                area_ids.append(area_id)

    X = np.array(x_rows, dtype=np.float64)
    raw_X = np.array(raw_rows, dtype=np.float64)
    return X, area_ids, excluded_areas, raw_X


def fit_scaler(X: np.ndarray) -> StandardScaler:
    """
    Fit and return a StandardScaler on pre-transformed features [pH, N, P, log1p(K)].
    """
    scaler = StandardScaler()
    scaler.fit(X)
    return scaler


def transform_single_sample(
    scaler: StandardScaler,
    ph: float,
    n: float,
    p: float,
    k: float,
) -> np.ndarray:
    """
    Transform a single [pH, N, P, K] observation into standard scaled space.
    Returns array of shape (1, 4).
    """
    k_log = float(np.log1p(max(0.0, k)))
    raw_row = np.array([[ph, n, p, k_log]], dtype=np.float64)
    return scaler.transform(raw_row)


def inverse_transform_centroids(
    scaler: StandardScaler,
    centroids_scaled: np.ndarray,
) -> np.ndarray:
    """
    Inverse transform centroids from scaled space back to original physical scale.
    Reverses StandardScaler and applies np.expm1 to Kalium.
    
    Returns array of shape (K, 4) with [pH, N, P, K].
    """
    unscaled = scaler.inverse_transform(centroids_scaled)
    # unscaled columns: [ph, n, p, log1p_k]
    orig = np.copy(unscaled)
    orig[:, 3] = np.expm1(orig[:, 3])
    return orig
