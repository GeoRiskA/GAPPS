#!/bin/zsh

GAPPS_DIR="$(cd "$(dirname "$0")" && pwd)"
"$GAPPS_DIR/.venv/bin/python" "$GAPPS_DIR/run_gapps.py"