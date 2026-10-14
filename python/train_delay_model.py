"""
MarketLens: Machine Learning Pipeline
Phase 6: Predict Delivery Delays using Scikit-Learn & PostgreSQL
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from db_connection import get_db_engine
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import LabelEncoder
import joblib
from pathlib import Path

def train_delivery_delay_model():
    print("[ML] Connecting to PostgreSQL to extract training dataset...")
    engine = get_db_engine()

    # SQL query to extract relevant features for delay prediction
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

    print(f"[ML] Extracted {len(df):,} records for modeling.")

    # --- Data Preprocessing & Feature Engineering ---
    print("[ML] Preparing features and encoding categorical variables...")
    
    le_cust = LabelEncoder()
    le_sell = LabelEncoder()
    df['customer_state_enc'] = le_cust.fit_transform(df['customer_state'])
    df['seller_state_enc'] = le_sell.fit_transform(df['seller_state'])

    feature_cols = [
        'price', 'freight_value', 'product_weight_g', 
        'product_length_cm', 'product_height_cm', 'product_width_cm',
        'customer_state_enc', 'seller_state_enc', 
        'purchase_month', 'purchase_dow'
    ]
    
    X = df[feature_cols].fillna(0)
    y = df['is_delayed']

    # Train-Test Split (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"[ML] Training set size: {len(X_train):,}, Test set size: {len(X_test):,}")

    # --- Model Training ---
    print("[ML] Training Random Forest Classifier...")
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    rf_model.fit(X_train, y_train)

    # --- Evaluation ---
    print("[ML] Evaluating model performance...")
    y_pred = rf_model.predict(X_test)
    y_proba = rf_model.predict_proba(X_test)[:, 1]

    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred))
    
    auc_score = roc_auc_score(y_test, y_proba)
    print(f"ROC-AUC Score: {auc_score:.4f}")

    # Feature Importance
    importances = pd.Series(rf_model.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\n--- Top Feature Importances ---")
    print(importances.head(5))

    # --- Save Model and Encoders Inside Function ---
    MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(rf_model, MODEL_DIR / "delivery_delay_model.pkl")
    joblib.dump(le_cust, MODEL_DIR / "le_customer_state.pkl")
    joblib.dump(le_sell, MODEL_DIR / "le_seller_state.pkl")
    print(f"[ML] Model and encoders saved successfully to {MODEL_DIR}")

    print("\n[COMPLETE] Phase 6 Machine Learning model trained and saved successfully!")

if __name__ == "__main__":
    train_delivery_delay_model()