from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.applicant.repository import ApplicantRepository
from src.applicant.schemas import (
    ApplicantCreate,
    ApplicantCreateResponse,
    ApplicantListResponse,
    ApplicantResponse,
    ApplicantUpdate,
)
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

router = APIRouter(prefix="/v1/applicants", tags=["applicants"])


def get_applicant_repository() -> ApplicantRepository:
    return ApplicantRepository()


@router.post("", response_model=ApplicantCreateResponse, status_code=status.HTTP_201_CREATED)
def create_applicant(
    payload: ApplicantCreate,
    repository: ApplicantRepository = Depends(get_applicant_repository),
) -> ApplicantCreateResponse:
    try:
        applicant = repository.create_applicant(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApplicantCreateResponse.model_validate(applicant)


@router.get("", response_model=ApplicantListResponse)
def list_applicants(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repository: ApplicantRepository = Depends(get_applicant_repository),
) -> ApplicantListResponse:
    total = repository.count_applicants()
    items = [
        ApplicantResponse.model_validate(p)
        for p in repository.list_applicants(limit=limit, offset=offset)
    ]
    return ApplicantListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(items) < total,
    )


@router.get("/{applicant_id}", response_model=ApplicantResponse)
def get_applicant(
    applicant_id: int,
    repository: ApplicantRepository = Depends(get_applicant_repository),
) -> ApplicantResponse:
    applicant = repository.get_applicant(applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")
    return ApplicantResponse.model_validate(applicant)


@router.put("/{applicant_id}", response_model=ApplicantResponse)
def update_applicant(
    applicant_id: int,
    payload: ApplicantUpdate,
    repository: ApplicantRepository = Depends(get_applicant_repository),
) -> ApplicantResponse:
    try:
        applicant = repository.update_applicant(applicant_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")
    return ApplicantResponse.model_validate(applicant)


@router.delete("/{applicant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_applicant(
    applicant_id: int,
    repository: ApplicantRepository = Depends(get_applicant_repository),
) -> None:
    deleted = repository.delete_applicant(applicant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")


class ApplicantsApiImpl(BaseApplicantsApi):
    async def create_applicant(
        self,
        applicant_create: StubApplicantCreate,
    ) -> StubApplicantCreateResponse:
        payload = ApplicantCreate.model_validate(applicant_create.model_dump())
        response = create_applicant(payload, get_applicant_repository())
        return StubApplicantCreateResponse.model_validate(response.model_dump())

    async def delete_applicant(self, applicant_id: int) -> None:
        delete_applicant(applicant_id, get_applicant_repository())
        return None

    async def get_applicant(self, applicant_id: int) -> StubApplicantResponse:
        response = get_applicant(applicant_id, get_applicant_repository())
        return StubApplicantResponse.model_validate(response.model_dump())

    async def list_applicants(
        self,
        limit: int | None,
        offset: int | None,
    ) -> StubApplicantListResponse:
        response = list_applicants(
            limit=limit if limit is not None else 25,
            offset=offset if offset is not None else 0,
            repository=get_applicant_repository(),
        )
        return StubApplicantListResponse.model_validate(response.model_dump())

    async def update_applicant(
        self,
        applicant_id: int,
        applicant_update: StubApplicantUpdate,
    ) -> StubApplicantResponse:
        payload = ApplicantUpdate.model_validate(applicant_update.model_dump())
        response = update_applicant(applicant_id, payload, get_applicant_repository())
        return StubApplicantResponse.model_validate(response.model_dump())


