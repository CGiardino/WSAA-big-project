from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.applicant.router
import src.evaluation.router
import src.health.router
import src.metadata.router
import src.statistics.router 
import src.training.router

from src.db import ensure_schema_on_startup
from src.generated.server_stubs.apis.applicants_api import router as applicants_router
from src.generated.server_stubs.apis.evaluations_api import router as evaluations_router
from src.generated.server_stubs.apis.health_api import router as health_router
from src.generated.server_stubs.apis.metadata_api import router as metadata_router
from src.generated.server_stubs.apis.statistics_api import router as statistics_router
from src.generated.server_stubs.apis.training_api import router as training_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema_on_startup()
    yield


app = FastAPI(
    title="Health Insurance Risk Classifier API",
    version="0.1.0",
    description="API scaffold with Applicant CRUD operations.",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(applicants_router)
app.include_router(evaluations_router)
app.include_router(metadata_router)
app.include_router(statistics_router)
app.include_router(training_router)

