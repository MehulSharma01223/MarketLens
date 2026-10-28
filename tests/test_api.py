"""
Automated unit and integration tests for the MarketLens REST API (7 test functions).
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from api import create_app  # noqa: E402  # type: ignore

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True


def test_metadata_endpoint(client):
    resp = client.get("/metadata")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["model_loaded"] is True
    assert data["currency"] == "BRL (R$)"
    assert "evaluation_metrics" in data
    assert "feature_importances" in data
    assert isinstance(data["feature_importances"], dict)
    assert "input_schema" in data
    assert "price" in data["input_schema"]
    assert "purchase_dow" in data["input_schema"]
    assert data["input_schema"]["purchase_dow"]["min"] == 0
    assert data["input_schema"]["purchase_dow"]["max"] == 6
    assert "0=Sunday, 6=Saturday" in data["input_schema"]["purchase_dow"]["description"]
    assert "customer_state" in data["input_schema"]
    assert len(data["input_schema"]["customer_state"]["allowed_values"]) > 0


def test_predict_valid_request(client):
    payload = {
        "price": 120.0,
        "freight_value": 25.0,
        "product_weight_g": 1200.0,
        "product_length_cm": 35.0,
        "product_height_cm": 15.0,
        "product_width_cm": 25.0,
        "customer_state": "SP",
        "seller_state": "SP",
        "purchase_month": 6,
        "purchase_dow": 2,  # 2 = Tuesday (PostgreSQL EXTRACT(DOW): 0=Sunday .. 6=Saturday)
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["prediction"] in (0, 1)
    assert data["prediction_label"] in ("On Time", "Delayed")
    assert 0.0 <= data["delay_probability"] <= 1.0
    assert data["currency"] == "BRL (R$)"
    assert "R$" in data["interpretation"]
    assert "model_version" in data


def test_predict_missing_fields(client):
    payload = {"price": 100.0, "freight_value": 15.0}
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Validation error"
    assert "Missing required fields" in data["message"]


def test_predict_out_of_range_values(client):
    payload = {
        "price": -50.0,
        "freight_value": 25.0,
        "product_weight_g": 1200.0,
        "product_length_cm": 35.0,
        "product_height_cm": 15.0,
        "product_width_cm": 25.0,
        "customer_state": "SP",
        "seller_state": "SP",
        "purchase_month": 13,
        "purchase_dow": 2,
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Validation error"


def test_predict_invalid_state(client):
    payload = {
        "price": 120.0,
        "freight_value": 25.0,
        "product_weight_g": 1200.0,
        "product_length_cm": 35.0,
        "product_height_cm": 15.0,
        "product_width_cm": 25.0,
        "customer_state": "INVALID_STATE",
        "seller_state": "SP",
        "purchase_month": 6,
        "purchase_dow": 2,
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "Invalid 'customer_state'" in data["message"]


def test_unavailable_model_returns_503(tmp_path):
    empty_app = create_app(model_dir=tmp_path)
    empty_app.config["TESTING"] = True
    with empty_app.test_client() as c:
        health_resp = c.get("/health")
        assert health_resp.status_code == 503
        meta_resp = c.get("/metadata")
        assert meta_resp.status_code == 200
        assert meta_resp.get_json()["evaluation_metrics"] is None
        pred_resp = c.post("/predict", json={"price": 100.0})
        assert pred_resp.status_code == 503