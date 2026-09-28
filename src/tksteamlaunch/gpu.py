"""GPU vendor detection from PCI sysfs (stdlib only)."""

from __future__ import annotations

from pathlib import Path

# PCI vendor IDs for the three GPU makers.
_VENDORS = {"0x1002": "amd", "0x10de": "nvidia", "0x8086": "intel"}


def detect_vendors(sysfs: str | Path = "/sys/bus/pci/devices") -> set[str]:
    """Return GPU vendors present (subset of amd/nvidia/intel).

    Only VGA compatible and 3D controllers (class 0x030000/0x030200)
    count; audio and unrelated PCI devices are ignored. `sysfs` is a
    parameter for tests.
    """
    found: set[str] = set()
    try:
        devices = sorted(Path(sysfs).iterdir())
    except Exception:
        return found
    for dev in devices:
        try:
            cls = (dev / "class").read_text().strip().lower()
            if cls not in ("0x030000", "0x030200"):
                continue
            vendor = (dev / "vendor").read_text().strip().lower()
        except Exception:
            continue
        name = _VENDORS.get(vendor)
        if name:
            found.add(name)
    return found
