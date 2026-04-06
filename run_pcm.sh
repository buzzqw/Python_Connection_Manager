#!/usr/bin/env bash
# Avvia PCM con il virtualenv corretto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/PCM.py" "$@"
