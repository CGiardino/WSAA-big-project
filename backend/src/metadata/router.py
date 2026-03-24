from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.generated.openapi_models import (
    ModelAvailabilityResponse,
    ModelMetadataResponse,
    RiskCategory,
)
from src.metadata.repository import MetadataRepository

router = APIRouter(prefix="/v1", tags=["metadata"])


def get_metadata_repository() -> MetadataRepository:
    return MetadataRepository()


@router.get("/metadata/model", response_model=ModelMetadataResponse)
def get_model_metadata(
    repository: MetadataRepository = Depends(get_metadata_repository),
) -> ModelMetadataResponse:
    try:
        model_version = repository.get_active_model_version()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelMetadataResponse(
        model_name="health-insurance-risk-classifier",
        model_version=model_version,
        labels=[RiskCategory.Low, RiskCategory.Medium, RiskCategory.High],
        features=["age", "sex", "bmi", "children", "smoker", "region", "charges_original"],
        updated_at=datetime.now(UTC),
    )


@router.get("/metadata/model/availability", response_model=ModelAvailabilityResponse)
def get_model_availability(
    repository: MetadataRepository = Depends(get_metadata_repository),
) -> ModelAvailabilityResponse:
    try:
        artifact_exists = repository.check_artifact_exists()
        artifact_loadable = repository.check_artifact_loadable()
        active_version, active_path = repository.get_active_model_info()
    except (FileNotFoundError, ValueError):
        artifact_exists = False
        artifact_loadable = False
        active_version = None
        active_path = None

    return ModelAvailabilityResponse(
        artifact_exists=artifact_exists,
        artifact_loadable=artifact_loadable,
        active_model_version=active_version,
        active_model_path=str(active_path) if active_path is not None else None,
    )


