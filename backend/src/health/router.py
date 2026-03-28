
from src.generated.server_stubs.apis.health_api_base import BaseHealthApi
from src.generated.server_stubs.models.health_response import HealthResponse
from fastapi import HTTPException
from src.db import get_connection

class HealthApiImpl(BaseHealthApi):
    async def get_health(self) -> HealthResponse:
        # Try to connect to the DB and run a trivial query
        try:
            conn = get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            finally:
                conn.close()
        except Exception as exc:
            # If DB is not reachable, return 503
            raise HTTPException(status_code=503, detail=f"Database not available: {exc}")
        return HealthResponse(
            status="ok",
            service="health-insurance-risk-classifier",
            version="0.1.0",
        )

