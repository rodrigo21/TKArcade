"""IGDB adapter: token cache, Apicalypse queries and the field mapping."""

import json
import urllib.error

from tkarcade import config as C
from tkarcade import igdb


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _creds(client_id="cid", secret="sec"):
    prefs = C.Preferences()
    prefs.igdb_client_id = client_id
    prefs.igdb_client_secret = secret
    C.save_preferences(prefs)


def _stub(monkeypatch, rows=None, token=None, error=None):
    calls = []

    def fake_open(request, timeout=15):
        calls.append(request)
        if error is not None:
            raise error
        if "id.twitch.tv" in request.full_url:
            return _Resp(
                token if token is not None else {"access_token": "tok", "expires_in": 3600}
            )
        return _Resp(rows if rows is not None else [])

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    return calls


def _api_calls(calls):
    return [call for call in calls if "api.igdb.com" in call.full_url]


def _token_calls(calls):
    return [call for call in calls if "id.twitch.tv" in call.full_url]


def test_missing_credentials_is_offline(monkeypatch, xdg_env):
    calls = _stub(monkeypatch)
    assert igdb.fetch("local-x", "1145360") is None
    assert igdb.search("Hades") == []
    assert calls == []


def test_credentials_are_stripped(xdg_env):
    _creds("  cid  ", "  sec  ")
    assert igdb.credentials() == ("cid", "sec")


def test_resolve_prefers_the_dialog_draft(xdg_env):
    cfg = C.GameConfig()
    cfg.general.appid = "local-x"
    cfg.metadata.igdb_id = "42"
    C.save(cfg)
    assert igdb.resolve("local-x") == "42"
    assert igdb.resolve("local-x", "7") == "7"
    assert igdb.resolve("local-x", "nope") == "42"


def test_fetch_maps_the_payload(monkeypatch, xdg_env):
    _creds()
    calls = _stub(
        monkeypatch,
        rows=[
            {
                "name": "Hades",
                "summary": "Escape the underworld.",
                "first_release_date": 1581379200,
                "genres": [{"name": "Adventure"}, {"name": "Indie"}],
                "franchises": [{"name": "Hades"}],
                "involved_companies": [
                    {
                        "company": {"name": "Supergiant Games"},
                        "developer": True,
                        "publisher": True,
                    },
                    {"company": {"name": "Private Division"}, "publisher": True},
                ],
                "age_ratings": [{"rating": 10}, {"rating": 3}],
            }
        ],
    )
    assert igdb.fetch("local-hades", "1145360") == {
        "description": "Escape the underworld.",
        "developer": "Supergiant Games",
        "publisher": "Supergiant Games, Private Division",
        "genre": "Adventure, Indie",
        "series": "Hades",
        "age_ratings": ["ESRB T", "PEGI 12"],
        "date": "2020-02-11",
    }
    request = _api_calls(calls)[0]
    assert "where id = 1145360;" in request.data.decode()
    assert request.get_header("Client-id") == "cid"
    assert request.get_header("Authorization") == "Bearer tok"


def test_search_labels_candidates(monkeypatch, xdg_env):
    _creds()
    _stub(
        monkeypatch,
        rows=[
            {"id": 1145360, "name": "Hades", "first_release_date": 1581379200},
            {"id": 2, "name": "Hades II"},
        ],
    )
    assert igdb.search("Hades") == [
        {"id": "1145360", "name": "Hades (2020)"},
        {"id": "2", "name": "Hades II"},
    ]


def test_search_escapes_quotes(monkeypatch, xdg_env):
    _creds()
    calls = _stub(monkeypatch, rows=[{"id": 10, "name": 'Half-"Life"'}])
    igdb.search('Half-"Life"')
    assert 'search "Half-\\"Life\\""' in _api_calls(calls)[0].data.decode()


def test_token_is_cached_between_calls(monkeypatch, xdg_env):
    _creds()
    calls = _stub(monkeypatch, rows=[])
    igdb.search("Hades")
    igdb.search("Hades")
    assert len(_token_calls(calls)) == 1


def test_token_renews_for_a_new_client_id(monkeypatch, xdg_env):
    _creds("cid-a")
    calls = _stub(monkeypatch, rows=[])
    igdb.search("Hades")
    _creds("cid-b")
    igdb.search("Hades")
    assert len(_token_calls(calls)) == 2


def test_unknown_ratings_and_bad_dates_are_dropped(monkeypatch, xdg_env):
    _creds()
    _stub(
        monkeypatch,
        rows=[
            {
                "age_ratings": [
                    {"rating": 7},
                    {"rating": 27},
                    {"rating": 39},
                    {"rating": 13},
                    {"rating": 13},
                ],
                "first_release_date": "TBA",
            }
        ],
    )
    data = igdb.fetch("local-x", "1")
    assert data["age_ratings"] == ["CERO A"]
    assert data["date"] == ""


def test_request_failure_returns_none(monkeypatch, xdg_env):
    _creds()
    _stub(
        monkeypatch,
        error=urllib.error.HTTPError(
            "https://api.igdb.com/v4/games", 401, "Unauthorized", {}, None
        ),
    )
    assert igdb.fetch("local-x", "1") is None
    assert igdb.search("Hades") == []
