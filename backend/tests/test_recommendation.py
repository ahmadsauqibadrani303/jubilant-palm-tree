"""
Unit tests for SAFRONS recommendation engine and confidence scoring (FASE 2).
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.hara import HaraArea
from app.models.user import User
from app.models.zone_cluster import (
    HaraZoneCluster,
    HaraZoneLabelOverride,
    ensure_zone_cluster_tables,
)
from app.schemas.hara import HaraFeature
from app.services.hara_diagnosis import get_crop_suitability
from app.services.recommendation import (
    WEIGHT_CLUSTER_MARGIN,
    WEIGHT_DATA_COMPLETENESS,
    WEIGHT_RULE_ZONE_AGREEMENT,
    build_ai_analysis,
    rank_crop_suitabilities,
)


@pytest.fixture
def mock_feature_normal():
    return HaraFeature(
        geometry={"type": "Polygon", "coordinates": [[[106.8, -6.6], [106.9, -6.6], [106.9, -6.5], [106.8, -6.6]]]},
        properties={
            "id": 10,
            "name": "Sukamaju",
            "ph_rata2": 5.8,
            "n_rata2": 4.5,
            "p_rata2": 18.0,
            "k_rata2": 320.0,
            "slope__": "2-8",
            "texture_of": "Lempung",
        },
    )


@pytest.fixture
def mock_feature_critical_acid():
    return HaraFeature(
        geometry={"type": "Polygon", "coordinates": [[[106.8, -6.6], [106.9, -6.6], [106.9, -6.5], [106.8, -6.6]]]},
        properties={
            "id": 20,
            "name": "Tanah Sangat Masam",
            "ph_rata2": 4.2,  # Very acid -> critical
            "n_rata2": 1.5,   # Very low
            "p_rata2": 5.0,   # Very low
            "k_rata2": 60.0,  # Very low
            "slope__": ">60",  # Very steep -> critical
            "texture_of": "Liat",
        },
    )


@pytest.fixture
def mock_feature_no_data():
    return HaraFeature(
        geometry={"type": "Polygon", "coordinates": [[[106.8, -6.6], [106.9, -6.6], [106.9, -6.5], [106.8, -6.6]]]},
        properties={
            "id": 5,
            "name": "Water",
            "ph_rata2": -9999.0,
            "n_rata2": -9999.0,
            "p_rata2": -9999.0,
            "k_rata2": -9999.0,
            "slope__": "",
            "texture_of": "",
        },
    )


@pytest.fixture
def in_memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    ensure_zone_cluster_tables(session)
    yield session
    session.close()


def test_no_data_handling(mock_feature_no_data):
    """Verify that insufficient data areas return 'insufficient_data' status without guess."""
    result = build_ai_analysis(mock_feature_no_data)
    assert result.status == "insufficient_data"
    assert result.needs_expert_review is True
    assert result.confidence is None
    assert result.crop_ranking == []
    assert result.limiting_factors == []
    assert result.amendments == []
    assert "tidak lengkap" in result.summary.lower()


def test_crop_suitability_consistency(mock_feature_normal):
    """Verify that suitability classes in AI analysis strictly match get_crop_suitability."""
    raw_suitabilities = get_crop_suitability(mock_feature_normal)
    raw_map = {item.crop: item.suitability_class for item in raw_suitabilities}

    result = build_ai_analysis(mock_feature_normal)
    assert result.status == "ready"
    assert len(result.crop_ranking) == 3

    for item in result.crop_ranking:
        assert item.suitability_class == raw_map[item.crop]


def test_crop_ranking_tie_break():
    """Verify tie-break logic: S1 > S2 > S3 > N, then fewer limiting factors, then more S1 params."""
    from app.schemas.diagnosis import CropSuitability

    items = [
        CropSuitability(
            crop="tanaman_c",
            suitability_class="S2",
            limiting_factors=["n"],
            ph_class="S1",
            n_class="S2",
            p_class="S1",
            k_class="S1",
        ),
        CropSuitability(
            crop="tanaman_a",
            suitability_class="S1",
            limiting_factors=[],
            ph_class="S1",
            n_class="S1",
            p_class="S1",
            k_class="S1",
        ),
        CropSuitability(
            crop="tanaman_b",
            suitability_class="S2",
            limiting_factors=["n", "p"],
            ph_class="S1",
            n_class="S2",
            p_class="S2",
            k_class="S1",
        ),
    ]

    ranked = rank_crop_suitabilities(items)
    # S1 must be first
    assert ranked[0].crop == "tanaman_a"
    # S2 with 1 limiting factor must come before S2 with 2 limiting factors
    assert ranked[1].crop == "tanaman_c"
    assert ranked[2].crop == "tanaman_b"


def test_expert_override_wins(mock_feature_normal, in_memory_db):
    """Verify that an expert override takes precedence over algorithmic zone classification."""
    # Seed user and area
    user = User(
        id=1,
        email="expert@safrons.id",
        full_name="Pakar Agronomi",
        hashed_password="hash",
        role="expert",
    )
    in_memory_db.add(user)

    area_orm = HaraArea(
        id=10,
        name="Sukamaju",
        ph_rata2=Decimal("5.8"),
        n_rata2=Decimal("4.5"),
        p_rata2=Decimal("18.0"),
        k_rata2=Decimal("320.0"),
    )
    in_memory_db.add(area_orm)

    # Seed algorithmic cluster as 'high'
    in_memory_db.add(
        HaraZoneCluster(
            area_id=10,
            cluster_id=0,
            zone_key="high",
            zone_label="Zona Subur Tinggi",
            dist_to_centroid=0.5,
            dist_to_second=1.2,
            model_version="kmeans-v1.0.0",
        )
    )

    # Add expert override setting zone to 'low'
    in_memory_db.add(
        HaraZoneLabelOverride(
            area_id=10,
            zone_key="low",
            expert_id=1,
            note="Koreksi pakar: terjadi degradasi tanah setempat",
        )
    )
    in_memory_db.commit()

    result = build_ai_analysis(mock_feature_normal, db=in_memory_db)
    assert result.zone.is_overridden is True
    assert result.zone.zone_key == "low"
    assert result.zone.zone_label == "Zona Subur Rendah"
    assert result.zone.override_note == "Koreksi pakar: terjadi degradasi tanah setempat"


def test_confidence_breakdown_transparency(mock_feature_normal):
    """Verify transparent confidence breakdown with weights and valid score range."""
    result = build_ai_analysis(mock_feature_normal)
    conf = result.confidence
    assert conf is not None
    assert 0.0 <= conf.score <= 1.0
    assert conf.category in {"tinggi", "sedang", "rendah"}

    bd = conf.breakdown
    assert 0.0 <= bd.cluster_margin <= 1.0
    assert bd.data_completeness == 1.0
    assert 0.0 <= bd.rule_zone_agreement <= 1.0
    assert bd.boundary_proximity_penalty >= 0.0

    assert bd.weights["cluster_margin"] == WEIGHT_CLUSTER_MARGIN
    assert bd.weights["data_completeness"] == WEIGHT_DATA_COMPLETENESS
    assert bd.weights["rule_zone_agreement"] == WEIGHT_RULE_ZONE_AGREEMENT


def test_limiting_factors_order_and_advisory(mock_feature_critical_acid):
    """Verify limiting factors are sorted by severity, critical factors trigger expert review, and dosages are qualitative."""
    result = build_ai_analysis(mock_feature_critical_acid)
    assert result.needs_expert_review is True

    # Critical severity factors must be at top
    assert len(result.limiting_factors) > 0
    top_factor = result.limiting_factors[0]
    assert top_factor.severity == "critical"

    # Amendment advice check: qualitative dosage only!
    assert len(result.amendments) > 0
    for amd in result.amendments:
        assert amd.dosage is None
        assert "arahan penyuluh" in amd.dosage_note.lower() or "sesuaikan" in amd.dosage_note.lower()
