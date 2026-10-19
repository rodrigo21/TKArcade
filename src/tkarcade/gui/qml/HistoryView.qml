import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kirigami.dialogs as KirigamiDialogs

// Session history: a separate modal window like the widgets QDialog
// (resizable, transient on the main window). `open()` keeps the old
// Dialog call sites working; `close()` is the native Window one.
Window {
    id: historyView
    objectName: "historyView"
    title: qsTr("Session History")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 28
    minimumHeight: Kirigami.Units.gridUnit * 16
    width: Kirigami.Units.gridUnit * 36
    height: Kirigami.Units.gridUnit * 22
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var rows: []

    // Column widths shared by the header and the delegates so the two
    // rows of labels stay aligned (widgets QTableWidget parity).
    readonly property int colLast: Kirigami.Units.gridUnit * 9
    readonly property int colRuns: Kirigami.Units.gridUnit * 4
    readonly property int colTotal: Kirigami.Units.gridUnit * 5
    readonly property int colFails: Kirigami.Units.gridUnit * 4

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchQuitKeys(historyView)
        visible = true
    }

    function clearAll() {
        gameModel.clearAllHistory()
        rows = gameModel.historySummary()
    }

    ColumnLayout {
        anchors.fill: parent
        // Widgets QDialog layout margin (11px at the default font size).
        anchors.margins: Kirigami.Units.smallSpacing * 2
        spacing: Kirigami.Units.smallSpacing
        // Focus-chain quit (see MainPage): fires even where the
        // Shortcut map stays silent.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        RowLayout {
            objectName: "historyHeader"
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Controls.Label {
                Layout.fillWidth: true
                text: qsTr("Game")
                font.bold: true
            }
            Controls.Label {
                Layout.preferredWidth: historyView.colLast
                text: qsTr("Last played")
                font.bold: true
            }
            Controls.Label {
                Layout.preferredWidth: historyView.colRuns
                text: qsTr("Sessions")
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
            Controls.Label {
                Layout.preferredWidth: historyView.colTotal
                text: qsTr("Total time")
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
            Controls.Label {
                Layout.preferredWidth: historyView.colFails
                text: qsTr("Failures")
                font.bold: true
                horizontalAlignment: Text.AlignRight
            }
            // Spacer over the per-row Clear button.
            Item {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 3
            }
        }
        ListView {
            objectName: "historyRows"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: historyView.rows
            delegate: RowLayout {
                required property var modelData
                width: ListView.view ? ListView.view.width : 100
                Controls.Label {
                    objectName: "historyName"
                    Layout.fillWidth: true
                    text: modelData.name
                    elide: Text.ElideRight
                }
                Controls.Label {
                    Layout.preferredWidth: historyView.colLast
                    text: modelData.last
                    opacity: 0.7
                    elide: Text.ElideRight
                }
                Controls.Label {
                    objectName: "historyRuns"
                    Layout.preferredWidth: historyView.colRuns
                    text: modelData.runs ?? ""
                    horizontalAlignment: Text.AlignRight
                }
                Controls.Label {
                    Layout.preferredWidth: historyView.colTotal
                    text: modelData.total ?? ""
                    horizontalAlignment: Text.AlignRight
                }
                Controls.Label {
                    objectName: "historyFails"
                    Layout.preferredWidth: historyView.colFails
                    text: modelData.fails ?? ""
                    horizontalAlignment: Text.AlignRight
                }
                Controls.ToolButton {
                    objectName: "historyClear"
                    text: qsTr("Clear")
                    onClicked: {
                        gameModel.clearHistory(modelData.appid)
                        historyView.rows = gameModel.historySummary()
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "historyClearAll"
                text: qsTr("Clear History...")
                icon.name: "edit-delete"
                onClicked: clearAllDialog.open()
            }
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                text: qsTr("Close")
                onClicked: historyView.close()
            }
        }
    }

    KirigamiDialogs.PromptDialog {
        id: clearAllDialog
        objectName: "historyClearAllDialog"
        title: qsTr("Clear History")
        dialogType: KirigamiDialogs.PromptDialog.Warning
        subtitle: qsTr("Clear all session history? This cannot be undone.")
        customFooterActions: [
            Kirigami.Action {
                objectName: "historyClearAllConfirm"
                text: qsTr("Clear")
                icon.name: "edit-delete"
                onTriggered: {
                    historyView.clearAll()
                    clearAllDialog.close()
                }
            },
            Kirigami.Action {
                text: qsTr("Cancel")
                icon.name: "dialog-cancel"
                onTriggered: clearAllDialog.close()
            }
        ]
    }
}
