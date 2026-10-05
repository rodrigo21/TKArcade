#!/bin/bash
# Build the launcher AppImage with pyproject-appimage.
# Needs: pyproject-appimage (AUR, or `uv tool install pyproject-appimage`)
# and FUSE to run the result (see README.md here).
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT_DIR="${1:-packaging/appimage/dist}"
mkdir -p "$OUT_DIR"
# Versioned bundle name (release assets carry the version).
if TAG="$(git describe --tags --exact-match 2>/dev/null)"; then
    VER="${TAG#v}"
elif DESCRIBE="$(git describe --tags 2>/dev/null)"; then
    VER="${DESCRIBE#v}"
else
    VER="$(python3 -c 'from importlib.metadata import version; print(version("tkarcade"))' 2>/dev/null || echo dev)"
fi
NAME="TKArcade-${VER}.AppImage"
# Drop any previous bundle first: overwriting a running AppImage fails
# with "Text file busy" (unlinking a running file is fine on Linux).
rm -f "$OUT_DIR"/TKArcade*.AppImage
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

pyproject-appimage \
    --output "$OUT_DIR/$NAME" \
    --work-dir "$WORK_DIR"
chmod +x "$OUT_DIR/$NAME"
echo "built: $OUT_DIR/$NAME"
