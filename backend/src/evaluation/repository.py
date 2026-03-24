import tempfile
from pathlib import Path

from src.health_insurance_risk_classifier import evaluate_risk_with_best_model
from src.storage.repository import StorageRepository


class EvaluationRepository:
    """DAO service for risk evaluation operations."""

    def __init__(self) -> None:
        self.storage = StorageRepository()

    def evaluate_risk(
        self,
        age: int,
        bmi: float,
        children: int,
        smoker: str,
        sex: str,
        region: str,
    ) -> tuple[str, str]:
        """
        Evaluate risk category for an applicant.

        Returns:
            Tuple of (risk_label, model_version)
        """
        # Download data and model from Azure Blob Storage to temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-eval-"))
        
        data_blob_name = "data/health_insurance_data.csv"
        model_blob_name = "models/risk_model.keras"
        
        data_path = temp_dir / "health_insurance_data.csv"
        model_path = temp_dir / "risk_model.keras"
        
        self.storage.download_file(data_blob_name, data_path)
        self.storage.download_file(model_blob_name, model_path)

        return evaluate_risk_with_best_model(
            age=age,
            bmi=bmi,
            children=children,
            smoker=smoker,
            sex=sex,
            region=region,
            data_path=data_path,
            model_path=model_path,
        )
