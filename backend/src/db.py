import os

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
        started_at NVARCHAR(32),
        finished_at NVARCHAR(32),
        last_error NVARCHAR(255)
    )
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

    conn = connect(_get_connection_string())
    conn.setautocommit(True)
    return conn

def _seed_health_insurance_data_if_empty() -> None:
    # Lazy import avoids circular dependency between db <-> classifier/repositories.
    from src.health_insurance_risk_classifier import build_dataset, persist_dataset
    from src.storage.data_resolver import DataFileResolver
    
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
        
        # Load CSV from local path or blob storage and populate table
        try:
            data_path = DataFileResolver().resolve()
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
    finally:
        conn.close()
    
    # Try to seed the analytics data table if CSV exists
    _seed_health_insurance_data_if_empty()


