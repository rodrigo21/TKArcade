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
        gameModel.watchDialogKeys(historyView)
        visible = true
    }

    function clearAll() {
        gameModel.clearAllHistory()
        rows = gameModel.historySummary()
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
            gameModel.pressDefault(historyView, ["historyClose"])
        }
        // Same scheme as the games table header: button-set background,
        // bold titles and a hairline closing the bar.
        Item {
            objectName: "historyHeader"
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2
            Kirigami.Theme.colorSet: Kirigami.Theme.Button
            Kirigami.Theme.inherit: false
            Rectangle {
                objectName: "historyHeaderBar"
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }
            RowLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    id: gameHeader
                    Layout.fillWidth: true
                    text: qsTr("Game")
                    font.bold: true
                    color: Kirigami.Theme.textColor
                }
                Controls.Label {
                    id: lastHeader
                    Layout.preferredWidth: historyView.colLast
                    text: qsTr("Last Played")
                    font.bold: true
                    color: Kirigami.Theme.textColor
                }
                Controls.Label {
                    id: runsHeader
                    Layout.preferredWidth: historyView.colRuns
                    text: qsTr("Sessions")
                    font.bold: true
                    horizontalAlignment: Text.AlignRight
                    color: Kirigami.Theme.textColor
                }
                Controls.Label {
                    id: totalHeader
                    Layout.preferredWidth: historyView.colTotal
                    text: qsTr("Total Time")
                    font.bold: true
                    horizontalAlignment: Text.AlignRight
                    color: Kirigami.Theme.textColor
                }
                Controls.Label {
                    id: failsHeader
                    Layout.preferredWidth: historyView.colFails
                    text: qsTr("Failures")
                    font.bold: true
                    horizontalAlignment: Text.AlignRight
                    color: Kirigami.Theme.textColor
                }
                // Spacer over the per-row Clear button.
                Item {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 3
                }
            }
            // Cell rules, like the games table header. The labels are
            // laid out by the RowLayout, so the rules follow their right
            // edges instead of consuming width.
            Item {
                anchors.fill: parent
                Rectangle {
                    objectName: "historyHeaderSep"
                    x: gameHeader.x + gameHeader.width
                    width: 1
                    height: parent.height
                    color: Kirigami.Theme.textColor
                    opacity: 0.18
                }
                Rectangle {
                    objectName: "historyHeaderSep"
                    x: lastHeader.x + lastHeader.width
                    width: 1
                    height: parent.height
                    color: Kirigami.Theme.textColor
                    opacity: 0.18
                }
                Rectangle {
                    objectName: "historyHeaderSep"
                    x: runsHeader.x + runsHeader.width
                    width: 1
                    height: parent.height
                    color: Kirigami.Theme.textColor
                    opacity: 0.18
                }
                Rectangle {
                    objectName: "historyHeaderSep"
                    x: totalHeader.x + totalHeader.width
                    width: 1
                    height: parent.height
                    color: Kirigami.Theme.textColor
                    opacity: 0.18
                }
                Rectangle {
                    objectName: "historyHeaderSep"
                    x: failsHeader.x + failsHeader.width
                    width: 1
                    height: parent.height
                    color: Kirigami.Theme.textColor
                    opacity: 0.18
                }
            }
            Rectangle {
                objectName: "historyHeaderBottomLine"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Kirigami.Theme.textColor
                opacity: 0.18
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
                spacing: Kirigami.Units.smallSpacing
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
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 3
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
                objectName: "historyClose"
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
        subtitle: qsTr("Clear All Session History? This Cannot Be Undone.")
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
