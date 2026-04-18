"""DAO for statistics aggregation and plot artifact lookup."""

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.db_utils import get_connection
from src.storage.dao import StorageDAO

PLOTS_BLOB_PREFIX = "plots"


class StatisticsDAO:
    """DAO service for statistics and plot data operations."""

    def __init__(self) -> None:
        self.storage = StorageDAO()

    def get_summary_statistics(self) -> dict[str, Any]:
        """
        Fetch summary statistics from health_insurance_with_risk table.
        
        Returns:
            Dictionary with total_records, avg_age, avg_bmi, avg_charges, risk_distribution
        """
        live_summary: dict[str, Any] | None = None
        avg_charges = 0.0

        # Real-time summary from operational applicant/evaluation tables.
        with get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) AS total_records,
                            COALESCE(AVG(CAST(a.age AS FLOAT)), 0.0) AS avg_age,
                            COALESCE(AVG(CAST(a.bmi AS FLOAT)), 0.0) AS avg_bmi
                        FROM applicants a
                        """
                    )
                    row = cursor.fetchone()

                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        -- For each applicant, keep only the most recent evaluation row.
                        WITH latest_eval AS (
                            SELECT applicant_id, risk_category,
                                   ROW_NUMBER() OVER (PARTITION BY applicant_id ORDER BY id DESC) AS rn
                            FROM applicant_evaluations
                        )
                        -- Count applicants by current (latest) risk category.
                        SELECT risk_category, COUNT(*)
                        FROM latest_eval
                        WHERE rn = 1
                        GROUP BY risk_category
                        """
                    )
                    risk_rows = cursor.fetchall()

                risk_counts = {"Low": 0, "Medium": 0, "High": 0}
                for risk_row in risk_rows:
                    label = str(risk_row[0])
                    if label in risk_counts:
                        risk_counts[label] = int(risk_row[1])

                live_summary = {
                    "total_records": int(row[0] if row is not None else 0),
                    "avg_age": float(row[1] if row is not None else 0.0),
                    "avg_bmi": float(row[2] if row is not None else 0.0),
                    "risk_distribution": risk_counts,
                }
            except Exception:
                live_summary = None

        # Keep avg_charges populated from analytics dataset when available.
        with get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COALESCE(AVG(CAST([charges_original] AS FLOAT)), 0.0) AS avg_charges
                        FROM [health_insurance_with_risk]
                        """
                    )
                    avg_row = cursor.fetchone()
                avg_charges = float(avg_row[0] if avg_row is not None else 0.0)
            except Exception:
                avg_charges = 0.0

        if live_summary is None:
            return {
                "total_records": 0,
                "avg_age": 0.0,
                "avg_bmi": 0.0,
                "avg_charges": avg_charges,
                "risk_distribution": {"Low": 0, "Medium": 0, "High": 0},
            }

        live_summary["avg_charges"] = avg_charges
        return live_summary

    def list_plots(self) -> list[dict[str, str]]:
        """
        List all available plot files in plots directory.
        
        Returns:
            List of dicts with 'name' and 'url' keys
        """
        ALLOWED_PLOT_SUFFIXES = {".png", ".jpg", ".jpeg"}

        items = []
        plot_blobs = sorted(self.storage.list_files(starts_with=f"{PLOTS_BLOB_PREFIX}/"))
        for blob_name in plot_blobs:
            # Public plot URLs are based on filename, not full blob key.
            file_name = Path(blob_name).name
            if Path(file_name).suffix.lower() not in ALLOWED_PLOT_SUFFIXES:
                continue
            items.append({
                "name": file_name,
                "url": f"/v1/statistics/plots/{file_name}",
            })

        return items

    def get_plot_path(self, plot_name: str) -> Path:
        """
        Get the full path to a plot file if it exists and is valid.
        
        Raises:
            ValueError: If plot_name is invalid or file does not exist
        """
        ALLOWED_PLOT_SUFFIXES = {".png", ".jpg", ".jpeg"}

        # Prevent directory traversal
        if Path(plot_name).name != plot_name:
            raise ValueError("Invalid plot name")

        suffix = Path(plot_name).suffix.lower()
        if suffix not in ALLOWED_PLOT_SUFFIXES:
            raise ValueError("Plot not found")

        blob_name = f"{PLOTS_BLOB_PREFIX}/{plot_name}"
        if not self.storage.exists(blob_name):
            raise ValueError("Plot not found")

        temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-plot-"))
        plot_path = temp_dir / plot_name
        # Download to temp storage so FastAPI can stream via FileResponse.
        self.storage.download_file(blob_name, plot_path)

        return plot_path

    @staticmethod
    def _column_sql_type(series: pd.Series) -> str:
        """Determine SQL column type based on pandas dtype."""
        if pd.api.types.is_integer_dtype(series.dtype):
            return "INT"
        if pd.api.types.is_float_dtype(series.dtype):
            return "FLOAT"
        return "NVARCHAR(255)"

    @staticmethod
    def _to_db_value(value):
        """Convert pandas/numpy types to database-compatible values."""
        if pd.isna(value):
            return None
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        return value

    def persist_dataset(self, df: pd.DataFrame) -> None:
        """
        Drop and recreate health_insurance_with_risk table, populate with DataFrame.
        
        Args:
            df: DataFrame with processed health insurance data including risk_category
        """
        columns = list(df.columns)
        column_defs = ", ".join(f"[{col}] {self._column_sql_type(df[col])} NULL" for col in columns)
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = (
            f"INSERT INTO health_insurance_with_risk ({', '.join(f'[{col}]' for col in columns)}) "
            f"VALUES ({placeholders})"
        )

        with get_connection() as conn:
            # Drop existing table
            with conn.cursor() as cursor:
                cursor.execute(
                    "IF OBJECT_ID('health_insurance_with_risk', 'U') IS NOT NULL DROP TABLE health_insurance_with_risk"
                )

            # Create table with schema from DataFrame
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE TABLE health_insurance_with_risk ({column_defs})")

            # Insert data
            rows = [tuple(self._to_db_value(v) for v in row) for row in df.itertuples(index=False, name=None)]
            if rows:
                with conn.cursor() as cursor:
                    cursor.executemany(insert_sql, rows)

            conn.commit()

    def run_sql_checks(self) -> dict:
        """
        Execute diagnostic SQL queries on health_insurance_with_risk table.
        
        Returns:
            Dictionary with results of diagnostic queries
        """
        results = {}

        with get_connection() as conn:
            # Total records count
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total_records FROM health_insurance_with_risk")
                row = cursor.fetchone()
                results["total_records"] = int(row[0]) if row else 0

            # Risk category distribution
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT risk_category, COUNT(*) as count
                    FROM health_insurance_with_risk
                    GROUP BY risk_category
                    ORDER BY count DESC
                    """
                )
                rows = cursor.fetchall()
                results["risk_distribution"] = [
                    {"risk_category": str(row[0]), "count": int(row[1])} for row in rows
                ]

            # Average age and BMI by risk category
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT risk_category,
                           AVG(age) as avg_age,
                           AVG(bmi) as avg_bmi,
                           COUNT(*) as count
                    FROM health_insurance_with_risk
                    GROUP BY risk_category
                    """
                )
                rows = cursor.fetchall()
                results["stats_by_risk"] = [
                    {
                        "risk_category": str(row[0]),
                        "avg_age": float(row[1]) if row[1] is not None else 0.0,
                        "avg_bmi": float(row[2]) if row[2] is not None else 0.0,
                        "count": int(row[3]),
                    }
                    for row in rows
                ]

        return results

    def load_analysis_data(self) -> pd.DataFrame:
        """
        Load complete health_insurance_with_risk table for analysis.
        
        Returns:
            DataFrame with all analysis data
        """
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM health_insurance_with_risk")
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description or []]

            df = pd.DataFrame.from_records([tuple(row) for row in rows], columns=columns)
            return df

