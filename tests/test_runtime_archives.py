"""Runtime archive downloads and safe extraction (no network, no Qt)."""

import hashlib
import io
import json
import stat
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from tkarcade import runtime_archives as A
from tkarcade import xdg

API_URLS = {
    "dxvk": "https://api.github.com/repos/doitsujin/dxvk/releases/latest",
    "vkd3d": "https://api.github.com/repos/HansKristian-Work/vkd3d-proton/releases/latest",
}


def _tar_bytes(root: str, files: dict[str, bytes], mode: str = "w:gz") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=mode) as tf:
        for rel, data in files.items():
            info = tarfile.TarInfo(f"{root}/{rel}" if root else rel)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zstd_bytes(data: bytes) -> bytes:
    try:
        from compression import zstd
    except ImportError:
        zstandard = pytest.importorskip("zstandard")
        return zstandard.ZstdCompressor().compress(data)
    return zstd.compress(data)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _opener(payloads: dict[str, bytes]):
    calls: list[str] = []

    def opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        return io.BytesIO(payloads[url])

    return opener, calls


def _release_payload(kind: str, name: str, url: str, data: bytes) -> bytes:
    return json.dumps(
        {
            "assets": [
                {
                    "name": name,
                    "browser_download_url": url,
                    "size": len(data),
                    "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                }
            ]
        }
    ).encode()


def _installed(kind: str, name: str) -> Path:
    return xdg.runtimes_dir() / kind / name


def test_latest_release_picks_preferred_asset(xdg_env):
    payload = json.dumps(
        {
            "assets": [
                {"name": "dxvk-2.7.1.zip", "browser_download_url": "https://x/d.zip"},
                {
                    "name": "dxvk-2.7.1.tar.gz",
                    "browser_download_url": "https://x/d.tar.gz",
                    "size": 12,
                    "digest": "sha256:abc",
                },
            ]
        }
    ).encode()
    opener, calls = _opener({API_URLS["dxvk"]: payload})
    release = A.latest_release("dxvk", opener)
    assert release == {
        "name": "dxvk-2.7.1.tar.gz",
        "url": "https://x/d.tar.gz",
        "size": 12,
        "digest": "sha256:abc",
        "tag": "",
    }
    assert calls == [API_URLS["dxvk"]]


def test_latest_release_requires_a_matching_asset(xdg_env):
    opener, _calls = _opener({API_URLS["dxvk"]: b'{"assets": []}'})
    with pytest.raises(A.ArchiveError, match="no dxvk archive"):
        A.latest_release("dxvk", opener)
    with pytest.raises(A.ArchiveError, match="unknown runtime kind"):
        A.latest_release("wine", opener)


def test_latest_release_surfaces_api_errors(xdg_env):
    def opener(request, timeout=None):
        raise OSError("HTTP 403")

    with pytest.raises(A.ArchiveError, match="HTTP 403"):
        A.latest_release("dxvk", opener)


def test_download_latest_extracts_and_cleans_up(xdg_env):
    data = _tar_bytes("dxvk-2.7.1", {"x64/d3d11.dll": b"dll", "x64/dxgi.dll": b"dll"})
    asset = "https://x/dxvk-2.7.1.tar.gz"
    opener, _calls = _opener(
        {API_URLS["dxvk"]: _release_payload("dxvk", "dxvk-2.7.1.tar.gz", asset, data), asset: data}
    )
    messages: list[str] = []
    assert A.download_latest("dxvk", opener, messages.append) == ""
    target = _installed("dxvk", "dxvk-2.7.1")
    assert (target / "x64" / "d3d11.dll").read_bytes() == b"dll"
    cache = xdg.archives_cache_dir()
    assert list(cache.iterdir()) == []
    assert any("Installed dxvk-2.7.1" in m for m in messages)


def test_download_latest_rejects_wrong_digest(xdg_env):
    data = _tar_bytes("dxvk-2.7.1", {"x64/d3d11.dll": b"dll"})
    asset = "https://x/dxvk-2.7.1.tar.gz"
    payload = json.dumps(
        {
            "assets": [
                {
                    "name": "dxvk-2.7.1.tar.gz",
                    "browser_download_url": asset,
                    "digest": "sha256:" + "0" * 64,
                }
            ]
        }
    ).encode()
    opener, _calls = _opener({API_URLS["dxvk"]: payload, asset: data})
    message = A.download_latest("dxvk", opener)
    assert "does not match" in message
    assert not _installed("dxvk", "dxvk-2.7.1").exists()
    assert list(xdg.archives_cache_dir().iterdir()) == []


def test_extract_archive_detects_kind_and_skips_existing(xdg_env, tmp_path):
    data = _tar_bytes("vkd3d-proton-3.1", {"x64/d3d12.dll": b"dll"})
    archive = tmp_path / "vkd3d-proton-3.1.tar.gz"
    archive.write_bytes(data)
    first = A.extract_archive(archive)
    assert first == _installed("vkd3d", "vkd3d-proton-3.1")
    assert (first / "x64" / "d3d12.dll").is_file()
    assert A.extract_archive(archive) == first
    assert not list(xdg.runtimes_dir().glob(".staging-*"))


def test_extract_archive_reads_tar_zst(xdg_env, tmp_path):
    plain = _tar_bytes("dxvk-2.7.1", {"x64/d3d11.dll": b"dll"}, mode="w")
    archive = tmp_path / "dxvk-2.7.1.tar.zst"
    archive.write_bytes(_zstd_bytes(plain))
    assert A.extract_archive(archive) == _installed("dxvk", "dxvk-2.7.1")


def test_extract_archive_reads_zip(xdg_env, tmp_path):
    archive = tmp_path / "dxvk-2.7.1.zip"
    archive.write_bytes(_zip_bytes({"dxvk-2.7.1/x64/d3d11.dll": b"dll"}))
    assert A.extract_archive(archive) == _installed("dxvk", "dxvk-2.7.1")


def test_extract_rejects_tar_traversal(xdg_env, tmp_path):
    archive = tmp_path / "evil.tar.gz"
    archive.write_bytes(_tar_bytes("", {"../escape": b"x", "dxvk-2.7.1/x64/d3d11.dll": b"d"}))
    with pytest.raises(A.ArchiveError):
        A.extract_archive(archive)
    assert not (xdg.runtimes_dir().parent / "escape").exists()


def test_extract_rejects_zip_traversal_and_symlinks(xdg_env, tmp_path):
    traversal = tmp_path / "evil.zip"
    traversal.write_bytes(_zip_bytes({"../escape": b"x"}))
    with pytest.raises(A.ArchiveError, match="unsafe archive member"):
        A.extract_archive(traversal)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("dxvk-2.7.1/x64/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "target")
    link = tmp_path / "link.zip"
    link.write_bytes(buf.getvalue())
    with pytest.raises(A.ArchiveError, match="symlink"):
        A.extract_archive(link)


def test_extract_requires_one_version_directory(xdg_env, tmp_path):
    flat = tmp_path / "flat.tar.gz"
    flat.write_bytes(_tar_bytes("", {"x64/d3d11.dll": b"dll"}))
    with pytest.raises(A.ArchiveError, match="top-level version directory"):
        A.extract_archive(flat)


def test_extract_caps_members_and_size(xdg_env, tmp_path, monkeypatch):
    two = tmp_path / "two.zip"
    two.write_bytes(_zip_bytes({"a/x": b"", "b/x": b""}))
    monkeypatch.setattr(A, "MAX_MEMBERS", 1)
    with pytest.raises(A.ArchiveError, match="too many entries"):
        A.extract_archive(two)
    monkeypatch.setattr(A, "MAX_MEMBERS", 20_000)
    monkeypatch.setattr(A, "MAX_EXTRACTED_BYTES", 1)
    big = tmp_path / "big.zip"
    big.write_bytes(_zip_bytes({"dxvk-1/x64/d3d11.dll": b"two bytes"}))
    with pytest.raises(A.ArchiveError, match="size cap"):
        A.extract_archive(big)


def test_sync_extracts_cache_and_keeps_user_files(xdg_env, tmp_path):
    cache = xdg.archives_cache_dir()
    cache.mkdir(parents=True)
    archive = cache / "dxvk-2.7.1.tar.gz"
    archive.write_bytes(_tar_bytes("dxvk-2.7.1", {"x64/d3d11.dll": b"dll"}))
    (xdg.runtimes_dir() / ".staging-stale").mkdir(parents=True)
    assert A.sync_archives() == ["dxvk-2.7.1"]
    assert archive.is_file()
    assert A.sync_archives() == []
    assert not (xdg.runtimes_dir() / ".staging-stale").exists()


def test_sync_reports_failures_through_progress(xdg_env):
    cache = xdg.archives_cache_dir()
    cache.mkdir(parents=True)
    (cache / "broken.zip").write_bytes(b"not a zip")
    messages: list[str] = []
    assert A.sync_archives(messages.append) == []
    assert messages and messages[0].startswith("broken.zip:")


def test_zstd_needs_a_backend(xdg_env, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "compression", None)
    monkeypatch.setitem(sys.modules, "zstandard", None)
    with (
        pytest.raises(A.ArchiveError, match="zstd archives need"),
        A._zstd_stream(tmp_path / "x.tar.zst"),
    ):
        pass


def test_latest_release_reports_the_tag(xdg_env):
    payload = json.dumps(
        {
            "tag_name": "v2.7.1",
            "assets": [{"name": "dxvk-2.7.1.tar.gz", "browser_download_url": "https://x/d.tar.gz"}],
        }
    ).encode()
    opener, _calls = _opener({API_URLS["dxvk"]: payload})
    assert A.latest_release("dxvk", opener)["tag"] == "v2.7.1"


def test_latest_release_uses_the_configured_repo(xdg_env):
    url = "https://api.github.com/repos/Someone/dxvk-sarek/releases/latest"
    opener, calls = _opener({url: b'{"assets": []}'})
    with pytest.raises(A.ArchiveError, match="no dxvk archive"):
        A.latest_release("dxvk", opener, repo="Someone/dxvk-sarek")
    assert calls == [url]


@pytest.mark.parametrize("repo", ["nope", "a/b/c", "../x/y", "doitsujin/dxvk?"])
def test_repo_rejects_invalid_values(xdg_env, repo):
    with pytest.raises(A.ArchiveError, match="invalid GitHub repository"):
        A.latest_release("dxvk", repo=repo)


def test_releases_skips_drafts_and_unmatched_assets(xdg_env):
    url = "https://api.github.com/repos/doitsujin/dxvk/releases?per_page=30"
    payload = json.dumps(
        [
            {
                "tag_name": "v3.0",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {"name": "dxvk-3.0.zip", "browser_download_url": "https://x/z.zip"},
                    {
                        "name": "dxvk-3.0.tar.gz",
                        "browser_download_url": "https://x/a.tar.gz",
                        "size": 5,
                        "digest": "sha256:aa",
                    },
                ],
            },
            {
                "tag_name": "v2.9",
                "draft": True,
                "assets": [
                    {"name": "dxvk-2.9.tar.gz", "browser_download_url": "https://x/b.tar.gz"}
                ],
            },
            {"tag_name": "notes", "draft": False, "assets": []},
            {
                "tag_name": "v3.1",
                "prerelease": True,
                "assets": [
                    {"name": "dxvk-3.1.tar.gz", "browser_download_url": "https://x/c.tar.gz"}
                ],
            },
        ]
    ).encode()
    opener, _calls = _opener({url: payload})
    rows = A.releases("dxvk", opener)
    assert [r["tag"] for r in rows] == ["v3.0", "v3.1"]
    assert rows[0]["name"] == "dxvk-3.0.tar.gz" and rows[0]["digest"] == "sha256:aa"
    assert rows[1]["prerelease"] is True


def test_releases_surface_api_errors(xdg_env):
    def opener(request, timeout=None):
        raise OSError("HTTP 403")

    with pytest.raises(A.ArchiveError, match="could not list dxvk releases"):
        A.releases("dxvk", opener)


def test_download_release_installs_the_picked_asset(xdg_env):
    data = _tar_bytes("dxvk-2.6.0", {"x64/d3d11.dll": b"dll"})
    asset = "https://x/dxvk-2.6.0.tar.gz"
    opener, _calls = _opener({asset: data})
    messages: list[str] = []
    assert (
        A.download_release(
            "dxvk",
            {
                "name": "dxvk-2.6.0.tar.gz",
                "url": asset,
                "size": len(data),
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                "tag": "v2.6.0",
            },
            opener,
            messages.append,
        )
        == ""
    )
    assert (_installed("dxvk", "dxvk-2.6.0") / "x64" / "d3d11.dll").read_bytes() == b"dll"
    source = A.sources()["dxvk/dxvk-2.6.0"]
    assert source["origin"] == "github" and source["tag"] == "v2.6.0"


def test_install_from_url_names_the_archive_by_its_basename(xdg_env):
    data = _tar_bytes("dxvk-sarek-2.4.1", {"x64/d3d11.dll": b"dll"})
    asset = "https://x/builds/dxvk-sarek-2.4.1.tar.gz"
    opener, _calls = _opener({asset: data})
    assert A.install_from_url("dxvk", asset, opener) == ""
    assert (_installed("dxvk", "dxvk-sarek-2.4.1") / "x64" / "d3d11.dll").is_file()
    assert A.sources()["dxvk/dxvk-sarek-2.4.1"]["origin"] == "url"
    assert list(xdg.archives_cache_dir().iterdir()) == []


def test_install_from_url_rejects_a_missing_name_or_unsupported_suffix(xdg_env):
    assert "only https://" in A.install_from_url("dxvk", "http://x/dxvk.tar.gz")
    assert "no file name" in A.install_from_url("dxvk", "https://x/")
    assert "unsupported archive" in A.install_from_url("dxvk", "https://x/dxvk.tar.xz")
    assert "unknown runtime kind" in A.install_from_url("wine", "https://x/d.tar.gz")


def test_remove_version_deletes_only_managed_versions(xdg_env, tmp_path):
    managed = _installed("dxvk", "dxvk-2.7.1")
    (managed / "x64").mkdir(parents=True)
    (managed / "x64" / "d3d11.dll").write_bytes(b"dll")
    A._record_source("dxvk", managed, "github", "doitsujin/dxvk", "v2.7.1", "https://x/d.tar.gz")
    assert A.sources()["dxvk/dxvk-2.7.1"]["tag"] == "v2.7.1"
    assert A.remove_version("dxvk", "dxvk-2.7.1") == ""
    assert not managed.exists()
    assert A.sources() == {}
    assert "dxvk-2.7.1" not in A._sources_path().read_text(encoding="utf-8")

    outside = tmp_path / "user-dxvk"
    (outside / "x64").mkdir(parents=True)
    assert "not a managed version" in A.remove_version("dxvk", str(outside))
    assert outside.is_dir()
    assert "not a managed version" in A.remove_version("dxvk", "../escape")
    assert "Unknown runtime kind" in A.remove_version("wine", "dxvk-2.7.1")


def test_remove_version_refuses_symlinks(xdg_env, tmp_path):
    target = tmp_path / "real"
    (target / "x64").mkdir(parents=True)
    link = xdg.runtimes_dir() / "dxvk" / "linked"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    assert "not a managed version" in A.remove_version("dxvk", "linked")
    assert target.is_dir()


def test_sources_drops_orphans_and_survives_a_broken_file(xdg_env):
    (xdg.runtimes_dir() / "dxvk" / "dxvk-2.7.1").mkdir(parents=True)
    A._write_sources(
        {
            "dxvk/dxvk-2.7.1": {"origin": "github"},
            "dxvk/gone": {"origin": "url"},
            "junk": "not a dict",
        }
    )
    assert set(A.sources()) == {"dxvk/dxvk-2.7.1"}
    A._sources_path().write_text("{not json", encoding="utf-8")
    assert A.sources() == {}


def _managed(kind: str, names: list[str]) -> dict[str, dict]:
    """Create managed version dirs and a .sources.json with ordered dates."""
    root = xdg.runtimes_dir() / kind
    data = {}
    for index, name in enumerate(names):
        (root / name).mkdir(parents=True)
        data[f"{kind}/{name}"] = {
            "origin": "github",
            "repo": "doitsujin/dxvk",
            "tag": name,
            "url": "",
            "at": f"2026-01-{index + 1:02d}T00:00:00Z",
        }
    A._write_sources(A.sources() | data)
    return data


def test_prune_keeps_the_newest_three(xdg_env):
    _managed("dxvk", ["dxvk-1", "dxvk-2", "dxvk-3", "dxvk-4"])
    removed = A.prune_versions()
    assert removed == ["dxvk/dxvk-1"]
    root = xdg.runtimes_dir() / "dxvk"
    assert sorted(p.name for p in root.iterdir()) == ["dxvk-2", "dxvk-3", "dxvk-4"]
    assert set(A.sources()) == {"dxvk/dxvk-2", "dxvk/dxvk-3", "dxvk/dxvk-4"}


def test_prune_never_deletes_the_default_or_a_game_pin(xdg_env):
    from tkarcade import config as C

    _managed("dxvk", ["dxvk-1", "dxvk-2", "dxvk-3", "dxvk-4"])
    prefs = C.load_preferences()
    prefs.dxvk_default = "dxvk-1"
    C.save_preferences(prefs)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.graphics.dxvk_version = "dxvk-2"
    C.save(cfg)
    removed = A.prune_versions()
    assert removed == []
    root = xdg.runtimes_dir() / "dxvk"
    assert sorted(p.name for p in root.iterdir()) == ["dxvk-1", "dxvk-2", "dxvk-3", "dxvk-4"]


def test_prune_ignores_unrecorded_versions(xdg_env):
    root = xdg.runtimes_dir() / "dxvk"
    for name in ("dxvk-1", "dxvk-2", "dxvk-3", "dxvk-4", "dropped"):
        (root / name).mkdir(parents=True)
    _managed("dxvk", ["dxvk-5", "dxvk-6", "dxvk-7", "dxvk-8"])
    removed = A.prune_versions()
    assert removed == ["dxvk/dxvk-5"]
    assert (root / "dropped").is_dir()
    assert sorted(p.name for p in root.iterdir()) == [
        "dropped",
        "dxvk-1",
        "dxvk-2",
        "dxvk-3",
        "dxvk-4",
        "dxvk-6",
        "dxvk-7",
        "dxvk-8",
    ]


def test_prune_disabled_with_zero(xdg_env):
    _managed("vkd3d", ["vkd3d-1", "vkd3d-2", "vkd3d-3", "vkd3d-4"])
    assert A.prune_versions(0) == []
    assert len(list((xdg.runtimes_dir() / "vkd3d").iterdir())) == 4


def test_download_uses_the_configured_mirror(xdg_env):
    from tkarcade import config as C

    prefs = C.load_preferences()
    prefs.download_mirror = "https://mirror.test/"
    C.save_preferences(prefs)
    data = _tar_bytes("dxvk-2.7.0", {"x64/d3d11.dll": b"dll"})
    original = "https://github.com/doitsujin/dxvk/releases/download/v2.7.0/dxvk-2.7.0.tar.gz"
    mirrored = "https://mirror.test/" + original
    opener, _calls = _opener({mirrored: data})
    assert (
        A.download_release(
            "dxvk",
            {
                "name": "dxvk-2.7.0.tar.gz",
                "url": original,
                "size": len(data),
                "digest": "",
                "tag": "v2.7.0",
            },
            opener,
        )
        == ""
    )
    assert (_installed("dxvk", "dxvk-2.7.0") / "x64" / "d3d11.dll").is_file()


def test_pasted_url_ignores_the_mirror(xdg_env):
    from tkarcade import config as C

    prefs = C.load_preferences()
    prefs.download_mirror = "https://mirror.test"
    C.save_preferences(prefs)
    data = _tar_bytes("dxvk-sarek-2.4.2", {"x64/d3d11.dll": b"dll"})
    original = "https://example.test/builds/dxvk-sarek-2.4.2.tar.gz"
    opener, _calls = _opener({original: data})
    assert A.install_from_url("dxvk", original, opener) == ""
    assert (_installed("dxvk", "dxvk-sarek-2.4.2") / "x64" / "d3d11.dll").is_file()
