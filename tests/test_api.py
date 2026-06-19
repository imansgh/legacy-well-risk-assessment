"""Tests for the FastAPI backend using the in-process TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lwra.api.main import create_app
from lwra.sample_data import abandon_well, excellent_well


@pytest.fixture(scope="module")
def client() -> TestClient:
    """An in-process test client for the API."""
    return TestClient(create_app())


def _well_payload(well, *, traced: bool = False) -> dict:  # type: ignore[no-untyped-def]
    return {
        "well": well.model_dump(mode="json"),
        "as_of": "2025-01-01",
        "traced": traced,
    }


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_config(client: TestClient) -> None:
    response = client.get("/config")
    assert response.status_code == 200
    body = response.json()
    assert "risk_factor_weights" in body
    assert "integrity_category_thresholds" in body


def test_assess_lean(client: TestClient) -> None:
    response = client.post("/assess", json=_well_payload(excellent_well()))
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "lean"
    assert "trace" not in body["assessment"]
    assert body["assessment"]["recommendation"]["verdict"] == "reuse"


def test_assess_traced(client: TestClient) -> None:
    response = client.post("/assess", json=_well_payload(excellent_well(), traced=True))
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "traced"
    assert body["assessment"]["trace"] is not None


def test_assess_batch(client: TestClient) -> None:
    payload = {
        "wells": [excellent_well().model_dump(mode="json"), abandon_well().model_dump(mode="json")],
        "as_of": "2025-01-01",
        "traced": False,
    }
    response = client.post("/assess/batch", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    # Summary is ranked by risk, highest first.
    assert body["summary"][0]["well_id"] == "WELL-ABANDON"


def test_batch_rejects_duplicate_ids(client: TestClient) -> None:
    well = excellent_well().model_dump(mode="json")
    payload = {"wells": [well, well], "as_of": "2025-01-01", "traced": False}
    response = client.post("/assess/batch", json=payload)
    assert response.status_code == 422


def test_invalid_well_rejected(client: TestClient) -> None:
    bad = excellent_well().model_dump(mode="json")
    bad["total_depth_m"] = -5.0  # violates gt=0
    response = client.post("/assess", json={"well": bad})
    assert response.status_code == 422


@pytest.mark.parametrize("fmt", ["json", "excel", "pdf"])
def test_report_download(client: TestClient, fmt: str) -> None:
    response = client.post(f"/report/{fmt}", json=_well_payload(excellent_well()))
    assert response.status_code == 200
    assert len(response.content) > 0


def test_report_bad_format(client: TestClient) -> None:
    response = client.post("/report/csv", json=_well_payload(excellent_well()))
    assert response.status_code == 400
