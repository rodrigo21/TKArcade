"""VNDB payloads (Kana API, stdlib urllib).

A local game without a Steam AppID is searched by title; the picked
visual novel saves in ``[metadata] vndb_id`` so the next download skips
the search. VNDB answers a synopsis, the developers and a release date.
Its releases each carry a date and publishers, so an optional pick in
``[metadata] vndb_release`` replaces the visual-novel date and fills the
publisher. Its tags land in ``[metadata] tags`` through Download
Metadata, filtered by rating and spoiler. Fetch Artwork takes the
visual novel's cover and a screenshot from the same endpoint. The cache
and the rate gate live in ``metadata.py``.
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
RELEASE_ENDPOINT = "https://api.vndb.org/kana/release"
SEARCH_FIELDS = "id,title,alttitle,released"
FETCH_FIELDS = "id,description,released,developers.name,tags.name,tags.rating,tags.spoiler"
ART_FIELDS = "image{url,dims,sexual,violence},screenshots{url,dims,sexual,violence}"
#: VNDB image flags run from 0 to 2 as an average vote; this marks explicit.
EXPLICIT_FLAG = 1.5
RELEASE_FIELDS = (
    "id,title,alttitle,released,platforms,languages.lang,official,"
    "vns.id,vns.rtype,producers.name,producers.developer,producers.publisher"
)
RELEASE_LINK_FIELDS = "id,released,producers.name,producers.publisher,vns.id"
RELEASE_ART_FIELDS = "id,images{id,type,url,dims,sexual,violence,photo},vns.id"
SEARCH_RESULTS = 10
#: Kana caps one page at 100 rows.
# shortcut: the first 100 releases; paginate when a visual novel exceeds it.
RELEASE_RESULTS = 100
#: VNDB tags: drop spoilers and weak tags, keep the strongest few.
TAG_MIN_RATING = 2.0
TAG_LIMIT = 20

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


def resolve_release(game_id: str, target: str = "", release: str = "") -> str:
    """Release id to query: the draft pick wins over ``[metadata] vndb_release``.

    An explicit target with an empty release means no release, so clearing
    the pick in the dialog beats a stored value; without a target both ids
    come from the config.
    """
    wanted = cfgmod.normalize_vndb_release(release)
    if wanted:
        return wanted
    if str(target or "").strip():
        return ""
    try:
        cfg = cfgmod.load(str(game_id))
    except Exception:
        return ""
    if not cfgmod.normalize_vndb_id(cfg.metadata.vndb_id):
        return ""
    return cfgmod.normalize_vndb_release(cfg.metadata.vndb_release)


def _plain(text: object) -> str:
    """BBCode stripped and entities decoded, as the text area shows it."""
    return html.unescape(_BBCODE.sub("", str(text or ""))).strip()


def _publishers(value: object) -> str:
    """Release producers flagged as publisher, deduplicated."""
    names: list[str] = []
    for part in value if isinstance(value, list) else []:
        if not isinstance(part, dict) or not part.get("publisher"):
            continue
        name = str(part.get("name", "")).strip()
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _langs(row: dict) -> list[str]:
    codes: list[str] = []
    for part in row.get("languages") if isinstance(row.get("languages"), list) else []:
        if not isinstance(part, dict):
            continue
        code = str(part.get("lang", "") or "").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def _linked_rtype(row: dict, vn_id: str) -> str:
    """This release's link type to the visual novel ("" when not linked)."""
    for part in row.get("vns") if isinstance(row.get("vns"), list) else []:
        if not isinstance(part, dict):
            continue
        if str(part.get("id", "")) == vn_id:
            return str(part.get("rtype", "") or "complete")
    return ""


def _release_name(row: dict, rtype: str) -> str:
    """Short combo label: title, date, platforms, languages and markers."""
    title = str(row.get("title", "") or "").strip() or "Release"
    parts = [str(row.get("released", "") or "").strip() or "TBA"]
    platforms = [str(code).strip() for code in row.get("platforms") or [] if str(code).strip()]
    if platforms:
        parts.append(", ".join(platforms))
    langs = _langs(row)
    if langs:
        parts.append(", ".join(langs))
    markers: list[str] = []
    if row.get("official") is False:
        markers.append("unofficial")
    if rtype != "complete":
        markers.append(rtype)
    label = f"{title} ({' · '.join(parts)})"
    return f"{label} [{', '.join(markers)}]" if markers else label


def _release_detail(row: dict) -> str:
    """Tooltip: alternative title, full lists, type and producers."""
    title = str(row.get("title", "") or "").strip()
    alt = str(row.get("alttitle", "") or "").strip()
    parts: list[str] = []
    if alt and alt.casefold() != title.casefold():
        parts.append(alt)
    date = str(row.get("released", "") or "").strip()
    parts.append(f"Released {date}" if date else "Release date unknown")
    platforms = [str(code).strip() for code in row.get("platforms") or [] if str(code).strip()]
    if platforms:
        parts.append(f"Platforms {', '.join(platforms)}")
    langs = _langs(row)
    if langs:
        parts.append(f"Languages {', '.join(langs)}")
    parts.append("Official" if row.get("official") else "Unofficial")
    producers: list[str] = []
    for part in row.get("producers") if isinstance(row.get("producers"), list) else []:
        if not isinstance(part, dict):
            continue
        name = str(part.get("name", "")).strip()
        if not name:
            continue
        roles = [role for role in ("developer", "publisher") if part.get(role)]
        producers.append(f"{name} ({', '.join(roles)})" if roles else name)
    if producers:
        parts.append(f"Producers: {'; '.join(producers)}")
    return " · ".join(parts)


def _developers(value: object) -> str:
    if not isinstance(value, list):
        return ""
    names: list[str] = []
    for part in value:
        name = str(part.get("name", "")).strip() if isinstance(part, dict) else ""
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _tags(value: object) -> list[str]:
    """Non-spoiler tags at or above the rating floor, strongest first."""
    rows: list[tuple[float, str]] = []
    for part in value if isinstance(value, list) else []:
        if not isinstance(part, dict):
            continue
        name = str(part.get("name", "")).strip()
        try:
            spoiler = int(part.get("spoiler") or 0)
            rating = float(part.get("rating") or 0)
        except (TypeError, ValueError):
            continue
        if name and spoiler == 0 and rating >= TAG_MIN_RATING:
            rows.append((-rating, name))
    rows.sort()
    out: list[str] = []
    for _rating, name in rows:
        if name not in out:
            out.append(name)
        if len(out) >= TAG_LIMIT:
            break
    return out


def _label(row: dict) -> str:
    """Candidate row: title, alternative title and release year."""
    title = str(row.get("title", "") or "").strip()
    alt = str(row.get("alttitle", "") or "").strip()
    label = f"{title} / {alt}" if alt and alt.casefold() != title.casefold() else title
    year = str(row.get("released", "") or "").strip()[:4]
    return f"{label} ({year})" if year.isdigit() else label


def _image_url(image: object) -> str:
    """Absolute URL of one Kana image object ("" when missing)."""
    if not isinstance(image, dict):
        return ""
    url = str(image.get("url", "") or "").strip()
    return "https:" + url if url.startswith("//") else url


def _flag(image: dict, key: str) -> float:
    try:
        return float(image.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _explicit(image: object) -> bool:
    """True when the image is flagged explicit or violent."""
    if not isinstance(image, dict):
        return False
    return _flag(image, "sexual") >= EXPLICIT_FLAG or _flag(image, "violence") >= EXPLICIT_FLAG


def _post(body: dict, timeout: int = 15, endpoint: str = ENDPOINT) -> dict | None:
    request = urllib.request.Request(
        endpoint,
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
            found.append(
                {
                    "id": vid,
                    "name": _label(row),
                    "title": str(row.get("title", "") or "").strip(),
                    "alt": str(row.get("alttitle", "") or "").strip(),
                }
            )
    return found


def releases(vn_id: str, timeout: int = 15) -> list[dict]:
    """Releases linked to a visual novel: [{"id", "name", "detail", "langs"}]."""
    wanted = cfgmod.normalize_vndb_id(vn_id)
    if not wanted:
        return []
    payload = _post(
        {
            "filters": ["vn", "=", ["id", "=", wanted]],
            "fields": RELEASE_FIELDS,
            "sort": "released",
            "results": RELEASE_RESULTS,
        },
        timeout,
        RELEASE_ENDPOINT,
    )
    rows = payload.get("results") if payload is not None else None
    if not isinstance(rows, list):
        return []
    found: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id", "") or "").strip()
        rtype = _linked_rtype(row, wanted)
        if not re.fullmatch(r"r\d+", rid) or not rtype:
            continue
        found.append(
            {
                "id": rid,
                "name": _release_name(row, rtype),
                "detail": _release_detail(row),
                "langs": _langs(row),
            }
        )
    return found


def _release(
    vn_id: str, release_id: str, timeout: int, fields: str = RELEASE_LINK_FIELDS
) -> dict | None:
    """The picked release, only while it still links this visual novel."""
    payload = _post(
        {"filters": ["id", "=", release_id], "fields": fields, "results": 1},
        timeout,
        RELEASE_ENDPOINT,
    )
    rows = payload.get("results") if payload is not None else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    return row if _linked_rtype(row, vn_id) else None


def fetch(game_id: str, target: str = "", timeout: int = 15, release: str = "") -> dict | None:
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
    publisher = ""
    picked = cfgmod.normalize_vndb_release(release)
    if picked:
        rel = _release(vid, picked, timeout)
        if rel is None:
            return None
        date = str(rel.get("released", "") or "").strip()
        publisher = _publishers(rel.get("producers"))
    if not cfgmod.metadata_date_valid(date):
        date = ""
    return {
        "description": _plain(data.get("description")),
        "developer": _developers(data.get("developers")),
        "publisher": publisher,
        "genre": "",
        "series": "",
        "age_ratings": [],
        "date": date,
        "tags": _tags(data.get("tags")),
    }


def _dims(image: object) -> str:
    """Pixel-size label for the chooser ("" when VNDB omits it)."""
    if not isinstance(image, dict):
        return ""
    dims = image.get("dims")
    if not isinstance(dims, list) or len(dims) != 2:
        return ""
    try:
        return f"{int(dims[0])}x{int(dims[1])}"
    except (TypeError, ValueError):
        return ""


def _art_option(image: dict, auto: bool = False, label: str = "") -> dict:
    url = _image_url(image)
    return {"url": url, "thumb": url, "auto": auto, "label": label, "note": _dims(image)}


def _release_covers(vn_id: str, release: str, timeout: int, safe: bool) -> list[dict]:
    """Packaging front covers of the picked release, after the link check."""
    rel = _release(vn_id, release, timeout, RELEASE_ART_FIELDS)
    images = rel.get("images") if rel else None
    rows: list[dict] = []
    for image in images if isinstance(images, list) else []:
        if not isinstance(image, dict) or image.get("type") != "pkgfront":
            continue
        if not _image_url(image) or (safe and _explicit(image)):
            continue
        rows.append(_art_option(image, label="Release Cover"))
    return rows


def art_options(
    vn_id: str, timeout: int = 15, safe: bool = False, release: str = ""
) -> tuple[dict[str, list[dict]], str]:
    """Candidate images per kind: ({"cover": [...], "banner": [...]}, error).

    The cover is the visual novel's own image, then the packaging front of
    the picked release; a release cover never displaces the main image and
    only turns automatic when there is none. The banner lists every
    screenshot, least flagged first, and the first row is the automatic
    pick. With `safe`, images flagged explicit or violent are dropped.
    Error tokens: "no-id", "not-found".
    """
    wanted = cfgmod.normalize_vndb_id(vn_id)
    if not wanted:
        return {}, "no-id"
    payload = _post(
        {"filters": ["id", "=", wanted], "fields": ART_FIELDS, "results": 1},
        timeout,
    )
    rows = payload.get("results") if payload is not None else None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return {}, "not-found"
    row = rows[0]
    out: dict[str, list[dict]] = {}
    image = row.get("image")
    if not (safe and _explicit(image)) and _image_url(image):
        out["cover"] = [_art_option(image, auto=True)]
    picked = cfgmod.normalize_vndb_release(release)
    if picked:
        known = {option["url"] for option in out.get("cover", [])}
        covers = [
            row for row in _release_covers(wanted, picked, timeout, safe) if row["url"] not in known
        ]
        if covers:
            if "cover" not in out:
                covers[0]["auto"] = True
            out.setdefault("cover", []).extend(covers)
    shots = row.get("screenshots")
    usable = [
        shot
        for shot in (shots if isinstance(shots, list) else [])
        if isinstance(shot, dict) and _image_url(shot) and not (safe and _explicit(shot))
    ]
    usable.sort(key=lambda shot: (_flag(shot, "sexual"), _flag(shot, "violence")))
    banner = [_art_option(shot, auto=not index) for index, shot in enumerate(usable)]
    if banner:
        out["banner"] = banner
    return (out, "") if out else ({}, "not-found")


def art(vn_id: str, timeout: int = 15, safe: bool = False) -> tuple[dict[str, str], str]:
    """Cover and banner URLs for one visual novel: ({"cover", "banner"}, error).

    Wraps `art_options` and keeps the automatic pick.
    """
    options, error = art_options(vn_id, timeout, safe)
    if error:
        return {}, error
    found = {kind: rows[0]["url"] for kind, rows in options.items() if rows}
    return (found, "") if found else ({}, "not-found")
