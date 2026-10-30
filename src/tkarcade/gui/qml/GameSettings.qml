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
            ? qsTr("Add Game")
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
    // Friendly prefix-name picker (local Windows games).
    property var prefixChoices: []
    property string prefixHint: ""
    // The resolved prefix directory is on disk. Open/Clear… only make
    // sense then, and a local game using the default base has a prefix
    // even with an empty field.
    property bool prefixExists: false
    // Winetricks verbs: the prefix log (read-only) against the field, and
    // the `winetricks list-all` rows behind the picker.
    property var verbStatus: ({})
    property var verbCatalog: []
    property var verbFiltered: []
    property bool verbsLoading: false
    property var gfxInfo: ({})
    property string gfxStatus: ""
    property string errorText: ""
    property string pendingPrompt: "" // "saveAs" | "clone" | ""
    property var dmodeModel: [{"text": "", "data": ""}]
    property string dmodeCurrent: ""
    property string pendingArg: ""
    // Last Fetch Artwork outcome. It outranks the computed status until
    // the next action, because the background refresh lands right after
    // and would otherwise replace "Artwork Downloaded" with the disk
    // state of the moment before the download.
    property string artResult: ""
    // One width for every button in the Artwork section (and the matching
    // spacer on the rows with fewer buttons), so the fields line up in a
    // column instead of each button taking its own text width.
    readonly property real artButtonWidth: Kirigami.Units.gridUnit * 6
    // Same column for the Runtime tab's two left-hand sections (Runtime
    // and Prefix): the style floors a button at 80 px, so without this the
    // only one following its label is "Winetricks…"/"Protontricks…" (86).
    readonly property real runtimeButtonWidth: Kirigami.Units.gridUnit * 6
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
            "runtime_type": "",
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

    function openNew(runtimeType) {
        editAppid = ""
        defaultsMode = false
        fields = blankFields()
        // The Add dialog preselects the local runtime; empty leaves the
        // native default that pushToControls already applies.
        fields.runtime_type = runtimeType || ""
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

    // Read-only runtime row; tracks the Runtime combo so switching
    // clears it (Steam) or names the local Wine/umu runtime.
    function runtimeValues() {
        return (defaultsMode || (fields.is_steam || false))
            ? ["proton", "native"]
            : ["native", "wine", "umu"]
    }

    // protontricks always targets Steam's own compatdata dir: a Steam game
    // with a custom [runtime] prefix takes winetricks instead.
    function usesProtontricks() {
        return gameSettings.wineAvailable && rtPrefixField.text.trim() === ""
    }

    // Steam Linux Runtime codes in the combo's order (index 0 = disabled).
    function steamRuntimeCodes() {
        return ["", "scout", "soldier", "sniper", "steamrt4"]
    }

    function steamRuntimeValue() {
        return gameSettings.steamRuntimeCodes()[srBox.currentIndex] || ""
    }

    // Installed: where umu keeps it. Not installed: umu downloads it on the
    // first launch, so this never blocks Save or Play.
    function steamRuntimeHintText() {
        var code = gameSettings.steamRuntimeValue()
        if (code === "") {
            return ""
        }
        var state = gameModel.steamRuntimeState(code)
        return state.installed === true
            ? qsTr("%1 Is Installed: %2").arg(state.label).arg(state.path)
            : qsTr("%1 Is Not Installed: umu Downloads It On First Launch.").arg(state.label)
    }

    function runtimeText() {
        if (defaultsMode || editAppid === "") {
            return ""
        }
        if (!(fields.is_steam || false)) {
            if (runtimeTypeBox.currentIndex === 1) {
                var wine = localWineField.text.trim()
                return wine !== "" ? wine : qsTr("Wine from PATH")
            }
            if (runtimeTypeBox.currentIndex === 2) {
                var i = protonBox.currentIndex
                if (i >= 0 && i < protonChoices.length) {
                    return qsTr("UMU: %1").arg(protonChoices[i].name)
                }
                return qsTr("UMU (Choose a Proton Install)")
            }
            var sr = gameSettings.steamRuntimeValue()
            return sr === ""
                ? qsTr("Native (No Runtime)")
                : qsTr("Native · %1").arg(gameModel.steamRuntimeState(sr).label)
        }
        if (runtimeTypeBox.currentIndex === 1) {
            return qsTr("Native (No Proton)")
        }
        return gameModel.detectedRuntime(editAppid)
    }

    // Discovered Proton installs and the global Wine/prefix defaults.
    function refreshRuntime() {
        var opts = gameModel.runtimeOptions(editAppid)
        var wine = opts.wine || ""
        localWineField.placeholderText = wine !== ""
            ? qsTr("Empty = %1").arg(wine)
            : qsTr("Empty = wine from PATH")
        rtPrefixField.placeholderText = gameSettings.wineAvailable
            ? qsTr("Empty = Steam Default")
            : ((opts.default_prefix || "") !== ""
                ? qsTr("Empty = %1").arg(opts.default_prefix)
                : qsTr("Empty = the Prefix Base in Preferences"))
        protonChoices = opts.protons || []
        protonBox.model = protonChoices.map(function(p) { return p.name })
        if (!gameSettings.wineAvailable) {
            localWineField.text = fields.runtime_tool || ""
        }
        rtPrefixField.text = fields.runtime_prefix || ""
        localPrefixNameField.text = fields.runtime_prefix_name || ""
        var srIndex = gameSettings.steamRuntimeCodes().indexOf(fields.runtime_steam_runtime || "")
        srBox.currentIndex = srIndex > 0 ? srIndex : 0
        refreshPrefixHint()
        var chosen = fields.runtime_tool || ""
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
        steamRuntimeHint.text = steamRuntimeHintText()
    }

    // The dir field is the base: the prefix itself is a subfolder of it
    // named after the game (or the explicit name), so the hint reports
    // the path the launch really uses.
    function refreshPrefixHint() {
        if (editAppid === "") {
            prefixHint = ""
            prefixExists = false
            return
        }
        var state = gameModel.prefixNameState(
            editAppid, localPrefixNameField.text, rtPrefixField.text, nameField.text)
        // Steam's prefix is its compatdata dir, not <base>/<folder>:
        // the field itself decides, as before.
        prefixExists = gameSettings.wineAvailable ? rtPrefixField.text.trim() !== ""
            : state.exists === true
        var parts = []
        if (state.renamed === true) {
            parts.push(qsTr("Saved as: %1").arg(state.sanitized))
        }
        if ((state.shared || []).length > 0) {
            parts.push(qsTr("Shared with: %1").arg(state.shared.join(", ")))
        }
        parts.push(state.exists === true
            ? qsTr("Prefix: %1").arg(state.target)
            : qsTr("Created at Launch: %1").arg(state.target))
        prefixHint = parts.join(" — ")
    }

    function openPrefixChoices() {
        // The picker lists the folders under the base this game uses: the
        // per-game field wins over the Preferences base.
        prefixChoices = gameModel.prefixChoices(editAppid, rtPrefixField.text.trim())
        prefixDialog.open()
    }

    // The prefix's winetricks.log versus the verbs field: what the field
    // names and the log does not installs at the next launch.
    function refreshInstalledVerbs() {
        if (editAppid === "") {
            verbStatus = ({})
            return
        }
        verbStatus = gameModel.installedVerbs(editAppid, rtVerbs.text)
    }

    function verbStatusText() {
        var installed = verbStatus.installed || []
        var pending = verbStatus.pending || []
        var text = installed.length > 0
            ? installed.join(", ")
            : qsTr("Nothing Installed in This Prefix Yet")
        if (pending.length > 0) {
            text = qsTr("%1 — Pending at Launch: %2").arg(text).arg(pending.join(", "))
        }
        return text
    }

    function openVerbPicker() {
        verbsLoading = true
        gameModel.requestVerbCatalog()
        verbFilterField.text = ""
        filterVerbs("")
        verbDialog.open()
    }

    function filterVerbs(text) {
        var needle = String(text || "").trim().toLowerCase()
        var rows = []
        for (var i = 0; i < verbCatalog.length; i++) {
            var row = verbCatalog[i]
            if (needle === ""
                || String(row.verb || "").toLowerCase().indexOf(needle) >= 0
                || String(row.description || "").toLowerCase().indexOf(needle) >= 0
                || String(row.category || "").toLowerCase().indexOf(needle) >= 0) {
                rows.push(row)
            }
        }
        verbFiltered = rows
    }

    // The field stays the single source of truth: the picker only appends.
    function addVerb(verb) {
        var current = String(rtVerbs.text || "").trim()
        var tokens = current === "" ? [] : current.split(/\s+/)
        if (tokens.indexOf(verb) >= 0) {
            return
        }
        rtVerbs.text = current === "" ? verb : current + " " + verb
        refreshInstalledVerbs()
    }

    function openVerbTool() {
        var message = gameModel.openWinetricksGui(editAppid)
        if (message !== "") {
            settingsError.text = message
        }
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
            ? qsTr("In the Prefix: %1").arg(parts.join(", "))
            : qsTr("Nothing Installed in the Prefix Yet (Installed at Launch).")
        if (gfxDxvk.checked && !available.dxvk) {
            text += " " + qsTr("No DXVK Version Found in the Configured Directories.")
        }
        if (gfxVkd3dValue() === "proton" && !available.vkd3d) {
            text += " " + qsTr("No vkd3d-proton Version Found in the Configured Directories.")
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
        var types = runtimeValues()
        var typeIndex = types.indexOf(f.runtime_type || "")
        runtimeTypeBox.currentIndex = typeIndex >= 0
            ? typeIndex
            : ((f.is_steam || defaultsMode) ? -1 : 0)
        runtimeField.text = runtimeText()
        prefixField.text = f.custom_prefix || ""
        argsField.text = f.launch_args || ""
        cwdField.text = f.launch_cwd || ""
        catsField.text = (f.categories || []).join(", ")
        versionField.text = f.version || ""
        dateField.text = f.date || ""
        tagField.text = f.tag || ""
        artIconField.text = f.art_icon || ""
        artCoverField.text = f.art_cover || ""
        artBannerField.text = f.art_banner || ""
        artSourceField.text = f.art_source || ""
        refreshArtStatus()
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
        blockInternet.checked = !!f.block_internet
        nlDisable.checked = !!f.nl_disable
        nlProv.currentIndex = {"auto": 0, "plasma": 1, "gnome": 2, "off": 3}[f.nl_provider] ?? 0
        logField.text = editAppid !== "" ? gameModel.gameLogFile(editAppid) : ""
        ptFresh.checked = !!f.fresh_prefix
        refreshAudioSinks(f.audio_sink || "")
        refreshWineTools(f.runtime_tool || "")
        rtVerbs.text = f.winetricks_verbs || ""
        refreshInstalledVerbs()
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
            "runtime_type": runtimeValues()[runtimeTypeBox.currentIndex] || "",
            "show_menu": menuCheck.checked,
            "menu_timeout": timeoutSpin.value,
            "custom_prefix": prefixField.text,
            "launch_args": argsField.text,
            "launch_cwd": cwdField.text,
            "categories": catsField.text,
            "version": versionField.text,
            "date": dateField.text,
            "tag": tagField.text,
            "art_icon": artIconField.text,
            "art_cover": artCoverField.text,
            "art_banner": artBannerField.text,
            "art_source": artSourceField.text,
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
            "block_internet": blockInternet.checked,
            "nl_disable": nlDisable.checked,
            "nl_provider": ["auto", "plasma", "gnome", "off"][nlProv.currentIndex] || "auto",
            "fresh_prefix": ptFresh.checked,
            "audio_sink": audioSinkData(),
            "winetricks_verbs": rtVerbs.text,
            "proton_log": ptLog.checked,
            "winedebug": ["", "-all", "+err", "+warn,+err"][ptDebug.currentIndex] || "",
            // One prefix key and one tool key; the origin decides how the
            // launcher reads them (Steam compatdata/compat tool vs full
            // WINEPREFIX/wine binary/PROTONPATH).
            "runtime_prefix": rtPrefixField.text,
            "runtime_prefix_name": localPrefixNameField.text,
            "runtime_tool": gameSettings.wineAvailable
                ? wineToolData()
                : (runtimeTypeBox.currentIndex === 2 ? protonChoicePath() : localWineField.text),
            "runtime_steam_runtime": gameSettings.wineAvailable
                ? ""
                : (runtimeTypeBox.currentIndex === 0 ? gameSettings.steamRuntimeValue() : ""),
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
            setupConfirm("discardSwitch", qsTr("Unsaved Changes"),
                qsTr("You Have Unsaved Changes. Save Them Before Switching to Profile '%1'?").arg(name),
                qsTr("Discard"))
            confirmDialog.softIcon = true
            confirmDialog.detail = qsTr("(The Saved Profile Is Kept.)")
            confirmDialog.saveVisible = true
            confirmDialog.open(gameSettings)
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
            settingsError.text = qsTr("Profile '%1' Could Not Be Read.").arg(name)
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
                promptError.text = qsTr("Could Not Save the Profile.")
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
                settingsError.text = qsTr("Could Not Reset the Game.")
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
        } else if (confirmPurpose === "clearArtwork") {
            confirmDialog.close()
            clearFetchedArtwork()
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
        setupConfirm("newerApp", qsTr("Newer Configuration"),
            qsTr("%1 Saving Now Will Downgrade It and May Lose Settings. Continue?")
                .arg(qsTr("This Configuration Was Written by a Newer TKArcade.")),
            qsTr("OK"))
        confirmDialog.open(gameSettings)
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
            ? qsTr("Unsaved Changes to Profile '%1' Will Be Discarded (the Saved Profile Is Kept).").arg(dialogProfile)
            : (isDirty() ? qsTr("Unsaved Changes Will Be Discarded.")
                : qsTr("This Overwrites the Saved Game Config."))
        setupConfirm("resetDefaults", qsTr("Reset Game"),
            qsTr("Reset This Game to the Global Defaults Template Now?"),
            qsTr("Reset"))
        confirmDialog.detail = detail
        confirmDialog.open(gameSettings)
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
            mismatchLabel.text = qsTr("Preset '%1' Is for %2.\nApply Anyway?").arg(name).arg(mismatch)
            mismatchDialog.open()
            return
        }
        applyEnvPresetByName(name)
    }

    function applyEnvPresetByName(name) {
        var res = gameModel.applyEnvPreset(collectEnv(), name)
        setEnvRows(res.rows || [])
        if ((res.added || 0) === 0) {
            settingsError.text = qsTr("Preset '%1': All Keys Already Present.").arg(name)
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
        var items = [{"text": qsTr("(Steam Default)"), "data": ""}]
        var idx = 0
        for (var i = 0; i < tools.length; i++) {
            var label = tools[i][1] !== "" ? tools[i][0] + " (" + tools[i][1] + ")" : tools[i][0]
            items.push({"text": label, "data": tools[i][0]})
            if (tools[i][0] === select) {
                idx = i + 1
            }
        }
        if (select !== "" && idx === 0) {
            items.push({"text": qsTr("%1 (Not Installed)").arg(select), "data": select})
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
        var items = [{"text": qsTr("(System Default)"), "data": ""}]
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
            items.push({"text": qsTr("%1 (Unavailable)").arg(select), "data": select})
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
            refreshArtStatus()
        }
    }

    // Where the three images come from right now (token from the model),
    // and which provider produced them, so a typed Artwork Source AppID
    // stops looking like a no-op.
    function refreshArtStatus() {
        var draft = artSourceField.text
        var token = editAppid === "" ? "none" : gameModel.artworkStatus(editAppid, draft)
        var provider = editAppid === "" ? "" : gameModel.artworkProvider(editAppid, draft)
        var name = editAppid === "" ? "" : gameModel.artworkSourceName(editAppid, draft)
        var source = name !== ""
            ? qsTr("AppID %1 (%2)").arg(artSourceField.text).arg(name)
            : qsTr("AppID %1").arg(artSourceField.text)
        var messages = {
            "own": qsTr("Using This Game's Own Artwork."),
            "donor": qsTr("Using Artwork From %1.").arg(source),
            "mixed": qsTr("Some Artwork Comes From %1.").arg(source),
            "partial": qsTr("Some Images Are Missing. Use Fetch Artwork to Download Them."),
            "none": qsTr("No Artwork Yet. Save the Game and Use Fetch Artwork.")
        }
        if (artResult !== "") {
            artStatusLabel.text = artResult
            return
        }
        artStatusLabel.text = (messages[token] || "") + providerSuffix(provider)
    }

    function providerSuffix(provider) {
        var providers = {
            "steam": qsTr(" (Official Steam Artwork)"),
            "sgdb": qsTr(" (SteamGridDB Artwork)")
        }
        return providers[provider] || ""
    }

    // Clear… confirms first: the cached art belongs to the source AppID,
    // so other games pointing there lose it too.
    function requestClearFetched() {
        setupConfirm("clearArtwork", qsTr("Remove Downloaded Artwork"),
            qsTr("Remove the Downloaded Artwork of AppID %1? Any Other Game Using That AppID Falls Back to Steam's Own Art.").arg(artSourceField.text.trim()),
            qsTr("Remove"))
        confirmDialog.open(gameSettings)
    }

    function clearFetchedArtwork() {
        var err = gameModel.clearFetchedArtwork(editAppid, artSourceField.text)
        var messages = {
            "done": qsTr("Downloaded Artwork Removed."),
            "no-game": qsTr("Save the Game First."),
            "no-appid": qsTr("There Is No Downloaded Artwork to Remove.")
        }
        artResult = messages[err] || qsTr("There Is No Downloaded Artwork to Remove.")
        refreshArtStatus()
    }

    function fetchArtwork() {
        artResult = ""
        var err = gameModel.fetchArtwork(editAppid, artSourceField.text)
        var messages = {
            "": qsTr("Fetching Artwork…"),
            "no-game": qsTr("Save the Game First."),
            "no-appid": qsTr("Enter a Steam AppID in Artwork Source AppID First.")
        }
        artStatusLabel.text = messages[err] || err
    }

    // Outcome of the worker thread behind Fetch Artwork.
    function showFetchResult(status, provider) {
        var messages = {
            "ok": qsTr("Artwork Downloaded."),
            "not-a-steam-app": qsTr("That Number Is Not a Steam AppID (a SteamGridDB Page ID Looks Similar)."),
            "not-found": qsTr("SteamGridDB Has No Artwork for That AppID."),
            "blocked": qsTr("SteamGridDB Refused the Request (403). Try Again Later."),
            "network": qsTr("Could Not Reach the Artwork Servers."),
            "no-art": qsTr("No Artwork Found for That AppID.")
        }
        var text = messages[status] || qsTr("No Artwork Found for That AppID.")
        if (status === "ok") {
            text += providerSuffix(provider)
        }
        artResult = text
        refreshArtStatus()
    }

    function askChoice(purpose, items, arg) {
        pendingPrompt = purpose
        pendingArg = arg || ""
        choiceError.text = ""
        // Every row carries its label and value, so the ComboBox can show
        // the label (textRole) and acceptChoice can read the value. A bare
        // list of strings used to be fine; a list of objects without a
        // text role rendered as blank rows.
        var rows = []
        for (var i = 0; i < items.length; i++) {
            var item = items[i]
            if (item !== null && typeof item === "object") {
                rows.push({"text": String(item.text), "data": item.data})
            } else {
                rows.push({"text": String(item), "data": item})
            }
        }
        choiceBox.model = rows
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
                choiceError.text = qsTr("Could Not Create the Config File.")
                return
            }
            choicePrompt.close()
            refreshMangohudConfigs(path.split("/").pop())
            if (!gameModel.openPath(path) && page !== null) {
                page.notify(qsTr("Could Not Open the Config File."))
            }
        } else if (pendingPrompt === "artSource") {
            var pick = choiceBox.model[choiceBox.currentIndex]
            if (pick !== undefined && pick.data !== "") {
                artSourceField.text = pick.data
                refreshArtStatus()
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
            ? qsTr("No Wrappers Enabled")
            : qsTr("Will Launch with: %1").arg(w)
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
            return qsTr("%1 — %2 (Off)").arg(args[0]).arg(args[1])
        case "binary-missing":
            return qsTr("%1 Not Found in PATH — Skipped at Launch").arg(args[0])
        case "binary-missing-fatal":
            return qsTr("%1 Not Found in PATH — Launch Will Fail").arg(args[0])
        case "binary-absent":
            return qsTr("%1 Not Installed (Feature Off)").arg(args[0])
        case "prefix-none":
            return qsTr("No Custom Prefix — Game Launches Directly")
        case "hook-ok":
            return qsTr("%1: %2").arg(args[0]).arg(args[1])
        case "hook-missing":
            return qsTr("%1 Not Found: %2").arg(args[0]).arg(args[1])
        case "ludusavi-flatpak":
            return qsTr("Ludusavi via Flatpak (%1) — May Not See Proton Prefixes").arg(args[0])
        case "steam-ok":
            return qsTr("Steam Launch Options: %1").arg(args[0])
        case "steam-stale":
            return qsTr("Steam Runs %1 (%2) — This GUI Is %3").arg(args[0]).arg(args[1]).arg(args[2])
        case "steam-no-binary":
            return qsTr("Steam Launch Options Use tkarcade, Which Is Not in PATH")
        case "steam-missing":
            return qsTr("Steam Launch Options Lack tkarcade (Add: tkarcade %command%)")
        case "steam-unknown":
            return qsTr("Steam Userdata Not Found")
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
            body += " (<a href=\"" + row.link + "\">" + qsTr("Open Folder") + "</a>)"
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
        if (!defaultsMode && (fields.is_steam || false) && runtimeTypeBox.currentIndex < 0) {
            settingsError.text = qsTr("Choose the Runtime: Proton or Native (Steam Runtime).")
            return false
        }
        if (!gameModel.metadataDateValid(dateField.text)) {
            settingsError.text = qsTr("Release Date Must Be YYYY-MM-DD, YYYY-MM or YYYY.")
            return false
        }
        if (defaultsMode) {
            if (!gameModel.saveDefaults(collect())) {
                settingsError.text = qsTr("Could Not Save the Defaults.")
                return false
            }
            newerVersion = false
            return true
        }
        var created = gameModel.saveGame(editAppid, collect())
        if (created === "") {
            settingsError.text = editAppid === ""
                ? qsTr("Name and a Valid Executable Are Required.")
                : qsTr("Could Not Save the Game.")
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
            promptError.text = qsTr("Give the Profile a Name.")
            return
        }
        if (pendingPrompt === "mhName") {
            namePrompt.close()
            gameSettings.askChoice("mhTemplate", [
                qsTr("Copy of MangoHud.conf"),
                qsTr("Minimal Overlay"),
                qsTr("FPS Limiter Overlay"),
                qsTr("Full Metrics Overlay"),
                qsTr("Empty File")
            ], name)
            return
        }
        var ok = false
        if (pendingPrompt === "saveAs") {
            if (gameModel.profileExists(editAppid, name) && pendingName !== name) {
                pendingName = name
                setupConfirm("overwriteProfile", qsTr("Save Profile"),
                    qsTr("Overwrite Profile '%1'?").arg(name),
                    qsTr("Overwrite"))
                confirmDialog.softIcon = true
                confirmDialog.open(gameSettings)
                return
            }
            pendingName = ""
            if (!gameModel.saveGameProfile(editAppid, name, collect())) {
                promptError.text = qsTr("Could Not Save the Profile.")
                return
            }
            namePrompt.close()
            afterProfileSaved(name)
            return
        } else if (pendingPrompt === "clone") {
            var profiles = profileBox.model || []
            var src = profiles[profileBox.currentIndex] || ""
            if (src === "") {
                promptError.text = qsTr("Select a Profile First.")
                return
            }
            if (src === name) {
                promptError.text = qsTr("Source and Target Are the Same.")
                return
            }
            if (gameModel.profileExists(editAppid, name)) {
                promptError.text = qsTr("A Profile with This Name Already Exists.")
                return
            }
            ok = gameModel.cloneGameProfile(editAppid, src, name, collect())
        }
        if (!ok) {
            promptError.text = qsTr("Could Not Save the Profile.")
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
        // A background fetch landed: the cache behind the rows changed
        // under the open dialog.
        function onRefreshed() {
            if (editAppid !== "") {
                refreshArtStatus()
            }
        }
        function onArtworkFetched(appid, status, provider) {
            if (appid === editAppid) {
                showFetchResult(status, provider)
            }
        }
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
        // The verb list arrives from a worker on the first open (the
        // parser pays `winetricks list-all`); later opens are cached.
        function onVerbCatalogReady(rows) {
            var out = []
            for (var i = 0; i < rows.length; i++) {
                out.push({
                    "verb": rows[i].verb || "",
                    "description": rows[i].description || "",
                    "category": rows[i].category || ""
                })
            }
            gameSettings.verbCatalog = out
            gameSettings.verbsLoading = false
            gameSettings.filterVerbs(verbFilterField.text)
        }
        // The interactive tool exited: it may have written to the log, and
        // a non-zero exit leaves its output in the per-game log.
        function onVerbToolClosed(status, detail) {
            gameSettings.refreshInstalledVerbs()
            if (status === "failed") {
                settingsError.text = qsTr("The Tool Exited Unexpectedly — See %1").arg(detail)
            }
        }
    }

    Connections {
        target: gameModel
        function onCoverageFinished(status, detail) {
            var messages = {
                "covered": qsTr("Ludusavi Covers This Game.\n%1").arg(detail),
                "no-local-saves": qsTr("Manifest Entry Exists, but No Saves Found.\n%1").arg(detail),
                "no-entry": qsTr("No Manifest Entry for This Game.\nAdd a Custom Game Entry in Ludusavi to Enable Backups."),
                "unavailable": qsTr("Could Not Check Coverage:\n%1").arg(detail)
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
                text: qsTr("Commands")
            }
            Controls.TabButton {
                text: qsTr("Runtime")
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
                        // One label column for the tab, so the fields of every
                        // section start at the same x.
                        property real labelWidth: Math.max(generalForm.naturalLabelWidth,
                                                           profileForm.naturalLabelWidth,
                                                           launchForm.naturalLabelWidth)
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Game")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                labelWidth: generalColumn.labelWidth
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
                                    placeholderText: qsTr("Game Name")
                                    Layout.fillWidth: true
                                    onEditingFinished: gameSettings.refreshPrefixHint()
                                    KirigamiLayouts.FormData.label: qsTr("Game Name:")
                                }
                                Controls.TextField {
                                    id: catsField
                                    objectName: "settingsCats"
                                    placeholderText: qsTr("Action, Retro (Comma-Separated)")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Categories:")
                                }
                                // Optional identity extras, rendered as
                                // name suffixes in the library; the saved
                                // name never carries them.
                                Controls.TextField {
                                    id: versionField
                                    objectName: "settingsVersion"
                                    visible: !defaultsMode
                                    placeholderText: qsTr("Shown as Name [Version]")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Version:")
                                }
                                Controls.TextField {
                                    id: dateField
                                    objectName: "settingsDate"
                                    visible: !defaultsMode
                                    placeholderText: qsTr("YYYY-MM-DD, YYYY-MM or YYYY")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Release Date:")
                                }
                                Controls.TextField {
                                    id: tagField
                                    objectName: "settingsTag"
                                    visible: !defaultsMode
                                    placeholderText: qsTr("Shown as Name (TAG)")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("State Tag:")
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Profile")
                            Layout.fillWidth: true
                            visible: editAppid !== ""
                            WidgetsFormLayout {
                                id: profileForm
                                labelWidth: generalColumn.labelWidth
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
                                            setupConfirm("deleteProfile", qsTr("Delete Profile"),
                                                qsTr("Delete Profile '%1'? This Cannot Be Undone.").arg(name),
                                                qsTr("Delete"))
                                            confirmDialog.open(gameSettings)
                                        }
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Launch")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: launchForm
                                labelWidth: generalColumn.labelWidth
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    // Local games keep their only executable
                                    // here; Steam games use it to launch an
                                    // alternate one.
                                    KirigamiLayouts.FormData.label: (fields.is_steam || false)
                                        ? qsTr("Custom Executable (Override):")
                                        : qsTr("Game Executable:")
                                    Controls.TextField {
                                        id: exeField
                                        objectName: "settingsExe"
                                        placeholderText: qsTr("Game Executable")
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
                                            } else if (gameSettings.pendingBrowse === "runtimePrefix") {
                                                rtPrefixField.text = picked
                                                gameSettings.refreshPrefixHint()
                                            } else if (gameSettings.pendingBrowse === "localWine") {
                                                localWineField.text = picked
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
                                // A Windows executable saved as Linux
                                // (native) fails at launch: hint at it
                                // without blocking the save, and offer the
                                // type switch that makes the launch work.
                                RowLayout {
                                    objectName: "settingsExeHint"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: ""
                                    visible: !defaultsMode && runtimeTypeBox.currentIndex >= 0
                                        && runtimeValues()[runtimeTypeBox.currentIndex] === "native"
                                        && /\.(exe|bat|msi)$/i.test(exeField.text.trim())
                                    Controls.Label {
                                        Layout.fillWidth: true
                                        // A wrapped sentence reports its whole
                                        // line as implicit width, and this row
                                        // counts toward the form's natural width
                                        // even while hidden: the Launch tab used
                                        // to be the one that overflowed. The
                                        // label takes whatever fillWidth gives.
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        text: qsTr("This Looks Like a Windows Executable, but the Runtime Is a Linux Build.")
                                    }
                                    Controls.Button {
                                        objectName: "settingsSwitchType"
                                        text: (fields.is_steam || false)
                                            ? qsTr("Switch to Proton")
                                            : qsTr("Switch to Wine")
                                        onClicked: {
                                            var types = runtimeValues()
                                            var index = types.indexOf(
                                                (fields.is_steam || false) ? "proton" : "wine")
                                            if (index >= 0) {
                                                runtimeTypeBox.currentIndex = index
                                                runtimeField.text = gameSettings.runtimeText()
                                                gfxStatus = gameSettings.gfxStatusText()
                                            }
                                        }
                                    }
                                }
                                Controls.TextField {
                                    id: prefixField
                                    objectName: "settingsPrefix"
                                    placeholderText: qsTr("e.g. zink-run")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Custom Command Prefix:")
                                }
                                Controls.TextField {
                                    id: argsField
                                    objectName: "settingsArgs"
                                    placeholderText: qsTr("e.g. --fullscreen -v")
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Extra Launch Args:")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Working Directory:")
                                    Controls.TextField {
                                        id: cwdField
                                        objectName: "settingsCwd"
                                        placeholderText: qsTr("Empty = Game Folder")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "settingsCwdBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "launchCwd"
                                            gameModel.pickDir(qsTr("Working Directory"), qsTr("Select"))
                                        }
                                    }
                                }
                                Controls.CheckBox {
                                    id: menuCheck
                                    objectName: "settingsMenu"
                                    text: qsTr("Show Menu Before Launch")
                                }
                                Controls.SpinBox {
                                    id: timeoutSpin
                                    objectName: "settingsTimeout"
                                    from: 0
                                    to: 600
                                    KirigamiLayouts.FormData.label: qsTr("Menu Timeout (Seconds):")
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
                                                settingsError.text = qsTr("Could Not Open the Log File.")
                                            }
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
                            KirigamiLayouts.FormData.label: qsTr("Pre-Launch Command:")
                        }
                        Controls.TextField {
                            id: ppPreArgs
                            objectName: "ppPreArgs"
                            Layout.fillWidth: true
                            KirigamiLayouts.FormData.label: qsTr("Pre-Launch Arguments:")
                        }
                        Controls.TextField {
                            id: ppPost
                            objectName: "ppPost"
                            Layout.fillWidth: true
                            KirigamiLayouts.FormData.label: qsTr("Post-Exit Command:")
                        }
                        Controls.TextField {
                            id: ppPostArgs
                            objectName: "ppPostArgs"
                            Layout.fillWidth: true
                            KirigamiLayouts.FormData.label: qsTr("Post-Exit Arguments:")
                        }
                        Controls.SpinBox {
                            id: ppTimeout
                            objectName: "ppTimeout"
                            from: 1
                            to: 3600
                            KirigamiLayouts.FormData.label: qsTr("Timeout (Seconds):")
                        }
                        Controls.CheckBox {
                            id: ppShell
                            objectName: "ppShell"
                            text: qsTr("Run in Shell (bash -c)")
                        }
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
                        // One label column for the tab, so the fields of
                        // every section start at the same x.
                        property real labelWidth: Math.max(runtimeForm.naturalLabelWidth,
                                                           prefixForm.naturalLabelWidth,
                                                           graphicsForm.naturalLabelWidth,
                                                           debugForm.naturalLabelWidth)
                        SectionBox {
                            title: qsTr("Runtime")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: runtimeForm
                                labelWidth: compatColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.ComboBox {
                                    id: runtimeTypeBox
                                    objectName: "settingsRuntimeType"
                                    Layout.fillWidth: true
                                    // The origin decides the choices: Steam
                                    // games use the Steam Proton runtime, local
                                    // games their own Wine or umu-run Proton.
                                    model: (defaultsMode || (fields.is_steam || false))
                                        ? [qsTr("Proton"), qsTr("Native (Steam Runtime)")]
                                        : [
                                            qsTr("Native"),
                                            qsTr("Wine"),
                                            qsTr("UMU")
                                        ]
                                    displayText: currentIndex >= 0 ? currentText : qsTr("Choose...")
                                    KirigamiLayouts.FormData.label: qsTr("Runtime:")
                                    onActivated: {
                                        runtimeField.text = gameSettings.runtimeText()
                                        gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                Controls.TextField {
                                    id: runtimeField
                                    objectName: "settingsRuntime"
                                    visible: !defaultsMode && editAppid !== ""
                                        && runtimeTypeBox.currentIndex >= 0
                                    readOnly: true
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Detected Runtime:")
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: !gameSettings.wineAvailable && runtimeTypeBox.currentIndex === 1
                                    KirigamiLayouts.FormData.label: qsTr("Wine Binary:")
                                    Controls.TextField {
                                        id: localWineField
                                        objectName: "settingsLocalWine"
                                        Layout.fillWidth: true
                                        onTextChanged: runtimeField.text = gameSettings.runtimeText()
                                    }
                                    Controls.Button {
                                        objectName: "settingsLocalWineBrowse"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "localWine"
                                            gameModel.pickPath(qsTr("Wine Binary"), qsTr("Select"))
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: !gameSettings.wineAvailable && runtimeTypeBox.currentIndex === 2
                                    KirigamiLayouts.FormData.label: qsTr("Proton:")
                                    Controls.ComboBox {
                                        id: protonBox
                                        objectName: "settingsLocalProton"
                                        Layout.fillWidth: true
                                        displayText: count > 0 ? currentText : qsTr("No Proton Install Found")
                                        onActivated: runtimeField.text = gameSettings.runtimeText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: gameSettings.wineAvailable
                                    KirigamiLayouts.FormData.label: qsTr("Compat Tool:")
                                    Controls.ComboBox {
                                        id: wineToolBox
                                        objectName: "wineTool"
                                        textRole: "text"
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "wineToolApply"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
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
                                RowLayout {
                                    Layout.fillWidth: true
                                    // A local Linux build can run inside a
                                    // Steam Linux Runtime; a Steam game gets
                                    // its runtime from Steam instead.
                                    visible: !defaultsMode && !(fields.is_steam || false)
                                        && runtimeTypeBox.currentIndex === 0
                                    KirigamiLayouts.FormData.label: qsTr("Steam Runtime:")
                                    Controls.ComboBox {
                                        id: srBox
                                        objectName: "settingsSteamRuntime"
                                        Layout.fillWidth: true
                                        model: [
                                            qsTr("Disabled"),
                                            qsTr("Steam Linux Runtime 1.0 (scout)"),
                                            qsTr("Steam Linux Runtime 2.0 (soldier)"),
                                            qsTr("Steam Linux Runtime 3.0 (sniper)"),
                                            qsTr("Steam Linux Runtime 4.0 (steamrt4)")
                                        ]
                                        // currentIndex, not activated: the
                                        // row and the hint follow a restored
                                        // value too, not only a click.
                                        onCurrentIndexChanged: {
                                            runtimeField.text = gameSettings.runtimeText()
                                            steamRuntimeHint.text = gameSettings.steamRuntimeHintText()
                                        }
                                    }
                                }
                                // A wrapped hint belongs in a row that can
                                // shrink: as a bare form item it takes the
                                // whole form width and the tab clips it at
                                // the minimum window width.
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: !defaultsMode && !(fields.is_steam || false)
                                        && runtimeTypeBox.currentIndex === 0 && steamRuntimeHint.text !== ""
                                    Controls.Label {
                                        objectName: "steamRuntimeHint"
                                        id: steamRuntimeHint
                                        // Only when umu does not have the
                                        // runtime yet: it downloads it on
                                        // first launch.
                                        visible: text !== ""
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        color: Kirigami.Theme.disabledTextColor
                                    }
                                }
                                // Same shrinkable row as the hint above.
                                RowLayout {
                                    Layout.fillWidth: true
                                    // Native needs no tool: the sentence
                                    // only makes sense for Wine/umu.
                                    visible: !gameSettings.wineAvailable && runtimeTypeBox.currentIndex >= 1
                                    Controls.Label {
                                        objectName: "localRuntimeHint"
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        text: qsTr("Local Windows Games Run Through Wine or Proton (umu-run). Nothing Is Downloaded: Pick an Installed Tool.")
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Prefix")
                            Layout.fillWidth: true
                            // Steam always has a compatdata dir; local games
                            // only once a Wine/umu runtime is chosen.
                            visible: gameSettings.wineAvailable || runtimeTypeBox.currentIndex >= 1
                            WidgetsFormLayout {
                                id: prefixForm
                                labelWidth: compatColumn.labelWidth
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    // One row for the whole prefix: Steam's
                                    // compatdata dir (STEAM_COMPAT_DATA_PATH)
                                    // or, for a local game, the base and the
                                    // folder inside it. It reads as the
                                    // <base>/<folder> path the launch uses.
                                    visible: gameSettings.wineAvailable || runtimeTypeBox.currentIndex >= 1
                                    KirigamiLayouts.FormData.label: gameSettings.wineAvailable
                                        ? qsTr("Custom Prefix Dir:")
                                        : qsTr("Wine Prefix:")
                                    Kirigami.ActionTextField {
                                        id: rtPrefixField
                                        objectName: "winePrefix"
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: Kirigami.Units.gridUnit * 4
                                        placeholderText: gameSettings.wineAvailable
                                            ? qsTr("Empty = Steam Default")
                                            : qsTr("Empty = the Prefix Base in Preferences")
                                        onEditingFinished: gameSettings.refreshPrefixHint()
                                        // The pickers sit inside the fields
                                        // they fill: two text buttons plus
                                        // Clear/Open do not fit one row at
                                        // the minimum window width.
                                        rightActions: [
                                            Kirigami.Action {
                                                objectName: "winePrefixBaseBrowse"
                                                // A Steam compatdata dir is picked
                                                // by the text button below.
                                                visible: !gameSettings.wineAvailable
                                                text: qsTr("Choose the Prefix Base…")
                                                icon.name: "document-open-folder"
                                                onTriggered: {
                                                    gameSettings.pendingBrowse = "runtimePrefix"
                                                    gameModel.pickDir(qsTr("Prefix Base"), qsTr("Select"))
                                                }
                                            }
                                        ]
                                        // The field scrolls a value longer than
                                        // itself from the left, with no
                                        // ellipsis (QQC2), so the tooltip
                                        // carries the whole text.
                                        Controls.ToolTip.text: (gameSettings.wineAvailable
                                            ? qsTr("Steam's Compatdata Directory (STEAM_COMPAT_DATA_PATH).")
                                            : qsTr("Base Directory: the Prefix Itself Is a Subfolder Named After the Game."))
                                            + (text !== "" ? "\n" + text : "")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Label {
                                        objectName: "prefixBaseSuffix"
                                        visible: !gameSettings.wineAvailable
                                        Layout.alignment: Qt.AlignVCenter
                                        text: qsTr("(Base)")
                                        opacity: 0.7
                                    }
                                    Controls.Label {
                                        visible: !gameSettings.wineAvailable
                                        Layout.alignment: Qt.AlignVCenter
                                        text: "/"
                                        opacity: 0.5
                                    }
                                    Kirigami.ActionTextField {
                                        id: localPrefixNameField
                                        objectName: "settingsLocalPrefixName"
                                        visible: !gameSettings.wineAvailable
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: Kirigami.Units.gridUnit * 3
                                        placeholderText: qsTr("Empty = the Game Name (Normalized)")
                                        onTextChanged: gameSettings.refreshPrefixHint()
                                        rightActions: [
                                            Kirigami.Action {
                                                objectName: "winePrefixFolderChoose"
                                                text: qsTr("Choose an Existing Prefix…")
                                                icon.name: "view-list-details"
                                                onTriggered: gameSettings.openPrefixChoices()
                                            }
                                        ]
                                        Controls.ToolTip.text: qsTr("Folder Name Under the Base, Normalized from the Game Name When Empty.")
                                            + (text !== "" ? "\n" + text : "")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Label {
                                        objectName: "prefixFolderSuffix"
                                        visible: !gameSettings.wineAvailable
                                        Layout.alignment: Qt.AlignVCenter
                                        text: qsTr("(Folder)")
                                        opacity: 0.7
                                    }
                                    // Steam keeps its text buttons; for a
                                    // local game the two pickers are the
                                    // inline actions above.
                                    Controls.Button {
                                        objectName: "winePrefixBrowse"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        visible: gameSettings.wineAvailable
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            gameSettings.pendingBrowse = "runtimePrefix"
                                            gameModel.pickDir(qsTr("Prefix Dir"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixCreate"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        visible: gameSettings.wineAvailable
                                        text: qsTr("Create")
                                        onClicked: {
                                            var msg = gameModel.ensurePrefix(editAppid)
                                            if (msg !== "") {
                                                settingsError.text = msg
                                            }
                                        }
                                    }
                                }
                                // The resolved prefix and the actions on it.
                                // The wrapped hint reports its whole line as
                                // implicit width; inside a bare form item it
                                // widens the grid past the frame (and the
                                // buttons past the window), so it sits in a
                                // row that can shrink.
                                RowLayout {
                                    Layout.fillWidth: true
                                    visible: gameSettings.wineAvailable || runtimeTypeBox.currentIndex >= 1
                                    Controls.Label {
                                        objectName: "settingsLocalPrefixHint"
                                        // Kept in the layout even when empty
                                        // (Steam has no hint): the fillWidth
                                        // is what keeps the buttons right.
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        opacity: 0.7
                                        // Steam's prefix is the compatdata
                                        // dir itself; the <base>/<folder>
                                        // resolution is a local-game rule.
                                        text: gameSettings.wineAvailable ? "" : gameSettings.prefixHint
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixClear"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        // A local game with a prefix on disk
                                        // has a WINEPREFIX to delete, even
                                        // when it lives under the default
                                        // base (empty field).
                                        visible: gameSettings.wineAvailable
                                            || gameSettings.prefixExists
                                        text: qsTr("Clear…")
                                        onClicked: {
                                            var target = gameModel.prefixDir(editAppid)
                                            if (target === "") {
                                                return
                                            }
                                            setupConfirm("clearPrefix", qsTr("Clear Prefix"),
                                                qsTr("Delete the Prefix Now?"),
                                                qsTr("Delete"))
                                            confirmDialog.detail = target
                                            confirmDialog.warning = qsTr("Saves Inside Are Lost.")
                                            confirmDialog.open(gameSettings)
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "winePrefixOpen"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        visible: gameSettings.wineAvailable
                                            || gameSettings.prefixExists
                                        text: qsTr("Open")
                                        onClicked: {
                                            if (!gameModel.openPath(gameModel.prefixDir(editAppid))) {
                                                settingsError.text = qsTr("Could Not Open the Prefix Folder.")
                                            }
                                        }
                                    }
                                }
                                Controls.CheckBox {
                                    id: ptFresh
                                    objectName: "ptFresh"
                                    visible: gameSettings.wineAvailable
                                    text: qsTr("Delete Prefix Before Launch (Fresh Start)")
                                    Controls.ToolTip.text: qsTr("Deletes the Compatdata Prefix So Steam Recreates It. WIPES Saves Inside the Prefix — Rely on Cloud or Ludusavi Backups!")
                                    Controls.ToolTip.visible: hovered
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Winetricks Verbs:")
                                    Controls.TextField {
                                        id: rtVerbs
                                        objectName: "ptVerbs"
                                        placeholderText: qsTr("dotnet48 vcrun2022 (Space-Separated)")
                                        Layout.fillWidth: true
                                        onEditingFinished: gameSettings.refreshInstalledVerbs()
                                        Controls.ToolTip.text: gameSettings.usesProtontricks()
                                            ? qsTr("Winetricks Verbs Installed via protontricks Before Launch.")
                                            : qsTr("Installed with winetricks into This Prefix Before Launch; the Prefix Must Already Exist.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "ptVerbsAdd"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        text: qsTr("Add…")
                                        onClicked: gameSettings.openVerbPicker()
                                        Controls.ToolTip.text: qsTr("Search the Verb List and Append One to the Field.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    // The prefix's own winetricks.log: the
                                    // field only acts at the next launch, so
                                    // the two lists are shown apart.
                                    visible: editAppid !== ""
                                    KirigamiLayouts.FormData.label: qsTr("In the Prefix:")
                                    Controls.Label {
                                        objectName: "ptVerbsInstalled"
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        text: gameSettings.verbStatusText()
                                    }
                                    Controls.Button {
                                        objectName: "ptVerbsGui"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        // protontricks targets the game's
                                        // own compatdata dir; a custom prefix
                                        // takes winetricks against its pfx.
                                        text: gameSettings.usesProtontricks()
                                            ? qsTr("Protontricks…")
                                            : qsTr("Winetricks…")
                                        onClicked: gameSettings.openVerbTool()
                                        Controls.ToolTip.text: gameSettings.usesProtontricks()
                                            ? qsTr("Open protontricks for This Game in Its Own Window.")
                                            : qsTr("Open winetricks Against This Prefix in Its Own Window.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Graphics")
                            Layout.fillWidth: true
                            // Only a plain Wine prefix takes the layers: umu
                            // and Proton ship their own DXVK/vkd3d.
                            visible: !gameSettings.wineAvailable && runtimeTypeBox.currentIndex === 1
                            WidgetsFormLayout {
                                id: graphicsForm
                                labelWidth: compatColumn.labelWidth
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("DXVK:")
                                    Controls.CheckBox {
                                        id: gfxDxvk
                                        objectName: "settingsGraphicsDxvk"
                                        text: qsTr("D3D9/10/11 Through DXVK")
                                        onCheckedChanged: gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("D3D12 Layer:")
                                    Controls.ComboBox {
                                        id: gfxVkd3d
                                        objectName: "settingsGraphicsVkd3d"
                                        Layout.fillWidth: true
                                        model: [
                                            qsTr("Off (Wine Builtin)"),
                                            qsTr("vkd3d-proton"),
                                            qsTr("vkd3d (Wine Builtin, Lower Compatibility)")
                                        ]
                                        onActivated: gfxStatus = gameSettings.gfxStatusText()
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    Controls.Label {
                                        objectName: "settingsGfxStatus"
                                        Layout.fillWidth: true
                                        // A wrapped sentence reports its
                                        // whole line as implicit width; left
                                        // alone it pushes the Remove button
                                        // past the frame edge.
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                        text: gameSettings.gfxStatus
                                    }
                                    Controls.Button {
                                        objectName: "settingsGfxRemove"
                                        text: qsTr("Remove from Prefix")
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
                            title: qsTr("Debug")
                            Layout.fillWidth: true
                            visible: gameSettings.wineAvailable
                            WidgetsFormLayout {
                                id: debugForm
                                labelWidth: compatColumn.labelWidth
                                Layout.fillWidth: true
                                RowLayout {
                                    visible: editAppid !== ""
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: ptLog
                                        objectName: "ptLog"
                                        text: qsTr("Capture Proton Log (Disk-Heavy)")
                                        Controls.ToolTip.text: qsTr("Sets PROTON_LOG=1 with a per-game Log Dir (Proton Only).")
                                        Controls.ToolTip.visible: hovered
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "ptLogOpen"
                                        Layout.preferredWidth: gameSettings.runtimeButtonWidth
                                        Layout.minimumWidth: gameSettings.runtimeButtonWidth
                                        text: qsTr("Open")
                                        onClicked: {
                                            if (!gameModel.openPath(ptLogDir)) {
                                                settingsError.text = qsTr("Could Not Open the Proton Log Folder.")
                                            }
                                        }
                                    }
                                }
                                Controls.ComboBox {
                                    id: ptDebug
                                    objectName: "ptDebug"
                                    Layout.fillWidth: true
                                    model: [qsTr("Off"), qsTr("Quiet (-all)"), qsTr("Errors (+err)"), qsTr("Warnings (+warn,+err)")]
                                    Controls.ToolTip.text: qsTr("Sets WINEDEBUG for Wine/Proton Output.")
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
                            // One label column for the tab, so the fields of every
                            // section start at the same x.
                            property real labelWidth: Math.max(gameModeForm.naturalLabelWidth,
                                                               mangoForm.naturalLabelWidth,
                                                               upscalerForm.naturalLabelWidth)
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Game Mode")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: gameModeForm
                                    labelWidth: perfForm.labelWidth
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: perfFeral
                                        objectName: "perfFeral"
                                        text: qsTr("Enable Feral GameMode (gamemoderun)")
                                        Controls.ToolTip.text: qsTr("Optimizes CPU and GPU Governors While the Game Runs. Mutually Exclusive with CachyOS game-performance.")
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
                                        Controls.ToolTip.text: qsTr("Applies the CachyOS Gaming Performance Profile. Mutually Exclusive with Feral GameMode.")
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
                                    id: mangoForm
                                    labelWidth: perfForm.labelWidth
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
                                        KirigamiLayouts.FormData.label: qsTr("FPS Limit (0 = Off):")
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
                                    id: upscalerForm
                                    labelWidth: perfForm.labelWidth
                                    Controls.CheckBox {
                                        id: rtEnable
                                        objectName: "rtEnable"
                                        text: qsTr("Enable RT Upscaler (linux-rt-upscaler)")
                                        Controls.ToolTip.text: qsTr("SRCNN Upscaling for X11/XWayland Windows; Forces PROTON_ENABLE_WAYLAND=0.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.TextField {
                                        id: rtArgs
                                        objectName: "rtArgs"
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Upscaler Options:")
                                        placeholderText: qsTr("-m 4x24 (See upscale --help-all)")
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
                            // One label column for the tab, so the fields of every
                            // section start at the same x.
                            property real labelWidth: Math.max(displayModeForm.naturalLabelWidth,
                                                               gamescopeForm.naturalLabelWidth)
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Display Mode")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: displayModeForm
                                    labelWidth: dispForm.labelWidth
                                    Controls.TextField {
                                        id: dispOut
                                        objectName: "dispOut"
                                        placeholderText: qsTr("Auto = Current Output")
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
                                        text: qsTr("Same Mode as Current: Dips Down and Back First (VRAM Workaround).")
                                    }
                                    RowLayout {
                                        id: dipRow
                                        objectName: "dipRow"
                                        visible: false
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Dip Delay:")
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
                                    id: gamescopeForm
                                    labelWidth: dispForm.labelWidth
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
                            // One label column for the tab, so the fields of every
                            // section start at the same x.
                            property real labelWidth: Math.max(notifyForm.naturalLabelWidth,
                                                               suspendForm.naturalLabelWidth,
                                                               nightLightForm.naturalLabelWidth,
                                                               networkForm.naturalLabelWidth,
                                                               audioForm.naturalLabelWidth,
                                                               luForm.naturalLabelWidth)
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            SectionBox {
                                title: qsTr("Notifications")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: notifyForm
                                    labelWidth: sysForm.labelWidth
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: ntLaunch
                                        objectName: "ntLaunch"
                                        text: qsTr("Notify on Launch")
                                        Controls.ToolTip.text: qsTr("Show a Transient Summary Notification When the Game Starts.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Idle Suspend")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: suspendForm
                                    labelWidth: sysForm.labelWidth
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: seInhibit
                                        objectName: "seInhibit"
                                        text: qsTr("Inhibit Idle Suspend While Playing")
                                        Controls.ToolTip.text: qsTr("Holds a logind Idle Lock During the Session. Sleep Lock Is Not Included (Needs Privileges).")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Night Light")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: nightLightForm
                                    labelWidth: sysForm.labelWidth
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: nlDisable
                                        objectName: "nlDisable"
                                        text: qsTr("Disable Night Light While the Game Is Running (Restored on Exit)")
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
                                title: qsTr("Network")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: networkForm
                                    labelWidth: sysForm.labelWidth
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: blockInternet
                                        objectName: "blockInternet"
                                        text: qsTr("Block Internet While the Game Runs")
                                        Controls.ToolTip.text: qsTr("Runs the Game in an Unprivileged Network Namespace (unshare -Urn). Multiplayer, Achievements and Online Services Will Not Work.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Label {
                                        objectName: "blockInternetHint"
                                        visible: blockInternet.checked
                                            && !gameModel.networkIsolationAvailable()
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        color: Kirigami.Theme.negativeTextColor
                                        text: qsTr("Unprivileged Network Namespaces Are Unavailable Here; the Launcher Will Refuse to Start This Game.")
                                    }
                                }
                            }
                            SectionBox {
                                title: qsTr("Audio")
                                Layout.fillWidth: true
                                WidgetsFormLayout {
                                    id: audioForm
                                    labelWidth: sysForm.labelWidth
                                    Layout.fillWidth: true
                                    RowLayout {
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Output Sink:")
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
                                    labelWidth: sysForm.labelWidth
                                    id: luForm
                                    objectName: "luForm"
                                    Layout.fillWidth: true
                                    Controls.CheckBox {
                                        id: luEnable
                                        objectName: "luEnable"
                                        text: qsTr("Enable Ludusavi for This Game")
                                    }
                                    Controls.CheckBox {
                                        id: luRestore
                                        objectName: "luRestore"
                                        text: qsTr("Restore Backup Before Launch")
                                        Controls.ToolTip.text: qsTr("Unchecked = --no-restore")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.CheckBox {
                                        id: luBackup
                                        objectName: "luBackup"
                                        text: qsTr("Back up After Exit")
                                        Controls.ToolTip.text: qsTr("Unchecked = --no-backup")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.TextField {
                                        id: luName
                                        objectName: "luName"
                                        // A local game has no Steam id for --infer:
                                        // empty resolves saves by the game name.
                                        placeholderText: !fields.is_steam && (fields.name || "") !== ""
                                            ? qsTr("Empty = %1").arg(fields.name)
                                            : qsTr("Leave Empty to Detect the Game from Steam")
                                        Layout.fillWidth: true
                                        KirigamiLayouts.FormData.label: qsTr("Game Name Override:")
                                    }
                                    Controls.CheckBox {
                                        id: luGui
                                        objectName: "luGui"
                                        text: qsTr("Show Prompts (--gui)")
                                        Controls.ToolTip.text: qsTr("With Prompts Enabled, Restore and Backup Can Be Declined per Session.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Label {
                                        // The widgets adds this note as a spanning row
                                        // (addRow with a single widget), not as a field.
                                        objectName: "luNote"
                                        KirigamiLayouts.FormData.isSection: true
                                        Layout.fillWidth: true
                                        wrapMode: Text.WordWrap
                                        text: qsTr("With Prompts Enabled, Restore and Backup Can Be Declined per Session.")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        visible: editAppid !== ""
                                        KirigamiLayouts.FormData.label: qsTr("Coverage:")
                                        Controls.Button {
                                            objectName: "luCoverage"
                                            text: qsTr("Check Coverage...")
                                            onClicked: gameModel.checkCoverage(editAppid, luName.text, fields.name || "")
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
                        // One label column for the tab, so the fields of every
                        // section start at the same x.
                        property real labelWidth: Math.max(artForm.naturalLabelWidth,
                                                           notesForm.naturalLabelWidth)
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        SectionBox {
                            title: qsTr("Artwork")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                labelWidth: artColumn.labelWidth
                                id: artForm
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Icon Override:")
                                    Controls.TextField {
                                        id: artIconField
                                        objectName: "artIcon"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artIconPick"
                                        text: qsTr("Pick…")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:icon"
                                            gameModel.pickPath(qsTr("Icon Image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artIconClear"
                                        text: qsTr("Clear")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: gameSettings.clearArtwork("icon")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Cover Image:")
                                    Controls.TextField {
                                        id: artCoverField
                                        objectName: "artCover"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artCoverPick"
                                        text: qsTr("Pick…")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:cover"
                                            gameModel.pickPath(qsTr("Cover Image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artCoverClear"
                                        text: qsTr("Clear")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: gameSettings.clearArtwork("cover")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Banner Image:")
                                    Controls.TextField {
                                        id: artBannerField
                                        objectName: "artBanner"
                                        readOnly: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Button {
                                        objectName: "artBannerPick"
                                        text: qsTr("Pick…")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: {
                                            gameSettings.pendingBrowse = "art:banner"
                                            gameModel.pickPath(qsTr("Banner Image"), qsTr("Select"))
                                        }
                                    }
                                    Controls.Button {
                                        objectName: "artBannerClear"
                                        text: qsTr("Clear")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        onClicked: gameSettings.clearArtwork("banner")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Artwork Source AppID:")
                                    Controls.TextField {
                                        id: artSourceField
                                        objectName: "artSource"
                                        placeholderText: qsTr("Steam AppID to Take Artwork From")
                                        Layout.fillWidth: true
                                        Controls.ToolTip.text: qsTr("Steam AppID (installed or not) Whose Artwork This Game Uses. Downloaded From SteamGridDB When a Key Is Set.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "artSourceFind"
                                        text: qsTr("Find…")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        // One button, left column: the spacer keeps the
                                        // field the same width as the rows above.
                                        onClicked: {
                                            var rows = gameModel.donorCandidates(artSourceField.text)
                                            if (rows.length === 0) {
                                                if (page !== null) {
                                                    page.notify(qsTr("No Games Match That AppID or Name."))
                                                }
                                                return
                                            }
                                            var items = []
                                            for (var i = 0; i < rows.length; i++) {
                                                items.push({"text": rows[i][1] + " [" + rows[i][0] + "]", "data": rows[i][0]})
                                            }
                                            gameSettings.askChoice("artSource", items, "")
                                        }
                                    }
                                    Item {
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Status:")
                                    Controls.Label {
                                        id: artStatusLabel
                                        objectName: "artStatus"
                                        Layout.fillWidth: true
                                        // Without a 0 preferred/minimum the
                                        // RowLayout refuses to shrink below
                                        // implicitWidth, the wrap never
                                        // fires and the button is pushed
                                        // past the section edge at 612 px.
                                        Layout.preferredWidth: 0
                                        Layout.minimumWidth: 0
                                        wrapMode: Text.WordWrap
                                    }
                                    Controls.Button {
                                        objectName: "artFetch"
                                        text: qsTr("Fetch Artwork")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        enabled: editAppid !== ""
                                        onClicked: gameSettings.fetchArtwork()
                                    }
                                    Controls.Button {
                                        objectName: "artClear"
                                        text: qsTr("Clear…")
                                        Layout.preferredWidth: gameSettings.artButtonWidth
                                        Layout.minimumWidth: gameSettings.artButtonWidth
                                        enabled: editAppid !== ""
                                            && artSourceField.text.trim() !== ""
                                        onClicked: gameSettings.requestClearFetched()
                                        Controls.ToolTip.text: qsTr("Remove the Artwork Downloaded From the Artwork Source AppID")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Notes")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: notesForm
                                labelWidth: artColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.TextArea {
                                    id: notesArea
                                    objectName: "settingsNotes"
                                    placeholderText: qsTr("Notes for This Game…")
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
                                gameSettings.page.notify(qsTr("Could Not Open the Link."))
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
                    diffText.text = diff !== "" ? diff : qsTr("(No Differences)")
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
        title: pendingPrompt === "mhName" ? qsTr("New MangoHud Configuration") : (pendingPrompt === "clone" ? qsTr("Clone Profile") : qsTr("Save Profile"))
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.TextField {
                id: promptField
                objectName: "settingsPromptField"
                placeholderText: qsTr("Profile Name")
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
                ? qsTr("Start From:")
                : qsTr("Take Artwork From…"))
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.ComboBox {
                id: choiceBox
                objectName: "settingsChoiceBox"
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 20
                textRole: "text"
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
                placeholderText: qsTr("KEY=value Lines (# Comments and Blanks Skipped)")
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
        id: prefixDialog
        parent: gameSettings.contentItem
        objectName: "settingsPrefixPicker"
        title: qsTr("Existing Prefixes")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Layout.fillWidth: true
            Controls.Label {
                objectName: "settingsPrefixPickerEmpty"
                visible: prefixChoiceRows.count === 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("No Wine Prefix Found Under the Prefix Base.")
            }
            ListView {
                id: prefixChoiceRows
                objectName: "settingsPrefixPickerRows"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, Kirigami.Units.gridUnit * 14)
                clip: true
                model: gameSettings.prefixChoices
                delegate: Controls.ItemDelegate {
                    required property var modelData
                    width: ListView.view ? ListView.view.width : 100
                    text: (modelData.games || []).length > 0
                        ? qsTr("%1 — %2").arg(modelData.name).arg(modelData.games.join(", "))
                        : modelData.name
                    onClicked: {
                        localPrefixNameField.text = modelData.name
                        gameSettings.refreshPrefixHint()
                        prefixDialog.close()
                    }
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsPrefixPickerClose"
                text: qsTr("Close")
                onClicked: prefixDialog.close()
            }
        }
    }

    // Winetricks verb picker: searchable `list-all`; a click appends to
    // the verbs field and the dialog stays open for the next one.
    Kirigami.Dialog {
        id: verbDialog
        parent: gameSettings.contentItem
        objectName: "settingsVerbPicker"
        title: qsTr("Add Winetricks Verb")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Layout.fillWidth: true
            Controls.TextField {
                id: verbFilterField
                objectName: "settingsVerbFilter"
                Layout.fillWidth: true
                placeholderText: qsTr("Filter Verbs (Name or Description)")
                onTextChanged: gameSettings.filterVerbs(text)
            }
            Controls.Label {
                objectName: "settingsVerbPickerStatus"
                visible: gameSettings.verbFiltered.length === 0
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: gameSettings.verbsLoading
                    ? qsTr("Loading Verbs…")
                    : (gameSettings.verbCatalog.length === 0
                        ? qsTr("No Verb List: Winetricks Was Not Found in PATH.")
                        : qsTr("No Matching Verb."))
            }
            ListView {
                id: verbRows
                objectName: "settingsVerbRows"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(contentHeight, Kirigami.Units.gridUnit * 14)
                clip: true
                model: gameSettings.verbFiltered
                delegate: Controls.ItemDelegate {
                    required property var modelData
                    width: ListView.view ? ListView.view.width : 100
                    text: (modelData.description || "") === ""
                        ? modelData.verb
                        : qsTr("%1 — %2").arg(modelData.verb).arg(modelData.description)
                    onClicked: gameSettings.addVerb(modelData.verb)
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsVerbPickerClose"
                text: qsTr("Close")
                onClicked: verbDialog.close()
            }
        }
    }

    // One confirmation at a time: the purpose selects the action in
    // acceptConfirm/acceptConfirmSave, everything else is presentation.
    // Activating the window buttons runs the accept functions, which close
    // the dialog themselves (a failed action keeps the settings window up).
    function setupConfirm(purpose, title, question, acceptText) {
        confirmDialog.title = title
        confirmDialog.question = question
        confirmDialog.detail = ""
        confirmDialog.warning = ""
        confirmDialog.softIcon = false
        confirmDialog.acceptText = acceptText
        confirmDialog.saveVisible = false
        confirmPurpose = purpose
    }

    // A separate modal window on the settings one, the widgets QMessageBox
    // shape: a long detail gets its own wrapping block instead of dictating
    // the box width.
    ConfirmDialog {
        id: confirmDialog
        onAccepted: gameSettings.acceptConfirm()
        onSaved: gameSettings.acceptConfirmSave()
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
