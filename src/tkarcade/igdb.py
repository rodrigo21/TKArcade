"""IGDB metadata payload (Apicalypse over HTTP, stdlib urllib).

IGDB needs a Twitch application: the client id and secret live in
``[ui]`` and an app access token is cached in the provider's cache dir,
renewed when it expires or the client id changes. A title search picks
one game, whose numeric id saves in ``[metadata] igdb_id`` so the next
download skips the search. The cache and the rate gate live in
``metadata.py``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from . import config as cfgmod
from . import xdg

log = logging.getLogger("tkarcade.igdb")

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
API_URL = "https://api.igdb.com/v4/games"
SEARCH_FIELDS = "id,name,first_release_date"
FETCH_FIELDS = (
    "name,summary,first_release_date,genres.name,franchises.name,"
    "themes.name,keywords.name,"
    "involved_companies.company.name,involved_companies.developer,"
    "involved_companies.publisher,age_ratings.rating"
)
#: Artwork kinds IGDB serves, with the size token its CDN takes. IGDB has
#: no square icon.
ART_FIELDS = "cover.url,artworks.url,screenshots.url"
ART_SIZES = {"cover": "t_720p", "banner": "t_1080p"}
SEARCH_RESULTS = 10

#: IGDB age-rating value -> ``config.AGE_RATINGS`` entry. The enum is one
#: global list, not per board; EC (7), GRAC_TESTING (27) and ACB_RC (39)
#: have no config label and stay out.
RATINGS: dict[int, str] = {
    1: "PEGI 3",
    2: "PEGI 7",
    3: "PEGI 12",
    4: "PEGI 16",
    5: "PEGI 18",
    6: "ESRB RP",
    8: "ESRB E",
    9: "ESRB E10+",
    10: "ESRB T",
    11: "ESRB M",
    12: "ESRB AO",
    13: "CERO A",
    14: "CERO B",
    15: "CERO C",
    16: "CERO D",
    17: "CERO Z",
    18: "USK 0",
    19: "USK 6",
    20: "USK 12",
    21: "USK 16",
    22: "USK 18",
    23: "GRAC All",
    24: "GRAC 12",
    25: "GRAC 15",
    26: "GRAC 18",
    28: "ClassInd L",
    29: "ClassInd 10",
    30: "ClassInd 12",
    31: "ClassInd 14",
    32: "ClassInd 16",
    33: "ClassInd 18",
    34: "ACB G",
    35: "ACB PG",
    36: "ACB M",
    37: "ACB MA15+",
    38: "ACB R18+",
}


def credentials() -> tuple[str, str]:
    """Twitch client id and secret from ``[ui]`` ("" when unset)."""
    try:
        prefs = cfgmod.load_preferences()
    except Exception:
        return "", ""
    return str(prefs.igdb_client_id or "").strip(), str(prefs.igdb_client_secret or "").strip()


def resolve(game_id: str, target: str = "") -> str:
    """IGDB numeric id to query: the dialog draft wins over ``[metadata] igdb_id``."""
    wanted = cfgmod.normalize_igdb_id(target)
    if wanted:
        return wanted
    try:
        return cfgmod.normalize_igdb_id(cfgmod.load(str(game_id)).metadata.igdb_id)
    except Exception:
        return ""


def _token_path():
    return xdg.app_cache_dir() / "igdb-meta" / ".token.json"


def _token(client_id: str, secret: str, timeout: int = 15) -> str:
    """Cached app token, renewed on expiry or a changed client id."""
    path = _token_path()
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        stored = None
    if isinstance(stored, dict) and stored.get("client_id") == client_id:
        try:
            if float(stored.get("expires", 0)) > time.time() + 60:
                token = str(stored.get("token", "") or "")
                if token:
                    return token
        except (TypeError, ValueError):
            pass
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": secret,
            "grant_type": "client_credentials",
        }
    ).encode("utf-8")
    request = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("igdb token request failed: %s", e)
        return ""
    token = str(payload.get("access_token", "") or "") if isinstance(payload, dict) else ""
    if not token:
        return ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "client_id": client_id,
                    "token": token,
                    "expires": int(time.time()) + int(payload.get("expires_in", 0) or 0),
                }
            ),
            encoding="utf-8",
        )
    except Exception as e:
        log.debug("igdb token cache write failed: %s", e)
    return token


def _query(body: str, timeout: int = 15) -> list[dict]:
    """One Apicalypse query; [] on a missing key, a failure or a bad answer."""
    client_id, secret = credentials()
    if not (client_id and secret):
        return []
    token = _token(client_id, secret, timeout)
    if not token:
        return []
    request = urllib.request.Request(
        API_URL,
        data=body.encode("utf-8"),
        headers={
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log.debug("igdb request failed: %s", e)
        return []
    return payload if isinstance(payload, list) else []


def _escaped(term: str) -> str:
    """Apicalypse string: backslashes and quotes cannot break the query."""
    return term.replace("\\", "\\\\").replace('"', '\\"')


def _date(value: object) -> str:
    """Unix release date -> ``YYYY-MM-DD``; "" when missing or invalid."""
    try:
        stamp = int(value)
    except (TypeError, ValueError):
        return ""
    try:
        text = datetime.fromtimestamp(stamp, tz=UTC).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return ""
    return text if cfgmod.metadata_date_valid(text) else ""


def _label(row: dict) -> str:
    """Candidate row: title and release year."""
    name = str(row.get("name", "") or "").strip()
    year = ""
    try:
        year = datetime.fromtimestamp(int(row.get("first_release_date")), tz=UTC).strftime("%Y")
    except (TypeError, ValueError, OSError):
        year = ""
    return f"{name} ({year})" if year else name


def _name_list(value: object) -> list[str]:
    """``name`` keys of a genre, franchise or company list, deduped."""
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for part in value:
        name = str(part.get("name", "")).strip() if isinstance(part, dict) else ""
        if name and name not in names:
            names.append(name)
    return names


def _names(value: object) -> str:
    """Joined ``name`` keys of a genre, franchise or company list."""
    return ", ".join(_name_list(value))


def _tags(data: dict) -> list[str]:
    """Genres, franchise, themes and keywords, as one tag list."""
    out: list[str] = []
    for key in ("genres", "franchises", "themes", "keywords"):
        for name in _name_list(data.get(key)):
            if name not in out:
                out.append(name)
    return out


def _companies(value: object, flag: str) -> str:
    """Companies whose ``developer``/``publisher`` flag is set."""
    if not isinstance(value, list):
        return ""
    names: list[str] = []
    for part in value:
        if not isinstance(part, dict) or not part.get(flag):
            continue
        company = part.get("company")
        name = str(company.get("name", "")).strip() if isinstance(company, dict) else ""
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _ratings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for part in value:
        if not isinstance(part, dict):
            continue
        try:
            label = RATINGS.get(int(part.get("rating")))
        except (TypeError, ValueError):
            label = None
        if label and label not in out:
            out.append(label)
    return out


def search(query: str, timeout: int = 15) -> list[dict]:
    """Games matching a title: [{"id", "name"}], best first."""
    term = str(query or "").strip()
    if not term:
        return []
    rows = _query(
        f'search "{_escaped(term)}"; fields {SEARCH_FIELDS}; limit {SEARCH_RESULTS};',
        timeout,
    )
    found: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        gid = str(row.get("id", "") or "").strip()
        if gid.isdigit():
            found.append({"id": gid, "name": _label(row)})
    return found


def fetch(game_id: str, target: str = "", timeout: int = 15) -> dict | None:
    """Fetch one IGDB game's metadata. None on any failure or no entry."""
    wanted = resolve(game_id, target)
    if not wanted:
        return None
    rows = _query(f"fields {FETCH_FIELDS}; where id = {wanted};", timeout)
    if not rows or not isinstance(rows[0], dict):
        return None
    data = rows[0]
    companies = data.get("involved_companies")
    return {
        "description": str(data.get("summary", "") or "").strip(),
        "developer": _companies(companies, "developer"),
        "publisher": _companies(companies, "publisher"),
        "genre": _names(data.get("genres")),
        "series": _names(data.get("franchises")),
        "age_ratings": _ratings(data.get("age_ratings")),
        "date": _date(data.get("first_release_date")),
        "tags": _tags(data),
    }


def _image(url: object, size: str) -> str:
    """Absolute CDN URL at the requested size token ("" when missing)."""
    text = str(url or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        text = "https:" + text
    return text.replace("/t_thumb/", f"/{size}/")


def art(game_id: str, target: str = "", timeout: int = 15) -> tuple[dict[str, str], str]:
    """Cover and banner URLs for one game: ({"cover", "banner"}, error).

    IGDB has no square icon. The banner is the first artwork and falls
    back to a screenshot, both 16:9; the views crop it into their box.
    Error tokens: "no-igdb-key", "no-id", "not-found".
    """
    client_id, secret = credentials()
    if not (client_id and secret):
        return {}, "no-igdb-key"
    wanted = resolve(game_id, target)
    if not wanted:
        return {}, "no-id"
    rows = _query(f"fields {ART_FIELDS}; where id = {wanted};", timeout)
    if not rows or not isinstance(rows[0], dict):
        return {}, "not-found"
    data = rows[0]
    cover = data.get("cover")
    cover_url = _image(cover.get("url") if isinstance(cover, dict) else "", ART_SIZES["cover"])
    banner_url = ""
    for key in ("artworks", "screenshots"):
        entries = data.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("url"):
                banner_url = _image(entry["url"], ART_SIZES["banner"])
                break
        if banner_url:
            break
    found = {kind: url for kind, url in (("cover", cover_url), ("banner", banner_url)) if url}
    return (found, "") if found else ({}, "not-found")
