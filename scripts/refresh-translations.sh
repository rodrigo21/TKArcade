#!/usr/bin/env bash
# Refresh translations/tkarcade_pt_BR.ts and the compiled .qm.
# One lupdate run over the whole QML tree plus the tray menu (the only
# translatable Python strings): lupdate marks whatever it does not see as
# vanished, so a partial run would kill every other context. -no-obsolete
# drops those vanished entries instead of letting them pile up.
# Translate leftovers, then rerun to recompile: lrelease refuses to write
# the .qm while any message is still unfinished.
set -euo pipefail
cd "$(dirname "$0")/.."
TS=translations/tkarcade_pt_BR.ts
QM=src/tkarcade/translations/tkarcade_pt_BR.qm
lupdate6 -no-obsolete src/tkarcade/gui/qml/*.qml src/tkarcade/gui/tray.py -ts "$TS"
python3 -W ignore - <<'EOF'
import xml.etree.ElementTree as ET

t = ET.parse("translations/tkarcade_pt_BR.ts")
messages = [
    (ctx.findtext("name"), m)
    for ctx in t.getroot().findall("context")
    for m in ctx.findall("message")
]


def translation(message):
    return message.find("translation")


empty = [
    (name, m.findtext("source"))
    for name, m in messages
    if translation(m) is None or not (translation(m).text or "").strip()
]
unfinished = [
    (name, m.findtext("source"))
    for name, m in messages
    if translation(m) is not None and translation(m).get("type") == "unfinished"
]
print(f"untranslated: {len(empty)}")
for name, source in empty[:20]:
    print(f"  [{name}] {source!r}")
print(f"unfinished: {len(unfinished)}")
for name, source in unfinished[:20]:
    print(f"  [{name}] {source!r}")
EOF
lrelease6 -fail-on-unfinished "$TS" -qm "$QM"
