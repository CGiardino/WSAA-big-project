from contextlib import asynccontextmanager  # For FastAPI lifespan events

from fastapi import FastAPI  # Main FastAPI framework

# Import routers to register endpoints (side-effect imports)
import src.applicant.router
import src.evaluation.router
import src.health.router
import src.metadata.router
import src.statistics.router
import src.training.router

from src.db import ensure_schema_on_startup  # Ensures DB schema is ready
# Import OpenAPI-generated routers for each API domain
from src.generated.server_stubs.apis.applicants_api import router as applicants_router
from src.generated.server_stubs.apis.evaluations_api import router as evaluations_router
from src.generated.server_stubs.apis.health_api import router as health_router
from src.generated.server_stubs.apis.metadata_api import router as metadata_router
from src.generated.server_stubs.apis.statistics_api import router as statistics_router
from src.generated.server_stubs.apis.training_api import router as training_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup tasks (e.g., DB schema check) before serving requests."""
    ensure_schema_on_startup()
    yield

# Create FastAPI app instance with metadata and lifespan handler
app = FastAPI(
    title="Health Insurance Risk Classifier API",
    version="0.1.0",
    description="API for classifying health insurance risk based on applicant data, with endpoints for managing applicants, evaluating risk, retrieving model metadata, and running training jobs.",
    lifespan=lifespan,
)
# Register all routers for API endpoints
app.include_router(health_router)
app.include_router(applicants_router)
app.include_router(evaluations_router)
app.include_router(metadata_router)
app.include_router(statistics_router)
app.include_router(training_router)

