"""Icon extraction from a Windows executable (thin icoextract wrapper)."""

import io
import sys
import types

from tkarcade import exeicon


class _FakeExtractor:
    """Stands in for `icoextract.IconExtractor`."""

    payload = b"ICO"

    def __init__(self, path):
        self.path = path

    def get_icon(self):
        return io.BytesIO(self.payload)


def _install(monkeypatch, extractor=_FakeExtractor):
    module = types.SimpleNamespace(IconExtractor=extractor)
    monkeypatch.setitem(sys.modules, "icoextract", module)


def test_exe_icon_returns_the_ico_bytes(monkeypatch, tmp_path):
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    _install(monkeypatch)
    assert exeicon.icon_bytes(exe) == b"ICO"


def test_non_exe_and_missing_path_have_no_icon(monkeypatch, tmp_path):
    _install(monkeypatch)
    assert exeicon.icon_bytes(tmp_path / "game.txt") is None
    assert exeicon.icon_bytes("") is None
    assert exeicon.icon_bytes(None) is None
    assert exeicon.icon_bytes(tmp_path / "gone.exe") is None


def test_extractor_failure_is_no_icon(monkeypatch, tmp_path):
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")

    def boom(path):
        raise ValueError("no icons")

    _install(monkeypatch, boom)
    assert exeicon.icon_bytes(exe) is None


def test_missing_dependency_is_no_icon(monkeypatch, tmp_path):
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setitem(sys.modules, "icoextract", None)
    assert exeicon.icon_bytes(exe) is None
