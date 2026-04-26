"""HTTP routing layer for model training and training dataset APIs."""

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from src.analytics.dataset_preparation import build_dataset, persist_dataset
from src.generated.openapi_models import (
    Status,
    TrainingDatasetListResponse,
    TrainingDatasetRow,
    TrainingRunRequest,
    TrainingRunResponse,
    TrainingStatusResponse,
)
from src.generated.server_stubs.apis.training_api_base import BaseTrainingApi
from src.generated.server_stubs.models.training_dataset_list_response import (
    TrainingDatasetListResponse as StubTrainingDatasetListResponse,
)
from src.generated.server_stubs.models.training_run_request import (
    TrainingRunRequest as StubTrainingRunRequest,
)
from src.generated.server_stubs.models.training_run_response import (
    TrainingRunResponse as StubTrainingRunResponse,
)
from src.generated.server_stubs.models.training_status_response import (
    TrainingStatusResponse as StubTrainingStatusResponse,
)
from src.risk_classifier import (
    load_analysis_data,
    run_eda,
    run_training,
)
from src.storage.dao import StorageDAO
from src.training.dao import TrainingDAO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["training"])


def get_training_dao() -> TrainingDAO:
    # Isolated factory helps dependency overrides in tests.
    return TrainingDAO()


@router.post("/training/run", response_model=TrainingRunResponse)
def run_training_job(
    payload: TrainingRunRequest | None = None,
    dao: TrainingDAO = Depends(get_training_dao),
) -> TrainingRunResponse:
    req = payload or TrainingRunRequest(epochs=200)
    # Default to 200 epochs when caller omits payload or explicit value.
    epochs = req.epochs or 200
    run_id = uuid4()
    started_at = datetime.now(UTC)

    # Initialize storage and download data
    try:
        logger.info(f"Training run {run_id} started with epochs={epochs}")
        storage = StorageDAO()
        logger.info("StorageDAO initialized successfully")
        
        temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-training-"))
        logger.info(f"Created temp directory: {temp_dir}")
        
        data_blob_name = "data/health_insurance_data.csv"
        data_path = temp_dir / "health_insurance_data.csv"
        
        logger.info(f"Downloading blob '{data_blob_name}' to {data_path}")
        storage.download_file(data_blob_name, data_path)
        logger.info(f"Data file downloaded successfully, size: {data_path.stat().st_size} bytes")
        
    except ValueError as exc:
        error_msg = f"Configuration error: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg) from exc
    except FileNotFoundError as exc:
        error_msg = f"Data file not found in storage: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=400, detail=error_msg) from exc
    except Exception as exc:
        error_msg = f"Failed to download training data: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg) from exc
    
    # Plot artifacts are uploaded to blob storage; keep any transient files in the run temp directory.
    logger.info("Using temporary run directory for transient plot operations: %s", temp_dir)

    # Save initial status
    run_status: dict[str, object | None] = {
        "run_id": run_id,
        "status": "running",
        "epochs": epochs,
        "model_version": None,
        "classification_report": None,
        "started_at": started_at,
        "finished_at": None,
        "last_error": None,
    }
    
    try:
        dao.save_run_status(run_status)
        logger.info(f"Saved initial run status for {run_id}")
    except Exception as exc:
        logger.error(f"Failed to save run status: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save training status") from exc

    # Execute training pipeline
    trained_model_version = None
    classification_report = None
    
    try:
        logger.info("Starting data preparation phase")
        df = build_dataset(data_path)
        logger.info(f"Dataset built: {len(df)} rows")
        
        persist_dataset(df)
        logger.info("Dataset persisted to database")
        
        logger.info("Loading analysis data")
        df_analysis = load_analysis_data()
        logger.info(f"Analysis data loaded: {len(df_analysis)} rows")
        
        logger.info("Running exploratory data analysis")
        run_eda(df_analysis, temp_dir)
        logger.info("EDA completed, plots generated")
        
        logger.info(f"Starting model training with {epochs} epochs")
        trained_model_version, classification_report = run_training(
            plot_dir=temp_dir,
            epochs=epochs,
        )
        logger.info(f"Model training completed: {trained_model_version}")
        
    except Exception as exc:
        finished_at = datetime.now(UTC)
        error_msg = f"Training pipeline failed: {str(exc)}"
        logger.error(error_msg, exc_info=True)
        
        run_status.update(
            {
                "status": "failed",
                "finished_at": finished_at,
                "last_error": error_msg,
            }
        )
        try:
            # Persist failure state so `/training/status` remains informative.
            dao.save_run_status(run_status)
            logger.info(f"Saved failed run status for {run_id}")
        except Exception as db_exc:
            logger.error(f"Failed to save error status: {str(db_exc)}", exc_info=True)
        
        raise HTTPException(status_code=500, detail=error_msg) from exc

    # Save completion status
    finished_at = datetime.now(UTC)
    run_status.update(
        {
            "status": "completed",
            "model_version": trained_model_version,
            "classification_report": classification_report,
            "finished_at": finished_at,
            "last_error": None,
        }
    )
    
    try:
        dao.save_run_status(run_status)
        logger.info(f"Saved completed run status for {run_id}")
    except Exception as exc:
        logger.error(f"Failed to save completion status: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save training completion") from exc

    logger.info(f"Training run {run_id} completed successfully")
    return TrainingRunResponse(
        run_id=run_id,
        status=Status.completed,
        epochs=epochs,
        model_version=trained_model_version,
        started_at=started_at,
        finished_at=finished_at,
        classification_report=classification_report,
    )


@router.get("/training/status", response_model=TrainingStatusResponse)
def get_training_status(
    dao: TrainingDAO = Depends(get_training_dao),
) -> TrainingStatusResponse:
    latest = dao.get_latest_run_status()
    if latest is None:
        # Stable idle payload when no run has ever been persisted.
        return TrainingStatusResponse(
            run_id=None,
            status="idle",
            epochs=None,
            model_version=None,
            started_at=None,
            finished_at=None,
            last_error=None,
            classification_report=None,
        )
    return TrainingStatusResponse(**latest)


@router.get("/training/status/{run_id}", response_model=TrainingStatusResponse)
def get_training_status_by_run_id(
    run_id: str,
    dao: TrainingDAO = Depends(get_training_dao),
) -> TrainingStatusResponse:
    run_status = dao.get_run_status_by_id(run_id)
    if run_status is None:
        raise HTTPException(status_code=404, detail="training run not found")
    return TrainingStatusResponse(**run_status)


@router.get("/training/dataset", response_model=TrainingDatasetListResponse)
def list_training_dataset(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    dao: TrainingDAO = Depends(get_training_dao),
) -> TrainingDatasetListResponse:
    rows, total = dao.list_training_dataset(limit=limit, offset=offset)

    items: list[TrainingDatasetRow] = []
    for row_data in rows:
        # Validate each row against OpenAPI schema before returning it.
        items.append(TrainingDatasetRow.model_validate(row_data))

    return TrainingDatasetListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(items) < total,
    )


class TrainingApiImpl(BaseTrainingApi):
    """Adapter that delegates generated stub calls to runtime handlers."""

    async def get_training_status(self) -> StubTrainingStatusResponse:
        response = get_training_status(get_training_dao())
        return StubTrainingStatusResponse.model_validate(response.model_dump(mode="json"))

    async def get_training_status_by_run_id(self, run_id) -> StubTrainingStatusResponse:
        response = get_training_status_by_run_id(str(run_id), get_training_dao())
        return StubTrainingStatusResponse.model_validate(response.model_dump(mode="json"))

    async def list_training_dataset(
        self,
        limit: int | None,
        offset: int | None,
    ) -> StubTrainingDatasetListResponse:
        response = list_training_dataset(
            limit=limit if limit is not None else 25,
            offset=offset if offset is not None else 0,
            dao=get_training_dao(),
        )
        return StubTrainingDatasetListResponse.model_validate(response.model_dump(mode="json"))

    async def run_training(
        self,
        training_run_request: StubTrainingRunRequest | None,
    ) -> StubTrainingRunResponse:
        payload = (
            TrainingRunRequest.model_validate(training_run_request.model_dump())
            if training_run_request is not None
            else None
        )
        response = run_training_job(payload, get_training_dao())
        return StubTrainingRunResponse.model_validate(response.model_dump(mode="json"))
