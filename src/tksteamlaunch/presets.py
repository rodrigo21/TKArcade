"""Curated environment presets with driver/proton applicability metadata.

Applicability audited 2026-09-30 against the proton-cachyos README
(upstream + CachyOS tables), the GE-Proton README, GE-Proton 10-9
release notes, and the installed `proton` scripts of Valve Experimental,
GE-Proton, proton-cachyos-slr and DW-Proton on the maintainer's PC
(absence in a build's `proton` script = no-op there, so the preset is
not offered for that flavor).
"""

from __future__ import annotations

from dataclasses import dataclass, field

KNOWN_DRIVERS = ("amd", "nvidia", "intel")
KNOWN_PROTONS = ("valve", "ge", "cachyos", "dw")


@dataclass(frozen=True)
class Preset:
    """One preset. Empty drivers/proton means applicable everywhere."""

    vars: dict[str, str] = field(default_factory=dict)
    drivers: tuple[str, ...] = ()
    proton: tuple[str, ...] = ()
    note: str = ""


PRESETS: dict[str, Preset] = {
    "FSR Upscaling (Wine/Proton)": Preset(vars={"WINE_FULLSCREEN_FSR": "1"}),
    "Faster Shaders (RADV)": Preset(vars={"RADV_PERFTEST": "gpl"}, drivers=("amd",)),
    "Prefer Wayland (SDL)": Preset(vars={"SDL_VIDEODRIVER": "wayland"}),
    "Proton Wayland": Preset(
        vars={"PROTON_ENABLE_WAYLAND": "1"},
        proton=("ge", "cachyos", "dw"),
        note="Needs a Wayland session; no-op where the build lacks winewayland.",
    ),
    "Disable VSync (Mesa)": Preset(vars={"vblank_mode": "0"}, drivers=("amd", "intel")),
    "Disable VSync (NVIDIA)": Preset(vars={"__GL_SYNC_TO_VBLANK": "0"}, drivers=("nvidia",)),
    "FSR4 Upgrade (Proton)": Preset(
        vars={"PROTON_FSR4_UPGRADE": "1"},
        proton=("ge", "cachyos", "dw"),
        note="Needs an FSR 3.1 game; downloads the DLL on first run.",
    ),
    "No Fsync": Preset(vars={"PROTON_NO_FSYNC": "1"}),
    "No Esync": Preset(
        vars={"PROTON_NO_ESYNC": "1"},
        note="No-op on builds that dropped the toggle (e.g. Experimental).",
    ),
    "Large Address Aware": Preset(
        vars={"PROTON_FORCE_LARGE_ADDRESS_AWARE": "1"},
        note="Already default-on upstream; set explicitly for older builds.",
    ),
    "Old GL String": Preset(vars={"PROTON_OLD_GL_STRING": "1"}),
    "Use WineD3D (OpenGL)": Preset(vars={"PROTON_USE_WINED3D": "1"}),
    "Disable D3D11": Preset(vars={"PROTON_NO_D3D11": "1"}),
    "Disable D3D10": Preset(vars={"PROTON_NO_D3D10": "1"}),
    "Disable D3D9": Preset(
        vars={"PROTON_NO_D3D9": "1"},
        note="Toggle removed upstream; no-op on current builds.",
    ),
    "DXVK D3D8": Preset(vars={"PROTON_DXVK_D3D8": "1"}),
    "D7VK DDraw": Preset(
        vars={"PROTON_D7VK_DDRAW": "1"},
        proton=("cachyos", "dw"),
        note="DirectX 7 and lower via D7VK.",
    ),
    "D7VK (GE-Proton)": Preset(
        vars={"PROTON_USE_D7VK": "1"},
        proton=("ge",),
        note="GE's own switch; needs D7VK's ddraw.dll present.",
    ),
    "DXVK Sarek (old GPUs)": Preset(
        vars={"PROTON_DXVK_SAREK": "1"},
        proton=("cachyos", "dw"),
        note="DXVK-Sarek fork for Vulkan 1.1/1.2 GPUs; never with anti-cheat.",
    ),
    "Local Shader Cache": Preset(
        vars={"PROTON_LOCAL_SHADER_CACHE": "1"},
        proton=("ge", "cachyos", "dw"),
        note="Per-game shader cache even with pre-caching off; isolates, not precompiles.",
    ),
    "Media Force GST": Preset(
        vars={"PROTON_MEDIA_FORCE_GST": "1"},
        proton=("cachyos", "dw"),
        note="Fixes cutscene video/audio playback in some games.",
    ),
    "Integer Scaling": Preset(
        vars={"WINE_FULLSCREEN_INTEGER_SCALING": "1"},
        note="Sharp pixels when upscaling; great for old games.",
    ),
    "HDR (DXVK)": Preset(
        vars={"DXVK_HDR": "1"},
        note="Needs an HDR chain: compositor, game and monitor.",
    ),
    "Japanese Locale": Preset(
        vars={"HOST_LC_ALL": "ja_JP.UTF-8"},
        note="For games needing a Japanese locale (e.g. visual novels).",
    ),
    "Block Hosts (edit list)": Preset(
        vars={"WINE_BLOCK_HOSTS": ""},
        note="Comma- or semicolon-separated hosts (max 16) Wine must not reach; edit after adding.",
    ),
    "SDL Input": Preset(
        vars={"PROTON_USE_SDL": "1"},
        proton=("ge", "cachyos", "dw"),
        note="SDL instead of HIDRAW/Steam Input for controllers.",
    ),
    "No Steam Input": Preset(
        vars={"PROTON_NO_STEAMINPUT": "1"},
        proton=("ge", "cachyos", "dw"),
    ),
    "Wine Audio (Pulse)": Preset(
        vars={"WINE_AUDIO_DRIVER": "pulse"},
        note="Force winepulse.drv instead of the default list.",
    ),
    "No NTSync": Preset(
        vars={"PROTON_NO_NTSYNC": "1"},
        proton=("ge",),
        note="Disable the ntsync kernel-module sync primitives (GE 10-9+).",
    ),
    "KWin Hacks": Preset(
        vars={"WINE_USE_KWIN_HACKS": "1"},
        note="Legacy: only matters on KDE <6.4 (Wayland) / <6.6 (X11).",
    ),
    "DLSS Upgrade (NVIDIA)": Preset(
        vars={"PROTON_DLSS_UPGRADE": "1"},
        drivers=("nvidia",),
        proton=("ge", "cachyos", "dw"),
    ),
    "Hide NVIDIA GPU": Preset(vars={"PROTON_HIDE_NVIDIA_GPU": "1"}, drivers=("nvidia",)),
    "Disable NVAPI": Preset(vars={"PROTON_DISABLE_NVAPI": "1"}, drivers=("nvidia",)),
}


def apply_preset(vars: dict[str, str], name: str) -> list[str]:
    """Merge preset entries missing from vars. Returns added key names."""
    preset = PRESETS.get(name)
    if preset is None:
        return []
    added = []
    for key, value in preset.vars.items():
        if key not in vars:
            vars[key] = value
            added.append(key)
    return added
