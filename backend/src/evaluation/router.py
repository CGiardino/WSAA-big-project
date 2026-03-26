from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from src.generated.openapi_models import (
    RiskCategory,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
)
from src.evaluation.repository import EvaluationRepository

router = APIRouter(prefix="/v1", tags=["evaluations"])


def get_evaluation_repository() -> EvaluationRepository:
    return EvaluationRepository()


@router.post("/evaluations/risk", response_model=RiskEvaluationResponse)
def create_risk_evaluation(
    payload: RiskEvaluationRequest,
    repository: EvaluationRepository = Depends(get_evaluation_repository),
) -> RiskEvaluationResponse:
    try:
        risk_label, model_version = repository.evaluate_risk(
            age=payload.age,
            bmi=payload.bmi,
            children=payload.children,
            smoker=payload.smoker.value,
            sex=payload.sex.value,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    now = datetime.now(UTC)
    return RiskEvaluationResponse(
        evaluation_id=uuid4(),
        risk_category=RiskCategory(risk_label),
        model_version=model_version,
        created_at=now,
    )



