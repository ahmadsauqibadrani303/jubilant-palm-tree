"""
Pydantic schemas for SAFRONS AI Soil Fertility & Land Recommendation (FASE 2 & 3).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

ConfidenceCategory = Literal["tinggi", "sedang", "rendah"]
AnalysisStatus = Literal["ready", "insufficient_data"]
FactorSeverity = Literal["info", "watch", "attention", "critical"]
ReviewDecision = Literal["validated", "overridden"]


class ZoneInfo(BaseModel):
    zone_key: str
    zone_label: str
    cluster_id: int
    dist_to_centroid: float | None = None
    dist_to_second: float | None = None
    is_overridden: bool = False
    override_note: str | None = None


class LimitingFactorDetail(BaseModel):
    parameter: str
    label: str
    value: float | str | None = None
    status: str
    status_label: str
    severity: FactorSeverity
    explanation: str


class CropRankingItem(BaseModel):
    crop: str
    crop_label: str
    suitability_class: str = Field(alias="class")
    limiting_factors: list[str]
    reason: str
    not_recommended: bool
    ph_class: str
    n_class: str
    p_class: str
    k_class: str

    model_config = {"populate_by_name": True}


class AmendmentAdvice(BaseModel):
    parameter: str
    action_type: str
    title: str
    recommendation: str
    input_category: str
    dosage: str | None = None
    dosage_note: str
    reason: str


class ConfidenceBreakdown(BaseModel):
    cluster_margin: float
    data_completeness: float
    rule_zone_agreement: float
    boundary_proximity_penalty: float
    weights: dict[str, float]


class ConfidenceInfo(BaseModel):
    score: float
    category: ConfidenceCategory
    breakdown: ConfidenceBreakdown


class AnalysisMeta(BaseModel):
    model_version: str
    rule_set_version: str
    generated_at: str
    disclaimer: str


class AnalysisReviewCreate(BaseModel):
    decision: ReviewDecision
    zone_key: str | None = None
    note: str | None = None


class AnalysisReviewRead(BaseModel):
    id: int
    area_id: int
    expert_id: int
    expert_name: str | None = None
    decision: str
    zone_key: str | None = None
    note: str | None = None
    created_at: str


class AiAnalysisRead(BaseModel):
    area_id: int
    status: AnalysisStatus
    summary: str
    needs_expert_review: bool
    zone: ZoneInfo | None = None
    limiting_factors: list[LimitingFactorDetail] = []
    crop_ranking: list[CropRankingItem] = []
    amendments: list[AmendmentAdvice] = []
    confidence: ConfidenceInfo | None = None
    latest_review: AnalysisReviewRead | None = None
    meta: AnalysisMeta


class ZoneSummaryItem(BaseModel):
    area_id: int
    zone_key: str
    zone_label: str
    confidence_category: str


class ModelInfoRead(BaseModel):
    model_version: str
    algorithm: str
    k: int
    trained_at: str
    features: list[str]
    metrics: dict[str, float]
    clusters: list[dict[str, Any]]
    total_areas: int
    valid_areas: int


class ReviewQueueItem(BaseModel):
    area_id: int
    name: str
    zone_key: str
    zone_label: str
    confidence_score: float | None = None
    confidence_category: str
    reasons: list[str]
    latest_review: AnalysisReviewRead | None = None
