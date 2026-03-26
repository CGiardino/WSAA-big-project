#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/src/generated"
OUTPUT_FILE="$OUTPUT_DIR/openapi_models.py"

mkdir -p "$OUTPUT_DIR"

# Keep explicit package imports stable across environments.
if [ ! -f "$OUTPUT_DIR/__init__.py" ]; then
  touch "$OUTPUT_DIR/__init__.py"
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Error: python is not available in PATH." >&2
  exit 1
fi

"$PYTHON_BIN" -m datamodel_code_generator \
  --input "$ROOT_DIR/openapi.yaml" \
  --input-file-type openapi \
  --output "$OUTPUT_FILE" \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --field-constraints \
  --use-standard-collections

echo "Generated: src/generated/openapi_models.py"

