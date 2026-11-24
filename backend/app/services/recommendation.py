"""
Recommendation and AI Analysis Service for SAFRONS (FASE 2).
Combines K-Means soil fertility zoning and Liebig Law of the Minimum rule-based evaluation.
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.zone_cluster import AnalysisReview, HaraZoneCluster, HaraZoneLabelOverride
from app.schemas.analysis import (
    AiAnalysisRead,
    AmendmentAdvice,
    AnalysisMeta,
    AnalysisReviewRead,
    ConfidenceBreakdown,
    ConfidenceInfo,
    CropRankingItem,
    LimitingFactorDetail,
    ZoneInfo,
)
from app.schemas.hara import HaraFeature
from app.services.fertilizer_rules import get_amendment_for_factor
from app.services.hara_diagnosis import (
    CROP_CRITERIA,
    RULE_SET_VERSION,
    build_hara_diagnosis,
    get_crop_suitability,
    has_insufficient_data,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = "kmeans-v1.0.0"
DISCLAIMER_TEXT = "Rekomendasi indikatif berdasarkan data hara relatif; konfirmasi dengan uji tanah"

# Confidence weight constants (transparent breakdown)
WEIGHT_CLUSTER_MARGIN = 0.35
WEIGHT_DATA_COMPLETENESS = 0.35
WEIGHT_RULE_ZONE_AGREEMENT = 0.30

SEVERITY_ORDER = {
    "critical": 1,
    "attention": 2,
    "watch": 3,
    "info": 4,
}

CLASS_RANK = {
    "S1": 1,
    "S2": 2,
    "S3": 3,
    "N": 4,
}

CROP_LABELS = {
    "jagung": "Jagung",
    "kacang_tanah": "Kacang Tanah",
    "kakao": "Kakao",
}

# Cache for fallback file assignments
_CACHED_ASSIGNMENTS: dict[int, dict[str, Any]] | None = None


def get_cached_zone_assignment(area_id: int) -> dict[str, Any] | None:
    """
    Fallback reader from zone_assignments.json artifact when DB record is not available.
    """
    global _CACHED_ASSIGNMENTS
    if _CACHED_ASSIGNMENTS is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        assign_path = os.path.join(base_dir, "ml", "artifacts", "zone_assignments.json")
        if os.path.exists(assign_path):
            with open(assign_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                _CACHED_ASSIGNMENTS = {int(k): v for k, v in raw.items()}
        else:
            _CACHED_ASSIGNMENTS = {}
    return _CACHED_ASSIGNMENTS.get(area_id)


def get_latest_analysis_review(area_id: int, db: Session | None = None) -> AnalysisReviewRead | None:
    """
    Fetch the latest expert validation or override review for an area.
    """
    if db is None:
        return None
    try:
        review = db.scalar(
            select(AnalysisReview)
            .where(AnalysisReview.area_id == area_id)
            .order_by(AnalysisReview.created_at.desc())
        )
        if review is not None:
            expert_name = review.expert.full_name if review.expert else None
            return AnalysisReviewRead(
                id=review.id,
                area_id=review.area_id,
                expert_id=review.expert_id,
                expert_name=expert_name,
                decision=review.decision,
                zone_key=review.zone_key,
                note=review.note,
                created_at=review.created_at.isoformat(),
            )
    except SQLAlchemyError as err:
        logger.debug("Could not query analysis_review: %s", err)
    return None


def resolve_zone_info(area_id: int, db: Session | None = None) -> ZoneInfo:
    """
    Resolve zone classification for an area.
    Expert manual override takes precedence over algorithmic cluster.
    """
    # 1. Check for expert override in DB
    if db is not None:
        try:
            override = db.scalar(
                select(HaraZoneLabelOverride)
                .where(HaraZoneLabelOverride.area_id == area_id)
                .order_by(HaraZoneLabelOverride.created_at.desc())
            )
            if override is not None:
                labels = {
                    "high": "Zona Subur Tinggi",
                    "medium": "Zona Subur Sedang",
                    "low": "Zona Subur Rendah",
                    "unknown": "Tidak Diketahui / Data Kurang",
                }
                return ZoneInfo(
                    zone_key=override.zone_key,
                    zone_label=labels.get(override.zone_key, override.zone_key.title()),
                    cluster_id=-2,  # Mark as manually overridden
                    is_overridden=True,
                    override_note=override.note,
                )
        except SQLAlchemyError as err:
            logger.debug("Could not query hara_zone_label_override: %s", err)

    # 2. Check hara_zone_cluster table in DB
    if db is not None:
        try:
            cluster_row = db.get(HaraZoneCluster, area_id)
            if cluster_row is not None:
                return ZoneInfo(
                    zone_key=cluster_row.zone_key,
                    zone_label=cluster_row.zone_label,
                    cluster_id=cluster_row.cluster_id,
                    dist_to_centroid=cluster_row.dist_to_centroid,
                    dist_to_second=cluster_row.dist_to_second,
                    is_overridden=False,
                )
        except SQLAlchemyError as err:
            logger.debug("Could not query hara_zone_cluster: %s", err)

    # 3. Fallback to cached artifact
    assign = get_cached_zone_assignment(area_id)
    if assign is not None:
        return ZoneInfo(
            zone_key=assign["zone_key"],
            zone_label=assign["zone_label"],
            cluster_id=assign["cluster_id"],
            dist_to_centroid=assign.get("dist_to_centroid"),
            dist_to_second=assign.get("dist_to_second"),
            is_overridden=False,
        )

    # 4. Default unknown
    return ZoneInfo(
        zone_key="unknown",
        zone_label="Tidak Diketahui / Data Kurang",
        cluster_id=-1,
        is_overridden=False,
    )


def build_limiting_factor_details(diagnosis_factors: list[Any]) -> list[LimitingFactorDetail]:
    """
    Extract and sort global soil limiting factors based on diagnosis severity.
    """
    constraints: list[LimitingFactorDetail] = []

    explanations = {
        "ph": {
            "very_acid": "Tingkat keasaman sangat tinggi (pH < 4.5); membatasi ketersediaan P dan meningkatkan risiko toksisitas Al.",
            "acid": "Reaksi tanah masam (pH 4.5 - 5.5); membatasi ketersediaan hara optimal.",
            "slightly_acid": "Tanah sedikit masam; perlu dipantau agar tidak berlanjut ke masam.",
            "slightly_alkaline": "Reaksi tanah sedikit alkalis; perlu dipantau terhadap ketersediaan hara mikro.",
            "alkaline": "Reaksi tanah alkalis; dapat menurunkan kelarutan fosfat dan hara mikro.",
        },
        "n_rata2": {
            "very_low": "Kadar Nitrogen sangat rendah di bawah pita acuan relatif; membatasi pertumbuhan daun dan vegetatif.",
            "low": "Kadar Nitrogen rendah; perlu penambahan pupuk N terukur.",
            "high": "Kadar Nitrogen di atas rata-rata; kurangi pupuk N untuk mencegah pemborosan.",
            "very_high": "Kadar Nitrogen sangat tinggi; waspadai sukulensi berlebih tanaman.",
        },
        "p_rata2": {
            "very_low": "Kadar Fosfor sangat rendah; sangat membatasi perkembangan akar dan pembungaan.",
            "low": "Kadar Fosfor rendah; memerlukan pasokan pupuk fosfat dasar.",
            "high": "Kadar Fosfor tinggi; pertahankan pada tingkat pemeliharaan.",
            "very_high": "Kadar Fosfor sangat tinggi; hindari penambahan pupuk P berlebih.",
        },
        "k_rata2": {
            "very_low": "Kadar Kalium sangat rendah; menurunkan ketahanan terhadap kekeringan dan hama.",
            "low": "Kadar Kalium rendah; perlu aplikasi pupuk KCl/kalium.",
            "high": "Kadar Kalium tinggi; pantau keseimbangan kation Ca/Mg.",
            "very_high": "Kadar Kalium sangat tinggi; kurangi input kalium anorganik.",
        },
        "slope": {
            "steep": "Kemiringan lereng curam (16-40%); risiko erosi dan pencucian hara tinggi.",
            "very_steep": "Kemiringan lereng sangat curam (>40%); konservasi tanah mutlak diperlukan.",
            "moderate": "Kemiringan lereng agak miring (9-15%); memerlukan penanganan limpasan rutin.",
        },
    }

    indonesian_labels = {
        "ph": "Reaksi Tanah (pH)",
        "n_rata2": "Nitrogen (N)",
        "p_rata2": "Fosfor (P)",
        "k_rata2": "Kalium (K)",
        "slope": "Kemiringan Lereng",
    }

    for factor in diagnosis_factors:
        key = getattr(factor, "key", None)
        status = getattr(factor, "status", None)
        severity = getattr(factor, "severity", "info")
        value = getattr(factor, "value", None)

        # Consider non-info or constrained factors
        if severity in {"critical", "attention", "watch"}:
            expl = explanations.get(key, {}).get(status)
            if not expl:
                expl = f"Kondisi {key} dengan status {status} berpotensi membatasi produktivitas tanaman."

            constraints.append(
                LimitingFactorDetail(
                    parameter=key,
                    label=indonesian_labels.get(key, factor.label),
                    value=value,
                    status=status,
                    status_label=getattr(factor, "status_label", status),
                    severity=severity,
                    explanation=expl,
                )
            )

    # Sort by severity rank (critical first, then attention, then watch)
    constraints.sort(key=lambda x: SEVERITY_ORDER.get(x.severity, 99))
    return constraints


def rank_crop_suitabilities(crop_suitabilities: list[Any]) -> list[CropRankingItem]:
    """
    Rank 3 crops by:
      1. Suitability class (S1 > S2 > S3 > N)
      2. Fewer limiting factors
      3. More S1 individual parameter parameters
    """
    ranked_items: list[CropRankingItem] = []

    for item in crop_suitabilities:
        crop = item.crop
        s_class = item.suitability_class
        lim_factors = item.limiting_factors

        # 1-sentence Indonesian reasoning
        crop_label = CROP_LABELS.get(crop, crop.title())
        if s_class == "S1":
            reason = f"{crop_label} sangat sesuai (S1) tanpa faktor pembatas utama pada lahan ini."
        elif s_class == "S2":
            lim_str = ", ".join(lim_factors)
            reason = f"{crop_label} cukup sesuai (S2) dengan pembatas ringan pada {lim_str}."
        elif s_class == "S3":
            lim_str = ", ".join(lim_factors)
            reason = f"{crop_label} sesuai marginal (S3), dibatasi secara signifikan oleh {lim_str}."
        else:
            lim_str = ", ".join(lim_factors) if lim_factors else "keterbatasan biofisik tanah"
            reason = f"{crop_label} tidak direkomendasikan (N) karena kendala berat pada {lim_str}."

        ranked_items.append(
            CropRankingItem(
                crop=crop,
                crop_label=crop_label,
                suitability_class=s_class,
                limiting_factors=lim_factors,
                reason=reason,
                not_recommended=(s_class == "N"),
                ph_class=item.ph_class,
                n_class=item.n_class,
                p_class=item.p_class,
                k_class=item.k_class,
            )
        )

    # Sort:
    # 1. CLASS_RANK (1=S1, 2=S2, 3=S3, 4=N) ascending
    # 2. len(limiting_factors) ascending (fewer is better)
    # 3. count of S1 descending (more is better -> negative)
    def _rank_key(c: CropRankingItem) -> tuple[int, int, int]:
        c_rank = CLASS_RANK.get(c.suitability_class, 5)
        num_lim = len(c.limiting_factors)
        s1_cnt = sum(
            1 for p in [c.ph_class, c.n_class, c.p_class, c.k_class] if p == "S1"
        )
        return (c_rank, num_lim, -s1_cnt)

    ranked_items.sort(key=_rank_key)
    return ranked_items


def build_amendment_advices(
    diagnosis_factors: list[Any],
) -> list[AmendmentAdvice]:
    """
    Generate amendment and fertilizer advisory per limiting factor.
    """
    advices: list[AmendmentAdvice] = []
    seen_params = set()

    for factor in diagnosis_factors:
        key = getattr(factor, "key", None)
        status = getattr(factor, "status", None)
        severity = getattr(factor, "severity", "info")

        if key in seen_params:
            continue

        rule = get_amendment_for_factor(key, status, severity)
        if rule is not None:
            seen_params.add(key)
            advices.append(
                AmendmentAdvice(
                    parameter=rule["parameter"],
                    action_type=rule["action_type"],
                    title=rule["title"],
                    recommendation=rule["recommendation"],
                    input_category=rule["input_category"],
                    dosage=rule.get("dosage"),
                    dosage_note=rule["dosage_note"],
                    reason=rule["reason"],
                )
            )

    return advices


def check_boundary_proximity(area: HaraFeature) -> float:
    """
    Check if any parameter is within 5% of class boundaries defined in CROP_CRITERIA.
    Returns penalty deduction between 0.0 and 0.15.
    """
    props = area.properties
    vals = {
        "ph": props.ph_rata2,
        "n": props.n_rata2,
        "p": props.p_rata2,
        "k": props.k_rata2,
    }

    penalties = 0.0
    for criteria_set in CROP_CRITERIA.values():
        for param, bounds in criteria_set.items():
            val = vals.get(param)
            if val is None or val <= -9000:
                continue
            # bounds: (s1_min, s1_max, s2_min, s2_max, s3_min, s3_max)
            for threshold in bounds:
                if threshold is not None and threshold > 0:
                    rel_dist = abs(val - threshold) / threshold
                    if rel_dist < 0.05:  # Within 5%
                        penalties += 0.03

    return min(0.15, round(penalties, 4))


def calculate_confidence(
    zone_info: ZoneInfo,
    crop_rankings: list[CropRankingItem],
    area: HaraFeature,
) -> ConfidenceInfo:
    """
    Compute transparent confidence score with breakdown.
    """
    # 1. Cluster margin = 1 - d1 / (d1 + d2)
    d1 = zone_info.dist_to_centroid
    d2 = zone_info.dist_to_second
    if d1 is not None and d2 is not None and (d1 + d2) > 0:
        cluster_margin = float(1.0 - (d1 / (d1 + d2)))
    else:
        # Fallback if unknown or manual override
        cluster_margin = 0.50 if not zone_info.is_overridden else 0.85

    # 2. Data completeness
    completeness = 1.0  # Already checked before this call

    # 3. Rule-zone agreement
    # Check consistency between cluster zone and crop suitability ranking
    top_class = crop_rankings[0].suitability_class if crop_rankings else "N"
    z_key = zone_info.zone_key

    if z_key == "high":
        if top_class in {"S1", "S2"}:
            rule_zone_agreement = 1.0
        elif top_class == "S3":
            rule_zone_agreement = 0.70
        else:
            rule_zone_agreement = 0.35  # Inconsistent: high fertility zone but crop is N
    elif z_key == "medium":
        if top_class in {"S1", "S2", "S3"}:
            rule_zone_agreement = 1.0
        else:
            rule_zone_agreement = 0.60
    elif z_key == "low":
        if top_class in {"S3", "N"}:
            rule_zone_agreement = 1.0
        elif top_class == "S2":
            rule_zone_agreement = 0.80
        else:
            rule_zone_agreement = 0.50
    else:
        rule_zone_agreement = 0.50

    # 4. Boundary proximity penalty
    penalty = check_boundary_proximity(area)

    # Weighted score
    raw_score = (
        (WEIGHT_CLUSTER_MARGIN * cluster_margin)
        + (WEIGHT_DATA_COMPLETENESS * completeness)
        + (WEIGHT_RULE_ZONE_AGREEMENT * rule_zone_agreement)
        - penalty
    )
    score = round(max(0.0, min(1.0, raw_score)), 4)

    # Category determination
    if score >= 0.75:
        category = "tinggi"
    elif score >= 0.50:
        category = "sedang"
    else:
        category = "rendah"

    breakdown = ConfidenceBreakdown(
        cluster_margin=round(cluster_margin, 4),
        data_completeness=round(completeness, 4),
        rule_zone_agreement=round(rule_zone_agreement, 4),
        boundary_proximity_penalty=round(penalty, 4),
        weights={
            "cluster_margin": WEIGHT_CLUSTER_MARGIN,
            "data_completeness": WEIGHT_DATA_COMPLETENESS,
            "rule_zone_agreement": WEIGHT_RULE_ZONE_AGREEMENT,
        },
    )

    return ConfidenceInfo(score=score, category=category, breakdown=breakdown)


def build_ai_analysis(
    area: HaraFeature,
    db: Session | None = None,
) -> AiAnalysisRead:
    """
    Main entry point for AI Soil Fertility Analysis & Recommendation.
    Combines rule-based Liebig evaluation and K-Means fertility clustering.
    """
    area_id = int(area.properties.id)
    generated_at = datetime.now(UTC).isoformat()

    latest_review = get_latest_analysis_review(area_id, db=db)

    # 1. Handle no-data / insufficient data
    if has_insufficient_data(area):
        return AiAnalysisRead(
            area_id=area_id,
            status="insufficient_data",
            summary="Analisis tidak dapat dilakukan karena data hara pada poligon ini tidak lengkap atau tidak valid.",
            needs_expert_review=True,
            zone=resolve_zone_info(area_id, db=db),
            limiting_factors=[],
            crop_ranking=[],
            amendments=[],
            confidence=None,
            latest_review=latest_review,
            meta=AnalysisMeta(
                model_version=MODEL_VERSION,
                rule_set_version=RULE_SET_VERSION,
                generated_at=generated_at,
                disclaimer=DISCLAIMER_TEXT,
            ),
        )

    # 2. Call existing services (NO duplicate logic)
    diagnosis = build_hara_diagnosis(area, db=db)
    crop_suitabilities = get_crop_suitability(area, db=db)

    # 3. Resolve Zone
    zone_info = resolve_zone_info(area_id, db=db)

    # 4. Limiting Factors (global lahan)
    limiting_factors = build_limiting_factor_details(diagnosis.factors)

    # 5. Crop Ranking
    crop_ranking = rank_crop_suitabilities(crop_suitabilities)

    # 6. Amendment Advices
    amendments = build_amendment_advices(diagnosis.factors)

    # 7. Confidence Calculation
    confidence = calculate_confidence(zone_info, crop_ranking, area)

    # 8. Check needs_expert_review condition:
    # True if confidence is 'rendah' OR top crop is not S1/S2 OR any factor has severity 'critical'
    top_class = crop_ranking[0].suitability_class if crop_ranking else "N"
    has_critical_factor = any(f.severity == "critical" for f in diagnosis.factors)
    needs_review = (
        (confidence.category == "rendah")
        or (top_class not in {"S1", "S2"})
        or has_critical_factor
    )

    # 9. Summary in clear Indonesian
    top_crop = crop_ranking[0] if crop_ranking else None
    if top_crop and top_crop.suitability_class in {"S1", "S2"}:
        summary = (
            f"Lahan berada di {zone_info.zone_label}. Komoditas yang paling direkomendasikan adalah "
            f"{top_crop.crop_label} (kelas {top_crop.suitability_class})."
        )
    elif top_crop:
        summary = (
            f"Lahan berada di {zone_info.zone_label}. Rekomendasi tanaman terbatas "
            f"({top_crop.crop_label} berstatus {top_crop.suitability_class}) "
            f"karena adanya faktor pembatas utama."
        )
    else:
        summary = f"Lahan berada di {zone_info.zone_label}."

    return AiAnalysisRead(
        area_id=area_id,
        status="ready",
        summary=summary,
        needs_expert_review=needs_review,
        zone=zone_info,
        limiting_factors=limiting_factors,
        crop_ranking=crop_ranking,
        amendments=amendments,
        confidence=confidence,
        latest_review=latest_review,
        meta=AnalysisMeta(
            model_version=MODEL_VERSION,
            rule_set_version=RULE_SET_VERSION,
            generated_at=generated_at,
            disclaimer=DISCLAIMER_TEXT,
        ),
    )
