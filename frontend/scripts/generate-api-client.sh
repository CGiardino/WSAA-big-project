#!/usr/bin/env bash
set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
OPENAPI_SPEC="$PROJECT_ROOT/backend/openapi.yaml"
OUTPUT_DIR="$FRONTEND_DIR/src/app/generated-api"

if [ ! -f "$OPENAPI_SPEC" ]; then
  echo "Error: OpenAPI spec not found at $OPENAPI_SPEC" >&2
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

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

"${GENERATOR_CMD[@]}" generate \
  -i "$OPENAPI_SPEC" \
  -g typescript-angular \
  -o "$OUTPUT_DIR"

echo "Generated frontend API client at: $OUTPUT_DIR"


