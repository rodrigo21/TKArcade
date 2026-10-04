#!/bin/bash
# Build the launcher AppImage with pyproject-appimage.
# Needs: pyproject-appimage (AUR, or `uv tool install pyproject-appimage`)
# and FUSE to run the result (see README.md here).
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT_DIR="${1:-packaging/appimage/dist}"
mkdir -p "$OUT_DIR"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

pyproject-appimage \
    --output "$OUT_DIR/TKSteamLaunch.AppImage" \
    --work-dir "$WORK_DIR"
chmod +x "$OUT_DIR/TKSteamLaunch.AppImage"
echo "built: $OUT_DIR/TKSteamLaunch.AppImage"
