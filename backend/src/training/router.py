import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from src.generated.openapi_models import (
    TrainingDatasetListResponse,
    TrainingDatasetRow,
    TrainingRunRequest,
    TrainingRunResponse,
    TrainingStatusResponse,
)
from src.health_insurance_risk_classifier import (
    build_dataset,
    load_analysis_data,
    persist_dataset,
    run_eda,
    run_training,
)
from src.storage.repository import StorageRepository
from src.training.repository import TrainingRepository

router = APIRouter(prefix="/v1", tags=["training"])


def get_training_repository() -> TrainingRepository:
    return TrainingRepository()


@router.post("/training/run", response_model=TrainingRunResponse)
def run_training_job(
    payload: TrainingRunRequest | None = None,
    repository: TrainingRepository = Depends(get_training_repository),
) -> TrainingRunResponse:
    req = payload or TrainingRunRequest()
    epochs = req.epochs or 200

    try:
        storage = StorageRepository()
        temp_dir = Path(tempfile.mkdtemp(prefix="wsaa-training-"))
        
        data_blob_name = "data/health_insurance_data.csv"
        data_path = temp_dir / "health_insurance_data.csv"
        
        storage.download_file(data_blob_name, data_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    
    plots_dir = Path(__file__).resolve().parents[2] / "plots"


    run_id = uuid4()
    started_at = datetime.now(UTC)
    run_status: dict[str, object | None] = {
        "run_id": run_id,
        "status": "running",
        "epochs": epochs,
        "model_version": None,
        "started_at": started_at,
        "finished_at": None,
        "last_error": None,
    }
    repository.save_run_status(run_status)

    try:
        df = build_dataset(data_path)
        persist_dataset(df)
        df_analysis = load_analysis_data()
        run_eda(df_analysis, plots_dir)
        trained_model_version = run_training(
            plot_dir=plots_dir,
            epochs=epochs,
        )
    except Exception as exc:
        finished_at = datetime.now(UTC)
        run_status.update(
            {
                "status": "failed",
                "finished_at": finished_at,
                "last_error": str(exc),
            }
        )
        repository.save_run_status(run_status)
        raise HTTPException(status_code=500, detail="Training run failed") from exc

    finished_at = datetime.now(UTC)
    run_status.update(
        {
            "status": "completed",
            "model_version": trained_model_version,
            "finished_at": finished_at,
            "last_error": None,
        }
    )
    repository.save_run_status(run_status)

    return TrainingRunResponse(
        run_id=run_id,
        status="completed",
        epochs=epochs,
        model_version=trained_model_version,
        started_at=started_at,
        finished_at=finished_at,
    )


@router.get("/training/status", response_model=TrainingStatusResponse)
def get_training_status(
    repository: TrainingRepository = Depends(get_training_repository),
) -> TrainingStatusResponse:
    latest = repository.get_latest_run_status()
    if latest is None:
        return TrainingStatusResponse(
            run_id=None,
            status="idle",
            epochs=None,
            model_version=None,
            started_at=None,
            finished_at=None,
            last_error=None,
        )
    return TrainingStatusResponse(**latest)


@router.get("/training/status/{run_id}", response_model=TrainingStatusResponse)
def get_training_status_by_run_id(
    run_id: str,
    repository: TrainingRepository = Depends(get_training_repository),
) -> TrainingStatusResponse:
    run_status = repository.get_run_status_by_id(run_id)
    if run_status is None:
        raise HTTPException(status_code=404, detail="training run not found")
    return TrainingStatusResponse(**run_status)


@router.get("/training/dataset", response_model=TrainingDatasetListResponse)
def list_training_dataset(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repository: TrainingRepository = Depends(get_training_repository),
) -> TrainingDatasetListResponse:
    rows, total = repository.list_training_dataset(limit=limit, offset=offset)

    items: list[TrainingDatasetRow] = []
    for row_data in rows:
        items.append(TrainingDatasetRow.model_validate(row_data))

    return TrainingDatasetListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(items) < total,
    )

