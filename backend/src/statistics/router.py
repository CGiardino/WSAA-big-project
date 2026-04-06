"""HTTP routing layer for summary statistics and plot retrieval."""

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
from src.statistics.dao import StatisticsDAO

router = APIRouter(prefix="/v1", tags=["statistics"])


def get_statistics_dao() -> StatisticsDAO:
    return StatisticsDAO()


@router.get("/statistics/summary", response_model=StatisticsSummaryResponse)
def get_statistics_summary(
    dao: StatisticsDAO = Depends(get_statistics_dao),
) -> StatisticsSummaryResponse:
    summary = dao.get_summary_statistics()

    # Keep risk labels ordered/stable for frontend charts.
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
    dao: StatisticsDAO = Depends(get_statistics_dao),
) -> StatisticsPlotsResponse:
    items = [StatisticsPlotItem(**item) for item in dao.list_plots()]
    return StatisticsPlotsResponse(items=items)


@router.get("/statistics/plots/{plot_name}")
def get_statistics_plot(
    plot_name: str,
    dao: StatisticsDAO = Depends(get_statistics_dao),
) -> FileResponse:
    # The DAO validates file names and downloads the blob to a temp file path.
    plot_path = dao.get_plot_path(plot_name)
    if not plot_path.exists():
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(plot_path)


class StatisticsApiImpl(BaseStatisticsApi):
    """Adapter that connects generated statistics stubs to handlers."""

    async def get_statistics_summary(self) -> StubStatisticsSummaryResponse:
        response = get_statistics_summary(get_statistics_dao())
        return StubStatisticsSummaryResponse.model_validate(response.model_dump())

    async def list_statistics_plots(self) -> StubStatisticsPlotsResponse:
        response = list_statistics_plots(get_statistics_dao())
        return StubStatisticsPlotsResponse.model_validate(response.model_dump())

    async def get_statistics_plot(self, plot_name: str) -> FileResponse:
        return get_statistics_plot(plot_name, get_statistics_dao())
