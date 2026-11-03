"""Runtime archive downloads and extraction (GUI-only helper).

The launcher never imports this module: downloads, digest checks and
unpacking stay on the GUI side, while `runtimes.graphics_versions` only
reads the managed installs it writes. Stdlib first: `compression.zstd`
covers Python 3.14+, and the `zstandard` package is imported lazily as
the fallback for older interpreters (marker dependency in pyproject).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import tarfile
import tempfile
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


def latest_release(kind: str, opener=None) -> dict:
    """Newest GitHub release asset for a layer (name, url, size, digest)."""
    repo, suffixes = LAYERS.get(kind, ("", ()))
    if not repo:
        raise ArchiveError(f"unknown runtime kind: {kind!r}")
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
    for suffix in suffixes:
        for asset in assets or []:
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name.endswith(suffix) and url:
                return {
                    "name": name,
                    "url": url,
                    "size": int(asset.get("size") or 0),
                    "digest": str(asset.get("digest") or ""),
                }
    raise ArchiveError(f"no {kind} archive in the latest release")


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


def download_latest(kind: str, opener=None, progress=None) -> str:
    """Download and install the latest release; "" on success, else a message."""
    say = progress if callable(progress) else (lambda _message: None)
    part = xdg.archives_cache_dir() / "pending"
    try:
        release = latest_release(kind, opener)
        say(f"Downloading {release['name']}…")
        cache = xdg.archives_cache_dir()
        cache.mkdir(parents=True, exist_ok=True)
        dest = cache / release["name"]
        part = dest.with_name(dest.name + ".part")
        digest = _download(release, part, opener)
        _verify_digest(release.get("digest", ""), digest)
        os.replace(part, dest)
        say(f"Extracting {release['name']}…")
        extracted = extract_archive(dest, kind)
        _remove(dest)
        say(f"Installed {extracted.name}.")
        return ""
    except ArchiveError as e:
        _remove(part)
        return str(e)
    except Exception as e:
        _remove(part)
        return f"{kind} download failed: {e}"


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
    return sorted({Path(path).name for path in installed() - before})
