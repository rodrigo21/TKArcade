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
    // Widgets AddSourceDialog: a short QDialog sized to its rows and the
    // button box; the Steam list scrolls once it would pass 20 gridUnits.
    readonly property real steamListCap: Kirigami.Units.gridUnit * 20
    // Width follows the widest "name [appid]" so nothing is clipped,
    // capped to 90% of the screen (ScanDialog); Local keeps the dialog
    // width the widgets used.
    readonly property real screenCap: screen ? screen.width * 0.9
                                             : Kirigami.Units.gridUnit * 80
    FontMetrics {
        id: addMetrics
        font: Kirigami.Theme.defaultFont
    }
    function contentWidth() {
        var widest = 0
        for (var i = 0; i < steamRows.length; i++) {
            widest = Math.max(widest, addMetrics.advanceWidth(steamRows[i].text))
        }
        // Radio indicator, padding and the scroll bar.
        return widest + Kirigami.Units.gridUnit * 3
    }
    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 8
    width: sourceBox.currentIndex === 0
        ? Math.min(screenCap,
                   Math.max(minimumWidth, contentWidth() + body.anchors.margins * 2))
        : Kirigami.Units.gridUnit * 26
    // The body margins are 12px per side; the old largeSpacing * 2 (8px
    // per side) left the body 8px short and squeezed the Steam list.
    height: Math.max(minimumHeight, body.implicitHeight + body.anchors.margins * 2)
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var page: null
    property var steamRows: []
    property int steamIndex: 0
    // Values behind runtimeTypeBox, in the same order as its labels.
    readonly property var runtimes: ["native", "umu", "wine"]

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(addGameDialog)
        sourceBox.currentIndex = 0
        runtimeTypeBox.currentIndex = 0
        loadSteam()
        visible = true
    }

    function selectedRuntime() {
        var index = runtimeTypeBox.currentIndex
        return (index >= 0 && index < runtimes.length) ? runtimes[index] : "native"
    }

    function loadSteam() {
        var rows = gameModel.scanCandidates()
        var fresh = []
        for (var i = 0; i < rows.length; i++) {
            fresh.push({"text": rows[i][1] + " [" + rows[i][0] + "]", "data": rows[i][0]})
        }
        steamRows = fresh
        steamIndex = 0
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
            var index = steamIndex
            var item = index >= 0 && index < steamRows.length ? steamRows[index] : null
            var appid = item !== null ? item.data : ""
            addGameDialog.close()
            if (appid !== "" && page !== null) {
                page.openGameSettings(appid)
            }
            return
        }
        addGameDialog.close()
        if (page !== null) {
            page.openNewGameSettings(selectedRuntime())
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
            text: qsTr("Runtime")
            visible: sourceBox.currentIndex === 1
        }
        Controls.ComboBox {
            id: runtimeTypeBox
            objectName: "addRuntime"
            visible: sourceBox.currentIndex === 1
            Layout.fillWidth: true
            // Same three choices as Settings, in the same order.
            model: [
                qsTr("Native"),
                qsTr("UMU"),
                qsTr("Wine")
            ]
        }
        Item {
            id: steamArea
            objectName: "addSteamGame"
            visible: sourceBox.currentIndex === 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            // The implicit height feeds the window binding; the cap keeps
            // a long library scrollable instead of stretching the dialog.
            implicitHeight: Math.min(addGameDialog.steamListCap, steamColumn.implicitHeight)
            Controls.ScrollView {
                anchors.fill: parent
                clip: true
                ColumnLayout {
                    id: steamColumn
                    objectName: "addSteamColumn"
                    width: Math.max(parent.width, implicitWidth)
                    spacing: Kirigami.Units.smallSpacing
                    Repeater {
                        model: addGameDialog.steamRows
                        Controls.RadioButton {
                            required property var modelData
                            required property int index
                            text: modelData.text
                            checked: addGameDialog.steamIndex === index
                            onToggled: {
                                if (checked) {
                                    addGameDialog.steamIndex = index
                                }
                            }
                        }
                    }
                }
            }
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
