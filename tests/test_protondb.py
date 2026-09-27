"""ProtonDB cache/fetch behavior (network stubbed)."""

import json
import time
import urllib.error

from tksteamlaunch import protondb as pdb


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


def test_fetch_and_cache_roundtrip(monkeypatch, tmp_path, xdg_env):
    _stub(monkeypatch, {"tier": "gold", "total": 10})
    data = pdb.refresh("70")
    assert data == {"tier": "gold", "total": 10}
    cached, fresh = pdb.cached("70")
    assert cached == {"tier": "gold", "total": 10} and fresh is True


def test_stale_cache_returned_but_flagged(monkeypatch, xdg_env):
    import json as jsonlib

    path = pdb.cache_path("71")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        jsonlib.dumps({"saved": int(time.time()) - pdb.CACHE_TTL - 1, "data": {"tier": "silver"}})
    )
    cached, fresh = pdb.cached("71")
    assert cached == {"tier": "silver"} and fresh is False
    assert pdb.cached("72") == (None, False)


def test_fetch_failures_are_none(monkeypatch):
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert pdb.fetch("73") is None
    assert pdb.fetch("not-an-id") is None
    _stub(monkeypatch, payload=["not", "a", "dict"])
    assert pdb.fetch("74") is None


def test_tier_styles_complete():
    assert set(pdb.TIER_STYLE) == {"platinum", "gold", "silver", "bronze", "borked"}
    for bg, fg in pdb.TIER_STYLE.values():
        assert bg.startswith("#") and fg.startswith("#")


def test_stale_cache_types(xdg_env):
    from tksteamlaunch import protondb as pdb

    p = pdb.cache_path("9")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"saved": "yesterday", "data": {"tier": "gold"}}', encoding="utf-8")
    assert pdb.cached("9") == (None, False)
