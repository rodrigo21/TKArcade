#!/usr/bin/env bash
# Refresh translations/tkarcade_pt_BR.ts from all sources.
# NEVER run lupdate on a subset: it marks every other context vanished.
# Python contexts come from pylupdate (temp file) and are revived into
# the merged catalog; translate leftovers, then lrelease to .qm.
set -euo pipefail
cd "$(dirname "$0")/.."
TS=translations/tkarcade_pt_BR.ts
TMP_TS=/tmp/opencode/ts_py_refresh.ts
lupdate6 src/tkarcade/gui/qml/*.qml -ts "$TS"
pylupdate6 src/tkarcade/gui/*.py src/tkarcade/widgets/*.py -ts "$TMP_TS"
TKARCADE_TS_PY="$TMP_TS" python3 - <<'EOF'
import os
import xml.etree.ElementTree as ET

base = ET.parse("translations/tkarcade_pt_BR.ts")
live = ET.parse(os.environ["TKARCADE_TS_PY"])

def ctxmap(root):
    return {c.findtext("name"): c for c in root.findall("context")}

def trtype(m):
    tr = m.find("translation")
    return tr.get("type") if tr is not None else None

bmap = ctxmap(base.getroot())
for lctx in live.getroot().findall("context"):
    b = bmap.get(lctx.findtext("name"))
    if b is None:
        continue
    bmsgs = {m.findtext("source"): m for m in b.findall("message")}
    for lm in lctx.findall("message"):
        bm = bmsgs.get(lm.findtext("source"))
        if bm is not None and trtype(bm) in ("vanished", "obsolete"):
            ltr, btr = lm.find("translation"), bm.find("translation")
            if (ltr is None or not (ltr.text or "").strip()) and btr is not None and (
                btr.text or ""
            ).strip():
                if ltr is None:
                    ltr = ET.SubElement(lm, "translation")
                ltr.text = btr.text
                if ltr.get("type") == "unfinished":
                    del ltr.attrib["type"]
            btr_live = bm.find("translation")
            if btr_live is not None and btr_live.get("type") in ("vanished", "obsolete"):
                del btr_live.attrib["type"]
base.write("translations/tkarcade_pt_BR.ts", encoding="utf-8", xml_declaration=True)
print("revived Python contexts")
EOF
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
