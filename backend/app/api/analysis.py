"""
API Endpoints for SAFRONS AI Soil Fertility Analysis & Recommendations (FASE 3).
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_expert
from app.db.session import get_db
from app.models.user import User
from app.models.zone_cluster import (
    AnalysisReview,
    HaraZoneCluster,
    HaraZoneLabelOverride,
    ensure_zone_cluster_tables,
)
from app.schemas.analysis import (
    AiAnalysisRead,
    AnalysisReviewCreate,
    ModelInfoRead,
    ReviewQueueItem,
    ZoneSummaryItem,
)
from app.services.hara_lookup import (
    HARA_COLUMNS,
    find_hara_feature_by_point,
    require_hara_feature,
    row_to_feature,
)
from app.services.recommendation import (
    build_ai_analysis,
)

router = APIRouter(tags=["analysis"])
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "artifacts"
)


@router.get("/api/v1/hara/areas/{area_id}/analysis", response_model=AiAnalysisRead)
def get_area_ai_analysis(
    area_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> AiAnalysisRead:
    """
    Get comprehensive AI soil fertility analysis and land suitability recommendation for an area.
    Target latency: <= 1.5 seconds.
    """
    ensure_zone_cluster_tables(db)
    feature = require_hara_feature(db, area_id)
    return build_ai_analysis(feature, db=db)


@router.get("/api/v1/hara/point/analysis", response_model=AiAnalysisRead)
def get_point_ai_analysis(
    db: Annotated[Session, Depends(get_db)],
    lon: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
) -> AiAnalysisRead:
    """
    Get AI analysis for the area containing a given coordinate point.
    """
    ensure_zone_cluster_tables(db)
    feature = find_hara_feature_by_point(db, lon, lat)
    if feature is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hara area found at the provided coordinates",
        )
    return build_ai_analysis(feature, db=db)


@router.get("/api/v1/hara/zones", response_model=list[ZoneSummaryItem])
def list_hara_zones(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> list[ZoneSummaryItem]:
    """
    Lightweight list of all area fertility zones for fast map overlay rendering.
    Cached on client with Cache-Control header.
    """
    ensure_zone_cluster_tables(db)
    response.headers["Cache-Control"] = "public, max-age=86400"

    items: list[ZoneSummaryItem] = []

    # 1. Try reading from hara_zone_cluster table
    try:
        rows = db.execute(
            select(
                HaraZoneCluster.area_id,
                HaraZoneCluster.zone_key,
                HaraZoneCluster.zone_label,
            ).order_by(HaraZoneCluster.area_id)
        ).all()

        if rows:
            # Check for overrides
            overrides = {
                ov.area_id: ov.zone_key
                for ov in db.scalars(select(HaraZoneLabelOverride)).all()
            }
            labels = {
                "high": "Zona Subur Tinggi",
                "medium": "Zona Subur Sedang",
                "low": "Zona Subur Rendah",
                "unknown": "Tidak Diketahui / Data Kurang",
            }
            for row in rows:
                z_key = overrides.get(row.area_id, row.zone_key)
                z_label = labels.get(z_key, row.zone_label)
                conf_cat = "tinggi" if z_key in {"high", "medium"} else ("rendah" if z_key == "unknown" else "sedang")
                items.append(
                    ZoneSummaryItem(
                        area_id=row.area_id,
                        zone_key=z_key,
                        zone_label=z_label,
                        confidence_category=conf_cat,
                    )
                )
            return items
    except SQLAlchemyError as err:
        logger.debug("Could not query hara_zone_cluster: %s", err)

    # 2. Fallback to cached artifact
    assign_path = os.path.join(ARTIFACTS_DIR, "zone_assignments.json")
    if os.path.exists(assign_path):
        with open(assign_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in sorted(raw.items(), key=lambda x: int(x[0])):
            z_key = v["zone_key"]
            conf_cat = "tinggi" if z_key in {"high", "medium"} else ("rendah" if z_key == "unknown" else "sedang")
            items.append(
                ZoneSummaryItem(
                    area_id=int(k),
                    zone_key=z_key,
                    zone_label=v["zone_label"],
                    confidence_category=conf_cat,
                )
            )
        return items

    return items


@router.get("/api/v1/ml/model-info", response_model=ModelInfoRead)
def get_ml_model_info() -> ModelInfoRead:
    """
    Get public metadata, metrics, and version information for the active K-Means clustering model.
    """
    meta_path = os.path.join(ARTIFACTS_DIR, "metadata.json")
    if not os.path.exists(meta_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model metadata artifact not found",
        )

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    return ModelInfoRead(
        model_version=meta.get("model_version", "kmeans-v1.0.0"),
        algorithm=meta.get("algorithm", "KMeans"),
        k=meta.get("k", 3),
        trained_at=meta.get("trained_at", ""),
        features=meta.get("features", []),
        metrics=meta.get("metrics", {}),
        clusters=meta.get("clusters", []),
        total_areas=meta.get("dataset", {}).get("total_areas", 191),
        valid_areas=meta.get("dataset", {}).get("valid_areas", 188),
    )


@router.post(
    "/api/v1/expert/areas/{area_id}/analysis-review",
    response_model=AiAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_review(
    area_id: int,
    body: AnalysisReviewCreate,
    current_user: Annotated[User, Depends(require_expert)],
    db: Annotated[Session, Depends(get_db)],
) -> AiAnalysisRead:
    """
    Expert validation or zone override review.
    Accessible strictly to users with role 'expert' or 'admin'.
    """
    ensure_zone_cluster_tables(db)
    feature = require_hara_feature(db, area_id)

    # 1. Record the review in analysis_review table
    review = AnalysisReview(
        area_id=area_id,
        expert_id=current_user.id,
        decision=body.decision,
        zone_key=body.zone_key,
        note=body.note,
        created_at=datetime.now(UTC),
    )
    db.add(review)

    # 2. If decision is overridden and zone_key is provided, record zone override
    if body.decision == "overridden" and body.zone_key:
        override = HaraZoneLabelOverride(
            area_id=area_id,
            zone_key=body.zone_key,
            expert_id=current_user.id,
            note=body.note,
            created_at=datetime.now(UTC),
        )
        db.add(override)

    db.commit()

    # 3. Return fresh AI analysis reflecting the new review/override state
    return build_ai_analysis(feature, db=db)


@router.get(
    "/api/v1/expert/analysis-review/queue",
    response_model=list[ReviewQueueItem],
)
def get_analysis_review_queue(
    current_user: Annotated[User, Depends(require_expert)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ReviewQueueItem]:
    """
    List areas with needs_expert_review == True that require agronomist validation.
    Areas without prior validation appear at the top of the queue.
    """
    ensure_zone_cluster_tables(db)

    # Load all areas from database
    if db.get_bind().dialect.name == "sqlite":
        from app.models.hara import HaraArea
        areas = [row_to_feature(
            {
                "id": a.id,
                "name": a.name,
                "ph_rata2": a.ph_rata2,
                "n_rata2": a.n_rata2,
                "p_rata2": a.p_rata2,
                "k_rata2": a.k_rata2,
                "slope__": a.slope__,
                "texture_of": a.texture_of,
                "geometry": None,
            }
        ) for a in db.scalars(select(HaraArea).order_by(HaraArea.id)).all()]
    else:
        rows = db.execute(
            text(
                f"""
                SELECT {HARA_COLUMNS}
                FROM hara_bogor
                ORDER BY id
                """
            )
        ).mappings().all()
        areas = [row_to_feature(r) for r in rows]

    queue: list[ReviewQueueItem] = []

    for area in areas:
        area_id = int(area.properties.id)
        name = area.properties.name or f"Area {area_id}"

        # Evaluate analysis
        analysis = build_ai_analysis(area, db=db)

        if analysis.needs_expert_review:
            reasons = []
            if analysis.status == "insufficient_data":
                reasons.append("Data hara tidak lengkap / bernilai sentinel")
            if analysis.confidence and analysis.confidence.category == "rendah":
                reasons.append(f"Skor keyakinan rendah ({analysis.confidence.score:.2f})")
            top_crop = analysis.crop_ranking[0] if analysis.crop_ranking else None
            if top_crop and top_crop.suitability_class not in {"S1", "S2"}:
                reasons.append(f"Tidak ada komoditas sesuai optimal (tertinggi {top_crop.suitability_class})")
            for f in analysis.limiting_factors:
                if f.severity == "critical":
                    reasons.append(f"Faktor kritis pada {f.label}")

            z_key = analysis.zone.zone_key if analysis.zone else "unknown"
            z_label = analysis.zone.zone_label if analysis.zone else "Tidak Diketahui"
            conf_score = analysis.confidence.score if analysis.confidence else None
            conf_cat = analysis.confidence.category if analysis.confidence else "rendah"

            queue.append(
                ReviewQueueItem(
                    area_id=area_id,
                    name=name,
                    zone_key=z_key,
                    zone_label=z_label,
                    confidence_score=conf_score,
                    confidence_category=conf_cat,
                    reasons=reasons,
                    latest_review=analysis.latest_review,
                )
            )

    # Sort queue: unreviewed first (latest_review is None), then by area_id
    queue.sort(key=lambda item: (0 if item.latest_review is None else 1, item.area_id))
    return queue
