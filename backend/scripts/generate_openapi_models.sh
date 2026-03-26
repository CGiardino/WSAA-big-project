#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/src/generated"
OUTPUT_FILE="$OUTPUT_DIR/openapi_models.py"
STUBS_OUTPUT_DIR="$OUTPUT_DIR/server_stubs"

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

if command -v openapi-generator-cli >/dev/null 2>&1; then
  GENERATOR_CMD=(openapi-generator-cli)
elif command -v python3 >/dev/null 2>&1 && python3 -c "import openapi_generator_cli" >/dev/null 2>&1; then
  GENERATOR_CMD=(python3 -m openapi_generator_cli)
elif command -v python >/dev/null 2>&1 && python -c "import openapi_generator_cli" >/dev/null 2>&1; then
  GENERATOR_CMD=(python -m openapi_generator_cli)
else
  echo "Error: openapi-generator-cli is not installed." >&2
  echo "Install it with: python -m pip install openapi-generator-cli" >&2
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

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

"${GENERATOR_CMD[@]}" generate \
  -i "$ROOT_DIR/openapi.yaml" \
  -g python-fastapi \
  -o "$TMP_DIR" \
  --type-mappings=file=StrictBytes \
  --additional-properties=sourceFolder=.,packageName=src.generated.server_stubs

rm -rf "$STUBS_OUTPUT_DIR"
mkdir -p "$STUBS_OUTPUT_DIR"
cp -R "$TMP_DIR/src/generated/server_stubs/." "$STUBS_OUTPUT_DIR/"

"$PYTHON_BIN" "$ROOT_DIR/scripts/clean_generated_stub_apis.py"

echo "Generated: src/generated/server_stubs (sanitized strict URL parameter flags)"

