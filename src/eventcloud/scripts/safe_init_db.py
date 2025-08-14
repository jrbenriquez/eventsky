# scripts/init_db.py
"""
Safe DB initializer:
- If the database is empty: create all tables from SQLAlchemy models.
- If some tables exist: print a warning and exit (recommended to use Alembic).
- Optional override: set ALLOW_CREATE_MISSING=true to create only missing tables.
"""

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
import os
import sys

# Import your SQLAlchemy engine/Base and models so metadata is populated
from eventcloud.db import engine, Base
# Import models to ensure they’re registered on Base.metadata
from eventcloud import models  # noqa: F401  (ensure side-effects)

ALLOW_CREATE_MISSING = os.getenv("ALLOW_CREATE_MISSING", "").lower() in {"1", "true", "yes"}

def main() -> int:
    inspector = inspect(engine)
    try:
        existing = set(inspector.get_table_names())
    except SQLAlchemyError as e:
        print(f"[init_db] ❌ Failed to inspect database: {e}", file=sys.stderr)
        return 1

    defined = set(Base.metadata.tables.keys())

    if not existing:
        # Completely empty DB — safe to create everything
        print("[init_db] 🆕 Empty database detected. Creating all tables…")
        try:
            Base.metadata.create_all(bind=engine)
            print("[init_db] ✅ All tables created.")
            return 0
        except SQLAlchemyError as e:
            print(f"[init_db] ❌ create_all failed: {e}", file=sys.stderr)
            return 1

    # Some tables already exist
    missing = sorted(defined - existing)
    extra = sorted(existing - defined)

    print("[init_db] ℹ️ Existing tables:", sorted(existing))
    print("[init_db] ℹ️ Defined tables :", sorted(defined))

    if not missing:
        print("[init_db] ✅ Schema tables already exist. Nothing to do.")
        if extra:
            print(f"[init_db] ⚠️ These tables exist in DB but not in models: {extra}")
        return 0

    # Mixed state
    print(f"[init_db] ⚠️ Detected missing tables: {missing}")
    if extra:
        print(f"[init_db] ⚠️ Also found extra tables not in models: {extra}")

    if not ALLOW_CREATE_MISSING:
        print(
            "[init_db] ⛔️ Will NOT modify a partially-initialized database.\n"
            "         Use Alembic migrations to evolve schema safely:\n"
            "           alembic upgrade head\n"
            "         (Or set ALLOW_CREATE_MISSING=true to create only the missing tables.)"
        )
        return 2

    # User explicitly allowed creating only the missing tables
    try:
        print("[init_db] 🚧 Creating only missing tables (ALLOW_CREATE_MISSING=true)…")
        # Build a minimal MetaData with only missing tables and create them
        from sqlalchemy import MetaData
        md = MetaData()
        for name in missing:
            Base.metadata.tables[name].tometadata(md)
        md.create_all(bind=engine)
        print("[init_db] ✅ Missing tables created.")
        return 0
    except SQLAlchemyError as e:
        print(f"[init_db] ❌ Failed to create missing tables: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

