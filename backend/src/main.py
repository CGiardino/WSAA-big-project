from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.applicant.router import router as applicant_router
from src.db import ensure_schema_on_startup
from src.evaluation.router import router as evaluation_router
from src.metadata.router import router as metadata_router
from src.statistics.router import router as statistics_router
from src.training.router import router as training_router

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


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "health-insurance-risk-classifier",
        "version": "0.1.0",
    }


app.include_router(applicant_router)
app.include_router(evaluation_router)
app.include_router(metadata_router)
app.include_router(statistics_router)
app.include_router(training_router)

