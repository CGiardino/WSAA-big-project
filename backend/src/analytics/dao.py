"""Analytics and training data persistence repository.

Encapsulates all database operations for the health insurance risk classifier workflow,
including dataset persistence, analysis data loading, and training data queries.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.db import get_connection


class AnalyticsRepository:
    """DAO service for analytics workflow database operations."""

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

    def load_training_data(self) -> pd.DataFrame:
        """
        Load feature-selected data for neural network training.
        
        Returns:
            DataFrame with features and risk_category for training
        """
        feature_selection_query = """
        SELECT age, bmi, children, sex_encoded, smoker_encoded,
               region_northeast, region_northwest, region_southeast, region_southwest,
               charges_original,
               risk_category
        FROM health_insurance_with_risk
        """

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(feature_selection_query)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description or []]

            df = pd.DataFrame.from_records([tuple(row) for row in rows], columns=columns)
            return df


