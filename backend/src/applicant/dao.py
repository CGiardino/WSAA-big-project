"""Applicant persistence and risk evaluation orchestration DAO."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.generated.openapi_models import ApplicantCreate, ApplicantUpdate
from src.utils.db_utils import get_connection
from src.risk_classifier import evaluate_risk_with_best_model
from src.storage.dao import StorageDAO

DEFAULT_REGION = "southeast"


# Utility to extract enum value or raw value
def _enum_or_raw(value: object) -> object:
    return getattr(value, "value", value)


# Utility to convert DB row to applicant dict, handling both dict and tuple/row
def _row_to_applicant(row: dict | list) -> dict:
    def _pick(key: str, idx: int):
        if hasattr(row, "keys"):
            return row[key]
        return row[idx]

    applicant = {
        "id": _pick("id", 0),
        "age": _pick("age", 1),
        "sex": _pick("sex", 2),
        "bmi": _pick("bmi", 3),
        "children": _pick("children", 4),
        "smoker": _pick("smoker", 5),
        "created_at": _pick("created_at", 7),
        "updated_at": _pick("updated_at", 8),
    }

    evaluation_id = _pick("evaluation_id", 9)
    if evaluation_id is not None:
        applicant["evaluation"] = {
            "evaluation_id": evaluation_id,
            "risk_category": _pick("risk_category", 10),
            "model_version": _pick("model_version", 11),
            "created_at": _pick("evaluation_created_at", 12),
        }
    else:
        applicant["evaluation"] = None

    return applicant


class ApplicantDAO:
    """Encapsulates applicant CRUD plus evaluation side effects."""

    def __init__(self) -> None:
        pass

    def _connect(self):
        # Get a new DB connection
        return get_connection()

    def _evaluate_applicant_payload(self, payload: ApplicantCreate | ApplicantUpdate) -> tuple[str, str]:
        """Evaluate risk for applicant using latest model and data."""
        try:
            storage = StorageDAO()
            temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-applicant-"))
            data_blob_name = "data/health_insurance_data.csv"
            model_blob_name = "models/risk_model.keras"
            data_path = temp_dir / "health_insurance_data.csv"
            model_path = temp_dir / "risk_model.keras"
            storage.download_file(data_blob_name, data_path)
            storage.download_file(model_blob_name, model_path)
        except FileNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        # Evaluate risk using classifier
        return evaluate_risk_with_best_model(
            age=payload.age,
            bmi=payload.bmi,
            children=payload.children,
            smoker=str(_enum_or_raw(payload.smoker)),
            sex=str(_enum_or_raw(payload.sex)),
            region=DEFAULT_REGION,
            data_path=data_path,
            model_path=model_path,
        )

    def _insert_applicant_evaluation(
        self,
        conn,
        *,
        applicant_id: int,
        risk_label: str,
        model_version: str,
        created_at: str,
    ) -> str:
        """Insert a new applicant evaluation row and return its ID."""
        evaluation_id = str(uuid4())
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO applicant_evaluations (
                    evaluation_id,
                    applicant_id,
                    risk_category,
                    model_version,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (evaluation_id, applicant_id, risk_label, model_version, created_at),
            )
        return evaluation_id

    def list_applicants(self, *, limit: int, offset: int) -> list[dict]:
        """List applicants with their latest evaluation, paginated."""
        with self._connect() as conn:
            sql = """
            SELECT
                a.id,
                a.age,
                a.sex,
                a.bmi,
                a.children,
                a.smoker,
                a.region,
                a.created_at,
                a.updated_at,
                ae.evaluation_id,
                ae.risk_category,
                ae.model_version,
                ae.created_at AS evaluation_created_at
            FROM applicants a
            LEFT JOIN applicant_evaluations ae
                ON ae.id = (
                    SELECT MAX(id)
                    FROM applicant_evaluations
                    WHERE applicant_id = a.id
                )
            ORDER BY a.id DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            params = (offset, limit)
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [_row_to_applicant(row) for row in rows]

    def count_applicants(self) -> int:
        """Return total number of applicants."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM applicants")
                row = cursor.fetchone()
        if row is None:
            return 0
        return int(row[0])

    def get_applicant(self, applicant_id: int) -> dict | None:
        """Get a single applicant and their latest evaluation by ID."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        a.id,
                        a.age,
                        a.sex,
                        a.bmi,
                        a.children,
                        a.smoker,
                        a.region,
                        a.created_at,
                        a.updated_at,
                        ae.evaluation_id,
                        ae.risk_category,
                        ae.model_version,
                        ae.created_at AS evaluation_created_at
                    FROM applicants a
                    LEFT JOIN applicant_evaluations ae
                        ON ae.id = (
                            SELECT MAX(id)
                            FROM applicant_evaluations
                            WHERE applicant_id = a.id
                        )
                    WHERE a.id = ?
                    """,
                    (applicant_id,),
                )
                row = cursor.fetchone()
        return _row_to_applicant(row) if row else None

    def create_applicant(self, payload: ApplicantCreate) -> dict:
        """Create a new applicant and their initial evaluation."""
        risk_label, model_version = self._evaluate_applicant_payload(payload)
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            # Insert applicant row
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO applicants (age, sex, bmi, children, smoker, region, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.age,
                        _enum_or_raw(payload.sex),
                        payload.bmi,
                        payload.children,
                        _enum_or_raw(payload.smoker),
                        DEFAULT_REGION,
                        now,
                        now,
                    ),
                )
            # Get inserted applicant ID
            with conn.cursor() as cursor:
                cursor.execute("SELECT TOP 1 id FROM applicants ORDER BY id DESC")
                row = cursor.fetchone()
                applicant_id = int(row[0]) if row else None
            # Insert evaluation row
            evaluation_id = self._insert_applicant_evaluation(
                conn,
                applicant_id=int(applicant_id),
                risk_label=risk_label,
                model_version=model_version,
                created_at=now,
            )
            conn.commit()
        applicant = self.get_applicant(int(applicant_id))
        if applicant is None:
            raise RuntimeError("Failed to load created applicant")
        return {
            "applicant": applicant,
            "evaluation": {
                "evaluation_id": evaluation_id,
                "risk_category": risk_label,
                "model_version": model_version,
                "created_at": now,
            },
        }

    def update_applicant(self, applicant_id: int, payload: ApplicantUpdate) -> dict | None:
        """Update an applicant and add a new evaluation."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            # Check if applicant exists
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM applicants WHERE id = ?", (applicant_id,))
                exists = cursor.fetchone() is not None
            if not exists:
                conn.commit()
                return None
        risk_label, model_version = self._evaluate_applicant_payload(payload)
        with self._connect() as conn:
            # Update applicant row
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE applicants
                    SET age = ?, sex = ?, bmi = ?, children = ?, smoker = ?, region = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.age,
                        _enum_or_raw(payload.sex),
                        payload.bmi,
                        payload.children,
                        _enum_or_raw(payload.smoker),
                        DEFAULT_REGION,
                        now,
                        applicant_id,
                    ),
                )
                row_count = cursor.rowcount
            if row_count == 0:
                conn.commit()
                return None
            # Insert new evaluation row
            self._insert_applicant_evaluation(
                conn,
                applicant_id=applicant_id,
                risk_label=risk_label,
                model_version=model_version,
                created_at=now,
            )
            conn.commit()
        return self.get_applicant(applicant_id)

    def delete_applicant(self, applicant_id: int) -> bool:
        """Delete an applicant and all their evaluations."""
        with self._connect() as conn:
            # Delete evaluations first (FK constraint)
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM applicant_evaluations WHERE applicant_id = ?", (applicant_id,)
                )
            # Delete applicant row
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM applicants WHERE id = ?", (applicant_id,))
                row_count = cursor.rowcount
            conn.commit()
            return row_count > 0

