from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.generated.openapi_models import (
    RiskCategory,
    StatisticsPlotItem,
    StatisticsPlotsResponse,
    StatisticsRiskCount,
    StatisticsSummaryResponse,
)
from src.generated.server_stubs.apis.statistics_api_base import BaseStatisticsApi
from src.generated.server_stubs.models.statistics_plots_response import (
    StatisticsPlotsResponse as StubStatisticsPlotsResponse,
)
from src.generated.server_stubs.models.statistics_summary_response import (
    StatisticsSummaryResponse as StubStatisticsSummaryResponse,
)
from src.statistics.repository import StatisticsRepository

router = APIRouter(prefix="/v1", tags=["statistics"])


def get_statistics_repository() -> StatisticsRepository:
    return StatisticsRepository()


@router.get("/statistics/summary", response_model=StatisticsSummaryResponse)
def get_statistics_summary(
    repository: StatisticsRepository = Depends(get_statistics_repository),
) -> StatisticsSummaryResponse:
    summary = repository.get_summary_statistics()

    risk_distribution = [
        StatisticsRiskCount(
            risk_category=RiskCategory.Low, count=summary["risk_distribution"]["Low"]
        ),
        StatisticsRiskCount(
            risk_category=RiskCategory.Medium, count=summary["risk_distribution"]["Medium"]
        ),
        StatisticsRiskCount(
            risk_category=RiskCategory.High, count=summary["risk_distribution"]["High"]
        ),
    ]

    return StatisticsSummaryResponse(
        total_records=summary["total_records"],
        avg_age=summary["avg_age"],
        avg_bmi=summary["avg_bmi"],
        avg_charges=summary["avg_charges"],
        risk_distribution=risk_distribution,
    )


@router.get("/statistics/plots", response_model=StatisticsPlotsResponse)
def list_statistics_plots(
    repository: StatisticsRepository = Depends(get_statistics_repository),
) -> StatisticsPlotsResponse:
    plots = repository.list_plots()
    items = [StatisticsPlotItem(name=p["name"], url=p["url"]) for p in plots]
    return StatisticsPlotsResponse(items=items)


@router.get("/statistics/plots/{plot_name}")
def get_statistics_plot(
    plot_name: str,
    repository: StatisticsRepository = Depends(get_statistics_repository),
) -> FileResponse:
    try:
        plot_path = repository.get_plot_path(plot_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return FileResponse(plot_path)


class StatisticsApiImpl(BaseStatisticsApi):
    async def get_statistics_plot(self, plot_name: str) -> bytes:
        return get_statistics_plot(plot_name, get_statistics_repository())  # type: ignore[return-value]

    async def get_statistics_summary(self) -> StubStatisticsSummaryResponse:
        response = get_statistics_summary(get_statistics_repository())
        return StubStatisticsSummaryResponse.model_validate(response.model_dump())

    async def list_statistics_plots(self) -> StubStatisticsPlotsResponse:
        response = list_statistics_plots(get_statistics_repository())
        return StubStatisticsPlotsResponse.model_validate(response.model_dump())


