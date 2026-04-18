"""Startup seeding for analytics dataset state."""

import tempfile
from pathlib import Path

from src.analytics.dataset_preparation import build_dataset, persist_dataset
from src.utils.db_utils import get_connection
from src.storage.dao import StorageDAO


def seed_health_insurance_data_if_empty() -> None:
    """Populate analytics table from blob CSV if the table exists but has no rows."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM [health_insurance_with_risk]")
        row_count = cursor.fetchone()[0]
        if row_count > 0:
            return

        try:
            storage = StorageDAO()
            temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-seed-"))
            data_blob_name = "data/health_insurance_data.csv"
            data_path = temp_dir / "health_insurance_data.csv"

            storage.download_file(data_blob_name, data_path)
            df = build_dataset(data_path)
            persist_dataset(df)
        except FileNotFoundError:
            # Seeding is optional; skip when dataset is not available yet.
            return
    except Exception as exc:
        # Log but do not block API startup when optional seeding fails.
        print(f"Warning: Could not seed health_insurance_with_risk data: {exc}")
    finally:
        conn.close()

