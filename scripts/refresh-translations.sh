#!/usr/bin/env bash
# Refresh translations/tkarcade_pt_BR.ts and the compiled .qm.
# One lupdate run over the whole QML tree: lupdate marks whatever it does
# not see as vanished, so a partial run would kill every other context.
# Python needs no pass (GUI strings are all qsTr in QML; lupdate writes
# different placeholders than the retired pylupdate did anyway).
# Translate leftovers, then rerun to recompile.
set -euo pipefail
cd "$(dirname "$0")/.."
TS=translations/tkarcade_pt_BR.ts
QM=src/tkarcade/translations/tkarcade_pt_BR.qm
lupdate6 src/tkarcade/gui/qml/*.qml -ts "$TS"
python3 -W ignore - <<'EOF'
import xml.etree.ElementTree as ET

t = ET.parse("translations/tkarcade_pt_BR.ts")
empty = [
    (ctx.findtext("name"), m.findtext("source"))
    for ctx in t.getroot().findall("context")
    for m in ctx.findall("message")
    if m.find("translation") is None or not (m.find("translation").text or "").strip()
]
print(f"untranslated: {len(empty)}")
for name, source in empty[:20]:
    print(f"  [{name}] {source!r}")
EOF
lrelease6 "$TS" -qm "$QM"
