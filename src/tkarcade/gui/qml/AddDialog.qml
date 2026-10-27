import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Add game entry point (widgets AddSourceDialog parity): pick the
// source, then run its flow — Steam picker opens settings for the
// AppID, Local picks the environment and opens blank settings with it
// preselected. Modal window like the rest.
Window {
    id: addGameDialog
    objectName: "addGameDialog"
    title: qsTr("Add Game")
    modality: Qt.WindowModal
    // Widgets AddSourceDialog: a short QDialog sized to its two rows and
    // the button box.
    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 8
    width: Kirigami.Units.gridUnit * 26
    height: body.implicitHeight + Kirigami.Units.largeSpacing * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var page: null
    property var steamRows: []
    // Values behind typeBox, in the same order as its labels.
    readonly property var environments: ["native", "wine", "umu"]

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(addGameDialog)
        sourceBox.currentIndex = 0
        typeBox.currentIndex = 0
        loadSteam()
        visible = true
    }

    function selectedEnvironment() {
        var index = typeBox.currentIndex
        return (index >= 0 && index < environments.length) ? environments[index] : "native"
    }

    function loadSteam() {
        var rows = gameModel.scanCandidates()
        var fresh = []
        for (var i = 0; i < rows.length; i++) {
            fresh.push({"text": rows[i][1] + " [" + rows[i][0] + "]", "data": rows[i][0]})
        }
        steamRows = fresh
        steamBox.model = fresh
        steamBox.currentIndex = 0
    }

    function accept() {
        if (sourceBox.currentIndex === 0) {
            if (steamRows.length === 0) {
                if (page !== null) {
                    page.notify(qsTr("Every Steam Game Is Already Configured."))
                }
                addGameDialog.close()
                return
            }
            var item = steamBox.model[steamBox.currentIndex]
            var appid = item !== undefined ? item.data : ""
            addGameDialog.close()
            if (appid !== "" && page !== null) {
                page.openGameSettings(appid)
            }
            return
        }
        addGameDialog.close()
        if (page !== null) {
            page.openNewGameSettings(selectedEnvironment())
        }
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.smallSpacing
        focus: true
        // Enter hits the default button like the widgets QDialog (an open
        // popup's accept first, else ours); a focused TextArea keeps Return.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(addGameDialog, ["addConfirm"])
        }
        Controls.Label {
            text: qsTr("What Kind of Game Is This?")
        }
        Controls.ComboBox {
            id: sourceBox
            objectName: "addSource"
            Layout.fillWidth: true
            model: [qsTr("Steam Game"), qsTr("Local Game")]
        }
        Controls.Label {
            text: qsTr("Environment")
            visible: sourceBox.currentIndex === 1
        }
        Controls.ComboBox {
            id: typeBox
            objectName: "addEnvironment"
            visible: sourceBox.currentIndex === 1
            Layout.fillWidth: true
            // Same three choices as Settings, in the same order.
            model: [
                qsTr("Native"),
                qsTr("Wine"),
                qsTr("Proton (UMU)")
            ]
        }
        Controls.ComboBox {
            id: steamBox
            objectName: "addSteamGame"
            visible: sourceBox.currentIndex === 0
            Layout.fillWidth: true
            textRole: "text"
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "addConfirm"
                text: qsTr("OK")
                // QDialogButtonBox(Ok | Cancel): accept first, default.
                highlighted: true
                onClicked: addGameDialog.accept()
            }
            Controls.Button {
                objectName: "addCancel"
                text: qsTr("Cancel")
                onClicked: addGameDialog.close()
            }
        }
    }
}
