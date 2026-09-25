"""Env preset merging (missing keys only, never clobbers)."""

from tksteamlaunch import presets as pm


def test_apply_preset_merges_missing_only():
    vars = {"WINE_FULLSCREEN_FSR": "0"}
    assert pm.apply_preset(vars, "FSR Upscaling (Wine/Proton)") == []
    assert vars["WINE_FULLSCREEN_FSR"] == "0"
    assert pm.apply_preset(vars, "Faster Shaders (RADV)") == ["RADV_PERFTEST"]
    assert vars["RADV_PERFTEST"] == "gpl"
    assert pm.apply_preset(vars, "No Such Preset") == []


def test_preset_catalog():
    assert set(pm.ENV_PRESETS) == {
        "FSR Upscaling (Wine/Proton)",
        "Faster Shaders (RADV)",
        "Prefer Wayland (SDL)",
    }
    for values in pm.ENV_PRESETS.values():
        assert values and all(values)
