from src.generated.server_stubs.apis.health_api_base import BaseHealthApi
from src.generated.server_stubs.models.health_response import HealthResponse


class HealthApiImpl(BaseHealthApi):
    async def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="health-insurance-risk-classifier",
            version="0.1.0",
        )

