"""
MarketLens: Database Connection & Verification Module
Phase 3: PostgreSQL Integration
"""

import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "marketlens")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# Encode special characters in password (@, ?, etc.)
encoded_password = quote_plus(DB_PASSWORD)

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_db_engine():
    """Returns an engine instance for PostgreSQL connection."""
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def test_connection():
    """Verifies that the database connection works and prints the server version."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();")).scalar()
            print("[SUCCESS] Connected to PostgreSQL!")
            print(f"[SERVER VERSION] {result}")
        return True
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL: {e}")
        return False


if __name__ == "__main__":
    test_connection()