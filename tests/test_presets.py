"""Env presets: merge semantics, metadata schema, GPU/flavor helpers."""

from tksteamlaunch import presets as pm


def test_apply_preset_merges_missing_only():
    vars = {"WINE_FULLSCREEN_FSR": "0"}
    assert pm.apply_preset(vars, "FSR Upscaling (Wine/Proton)") == []
    assert vars["WINE_FULLSCREEN_FSR"] == "0"
    assert pm.apply_preset(vars, "Faster Shaders (RADV)") == ["RADV_PERFTEST"]
    assert vars["RADV_PERFTEST"] == "gpl"
    assert pm.apply_preset(vars, "No Such Preset") == []


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
    from tksteamlaunch import gpu as gpumod

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
    from tksteamlaunch import proton as protonmod

    assert protonmod.flavor("Proton-cachyos") == "cachyos"
    assert protonmod.flavor("GE-Proton10-12") == "ge"
    assert protonmod.flavor("DW-Proton Latest") == "dw"
    assert protonmod.flavor("proton_9") == "valve"
    assert protonmod.flavor("") == "valve"


def test_proton_wayland_preset_tag():
    import tksteamlaunch.presets as pm

    assert pm.PRESETS["Proton Wayland"].vars == {"PROTON_ENABLE_WAYLAND": "1"}
    assert pm.PRESETS["Proton Wayland"].proton == ("ge", "cachyos", "dw")
