from pathlib import Path
from typing import Optional

from src.health_insurance_risk_classifier import get_active_nn_model_info


class MetadataRepository:
    """DAO service for model metadata and availability operations."""

    def __init__(self) -> None:
        pass

    def get_active_model_version(self) -> str:
        """Get the active model version from Azure model registry."""
        active_version, _ = get_active_nn_model_info()
        if not active_version:
            raise ValueError("Active model not available")
        return active_version

    def get_active_model_info(self) -> tuple[Optional[str], Optional[Path]]:
        """
        Get active model version and path.

        Returns:
            Tuple of (active_version, active_model_path)
        """
        return get_active_nn_model_info()

    def check_artifact_exists(self) -> bool:
        """Check if an artifact exists at the model path."""
        _, active_path = self.get_active_model_info()
        return active_path is not None

    def check_artifact_loadable(self) -> bool:
        """Check if the model artifact can be loaded by TensorFlow/Keras."""
        _, active_path = self.get_active_model_info()
        if active_path is None:
            return False

        try:
            from tensorflow import keras
            keras.models.load_model(active_path)
            return True
        except Exception:
            return False

