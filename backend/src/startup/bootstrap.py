"""Application startup orchestration (schema + optional seed)."""

from src.analytics.seeding import seed_health_insurance_data_if_empty
from src.utils.db_utils import get_connection
from src.startup.schema import STARTUP_SCHEMA_STATEMENTS


def ensure_core_schema() -> None:
    """Ensure all required SQL tables exist."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for statement in STARTUP_SCHEMA_STATEMENTS:
                cursor.execute(statement)
    finally:
        conn.close()


def ensure_startup_state() -> None:
    """Run startup bootstrapping steps in deterministic order."""
    ensure_core_schema()
    seed_health_insurance_data_if_empty()

