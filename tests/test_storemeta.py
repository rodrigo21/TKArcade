"""Steam store metadata payload mapping (network stubbed)."""

import json
import urllib.error

from tkarcade import config as C
from tkarcade import storemeta as meta


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _stub(monkeypatch, payload=None, error=None):
    def fake_open(url, timeout=15):
        if error is not None:
            raise error
        return _Resp(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_open)


def test_rating_labels_exist_in_the_config():
    for board in meta.RATINGS.values():
        for label in board.values():
            assert label in C.AGE_RATINGS


def test_normalize_payload():
    out = meta.normalize(
        {
            "short_description": "Tom &amp; Jerry &quot;test&quot;",
            "developers": ["Valve", " "],
            "publishers": ["Valve"],
            "genres": [{"description": "Action"}, {"description": "Adventure"}],
            "franchise": "Witcher",
            "release_date": {"date": "28 Aug, 2025"},
            "ratings": {
                "esrb": {"rating": "m"},
                "pegi": {"rating": "18"},
                "usk": {"rating": "16"},
                "igrs": {"rating": "13"},
            },
        }
    )
    assert out["description"] == 'Tom & Jerry "test"'
    assert out["developer"] == "Valve"
    assert out["publisher"] == "Valve"
    assert out["genre"] == "Action, Adventure"
    assert out["series"] == "Witcher"
    assert out["age_ratings"] == ["ESRB M", "PEGI 18", "USK 16"]
    assert out["date"] == "2025-08-28"


def test_normalize_missing_fields():
    assert meta.normalize({}) == {
        "description": "",
        "developer": "",
        "publisher": "",
        "genre": "",
        "series": "",
        "age_ratings": [],
        "date": "",
    }
    assert meta.normalize({"release_date": {"date": "Coming soon"}})["date"] == ""


def test_local_game_uses_the_linked_appid(monkeypatch):
    seen = []

    def fake_open(url, timeout=15):
        seen.append(url)
        return _Resp({"620": {"data": {"short_description": "Portal"}}})

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert meta.fetch("local-doom", "620")["description"] == "Portal"
    assert seen == [meta.ENDPOINT.format(appid="620")]
    # No store link and no Steam ID: nothing to query.
    assert meta.fetch("local-doom") is None
    assert seen == [meta.ENDPOINT.format(appid="620")]


def test_fetch_failures_are_none(monkeypatch):
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert meta.fetch("73") is None
    _stub(monkeypatch, payload={"73": {"success": False}})
    assert meta.fetch("73") is None
    _stub(monkeypatch, payload={"73": {"data": []}})
    assert meta.fetch("73") is None
