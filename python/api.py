"""
MarketLens: REST API for Order Delivery Delay Prediction
Endpoints: GET /health, GET /metadata, POST /predict
"""

import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import pandas as pd
from flask import Flask, jsonify, request

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import API_HOST, API_PORT, MODEL_DIR, MODEL_NAME, MODEL_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("marketlens.api")

FEATURE_COLUMNS = [
    "price",
    "freight_value",
    "product_weight_g",
    "product_length_cm",
    "product_height_cm",
    "product_width_cm",
    "customer_state_enc",
    "seller_state_enc",
    "purchase_month",
    "purchase_dow",
]

NUMERIC_CONSTRAINTS = {
    "price": {"type": (int, float), "min": 0.01, "max": 50000.0, "description": "Item price in Brazilian Real (BRL, R$)"},
    "freight_value": {"type": (int, float), "min": 0.0, "max": 10000.0, "description": "Shipping cost in Brazilian Real (BRL, R$)"},
    "product_weight_g": {"type": (int, float), "min": 1.0, "max": 100000.0, "description": "Product weight in grams"},
    "product_length_cm": {"type": (int, float), "min": 1.0, "max": 300.0, "description": "Package length in cm"},
    "product_height_cm": {"type": (int, float), "min": 1.0, "max": 300.0, "description": "Package height in cm"},
    "product_width_cm": {"type": (int, float), "min": 1.0, "max": 300.0, "description": "Package width in cm"},
    "purchase_month": {"type": int, "min": 1, "max": 12, "description": "Month of purchase (1=Jan, 12=Dec)"},
    "purchase_dow": {"type": int, "min": 0, "max": 6, "description": "Day of week matching PostgreSQL EXTRACT(DOW) (0=Sunday, 6=Saturday)"},
}


class ModelRegistry:
    """Loads model artifacts once at startup and holds them in memory."""

    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self.model = None
        self.le_cust = None
        self.le_sell = None
        self.metadata: Dict[str, Any] | None = None
        self.is_loaded = False
        self.load_error: str | None = None

    def load(self) -> bool:
        try:
            model_path = self.model_dir / "delivery_delay_model.pkl"
            cust_path = self.model_dir / "le_customer_state.pkl"
            sell_path = self.model_dir / "le_seller_state.pkl"
            meta_path = self.model_dir / "model_metadata.json"

            if not (model_path.exists() and cust_path.exists() and sell_path.exists()):
                raise FileNotFoundError(
                    f"Required model artifacts missing in {self.model_dir}."
                )

            self.model = joblib.load(model_path)
            self.le_cust = joblib.load(cust_path)
            self.le_sell = joblib.load(sell_path)

            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = None

            self.is_loaded = True
            self.load_error = None
            logger.info("Loaded ML model and encoders from %s", self.model_dir)
            return True
        except Exception as exc:
            self.is_loaded = False
            self.load_error = str(exc)
            logger.error("Failed to load model artifacts: %s", exc)
            return False


def validate_payload(payload: Any, registry: ModelRegistry) -> Tuple[bool, str | None, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return False, "Request body must be a valid JSON object.", {}

    required_fields = list(NUMERIC_CONSTRAINTS.keys()) + ["customer_state", "seller_state"]
    missing = [f for f in required_fields if f not in payload or payload[f] is None]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}", {}

    cleaned: Dict[str, Any] = {}
    for field, rules in NUMERIC_CONSTRAINTS.items():
        val = payload[field]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            expected_name = "integer" if rules["type"] is int else "number"
            return False, f"Field '{field}' must be a valid {expected_name}.", {}

        if not math.isfinite(float(val)):
            return False, f"Field '{field}' must be a finite number.", {}

        if rules["type"] is int:
            if isinstance(val, float) and not val.is_integer():
                return False, f"Field '{field}' must be an integer.", {}
            val = int(val)
        else:
            val = float(val)

        if val < rules["min"] or val > rules["max"]:
            return False, f"Field '{field}' must be between {rules['min']} and {rules['max']}.", {}
        cleaned[field] = val

    if not isinstance(payload["customer_state"], str) or not isinstance(payload["seller_state"], str):
        return False, "Fields 'customer_state' and 'seller_state' must be strings.", {}

    cust_state = payload["customer_state"].strip().upper()
    sell_state = payload["seller_state"].strip().upper()

    valid_cust = set(str(x) for x in registry.le_cust.classes_)
    valid_sell = set(str(x) for x in registry.le_sell.classes_)

    if cust_state not in valid_cust:
        return False, f"Invalid 'customer_state' ('{cust_state}'). Must be one of {sorted(valid_cust)}.", {}
    if sell_state not in valid_sell:
        return False, f"Invalid 'seller_state' ('{sell_state}'). Must be one of {sorted(valid_sell)}.", {}

    cleaned["customer_state"] = cust_state
    cleaned["seller_state"] = sell_state
    return True, None, cleaned


def create_app(model_dir: Path = MODEL_DIR) -> Flask:
    app = Flask(__name__)
    registry = ModelRegistry(model_dir)
    registry.load()
    app.config["MODEL_REGISTRY"] = registry

    @app.route("/health", methods=["GET"])
    def health():
        reg: ModelRegistry = app.config["MODEL_REGISTRY"]
        status_code = 200 if reg.is_loaded else 503
        return jsonify({
            "status": "healthy" if reg.is_loaded else "degraded",
            "model_loaded": reg.is_loaded,
            "metadata_loaded": reg.metadata is not None,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "error": reg.load_error,
        }), status_code

    @app.route("/metadata", methods=["GET"])
    def metadata():
        reg: ModelRegistry = app.config["MODEL_REGISTRY"]
        cust_states = [str(x) for x in reg.le_cust.classes_] if reg.is_loaded else []
        sell_states = [str(x) for x in reg.le_sell.classes_] if reg.is_loaded else []

        live_importances = None
        if reg.is_loaded and hasattr(reg.model, "feature_importances_"):
            s = pd.Series(reg.model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
            live_importances = {k: round(float(v), 4) for k, v in s.items()}

        input_schema = {
            field: {
                "type": "integer" if rules["type"] is int else "float",
                "min": rules["min"],
                "max": rules["max"],
                "required": True,
                "description": rules["description"],
            }
            for field, rules in NUMERIC_CONSTRAINTS.items()
        }
        input_schema["customer_state"] = {
            "type": "string",
            "allowed_values": cust_states,
            "required": True,
            "description": "Two-letter Brazilian customer state code (e.g., SP, RJ, MG)",
        }
        input_schema["seller_state"] = {
            "type": "string",
            "allowed_values": sell_states,
            "required": True,
            "description": "Two-letter Brazilian seller state code (e.g., SP, PR, MG)",
        }

        meta = reg.metadata or {}
        has_meta = reg.metadata is not None

        return jsonify({
            "model_name": meta.get("model_name", MODEL_NAME),
            "model_version": meta.get("model_version", MODEL_VERSION),
            "training_status": meta.get("training_status", "trained" if reg.is_loaded else "unavailable"),
            "model_loaded": reg.is_loaded,
            "currency": meta.get("currency", "BRL (R$)"),
            "target": meta.get("target", "is_delayed"),
            "evaluation_metrics": meta.get("metrics") if has_meta else None,
            "dataset_summary": (
                {
                    "total_records": meta.get("dataset_records"),
                    "train_records": meta.get("train_records"),
                    "test_records": meta.get("test_records"),
                }
                if has_meta
                else None
            ),
            "feature_importances": meta.get("feature_importances", live_importances),
            "limitations": meta.get("limitations", []),
            "input_schema": input_schema,
        }), 200

    @app.route("/predict", methods=["POST"])
    def predict():
        reg: ModelRegistry = app.config["MODEL_REGISTRY"]
        if not reg.is_loaded:
            return jsonify({
                "error": "Model unavailable",
                "message": reg.load_error or "Model artifacts are not loaded.",
            }), 503

        if not request.is_json:
            return jsonify({
                "error": "Invalid Content-Type",
                "message": request.headers.get('Content-Type'),
            }), 400

        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({
                "error": "Malformed JSON",
                "message": "Request body could not be parsed as valid JSON.",
            }), 400

        is_valid, err_msg, cleaned = validate_payload(payload, reg)
        if not is_valid:
            return jsonify({
                "error": "Validation error",
                "message": err_msg,
            }), 400

        try:
            c_enc = int(reg.le_cust.transform([cleaned["customer_state"]])[0])
            s_enc = int(reg.le_sell.transform([cleaned["seller_state"]])[0])

            feature_df = pd.DataFrame([{
                "price": cleaned["price"],
                "freight_value": cleaned["freight_value"],
                "product_weight_g": cleaned["product_weight_g"],
                "product_length_cm": cleaned["product_length_cm"],
                "product_height_cm": cleaned["product_height_cm"],
                "product_width_cm": cleaned["product_width_cm"],
                "customer_state_enc": c_enc,
                "seller_state_enc": s_enc,
                "purchase_month": cleaned["purchase_month"],
                "purchase_dow": cleaned["purchase_dow"],
            }])[FEATURE_COLUMNS]

            pred_class = int(reg.model.predict(feature_df)[0])
            delay_prob = float(reg.model.predict_proba(feature_df)[0][1])

            risk_level = (
                "High Risk" if delay_prob >= 0.50
                else "Moderate Risk" if delay_prob >= 0.30
                else "Low Risk"
            )
            cross_state = cleaned["customer_state"] != cleaned["seller_state"]
            route_note = (
                f"Cross-state shipment ({cleaned['seller_state']} -> {cleaned['customer_state']})"
                if cross_state
                else f"Intra-state shipment ({cleaned['customer_state']})"
            )

            meta = reg.metadata or {}
            interpretation = (
                f"{risk_level} of delivery delay ({delay_prob * 100:.1f}% estimated probability). "
                f"{route_note}, freight R$ {cleaned['freight_value']:.2f}, weight {cleaned['product_weight_g']:.0f}g."
            )

            return jsonify({
                "prediction": pred_class,
                "prediction_label": "Delayed" if pred_class == 1 else "On Time",
                "delay_probability": round(delay_prob, 4),
                "risk_level": risk_level,
                "interpretation": interpretation,
                "currency": "BRL (R$)",
                "model_name": meta.get("model_name", MODEL_NAME),
                "model_version": meta.get("model_version", MODEL_VERSION),
            }), 200

        except Exception as exc:
            logger.exception("Unexpected error during prediction")
            return jsonify({
                "error": "Internal server error",
                "message": str(exc),
            }), 500

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host=API_HOST, port=API_PORT, debug=False)