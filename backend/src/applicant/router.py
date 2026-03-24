from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.applicant.repository import ApplicantRepository
from src.applicant.schemas import (
    ApplicantCreate,
    ApplicantCreateResponse,
    ApplicantListResponse,
    ApplicantResponse,
    ApplicantUpdate,
)

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

