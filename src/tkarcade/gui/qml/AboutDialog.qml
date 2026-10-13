import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// About: a separate modal window like the widgets dialog
// (resizable, transient on the main window). `open()` keeps the
// call sites working; `close()` is the native Window one.
Window {
    id: aboutDialog
    objectName: "aboutDialog"
    title: qsTr("About TKArcade")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 28
    minimumHeight: Kirigami.Units.gridUnit * 16
    width: Kirigami.Units.gridUnit * 34
    height: Kirigami.Units.gridUnit * 20
    visible: false
    color: Kirigami.Theme.backgroundColor

    function open() {
        transientParent = Controls.ApplicationWindow.window
        visible = true
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing
        Kirigami.SelectableLabel {
            objectName: "aboutText"
            Layout.fillWidth: true
            Layout.fillHeight: true
            wrapMode: Text.WordWrap
            text: gameModel.aboutText()
        }
        RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Close")
                onClicked: aboutDialog.close()
            }
        }
    }
}
