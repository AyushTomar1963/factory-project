"""One-off backfill: route existing IQC inspection logs into store bins.

Run on Render shell or locally against the same DATABASE_URL:

    python scripts/sync_iqc_to_store.py
"""

from database import SessionLocal
from store_service import sync_store_from_inspections


def main():
    db = SessionLocal()
    try:
        result = sync_store_from_inspections(db, commit=True)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
