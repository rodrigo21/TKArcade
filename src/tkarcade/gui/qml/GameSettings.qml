import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kirigami.layouts as KirigamiLayouts

// Per-game settings window (widgets GameDialog parity, tab by tab:
// General and Notes first, the rest follow). A separate modal window
// like the widgets QDialog (resizable, centered on the main window via
// transientParent) — never embedded in the pageStack, never a popup;
// the text prompt below replaces QInputDialog for profile names.
Window {
    id: gameSettings
    objectName: "gameSettings"
    title: defaultsMode
        ? qsTr("Global Defaults")
        : (editAppid === ""
            ? qsTr("Add game")
            : (loadedName !== ""
                ? qsTr("Game Settings — %1 (%2)").arg(loadedName).arg(editAppid)
                : qsTr("Game Settings (%1)").arg(editAppid)))
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 34
    minimumHeight: Kirigami.Units.gridUnit * 30
    width: Kirigami.Units.gridUnit * 42
    height: Kirigami.Units.gridUnit * 44
    visible: false
    color: Kirigami.Theme.backgroundColor

    property string editAppid: ""
    property bool defaultsMode: false
    // Name shown in the window title (widgets GameDialog set it once from
    // the Steam name / config name), not the live field text.
    property string loadedName: ""
    // Standalone CLI editor (gui/edit.py): the widgets GameDialog ran with
    // launch_mode/can_launch and offered Launch and Save & Launch.
    property bool launchMode: false
    property bool canLaunch: true
    // Bottom blocks, persisted in the preferences like the widgets
    // preview flag (toggled from their centered title checkboxes). They
    // start collapsed: reference material, not editing space.
    property bool previewVisible: false
    property bool depStatusVisible: false
    // Wine/Proton only mean something for a Steam id (or the defaults
    // template): a local game has no compatdata prefix to edit.
    readonly property bool wineAvailable: defaultsMode || ((fields.is_steam || false) && editAppid !== "")

    // Outcome of a closing action, for that standalone editor only:
    // "saved" | "launch" | "cancelled". The shell ignores it (no listener).
    signal finished(string outcome)
    property string dialogProfile: ""
    property string lastLoaded: ""
    property string pendingProfile: ""
    property string pendingName: ""
    property string confirmPurpose: ""
    // Downgrade gate (widgets _newer_version): the source on screen was
    // written by a newer TKArcade, so Save/Reset ask first. pendingGate
    // remembers which action to retry once the user accepts.
    property bool newerVersion: false
    property string pendingGate: ""
    property string pendingBrowse: ""
    property var wineToolsData: []
    property var fields: ({})
    // Local Windows runtime (wine/umu) choices and graphics-layer status.
    property var protonChoices: []
    property var gfxInfo: ({})
    property string gfxStatus: ""
    property string errorText: ""
    property string pendingPrompt: "" // "saveAs" | "clone" | ""
    property var dmodeModel: [{"text": "", "data": ""}]
    property string dmodeCurrent: ""
    property string pendingArg: ""
    property string pendingPreset: ""
    property string ptLogDir: ""
    property var page: null
    // JSON of the draft the preview was built from (see
    // refreshPreviewIfStale); "" until the first refresh.
    property string previewSnapshot: ""
    // Widgets _is_dark_theme: the status marks pick their palette from it.
    readonly property bool statusDark: Kirigami.Theme.backgroundColor.hslLightness < 0.5

    // Enter with one of the prompts below focused: the popup owns the key
    // chain while it is open, and the body handler (further down) is not in
    // it. The window-level Enter route lives in the Python key filter
    // (gui/model.py), which reaches the open prompt's accept button.

    // Widgets GameDialog::focusInEvent: another writer (the CLI, a second
    // editor) may have added or removed profiles while this window sat in
    // the back, and the combo would keep listing the stale set.
    onActiveChanged: {
        if (active) {
            gameSettings.refreshProfiles()
        }
    }

    function blankFields() {
        return {
            "appid": "",
            "name": "",
            "custom_executable": "",
            "game_type": "",
            "show_menu": false,
            "menu_timeout": 0,
            "custom_prefix": "",
            "active_profile": "",
            "notes": "",
            "profiles": [],
            "is_steam": false
        }
    }

    function openFor(appid) {
        editAppid = appid
        defaultsMode = false
        reload()
        errorText = ""
        tabBar.currentIndex = 0
        gameModel.watchDialogKeys(gameSettings)
        visible = true
    }

    function openNew() {
        editAppid = ""
        defaultsMode = false
        fields = blankFields()
        pushToControls()
        errorText = ""
        tabBar.currentIndex = 0
        gameModel.watchDialogKeys(gameSettings)
        visible = true
    }

    function openDefaults() {
        editAppid = ""
        defaultsMode = true
        fields = gameModel.loadDefaults()
        pushToControls()
        refreshNewerFlag()
        errorText = ""
        tabBar.currentIndex = 0
        gameModel.watchDialogKeys(gameSettings)
        visible = true
    }

    // Close reporting a user outcome, for the standalone editor (gui/edit.py):
    // it becomes the JSON line the launcher reads. Guarded so a close that
    // Qt sends afterwards (window-manager X, Escape) cannot report twice.
    property bool outcomeReported: false

    function finish(outcome) {
        if (outcomeReported) {
            return
        }
        outcomeReported = true
        visible = false
        finished(outcome)
    }

    onClosing: function (close) {
        // Window manager close / Escape: same as Cancel, never launch.
        if (!outcomeReported) {
            outcomeReported = true
            finished("cancelled")
        }
    }

    onVisibleChanged: {
        // Reopening after a close (the shell opens it many times) must
        // not be blocked by the previous outcome.
        if (visible) {
            outcomeReported = false
        }
    }

    function reload() {
        fields = gameModel.loadGame(editAppid)
        pushToControls()
        refreshNewerFlag()
    }

    // Widgets _refresh_newer_flag: the live file, the active profile file
    // or the Global Defaults template, whichever the dialog is showing.
    function refreshNewerFlag() {
        newerVersion = gameModel.needsNewerApp(
            defaultsMode ? "" : editAppid, defaultsMode ? "" : dialogProfile)
    }

    // Read-only runtime row; tracks the Game type combo so switching
    // clears it (Steam) or names the local Wine/umu runtime.
    function typeValues() {
        return (defaultsMode || (fields.is_steam || false))
            ? ["proton", "native"]
            : ["native", "wine", "umu"]
    }

    function runtimeText() {
        if (defaultsMode || editAppid === "") {
            return ""
        }
        if (!(fields.is_steam || false)) {
            if (typeBox.currentIndex === 1) {
                var wine = localWineField.text.trim()
                return wine !== "" ? wine : qsTr("Wine from PATH")
            }
            if (typeBox.currentIndex === 2) {
                var i = protonBox.currentIndex
                if (i >= 0 && i < protonChoices.length) {
                    return qsTr("Proton via umu: %1").arg(protonChoices[i].name)
                }
                return qsTr("Proton via umu (choose an install)")
            }
            return qsTr("Native (no runtime)")
        }
        if (typeBox.currentIndex === 1) {
            return qsTr("Native (no Proton)")
        }
        return gameModel.detectedRuntime(editAppid)
    }

    // Discovered Proton installs and the global Wine/prefix defaults.
    function refreshRuntime() {
        var opts = gameModel.runtimeOptions(editAppid)
        var wine = opts.wine || ""
        localWineField.placeholderText = wine !== ""
            ? qsTr("empty = %1").arg(wine)
            : qsTr("empty = wine from PATH")
        localPrefixField.placeholderText = (opts.default_prefix || "") !== ""
            ? qsTr("empty = %1").arg(opts.default_prefix)
            : qsTr("empty = the prefix base in Preferences")
        protonChoices = opts.protons || []
        protonBox.model = protonChoices.map(function(p) { return p.name })
        localWineField.text = fields.runtime_wine_binary || ""
        localPrefixField.text = fields.runtime_prefix_dir || ""
        var chosen = fields.runtime_proton_path || ""
        var idx = -1
        for (var i = 0; i < protonChoices.length; i++) {
            if (protonChoices[i].path === chosen) {
                idx = i
                break
            }
        }
        protonBox.currentIndex = idx
        refreshGfx(true)
        runtimeField.text = runtimeText()
    }

    function refreshGfx(reset) {
        gfxInfo = gameModel.graphicsState(editAppid)
        if (reset === true) {
            gfxDxvk.checked = fields.graphics_dxvk === true
            var index = ["", "proton", "wine"].indexOf(fields.graphics_vkd3d || "")
            gfxVkd3d.currentIndex = index >= 0 ? index : 0
        }
        gfxStatus = gfxStatusText()
    }

    function gfxVkd3dValue() {
        return ["", "proton", "wine"][gfxVkd3d.currentIndex] || ""
    }

    function gfxStatusText() {
        var installed = gfxInfo.installed || {}
        var available = gfxInfo.available || {}
        var parts = []
        if (installed.dxvk) {
            parts.push("DXVK " + installed.dxvk)
        }
        if (installed.vkd3d) {
            parts.push("vkd3d-proton " + installed.vkd3d)
        }
        var text = parts.length > 0
            ? qsTr("In the prefix: %1").arg(parts.join(", "))
            : qsTr("Nothing installed in the prefix yet (installed at launch).")
        if (gfxDxvk.checked && !available.dxvk) {
            text += " " + qsTr("No DXVK version found in the configured directories.")
        }
        if (gfxVkd3dValue() === "proton" && !available.vkd3d) {
            text += " " + qsTr("No vkd3d-proton version found in the configured directories.")
        }
        return text
    }

    function protonChoicePath() {
        var i = protonBox.currentIndex
        if (i < 0 || i >= protonChoices.length) {
            return ""
        }
        return protonChoices[i].path || ""
    }

    function pushToControls() {
        var f = fields
        appidField.text = f.appid || ""
        nameField.text = (f.is_steam && editAppid !== "")
            ? (gameModel.gameNames([editAppid])[0] || editAppid)
            : (f.name || "")
        loadedName = nameField.text
        exeField.text = f.custom_executable || ""
        var types = typeValues()
        var typeIndex = types.indexOf(f.game_type || "")
        typeBox.currentIndex = typeIndex >= 0
            ? typeIndex
            : ((f.is_steam || defaultsMode) ? -1 : 0)
        runtimeField.text = runtimeText()
        prefixField.text = f.custom_prefix || ""
        argsField.text = f.launch_args || ""
        cwdField.text = f.launch_cwd || ""
        platformField.text = f.platform || ""
        catsField.text = (f.categories || []).join(", ")
        artIconField.text = f.art_icon || ""
        artCoverField.text = f.art_cover || ""
        artBannerField.text = f.art_banner || ""
        artDonorField.text = f.art_donor || ""
        menuCheck.checked = !!f.show_menu
        timeoutSpin.value = f.menu_timeout || 0
        notesArea.text = f.notes || ""
        dialogProfile = f.active_profile || ""
        profileBox.model = (f.profiles || []).slice()
        profileBox.currentIndex = Math.max(0, (f.profiles || []).indexOf(dialogProfile))
        settingsError.text = ""
        ppPre.text = f.pre_command || ""
        ppPreArgs.text = f.pre_args || ""
        ppPost.text = f.post_command || ""
        ppPostArgs.text = f.post_args || ""
        ppTimeout.value = f.pp_timeout || 60
        ppShell.checked = !!f.run_in_shell
        perfFeral.checked = !!f.gamemode_feral
        perfCachy.checked = !!f.gamemode_cachy
        dispOut.text = f.display_output || ""
        dispProv.currentIndex = {"auto": 0, "plasma": 1, "gnome": 2, "wlroots": 3, "x11": 4, "off": 5}[f.display_provider] ?? 0
        dmodeModel = [{"text": "", "data": ""}]
        dmodeBox.editText = f.display_mode || ""
        dmodeCurrent = ""
        dipSlider.value = f.dip_seconds || 8
        updateDip()
        gsEnable.checked = !!f.gamescope_enable
        gsArgs.text = f.gamescope_args || ""
        mhEnable.checked = !!f.mangohud_enable
        mhArgs.text = f.mangohud_args || ""
        refreshMangohudConfigs(f.mangohud_config || "")
        mhFps.value = f.mangohud_fps || 0
        rtEnable.checked = !!f.rt_enable
        rtArgs.text = f.rt_args || ""
        luEnable.checked = !!f.ludusavi_enable
        luRestore.checked = f.ludusavi_restore ?? true
        luBackup.checked = f.ludusavi_backup ?? true
        luName.text = f.ludusavi_name || ""
        luGui.checked = f.ludusavi_gui ?? true
        ntLaunch.checked = f.notify_on_launch ?? true
        seInhibit.checked = !!f.inhibit_idle
        nlDisable.checked = !!f.nl_disable
        nlProv.currentIndex = {"auto": 0, "plasma": 1, "gnome": 2, "off": 3}[f.nl_provider] ?? 0
        logField.text = editAppid !== "" ? gameModel.gameLogFile(editAppid) : ""
        ptFresh.checked = !!f.fresh_prefix
        refreshAudioSinks(f.audio_sink || "")
        winePrefixField.text = f.wine_prefix || ""
        refreshWineTools(f.wine_version || "")
        ptVerbs.text = f.winetricks_verbs || ""
        ptLog.checked = !!f.proton_log
        ptDebug.currentIndex = {"": 0, "-all": 1, "+err": 2, "+warn,+err": 3}[f.winedebug] ?? 0
        ptLogDir = editAppid !== "" ? gameModel.protonLogDir(editAppid) : ""
        var prefs = gameModel.loadPrefs()
        previewVisible = prefs.showPreview ?? false
        depStatusVisible = prefs.showDependencyStatus ?? false
        setEnvRows(f.env_vars || [])
        applyToolCheck(perfFeral, "gamemoderun")
        applyToolCheck(perfCachy, "game-performance")
        applyToolCheck(gsEnable, "gamescope")
        applyToolCheck(mhEnable, "mangohud")
        applyToolCheck(luEnable, "ludusavi")
        // After the availability pass, so the wrapper summary never
        // advertises a tool the command builder will skip (widgets
        // parity: gamemoderun missing -> GameMode stays out of the list).
        refreshRuntime()
        refreshPreview()
        // Opening the dialog is the one moment the Steam launch-options
        // scan runs (it reads the userdata files).
        refreshDependencyStatus(true)
        if (f.load_warning) {
            settingsError.text = f.load_warning
        }
        lastLoaded = snapshot()
    }

    function applyToolCheck(box, binary) {
        if (gameModel.toolAvailable(binary)) {
            box.enabled = true
            return
        }
        box.checked = false
        box.enabled = false
    }

    function collect() {
        var profiles = fields.profiles || []
        return {
            "name": nameField.text,
            "custom_executable": exeField.text,
            "game_type": typeValues()[typeBox.currentIndex] || "",
            "show_menu": menuCheck.checked,
            "menu_timeout": timeoutSpin.value,
            "custom_prefix": prefixField.text,
            "launch_args": argsField.text,
            "launch_cwd": cwdField.text,
            "platform": platformField.text,
            "categories": catsField.text,
            "art_icon": artIconField.text,
            "art_cover": artCoverField.text,
            "art_banner": artBannerField.text,
            "art_donor": artDonorField.text,
            "notes": notesArea.text,
            "profiles": profiles,
            "env_vars": collectEnv(),
            "pre_command": ppPre.text,
            "pre_args": ppPreArgs.text,
            "post_command": ppPost.text,
            "post_args": ppPostArgs.text,
            "pp_timeout": ppTimeout.value,
            "run_in_shell": ppShell.checked,
            "gamemode_feral": perfFeral.checked,
            "gamemode_cachy": perfCachy.checked,
            "display_provider": ["auto", "plasma", "gnome", "wlroots", "x11", "off"][dispProv.currentIndex] || "auto",
            "display_output": dispOut.text,
            "display_mode": dmodeCurrentText(),
            "dip_seconds": dipSlider.value,
            "gamescope_enable": gsEnable.checked,
            "gamescope_args": gsArgs.text,
            "mangohud_enable": mhEnable.checked,
            "mangohud_args": mhArgs.text,
            "mangohud_config": mhConfigData(),
            "mangohud_fps": mhFps.value,
            "rt_enable": rtEnable.checked,
            "rt_args": rtArgs.text,
            "ludusavi_enable": luEnable.checked,
            "ludusavi_restore": luRestore.checked,
            "ludusavi_backup": luBackup.checked,
            "ludusavi_name": luName.text,
            "ludusavi_gui": luGui.checked,
            "notify_on_launch": ntLaunch.checked,
            "inhibit_idle": seInhibit.checked,
            "nl_disable": nlDisable.checked,
            "nl_provider": ["auto", "plasma", "gnome", "off"][nlProv.currentIndex] || "auto",
            "fresh_prefix": ptFresh.checked,
            "audio_sink": audioSinkData(),            "wine_prefix": winePrefixField.text,
            "wine_version": wineToolData(),
            "winetricks_verbs": ptVerbs.text,
            "proton_log": ptLog.checked,
            "winedebug": ["", "-all", "+err", "+warn,+err"][ptDebug.currentIndex] || "",
            "runtime_wine_binary": localWineField.text,
            "runtime_proton_path": protonChoicePath(),
            "runtime_prefix_dir": localPrefixField.text,
            "graphics_dxvk": gfxDxvk.checked,
            "graphics_vkd3d": gfxVkd3dValue(),
            "active_profile": dialogProfile
        }
    }

    function snapshot() {
        var current = collect()
        delete current.profiles
        return JSON.stringify(current)
    }

    function isDirty() {
        return !defaultsMode && snapshot() !== lastLoaded
    }

    function requestProfileSwitch(index) {
        var profiles = profileBox.model || []
        var name = profiles[index] || ""
        if (name === dialogProfile) {
            return
        }
        if (isDirty()) {
            pendingProfile = name
            confirmLabel.text = qsTr(
                "You have unsaved changes. Save them before switching to profile '%1'?\n(The saved profile is kept.)").arg(name)
            confirmPurpose = "discardSwitch"
            confirmOk.text = qsTr("Discard")
            confirmDialog.open()
            profileBox.currentIndex = Math.max(0, profiles.indexOf(dialogProfile))
            return
        }
        switchProfile(name)
    }

    function switchProfile(name) {
        if (name === "") {
            fields = gameModel.loadGame(editAppid)
            pushToControls()
            gameModel.markActiveProfile(editAppid, "")
            lastLoaded = snapshot()
            refreshNewerFlag()
            return
        }
        var content = gameModel.profileContent(editAppid, name)
        if (Object.keys(content).length === 0) {
            settingsError.text = qsTr("Profile '%1' could not be read.").arg(name)
            profileBox.currentIndex = Math.max(0, (profileBox.model || []).indexOf(dialogProfile))
            return
        }
        fields = content
        pushToControls()
        dialogProfile = name
        profileBox.currentIndex = Math.max(0, (profileBox.model || []).indexOf(name))
        gameModel.markActiveProfile(editAppid, name)
        lastLoaded = snapshot()
        refreshNewerFlag()
    }

    function afterProfileSaved(name) {
        var fresh = gameModel.loadGame(editAppid)
        fields = fresh
        dialogProfile = name
        gameModel.markActiveProfile(editAppid, name)
        profileBox.model = (fresh.profiles || []).slice()
        profileBox.currentIndex = Math.max(0, (fresh.profiles || []).indexOf(name))
        lastLoaded = snapshot()
        refreshNewerFlag()
    }

    // Widgets focusInEvent: re-read the profile list, drop an active
    // profile that vanished on disk, and leave the draft alone otherwise.
    function refreshProfiles() {
        if (defaultsMode || editAppid === "") {
            return
        }
        var names = (gameModel.loadGame(editAppid).profiles || []).slice()
        var current = (profileBox.model || []).slice()
        if (names.join("\n") === current.join("\n")) {
            return
        }
        if (dialogProfile !== "" && names.indexOf(dialogProfile) < 0) {
            dialogProfile = ""
        }
        profileBox.model = names
        profileBox.currentIndex = Math.max(0, names.indexOf(dialogProfile))
    }

    function acceptConfirm() {
        if (confirmPurpose === "discardSwitch") {
            confirmDialog.close()
            switchProfile(pendingProfile)
        } else if (confirmPurpose === "overwriteProfile") {
            confirmDialog.close()
            if (!gameModel.saveGameProfile(editAppid, pendingName, collect())) {
                promptError.text = qsTr("Could not save the profile.")
                return
            }
            namePrompt.close()
            afterProfileSaved(pendingName)
            pendingName = ""
        } else if (confirmPurpose === "deleteProfile") {
            confirmDialog.close()
            var profiles = profileBox.model || []
            var name = profiles[profileBox.currentIndex] || ""
            if (name !== "" && gameModel.deleteGameProfile(editAppid, name)) {
                if (name === dialogProfile) {
                    reload()
                } else {
                    var fresh = gameModel.loadGame(editAppid)
                    fields = fresh
                    profileBox.model = (fresh.profiles || []).slice()
                    profileBox.currentIndex = Math.max(0, (fresh.profiles || []).indexOf(dialogProfile))
                    lastLoaded = snapshot()
                }
            }
        } else if (confirmPurpose === "resetDefaults") {
            confirmDialog.close()
            var vals = gameModel.templateGame(editAppid)
            vals.active_profile = ""
            if (gameModel.saveGame(editAppid, vals) === "") {
                settingsError.text = qsTr("Could not reset the game.")
                return
            }
            reload()
        } else if (confirmPurpose === "newerApp") {
            // Downgrade accepted: retry the action the gate interrupted.
            confirmDialog.close()
            newerVersion = false
            var gate = pendingGate
            pendingGate = ""
            if (gate === "save") {
                save()
            } else if (gate === "saveLaunch") {
                saveAndLaunch()
            } else if (gate === "saveSwitch") {
                if (saveFields()) {
                    switchProfile(pendingProfile)
                }
            } else if (gate === "reset") {
                resetDefaults()
            }
        } else if (confirmPurpose === "clearPrefix") {
            confirmDialog.close()
            var msg = gameModel.clearCustomPrefix(editAppid)
            if (msg !== "" && msg.indexOf("Cleared") !== 0) {
                settingsError.text = msg
            }
        }
        confirmPurpose = ""
    }

    // Profile switch with unsaved edits: Save keeps them on the current
    // source first (widgets _confirm_discard_changes, Save default),
    // Discard drops them, Cancel stays.
    function acceptConfirmSave() {
        confirmDialog.close()
        if (pendingProfile === "") {
            return
        }
        pendingGate = "saveSwitch"
        if (saveFields()) {
            switchProfile(pendingProfile)
        }
    }

    // Ask before downgrading a config written by a newer TKArcade
    // (widgets _confirm_newer_overwrite); acceptConfirm retries via
    // pendingGate.
    function askNewerOverwrite() {
        confirmLabel.text = qsTr("%1 Saving now will downgrade it and may lose settings. Continue?")
            .arg(qsTr("This configuration was written by a newer TKArcade."))
        confirmPurpose = "newerApp"
        confirmOk.text = qsTr("OK")
        confirmDialog.open()
    }

    // Per game: apply the Global Defaults *template* (widgets _on_reset),
    // written immediately -- a staged reset that Cancel silently discards
    // proved too easy to mistake for applied.
    function resetDefaults() {
        if (editAppid === "") {
            return
        }
        if (newerVersion) {
            pendingGate = "reset"
            askNewerOverwrite()
            return
        }
        var detail = dialogProfile !== ""
            ? qsTr("Unsaved changes to profile '%1' will be discarded (the saved profile is kept).").arg(dialogProfile)
            : (isDirty() ? qsTr("Unsaved changes will be discarded.")
                : qsTr("This overwrites the saved game config."))
        confirmLabel.text = qsTr("Reset this game to the Global Defaults template now?\n%1").arg(detail)
        confirmPurpose = "resetDefaults"
        confirmOk.text = qsTr("Reset")
        confirmDialog.open()
    }

    // Defaults editor: built-in factory values, in memory only -- Cancel
    // discards them, Save writes defaults.toml (widgets _on_reset_factory).
    function resetFactoryFields() {
        fields = gameModel.factoryGame("")
        pushToControls()
    }

    function collectEnv() {
        var out = []
        for (var i = 0; i < envModel.count; i++) {
            var row = envModel.get(i)
            out.push({"key": row.key, "value": row.value})
        }
        return out
    }

    function setEnvRows(rows) {
        envModel.clear()
        for (var i = 0; i < rows.length; i++) {
            envModel.append({"key": rows[i].key || "", "value": rows[i].value || ""})
        }
        // The widgets table always showed a row to type into; with no
        // variable saved, seed one empty row. An empty key is dropped on
        // save, so nothing is added until the user fills it in.
        if (envModel.count === 0) {
            envModel.append({"key": "", "value": ""})
        }
    }

    function envToText() {
        var lines = []
        for (var i = 0; i < envModel.count; i++) {
            var row = envModel.get(i)
            if (String(row.key).trim() !== "") {
                lines.push(String(row.key).trim() + "=" + row.value)
            }
        }
        return lines.join("\n")
    }

    function acceptBulk() {
        setEnvRows(gameModel.textToEnv(bulkArea.text))
        bulkDialog.close()
    }

    function openBulk() {
        bulkArea.text = envToText()
        bulkDialog.open()
    }

    function openPreset() {
        presetBox.model = gameModel.envPresetLabels()
        presetBox.currentIndex = 0
        presetDialog.open()
    }

    function acceptEnvPreset() {
        var name = gameModel.envPresetName(presetBox.currentText)
        if (name === "") {
            presetDialog.close()
            return
        }
        var mismatch = gameModel.envPresetMismatch(name, editAppid)
        if (mismatch !== "") {
            pendingPreset = name
            mismatchLabel.text = qsTr("Preset '%1' is for %2.\nApply anyway?").arg(name).arg(mismatch)
            mismatchDialog.open()
            return
        }
        applyEnvPresetByName(name)
    }

    function applyEnvPresetByName(name) {
        var res = gameModel.applyEnvPreset(collectEnv(), name)
        setEnvRows(res.rows || [])
        if ((res.added || 0) === 0) {
            settingsError.text = qsTr("Preset '%1': all keys already present.").arg(name)
        }
        mismatchDialog.close()
        presetDialog.close()
    }

    function envRowCount() {
        return envModel.count
    }

    function setEnvRow(i, key, value) {
        if (i >= 0 && i < envModel.count) {
            envModel.setProperty(i, "key", key)
            envModel.setProperty(i, "value", value)
        }
    }

    function dispProviderValue() {
        return ["auto", "plasma", "gnome", "wlroots", "x11", "off"][dispProv.currentIndex] || "auto"
    }

    function dmodeCurrentText() {
        var item = dmodeModel[dmodeBox.currentIndex]
        if (item !== undefined && item.data !== "") {
            return item.data
        }
        return dmodeBox.editText.trim()
    }

    function updateDip() {
        var show = dmodeCurrent !== "" && gameModel.displayModesMatch(dmodeCurrentText(), dmodeCurrent)
        dipRow.visible = show
        dipNote.visible = show
    }

    function refreshMangohudConfigs(select) {
        var items = [{"text": qsTr("Default (MangoHud.conf)"), "data": ""}]
        var names = gameModel.mangohudConfigs()
        for (var i = 0; i < names.length; i++) {
            items.push({"text": names[i], "data": names[i]})
        }
        mhConf.model = items
        var idx = 0
        for (var j = 0; j < items.length; j++) {
            if (items[j].data !== "" && items[j].data === select) {
                idx = j
            }
        }
        mhConf.currentIndex = idx
    }

    function mhConfigData() {
        var item = mhConf.model[mhConf.currentIndex]
        return item !== undefined ? item.data : ""
    }

    function refreshWineTools(select) {
        var tools = gameModel.wineTools()
        wineToolsData = tools
        var items = [{"text": qsTr("(Steam default)"), "data": ""}]
        var idx = 0
        for (var i = 0; i < tools.length; i++) {
            var label = tools[i][1] !== "" ? tools[i][0] + " (" + tools[i][1] + ")" : tools[i][0]
            items.push({"text": label, "data": tools[i][0]})
            if (tools[i][0] === select) {
                idx = i + 1
            }
        }
        if (select !== "" && idx === 0) {
            items.push({"text": qsTr("%1 (not installed)").arg(select), "data": select})
            idx = items.length - 1
        }
        wineToolBox.model = items
        wineToolBox.currentIndex = idx
    }

    function wineToolData() {
        var item = wineToolBox.model[wineToolBox.currentIndex]
        return item !== undefined ? item.data : ""
    }

    function refreshAudioSinks(select) {
        var sinks = gameModel.audioSinks()
        var items = [{"text": qsTr("(System default)"), "data": ""}]
        var idx = 0
        for (var i = 0; i < sinks.length; i++) {
            // The picker lists the human Description pactl reports; the
            // config keeps storing the node name (sinks[i][0]).
            items.push({"text": sinks[i][1] || sinks[i][0], "data": sinks[i][0]})
            if (sinks[i][0] === select) {
                idx = i + 1
            }
        }
        if (select !== "" && idx === 0) {
            items.push({"text": qsTr("%1 (unavailable)").arg(select), "data": select})
            idx = items.length - 1
        }
        auSinkBox.model = items
        auSinkBox.currentIndex = idx
    }

    function audioSinkData() {
        var item = auSinkBox.model[auSinkBox.currentIndex]
        return item !== undefined ? item.data : ""
    }

    function clearArtwork(kind) {
        if (gameModel.clearArtwork(editAppid, kind)) {
            if (kind === "icon") {
                artIconField.text = ""
            } else if (kind === "cover") {
                artCoverField.text = ""
            } else {
                artBannerField.text = ""
            }
        }
    }

    function askChoice(purpose, items, arg) {
        pendingPrompt = purpose
        pendingArg = arg || ""
        choiceError.text = ""
        choiceBox.model = items
        choiceBox.currentIndex = 0
        choicePrompt.open()
    }

    function acceptChoice() {
        if (pendingPrompt === "gsPreset") {
            var names = gameModel.gamescopePresets()
            var args = gameModel.gamescopePreset(names[choiceBox.currentIndex] || "")
            if (args !== "") {
                gsArgs.text = args
            }
            choicePrompt.close()
        } else if (pendingPrompt === "mhTemplate") {            // Positional twin of the labels passed at the ask site.
            var values = ["default", "minimal", "fps-cap", "full", "empty"]
            var path = gameModel.createMangohudConfig(pendingArg, values[choiceBox.currentIndex] || "default")
            if (path === "") {
                choiceError.text = qsTr("Could not create the config file.")
                return
            }
            choicePrompt.close()
            refreshMangohudConfigs(path.split("/").pop())
            if (!gameModel.openPath(path) && page !== null) {
                page.notify(qsTr("Could not open the config file."))
            }
        } else if (pendingPrompt === "artDonor") {
            var pick = choiceBox.model[choiceBox.currentIndex]
            if (pick !== undefined && pick.data !== "") {
                artDonorField.text = pick.data
            }
            choicePrompt.close()
        }
    }

    // The two bottom blocks toggle from their centered title checkboxes;
    // both choices persist in the preferences (the widgets kept the
    // preview flag in the Preferences dialog, the status box is ours).
    function setPreviewVisible(on) {
        if (previewVisible === on) {
            return
        }
        previewVisible = on
        gameModel.savePrefs({"showPreview": on})
    }

    function setDepStatusVisible(on) {
        if (depStatusVisible === on) {
            return
        }
        depStatusVisible = on
        gameModel.savePrefs({"showDependencyStatus": on})
    }

    function refreshPreview() {
        var res = gameModel.previewCommand(editAppid, collect())
        var lines = [res.command]
        var warns = res.warnings || []
        for (var i = 0; i < warns.length; i++) {
            lines.push("# warning: " + warns[i])
        }
        previewText.text = lines.join("\n")
        // Widgets parity: "Will launch with: A · B". The model returns the
        // joined list or the "No wrappers enabled" sentinel (kept for the
        // model contract); translate both cases here.
        var w = res.wrappers || ""
        previewWrappers.text = (w === "" || w === "No wrappers enabled")
            ? qsTr("No wrappers enabled")
            : qsTr("Will launch with: %1").arg(w)
        refreshDependencyStatus(false)
        previewSnapshot = snapshot()
    }

    // Widgets _wire_preview: every field edit refreshed the preview (and
    // the statuses behind it). Instead of wiring each of the dozens of
    // controls, the poll below compares the draft — `snapshot()` is the
    // same JSON the dirty check uses — and refreshes when it moved.
    function refreshPreviewIfStale() {
        if (snapshot() !== previewSnapshot) {
            refreshPreview()
        }
    }

    // Widgets Dependency Status: the draft's tools/paths as two columns of
    // ✓/⚠/● lines. `checkSteam` forces a fresh Steam launch-options probe
    // (the dialog asks on open; tab switches reuse the last one).
    function refreshDependencyStatus(checkSteam) {
        var rows = gameModel.dependencyStatus(editAppid, collect(), checkSteam === true)
        var out = []
        for (var i = 0; i < rows.length; i++) {
            out.push({
                "kind": rows[i].kind,
                "msg": rows[i].msg,
                "args": rows[i].args || [],
                "link": rows[i].link || ""
            })
        }
        statusBox.statusRows = out
    }

    // The model names the message ("msg") and passes its "%1..%n" values:
    // the wording lives here so lupdate sees every literal (the widgets
    // built these strings in Python, where they stayed untranslatable).
    function statusText(row) {
        var args = row.args || []
        switch (row.msg) {
        case "binary-ok":
            return qsTr("%1 — %2").arg(args[0]).arg(args[1])
        case "binary-off":
            return qsTr("%1 — %2 (off)").arg(args[0]).arg(args[1])
        case "binary-missing":
            return qsTr("%1 not found in PATH — skipped at launch").arg(args[0])
        case "binary-missing-fatal":
            return qsTr("%1 not found in PATH — launch will fail").arg(args[0])
        case "binary-absent":
            return qsTr("%1 not installed (feature off)").arg(args[0])
        case "prefix-none":
            return qsTr("No custom prefix — game launches directly")
        case "hook-ok":
            return qsTr("%1: %2").arg(args[0]).arg(args[1])
        case "hook-missing":
            return qsTr("%1 not found: %2").arg(args[0]).arg(args[1])
        case "ludusavi-flatpak":
            return qsTr("ludusavi via Flatpak (%1) — may not see Proton prefixes").arg(args[0])
        case "steam-ok":
            return qsTr("Steam launch options: %1").arg(args[0])
        case "steam-missing":
            return qsTr("Steam launch options lack tkarcade (add: tkarcade %command%)")
        case "steam-unknown":
            return qsTr("Steam userdata not found")
        }
        return ""
    }

    // The widgets picked its status colors from the theme's darkness
    // (game_dialog._is_dark_theme): same pairs, same marks.
    function statusColor(kind) {
        var colors = statusDark
            ? {"ok": "#7ee787", "warn": "#f47067", "note": "#e3b341"}
            : {"ok": "#1a7f37", "warn": "#d1242f", "note": "#9a6700"}
        return colors[kind] || colors["note"]
    }

    function escapeStatusText(text) {
        return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    }

    function statusLine(row) {
        var mark = row.kind === "warn" ? "⚠" : (row.kind === "note" ? "●" : "✓")
        var body = escapeStatusText(statusText(row))
        if (row.link !== undefined && row.link !== "") {
            body += " (<a href=\"" + row.link + "\">" + qsTr("Open folder") + "</a>)"
        }
        return "<span style=\"color:" + statusColor(row.kind) + "; font-weight:bold;\">"
            + mark + "</span> " + body
    }

    function save() {
        pendingGate = "save"
        if (saveFields()) {
            finish("saved")
        }
    }

    // Write the form; false means a validation error (or the downgrade
    // gate, which needs pendingGate set by the caller) is on screen and
    // the window must stay open.
    function saveFields() {
        if (newerVersion) {
            askNewerOverwrite()
            return false
        }
        // Steam games must name the type explicitly: no auto-detection and
        // no silent guess (the launcher refuses with exit 18). The defaults
        // template may stay unset, which keeps new games unset too.
        if (!defaultsMode && (fields.is_steam || false) && typeBox.currentIndex < 0) {
            settingsError.text = qsTr("Choose the game type: Windows (Proton) or Linux (native).")
            return false
        }
        if (defaultsMode) {
            if (!gameModel.saveDefaults(collect())) {
                settingsError.text = qsTr("Could not save the defaults.")
                return false
            }
            newerVersion = false
            return true
        }
        var created = gameModel.saveGame(editAppid, collect())
        if (created === "") {
            settingsError.text = editAppid === ""
                ? qsTr("Name and a valid executable are required.")
                : qsTr("Could not save the game.")
            return false
        }
        lastLoaded = snapshot()
        newerVersion = false
        if (editAppid === "" && page !== null) {
            page.select(created)
        }
        return true
    }

    // "Save & Launch" (editor only): persist, then hand the launch back.
    function saveAndLaunch() {
        pendingGate = "saveLaunch"
        if (saveFields()) {
            finish("launch")
        }
    }

    // "Launch" (editor only): widgets parity -- run with the *saved*
    // config, unsaved edits discarded.
    function launchWithoutSave() {
        finish("launch")
    }

    function askProfileName(purpose) {
        pendingPrompt = purpose
        pendingName = ""
        promptField.text = ""
        promptError.text = ""
        namePrompt.open()
    }

    function acceptProfileName() {
        var name = promptField.text.trim()
        if (name === "") {
            promptError.text = qsTr("Give the profile a name.")
            return
        }
        if (pendingPrompt === "mhName") {
            namePrompt.close()
            gameSettings.askChoice("mhTemplate", [
                qsTr("Copy of MangoHud.conf"),
                qsTr("Minimal overlay"),
                qsTr("FPS limiter overlay"),
                qsTr("Full metrics overlay"),
                qsTr("Empty file")
            ], name)
            return
        }
        var ok = false
        if (pendingPrompt === "saveAs") {
            if (gameModel.profileExists(editAppid, name) && pendingName !== name) {
                pendingName = name
                confirmLabel.text = qsTr("Overwrite profile '%1'?").arg(name)
                confirmPurpose = "overwriteProfile"
                confirmOk.text = qsTr("Overwrite")
                confirmDialog.open()
                return
            }
            pendingName = ""
            if (!gameModel.saveGameProfile(editAppid, name, collect())) {
                promptError.text = qsTr("Could not save the profile.")
                return
            }
            namePrompt.close()
            afterProfileSaved(name)
            return
        } else if (pendingPrompt === "clone") {
            var profiles = profileBox.model || []
            var src = profiles[profileBox.currentIndex] || ""
            if (src === "") {
                promptError.text = qsTr("Select a profile first.")
                return
            }
            if (src === name) {
                promptError.text = qsTr("Source and target are the same.")
                return
            }
            if (gameModel.profileExists(editAppid, name)) {
                promptError.text = qsTr("A profile with this name already exists.")
                return
            }
            ok = gameModel.cloneGameProfile(editAppid, src, name, collect())
        }
        if (!ok) {
            promptError.text = qsTr("Could not save the profile.")
            return
        }
        namePrompt.close()
        var fresh = gameModel.loadGame(editAppid)
        fields = fresh
        profileBox.model = (fresh.profiles || []).slice()
        profileBox.currentIndex = Math.max(0, (fresh.profiles || []).indexOf(dialogProfile))
        lastLoaded = snapshot()
    }

    Connections {
        target: gameModel
        function onDisplayModesFinished(modes) {
            var keep = dmodeCurrentText()
            var items = [{"text": "", "data": ""}]
            dmodeCurrent = ""
            for (var i = 0; i < modes.length; i++) {
                items.push({"text": modes[i][0], "data": modes[i][1]})
                if (modes[i][2]) {
                    dmodeCurrent = modes[i][1]
                }
            }
            dmodeModel = items
            var idx = -1
            for (var j = 0; j < items.length; j++) {
                if (items[j].data !== "" && items[j].data === keep) {
                    idx = j
                }
            }
            if (idx >= 0) {
                dmodeBox.currentIndex = idx
            } else {
                dmodeBox.editText = keep
            }
            updateDip()
        }
    }

    Connections {
        target: gameModel
        function onCoverageFinished(status, detail) {
            var messages = {
                "covered": qsTr("Ludusavi covers this game.\n%1").arg(detail),
                "no-local-saves": qsTr("Manifest entry exists, but no saves found.\n%1").arg(detail),
                "no-entry": qsTr("No manifest entry for this game.\nAdd a custom game entry in Ludusavi to enable backups."),
                "unavailable": qsTr("Could not check coverage:\n%1").arg(detail)
            }
            settingsError.text = messages[status] || detail
        }
    }

    // Live preview/status while the dialog is open (widgets _wire_preview
    // reacted to every widget). Cheap: `refreshPreviewIfStale` bails out
    // unless the draft changed.
    Timer {
        objectName: "previewPoller"
        interval: 200
        repeat: true
        running: gameSettings.visible
        onTriggered: gameSettings.refreshPreviewIfStale()
    }

    ColumnLayout {
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.smallSpacing
        // Focus-chain quit (see MainPage): fires even where the
        // Shortcut map stays silent.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        focus: true
        // Enter hits the default button like the widgets QDialog (an open
        // popup's accept first, else ours); a focused TextArea keeps Return.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(gameSettings, ["settingsSaveLaunch", "settingsSave"])
        }
        Controls.TabBar {
            id: tabBar
            objectName: "settingsTabs"
            Layout.fillWidth: true
            onCurrentIndexChanged: gameSettings.refreshPreview()
            Controls.TabButton {
                text: qsTr("General")
            }
            Controls.TabButton {
                text: qsTr("Launch")
            }
            Controls.TabButton {
                text: qsTr("Environment")
            }
            Controls.TabButton {
                text: qsTr("Compatibility")
            }
            Controls.TabButton {
                text: qsTr("Performance")
            }
            Controls.TabButton {
                text: qsTr("Display")
            }
            Controls.TabButton {
                text: qsTr("System")
            }
            Controls.TabButton {
                text: qsTr("Artwork/Notes")
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            objectName: "settingsStack"
            currentIndex: tabBar.currentIndex
            Controls.ScrollView {
                clip: true
                objectName: "settingsGeneralScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // ScrollView takes its scrollable size from the content's
                // implicitHeight; a plain Item has none, so sizing the
                // wrapper with `height:` leaves contentHeight at -1 and the
                // content is squeezed into the viewport (nothing scrolls).
                Item {
                    width: parent.width
                    implicitHeight: generalColumn.implicitHeight
                    ColumnLayout {
                        id: generalColumn
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Game")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: generalForm
                                objectName: "settingsGeneralForm"
                                // Fill the panel like the widgets form layout:
                                // labels in their own right-aligned column,
                                // fields stretched to the frame edge.
                                Layout.fillWidth: true
                                Controls.TextField {
                                    id: appidField
                                    objectName: "settingsAppid"
                                    visible: editAppid !== ""
                                    readOnly: true
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Steam App ID:")
                                }
                                Controls.TextField {
                                    id: nameField
                                    objectName: "settingsName"
                                    // Always shown per-game (widgets parity); readonly and
                                    // Steam-sourced for Steam games.
                                    visible: !defaultsMode
                                    readOnly: fields.is_steam || false
                                    placeholderText: qsTr("Game name")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Game name:")
                                }
                                Controls.ComboBox {
                                    id: typeBox
                                    objectName: "settingsType"
                                    Layout.fillWidth: true
                                    // The origin decides the choices: Steam
                                    // games use the Steam Proton runtime, local
                                    // games their own Wine or umu-run Proton.
                                    model: (defaultsMode || (fields.is_steam || false))
                                        ? [qsTr("Windows (Proton)"), qsTr("Linux (native)")]
                                        : [
                                            qsTr("Linux (native)"),
                                            qsTr("Windows (Wine)"),
                                            qsTr("Windows (Proton via UMU)")
                                        ]
                                    displayText: currentIndex >= 0 ? currentText : qsTr("Choose...")
                                    KirigamiLayouts.FormData.label: qsTr("Game type:")
                                    onActivated: {
                                        runtimeField.text = gameSettings.runtimeText()
                                        gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                Controls.TextField {
                                    id: runtimeField
                                    objectName: "settingsRuntime"
                                    visible: !defaultsMode && editAppid !== ""
                                        && typeBox.currentIndex >= 0
                                    readOnly: true
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Detected Runtime:")
                                }
                                Controls.TextField {
                                    id: platformField
                                    objectName: "settingsPlatform"
                                    placeholderText: qsTr("e.g. PC")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Platform:")
                                }
                                Controls.TextField {
                                    id: catsField
                                    objectName: "settingsCats"
                                    placeholderText: qsTr("Action, Retro (comma-separated)")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Categories:")
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Profile")
                            Layout.fillWidth: true
                            visible: editAppid !== ""
                            WidgetsFormLayout {
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Active:")
                                    Controls.ComboBox {
                                        id: profileBox
                                        objectName: "settingsProfiles"
                                        Layout.fillWidth: true
                                        textRole: "display"
                                        onActivated: (index) => gameSettings.requestProfileSwitch(index)
                                    }
                                    Controls.Button {
                                        objectName: "settingsProfileSave"
                                        text: qsTr("Save As…")
                                        onClicked: gameSettings.askProfileName("saveAs")
                                    }
                                    Controls.Button {
                                        objectName: "settingsProfileClone"
                                        text: qsTr("Clone…")
                                        onClicked: gameSettings.askProfileName("clone")
                                    }
                                    Controls.Button {
                                        objectName: "settingsProfileDelete"
                                        text: qsTr("Delete")
                                        onClicked: {
                                            var profiles = profileBox.model || []
                                            var name = profiles[profileBox.currentIndex] || ""
                                            if (name === "") {
                                                return
                                            }
                                            confirmLabel.text = qsTr("Delete profile '%1'? This cannot be undone.").arg(name)
                                            confirmPurpose = "deleteProfile"
                                            confirmOk.text = qsTr("Delete")
                                            confirmDialog.open()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Controls.ScrollView {
                clip: true
                objectName: "settingsLaunchScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // ScrollView takes its scrollable size from the content's
                // implicitHeight; a plain Item has none, so sizing the
                // wrapper with `height:` leaves contentHeight at -1 and the
                // content is squeezed into the viewport (nothing scrolls).
                Item {
                    width: parent.width
                    implicitHeight: launchColumn.implicitHeight
                    ColumnLayout {
                        id: launchColumn
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Launch")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Custom executable:")
                                    Controls.TextField {
                                        id: exeField
                                        objectName: "settingsExe"
                                        placeholderText: qsTr("Game executable")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "settingsBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: gameModel.browseExecutable()
                                    }
                                    Connections {
                                        target: gameModel
                                        function onBrowseFinished(picked) {
                                            if (!gameSettings.visible || picked === "") {
                                                gameSettings.pendingBrowse = ""
                                                return
                                            }
                                            if (gameSettings.pendingBrowse === "launchCwd") {
                                                cwdField.text = picked
                                            } else if (gameSettings.pendingBrowse === "winePrefix") {
                                                winePrefixField.text = picked
                                            } else if (gameSettings.pendingBrowse === "localWine") {
                                                localWineField.text = picked
                                            } else if (gameSettings.pendingBrowse === "localPrefix") {
                                                localPrefixField.text = picked
                                            } else if (gameSettings.pendingBrowse.indexOf("art:") === 0) {
                                                var kind = gameSettings.pendingBrowse.slice(4)
                                                var msg = gameModel.storeArtwork(
                                                    editAppid, kind, picked)
                                                if (msg !== "") {
                                                    settingsError.text = msg
                                                } else if (kind === "icon") {
                                                    artIconField.text = gameModel.artworkPath(editAppid, kind)
                                                } else if (kind === "cover") {
                                                    artCoverField.text = gameModel.artworkPath(editAppid, kind)
                                                } else {
                                                    artBannerField.text = gameModel.artworkPath(editAppid, kind)
                                                }
                                            } else {
                                                exeField.text = picked
                                                if (nameField.visible && nameField.text === "") {
                                                    var parts = picked.split("/")
                                                    nameField.text = parts[parts.length - 1]
                                                }
                                            }
                                            gameSettings.pendingBrowse = ""
                                        }
                                    }
                                }
                                Controls.TextField {
                                    id: prefixField
                                    objectName: "settingsPrefix"
                                    placeholderText: qsTr("e.g. zink-run")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Custom command prefix:")
                                }
                                Controls.TextField {
                                    id: argsField
                                    objectName: "settingsArgs"
                                    placeholderText: qsTr("e.g. --fullscreen -v")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Extra launch args:")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Working directory:")
                                    Controls.TextField {
                                        id: cwdField
                                        objectName: "settingsCwd"
                                        placeholderText: qsTr("empty = game folder")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "settingsCwdBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "launchCwd"
                                            gameModel.pickDir(qsTr("Working directory"), qsTr("Select"))
                                        }
                                    }
                                }
                                Controls.CheckBox {
                                    id: menuCheck
                                    objectName: "settingsMenu"
                                    text: qsTr("Show menu before launch")
                                }
                                Controls.SpinBox {
                                    id: timeoutSpin
                                    objectName: "settingsTimeout"
                                    from: 0
                                    to: 600
                                    KirigamiLayouts.FormData.label: qsTr("Menu timeout (seconds):")
                                }
                                RowLayout {
                                    visible: editAppid !== ""
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Log File:")
                                    Controls.TextField {
                                        id: logField
                                        objectName: "settingsLog"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "settingsLogOpen"
                                        text: qsTr("Open")
                                        onClicked: {
                                            if (!gameModel.openPath(logField.text)) {
                                                settingsError.text = qsTr("Could not open the log file.")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Pre/Post Commands")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: ppForm
                                Layout.fillWidth: true
                                Controls.TextField {
                                    id: ppPre
                                    objectName: "ppPre"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Pre-launch command:")
                                }
                                Controls.TextField {
                                    id: ppPreArgs
                                    objectName: "ppPreArgs"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Pre-launch arguments:")
                                }
                                Controls.TextField {
                                    id: ppPost
                                    objectName: "ppPost"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Post-exit command:")
                                }
                                Controls.TextField {
                                    id: ppPostArgs
                                    objectName: "ppPostArgs"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Post-exit arguments:")
                                }
                                Controls.SpinBox {
                                    id: ppTimeout
                                    objectName: "ppTimeout"
                                    from: 1
                                    to: 3600
                                    KirigamiLayouts.FormData.label: qsTr("Timeout (seconds):")
                                }
                                Controls.CheckBox {
                                    id: ppShell
                                    objectName: "ppShell"
                                    text: qsTr("Run in shell (bash -c)")
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                SectionBox {
                    title: qsTr("Environment Variables")
                    fillHeight: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    RowLayout {
                        // Widgets QTableWidget header; it lines up with the rows
                        // below, whose third column holds the per-row remove
                        // button (Kirigami only, hence the matching gap).
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Controls.Label {
                            objectName: "envHeaderVariable"
                            Layout.fillWidth: true
                            // QtQuick.Layouts splits the extra space proportionally
                            // to the preferred widths, so both header cells ask for
                            // the same hint to land on the row columns below.
                            Layout.preferredWidth: Kirigami.Units.gridUnit
                            horizontalAlignment: Text.AlignHCenter
                            font.bold: true
                            text: qsTr("Variable")
                        }
                        Controls.Label {
                            objectName: "envHeaderValue"
                            Layout.fillWidth: true
                            Layout.preferredWidth: Kirigami.Units.gridUnit
                            horizontalAlignment: Text.AlignHCenter
                            font.bold: true
                            text: qsTr("Value")
                        }
                        Item {
                            Layout.preferredWidth: envRemoveProto.implicitWidth
                        }
                    }
                    Controls.ScrollView {
                        clip: true
                        objectName: "settingsEnvRowsScroll"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Item {
                            width: parent.width
                            implicitHeight: envForm.implicitHeight
                            ColumnLayout {
                                id: envForm
                                objectName: "envForm"
                                width: parent.width
                                spacing: Kirigami.Units.smallSpacing
                                property int currentRow: -1
                                ListModel {
                                    id: envModel
                                }
                                Controls.ToolButton {
                                    id: envRemoveProto
                                    visible: false
                                    icon.name: "list-remove"
                                    display: Controls.AbstractButton.IconOnly
                                }
                                Repeater {
                                    model: envModel
                                    delegate: RowLayout {
                                        objectName: "envRow"
                                        width: envForm.width
                                        spacing: Kirigami.Units.smallSpacing
                                        Controls.TextField {
                                            Layout.fillWidth: true
                                            placeholderText: qsTr("Variable")
                                            text: key
                                            onTextChanged: envModel.setProperty(index, "key", text)
                                            onActiveFocusChanged: {
                                                if (activeFocus) {
                                                    envForm.currentRow = index
                                                }
                                            }
                                        }
                                        Controls.TextField {
                                            Layout.fillWidth: true
                                            placeholderText: qsTr("Value")
                                            text: value
                                            onTextChanged: envModel.setProperty(index, "value", text)
                                            onActiveFocusChanged: {
                                                if (activeFocus) {
                                                    envForm.currentRow = index
                                                }
                                            }
                                        }
                                        Controls.ToolButton {
                                            icon.name: "list-remove"
                                            display: Controls.AbstractButton.IconOnly
                                            onClicked: {
                                                envModel.remove(index)
                                                envForm.currentRow = -1
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                RowLayout {
                    // Centered, in the widgets order: Add, Bulk Edit...,
                    // Add Preset..., then the destructive Remove last.
                    Layout.fillWidth: true
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        objectName: "envAdd"
                        text: qsTr("Add")
                        onClicked: {
                            envModel.append({"key": "", "value": ""})
                            envForm.currentRow = envModel.count - 1
                        }
                    }
                    Controls.Button {
                        objectName: "envBulk"
                        text: qsTr("Bulk Edit...")
                        onClicked: gameSettings.openBulk()
                    }
                    Controls.Button {
                        objectName: "envPreset"
                        text: qsTr("Add Preset...")
                        onClicked: gameSettings.openPreset()
                    }
                    Controls.Button {
                        objectName: "envRemove"
                        text: qsTr("Remove")
                        // Widgets: removes the table's selected row. Here the
                        // last row whose field took focus plays that role.
                        enabled: envForm.currentRow >= 0 && envForm.currentRow < envModel.count
                        onClicked: {
                            envModel.remove(envForm.currentRow)
                            envForm.currentRow = -1
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                }
            }
            Controls.ScrollView {
                clip: true
                objectName: "settingsWineScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // ScrollView takes its scrollable size from the content's
                // implicitHeight; a plain Item has none, so sizing the
                // wrapper with `height:` leaves contentHeight at -1 and the
                // content is squeezed into the viewport (nothing scrolls).
                Item {
                    width: parent.width
                    implicitHeight: compatColumn.implicitHeight
                    ColumnLayout {
                        id: compatColumn
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Windows runtime")
                            Layout.fillWidth: true
                            visible: !defaultsMode && !(fields.is_steam || false)
                            WidgetsFormLayout {
                                id: localForm
                                objectName: "localRuntimeForm"
                                Layout.fillWidth: true
                                Controls.Label {
                                    objectName: "localRuntimeHint"
                                    Layout.fillWidth: true
                                    wrapMode: Text.WordWrap
                                    text: qsTr("Local Windows games run through Wine or Proton (umu-run). Nothing is downloaded: pick an installed tool.")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex === 1
                                    KirigamiLayouts.FormData.label: qsTr("Wine binary:")
                                    Controls.TextField {
                                        id: localWineField
                                        objectName: "settingsLocalWine"
                                        Layout.fillWidth: true
                                        onTextChanged: runtimeField.text = gameSettings.runtimeText()
                                    }
                                    Controls.Button {
                                        objectName: "settingsLocalWineBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "localWine"
                                            gameModel.pickPath(qsTr("Wine binary"), qsTr("Select"))
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex === 2
                                    KirigamiLayouts.FormData.label: qsTr("Proton:")
                                    Controls.ComboBox {
                                        id: protonBox
                                        objectName: "settingsLocalProton"
                                        Layout.fillWidth: true
                                        displayText: count > 0 ? currentText : qsTr("No Proton install found")
                                        onActivated: runtimeField.text = gameSettings.runtimeText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex >= 1
                                    KirigamiLayouts.FormData.label: qsTr("Prefix dir:")
                                    Controls.TextField {
                                        id: localPrefixField
                                        objectName: "settingsLocalPrefix"
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "settingsLocalPrefixBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "localPrefix"
                                            gameModel.pickDir(qsTr("Prefix dir"), qsTr("Select"))
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex >= 1
                                    KirigamiLayouts.FormData.label: qsTr("DXVK:")
                                    Controls.CheckBox {
                                        id: gfxDxvk
                                        objectName: "settingsGraphicsDxvk"
                                        text: qsTr("D3D9/10/11 through DXVK")
                                        onCheckedChanged: gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex >= 1
                                    KirigamiLayouts.FormData.label: qsTr("D3D12 layer:")
                                    Controls.ComboBox {
                                        id: gfxVkd3d
                                        objectName: "settingsGraphicsVkd3d"
                                        Layout.fillWidth: true
                                        model: [
                                            qsTr("Off (Wine builtin)"),
                                            qsTr("vkd3d-proton"),
                                            qsTr("vkd3d (Wine builtin, lower compatibility)")
                                        ]
                                        onActivated: gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: typeBox.currentIndex >= 1
                                    Controls.Label {
                                        objectName: "settingsGfxStatus"
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        text: gameSettings.gfxStatus
                                    }
                                    Controls.Button {
                                        objectName: "settingsGfxRemove"
                                        text: qsTr("Remove from prefix")
                                        enabled: Object.keys(gameSettings.gfxInfo.installed || {}).length > 0
                                        onClicked: {
                                            var msg = gameModel.removeGraphics(editAppid)
                                            if (msg !== "") {
                                                settingsError.text = msg
                                            }
                                            gameSettings.refreshGfx(false)
                                        }
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Wine")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: wineForm
                                objectName: "wineForm"
                                Layout.fillWidth: true
                                enabled: gameSettings.wineAvailable
                                Controls.CheckBox {
                                    id: ptFresh
                                    objectName: "ptFresh"
                                    text: qsTr("Delete prefix before launch (fresh start)")
                                    Controls.ToolTip.text: qsTr("Deletes the compatdata prefix so Steam recreates it. WIPES saves inside the prefix — rely on cloud or Ludusavi backups!")
                                    Controls.ToolTip.visible: hovered
                                }
                                Controls.TextField {
                                    id: ptVerbs
                                    objectName: "ptVerbs"
                                    placeholderText: qsTr("dotnet48 vcrun2022 (space-separated)")
                                    Controls.ToolTip.text: qsTr("Winetricks verbs installed via protontricks before launch.")
                                    Controls.ToolTip.visible: hovered
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Winetricks Verbs:")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Custom prefix dir:")
                                    Controls.TextField {
                                        id: winePrefixField
                                        objectName: "winePrefix"
                                        placeholderText: qsTr("empty = Steam default")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "winePrefix"
                                            gameModel.pickDir(qsTr("Custom prefix dir"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixCreate"
                                        text: qsTr("Create")
                                        onClicked: {
                                            var msg = gameModel.ensurePrefix(editAppid)
                                            if (msg !== "") {
                                                settingsError.text = msg
                                            }
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixClear"
                                        text: qsTr("Clear…")
                                        onClicked: {
                                            if (winePrefixField.text.trim() === "") {
                                                return
                                            }
                                            confirmLabel.text = qsTr(
                                                "Delete the custom prefix dir now?\n%1\nSaves inside are lost.").arg(
                                                winePrefixField.text.trim())
                                            confirmPurpose = "clearPrefix"
                                            confirmOk.text = qsTr("Delete")
                                            confirmDialog.open()
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixOpen"
                                        text: qsTr("Open")
                                        onClicked: {
                                            if (!gameModel.openPath(gameModel.prefixDir(editAppid))) {
                                                settingsError.text = qsTr("Could not open the prefix folder.")
                                            }
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Compat tool:")
                                    Controls.ComboBox {
                                        id: wineToolBox
                                        objectName: "wineTool"
                                        textRole: "text"
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "wineToolApply"
                                        text: qsTr("Apply")
                                        onClicked: {
                                            var msg = gameModel.applyWineVersion(editAppid, gameSettings.wineToolData())
                                            if (msg !== "") {
                                                settingsError.text = msg
                                            } else {
                                                gameSettings.refreshWineTools(gameSettings.wineToolData())
                                            }
                                        }
                                    }
                                }
                            }
                            // A local game has no compatdata prefix: the tab
                            // stays reachable and says why, instead of a grey
                            // wall (or a disabled tab button).
                            Controls.Label {
                                objectName: "wineSteamOnlyNote"
                                visible: !gameSettings.wineAvailable
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                text: qsTr("These are Steam Proton settings. Local games use the Windows runtime section.")
                            }
                        }
                        SectionBox {
                            title: qsTr("Proton")
                            Layout.fillWidth: true
                            visible: gameSettings.wineAvailable
                            WidgetsFormLayout {
                                Layout.fillWidth: true
                                enabled: gameSettings.wineAvailable
                                RowLayout {
                                    visible: editAppid !== ""
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: ptLog
                                        objectName: "ptLog"
                                        text: qsTr("Capture Proton log (disk-heavy)")
                                        Controls.ToolTip.text: qsTr("Sets PROTON_LOG=1 with a per-game log dir (Proton only).")
                                        Controls.ToolTip.visible: hovered
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        text: qsTr("Open")
                                        onClicked: {
                                            if (!gameModel.openPath(ptLogDir)) {
                                                settingsError.text = qsTr("Could not open the Proton log folder.")
                                            }
                                        }
                                    }
                                }
                                Controls.ComboBox {
                                    id: ptDebug
                                    objectName: "ptDebug"
                                    Layout.fillWidth: true
                                    model: [qsTr("Off"), qsTr("Quiet (-all)"), qsTr("Errors (+err)"), qsTr("Warnings (+warn,+err)")]
                                    Controls.ToolTip.text: qsTr("Sets WINEDEBUG for Wine/Proton output.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("Wine Debug:")
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    objectName: "settingsPerfScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        implicitHeight: perfForm.implicitHeight
                        ColumnLayout {
                            id: perfForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Game Mode")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: perfFeral
                                        objectName: "perfFeral"
                                        text: qsTr("Enable Feral GameMode (gamemoderun)")
                                        Controls.ToolTip.text: qsTr("Optimizes CPU and GPU governors while the game runs. Mutually exclusive with CachyOS game-performance.")
                                        Controls.ToolTip.visible: hovered
                                        onCheckedChanged: {
                                            if (checked) {
                                                perfCachy.checked = false
                                            }
                                        }
                                    }
                                    Controls.CheckBox {
                                        id: perfCachy
                                        objectName: "perfCachy"
                                        text: qsTr("Enable CachyOS game-performance")
                                        Controls.ToolTip.text: qsTr("Applies the CachyOS gaming performance profile. Mutually exclusive with Feral GameMode.")
                                        Controls.ToolTip.visible: hovered
                                        onCheckedChanged: {
                                            if (checked) {
                                                perfFeral.checked = false
                                            }
                                        }
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("MangoHud")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Controls.CheckBox {
                                        id: mhEnable
                                        objectName: "mhEnable"
                                        text: qsTr("Enable MangoHud")
                                    }
                                    Controls.TextField {
                                        id: mhArgs
                                        objectName: "mhArgs"
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("MangoHud Options:")
                                    }
                                    // Kirigami keeps the FPS cap the widgets
                                    // r240 dropped from its dialog.
                                    Controls.SpinBox {
                                        id: mhFps
                                        objectName: "mhFps"
                                        from: 0
                                        to: 999
                                        KirigamiLayouts.FormData.label: qsTr("FPS limit (0 = off):")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("MangoHud Configuration:")
                                        Controls.ComboBox {
                                            id: mhConf
                                            objectName: "mhConf"
                                            textRole: "text"
                                            Layout.fillWidth: true
                                        }
                                        Controls.Button {
                                            objectName: "mhNew"
                                            text: qsTr("New Configuration…")
                                            onClicked: gameSettings.askProfileName("mhName")
                                        }
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("RT Upscaler")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Controls.CheckBox {
                                        id: rtEnable
                                        objectName: "rtEnable"
                                        text: qsTr("Enable RT Upscaler (linux-rt-upscaler)")
                                        Controls.ToolTip.text: qsTr("SRCNN upscaling for X11/XWayland windows; forces PROTON_ENABLE_WAYLAND=0.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.TextField {
                                        id: rtArgs
                                        objectName: "rtArgs"
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Upscaler Options:")
                                        placeholderText: qsTr("-m 4x24 (see upscale --help-all)")
                                    }
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    objectName: "settingsDisplayScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        implicitHeight: dispForm.implicitHeight
                        ColumnLayout {
                            id: dispForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Display Mode")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Controls.TextField {
                                        id: dispOut
                                        objectName: "dispOut"
                                        placeholderText: qsTr("auto = current output")
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Output:")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Mode:")
                                        Controls.ComboBox {
                                            id: dmodeBox
                                            objectName: "dmodeBox"
                                            editable: true
                                            model: dmodeModel
                                            textRole: "text"
                                            Layout.fillWidth: true
                                            onEditTextChanged: gameSettings.updateDip()
                                        }
                                        Controls.Button {
                                            objectName: "dispRefresh"
                                            text: qsTr("Refresh")
                                            onClicked: gameModel.refreshDisplayModes(gameSettings.dispProviderValue(), dispOut.text.trim())
                                        }
                                    }
                                    // Widgets: the provider combo keeps its
                                    // content width instead of stretching.
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Provider:")
                                        Controls.ComboBox {
                                            id: dispProv
                                            objectName: "dispProv"
                                            model: [qsTr("Automatic"), qsTr("Plasma"), qsTr("GNOME"), qsTr("wlroots"), qsTr("X11"), qsTr("Disabled")]
                                        }
                                    }
                                    Controls.Label {
                                        id: dipNote
                                        objectName: "dipNote"
                                        visible: false
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        text: qsTr("Same mode as current: dips down and back first (VRAM workaround).")
                                    }
                                    RowLayout {
                                        id: dipRow
                                        objectName: "dipRow"
                                        visible: false
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Dip delay:")
                                        Controls.Slider {
                                            id: dipSlider
                                            objectName: "dipSlider"
                                            Layout.fillWidth: true
                                            from: 3
                                            to: 15
                                            stepSize: 1
                                        }
                                        Controls.Label {
                                            text: qsTr("%1 s").arg(dipSlider.value)
                                        }
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Gamescope")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Controls.CheckBox {
                                        id: gsEnable
                                        objectName: "gsEnable"
                                        text: qsTr("Enable Gamescope")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Gamescope Options:")
                                        Controls.TextField {
                                            id: gsArgs
                                            objectName: "gsArgs"
                                            placeholderText: qsTr("-f -H 1080 -r 144")
                                            Layout.fillWidth: true
                                        }
                                        Controls.Button {
                                            objectName: "gsPreset"
                                            text: qsTr("Preset…")
                                            onClicked: gameSettings.askChoice("gsPreset", gameModel.gamescopePresets(), "")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    objectName: "settingsSystemScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        implicitHeight: sysForm.implicitHeight
                        ColumnLayout {
                            id: sysForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Notifications")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: ntLaunch
                                        objectName: "ntLaunch"
                                        text: qsTr("Notify on launch")
                                        Controls.ToolTip.text: qsTr("Show a transient summary notification when the game starts.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Idle Suspend")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: seInhibit
                                        objectName: "seInhibit"
                                        text: qsTr("Inhibit idle suspend while playing")
                                        Controls.ToolTip.text: qsTr("Holds a logind idle lock during the session. Sleep lock is not included (needs privileges).")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Night Light")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: nlDisable
                                        objectName: "nlDisable"
                                        text: qsTr("Disable night light while the game is running (restored on exit)")
                                    }
                                    Controls.ComboBox {
                                        id: nlProv
                                        objectName: "nlProv"
                                        Layout.fillWidth: true
                                        model: [qsTr("Automatic"), qsTr("Plasma"), qsTr("GNOME"), qsTr("Disabled")]
                                        KirigamiLayouts.FormData.label: qsTr("Provider:")
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Audio")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    Layout.fillWidth: true
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Output sink:")
                                        Controls.ComboBox {
                                            id: auSinkBox
                                            objectName: "auSink"
                                            textRole: "text"
                                            Layout.fillWidth: true
                                        }
                                        Controls.Button {
                                            objectName: "auRefresh"
                                            text: qsTr("Refresh")
                                            onClicked: gameSettings.refreshAudioSinks(gameSettings.audioSinkData())
                                        }
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Saves (Ludusavi)")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: luForm
                                    objectName: "luForm"
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: luEnable
                                        objectName: "luEnable"
                                        text: qsTr("Enable Ludusavi for this game")
                                    }
                                    Controls.CheckBox {
                                        id: luRestore
                                        objectName: "luRestore"
                                        text: qsTr("Restore backup before launch")
                                        Controls.ToolTip.text: qsTr("Unchecked = --no-restore")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.CheckBox {
                                        id: luBackup
                                        objectName: "luBackup"
                                        text: qsTr("Back up after exit")
                                        Controls.ToolTip.text: qsTr("Unchecked = --no-backup")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.TextField {
                                        id: luName
                                        objectName: "luName"
                                        placeholderText: qsTr("Leave empty to detect the game from Steam")
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Game Name Override:")
                                    }
                                    Controls.CheckBox {
                                        id: luGui
                                        objectName: "luGui"
                                        text: qsTr("Show Prompts (--gui)")
                                        Controls.ToolTip.text: qsTr("With prompts enabled, restore and backup can be declined per session.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Label {
                                        // The widgets adds this note as a spanning row
                                        // (addRow with a single widget), not as a field.
                                        objectName: "luNote"
                                        KirigamiLayouts.FormData.isSection: true
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        text: qsTr("With prompts enabled, restore and backup can be declined per session.")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        visible: editAppid !== ""
                                        KirigamiLayouts.FormData.label: qsTr("Coverage:")
                                        Controls.Button {
                                            objectName: "luCoverage"
                                            text: qsTr("Check Coverage...")
                                            onClicked: gameModel.checkCoverage(editAppid, luName.text)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Controls.ScrollView {
                clip: true
                objectName: "settingsArtworkScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // ScrollView takes its scrollable size from the content's
                // implicitHeight; a plain Item has none, so sizing the
                // wrapper with `height:` leaves contentHeight at -1 and the
                // content is squeezed into the viewport (nothing scrolls).
                Item {
                    width: parent.width
                    implicitHeight: artColumn.implicitHeight
                    ColumnLayout {
                        id: artColumn
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Artwork")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: artForm
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Icon override:")
                                    Controls.TextField {
                                        id: artIconField
                                        objectName: "artIcon"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artIconPick"
                                        text: qsTr("Pick…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:icon"
                                            gameModel.pickPath(qsTr("Icon image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artIconClear"
                                        text: qsTr("Clear")
                                        onClicked: gameSettings.clearArtwork("icon")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Cover image:")
                                    Controls.TextField {
                                        id: artCoverField
                                        objectName: "artCover"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artCoverPick"
                                        text: qsTr("Pick…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:cover"
                                            gameModel.pickPath(qsTr("Cover image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artCoverClear"
                                        text: qsTr("Clear")
                                        onClicked: gameSettings.clearArtwork("cover")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Banner image:")
                                    Controls.TextField {
                                        id: artBannerField
                                        objectName: "artBanner"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artBannerPick"
                                        text: qsTr("Pick…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:banner"
                                            gameModel.pickPath(qsTr("Banner image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artBannerClear"
                                        text: qsTr("Clear")
                                        onClicked: gameSettings.clearArtwork("banner")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Donor AppID:")
                                    Controls.TextField {
                                        id: artDonorField
                                        objectName: "artDonor"
                                        placeholderText: qsTr("Steam AppID to reuse art from")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artDonorFind"
                                        text: qsTr("Find…")
                                        onClicked: {
                                            var rows = gameModel.donorCandidates("")
                                            var items = []
                                            for (var i = 0; i < rows.length; i++) {
                                                items.push({"text": rows[i][1] + " [" + rows[i][0] + "]", "data": rows[i][0]})
                                            }
                                            gameSettings.askChoice("artDonor", items, "")
                                        }
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Notes")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                Layout.fillWidth: true
                                Controls.TextArea {
                                    id: notesArea
                                    objectName: "settingsNotes"
                                    placeholderText: qsTr("Notes for this game…")
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    // Five lines of the default font: a note
                                    // box, not a document editor. The implicit
                                    // height is what sizes the section frame.
                                    implicitHeight: Kirigami.Units.gridUnit * 6
                                }
                            }
                        }
                    }
                }
            }
        }
        SectionBox {
            id: statusBox
            objectName: "depStatusBox"
            Layout.fillWidth: true
            // A wider gap than the column spacing: the tab body and its
            // scrolling viewport end here, the status block is the
            // dialog's own footer (all tabs share this shell).
            Layout.topMargin: Kirigami.Units.largeSpacing
            title: qsTr("Dependency Status")
            checkable: true
            checked: gameSettings.depStatusVisible
            onCheckedChanged: gameSettings.setDepStatusVisible(checked)
            property var statusRows: []
            GridLayout {
                id: depGrid
                objectName: "depStatusGrid"
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Kirigami.Units.largeSpacing * 2
                rowSpacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: statusBox.statusRows
                    delegate: Controls.Label {
                        required property var modelData
                        objectName: "depStatusLine"
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        textFormat: Text.RichText
                        wrapMode: Text.WordWrap
                        text: gameSettings.statusLine(modelData)
                        onLinkActivated: (link) => {
                            if (!gameModel.openPath(link) && gameSettings.page !== null) {
                                gameSettings.page.notify(qsTr("Could not open the link."))
                            }
                        }
                    }
                }
            }
        }
        SectionBox {
            id: previewBox
            objectName: "previewBox"
            Layout.fillWidth: true
            title: qsTr("Launch Command Preview")
            checkable: true
            checked: gameSettings.previewVisible
            onCheckedChanged: gameSettings.setPreviewVisible(checked)
            Controls.TextArea {
                id: previewText
                objectName: "previewText"
                readOnly: true
                font.family: "monospace"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 4
            }
            RowLayout {
                Layout.fillWidth: true
                Item {
                    Layout.fillWidth: true
                }
                Controls.Button {
                    objectName: "previewRefresh"
                    text: qsTr("Refresh")
                    onClicked: gameSettings.refreshPreview()
                }
            }
        }
        Controls.Label {
            id: settingsError
            objectName: "settingsError"
            visible: text !== ""
            color: Kirigami.Theme.negativeTextColor
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Controls.Label {
            id: previewWrappers
            objectName: "previewWrappers"
            Layout.fillWidth: true
            font: Kirigami.Theme.smallFont
            elide: Text.ElideRight
        }
        RowLayout {
            // Widgets QDialogButtonBox (GNOME/Breeze layout): the reset and
            // diff actions lead, the accept/cancel pair closes the row.
            Layout.fillWidth: true
            Controls.Button {
                objectName: "diffButton"
                // Widgets offered Diff vs Defaults for a game only: the
                // defaults editor edits the template itself.
                visible: !gameSettings.defaultsMode
                text: qsTr("Diff vs Defaults")
                onClicked: {
                    var diff = gameModel.diffDefaults(editAppid, gameSettings.collect())
                    diffText.text = diff !== "" ? diff : qsTr("(no differences)")
                    diffDialog.open()
                }
            }
            Controls.Button {
                objectName: "settingsReset"
                visible: gameSettings.defaultsMode || gameSettings.editAppid !== ""
                text: gameSettings.defaultsMode
                    ? qsTr("Reset to Factory Defaults")
                    : qsTr("Reset to Global Defaults")
                onClicked: gameSettings.defaultsMode
                    ? gameSettings.resetFactoryFields()
                    : gameSettings.resetDefaults()
            }
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsLaunch"
                visible: gameSettings.launchMode && gameSettings.canLaunch
                text: qsTr("Launch")
                icon.name: gameModel.iconName(["media-playback-start", "player-play"])
                onClicked: gameSettings.launchWithoutSave()
            }
            Controls.Button {
                objectName: "settingsSave"
                text: qsTr("Save")
                icon.name: gameModel.iconName(["document-save", "document-save-as"])
                // The widgets made Save the default button.
                highlighted: true
                onClicked: gameSettings.save()
            }
            Controls.Button {
                objectName: "settingsSaveLaunch"
                visible: gameSettings.launchMode && gameSettings.canLaunch
                text: qsTr("Save & Launch")
                icon.name: gameModel.iconName(["media-playback-start", "player-play"])
                onClicked: gameSettings.saveAndLaunch()
            }
            Controls.Button {
                objectName: "settingsCancel"
                text: qsTr("Cancel")
                icon.name: gameModel.iconName(["window-close", "dialog-cancel"])
                onClicked: gameSettings.finish("cancelled")
            }
        }
    }

    // The prompts are Popups. Kirigami parents them to
    // applicationWindow().overlay, which only exists inside a
    // Kirigami.ApplicationWindow; this file is a plain modal Window, so
    // without an explicit parent each prompt became a stray native window
    // behind the settings window (unusable while the window is modal).
    Kirigami.Dialog {
        id: namePrompt
        parent: gameSettings.contentItem
        objectName: "settingsNamePrompt"
        title: pendingPrompt === "mhName" ? qsTr("New MangoHud Configuration") : (pendingPrompt === "clone" ? qsTr("Clone profile") : qsTr("Save profile"))
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.TextField {
                id: promptField
                objectName: "settingsPromptField"
                placeholderText: qsTr("Profile name")
                Layout.fillWidth: true
                onAccepted: gameSettings.acceptProfileName()
            }
            Controls.Label {
                id: promptError
                visible: text !== ""
                color: Kirigami.Theme.negativeTextColor
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsPromptOk"
                text: qsTr("OK")
                highlighted: true
                onClicked: gameSettings.acceptProfileName()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: namePrompt.close()
            }
        }
    }

    Kirigami.Dialog {
        id: choicePrompt
        parent: gameSettings.contentItem
        objectName: "settingsChoicePrompt"
        title: pendingPrompt === "gsPreset"
            ? qsTr("Gamescope Preset")
            : (pendingPrompt === "mhTemplate"
                ? qsTr("Start from:")
                : qsTr("Reuse artwork from…"))
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.ComboBox {
                id: choiceBox
                objectName: "settingsChoiceBox"
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            }
            Controls.Label {
                id: choiceError
                visible: text !== ""
                color: Kirigami.Theme.negativeTextColor
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsChoiceOk"
                text: qsTr("OK")
                highlighted: true
                onClicked: gameSettings.acceptChoice()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: choicePrompt.close()
            }
        }
    }

    Kirigami.Dialog {
        id: bulkDialog
        parent: gameSettings.contentItem
        objectName: "envBulkDialog"
        title: qsTr("Bulk Edit Environment")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.TextArea {
                id: bulkArea
                objectName: "envBulkArea"
                placeholderText: qsTr("KEY=value lines (# comments and blanks skipped)")
                Layout.preferredWidth: Kirigami.Units.gridUnit * 28
                Layout.preferredHeight: Kirigami.Units.gridUnit * 12
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "bulkConfirm"
                text: qsTr("OK")
                highlighted: true
                onClicked: gameSettings.acceptBulk()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: bulkDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: presetDialog
        parent: gameSettings.contentItem
        objectName: "envPresetDialog"
        title: qsTr("Add Env Preset")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.ComboBox {
                id: presetBox
                objectName: "envPresetBox"
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "presetConfirm"
                text: qsTr("OK")
                highlighted: true
                onClicked: gameSettings.acceptEnvPreset()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: presetDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: mismatchDialog
        parent: gameSettings.contentItem
        objectName: "envMismatchDialog"
        title: qsTr("Add Env Preset")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.Label {
                id: mismatchLabel
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "mismatchConfirm"
                text: qsTr("Apply Anyway")
                highlighted: true
                onClicked: gameSettings.applyEnvPresetByName(gameSettings.pendingPreset)
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: mismatchDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: confirmDialog
        parent: gameSettings.contentItem
        objectName: "settingsConfirm"
        title: confirmPurpose === "deleteProfile" ? qsTr("Delete Profile")
            : (confirmPurpose === "resetDefaults" ? qsTr("Reset Game")
            : (confirmPurpose === "overwriteProfile" ? qsTr("Save Profile")
            : (confirmPurpose === "clearPrefix" ? qsTr("Clear Prefix")
            : (confirmPurpose === "newerApp" ? qsTr("Newer Configuration")
            : qsTr("Unsaved Changes")))))
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.Label {
                id: confirmLabel
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                id: confirmOk
                objectName: "settingsConfirmOk"
                text: qsTr("OK")
                highlighted: true
                onClicked: gameSettings.acceptConfirm()
            }
            Controls.Button {
                objectName: "settingsConfirmSave"
                visible: confirmPurpose === "discardSwitch"
                text: qsTr("Save")
                onClicked: gameSettings.acceptConfirmSave()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: confirmDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: diffDialog
        parent: gameSettings.contentItem
        objectName: "diffDialog"
        title: qsTr("Differences from Global Defaults")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.TextArea {
                id: diffText
                objectName: "diffText"
                readOnly: true
                font.family: "monospace"
                wrapMode: Text.WordWrap
                Layout.preferredWidth: Kirigami.Units.gridUnit * 32
                Layout.preferredHeight: Kirigami.Units.gridUnit * 14
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                text: qsTr("Close")
                onClicked: diffDialog.close()
            }
        }
    }
}
