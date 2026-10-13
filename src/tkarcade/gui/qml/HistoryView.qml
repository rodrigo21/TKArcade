import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

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

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchQuitKeys(historyView)
        visible = true
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
                    text: modelData.last
                    opacity: 0.7
                }
                Controls.Label {
                    text: modelData.total
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
                text: qsTr("Close")
                onClicked: historyView.close()
            }
        }
    }
}
