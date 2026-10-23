#!/bin/sh
# Single verification gate for development: lint, format, fast test suite.
# The full suite, including the QML driver, stays a separate run (AGENTS.md:
# once per task, and only when tests/ or QML changed).
# Usage: scripts/check.sh [extra pytest args]
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "error: run this from a TKArcade checkout" >&2
    exit 1
}
cd "$root"

python=${PYTHON:-.venv/bin/python}
ruff=${RUFF:-ruff}

"$ruff" check src/ tests/
"$ruff" format --check src/ tests/
"$python" -m pytest tests/ -q -m "not qml" "$@"
