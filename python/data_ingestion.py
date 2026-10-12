"""
MarketLens: Data Ingestion Pipeline
Phase 3: Bulk Load Clean Datasets into PostgreSQL
"""

import os
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from db_connection import get_db_engine

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_PATH = BASE_DIR / "data" / "processed"

# Ingestion manifest strictly ordered by foreign key constraints
INGESTION_PIPELINE = [
    {"table": "geolocation", "file": "geolocation_cleaned.csv"},
    {"table": "customers", "file": "customers_cleaned.csv"},
    {"table": "sellers", "file": "sellers_cleaned.csv"},
    {"table": "product_category_translation", "file": "category_translation_cleaned.csv"},
    {"table": "products", "file": "products_cleaned.csv"},
    {"table": "orders", "file": "orders_cleaned.csv"},
    {"table": "order_items", "file": "order_items_cleaned.csv"},
    {"table": "order_payments", "file": "payments_cleaned.csv"},
    {"table": "order_reviews", "file": "reviews_cleaned.csv"},
]


def ingest_data():
    engine = get_db_engine()
    print("[INGESTION] Starting bulk ingestion into PostgreSQL...\n")

    for step in INGESTION_PIPELINE:
        table_name = step["table"]
        file_name = step["file"]
        file_path = PROCESSED_PATH / file_name

        if not file_path.exists():
            print(f"[SKIP] File not found: {file_path}")
            continue

        print(f"--> Ingesting {file_name} into table '{table_name}'...")
        df = pd.read_csv(file_path)

        # Zip code prefix string format preservation (ensure 5 digits string)
        if "customer_zip_code_prefix" in df.columns:
            df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str).str.zfill(5)
        if "seller_zip_code_prefix" in df.columns:
            df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)
        if "geolocation_zip_code_prefix" in df.columns:
            df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(str).str.zfill(5)

        # Batch loading using pandas chunking for optimal speed and memory
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000
        )
        print(f"    [SUCCESS] Loaded {len(df):,} records into '{table_name}'.")

    # Final Record Count Validation
    print("\n[VALIDATION] Verifying row counts in database:")
    with engine.connect() as conn:
        for step in INGESTION_PIPELINE:
            t = step["table"]
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar()
            print(f"  • {t.ljust(28)} : {count:,} rows")

    print("\n[COMPLETE] Phase 3 Data Ingestion finished successfully!")


if __name__ == "__main__":
    ingest_data()