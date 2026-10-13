import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

// Preferences: a separate modal window like the widgets QDialog
// (resizable, transient on the main window). `open()` keeps the old
// Dialog call sites working; `close()` is the native Window one.
Window {
    id: prefsDialog
    objectName: "prefsDialog"
    title: qsTr("Preferences")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 26
    width: Kirigami.Units.gridUnit * 34
    height: Kirigami.Units.gridUnit * 36
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var values: ({})
    property var page: null

    function open() {
        transientParent = Controls.ApplicationWindow.window
        visible = true
    }

    function load() {
        values = gameModel.loadPrefs()
        quickSpin.value = values.trayQuickCount ?? 5
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
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
        Controls.ScrollView {
            clip: true
            Layout.fillWidth: true
            Layout.fillHeight: true
            Item {
                width: parent.width
                height: prefsForm.implicitHeight
                ColumnLayout {
                    id: prefsForm
                    width: parent.width
                    spacing: Kirigami.Units.smallSpacing
                    FormCard.FormCard {
                        Layout.fillWidth: true
                        FormCard.FormCheckDelegate {
                            text: qsTr("Show launch command preview")
                            checked: prefsDialog.values.showPreview ?? true
                            onClicked: prefsDialog.setPref("showPreview", checked)
                        }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Enable status bar icon")
                            checked: prefsDialog.values.trayEnable ?? false
                            onClicked: prefsDialog.setPref("trayEnable", checked)
                        }
                        FormCard.FormComboBoxDelegate {
                            text: qsTr("Tray icon style:")
                            model: [qsTr("Normal"), qsTr("Monochrome")]
                            currentIndex: prefsDialog.values.trayIcon === "mono" ? 1 : 0
                            onActivated: (index) => prefsDialog.setPref(
                                "trayIcon", index === 1 ? "mono" : "normal")
                        }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Minimize to tray")
                            checked: prefsDialog.values.minimizeToTray ?? false
                            onClicked: prefsDialog.setPref("minimizeToTray", checked)
                        }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Close to tray")
                            checked: prefsDialog.values.closeToTray ?? false
                            onClicked: prefsDialog.setPref("closeToTray", checked)
                        }
                        FormCard.FormCheckDelegate {
                            text: qsTr("Show recent games in tray menu")
                            checked: prefsDialog.values.trayQuickLaunch ?? false
                            onClicked: prefsDialog.setPref("trayQuickLaunch", checked)
                        }
                        FormCard.FormSpinBoxDelegate {
                            id: quickSpin
                            label: qsTr("Recent games:")
                            from: 1
                            to: 10
                            onValueModified: prefsDialog.setPref("trayQuickCount", value)
                        }
                    }
                    // Plain row: FormTextFieldDelegate calls bare i18ndc(),
                    // which needs a KLocalizedContext our engine does not
                    // install (works, but logs warnings).
                    RowLayout {
                        Controls.Label {
                            text: qsTr("SteamGridDB key:")
                        }
                        Controls.TextField {
                            Layout.fillWidth: true
                            echoMode: Controls.TextField.Password
                            placeholderText: qsTr("Free key from steamgriddb.com")
                            text: prefsDialog.values.sgdbApiKey ?? ""
                            onTextChanged: {
                                if (prefsDialog.values.sgdbApiKey !== text) {
                                    prefsDialog.setPref("sgdbApiKey", text)
                                }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "prefsSave"
                text: qsTr("Save")
                onClicked: {
                    if (gameModel.savePrefs(prefsDialog.values)) {
                        prefsDialog.close()
                    } else if (page !== null) {
                        page.notify(qsTr("Could not save preferences."))
                    }
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: prefsDialog.close()
            }
        }
    }
}
