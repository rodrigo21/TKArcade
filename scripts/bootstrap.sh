#!/bin/sh
# Recreate the local development environment for a fresh checkout.
# Writes only inside the working tree; never touches $HOME or the system
# interpreter. Safe to re-run.
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "error: run this from a TKArcade checkout" >&2
    exit 1
}
cd "$root"

command -v uv >/dev/null 2>&1 || {
    echo "error: uv is not installed (install the distro package)" >&2
    exit 1
}

# The distro packages supply PySide6/vdf/jeepney, so the venv reuses the
# system site packages. --no-deps is load-bearing: without it uv installs
# a PyPI PySide6 whose QML tree lacks org.kde.kirigami and the GUI tests
# fail. --no-build-isolation reuses the system build backend.
if [ -d .venv ]; then
    echo "reusing the existing .venv"
else
    uv venv --system-site-packages .venv
fi
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .

git config core.hooksPath scripts/git-hooks

missing=
for module in PySide6 vdf jeepney; do
    .venv/bin/python -c "import $module" 2>/dev/null || missing="$missing $module"
done
if [ -n "$missing" ]; then
    echo "warning: system packages missing:$missing" >&2
    echo "         install the distro python packages, then re-run this script" >&2
fi

echo "environment ready; checks: .venv/bin/python -m pytest tests/ -q"
