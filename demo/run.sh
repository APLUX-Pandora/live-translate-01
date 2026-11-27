#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python -u "$HERE/launch.py" "$@"
