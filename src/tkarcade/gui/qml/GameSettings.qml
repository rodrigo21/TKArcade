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
        visible = true
    }

    function openNew() {
        editAppid = ""
        fields = blankFields()
        pushToControls()
        errorText = ""
        tabBar.currentIndex = 0
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
            "gamemode_cachy": perfCachy.checked
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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
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
        title: pendingPrompt === "clone" ? qsTr("Clone profile") : qsTr("Save profile")
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
}
