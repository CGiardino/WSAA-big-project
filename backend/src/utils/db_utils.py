"""Database connection helpers."""


# Standard library imports
import os
import time

# External dependency for Azure SQL connection
from mssql_python import connect


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

