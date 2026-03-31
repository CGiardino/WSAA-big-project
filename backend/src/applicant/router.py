# FastAPI imports for API routing and dependency injection
from fastapi import APIRouter, Depends, HTTPException, Query, status

# Import DAO and schemas for applicant domain
from src.applicant.dao import ApplicantDAO
from src.generated.openapi_models import (
    ApplicantCreate,
    ApplicantCreateResponse,
    ApplicantListResponse,
    ApplicantResponse,
    ApplicantUpdate,
)
# Import OpenAPI-generated base classes and models (for type compatibility)
from src.generated.server_stubs.apis.applicants_api_base import BaseApplicantsApi
from src.generated.server_stubs.models.applicant_create import ApplicantCreate as StubApplicantCreate
from src.generated.server_stubs.models.applicant_create_response import (
    ApplicantCreateResponse as StubApplicantCreateResponse,
)
from src.generated.server_stubs.models.applicant_list_response import (
    ApplicantListResponse as StubApplicantListResponse,
)
from src.generated.server_stubs.models.applicant_response import ApplicantResponse as StubApplicantResponse
from src.generated.server_stubs.models.applicant_update import ApplicantUpdate as StubApplicantUpdate

# Define router for applicant endpoints
router = APIRouter(prefix="/v1/applicants", tags=["applicants"])

def get_applicant_dao() -> ApplicantDAO:
    """Dependency injector for ApplicantDAO."""
    return ApplicantDAO()

@router.post("", response_model=ApplicantCreateResponse, status_code=status.HTTP_201_CREATED)
def create_applicant(
    payload: ApplicantCreate,
    dao: ApplicantDAO = Depends(get_applicant_dao),
) -> ApplicantCreateResponse:
    """Create a new applicant. Returns the created applicant's details."""
    try:
        applicant = dao.create_applicant(payload)
    except ValueError as exc:
        # Return 400 if input is invalid
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApplicantCreateResponse.model_validate(applicant)

@router.get("", response_model=ApplicantListResponse)
def list_applicants(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    dao: ApplicantDAO = Depends(get_applicant_dao),
) -> ApplicantListResponse:
    """List applicants with pagination."""
    total = dao.count_applicants()
    items = [
        ApplicantResponse.model_validate(p)
        for p in dao.list_applicants(limit=limit, offset=offset)
    ]
    return ApplicantListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(items) < total,
    )



# Endpoint: Get a single applicant by ID
@router.get("/{applicant_id}", response_model=ApplicantResponse)
def get_applicant(
    applicant_id: int,
    dao: ApplicantDAO = Depends(get_applicant_dao),
) -> ApplicantResponse:
    """Retrieve a single applicant by ID."""
    applicant = dao.get_applicant(applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")
    return ApplicantResponse.model_validate(applicant)

# Endpoint: Update an applicant by ID
@router.put("/{applicant_id}", response_model=ApplicantResponse)
def update_applicant(
    applicant_id: int,
    payload: ApplicantUpdate,
    dao: ApplicantDAO = Depends(get_applicant_dao),
) -> ApplicantResponse:
    """Update an applicant's details."""
    try:
        applicant = dao.update_applicant(applicant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")
    return ApplicantResponse.model_validate(applicant)

# Endpoint: Delete an applicant by ID
@router.delete("/{applicant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_applicant(
    applicant_id: int,
    dao: ApplicantDAO = Depends(get_applicant_dao),
) -> None:
    """Delete an applicant by ID."""
    deleted = dao.delete_applicant(applicant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")

# Implementation of OpenAPI-generated Applicants API (for server stubs)
class ApplicantsApiImpl(BaseApplicantsApi):
    async def create_applicant(
        self,
        applicant_create: StubApplicantCreate,
    ) -> StubApplicantCreateResponse:
        # Validate and create applicant using main logic
        payload = ApplicantCreate.model_validate(applicant_create.model_dump())
        response = create_applicant(payload, get_applicant_dao())
        return StubApplicantCreateResponse.model_validate(response.model_dump())

    async def delete_applicant(self, applicant_id: int) -> None:
        # Delete applicant using main logic
        delete_applicant(applicant_id, get_applicant_dao())
        return None

    async def get_applicant(self, applicant_id: int) -> StubApplicantResponse:
        # Get applicant using main logic
        response = get_applicant(applicant_id, get_applicant_dao())
        return StubApplicantResponse.model_validate(response.model_dump())

    async def list_applicants(
        self,
        limit: int | None,
        offset: int | None,
    ) -> StubApplicantListResponse:
        # List applicants using main logic
        response = list_applicants(
            limit=limit if limit is not None else 25,
            offset=offset if offset is not None else 0,
            dao=get_applicant_dao(),
        )
        return StubApplicantListResponse.model_validate(response.model_dump())

    async def update_applicant(
        self,
        applicant_id: int,
        applicant_update: StubApplicantUpdate,
    ) -> StubApplicantResponse:
        # Update applicant using main logic
        payload = ApplicantUpdate.model_validate(applicant_update.model_dump())
        response = update_applicant(applicant_id, payload, get_applicant_dao())
        return StubApplicantResponse.model_validate(response.model_dump())
