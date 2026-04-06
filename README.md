# WSAA-big-project
For the Web Services and Applications Big Project, I extended my previous proof of concept, "Health Insurance Risk Classifier", developed for the Programming for Data Analytics course (link to repo: https://github.com/CGiardino/programming-for-data-analytics/tree/main/project).

The original project focused on data analysis and a neural network model for classifying individuals into insurance risk categories. For this module, I evolved it into a full web-based application with APIs, data persistence, and cloud deployment.

[See System Architecture Overview](SYSTEM_ARCHITECTURE.md)

## Quick Start

To start the backend, you must set both `WSAA_DB_CONNECTION_STRING` and `WSAA_AZURE_STORAGE_CONNECTION_STRING` environment variables. These are required for the backend to connect to the local Azure SQL and Azure Storage.
To start them locally, you can use Docker emulators:

1. Start local Azure SQL and Azure Storage emulators using Docker, and set environment variables (these must be running for local development):
   ```bash
   # Start Azure SQL
   docker run -e 'ACCEPT_EULA=Y' -e 'SA_PASSWORD=Your_password123' -p 1433:1433 -d mcr.microsoft.com/mssql/server:2022-latest
   export WSAA_DB_CONNECTION_STRING='mssql+pyodbc://sa:Your_password123@localhost:1433/tempdb?driver=ODBC+Driver+18+for+SQL+Server'

   # Start Azure Storage Emulator (Azurite)
   docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite
   export WSAA_AZURE_STORAGE_CONNECTION_STRING='DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFeqCnf2P==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;'


   ```
   - [Official docs: SQL Server on Docker](https://learn.microsoft.com/en-us/sql/linux/quickstart-install-connect-docker)
   - [Official docs: Azurite (Azure Storage emulator)](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?tabs=docker)
   - Alternatively, you can connect to actual Azure services if you have an Azure subscription, but using local emulators allows for a fully self-contained development environment. 

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install backend dependencies:
   ```bash
   python -m pip install -r backend/requirements.txt
   ```
4. Generate Python models and FastAPI stubs from OpenAPI:
   ```bash
   ./backend/scripts/generate_openapi_models.sh
   ```
5. Generate Angular API client from OpenAPI:
   ```bash
   ./frontend/scripts/generate-api-client.sh
   ```
6. Start the backend API (requires both environment variables to be set):
   ```bash
   cd backend
   uvicorn src.main:app --reload
   ```
7. In a new terminal, start the frontend:
   ```bash
   cd frontend
   npm install
   npm start
   ```

- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- API calls use `/api/*` and are proxied to the backend

## Release Deployment (Azure)

- Backend container image is built from `backend/Dockerfile` and pushed by `azure-pipelines.yml`.
- Backend is deployed to Azure Container Apps using `az containerapp update`.
- Frontend is built with Angular and deployed to Azure Static Web Apps.
- Set pipeline variables/secrets before running release:
  - `dockerRegistryServiceConnection`
  - `azureServiceConnection`
  - `acrLoginServer`
  - `resourceGroup`
  - `containerAppName`
  - `azureStaticWebAppsApiToken`
- For frontend API target, set `frontend/src/assets/env.js` `apiBaseUrl` to your Container App URL for release.

Additional: [See Project Plan](PROJECT_PLAN.md)
