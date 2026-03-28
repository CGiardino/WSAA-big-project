from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from azure.storage.blob import BlobServiceClient


class StorageDAO:
    """DAO service for Azure Blob container file operations."""

    def __init__(
        self,
        connection_string: str | None = None,
        container_name: str | None = None,
        prefix: str | None = None,
    ) -> None:
        self.connection_string = connection_string or os.getenv("WSAA_AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = container_name or "hirc"
        self.prefix = (prefix if prefix is not None else os.getenv("WSAA_AZURE_STORAGE_PREFIX", "")).strip("/")

        if not self.connection_string:
            raise ValueError("WSAA_AZURE_STORAGE_CONNECTION_STRING is required")
        self._validate_connection_string(self.connection_string)
        if not self.container_name:
            raise ValueError("WSAA_AZURE_STORAGE_CONTAINER is required")

        self._service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self._container_client = self._service_client.get_container_client(self.container_name)

    @staticmethod
    def _validate_connection_string(connection_string: str) -> None:
        required_parts = ("AccountName=", "AccountKey=")
        if not all(part in connection_string for part in required_parts):
            raise ValueError(
                "WSAA_AZURE_STORAGE_CONNECTION_STRING must include AccountName and AccountKey"
            )

    def _blob_name(self, blob_name: str) -> str:
        clean_name = blob_name.strip("/")
        if not clean_name:
            raise ValueError("blob_name must not be empty")
        return f"{self.prefix}/{clean_name}" if self.prefix else clean_name

    def list_files(self, starts_with: str | None = None) -> list[str]:
        """List blobs in the configured container and optional prefix."""
        prefix = self._blob_name(starts_with) if starts_with else (self.prefix + "/" if self.prefix else None)
        blobs = self._container_client.list_blobs(name_starts_with=prefix)
        items: list[str] = []
        for blob in blobs:
            name = str(blob.name)
            if self.prefix and name.startswith(self.prefix + "/"):
                name = name[len(self.prefix) + 1 :]
            items.append(name)
        return items

    def exists(self, blob_name: str) -> bool:
        """Check whether a blob exists."""
        client = self._container_client.get_blob_client(self._blob_name(blob_name))
        return bool(client.exists())

    def upload_file(self, local_path: str | Path, blob_name: str | None = None, overwrite: bool = True) -> str:
        """Upload a local file to the container and return its blob name."""
        path = Path(local_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Local file not found: {path}")

        target_name = self._blob_name(blob_name or path.name)
        blob_client = self._container_client.get_blob_client(target_name)
        with path.open("rb") as stream:
            blob_client.upload_blob(stream, overwrite=overwrite)
        return target_name

    def upload_stream(self, stream: BinaryIO, blob_name: str, overwrite: bool = True) -> str:
        """Upload a binary stream to the container and return its blob name."""
        target_name = self._blob_name(blob_name)
        blob_client = self._container_client.get_blob_client(target_name)
        blob_client.upload_blob(stream, overwrite=overwrite)
        return target_name

    def download_file(self, blob_name: str, destination_path: str | Path) -> Path:
        """Download a blob into a local file path and return the destination path."""
        path = Path(destination_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        source_name = self._blob_name(blob_name)
        blob_client = self._container_client.get_blob_client(source_name)
        with path.open("wb") as out:
            out.write(blob_client.download_blob().readall())
        return path

    def download_bytes(self, blob_name: str) -> bytes:
        """Download a blob content as bytes."""
        source_name = self._blob_name(blob_name)
        blob_client = self._container_client.get_blob_client(source_name)
        return blob_client.download_blob().readall()

    def delete_file(self, blob_name: str) -> None:
        """Delete a blob if it exists."""
        source_name = self._blob_name(blob_name)
        blob_client = self._container_client.get_blob_client(source_name)
        blob_client.delete_blob(delete_snapshots="include")


