"""VNDB adapter: title search, payload mapping and the id resolution."""

import json
import urllib.error

from tkarcade import config as C
from tkarcade import vndb


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
    calls = []

    def fake_open(request, timeout=15):
        calls.append(request)
        if error is not None:
            raise error
        return _Resp(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    return calls


def test_search_labels_candidates(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        {
            "results": [
                {"id": "v2002", "title": "STEINS;GATE", "alttitle": None, "released": "2009-10-15"},
                {"id": "v93", "title": "Muv-Luv", "alttitle": "マブラヴ", "released": "2003"},
            ]
        },
    )
    assert vndb.search("Steins;Gate") == [
        {"id": "v2002", "name": "STEINS;GATE (2009)"},
        {"id": "v93", "name": "Muv-Luv / マブラヴ (2003)"},
    ]
    request = calls[0]
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {
        "filters": ["search", "=", "Steins;Gate"],
        "fields": "id,title,alttitle,released",
        "results": 10,
        "sort": "searchrank",
    }


def test_search_without_a_title_skips_the_network(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, {"results": []})
    assert vndb.search("  ") == []
    assert calls == []


def test_search_keeps_only_visual_novels(monkeypatch, xdg_env):
    _stub(monkeypatch, {"results": [{"id": "p42", "title": "NITRO PLUS"}, "junk"]})
    assert vndb.search("NITRO") == []


def test_fetch_maps_the_payload(monkeypatch, xdg_env):
    calls = _stub(
        monkeypatch,
        {
            "results": [
                {
                    "id": "v2002",
                    "description": "[b]Fate[/b] &amp; time [url=https://example]travel[/url]",
                    "released": "2009-10",
                    "developers": [
                        {"name": "NITRO PLUS"},
                        {"name": "MAGES."},
                        {"name": "NITRO PLUS"},
                    ],
                }
            ]
        },
    )
    assert vndb.fetch("local-sg", "V2002") == {
        "description": "Fate & time travel",
        "developer": "NITRO PLUS, MAGES.",
        "publisher": "",
        "genre": "",
        "series": "",
        "age_ratings": [],
        "date": "2009-10",
    }
    assert json.loads(calls[0].data)["filters"] == ["id", "=", "v2002"]


def test_fetch_drops_unknown_dates_and_fields(monkeypatch, xdg_env):
    _stub(
        monkeypatch,
        {"results": [{"id": "v1", "description": None, "released": "TBA", "developers": None}]},
    )
    data = vndb.fetch("local-x", "v1")
    assert data["date"] == ""
    assert data["description"] == ""
    assert data["developer"] == ""


def test_resolve_prefers_the_draft_then_the_config(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-sg"
    cfg.metadata.vndb_id = "v2003"
    C.save(cfg)
    assert vndb.resolve("local-sg") == "v2003"
    assert vndb.resolve("local-sg", "v2002") == "v2002"
    assert vndb.resolve("local-none") == ""


def test_network_failure_is_none_and_no_candidates(monkeypatch, xdg_env):
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert vndb.search("Steins;Gate") == []
    assert vndb.fetch("local-sg", "v2002") is None
