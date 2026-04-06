"""Data-access service for single-request risk evaluations."""

import tempfile
from pathlib import Path

from src.health_insurance_risk_classifier import evaluate_risk_with_best_model
from src.storage.dao import StorageDAO


class EvaluationDAO:
    """DAO service for risk evaluation operations."""

    _DEFAULT_REGION = "southeast"

    def __init__(self) -> None:
        # Reuse one storage client per DAO instance.
        self.storage = StorageDAO()

    def evaluate_risk(
        self,
        age: int,
        bmi: float,
        children: int,
        smoker: str,
        sex: str,
    ) -> tuple[str, str]:
        """
        Evaluate risk category for an applicant.

        Returns:
            Tuple of (risk_label, model_version)
        """
        # Download model artifacts to a per-request temp directory.
        temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-eval-"))
        
        data_blob_name = "data/health_insurance_data.csv"
        model_blob_name = "models/risk_model.keras"
        
        data_path = temp_dir / "health_insurance_data.csv"
        model_path = temp_dir / "risk_model.keras"
        
        # Materialize dataset/model locally because TensorFlow expects file paths.
        self.storage.download_file(data_blob_name, data_path)
        self.storage.download_file(model_blob_name, model_path)

        return evaluate_risk_with_best_model(
            age=age,
            bmi=bmi,
            children=children,
            smoker=smoker,
            sex=sex,
            region=self._DEFAULT_REGION,
            data_path=data_path,
            model_path=model_path,
        )
