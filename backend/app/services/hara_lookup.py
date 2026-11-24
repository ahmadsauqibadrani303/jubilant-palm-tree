import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.hara import HaraArea
from app.schemas.hara import HaraFeature, HaraProperties, HaraFeatureCollection

_GEOJSON_COLLECTION: HaraFeatureCollection | None = None
_GEOJSON_MAP: dict[int, HaraFeature] = {}


def get_geojson_hara_collection() -> HaraFeatureCollection:
    global _GEOJSON_COLLECTION, _GEOJSON_MAP
    if _GEOJSON_COLLECTION is not None:
        return _GEOJSON_COLLECTION

    base_dir = Path(__file__).resolve().parent.parent.parent
    geojson_path = base_dir / "reference" / "data-hara-bogor" / "hara-bogor.geojson"
    if not geojson_path.exists():
        return HaraFeatureCollection(features=[])

    with open(geojson_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    features = []
    _GEOJSON_MAP = {}
    for feat in raw.get("features", []):
        props = feat.get("properties", {})
        obj_id = props.get("OBJECTID") or props.get("id")
        name = props.get("NAME") or props.get("name")
        ph = props.get("pH_rata2") if "pH_rata2" in props else props.get("ph_rata2")
        n = props.get("N_rata2") if "N_rata2" in props else props.get("n_rata2")
        p = props.get("P_rata2") if "P_rata2" in props else props.get("p_rata2")
        k = props.get("K_rata2") if "K_rata2" in props else props.get("k_rata2")
        slope = props.get("SLOPE__") or props.get("slope__")
        texture = props.get("TEXTURE_OF") or props.get("texture_of")

        hf = HaraFeature(
            geometry=feat.get("geometry"),
            properties=HaraProperties(
                id=int(obj_id),
                name=str(name) if name else None,
                ph_rata2=float(ph) if ph is not None and float(ph) >= 0 else None,
                n_rata2=float(n) if n is not None and float(n) >= 0 else None,
                p_rata2=float(p) if p is not None and float(p) >= 0 else None,
                k_rata2=float(k) if k is not None and float(k) >= 0 else None,
                slope__=str(slope) if slope else None,
                texture_of=str(texture) if texture else None,
            ),
        )
        features.append(hf)
        _GEOJSON_MAP[int(obj_id)] = hf

    _GEOJSON_COLLECTION = HaraFeatureCollection(features=features)
    return _GEOJSON_COLLECTION


def get_geojson_feature_by_id(area_id: int) -> HaraFeature | None:
    if not _GEOJSON_MAP:
        get_geojson_hara_collection()
    return _GEOJSON_MAP.get(area_id)

HARA_COLUMNS = """
    id,
    name,
    ph_rata2,
    n_rata2,
    p_rata2,
    k_rata2,
    slope__,
    texture_of,
    ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.0001))::json AS geometry
"""


def row_to_feature(row: Any) -> HaraFeature:
    geometry = row["geometry"]
    if isinstance(geometry, str):
        geometry = json.loads(geometry)

    properties = {
        "id": row["id"],
        "name": row["name"],
        "ph_rata2": numeric_to_float(row["ph_rata2"]),
        "n_rata2": numeric_to_float(row["n_rata2"]),
        "p_rata2": numeric_to_float(row["p_rata2"]),
        "k_rata2": numeric_to_float(row["k_rata2"]),
        "slope__": row["slope__"],
        "texture_of": row["texture_of"],
    }
    return HaraFeature(geometry=geometry, properties=properties)


def numeric_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def hara_area_to_feature(area: HaraArea) -> HaraFeature:
    row = {
        "id": area.id,
        "name": area.name,
        "ph_rata2": area.ph_rata2,
        "n_rata2": area.n_rata2,
        "p_rata2": area.p_rata2,
        "k_rata2": area.k_rata2,
        "slope__": area.slope__,
        "texture_of": area.texture_of,
        "geometry": None,
    }
    return row_to_feature(row)


def get_hara_feature_by_id(db: Session, area_id: int) -> HaraFeature | None:
    if db.get_bind().dialect.name == "sqlite":
        feat = get_geojson_feature_by_id(area_id)
        if feat is not None:
            return feat
        area = db.get(HaraArea, area_id)
        return hara_area_to_feature(area) if area is not None else None

    row = db.execute(
        text(
            f"""
            SELECT {HARA_COLUMNS}
            FROM hara_bogor
            WHERE id = :area_id
            """
        ),
        {"area_id": area_id},
    ).mappings().first()

    return row_to_feature(row) if row is not None else None


def require_hara_feature(db: Session, area_id: int) -> HaraFeature:
    area = get_hara_feature_by_id(db, area_id)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hara area not found")
    return area


def find_hara_feature_by_point(db: Session, lon: float, lat: float) -> HaraFeature | None:
    if db.get_bind().dialect.name == "sqlite":
        count = db.scalar(select(func.count()).select_from(HaraArea))
        if not count or count == 0:
            return None
        if count == 1:
            area = db.scalar(select(HaraArea).order_by(HaraArea.id).limit(1))
            return hara_area_to_feature(area) if area is not None else None

        try:
            from shapely.geometry import Point, shape
            pt = Point(lon, lat)
            collection = get_geojson_hara_collection()
            best_feat = None
            min_dist = float("inf")
            for feat in collection.features:
                if feat.geometry:
                    try:
                        s_geom = shape(feat.geometry.model_dump() if hasattr(feat.geometry, "model_dump") else feat.geometry)
                        if s_geom.contains(pt) or s_geom.intersects(pt):
                            return feat
                        dist = s_geom.distance(pt)
                        if dist < min_dist:
                            min_dist = dist
                            best_feat = feat
                    except Exception:
                        continue
            if best_feat and min_dist < 0.1:
                return best_feat
        except ImportError:
            pass

        area = db.scalar(select(HaraArea).order_by(HaraArea.id).limit(1))
        return hara_area_to_feature(area) if area is not None else None

    row = db.execute(
        text(
            f"""
            SELECT {HARA_COLUMNS}
            FROM hara_bogor
            WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ORDER BY id
            LIMIT 1
            """
        ),
        {"lon": lon, "lat": lat},
    ).mappings().first()

    return row_to_feature(row) if row is not None else None


def hara_area_exists(db: Session, area_id: int) -> bool:
    if db.get_bind().dialect.name == "sqlite":
        return db.get(HaraArea, area_id) is not None

    exists = db.scalar(text("SELECT 1 FROM hara_bogor WHERE id = :area_id"), {"area_id": area_id})
    return exists is not None


def get_hara_features_by_ids(
    db: Session, area_ids: list[int], include_geometry: bool = True
) -> dict[int, HaraFeature]:
    if not area_ids:
        return {}

    if db.get_bind().dialect.name == "sqlite":
        areas = db.scalars(select(HaraArea).where(HaraArea.id.in_(area_ids))).all()
        features = {}
        for area in areas:
            feat = get_geojson_feature_by_id(area.id)
            if feat is None:
                feat = hara_area_to_feature(area)
            if not include_geometry:
                feat = feat.model_copy(update={"geometry": None})
            features[area.id] = feat
        return features

    cols = HARA_COLUMNS if include_geometry else """
        id,
        name,
        ph_rata2,
        n_rata2,
        p_rata2,
        k_rata2,
        slope__,
        texture_of,
        NULL AS geometry
    """

    rows = db.execute(
        text(
            f"""
            SELECT {cols}
            FROM hara_bogor
            WHERE id = ANY(:area_ids)
            """
        ),
        {"area_ids": area_ids},
    ).mappings().all()

    return {row["id"]: row_to_feature(row) for row in rows}


