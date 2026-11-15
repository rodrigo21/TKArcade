"""Decode and re-encode stored artwork through Qt (GUI only).

Every image the app stores — a pasted URL, a picked file, an icon pulled
from a Windows executable, a provider download — is decoded by
`QImageReader` and written back in one format, chosen in Preferences.
`auto` prefers AVIF (best compression) and falls back to WebP, JPEG and
PNG, so a machine without the optional plugins still stores something.
JPEG has no transparency, so an `icon` never stores as JPEG.

The core artwork module stays stdlib-first on the launch path; this one
imports Qt and is used only by the model and its workers.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QImageReader, QImageWriter

from .. import artwork as artmod
from .. import config as cfgmod
from .. import xdg

log = logging.getLogger("tkarcade.artwork_io")

#: Formats the setting offers and the suffix each one writes.
_FORMATS = {"avif": ".avif", "webp": ".webp", "jpeg": ".jpg", "png": ".png"}

_WRITERS: set[str] | None = None


def _writers() -> set[str]:
    """Format names QImageWriter can produce on this machine."""
    global _WRITERS
    if _WRITERS is None:
        try:
            _WRITERS = {
                bytes(name).decode().lower() for name in QImageWriter.supportedImageFormats()
            }
        except Exception:
            _WRITERS = {"png", "jpeg"}
    return _WRITERS


def _resolve(choice: str, quality: int, kind: str = "") -> tuple[str, int, str]:
    """(format, quality, suffix) for a choice and quality."""
    order = [("avif", quality), ("webp", 90), ("jpeg", 90), ("png", 0)]
    if choice in _FORMATS:
        index = [name for name, _ in order].index(choice)
        order = order[index:]
        if choice != "png":
            order[0] = (choice, quality)
    for fmt, fallback_quality in order:
        if kind == "icon" and fmt == "jpeg":
            continue
        if fmt == "png" or fmt in _writers():
            return fmt, fallback_quality, _FORMATS[fmt]
    return "png", 0, ".png"


def preload() -> None:
    """Resolve the writer list on the GUI thread before workers need it."""
    _writers()


def target(kind: str = "") -> tuple[str, int, str]:
    """(format, quality, suffix) for one stored image kind.

    An explicit choice keeps the configured quality; the rest of the
    chain keeps its own. JPEG is skipped for `icon`.
    """
    try:
        prefs = cfgmod.load_preferences()
        choice = prefs.artwork_format
        quality = prefs.artwork_quality
    except Exception:
        choice, quality = "auto", 85
    return _resolve(choice, quality, kind)


def describe(choice: str, quality: int) -> str:
    """Human label for a format choice: what it writes on this machine."""
    fmt, resolved_quality, _suffix = _resolve(choice, quality)
    if fmt == "png":
        return "PNG, Lossless"
    return f"{fmt.upper()}, Quality {resolved_quality}"


def decode(data: bytes) -> tuple[QImage | None, str]:
    """Decode any image Qt reads: (image, token).

    The token is "" or "large" on success, "huge" when the pixel size is
    over the hard limit (checked before the decode when the format
    declares its size) and "not-image" when Qt could not read it. A
    multi-size ICO yields its largest frame.
    """
    raw = QByteArray(data)
    buffer = QBuffer(raw)
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        return None, "not-image"
    reader = QImageReader(buffer)
    # Format and frame count are read first: querying the size first makes
    # PySide6 report an empty format afterwards.
    fmt = bytes(reader.format()).lower()
    count = reader.imageCount()
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and artmod.image_size_token(size.width(), size.height()) == "huge":
        return None, "huge"
    image = reader.read()
    if image.isNull():
        return None, "not-image"
    if fmt == b"ico" and count > 1:
        best = image
        for index in range(count):
            reader.jumpToImage(index)
            frame = reader.read()
            if frame.isNull():
                continue
            if frame.width() * frame.height() > best.width() * best.height():
                best = frame
        image = best
    token = artmod.image_size_token(image.width(), image.height())
    if token == "huge":
        return None, token
    return image, token


def _encode(image: QImage, fmt: str, quality: int) -> bytes | None:
    out = QBuffer()
    if not out.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    writer = QImageWriter(out, fmt.encode())
    if fmt != "png":
        writer.setQuality(quality)
    if not writer.write(image) or out.size() == 0:
        log.warning("artwork: %s encode failed: %s", fmt, writer.errorString())
        return None
    return bytes(out.data())


def _encode_best(image: QImage, kind: str) -> tuple[bytes | None, str]:
    fmt, quality, suffix = target(kind)
    body = _encode(image, fmt, quality)
    if body is not None:
        return body, suffix
    if suffix != ".png":
        body = _encode(image, "png", 0)
        if body is not None:
            return body, ".png"
    return None, ""


def _fit_icon(image: QImage) -> QImage:
    """Downscale an oversized icon, keeping its aspect and alpha."""
    if max(image.width(), image.height()) <= artmod.ICON_MAX_SIDE:
        return image
    return image.scaled(
        artmod.ICON_MAX_SIDE,
        artmod.ICON_MAX_SIDE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _oversized_icon(path: Path, kind: str) -> bool:
    """Whether a stored icon is above the cap and needs a rewrite."""
    if kind != "icon":
        return False
    try:
        size = QImageReader(str(path)).size()
    except Exception:
        return True
    if not size.isValid():
        return True
    return max(size.width(), size.height()) > artmod.ICON_MAX_SIDE


def convert_to(data: bytes, kind: str = "") -> tuple[bytes | None, str, str]:
    """Decode any readable image and write it in the storage format.

    Returns (body, suffix, token); body is None on failure. An `icon` is
    downscaled to `ICON_MAX_SIDE` and the token reports the stored size,
    so a large icon source is not flagged as a large artwork.
    """
    image, _token = decode(data)
    if image is None:
        return None, "", _token
    if kind == "icon":
        image = _fit_icon(image)
    token = artmod.image_size_token(image.width(), image.height())
    body, suffix = _encode_best(image, kind)
    if body is None:
        return None, "", "not-image"
    return body, suffix, token


def convert_file(path: Path, kind: str = "") -> tuple[Path | None, str]:
    """Re-encode one stored file in place: (new path, token).

    A file already in the target suffix is left alone, so running the
    migration twice never stacks another lossy pass on it. An icon above
    the size cap is the exception: it is rewritten even in the target
    format, which is the one place the pass also downscales.
    """
    path = Path(path)
    if path.suffix.lower() == target(kind)[2] and not _oversized_icon(path, kind):
        return path, ""
    try:
        data = path.read_bytes()
    except OSError:
        return None, "file"
    body, suffix, token = convert_to(data, kind)
    if body is None:
        return None, token
    return artmod.replace_image(path, body, suffix), token


def convert_exe_icon(appid: str, path: Path) -> Path | None:
    """Re-encode one extracted executable icon and record its suffix."""
    path = Path(path)
    new, _token = convert_file(path, "icon")
    if new is None:
        return None
    if new != path:
        artmod.record_exe_icon(appid, new)
    return new


def _grid_kind(name: str) -> str:
    """Kind of a cached file, from its name (`<key>-icon.png`)."""
    stem = Path(name).stem
    for kind in ("icon", "background", "banner"):
        if stem.endswith("-" + kind):
            return kind
    return "cover"


def stored_images() -> list[tuple[Path, str]]:
    """Every image file the app owns: (path, kind)."""
    return _grid_images() + _manual_images()


def _grid_images() -> list[tuple[Path, str]]:
    """Provider art in the grid cache: (path, kind)."""
    found: list[tuple[Path, str]] = []
    try:
        entries = list((xdg.app_cache_dir() / "grids").iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in artmod.IMAGE_SUFFIXES:
            continue
        stem = Path(entry.name).stem
        kind = "icon" if stem.endswith("-exe") else _grid_kind(entry.name)
        found.append((entry, kind))
    return found


def _manual_images() -> list[tuple[Path, str]]:
    """Copied-in artwork under `artwork/<key>/`: (path, kind)."""
    found: list[tuple[Path, str]] = []
    try:
        folders = [entry for entry in (xdg.app_cache_dir() / "artwork").iterdir() if entry.is_dir()]
    except OSError:
        return found
    for folder in folders:
        try:
            entries = [
                entry
                for entry in folder.iterdir()
                if entry.is_file() and entry.stem in artmod.MANUAL_KINDS
            ]
        except OSError:
            continue
        found.extend((entry, entry.stem) for entry in entries)
    return found


def _ensure_exe_icons() -> None:
    """Give every local game's executable icon a sidecar entry.

    A cache from before the sidecar recorded the executable can carry a
    converted icon with no stat to validate against; extracting once
    writes the entry the re-encode then keeps in step.
    """
    for appid in cfgmod.list_appids():
        if not str(appid).startswith("local-"):
            continue
        try:
            cfg = cfgmod.load(str(appid))
            exe = str(cfg.general.custom_executable or "").strip()
        except Exception:
            continue
        if not exe:
            continue
        try:
            artmod.exe_icon(str(appid), exe)
        except Exception as e:
            log.warning("artwork: exe icon %s failed: %s", appid, e)


def _update_config_paths(mapping: dict[str, str]) -> None:
    """Point the game configs at the converted manual slots."""
    for appid in cfgmod.list_appids():
        try:
            cfg = cfgmod.load(str(appid))
        except Exception:
            continue
        changed = False
        for kind in ("icon", "cover", "banner", "background"):
            value = str(getattr(cfg.artwork, kind, "") or "")
            if value in mapping:
                setattr(cfg.artwork, kind, mapping[value])
                changed = True
        if changed:
            try:
                cfgmod.save(cfg)
            except Exception as e:
                log.warning("artwork: could not save %s: %s", appid, e)


def reencode_all() -> tuple[int, int, int, dict[str, str]]:
    """Re-encode every stored artwork file in the configured format.

    Returns (converted, skipped, failed, {old path: new path}). The game
    configs that point at a converted manual slot are rewritten too; a
    profile's copy of the path is cosmetic and stays as it was.
    """
    converted = skipped = failed = 0
    mapping: dict[str, str] = {}
    _ensure_exe_icons()
    for path, kind in stored_images():
        try:
            before = path.stat().st_mtime_ns
        except OSError:
            before = 0
        try:
            new, _token = convert_file(path, kind)
        except Exception as e:
            log.warning("artwork: re-encode %s failed: %s", path, e)
            failed += 1
            continue
        if new is None:
            failed += 1
        elif new != path:
            converted += 1
            mapping[str(path)] = str(new)
        elif path.stat().st_mtime_ns != before:
            # Rewritten in place: an oversized icon in its target format.
            converted += 1
        else:
            skipped += 1
        if (
            new is not None
            and "-exe." in path.name
            and (new != path or new.suffix.lower() == ".avif")
        ):
            # An AVIF executable icon came from this conversion; keep the
            # sidecar from re-extracting it when it was cached earlier.
            key = path.name.rsplit("-exe.", 1)[0]
            artmod.record_exe_icon(key, new)
    if mapping:
        _update_config_paths(mapping)
    return converted, skipped, failed, mapping
