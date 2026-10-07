"""
Database initialization script for HackQubit 2.0 (Problem 18).
Executes database/schema.sql and database/seed.sql against either
PostgreSQL or SQLite depending on the configured DATABASE_URL.
"""
import os
import re
import sys
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = BASE_DIR / "database" / "schema.sql"
SEED_FILE = BASE_DIR / "database" / "seed.sql"

def get_database_url() -> str:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./database/students.db")
    # psycopg2 doesn't understand SQLAlchemy's driver suffix (postgresql+psycopg2://)
    return re.sub(r"^postgres(ql)?\+\w+://", "postgresql://", db_url)

def init_sqlite(db_path: Path):
    print(f"Initializing SQLite database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    seed_sql = SEED_FILE.read_text(encoding="utf-8")

    cursor.executescript(schema_sql)
    cursor.executescript(seed_sql)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM students;")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"[OK] Successfully initialized SQLite database with {count} student records.")

def init_postgres(db_url: str):
    print(f"Initializing PostgreSQL database using DATABASE_URL...")
    try:
        import psycopg2
    except ImportError:
        print("[!] psycopg2 not installed. Attempting SQLAlchemy...")
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(db_url)
            with engine.connect() as conn:
                schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
                seed_sql = SEED_FILE.read_text(encoding="utf-8")
                conn.execute(text(schema_sql))
                if conn.execute(text("SELECT COUNT(*) FROM students;")).scalar() == 0:
                    conn.execute(text(seed_sql))
                conn.commit()
                res = conn.execute(text("SELECT COUNT(*) FROM students;")).fetchone()
                print(f"[OK] Successfully initialized PostgreSQL database with {res[0]} student records.")
            return
        except Exception as e:
            print(f"[ERROR] Failed to initialize PostgreSQL: {e}")
            sys.exit(1)

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    seed_sql = SEED_FILE.read_text(encoding="utf-8")
    cursor.execute(schema_sql)
    # Only seed an empty table, so an existing dataset (e.g. dummy_students.sql) isn't mixed with seed rows
    cursor.execute("SELECT COUNT(*) FROM students;")
    if cursor.fetchone()[0] == 0:
        cursor.execute(seed_sql)
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM students;")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"[OK] Successfully initialized PostgreSQL database with {count} student records.")

def main():
    db_url = get_database_url()
    if db_url.startswith("sqlite"):
        # Resolve file path
        parsed = db_url.replace("sqlite:///", "").replace("sqlite://", "")
        db_path = BASE_DIR / parsed if not Path(parsed).is_absolute() else Path(parsed)
        init_sqlite(db_path)
    elif db_url.startswith("postgresql") or db_url.startswith("postgres"):
        init_postgres(db_url)
    else:
        print(f"Unknown database scheme in DATABASE_URL: {db_url}")
        sys.exit(1)

if __name__ == "__main__":
    main()

