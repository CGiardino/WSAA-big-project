"""Centralized startup schema statements for Azure SQL bootstrapping."""

from pathlib import Path


def _read_sql_file(file_name: str) -> str:
    """Load a schema SQL statement from this package directory."""
    schema_path = Path(__file__).resolve().parent / file_name
    return schema_path.read_text(encoding="utf-8")


STARTUP_SCHEMA_STATEMENTS = (
    _read_sql_file("applicants.sql"),
    _read_sql_file("evaluations.sql"),
    _read_sql_file("training_runs.sql"),
)


