import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Per-game settings page (widgets GameDialog parity, tab by tab: General
// and Notes first, the rest follow). Pushed on the pageStack like a real
// window (a dialog is too small and cannot resize); the text prompt below
// replaces QInputDialog for profile names.
Kirigami.Page {
    id: gameSettings
    objectName: "gameSettings"
    title: editAppid === "" ? qsTr("Add game") : qsTr("Edit game")

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
    }

    function openNew() {
        editAppid = ""
        fields = blankFields()
        pushToControls()
        errorText = ""
        tabBar.currentIndex = 0
    }

    function closePage() {
        if (page !== null) {
            page.closeGameSettings()
        }
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
            "profiles": profiles
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
        spacing: Kirigami.Units.smallSpacing
        Controls.TabBar {
            id: tabBar
            objectName: "settingsTabs"
            Layout.fillWidth: true
            Controls.TabButton {
                text: qsTr("General")
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
    }

    footer: RowLayout {
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
