"""VNDB metadata payload (Kana API, stdlib urllib).

A local game without a Steam AppID is searched by title; the picked
visual novel saves in ``[metadata] vndb_id`` so the next download skips
the search. VNDB answers a synopsis, the developers and a release date.
It has no publisher, series, age ratings or genre field: tags are a
different taxonomy and stay out. The cache and the rate gate live in
``metadata.py``.
"""

from __future__ import annotations

import html
import json
import logging
import re
import urllib.request

from . import config as cfgmod

log = logging.getLogger("tkarcade.vndb")

ENDPOINT = "https://api.vndb.org/kana/vn"
SEARCH_FIELDS = "id,title,alttitle,released"
FETCH_FIELDS = "id,description,released,developers.name"
SEARCH_RESULTS = 10

#: VNDB descriptions are BBCode; the text area takes plain text.
_BBCODE = re.compile(r"\[[^\]]*\]")


def resolve(game_id: str, target: str = "") -> str:
    """VNDB id to query: the dialog draft wins over ``[metadata] vndb_id``."""
    wanted = cfgmod.normalize_vndb_id(target)
    if wanted:
        return wanted
    try:
        return cfgmod.normalize_vndb_id(cfgmod.load(str(game_id)).metadata.vndb_id)
    except Exception:
        return ""


def _plain(text: object) -> str:
    """BBCode stripped and entities decoded, as the text area shows it."""
    return html.unescape(_BBCODE.sub("", str(text or ""))).strip()


def _developers(value: object) -> str:
    if not isinstance(value, list):
        return ""
    names: list[str] = []
    for part in value:
        name = str(part.get("name", "")).strip() if isinstance(part, dict) else ""
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _label(row: dict) -> str:
    """Candidate row: title, alternative title and release year."""
    title = str(row.get("title", "") or "").strip()
    alt = str(row.get("alttitle", "") or "").strip()
    label = f"{title} / {alt}" if alt and alt.casefold() != title.casefold() else title
    year = str(row.get("released", "") or "").strip()[:4]
    return f"{label} ({year})" if year.isdigit() else label


def _post(body: dict, timeout: int = 15) -> dict | None:
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("vndb request failed: %s", e)
        return None
    return payload if isinstance(payload, dict) else None


def search(query: str, timeout: int = 15) -> list[dict]:
    """Visual novels matching a title: [{"id", "name"}], best first."""
    term = str(query or "").strip()
    if not term:
        return []
    payload = _post(
        {
            "filters": ["search", "=", term],
            "fields": SEARCH_FIELDS,
            "results": SEARCH_RESULTS,
            "sort": "searchrank",
        },
        timeout,
    )
    rows = payload.get("results") if payload is not None else None
    if not isinstance(rows, list):
        return []
    found: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("id", "") or "").strip()
        if re.fullmatch(r"v\d+", vid):
            found.append({"id": vid, "name": _label(row)})
    return found


def fetch(game_id: str, target: str = "", timeout: int = 15) -> dict | None:
    """Fetch one visual novel's metadata. None on any failure or no entry."""
    vid = resolve(game_id, target)
    if not vid:
        return None
    payload = _post(
        {"filters": ["id", "=", vid], "fields": FETCH_FIELDS, "results": 1},
        timeout,
    )
    rows = payload.get("results") if payload is not None else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    data = rows[0]
    date = str(data.get("released", "") or "").strip()
    if not cfgmod.metadata_date_valid(date):
        date = ""
    return {
        "description": _plain(data.get("description")),
        "developer": _developers(data.get("developers")),
        "publisher": "",
        "genre": "",
        "series": "",
        "age_ratings": [],
        "date": date,
    }
