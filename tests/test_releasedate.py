"""Steam release date cache/fetch behavior (network stubbed)."""

import json
import time
import urllib.error

from tkarcade import releasedate as rdate


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


def test_parse_date():
    assert rdate.parse_date("28 Aug, 2025") == "2025-08-28"
    assert rdate.parse_date("1 Jan 2024") == "2024-01-01"
    # The store answers the same English locale month first when it likes.
    assert rdate.parse_date("Jun 11, 2021") == "2021-06-11"
    assert rdate.parse_date("2025 Aug 28") == "2025-08-28"
    assert rdate.parse_date("Coming soon") == ""
    assert rdate.parse_date("To be announced") == ""
    assert rdate.parse_date("Jun 2021") == ""
    assert rdate.parse_date("31 Feb, 2025") == ""
    assert rdate.parse_date(None) == ""


def test_fetch_and_cache_roundtrip(monkeypatch, xdg_env):
    _stub(
        monkeypatch,
        {"70": {"success": True, "data": {"release_date": {"date": "28 Aug, 2025"}}}},
    )
    assert rdate.refresh("steam-70") == "2025-08-28"
    assert rdate.cached("steam-70") == ("2025-08-28", True)
    assert rdate.cache_path("steam-70").is_file()


def test_canonical_id_caches_under_game_id_fetches_numeric(monkeypatch, xdg_env):
    seen = []

    def fake_open(url, timeout=15):
        seen.append(url)
        return _Resp({"70": {"data": {"release_date": {"date": "2 Feb, 2021"}}}})

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert rdate.refresh("steam-70") == "2021-02-02"
    assert seen == [rdate.ENDPOINT.format(appid="70")]
    assert rdate.cached("steam-70")[0] == "2021-02-02"
    assert rdate.fetch("local-doom") is None


def test_coming_soon_cached_empty(monkeypatch, xdg_env):
    _stub(monkeypatch, {"70": {"data": {"release_date": {"date": "Coming soon"}}}})
    assert rdate.refresh("steam-70") == ""
    assert rdate.cached("steam-70") == ("", True)


def test_stale_cache_returned_but_flagged(xdg_env):
    path = rdate.cache_path("71")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"saved": int(time.time()) - rdate.CACHE_TTL - 1, "date": "2020-05-04"})
    )
    assert rdate.cached("71") == ("2020-05-04", False)
    assert rdate.cached("72") == ("", False)


def test_fetch_failures_are_none(monkeypatch):
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert rdate.fetch("73") is None
    assert rdate.fetch("not-an-id") is None
    _stub(monkeypatch, payload=["not", "a", "dict"])
    assert rdate.fetch("74") is None
    _stub(monkeypatch, payload={"74": {"data": {"release_date": None}}})
    assert rdate.fetch("74") == ""


def test_stale_cache_types(xdg_env):
    path = rdate.cache_path("9")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"saved": "yesterday", "date": "2020-01-01"}', encoding="utf-8")
    assert rdate.cached("9") == ("", False)
