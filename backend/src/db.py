import os
import tempfile
from pathlib import Path
import time

from mssql_python import connect

CREATE_APPLICANTS_SQL = '''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='applicants' AND xtype='U')
BEGIN
    CREATE TABLE applicants (
        id INT IDENTITY(1,1) PRIMARY KEY,
        age INT NOT NULL,
        sex NVARCHAR(10) NOT NULL,
        bmi FLOAT NOT NULL,
        children INT NOT NULL,
        smoker NVARCHAR(10) NOT NULL,
        region NVARCHAR(50) NOT NULL,
        created_at NVARCHAR(32) NOT NULL,
        updated_at NVARCHAR(32) NOT NULL
    )
END
'''

CREATE_EVALUATIONS_SQL = '''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='applicant_evaluations' AND xtype='U')
BEGIN
    CREATE TABLE applicant_evaluations (
        id INT IDENTITY(1,1) PRIMARY KEY,
        evaluation_id NVARCHAR(64) NOT NULL UNIQUE,
        applicant_id INT NOT NULL,
        risk_category NVARCHAR(20) NOT NULL,
        model_version NVARCHAR(32) NOT NULL,
        created_at NVARCHAR(32) NOT NULL,
        FOREIGN KEY(applicant_id) REFERENCES applicants(id)
    )
END
'''

CREATE_TRAINING_RUNS_SQL = '''
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='training_runs' AND xtype='U')
BEGIN
    CREATE TABLE training_runs (
        run_id NVARCHAR(64) PRIMARY KEY,
        status NVARCHAR(32) NOT NULL,
        epochs INT,
        model_version NVARCHAR(32),
        classification_report NVARCHAR(MAX),
        started_at NVARCHAR(32),
        finished_at NVARCHAR(32),
        last_error NVARCHAR(255)
    )
END
'''

ALTER_TRAINING_RUNS_ADD_CLASSIFICATION_REPORT_SQL = '''
IF COL_LENGTH('training_runs', 'classification_report') IS NULL
BEGIN
    ALTER TABLE training_runs
    ADD classification_report NVARCHAR(MAX) NULL
END
'''


def get_db_backend():
    return "azuresql"


def _get_connection_string() -> str:
    connection_string = os.getenv("WSAA_DB_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("WSAA_DB_CONNECTION_STRING is required for Azure SQL backend.")
    return connection_string


def get_connection():
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
    # Lazy import avoids circular dependency between db <-> classifier/repositories.
    from src.health_insurance_risk_classifier import build_dataset, persist_dataset
    from src.storage.dao import StorageDAO
    
    conn = get_connection()
    try:
        # Check if table exists and is empty
        cursor = conn.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'health_insurance_with_risk'"
        )
        table_exists = cursor.fetchone()[0] > 0

        if table_exists:
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
        # Log but don't fail startup if seeding fails
        print(f"Warning: Could not seed health_insurance_with_risk data: {e}")
    finally:
        conn.close()


def ensure_schema_on_startup() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_APPLICANTS_SQL)
            cursor.execute(CREATE_EVALUATIONS_SQL)
            cursor.execute(CREATE_TRAINING_RUNS_SQL)
            cursor.execute(ALTER_TRAINING_RUNS_ADD_CLASSIFICATION_REPORT_SQL)
    finally:
        conn.close()
    
    # Try to seed the analytics data table if CSV exists
    _seed_health_insurance_data_if_empty()
