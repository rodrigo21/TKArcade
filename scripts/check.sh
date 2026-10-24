#!/bin/sh
# Single verification gate for development: lint, format, tests.
#
# Usage:
#   scripts/check.sh                     # fast suite (no QML driver)
#   scripts/check.sh --changed           # tests for what git shows as changed
#   scripts/check.sh --qml               # full suite, QML driver included
#   scripts/check.sh tests/test_config.py  # only the given pytest targets
#
# `--changed` maps a changed source file to tests/test_<basename>.py
# (backends/ always maps to tests/test_backends.py, QML to the full suite).
# A file with no matching module falls back to the whole fast suite on
# purpose: the gate never silently skips a change.
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "error: run this from a TKArcade checkout" >&2
    exit 1
}
cd "$root"

changed=0
qml=0
while [ $# -gt 0 ]; do
    case "$1" in
        --changed) changed=1; shift ;;
        --qml) qml=1; shift ;;
        *) break ;;
    esac
done

python=${PYTHON:-.venv/bin/python}
ruff=${RUFF:-ruff}

"$ruff" check src/ tests/
"$ruff" format --check src/ tests/

add() {
    case " $targets " in
        *" $1 "*) ;;
        *) targets="$targets $1" ;;
    esac
}

targets=
if [ $# -gt 0 ]; then
    targets=" $*"
elif [ "$changed" = 1 ]; then
    files=$( { git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u)
    unmapped=
    touched_src=0
    for f in $files; do
        case "$f" in
            *.qml) qml=1 ;;
            tests/*.py) add "$f" ;;
            src/tkarcade/backends/*.py) add tests/test_backends.py; touched_src=1 ;;
            src/tkarcade/*.py|src/tkarcade/gui/*.py)
                touched_src=1
                base=$(basename "$f" .py)
                if [ -f "tests/test_$base.py" ]; then
                    add "tests/test_$base.py"
                else
                    unmapped="$unmapped $f"
                fi
                ;;
            pyproject.toml|packaging/*) add tests/test_packaging.py ;;
        esac
    done
    # The import guard covers the whole tree and is cheap: always run it
    # when source changed.
    [ "$touched_src" = 1 ] && add tests/test_no_widgets.py
    if [ -n "$unmapped" ]; then
        echo "check: no test module for$unmapped, running the fast suite"
        targets=tests/
    fi
fi

if [ "$qml" = 1 ]; then
    echo "check: full suite (QML driver included)"
    # shellcheck disable=SC2086  # a target list, split on purpose
    exec "$python" -m pytest tests/ -q $targets
fi

[ -n "$targets" ] || targets=" tests/"
# The one deselected node is the `qml`-marked driver in
# tests/test_kirigami_qml.py: it runs the whole offscreen QML suite in
# subprocesses, so `--qml` is the only way to run it.
echo "check: pytest$targets (the qml suite driver is deselected, use --qml)"
# shellcheck disable=SC2086  # a target list, split on purpose
exec "$python" -m pytest $targets -q -m "not qml"
