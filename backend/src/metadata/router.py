from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from src.generated.openapi_models import (
    ModelAvailabilityResponse,
    ModelMetadataResponse,
    RiskCategory,
)
from src.generated.server_stubs.apis.metadata_api_base import BaseMetadataApi
from src.generated.server_stubs.models.model_availability_response import (
    ModelAvailabilityResponse as StubModelAvailabilityResponse,
)
from src.generated.server_stubs.models.model_metadata_response import (
    ModelMetadataResponse as StubModelMetadataResponse,
)
from src.metadata.dao import MetadataDAO

router = APIRouter(prefix="/v1", tags=["metadata"])


def get_metadata_dao() -> MetadataDAO:
    return MetadataDAO()


@router.get("/metadata/model", response_model=ModelMetadataResponse)
def get_model_metadata(
    dao: MetadataDAO = Depends(get_metadata_dao),
) -> ModelMetadataResponse:
    try:
        model_version = dao.get_active_model_version()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ModelMetadataResponse(
        model_name="health-insurance-risk-classifier",
        model_version=model_version,
        labels=[RiskCategory.Low, RiskCategory.Medium, RiskCategory.High],
        features=["age", "sex", "bmi", "children", "smoker"],
        updated_at=datetime.now(UTC),
    )


@router.get("/metadata/model/availability", response_model=ModelAvailabilityResponse)
def get_model_availability(
    dao: MetadataDAO = Depends(get_metadata_dao),
) -> ModelAvailabilityResponse:
    try:
        artifact_exists = dao.check_artifact_exists()
        artifact_loadable = dao.check_artifact_loadable()
        active_version, active_path = dao.get_active_model_info()
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


class MetadataApiImpl(BaseMetadataApi):
    async def get_model_availability(self) -> StubModelAvailabilityResponse:
        response = get_model_availability(get_metadata_dao())
        return StubModelAvailabilityResponse.model_validate(response.model_dump())

    async def get_model_metadata(self) -> StubModelMetadataResponse:
        response = get_model_metadata(get_metadata_dao())
        return StubModelMetadataResponse.model_validate(response.model_dump())

