# SYSTEM ARCHITECTURE

Health Insurance Risk Classifier platform with:
- Angular frontend
- Python FastAPI backend
- SQL database
- Azure deployment

The platform evolves the original analytics prototype into a full web application with stable contracts, persistent storage, model-backed predictions, and cloud operations.

Current API domain naming uses insurance terminology:
- `applicants` for applicant CRUD
- `evaluations` for risk evaluation results
- `training` for model training operations

## Architecture Principles
- API-first: `openapi.yaml` is the contract source of truth.
- Contract-driven development: backend models/routes are generated from OpenAPI and then implemented.
- Layered backend design: API, service, model adapter, repository.
- Cloud-ready deployment: stateless API + managed SQL + managed hosting on Azure.

## Target Tech Stack
- Frontend: Angular
- Backend: Python FastAPI
- API contract: OpenAPI 3 (`openapi.yaml`)
- Persistence: Azure SQL-compatible engine locally via Docker, Azure SQL in cloud
- Deployment platform: Azure

## High-Level System Components
1. Frontend (Angular)
- Calls backend endpoints defined in `openapi.yaml`.
- Uses generated API client types/services from the OpenAPI contract.
- Provides forms, result views, and history/management views.

2. API Layer (FastAPI)
- Exposes REST endpoints for evaluations, metadata, training, health, and applicant data.
- Enforces request/response validation against generated OpenAPI models.
- Handles auth, errors, and HTTP semantics.

3. Application Service Layer
- Coordinates business workflows (predict, persist, fetch, batch operations).
- Applies domain rules and orchestrates model/repository calls.
- Keeps route handlers thin and testable.

4. Model Adapter Layer
- Encapsulates risk-model loading and inference.
- Supports versioned model artifacts and metadata retrieval.
- Loads the active model for evaluation requests.
- Isolated from API handlers so model changes do not break route contracts.

5. Data Access Layer (Repository)
- Encapsulates SQL interactions for applicants, evaluations, training runs, and related entities.
- Provides backend storage abstraction for local Dockerized Azure SQL and Azure SQL environments.
- Manages schema boundaries, constraints, and query behavior.

6. SQL Database
- Stores applicant records, evaluation outputs, model metadata, training run metadata, and timestamps.
- Supports reporting/history features and batch processing outputs.

7. Model Artifact Storage
- Stores trained model files (versioned artifacts) in Azure Blob Storage.
- Supports model upload after training and model download/cache for evaluation requests.

8. External Integration Layer
- Imports applicant data from CSV files for batch training workflows.
- Uses the same service layer and model adapter to keep logic consistent.

9. Observability and Operations
- Health endpoints, structured logs, and error tracing.
- Deployment pipeline for code generation, testing, and Azure release.

## Data Flows

### Single Evaluation Flow
1. Angular sends evaluation input to FastAPI.
2. FastAPI validates payload via generated OpenAPI schema models.
3. Service layer loads or reuses active model artifact from Blob-backed model adapter.
4. Service layer runs inference and persists request/result to SQL.
5. API returns risk category and metadata to frontend.

### Training Run Flow
1. Client calls `POST /v1/training/run` with optional training options (e.g., epochs).
2. API starts training workflow and returns run metadata (including `run_id`).
3. Training workflow prepares data and trains model.
4. Trained model artifact is stored in Azure Blob Storage.
5. Training status is available via `GET /v1/training/status`.

### Applicant CRUD Flow
1. Angular calls applicant endpoints (`/v1/applicants`).
2. FastAPI validates request bodies.
3. Repository executes SQL operations.
4. API returns created/read/updated/deleted results.

### Batch Integration Flow
1. Applicant CSV file is uploaded or provided to the integration endpoint.
2. Service validates and parses training records from the CSV.
3. Service stores/versions the prepared training dataset metadata.
4. Service triggers a training run using the imported batch data.
5. Training run status and resulting model metadata are persisted and exposed via API.

## Data Domains (Core)
- Applicants: identity/contact/demographic fields.
- Evaluations: input features, evaluated risk category, model version, timestamp.
- Model metadata: active model name/version and supported labels/features.
- Training runs: run id, status, epochs, model version, timestamps, error details.
- Batch jobs (planned): CSV training source reference, dataset version, run status, record counts, summary metrics.

## Azure Deployment View
- Angular app hosted on Azure web hosting service.
- FastAPI app hosted on Azure compute service.
- SQL hosted on Azure managed SQL service.
- Model artifacts hosted in Azure Blob Storage.
- CI/CD pipeline runs:
  - dependency install
  - OpenAPI code generation
  - tests
  - deployment to Azure environments

## Local Development Environment
- API runs locally with FastAPI.
- SQL runs locally in Docker using an Azure SQL-compatible image (for parity with cloud SQL behavior).
- Local training can keep run state in-memory for a single API instance.
- For multi-instance/cloud reliability, training run status should be persisted in SQL and model artifacts in Blob.
- Local configuration should mirror Azure connection settings where possible (host, port, credentials, database name).

## Security and Access (Design-Level)
- Authentication and authorization enforced at API boundary.
- Secrets managed via Azure configuration/secret management.
- Input validation and structured error responses enforced by schema.
- Transport security via HTTPS.



