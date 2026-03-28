from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from src.generated.openapi_models import (
    RiskCategory,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
)
from src.generated.server_stubs.apis.evaluations_api_base import BaseEvaluationsApi
from src.generated.server_stubs.models.risk_evaluation_request import (
    RiskEvaluationRequest as StubRiskEvaluationRequest,
)
from src.generated.server_stubs.models.risk_evaluation_response import (
    RiskEvaluationResponse as StubRiskEvaluationResponse,
)
from src.evaluation.dao import EvaluationDAO

router = APIRouter(prefix="/v1", tags=["evaluations"])


def get_evaluation_dao() -> EvaluationDAO:
    return EvaluationDAO()


@router.post("/evaluations/risk", response_model=RiskEvaluationResponse)
def create_risk_evaluation(
    payload: RiskEvaluationRequest,
    dao: EvaluationDAO = Depends(get_evaluation_dao),
) -> RiskEvaluationResponse:
    try:
        risk_label, model_version = dao.evaluate_risk(
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


class EvaluationsApiImpl(BaseEvaluationsApi):
    async def create_risk_evaluation(
        self,
        risk_evaluation_request: StubRiskEvaluationRequest,
    ) -> StubRiskEvaluationResponse:
        payload = RiskEvaluationRequest.model_validate(risk_evaluation_request.model_dump())
        response = create_risk_evaluation(payload, get_evaluation_dao())
        return StubRiskEvaluationResponse.model_validate(response.model_dump())



