#!/usr/bin/env python3
"""One-shot bootstrap helpers used by docker-compose local stack."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _seed_data_blob() -> None:
    connection_string = _required_env("WSAA_AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("WSAA_AZURE_STORAGE_CONTAINER", "hirc").strip() or "hirc"
    blob_name = os.getenv("WSAA_BOOTSTRAP_DATA_BLOB", "data/health_insurance_data.csv").strip()
    data_path = Path(os.getenv("WSAA_BOOTSTRAP_DATA_PATH", "/app/data/health_insurance_data.csv"))

    if not data_path.exists() or not data_path.is_file():
        raise FileNotFoundError(f"Seed CSV not found: {data_path}")

    service = BlobServiceClient.from_connection_string(connection_string)
    container = service.get_container_client(container_name)

    try:
        container.create_container()
        print(f"Created blob container '{container_name}'")
    except ResourceExistsError:
        pass

    blob = container.get_blob_client(blob_name)
    if blob.exists():
        print(f"Seed blob already present: {blob_name}")
        return

    with data_path.open("rb") as stream:
        blob.upload_blob(stream, overwrite=False)
    print(f"Uploaded seed blob: {blob_name}")


def _wait_for_backend(api_url: str, timeout_seconds: int, interval_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"{api_url.rstrip('/')}/health"

    while time.time() < deadline:
        try:
            request = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                if 200 <= response.status < 300:
                    print("Backend is healthy")
                    return
        except Exception:
            pass
        time.sleep(interval_seconds)

    raise TimeoutError(f"Backend did not become healthy within {timeout_seconds} seconds")


def _request_json(method: str, url: str, payload: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def _ensure_model() -> None:
    api_url = os.getenv("WSAA_BOOTSTRAP_API_URL", "http://backend:80").strip() or "http://backend:80"
    training_epochs = int(os.getenv("WSAA_BOOTSTRAP_EPOCHS", "200"))
    wait_timeout = int(os.getenv("WSAA_BOOTSTRAP_WAIT_SECONDS", "600"))
    run_timeout = int(os.getenv("WSAA_BOOTSTRAP_TRAINING_TIMEOUT_SECONDS", "3600"))

    _wait_for_backend(api_url, timeout_seconds=wait_timeout, interval_seconds=5)

    availability_url = f"{api_url.rstrip('/')}/v1/metadata/model/availability"
    status_code, availability = _request_json("GET", availability_url, timeout=30)
    if status_code != 200:
        raise RuntimeError(f"Failed to check model availability ({status_code}): {availability}")

    if availability.get("artifact_exists") and availability.get("artifact_loadable"):
        active_version = availability.get("active_model_version")
        print(f"Model already available ({active_version}); skipping initial training")
        return

    print(f"No loadable model available; running initial training with epochs={training_epochs}")
    training_url = f"{api_url.rstrip('/')}/v1/training/run"
    status_code, response = _request_json(
        "POST",
        training_url,
        payload={"epochs": training_epochs},
        timeout=run_timeout,
    )
    if status_code != 200:
        raise RuntimeError(f"Initial training failed ({status_code}): {response}")

    print(f"Initial training completed: run_id={response.get('run_id')}, model={response.get('model_version')}")


def main() -> None:
    mode = os.getenv("WSAA_BOOTSTRAP_MODE", "").strip().lower()
    if not mode and len(sys.argv) > 1:
        mode = str(sys.argv[1]).strip().lower()

    if mode == "seed-data":
        _seed_data_blob()
        return
    if mode == "ensure-model":
        _ensure_model()
        return

    raise ValueError("Usage: bootstrap_local_stack.py [seed-data|ensure-model]")


if __name__ == "__main__":
    main()


