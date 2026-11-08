"""Runtime archive downloads and extraction (GUI-only helper).

The launcher never imports this module: downloads, digest checks and
unpacking stay on the GUI side, while `runtimes.graphics_versions` only
reads the managed installs it writes. Stdlib first: `compression.zstd`
covers Python 3.14+, and the `zstandard` package is imported lazily as
the fallback for older interpreters (marker dependency in pyproject).
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from . import runtimes, xdg

#: kind -> (GitHub repo, preferred asset suffixes)
LAYERS = {
    "dxvk": ("doitsujin/dxvk", (".tar.gz", ".zip")),
    "vkd3d": ("HansKristian-Work/vkd3d-proton", (".tar.zst", ".tar.gz", ".zip")),
}
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024
MAX_MEMBERS = 20_000
_TIMEOUT = 20
_USER_AGENT = "TKArcade"


class ArchiveError(RuntimeError):
    """A download or extraction step refused to continue."""


def _open_url(request, timeout: float = _TIMEOUT):
    return urllib.request.urlopen(request, timeout=timeout)


def _remove(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def _archive_format(name: str) -> str:
    low = name.lower()
    for suffix, fmt in (
        (".tar.gz", "tar.gz"),
        (".tgz", "tar.gz"),
        (".tar.zst", "tar.zst"),
        (".tzst", "tar.zst"),
        (".zip", "zip"),
    ):
        if low.endswith(suffix):
            return fmt
    raise ArchiveError(f"unsupported archive: {name}")


def _repo(kind: str, repo: str = "") -> str:
    """GitHub owner/repo for a layer: the configured one, else the official."""
    default = LAYERS.get(kind, ("", ()))[0]
    if not default:
        raise ArchiveError(f"unknown runtime kind: {kind!r}")
    text = str(repo or "").strip().strip("/")
    if not text:
        return default
    parts = text.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9._-]+", p) for p in parts):
        raise ArchiveError(f"invalid GitHub repository: {repo!r}")
    return text


def _source_for(kind: str, repo: str) -> tuple[str, str]:
    """(origin label, repository) for the configured source of a layer."""
    official = _repo(kind)
    wanted = _repo(kind, repo)
    return ("github" if wanted == official else "repo"), wanted


def _pick_asset(assets, suffixes) -> dict | None:
    """First asset whose name matches a preferred suffix (None = no match)."""
    for suffix in suffixes:
        for asset in assets or []:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name.endswith(suffix) and url:
                return {
                    "name": name,
                    "url": url,
                    "size": int(asset.get("size") or 0),
                    "digest": str(asset.get("digest") or ""),
                }
    return None


def latest_release(kind: str, opener=None, repo: str = "") -> dict:
    """Newest GitHub release asset for a layer (name, url, size, digest, tag)."""
    repo = _repo(kind, repo)
    open_url = opener or _open_url
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with open_url(request, timeout=_TIMEOUT) as response:
            data = json.load(response)
    except ArchiveError:
        raise
    except Exception as e:
        raise ArchiveError(f"could not query the latest {kind} release: {e}") from e
    assets = data.get("assets") if isinstance(data, dict) else None
    asset = _pick_asset(assets, LAYERS[kind][1])
    if asset is None:
        raise ArchiveError(f"no {kind} archive in the latest release")
    asset["tag"] = str(data.get("tag_name") or "")
    return asset


def releases(kind: str, opener=None, repo: str = "") -> list[dict]:
    """GitHub releases for a layer, newest first (drafts skipped)."""
    repo = _repo(kind, repo)
    open_url = opener or _open_url
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases?per_page=30",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with open_url(request, timeout=_TIMEOUT) as response:
            data = json.load(response)
    except ArchiveError:
        raise
    except Exception as e:
        raise ArchiveError(f"could not list {kind} releases: {e}") from e
    if not isinstance(data, list):
        raise ArchiveError(f"unexpected {kind} release list")
    out = []
    for entry in data:
        if not isinstance(entry, dict) or entry.get("draft"):
            continue
        asset = _pick_asset(entry.get("assets"), LAYERS[kind][1])
        if asset is None:
            continue
        asset["tag"] = str(entry.get("tag_name") or "")
        asset["prerelease"] = bool(entry.get("prerelease"))
        out.append(asset)
    return out


def _download(release: dict, part: Path, opener) -> str:
    """Stream the asset to `part`, returning the SHA-256 hex digest."""
    if int(release.get("size") or 0) > MAX_DOWNLOAD_BYTES:
        raise ArchiveError("archive exceeds the download size cap")
    open_url = opener or _open_url
    request = urllib.request.Request(release["url"], headers={"User-Agent": _USER_AGENT})
    hasher = hashlib.sha256()
    written = 0
    try:
        with open_url(request, timeout=_TIMEOUT) as response, open(part, "wb") as fh:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_DOWNLOAD_BYTES:
                    raise ArchiveError("download exceeds the size cap")
                hasher.update(chunk)
                fh.write(chunk)
    except ArchiveError:
        raise
    except Exception as e:
        raise ArchiveError(f"download failed: {e}") from e
    if not written:
        raise ArchiveError("downloaded archive is empty")
    return hasher.hexdigest()


def _verify_digest(digest: str, actual: str) -> None:
    algo, _, expected = str(digest or "").partition(":")
    if algo.lower() != "sha256" or not expected:
        return
    if expected.lower() != actual:
        raise ArchiveError("downloaded archive does not match the release digest")


def _sources_path() -> Path:
    return xdg.runtimes_dir() / ".sources.json"


def sources() -> dict[str, dict]:
    """Provenance per "<kind>/<name>", pruned to versions still installed.

    GUI-only bookkeeping: the launcher never reads it, and a hand-deleted
    version directory simply drops out here.
    """
    try:
        data = json.loads(_sources_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    root = xdg.runtimes_dir()
    out: dict[str, dict] = {}
    for key, value in data.items():
        kind, _, name = str(key).partition("/")
        if not name or not isinstance(value, dict):
            continue
        if (root / kind / name).is_dir():
            out[str(key)] = dict(value)
    return out


def _write_sources(data: dict[str, dict]) -> None:
    root = xdg.runtimes_dir()
    root.mkdir(parents=True, exist_ok=True)
    part = _sources_path().with_name(".sources.json.part")
    part.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(part, _sources_path())


def _record_source(
    kind: str, version_dir: Path, origin: str, repo: str, tag: str, url: str
) -> None:
    data = sources()
    data[f"{kind}/{version_dir.name}"] = {
        "origin": origin,
        "repo": repo,
        "tag": tag,
        "url": url,
        "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        _write_sources(data)
    except OSError:
        pass  # provenance is advisory: a read-only data dir must not fail a install


def _install_asset(kind: str, asset: dict, opener, say, origin: str, repo: str = "") -> str:
    """Download an archive asset, extract it and record where it came from."""
    name = xdg.safe_stem(Path(str(asset.get("name") or "")).name)
    _archive_format(name)
    cache = xdg.archives_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / name
    part = cache / (name + ".part")
    try:
        say(f"Downloading {name}…")
        digest = _download({**asset, "name": name}, part, opener)
        _verify_digest(asset.get("digest", ""), digest)
        os.replace(part, dest)
        say(f"Extracting {name}…")
        installed = extract_archive(dest, kind)
        _record_source(
            kind, installed, origin, repo, str(asset.get("tag") or ""), str(asset.get("url") or "")
        )
        _remove(dest)
        try:
            for gone in prune_versions():
                say(f"Removed {gone}.")
        except Exception as e:  # pruning is housekeeping: never fail the install
            say(f"Old builds not pruned: {e}")
        say(f"Installed {installed.name}.")
        return ""
    except ArchiveError as e:
        _remove(part)
        return str(e)
    except Exception as e:
        _remove(part)
        return f"{kind} download failed: {e}"


def download_latest(kind: str, opener=None, progress=None, repo: str = "") -> str:
    """Download and install the latest release; "" on success, else a message."""
    say = progress if callable(progress) else (lambda _message: None)
    try:
        origin, wanted = _source_for(kind, repo)
        release = latest_release(kind, opener, wanted)
        return _install_asset(kind, release, opener, say, origin, wanted)
    except ArchiveError as e:
        return str(e)
    except Exception as e:
        return f"{kind} download failed: {e}"


def download_release(kind: str, asset: dict, opener=None, progress=None, repo: str = "") -> str:
    """Install one release picked from `releases()`; "" on success."""
    say = progress if callable(progress) else (lambda _message: None)
    try:
        origin, wanted = _source_for(kind, repo)
        return _install_asset(kind, asset, opener, say, origin, wanted)
    except ArchiveError as e:
        return str(e)
    except Exception as e:
        return f"{kind} download failed: {e}"


def install_from_url(kind: str, url: str, opener=None, progress=None) -> str:
    """Install a layer from a direct archive URL; "" on success, else a message.

    No release metadata: there is no digest to check, so HTTPS and the
    archive checks (suffix, size caps, single version directory) are the
    whole trust model.
    """
    say = progress if callable(progress) else (lambda _message: None)
    try:
        _repo(kind)  # validates the kind
        parts = urllib.parse.urlsplit(str(url or ""))
        if parts.scheme.lower() != "https":
            raise ArchiveError("only https:// archive URLs are accepted")
        name = Path(parts.path).name
        if not name:
            raise ArchiveError("the URL has no file name")
        asset = {"name": name, "url": str(url), "size": 0, "digest": ""}
        return _install_asset(kind, asset, opener, say, "url")
    except ArchiveError as e:
        return str(e)
    except Exception as e:
        return f"{kind} download failed: {e}"


def remove_version(kind: str, name: str) -> str:
    """Delete one managed version directory; "" on success, else a message."""
    if kind not in runtimes.GRAPHICS_DLLS:
        return f"Unknown runtime kind: {kind}"
    root = xdg.runtimes_dir() / kind
    target = root / str(name or "")
    try:
        root_real = root.resolve()
    except OSError:
        return f"{name} is not a managed version."
    if target.is_symlink():
        return f"{name} is not a managed version."
    resolved = target.resolve()
    if resolved.parent != root_real or not resolved.is_dir():
        return f"{name} is not a managed version."
    shutil.rmtree(resolved)
    # sources() already pruned the deleted directory; writing it back also
    # drops orphans left in the file by hand-deleted versions.
    data = sources()
    try:
        _write_sources(data)
    except OSError:
        pass
    return ""


#: Managed builds kept per layer; the newest installs win.
KEEP_VERSIONS = 3


def _protected_versions() -> dict[str, set[str]]:
    """Version names a prune must never delete: the defaults and game pins."""
    from . import config as cfgmod

    protected: dict[str, set[str]] = {"dxvk": set(), "vkd3d": set()}
    try:
        prefs = cfgmod.load_preferences()
        protected["dxvk"].add(prefs.dxvk_default)
        protected["vkd3d"].add(prefs.vkd3d_default)
    except Exception:
        pass
    try:
        appids = cfgmod.list_appids()
    except Exception:
        appids = []
    for appid in appids:
        try:
            cfg = cfgmod.load(appid)
        except Exception:
            continue
        protected["dxvk"].add(cfg.graphics.dxvk_version)
        protected["vkd3d"].add(cfg.graphics.vkd3d_version)
    return {kind: {name for name in names if name} for kind, names in protected.items()}


def prune_versions(keep: int = KEEP_VERSIONS) -> list[str]:
    """Delete managed builds beyond the newest `keep` per kind; return names.

    Only builds recorded in `.sources.json` are eligible, so a version the
    user dropped into the archive cache, an external folder or the distro
    tree is never touched. The default build and any version pinned by a
    game survive even when they are older than the cut.
    """
    if keep <= 0:
        return []
    protected = _protected_versions()
    entries = sources()
    removed: list[str] = []
    for kind in runtimes.GRAPHICS_DLLS:
        rows = sorted(
            (str(value.get("at", "")), key.split("/", 1)[1])
            for key, value in entries.items()
            if key.startswith(f"{kind}/") and key.split("/", 1)[1]
        )
        for _at, name in reversed(rows[: max(0, len(rows) - keep)]):
            if name in protected.get(kind, set()):
                continue
            try:
                if remove_version(kind, name) == "":
                    removed.append(f"{kind}/{name}")
            except OSError:
                continue
    return removed


def _cleanup_staging(root: Path) -> None:
    for entry in root.glob(".staging-*"):
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)


def _check_zip_name(name: str) -> None:
    path = Path(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or name.startswith(("/", "\\")):
        raise ArchiveError(f"unsafe archive member: {name}")


def _extract_zip(archive: Path, staging: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ArchiveError("archive has too many entries")
        total = 0
        for info in infos:
            _check_zip_name(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ArchiveError(f"archive contains a symlink: {info.filename}")
            total += info.file_size
            if total > MAX_EXTRACTED_BYTES:
                raise ArchiveError("archive expands past the size cap")
        try:
            zf.extractall(staging)
        except (zipfile.BadZipFile, OSError, RuntimeError) as e:
            raise ArchiveError(f"could not extract archive: {e}") from e


def _extract_tar_members(tf: tarfile.TarFile, staging: Path) -> None:
    total = 0
    for index, member in enumerate(tf):
        if index >= MAX_MEMBERS:
            raise ArchiveError("archive has too many entries")
        total += max(member.size, 0)
        if total > MAX_EXTRACTED_BYTES:
            raise ArchiveError("archive expands past the size cap")
        try:
            tf.extract(member, path=staging, filter="data")
        except (tarfile.TarError, OSError, ValueError) as e:
            raise ArchiveError(f"unsafe archive member: {member.name}") from e


@contextlib.contextmanager
def _zstd_stream(path: Path):
    """Decompressing reader: stdlib on 3.14+, the zstandard package below."""
    try:
        from compression import zstd
    except ImportError:
        pass
    else:
        with zstd.open(path, "rb") as stream:
            yield stream
        return
    try:
        import zstandard
    except ImportError as e:
        raise ArchiveError("zstd archives need Python 3.14+ or the zstandard package") from e
    with open(path, "rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader:
        yield reader


def _extract_tar(archive: Path, staging: Path, fmt: str) -> None:
    if fmt == "tar.gz":
        with tarfile.open(archive, mode="r:gz") as tf:
            _extract_tar_members(tf, staging)
        return
    with _zstd_stream(archive) as stream, tarfile.open(fileobj=stream, mode="r|") as tf:
        _extract_tar_members(tf, staging)


def _kind_for(version_dir: Path) -> str:
    kinds = [
        kind
        for kind, dll in runtimes.GRAPHICS_DLLS.items()
        if (version_dir / "x64" / dll).is_file()
    ]
    if len(kinds) != 1:
        raise ArchiveError("archive must hold exactly one graphics layer")
    return kinds[0]


def _version_dir(staging: Path, kind: str) -> Path:
    dlls = [runtimes.GRAPHICS_DLLS[kind]] if kind else list(runtimes.GRAPHICS_DLLS.values())
    matches = [
        child
        for child in staging.iterdir()
        if child.is_dir() and any((child / "x64" / dll).is_file() for dll in dlls)
    ]
    if len(matches) != 1:
        raise ArchiveError("archive must hold exactly one top-level version directory")
    return matches[0]


def extract_archive(archive: Path, kind: str = "") -> Path:
    """Extract `archive` into the managed dir and return the version root.

    `kind` forces the layer; empty detects it from the `x64` DLL. An
    existing version with the same name is kept (idempotent).
    """
    archive = Path(archive)
    fmt = _archive_format(archive.name)
    root = xdg.runtimes_dir()
    root.mkdir(parents=True, exist_ok=True)
    _cleanup_staging(root)
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
    try:
        if fmt == "zip":
            _extract_zip(archive, staging)
        else:
            _extract_tar(archive, staging, fmt)
        version_dir = _version_dir(staging, kind)
        kind = kind or _kind_for(version_dir)
        target = root / kind / xdg.safe_stem(version_dir.name)
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(version_dir, target)
        return target
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def supported(name: str) -> bool:
    """Whether the cache file name has a supported archive suffix."""
    try:
        _archive_format(name)
    except ArchiveError:
        return False
    return True


def sync_archives(progress=None) -> list[str]:
    """Extract supported archives in the cache; returns newly installed names.

    An archive whose version already exists is skipped and user-dropped
    files stay in the cache. Extraction failures go through `progress`.
    """
    say = progress if callable(progress) else (lambda _message: None)
    root = xdg.runtimes_dir()
    _cleanup_staging(root)
    cache = xdg.archives_cache_dir()
    try:
        entries = sorted(p for p in cache.iterdir() if p.is_file())
    except OSError:
        return []

    def installed() -> set[str]:
        return {
            str(path)
            for kind in runtimes.GRAPHICS_DLLS
            for path in (root / kind).glob("*")
            if path.is_dir()
        }

    before = installed()
    for archive in entries:
        if archive.name.endswith(".part") or not supported(archive.name):
            continue
        try:
            extract_archive(archive)
        except Exception as e:
            say(f"{archive.name}: {e}")
    try:
        prune_versions()
    except Exception as e:  # housekeeping must not break the scan
        say(f"Old builds not pruned: {e}")
    return sorted({Path(path).name for path in installed() - before})
