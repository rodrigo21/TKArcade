#!/bin/sh
# Launch the Kirigami shell against a throwaway profile, for the manual
# checks that offscreen cannot verdict (docs/plans/real-display-checks.md).
#
# Usage:
#   scripts/display-check.sh                      # en, 3 seeded games
#   scripts/display-check.sh --lang pt_BR         # translated catalog in situ
#   scripts/display-check.sh --profile DIR        # reuse a profile
#   scripts/display-check.sh --keep               # keep the throwaway profile
#   scripts/display-check.sh -- --verbose         # args go to tkarcade
#
# Nothing touches your real ~/.config: XDG_CONFIG_HOME, XDG_DATA_HOME,
# XDG_STATE_HOME, XDG_CACHE_HOME and TMPDIR all point inside the profile
# (TMPDIR keeps the single-instance socket there, so a running shell
# cannot answer for this one and hide the window).
set -eu

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "error: run this from a TKArcade checkout" >&2
    exit 1
}
cd "$root"

python=${PYTHON:-.venv/bin/python}
[ -x "$python" ] || {
    echo "error: $python missing; run scripts/bootstrap.sh" >&2
    exit 1
}

usage() {
    # The header comment, minus the shebang, up to the first non-comment.
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
}

lang=en
keep=0
profile=
while [ $# -gt 0 ]; do
    case "$1" in
        --lang)
            [ $# -ge 2 ] || { echo "error: --lang needs a code" >&2; exit 2; }
            lang=$2
            shift 2
            ;;
        --profile)
            [ $# -ge 2 ] || { echo "error: --profile needs a directory" >&2; exit 2; }
            profile=$2
            shift 2
            ;;
        --keep) keep=1; shift ;;
        --help|-h) usage; exit 0 ;;
        --) shift; break ;;
        *) break ;;
    esac
done

if [ -n "$profile" ]; then
    # The caller named the directory, so it stays: rebuilding it in place
    # is how a second pass reuses the same seed.
    dir=$profile
    mkdir -p "$dir"
    keep=1
else
    dir=$(mktemp -d "${TMPDIR:-/tmp}/tkarcade-check.XXXXXX")
fi

cleanup() {
    [ "$keep" = 1 ] || rm -rf "$dir"
}
trap cleanup EXIT INT TERM

for sub in config data state cache tmp; do
    mkdir -p "$dir/$sub"
done

# The config API resolves paths from these at import time, so export them
# before seeding, not only for the launch below.
export XDG_CONFIG_HOME="$dir/config"
export XDG_DATA_HOME="$dir/data"
export XDG_STATE_HOME="$dir/state"
export XDG_CACHE_HOME="$dir/cache"
export TMPDIR="$dir/tmp"

# Seed through the config API, never hand-written TOML: the files stay
# valid as the schema grows, and the artwork is a real raster image.
PYTHONPATH=src "$python" - "$dir" "$lang" "$root" <<'PY'
import sys
from pathlib import Path

from tkarcade import config as C

base, lang, root = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])

prefs = C.Preferences()
prefs.tray_enable = True
prefs.close_to_tray = True
prefs.show_preview = True
prefs.language = lang
C.save_preferences(prefs)


def cover() -> str:
    """A solid-colour PNG, so the artwork rows show an image, not a gap."""
    path = base / "art" / "cover.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PySide6.QtGui import QColor, QImage
    except ImportError:  # no PySide6 yet: the bundled SVG still resolves
        return str(root / "src" / "tkarcade" / "icons" / "tkarcade.svg")
    img = QImage(300, 400, QImage.Format_RGB32)
    img.fill(QColor("#3daee9"))
    img.save(str(path))
    return str(path)


art = cover()


def game(appid: str, name: str, exe: str, **general) -> None:
    cfg = C.GameConfig()
    cfg.general.appid = appid
    cfg.general.name = name
    cfg.general.custom_executable = exe
    for key, value in general.items():
        setattr(cfg.general, key, value)
    C.save(cfg)


# One per runtime, plus categories/artwork so the columns and both
# dialogs have something to show without the real library.
game("check-native", "Check Native", "/bin/true")
game("check-wine", "Check Wine", "check.exe", environment="wine")
game("check-category", "Check Category", "/bin/true", categories=["Testing"])
cfg = C.load("check-category")
cfg.artwork.cover = art
cfg.artwork.banner = art
C.save(cfg)

print(f"profile: {base}")
PY

echo "checklist: docs/plans/real-display-checks.md" >&2
echo "start with the tray icon (right-click), then the dialogs" >&2

XDG_CONFIG_HOME="$dir/config" \
XDG_DATA_HOME="$dir/data" \
XDG_STATE_HOME="$dir/state" \
XDG_CACHE_HOME="$dir/cache" \
TMPDIR="$dir/tmp" \
TKARCADE_VERBOSE=1 \
PYTHONPATH=src \
    "$python" -m tkarcade.launcher "$@"
