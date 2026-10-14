import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Per-game settings window (widgets GameDialog parity, tab by tab:
// General and Notes first, the rest follow). A separate modal window
// like the widgets QDialog (resizable, centered on the main window via
// transientParent) — never embedded in the pageStack, never a popup;
// the text prompt below replaces QInputDialog for profile names.
Window {
    id: gameSettings
    objectName: "gameSettings"
    title: editAppid === "" ? qsTr("Add game") : qsTr("Edit game")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 34
    minimumHeight: Kirigami.Units.gridUnit * 30
    width: Kirigami.Units.gridUnit * 42
    height: Kirigami.Units.gridUnit * 36
    visible: false
    color: Kirigami.Theme.backgroundColor

    property string editAppid: ""
    property var fields: ({})
    property string errorText: ""
    property string pendingPrompt: "" // "saveAs" | "clone" | ""
    property var dmodeModel: [{"text": "", "data": ""}]
    property string dmodeCurrent: ""
    property string pendingArg: ""
    property string ptLogDir: ""
    property var page: null

    function blankFields() {
        return {
            "appid": "",
            "name": "",
            "custom_executable": "",
            "game_type": "auto",
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
        reload()
        errorText = ""
        tabBar.currentIndex = 0
        gameModel.watchQuitKeys(gameSettings)
        visible = true
    }

    function openNew() {
        editAppid = ""
        fields = blankFields()
        pushToControls()
        errorText = ""
        tabBar.currentIndex = 0
        gameModel.watchQuitKeys(gameSettings)
        visible = true
    }

    function closePage() {
        visible = false
    }

    function reload() {
        fields = gameModel.loadGame(editAppid)
        pushToControls()
    }

    function pushToControls() {
        var f = fields
        appidField.text = f.appid || ""
        nameField.text = f.name || ""
        exeField.text = f.custom_executable || ""
        typeBox.currentIndex = f.game_type === "proton" ? 1 : (f.game_type === "native" ? 2 : 0)
        prefixField.text = f.custom_prefix || ""
        menuCheck.checked = !!f.show_menu
        timeoutSpin.value = f.menu_timeout || 0
        notesArea.text = f.notes || ""
        profileBox.model = (f.profiles || []).slice()
        profileBox.currentIndex = Math.max(0, (f.profiles || []).indexOf(f.active_profile))
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
        ptVerbs.text = f.winetricks_verbs || ""
        ptLog.checked = !!f.proton_log
        ptDebug.currentIndex = {"": 0, "-all": 1, "+err": 2, "+warn,+err": 3}[f.winedebug] ?? 0
        ptLogDir = editAppid !== "" ? gameModel.protonLogDir(editAppid) : ""
        envModel.clear()
        var rows = f.env_vars || []
        for (var i = 0; i < rows.length; i++) {
            envModel.append({"key": rows[i].key || "", "value": rows[i].value || ""})
        }
    }

    function collect() {
        var profiles = fields.profiles || []
        return {
            "name": nameField.text,
            "custom_executable": exeField.text,
            "game_type": ["auto", "proton", "native"][typeBox.currentIndex] || "auto",
            "show_menu": menuCheck.checked,
            "menu_timeout": timeoutSpin.value,
            "custom_prefix": prefixField.text,
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
            "winetricks_verbs": ptVerbs.text,
            "proton_log": ptLog.checked,
            "winedebug": ["", "-all", "+err", "+warn,+err"][ptDebug.currentIndex] || ""
        }
    }

    function collectEnv() {
        var out = []
        for (var i = 0; i < envModel.count; i++) {
            var row = envModel.get(i)
            out.push({"key": row.key, "value": row.value})
        }
        return out
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

    function removeEnvRow(i) {
        if (i >= 0 && i < envModel.count) {
            envModel.remove(i)
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
        } else if (pendingPrompt === "mhTemplate") {
            // Positional twin of the labels passed at the ask site.
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
        }
    }

    function save() {
        var created = gameModel.saveGame(editAppid, collect())
        if (created === "") {
            settingsError.text = editAppid === ""
                ? qsTr("Name and a valid executable are required.")
                : qsTr("Could not save the game.")
            return
        }
        if (editAppid === "" && page !== null) {
            page.select(created)
        }
        closePage()
    }

    function askProfileName(purpose) {
        pendingPrompt = purpose
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
            ok = gameModel.saveGameProfile(editAppid, name)
        } else if (pendingPrompt === "clone") {
            var profiles = profileBox.model || []
            ok = gameModel.cloneGameProfile(editAppid, profiles[profileBox.currentIndex] || "", name)
        }
        if (!ok) {
            promptError.text = qsTr("Could not save the profile.")
            return
        }
        namePrompt.close()
        reload()
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
        // Focus-chain quit (see MainPage): fires even where the
        // Shortcut map stays silent.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        Controls.TabBar {
            id: tabBar
            objectName: "settingsTabs"
            Layout.fillWidth: true
            Controls.TabButton {
                text: qsTr("General")
            }
            Controls.TabButton {
                text: qsTr("Environment")
            }
            Controls.TabButton {
                text: qsTr("Pre/Post Commands")
            }
            Controls.TabButton {
                text: qsTr("Performance")
            }
            Controls.TabButton {
                text: qsTr("Display")
            }
            Controls.TabButton {
                text: qsTr("Ludusavi")
            }
            Controls.TabButton {
                text: qsTr("System")
            }
            Controls.TabButton {
                text: qsTr("Wine / Proton")
                enabled: (fields.is_steam || false) && editAppid !== ""
            }
            Controls.TabButton {
                text: qsTr("Notes")
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex
            Controls.ScrollView {
                clip: true
                objectName: "settingsGeneralScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Item {
                    width: parent.width
                    height: generalForm.implicitHeight
                    ColumnLayout {
                    id: generalForm
                    objectName: "settingsGeneralForm"
                    // Centered readable column (widgets-dialog feel),
                    // capped — never full-bleed. Anchored: a raw x is
                    // reset by the ScrollView content management.
                    width: Math.min(parent.width, Kirigami.Units.gridUnit * 38)
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    visible: editAppid !== ""
                    text: qsTr("Steam App ID:")
                }
                Controls.TextField {
                    id: appidField
                    objectName: "settingsAppid"
                    visible: editAppid !== ""
                    readOnly: true
                    Layout.fillWidth: true
                }
                Controls.Label {
                    visible: !(fields.is_steam || false)
                    text: qsTr("Game name:")
                }
                Controls.TextField {
                    id: nameField
                    objectName: "settingsName"
                    visible: !(fields.is_steam || false)
                    placeholderText: qsTr("Game name")
                    Layout.fillWidth: true
                }
                Controls.Label {
                    text: qsTr("Custom executable:")
                }
                RowLayout {
                    Layout.fillWidth: true
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
                                return
                            }
                            exeField.text = picked
                            if (nameField.visible && nameField.text === "") {
                                var parts = picked.split("/")
                                nameField.text = parts[parts.length - 1]
                            }
                        }
                    }
                }
                Controls.Label {
                    text: qsTr("Game type:")
                }
                Controls.ComboBox {
                    id: typeBox
                    objectName: "settingsType"
                    Layout.fillWidth: true
                    model: [qsTr("Automatic"), qsTr("Proton"), qsTr("Native Linux")]
                }
                Controls.Label {
                    text: qsTr("Custom command prefix:")
                }
                Controls.TextField {
                    id: prefixField
                    objectName: "settingsPrefix"
                    placeholderText: qsTr("e.g. zink-run")
                    Layout.fillWidth: true
                }
                Controls.CheckBox {
                    id: menuCheck
                    objectName: "settingsMenu"
                    text: qsTr("Show menu before launch")
                }
                RowLayout {
                    Controls.Label {
                        text: qsTr("Menu timeout (seconds):")
                    }
                    Controls.SpinBox {
                        id: timeoutSpin
                        objectName: "settingsTimeout"
                        from: 0
                        to: 600
                    }
                }
                Controls.Label {
                    visible: editAppid !== ""
                    text: qsTr("Profile:")
                }
                RowLayout {
                    visible: editAppid !== ""
                    Layout.fillWidth: true
                    Controls.ComboBox {
                        id: profileBox
                        objectName: "settingsProfiles"
                        Layout.fillWidth: true
                        textRole: "display"
                        onActivated: (index) => {
                            var profiles = profileBox.model || []
                            if (gameModel.loadGameProfile(editAppid, profiles[index] || "")) {
                                reload()
                            }
                        }
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
                            if (gameModel.deleteGameProfile(editAppid, profiles[profileBox.currentIndex] || "")) {
                                reload()
                            }
                        }
                    }
                }
                Controls.Label {
                    visible: editAppid !== ""
                    text: qsTr("Log File:")
                }
                RowLayout {
                    visible: editAppid !== ""
                    Layout.fillWidth: true
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
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.Label {
                    text: qsTr("Per-game environment variables:")
                }
                Controls.ScrollView {
                    clip: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: envForm.implicitHeight
                        ColumnLayout {
                            id: envForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            ListModel {
                                id: envModel
                            }
                            Repeater {
                                model: envModel
                                delegate: RowLayout {
                                    width: envForm.width
                                    Controls.TextField {
                                        Layout.fillWidth: true
                                        placeholderText: qsTr("Variable")
                                        text: key
                                        onTextChanged: envModel.setProperty(index, "key", text)
                                    }
                                    Controls.TextField {
                                        Layout.fillWidth: true
                                        placeholderText: qsTr("Value")
                                        text: value
                                        onTextChanged: envModel.setProperty(index, "value", text)
                                    }
                                    Controls.ToolButton {
                                        icon.name: "list-remove"
                                        display: Controls.AbstractButton.IconOnly
                                        onClicked: envModel.remove(index)
                                    }
                                }
                            }
                        }
                    }
                }
                Controls.Button {
                    objectName: "envAdd"
                    text: qsTr("Add variable")
                    onClicked: envModel.append({"key": "", "value": ""})
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: ppForm.implicitHeight
                        ColumnLayout {
                            id: ppForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Controls.Label {
                                text: qsTr("Pre-launch command:")
                            }
                            Controls.TextField {
                                id: ppPre
                                objectName: "ppPre"
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                text: qsTr("Pre-launch arguments:")
                            }
                            Controls.TextField {
                                id: ppPreArgs
                                objectName: "ppPreArgs"
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                text: qsTr("Post-exit command:")
                            }
                            Controls.TextField {
                                id: ppPost
                                objectName: "ppPost"
                                Layout.fillWidth: true
                            }
                            Controls.Label {
                                text: qsTr("Post-exit arguments:")
                            }
                            Controls.TextField {
                                id: ppPostArgs
                                objectName: "ppPostArgs"
                                Layout.fillWidth: true
                            }
                            RowLayout {
                                Controls.Label {
                                    text: qsTr("Timeout (seconds):")
                                }
                                Controls.SpinBox {
                                    id: ppTimeout
                                    objectName: "ppTimeout"
                                    from: 1
                                    to: 3600
                                }
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
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: perfForm.implicitHeight
                        ColumnLayout {
                            id: perfForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Controls.GroupBox {
                                title: qsTr("System")
                                Layout.fillWidth: true
                                ColumnLayout {
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
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: dispForm.implicitHeight
                        ColumnLayout {
                            id: dispForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Controls.GroupBox {
                                title: qsTr("Display Mode")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.Label {
                                        text: qsTr("Output:")
                                    }
                                    Controls.TextField {
                                        id: dispOut
                                        objectName: "dispOut"
                                        placeholderText: qsTr("auto = current output")
                                        Layout.fillWidth: true
                                    }
                                    Controls.Label {
                                        text: qsTr("Mode:")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
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
                                    Controls.Label {
                                        text: qsTr("Provider:")
                                    }
                                    Controls.ComboBox {
                                        id: dispProv
                                        objectName: "dispProv"
                                        Layout.fillWidth: true
                                        model: [qsTr("Automatic"), qsTr("Plasma"), qsTr("GNOME"), qsTr("wlroots"), qsTr("X11"), qsTr("Disabled")]
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
                                        Controls.Label {
                                            text: qsTr("Dip delay:")
                                        }
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
                            Controls.GroupBox {
                                title: qsTr("Gamescope")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: gsEnable
                                        objectName: "gsEnable"
                                        text: qsTr("Enable Gamescope")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
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
                            Controls.GroupBox {
                                title: qsTr("MangoHud")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: mhEnable
                                        objectName: "mhEnable"
                                        text: qsTr("Enable MangoHud")
                                    }
                                    Controls.Label {
                                        text: qsTr("MangoHud Options:")
                                    }
                                    Controls.TextField {
                                        id: mhArgs
                                        objectName: "mhArgs"
                                        Layout.fillWidth: true
                                    }
                                    Controls.Label {
                                        text: qsTr("MangoHud Configuration:")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
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
                            Controls.GroupBox {
                                title: qsTr("RT Upscaler")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: rtEnable
                                        objectName: "rtEnable"
                                        text: qsTr("Enable RT Upscaler (linux-rt-upscaler)")
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Controls.TextField {
                                            id: rtArgs
                                            objectName: "rtArgs"
                                            placeholderText: qsTr("-m 4x24 (see upscale --help-all)")
                                            Layout.fillWidth: true
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
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: luForm.implicitHeight
                        ColumnLayout {
                            id: luForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
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
                            Controls.Label {
                                text: qsTr("Game Name Override:")
                            }
                            Controls.TextField {
                                id: luName
                                objectName: "luName"
                                placeholderText: qsTr("Leave empty to detect the game from Steam")
                                Layout.fillWidth: true
                            }
                            Controls.CheckBox {
                                id: luGui
                                objectName: "luGui"
                                text: qsTr("Show Prompts (--gui)")
                                Controls.ToolTip.text: qsTr("With prompts enabled, restore and backup can be declined per session.")
                                Controls.ToolTip.visible: hovered
                            }
                            Controls.Label {
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                                text: qsTr("With prompts enabled, restore and backup can be declined per session.")
                            }
                            RowLayout {
                                visible: editAppid !== ""
                                Controls.Label {
                                    text: qsTr("Coverage:")
                                }
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
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.ScrollView {
                    clip: true
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: sysForm.implicitHeight
                        ColumnLayout {
                            id: sysForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Controls.GroupBox {
                                title: qsTr("Notifications")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: ntLaunch
                                        objectName: "ntLaunch"
                                        text: qsTr("Notify on launch")
                                        Controls.ToolTip.text: qsTr("Show a transient summary notification when the game starts.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            Controls.GroupBox {
                                title: qsTr("Idle Suspend")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: seInhibit
                                        objectName: "seInhibit"
                                        text: qsTr("Inhibit idle suspend while playing")
                                        Controls.ToolTip.text: qsTr("Holds a logind idle lock during the session. Sleep lock is not included (needs privileges).")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                            Controls.GroupBox {
                                title: qsTr("Night Light")
                                Layout.fillWidth: true
                                ColumnLayout {
                                    Controls.CheckBox {
                                        id: nlDisable
                                        objectName: "nlDisable"
                                        text: qsTr("Disable night light while the game is running (restored on exit)")
                                    }
                                    Controls.Label {
                                        text: qsTr("Provider:")
                                    }
                                    Controls.ComboBox {
                                        id: nlProv
                                        objectName: "nlProv"
                                        Layout.fillWidth: true
                                        model: [qsTr("Automatic"), qsTr("Plasma"), qsTr("GNOME"), qsTr("Disabled")]
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
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        height: wineForm.implicitHeight
                        ColumnLayout {
                            id: wineForm
                            objectName: "wineForm"
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            enabled: (fields.is_steam || false) && editAppid !== ""
                            Controls.CheckBox {
                                id: ptFresh
                                objectName: "ptFresh"
                                text: qsTr("Delete prefix before launch (fresh start)")
                                Controls.ToolTip.text: qsTr("Deletes the compatdata prefix so Steam recreates it. WIPES saves inside the prefix — rely on cloud or Ludusavi backups!")
                                Controls.ToolTip.visible: hovered
                            }
                            Controls.Label {
                                text: qsTr("Winetricks Verbs:")
                            }
                            Controls.TextField {
                                id: ptVerbs
                                objectName: "ptVerbs"
                                placeholderText: qsTr("dotnet48 vcrun2022 (space-separated)")
                                Controls.ToolTip.text: qsTr("Winetricks verbs installed via protontricks before launch.")
                                Controls.ToolTip.visible: hovered
                                Layout.fillWidth: true
                            }
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
                            Controls.Label {
                                text: qsTr("Wine Debug:")
                            }
                            Controls.ComboBox {
                                id: ptDebug
                                objectName: "ptDebug"
                                Layout.fillWidth: true
                                model: [qsTr("Off"), qsTr("Quiet (-all)"), qsTr("Errors (+err)"), qsTr("Warnings (+warn,+err)")]
                                Controls.ToolTip.text: qsTr("Sets WINEDEBUG for Wine/Proton output.")
                                Controls.ToolTip.visible: hovered
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Controls.TextArea {
                    id: notesArea
                    objectName: "settingsNotes"
                    placeholderText: qsTr("Notes for this game…")
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    Layout.fillHeight: true
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
        RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "settingsSave"
                text: qsTr("Save")
                onClicked: gameSettings.save()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: gameSettings.closePage()
            }
        }
    }

    Kirigami.Dialog {
        id: namePrompt
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
            Controls.Button {
                objectName: "settingsPromptOk"
                text: qsTr("OK")
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
        objectName: "settingsChoicePrompt"
        title: pendingPrompt === "mhTemplate" ? qsTr("Start from:") : qsTr("Gamescope Preset")
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
            Controls.Button {
                objectName: "settingsChoiceOk"
                text: qsTr("OK")
                onClicked: gameSettings.acceptChoice()
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: choicePrompt.close()
            }
        }
    }
}
