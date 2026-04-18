"""DAO for persisting and querying training run state."""

from __future__ import annotations

from src.utils.db_utils import get_connection

from datetime import datetime
from typing import Any


def _connect():
    return get_connection()


class TrainingDAO:
    """Handles training run state and dataset retrieval queries."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _row_to_status_dict(row: Any) -> dict[str, Any]:
        columns = [
            "run_id",
            "status",
            "epochs",
            "model_version",
            "classification_report",
            "started_at",
            "finished_at",
            "last_error",
        ]
        if hasattr(row, "keys"):
            # Support dict-like row objects from different SQL drivers.
            return {col: row[col] for col in columns}
        return {col: row[idx] for idx, col in enumerate(columns)}

    def save_run_status(self, run_status: dict[str, Any]) -> None:
        def _as_db_timestamp(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        with _connect() as conn:
            params = (
                str(run_status.get("run_id")),
                str(run_status.get("status")),
                run_status.get("epochs"),
                run_status.get("model_version"),
                run_status.get("classification_report"),
                _as_db_timestamp(run_status.get("started_at")),
                _as_db_timestamp(run_status.get("finished_at")),
                run_status.get("last_error"),
            )

            # Attempt UPDATE
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE training_runs
                    SET
                        status = ?,
                        epochs = ?,
                        model_version = ?,
                        classification_report = ?,
                        started_at = ?,
                        finished_at = ?,
                        last_error = ?
                    WHERE run_id = ?
                    """,
                    (
                        params[1],
                        params[2],
                        params[3],
                        params[4],
                        params[5],
                        params[6],
                        params[7],
                        params[0],
                    ),
                )
                row_count = cursor.rowcount
            
            # If UPDATE didn't match any rows, do INSERT
            if row_count == 0:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO training_runs (
                            run_id,
                            status,
                            epochs,
                            model_version,
                            classification_report,
                            started_at,
                            finished_at,
                            last_error
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        params,
                    )
            conn.commit()

    def get_latest_run_status(self) -> dict[str, Any] | None:
        with _connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP 1 run_id, status, epochs, model_version, classification_report, started_at, finished_at, last_error
                    FROM training_runs
                    ORDER BY started_at DESC
                    """
                )
                row = cursor.fetchone()
        return self._row_to_status_dict(row) if row is not None else None

    def get_run_status_by_id(self, run_id: str) -> dict[str, Any] | None:
        with _connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP 1 run_id, status, epochs, model_version, classification_report, started_at, finished_at, last_error
                    FROM training_runs
                    WHERE run_id = ?
                    """,
                    (run_id,),
                )
                row = cursor.fetchone()
        return self._row_to_status_dict(row) if row is not None else None

    def list_training_dataset(
        self, limit: int = 25, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Fetch training dataset rows from health_insurance_with_risk table.
        
        Returns:
            Tuple of (rows_list, total_count)
        """
        rows = []
        total = 0

        with _connect() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COLUMN_NAME
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = 'health_insurance_with_risk'
                        """
                    )
                    column_rows = cursor.fetchall()

                table_columns = {str(row[0]) for row in column_rows}
                if not table_columns:
                    return [], 0

                age_column = "age_original" if "age_original" in table_columns else "age"
                bmi_column = "bmi_original" if "bmi_original" in table_columns else "bmi"
                children_column = (
                    "children_original"
                    if "children_original" in table_columns
                    else "children"
                )

                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS total FROM health_insurance_with_risk")
                    total_row = cursor.fetchone()

                total = int(total_row[0] if total_row is not None else 0)

                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT
                            [{age_column}] AS age,
                            [sex],
                            [{bmi_column}] AS bmi,
                            [{children_column}] AS children,
                            [smoker],
                            [charges_original],
                            [risk_category]
                        FROM [health_insurance_with_risk]
                        ORDER BY [{age_column}]
                        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
                        """,
                        (offset, limit),
                    )
                    rows = cursor.fetchall()
            except Exception:
                # Keep the endpoint resilient when analytics table is not ready yet.
                return [], 0

        result = []
        for row in rows:
            row_data = {
                "age": row[0],
                "sex": row[1],
                "bmi": row[2],
                "children": row[3],
                "smoker": row[4],
                "charges_original": row[5],
                "risk_category": row[6],
            }
            for key in ("age", "children"):
                value = row_data.get(key)
                if value is not None:
                    # Normalize possible FLOAT/DECIMAL SQL values to API ints.
                    row_data[key] = int(round(float(value)))
            result.append(row_data)

        return result, total

    def load_training_data(self) -> tuple:
        """
        Load feature-selected data for neural network training.
        
        Returns:
            Tuple of (DataFrame with features and risk_category for training, column names)
        """
        import pandas as pd

        feature_selection_query = """
        SELECT age, bmi, children, sex_encoded, smoker_encoded,
               region_northeast, region_northwest, region_southeast, region_southwest,
               charges_original,
               risk_category
        FROM health_insurance_with_risk
        """

        with _connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(feature_selection_query)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description or []]

        df = pd.DataFrame.from_records([tuple(row) for row in rows], columns=columns)
        return df

