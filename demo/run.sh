#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Create the project environment: python3 -m venv $ROOT/.venv" >&2
  echo "Install requirements with $ROOT/.venv/bin/python -m pip install -r $ROOT/requirements.txt" >&2
  exit 1
fi
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export LT01_CLOCK_MS=160
export LD_LIBRARY_PATH="/usr/local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$PYTHON" -u "$HERE/demo_server.py" "$@"
