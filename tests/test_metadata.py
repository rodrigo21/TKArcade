"""Metadata registry: cache keying and the provider rate gate (network stubbed)."""

import json
import time
import urllib.error

from tkarcade import metadata as md


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

    def fake_open(url, timeout=15):
        calls.append(url)
        if error is not None:
            raise error
        return _Resp(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    return calls


def _write_cache(provider, game_id, data, saved=None, target=None):
    path = md.cache_path(provider, game_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"saved": int(time.time()) if saved is None else saved, "data": data}
    if target is not None:
        payload["target"] = target
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_registry_declares_steam():
    steam = md.PROVIDERS["steam"]
    assert steam.label == "Steam"
    assert steam.needs_key is False
    assert steam.cache_dir == "steam-meta"
    assert steam.fields == md.FIELDS


def test_download_caches_and_reuses(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, {"70": {"data": {"short_description": "Hi"}}})
    assert md.download("steam", "steam-70")["description"] == "Hi"
    assert md.cache_path("steam", "steam-70").is_file()
    assert md.download("steam", "steam-70")["description"] == "Hi"
    assert len(calls) == 1


def test_changed_target_reads_as_not_cached(monkeypatch, xdg_env):
    calls = _stub(monkeypatch, {"620": {"data": {"short_description": "Portal"}}})
    assert md.download("steam", "local-doom", "620")["description"] == "Portal"
    assert md.cached("steam", "local-doom", "620")[1] is True
    # A changed store link must never fill the previous game's fields.
    assert md.cached("steam", "local-doom", "621") == (None, False)
    assert md.cached("steam", "local-doom") == (None, False)
    assert md.download("steam", "local-doom") is None
    assert len(calls) == 1


def test_stale_cache_is_flagged_and_refetched(monkeypatch, xdg_env):
    _write_cache("steam", "steam-9", {"series": "Old"}, saved=int(time.time()) - md.CACHE_TTL - 1)
    assert md.cached("steam", "steam-9") == ({"series": "Old"}, False)
    calls = _stub(monkeypatch, {"9": {"data": {"short_description": "New"}}})
    assert md.download("steam", "steam-9")["description"] == "New"
    assert md.cached("steam", "steam-9") == (
        {
            "description": "New",
            "developer": "",
            "publisher": "",
            "genre": "",
            "series": "",
            "age_ratings": [],
            "date": "",
        },
        True,
    )
    assert len(calls) == 1


def test_failed_fetch_leaves_the_cache_alone(monkeypatch, xdg_env):
    _write_cache("steam", "steam-9", {"series": "Old"}, saved=int(time.time()) - md.CACHE_TTL - 1)
    _stub(monkeypatch, error=urllib.error.URLError("down"))
    assert md.download("steam", "steam-9") is None
    assert md.cached("steam", "steam-9")[0] == {"series": "Old"}


def test_unknown_provider_is_none(xdg_env):
    assert md.download("nope", "steam-70") is None
    assert md.cached("nope", "steam-70") == (None, False)


def test_rate_gate_spaces_calls(monkeypatch):
    clock = {"now": 100.0}
    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(md.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(md.time, "sleep", fake_sleep)
    fake = md.Provider(
        label="Fake",
        cache_dir="fake-meta",
        fields=(),
        resolve=lambda game_id, target="": target or game_id,
        fetch=lambda game_id, target: None,
        min_interval=0.5,
    )
    monkeypatch.setitem(md.PROVIDERS, "fake", fake)
    monkeypatch.setitem(md._next_call, "fake", 0.0)
    md._gate("fake")
    assert sleeps == []
    md._gate("fake")
    assert sleeps == [0.5]
    md._gate("steam")  # Steam declares no interval and never waits.
    assert sleeps == [0.5]
