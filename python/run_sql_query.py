"""
MarketLens: SQL Query Runner
Executes SQL analysis files and formats outputs neatly using Pandas
"""

import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from db_connection import get_db_engine

BASE_DIR = Path(__file__).resolve().parent.parent


def run_query_file(file_name: str):
    sql_path = BASE_DIR / "sql" / file_name
    if not sql_path.exists():
        print(f"[ERROR] SQL file not found: {sql_path}")
        return

    print(f"\n[RUNNING] Executing queries from: {file_name}\n" + "=" * 60)
    engine = get_db_engine()

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split queries by semicolon
    queries = [q.strip() for q in content.split(";") if q.strip()]

    with engine.connect() as conn:
        for idx, query in enumerate(queries, start=1):
            # Extract first commented header if available
            header = f"Query {idx}"
            for line in query.splitlines():
                if line.startswith("--"):
                    header = line.lstrip("-").strip()
                    break

            print(f"\n>>> {header}")
            try:
                df = pd.read_sql_query(text(query), conn)
                if not df.empty:
                    print(df.to_string(index=False))
                else:
                    print("(Query returned 0 rows)")
            except Exception as e:
                print(f"[EXECUTION ERROR] {e}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sales_analysis.sql"
    run_query_file(target)