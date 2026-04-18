"""FastAPI application bootstrap and router registration."""

from contextlib import asynccontextmanager  # For FastAPI lifespan events
import os

from fastapi import Depends, FastAPI  # Main FastAPI framework
from fastapi.middleware.cors import CORSMiddleware

# Import domain routers (these will be registered with the FastAPI app)
import src.applicant.router
import src.evaluation.router
import src.health.router
import src.metadata.router
import src.statistics.router
import src.training.router

from src.startup.bootstrap import ensure_startup_state
# Import OpenAPI-generated routers for each API domain
from src.generated.server_stubs.apis.applicants_api import router as applicants_router
from src.generated.server_stubs.apis.evaluations_api import router as evaluations_router
from src.generated.server_stubs.apis.health_api import router as health_router
from src.generated.server_stubs.apis.metadata_api import router as metadata_router
from src.generated.server_stubs.apis.statistics_api import router as statistics_router
from src.generated.server_stubs.apis.training_api import router as training_router
from src.auth.dependencies import require_access_token


def _get_cors_origins() -> list[str]:
    """Parse allowed CORS origins from WSAA_CORS_ORIGINS only."""
    configured = os.getenv("WSAA_CORS_ORIGINS", "")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup tasks (e.g., DB schema check) before serving requests."""
    # Ensure SQL tables/migrations are ready before the first request is handled.
    ensure_startup_state()
    yield

# Create FastAPI app instance with metadata and lifespan handler
app = FastAPI(
    title="Health Insurance Risk Classifier API",
    version="0.1.0",
    description="API for classifying health insurance risk based on applicant data, with endpoints for managing applicants, evaluating risk, retrieving model metadata, and running training jobs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generated routers expose the OpenAPI contract endpoints.
# Register all routers for API endpoints
app.include_router(health_router)
secured_route_dependencies = [Depends(require_access_token)]
app.include_router(applicants_router, dependencies=secured_route_dependencies)
app.include_router(evaluations_router, dependencies=secured_route_dependencies)
app.include_router(metadata_router, dependencies=secured_route_dependencies)
app.include_router(statistics_router, dependencies=secured_route_dependencies)
app.include_router(training_router, dependencies=secured_route_dependencies)
