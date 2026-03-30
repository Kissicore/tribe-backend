#!/bin/bash
# Hook-Check AI — Railway startup script
# Uses Railway's $PORT variable (defaults to 8000)

set -e

PORT=${PORT:-8000}
HOST="0.0.0.0"

echo "Starting Hook-Check AI Inference Server on port $PORT..."
echo "   Tribe path: ${TRIBE_PATH:-./tribe_v2}"
echo "   Hook seconds: ${HOOK_SECONDS:-8}"

exec uvicorn inference_server:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    --log-level info
