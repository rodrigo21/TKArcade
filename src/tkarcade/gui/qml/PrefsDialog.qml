import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kirigami.layouts as KirigamiLayouts

// Preferences: a separate modal window like the widgets QDialog
// (resizable, transient on the main window). `open()` keeps the old
// Dialog call sites working; `close()` is the native Window one.
Window {
    id: prefsDialog
    objectName: "prefsDialog"
    title: qsTr("Preferences")
    modality: Qt.WindowModal
    // Widgets PreferencesDialog: a plain QFormLayout (checkboxes in the
    // field column, right-aligned labels), a right-aligned Save/Cancel
    // box, and a window sized to the form. `resize(420, 280)` with the
    // layout minimum landing at 420x312 at the time.
    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 16
    width: Kirigami.Units.gridUnit * 23
    height: body.implicitHeight + body.anchors.margins * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var values: ({})
    property var page: null
    property var langCodes: []

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(prefsDialog)
        visible = true
    }

    function load() {
        values = gameModel.loadPrefs()
        quickSpin.value = values.trayQuickCount ?? 5
        var opts = gameModel.languageOptions()
        langCodes = []
        var labels = []
        for (var i = 0; i < opts.length; i++) {
            langCodes.push(opts[i][0])
            labels.push(opts[i][1])
        }
        langCombo.model = labels
        var at = langCodes.indexOf(values.language ?? "system")
        langCombo.currentIndex = at >= 0 ? at : 0
    }

    function setPref(key, value) {
        var copy = {}
        for (var k in values) {
            copy[k] = values[k]
        }
        copy[key] = value
        values = copy
    }

    ColumnLayout {
        id: body
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
            gameModel.pressDefault(prefsDialog, ["prefsSave"])
        }
        Controls.ScrollView {
            clip: true
            objectName: "prefsScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Item {
                width: parent.width
                implicitHeight: prefsForm.implicitHeight
                WidgetsFormLayout {
                    id: prefsForm
                    objectName: "prefsForm"
                    width: parent.width
                    Controls.CheckBox {
                        objectName: "prefsShowPreview"
                        text: qsTr("Show Launch Command Preview")
                        checked: prefsDialog.values.showPreview ?? true
                        onClicked: prefsDialog.setPref("showPreview", checked)
                        Controls.ToolTip.text: qsTr("Live Preview Box at the Bottom of Game Dialogs.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.CheckBox {
                        id: trayCheck
                        objectName: "prefsTray"
                        text: qsTr("Enable Status Bar Icon")
                        checked: prefsDialog.values.trayEnable ?? false
                        onClicked: prefsDialog.setPref("trayEnable", checked)
                        Controls.ToolTip.text: qsTr("Keep TKArcade in the System Tray.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.ComboBox {
                        objectName: "prefsTrayIcon"
                        Layout.fillWidth: true
                        enabled: trayCheck.checked
                        model: [qsTr("Normal"), qsTr("Monochrome")]
                        KirigamiLayouts.FormData.label: qsTr("Tray Icon Style:")
                        currentIndex: prefsDialog.values.trayIcon === "mono" ? 1 : 0
                        onActivated: (index) => prefsDialog.setPref(
                            "trayIcon", index === 1 ? "mono" : "normal")
                    }
                    Controls.CheckBox {
                        text: qsTr("Minimize to Tray")
                        enabled: trayCheck.checked
                        checked: prefsDialog.values.minimizeToTray ?? false
                        onClicked: prefsDialog.setPref("minimizeToTray", checked)
                    }
                    Controls.CheckBox {
                        text: qsTr("Close to Tray")
                        enabled: trayCheck.checked
                        checked: prefsDialog.values.closeToTray ?? false
                        onClicked: prefsDialog.setPref("closeToTray", checked)
                    }
                    Controls.CheckBox {
                        id: quickCheck
                        text: qsTr("Show Recent Games in Tray Menu")
                        enabled: trayCheck.checked
                        checked: prefsDialog.values.trayQuickLaunch ?? false
                        onClicked: prefsDialog.setPref("trayQuickLaunch", checked)
                        Controls.ToolTip.text: qsTr("Launch Recent Games Through Steam (steam:// URL).")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.SpinBox {
                        id: quickSpin
                        objectName: "prefsQuickCount"
                        from: 1
                        to: 10
                        enabled: trayCheck.checked && quickCheck.checked
                        onValueModified: prefsDialog.setPref("trayQuickCount", value)
                        Controls.ToolTip.text: qsTr("How Many Recent Games to List.")
                        Controls.ToolTip.visible: hovered
                        KirigamiLayouts.FormData.label: qsTr("Recent Games:")
                    }
                    Controls.TextField {
                        objectName: "prefsSgdb"
                        Layout.fillWidth: true
                        echoMode: Controls.TextField.Password
                        placeholderText: qsTr("Free Key from steamgriddb.com")
                        text: prefsDialog.values.sgdbApiKey ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.sgdbApiKey !== text) {
                                prefsDialog.setPref("sgdbApiKey", text)
                            }
                        }
                        Controls.ToolTip.text: qsTr("SteamGridDB API Key for Missing Artwork Fallback.")
                        Controls.ToolTip.visible: hovered
                        KirigamiLayouts.FormData.label: qsTr("SteamGridDB Key:")
                    }
                    Controls.ComboBox {
                        id: langCombo
                        objectName: "prefsLanguage"
                        Layout.fillWidth: true
                        KirigamiLayouts.FormData.label: qsTr("Language:")
                        onActivated: (index) => prefsDialog.setPref(
                            "language", prefsDialog.langCodes[index] || "system")
                        Controls.ToolTip.text: qsTr("Takes Effect on Restart.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.TextField {
                        objectName: "prefsPrefixBase"
                        Layout.fillWidth: true
                        placeholderText: qsTr("Default: $XDG_DATA_HOME/tkarcade/prefixes")
                        text: prefsDialog.values.prefixBase ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.prefixBase !== text) {
                                prefsDialog.setPref("prefixBase", text)
                            }
                        }
                        KirigamiLayouts.FormData.label: qsTr("Prefix Base:")
                        Controls.ToolTip.text: qsTr("Local Games Use <base>/<AppID> Unless the Game Overrides the Path.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.TextField {
                        objectName: "prefsWineBinary"
                        Layout.fillWidth: true
                        placeholderText: qsTr("Default: wine from PATH")
                        text: prefsDialog.values.wineBinary ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.wineBinary !== text) {
                                prefsDialog.setPref("wineBinary", text)
                            }
                        }
                        KirigamiLayouts.FormData.label: qsTr("Wine Binary:")
                        Controls.ToolTip.text: qsTr("Wine Executable (Path or Name) for Non-Steam Games.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.TextField {
                        objectName: "prefsProtonDirs"
                        Layout.fillWidth: true
                        placeholderText: qsTr("One Directory per Entry (: Separated)")
                        text: prefsDialog.values.protonDirs ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.protonDirs !== text) {
                                prefsDialog.setPref("protonDirs", text)
                            }
                        }
                        KirigamiLayouts.FormData.label: qsTr("Proton Directories:")
                        Controls.ToolTip.text: qsTr("Extra Proton Installs, on Top of Steam's compatibilitytools.d.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.TextField {
                        objectName: "prefsDxvkDirs"
                        Layout.fillWidth: true
                        placeholderText: qsTr("One Directory per Entry (: Separated)")
                        text: prefsDialog.values.dxvkDirs ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.dxvkDirs !== text) {
                                prefsDialog.setPref("dxvkDirs", text)
                            }
                        }
                        KirigamiLayouts.FormData.label: qsTr("DXVK Directories:")
                        Controls.ToolTip.text: qsTr("Directories Holding One DXVK Version per Subdirectory.")
                        Controls.ToolTip.visible: hovered
                    }
                    Controls.TextField {
                        objectName: "prefsVkd3dDirs"
                        Layout.fillWidth: true
                        placeholderText: qsTr("One Directory per Entry (: Separated)")
                        text: prefsDialog.values.vkd3dDirs ?? ""
                        onTextChanged: {
                            if (prefsDialog.values.vkd3dDirs !== text) {
                                prefsDialog.setPref("vkd3dDirs", text)
                            }
                        }
                        KirigamiLayouts.FormData.label: qsTr("vkd3d-proton Directories:")
                        Controls.ToolTip.text: qsTr("Directories Holding One vkd3d-proton Version per Subdirectory.")
                        Controls.ToolTip.visible: hovered
                    }
                }
            }
        }
        RowLayout {
            id: footer
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "prefsSave"
                text: qsTr("Save")
                // QDialogButtonBox(Save | Cancel): accept first, default.
                highlighted: true
                onClicked: {
                    if (gameModel.savePrefs(prefsDialog.values)) {
                        prefsDialog.close()
                    } else if (page !== null) {
                        page.notify(qsTr("Could Not Save Preferences."))
                    }
                }
            }
            Controls.Button {
                objectName: "prefsCancel"
                text: qsTr("Cancel")
                onClicked: prefsDialog.close()
            }
        }
    }
}
