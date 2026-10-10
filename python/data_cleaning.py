"""
MarketLens: E-Commerce Analytics Pipeline
Phase 2: Data Cleaning & Processing Module
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np

# Base directory: script ki location (MarketLens folder) ke hisaab se absolute paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RAW_PATH = BASE_DIR / "data" / "raw"
DEFAULT_PROCESSED_PATH = BASE_DIR / "data" / "processed"


def run_cleaning_pipeline(raw_path=DEFAULT_RAW_PATH, processed_path=DEFAULT_PROCESSED_PATH):
    print(f"[PIPELINE] Starting Data Cleaning Pipeline...")
    print(f"[PIPELINE] Raw Data Path: {raw_path}")
    print(f"[PIPELINE] Processed Data Path: {processed_path}")

    os.makedirs(processed_path, exist_ok=True)

    # 1. Load Datasets
    print("\n[1/5] Loading raw datasets...")
    customers = pd.read_csv(os.path.join(raw_path, "olist_customers_dataset.csv"))
    geolocation = pd.read_csv(os.path.join(raw_path, "olist_geolocation_dataset.csv"))
    order_items = pd.read_csv(os.path.join(raw_path, "olist_order_items_dataset.csv"))
    payments = pd.read_csv(os.path.join(raw_path, "olist_order_payments_dataset.csv"))
    reviews = pd.read_csv(os.path.join(raw_path, "olist_order_reviews_dataset.csv"))
    orders = pd.read_csv(os.path.join(raw_path, "olist_orders_dataset.csv"))
    products = pd.read_csv(os.path.join(raw_path, "olist_products_dataset.csv"))
    sellers = pd.read_csv(os.path.join(raw_path, "olist_sellers_dataset.csv"))
    category_translation = pd.read_csv(os.path.join(raw_path, "product_category_name_translation.csv"))

    # 2. Datetime Conversions
    print("[2/5] Casting datetime columns...")
    datetime_map = {
        "orders": [
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date"
        ],
        "order_items": ["shipping_limit_date"],
        "reviews": ["review_creation_date", "review_answer_timestamp"]
    }
    
    tables_dict = {"orders": orders, "order_items": order_items, "reviews": reviews}
    for table_name, cols in datetime_map.items():
        for col in cols:
            tables_dict[table_name][col] = pd.to_datetime(tables_dict[table_name][col], errors="coerce")

    # 3. Zip Code Zero-Padding
    print("[3/5] Standardizing zip codes to 5-digit strings...")
    customers["customer_zip_code_prefix"] = customers["customer_zip_code_prefix"].astype(str).str.zfill(5)
    sellers["seller_zip_code_prefix"] = sellers["seller_zip_code_prefix"].astype(str).str.zfill(5)
    geolocation["geolocation_zip_code_prefix"] = geolocation["geolocation_zip_code_prefix"].astype(str).str.zfill(5)

    # 4. Deduplication, Aggregation & Imputation
    print("[4/5] Executing deduplication and missing value imputations...")
    # Deduplicate reviews (retain latest timestamp)
    reviews_clean = (
        reviews.sort_values("review_answer_timestamp")
        .drop_duplicates(subset=["review_id"], keep="last")
        .reset_index(drop=True)
    )

    # Aggregate geolocation
    geolocation_clean = (
        geolocation.groupby("geolocation_zip_code_prefix")
        .agg({
            "geolocation_lat": "mean",
            "geolocation_lng": "mean",
            "geolocation_city": "first",
            "geolocation_state": "first"
        })
        .reset_index()
    )

    # Impute products missing metadata
    products["product_category_name"] = products["product_category_name"].fillna("uncategorized")
    dimension_cols = ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm", "product_photos_qty"]
    for dim in dimension_cols:
        products[dim] = products[dim].fillna(products[dim].median())

    # Payments sanity filter
    payments_clean = payments[payments["payment_value"] > 0].copy().reset_index(drop=True)

    # 5. Export Processed Datasets
    print("[5/5] Exporting clean CSVs to processed directory...")
    export_manifest = {
        "customers_cleaned.csv": customers,
        "geolocation_cleaned.csv": geolocation_clean,
        "order_items_cleaned.csv": order_items,
        "payments_cleaned.csv": payments_clean,
        "reviews_cleaned.csv": reviews_clean,
        "orders_cleaned.csv": orders,
        "products_cleaned.csv": products,
        "sellers_cleaned.csv": sellers,
        "category_translation_cleaned.csv": category_translation
    }

    for filename, df in export_manifest.items():
        filepath = os.path.join(processed_path, filename)
        df.to_csv(filepath, index=False)
        print(f"  -> Saved {filename} ({len(df):,} rows)")

    print("\n[SUCCESS] Data Cleaning Pipeline completed successfully!")


if __name__ == "__main__":
    run_cleaning_pipeline()