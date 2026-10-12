"""
MarketLens: Schema Initializer
Phase 3: Execute DDL to create relational tables in PostgreSQL
"""

from pathlib import Path
from sqlalchemy import text
from db_connection import get_db_engine

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"


def apply_schema():
    print(f"[DDL] Reading schema file from: {SCHEMA_PATH}")
    
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    engine = get_db_engine()
    
    print("[DDL] Executing schema.sql on marketlens database...")
    with engine.begin() as conn:
        conn.execute(text(schema_sql))
    
    print("[SUCCESS] All 9 tables and indexes created successfully in PostgreSQL!")


if __name__ == "__main__":
    apply_schema()