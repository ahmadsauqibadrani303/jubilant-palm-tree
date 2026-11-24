"""
Integration tests for SAFRONS AI analysis endpoints and RBAC (FASE 3).
"""

import time
from collections.abc import Callable, Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.hara import HaraArea
from app.models.user import User
from app.models.zone_cluster import ensure_zone_cluster_tables


@pytest.fixture()
def client_with_db() -> Generator[tuple[TestClient, Callable[[], Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed test hara area
    with testing_session_local() as db:
        ensure_zone_cluster_tables(db)
        area = HaraArea(
            id=1,
            name="Cibinong",
            ph_rata2=Decimal("5.6"),
            n_rata2=Decimal("3.8"),
            p_rata2=Decimal("12.5"),
            k_rata2=Decimal("260.0"),
            slope__="2-8",
            texture_of="Lempung Berdebu",
        )
        db.add(area)
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), testing_session_local
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, email: str, role: str | None = None) -> dict[str, str]:
    password = "strong-password-123"
    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Test User"})
    if role is not None:
        promote_user_in_test_db(email, role)
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def promote_user_in_test_db(email: str, role: str) -> None:
    db_override = app.dependency_overrides[get_db]
    db = next(db_override())
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.role = role
            db.commit()
    finally:
        db.close()


def test_get_area_ai_analysis_success_and_latency(client_with_db):
    """Verify GET /api/v1/hara/areas/{id}/analysis returns valid schema and finishes in <= 1.5s."""
    client, _ = client_with_db
    start_time = time.perf_counter()
    response = client.get("/api/v1/hara/areas/1/analysis")
    elapsed = time.perf_counter() - start_time

    assert response.status_code == 200
    assert elapsed < 1.5, f"Inference latency was {elapsed:.3f}s, exceeding 1.5s target"

    data = response.json()
    assert data["area_id"] == 1
    assert data["status"] == "ready"
    assert "zone" in data
    assert "crop_ranking" in data
    assert len(data["crop_ranking"]) == 3
    assert "confidence" in data
    assert data["confidence"]["category"] in {"tinggi", "sedang", "rendah"}
    assert "meta" in data
    assert data["meta"]["model_version"] == "kmeans-v1.0.0"


def test_get_area_ai_analysis_not_found(client_with_db):
    """Verify 404 when querying an area_id that does not exist."""
    client, _ = client_with_db
    response = client.get("/api/v1/hara/areas/9999/analysis")
    assert response.status_code == 404
    assert response.json()["detail"] == "Hara area not found"


def test_get_hara_zones_lightweight_list(client_with_db):
    """Verify GET /api/v1/hara/zones returns lightweight list with cache headers."""
    client, _ = client_with_db
    response = client.get("/api/v1/hara/zones")
    assert response.status_code == 200
    assert "public, max-age=86400" in response.headers.get("Cache-Control", "")

    items = response.json()
    assert isinstance(items, list)
    assert len(items) > 0
    first = items[0]
    assert "area_id" in first
    assert "zone_key" in first
    assert "zone_label" in first
    assert "confidence_category" in first


def test_get_ml_model_info(client_with_db):
    """Verify GET /api/v1/ml/model-info returns public metadata and metrics."""
    client, _ = client_with_db
    response = client.get("/api/v1/ml/model-info")
    assert response.status_code == 200

    data = response.json()
    assert data["model_version"] == "kmeans-v1.0.0"
    assert data["algorithm"] == "KMeans"
    assert data["k"] == 3
    assert "silhouette" in data["metrics"]
    assert "davies_bouldin" in data["metrics"]
    assert len(data["clusters"]) == 3


def test_expert_review_rbac_and_override(client_with_db):
    """
    Test RBAC on POST /api/v1/expert/areas/{id}/analysis-review:
      - 401 unauthenticated
      - 403 normal user
      - 201 expert / admin
    """
    client, _ = client_with_db
    payload = {
        "decision": "overridden",
        "zone_key": "high",
        "note": "Koreksi pakar: tanah telah diperbaiki secara intensif",
    }

    # 1. Unauthenticated -> 401
    res_unauth = client.post("/api/v1/expert/areas/1/analysis-review", json=payload)
    assert res_unauth.status_code == 401

    # 2. Normal user -> 403
    user_hdr = auth_headers(client, "petani@desa.id", role="user")
    res_user = client.post("/api/v1/expert/areas/1/analysis-review", json=payload, headers=user_hdr)
    assert res_user.status_code == 403
    assert "Expert access required" in res_user.json()["detail"]

    # 3. Expert -> 201 Created
    expert_hdr = auth_headers(client, "pakar@safrons.id", role="expert")
    res_expert = client.post("/api/v1/expert/areas/1/analysis-review", json=payload, headers=expert_hdr)
    assert res_expert.status_code == 201

    data = res_expert.json()
    assert data["zone"]["is_overridden"] is True
    assert data["zone"]["zone_key"] == "high"
    assert data["latest_review"] is not None
    assert data["latest_review"]["decision"] == "overridden"
    assert data["latest_review"]["note"] == "Koreksi pakar: tanah telah diperbaiki secara intensif"


def test_expert_review_queue_rbac(client_with_db):
    """
    Test RBAC and queue retrieval on GET /api/v1/expert/analysis-review/queue.
    """
    client, _ = client_with_db

    # Unauthenticated -> 401
    assert client.get("/api/v1/expert/analysis-review/queue").status_code == 401

    # Normal user -> 403
    user_hdr = auth_headers(client, "petani2@desa.id", role="user")
    assert client.get("/api/v1/expert/analysis-review/queue", headers=user_hdr).status_code == 403

    # Expert -> 200 OK
    expert_hdr = auth_headers(client, "pakar2@safrons.id", role="expert")
    res = client.get("/api/v1/expert/analysis-review/queue", headers=expert_hdr)
    assert res.status_code == 200
    queue = res.json()
    assert isinstance(queue, list)
