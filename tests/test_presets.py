"""Env presets: merge semantics, metadata schema, GPU/flavor helpers."""

from tkarcade import presets as pm


def test_apply_preset_merges_missing_only():
    env = {"WINE_FULLSCREEN_FSR": "0"}
    assert pm.apply_preset(env, "FSR Upscaling (Wine/Proton)") == []
    assert env["WINE_FULLSCREEN_FSR"] == "0"
    assert pm.apply_preset(env, "Faster Shaders (RADV)") == ["RADV_PERFTEST"]
    assert env["RADV_PERFTEST"] == "gpl"
    assert pm.apply_preset(env, "No Such Preset") == []


def test_preset_catalog_schema():
    assert "FSR Upscaling (Wine/Proton)" in pm.PRESETS
    assert "Japanese Locale" in pm.PRESETS
    assert "DLSS Upgrade (NVIDIA)" in pm.PRESETS
    for name, preset in pm.PRESETS.items():
        assert preset.vars, name
        assert set(preset.drivers) <= set(pm.KNOWN_DRIVERS), name
        assert set(preset.proton) <= set(pm.KNOWN_PROTONS), name
    nvidia = pm.PRESETS["Disable VSync (NVIDIA)"]
    assert nvidia.drivers == ("nvidia",)
    assert pm.PRESETS["D7VK DDraw"].proton == ("cachyos", "dw")
    assert pm.PRESETS["No NTSync"].proton == ("ge",)
    assert pm.PRESETS["Media Force GST"].proton == ("cachyos", "dw")
    assert pm.PRESETS["SDL Input"].proton == ("ge", "cachyos", "dw")
    assert pm.PRESETS["No Steam Input"].proton == ("ge", "cachyos", "dw")
    assert pm.PRESETS["Local Shader Cache"].proton == ("ge", "cachyos", "dw")
    assert pm.PRESETS["FSR4 Upgrade (Proton)"].proton == ("ge", "cachyos", "dw")
    assert "semicolon" in pm.PRESETS["Block Hosts (edit list)"].note


def test_detect_vendors_fake_sysfs(tmp_path):
    from tkarcade import gpu as gpumod

    def dev(name, cls, vendor):
        d = tmp_path / name
        d.mkdir()
        (d / "class").write_text(cls)
        (d / "vendor").write_text(vendor)

    dev("0000:01:00.0", "0x030000", "0x1002")
    dev("0000:02:00.0", "0x030200", "0x10de")
    dev("0000:03:00.0", "0x040300", "0x1002")  # audio: ignored
    dev("0000:04:00.0", "0x030000", "0x1234")  # unknown vendor: ignored
    assert gpumod.detect_vendors(tmp_path) == {"amd", "nvidia"}
    assert gpumod.detect_vendors(tmp_path / "missing") == set()


def test_proton_flavor():
    from tkarcade import proton as protonmod

    assert protonmod.flavor("Proton-cachyos") == "cachyos"
    assert protonmod.flavor("GE-Proton10-12") == "ge"
    assert protonmod.flavor("DW-Proton Latest") == "dw"
    assert protonmod.flavor("proton_9") == "valve"
    assert protonmod.flavor("") == "valve"


def test_proton_wayland_preset_tag():
    import tkarcade.presets as pm

    assert pm.PRESETS["Proton Wayland"].vars == {"PROTON_ENABLE_WAYLAND": "1"}
    assert pm.PRESETS["Proton Wayland"].proton == ("ge", "cachyos", "dw")


def test_vsync_presets_audited():
    """The two VSync presets are GL/GLX-scoped and still valid (2026-10-19).

    Mesa keeps `vblank_mode` as a driconf option (0 = never synchronise)
    and its own xmlconfig test proves the environment variable overrides
    drirc; the NVIDIA README still documents the boolean
    `__GL_SYNC_TO_VBLANK`. Neither touches Vulkan (its own present mode,
    MESA_VK_WSI_PRESENT_MODE, or DXVK's dxgi.syncInterval).
    """
    import tkarcade.presets as pm

    mesa = pm.PRESETS["Disable VSync (Mesa)"]
    assert mesa.vars == {"vblank_mode": "0"}
    assert mesa.drivers == ("amd", "intel")
    assert "OpenGL" in mesa.note
    nvidia = pm.PRESETS["Disable VSync (NVIDIA)"]
    assert nvidia.vars == {"__GL_SYNC_TO_VBLANK": "0"}
    assert "OpenGL" in nvidia.note


def test_fps_limit_preset():
    import tkarcade.presets as pm

    preset = pm.PRESETS["FPS Limit (DXVK)"]
    assert preset.vars == {"DXVK_CONFIG": "dxgi.maxFrameRate = 60; d3d9.maxFrameRate = 60"}
    assert "DX9" in preset.note
