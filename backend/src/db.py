"""Database connection and startup schema initialization helpers."""


# Standard library imports
import os
import tempfile
from pathlib import Path
import time

# External dependency for Azure SQL connection
from mssql_python import connect
from src.health_insurance_risk_classifier import build_dataset, persist_dataset
from src.storage.dao import StorageDAO
from src.schema import STARTUP_SCHEMA_STATEMENTS

def get_db_backend():
    """Return the type of DB backend in use (for future extensibility)."""
    return "azuresql"

def _get_connection_string() -> str:
    """Fetch the Azure SQL connection string from the environment variable."""
    connection_string = os.getenv("WSAA_DB_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("WSAA_DB_CONNECTION_STRING is required for Azure SQL backend.")
    return connection_string

def get_connection():
    """Establish a connection to Azure SQL with retry logic for transient errors."""
    if connect is None:
        raise ImportError("mssql-python is required for Azure SQL backend.")

    max_retries = 5
    delay_seconds = 8
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = connect(_get_connection_string())
            conn.setautocommit(True)
            return conn
        except RuntimeError as e:
            # Azure SQL paused/timeout error detection (ODBC 258 or similar)
            if "Timeout error [258]" in str(e) or "timeout" in str(e).lower():
                print(f"[DB] Connection attempt {attempt} failed due to timeout/paused state. Retrying in {delay_seconds} seconds...")
                last_exception = e
                time.sleep(delay_seconds)
            else:
                raise
        except OSError as e:
            # Some drivers may raise OSError for network/timeout
            print(f"[DB] Connection attempt {attempt} failed due to OSError. Retrying in {delay_seconds} seconds...")
            last_exception = e
            time.sleep(delay_seconds)
    # All retries failed
    print(f"[DB] All {max_retries} connection attempts failed. Raising last exception.")
    raise last_exception if last_exception else RuntimeError("Failed to connect to Azure SQL after retries.")

def _seed_health_insurance_data_if_empty() -> None:
    """Populate the analytics table from CSV if it exists and the table is empty."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM [health_insurance_with_risk]")
        row_count = cursor.fetchone()[0]
        if row_count > 0:
            return  # Table already populated
        
        # Download CSV from Azure Blob Storage and populate table
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
    except Exception as e:
        # Log but don't fail to start up if seeding fails
        print(f"Warning: Could not seed health_insurance_with_risk data: {e}")
    finally:
        conn.close()

def ensure_schema_on_startup() -> None:
    """Ensure all required tables exist and seed analytics data if needed."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for statement in STARTUP_SCHEMA_STATEMENTS:
                cursor.execute(statement)
    finally:
        conn.close()
    # Try to seed the analytics data table if CSV exists
    _seed_health_insurance_data_if_empty()
