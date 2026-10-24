"""
MarketLens: Non-Destructive Model Metadata Exporter
Evaluates the existing saved model in models/ without retraining or overwriting .pkl files,
and writes measured metrics to models/model_metadata.json.
"""

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import text

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import MODEL_DIR, MODEL_NAME, MODEL_VERSION
from db_connection import get_db_engine

FEATURE_COLS = [
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


def export_metadata() -> None:
    model_path = MODEL_DIR / "delivery_delay_model.pkl"
    cust_path = MODEL_DIR / "le_customer_state.pkl"
    sell_path = MODEL_DIR / "le_seller_state.pkl"

    if not (model_path.exists() and cust_path.exists() and sell_path.exists()):
        raise FileNotFoundError(
            f"Cannot export metadata: missing .pkl artifacts in {MODEL_DIR}."
        )

    print(f"[Metadata] Loading existing model artifacts from {MODEL_DIR} (no retraining)...")
    rf_model = joblib.load(model_path)
    le_cust = joblib.load(cust_path)
    le_sell = joblib.load(sell_path)

    print("[Metadata] Querying PostgreSQL to reproduce test split evaluation...")
    engine = get_db_engine()
    query = """
    SELECT 
        o.order_id,
        oi.price,
        oi.freight_value,
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,
        c.customer_state,
        s.seller_state,
        EXTRACT(MONTH FROM o.order_purchase_timestamp) AS purchase_month,
        EXTRACT(DOW FROM o.order_purchase_timestamp) AS purchase_dow,
        CASE 
            WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 
            ELSE 0 
        END AS is_delayed
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN sellers s ON oi.seller_id = s.seller_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
      AND o.order_estimated_delivery_date IS NOT NULL
      AND p.product_weight_g IS NOT NULL;
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)

    df["customer_state_enc"] = le_cust.transform(df["customer_state"])
    df["seller_state_enc"] = le_sell.transform(df["seller_state"])

    X = df[FEATURE_COLS].fillna(0)
    y = df["is_delayed"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    y_pred = rf_model.predict(X_test)
    y_proba = rf_model.predict_proba(X_test)[:, 1]
    report_dict = classification_report(y_test, y_pred, output_dict=True)
    auc_score = roc_auc_score(y_test, y_proba)

    importances = pd.Series(rf_model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)

    metadata = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "training_status": "trained",
        "target": "is_delayed (1 = delivered after estimated date, 0 = delivered on or before estimated date)",
        "currency": "BRL (R$)",
        "dataset_records": int(len(df)),
        "train_records": int(len(X_train)),
        "test_records": int(len(X_test)),
        "metrics": {
            "roc_auc": round(float(auc_score), 4),
            "accuracy": round(float(report_dict["accuracy"]), 4),
            "on_time_precision": round(float(report_dict["0"]["precision"]), 4),
            "on_time_recall": round(float(report_dict["0"]["recall"]), 4),
            "on_time_f1": round(float(report_dict["0"]["f1-score"]), 4),
            "delayed_precision": round(float(report_dict["1"]["precision"]), 4),
            "delayed_recall": round(float(report_dict["1"]["recall"]), 4),
            "delayed_f1": round(float(report_dict["1"]["f1-score"]), 4),
        },
        "feature_importances": {k: round(float(v), 4) for k, v in importances.items()},
        "customer_states": [str(x) for x in le_cust.classes_],
        "seller_states": [str(x) for x in le_sell.classes_],
        "limitations": [
            "Trained on historical Olist Brazilian e-commerce deliveries (2016-2018); all monetary values are in Brazilian Real (BRL, R$).",
            "Class imbalance (~7.9% delayed orders); class_weight='balanced' prioritizes delay recall over precision.",
            "Uses only pre-delivery order and item attributes known at purchase time to prevent target leakage; external transit disruptions are unobserved.",
        ],
    }

    meta_path = MODEL_DIR / "model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[Metadata] Saved measured metadata to {meta_path}")


if __name__ == "__main__":
    export_metadata()