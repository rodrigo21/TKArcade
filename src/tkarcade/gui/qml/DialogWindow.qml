import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// A separate modal window for the shell's input and report dialogs: the
// caller's body fills the content area, the footer carries the buttons
// (QDialogButtonBox order). Escape closes through watchDialogKeys, like
// ConfirmDialog.qml, whose shape this shares without the icon column.
Window {
    id: dialogWindow
    objectName: "dialogWindow"
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 20
    width: Kirigami.Units.gridUnit * 24
    // The height follows the content, so the box hugs its body.
    height: body.implicitHeight + body.anchors.margins * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    property string acceptText: qsTr("OK")
    property bool acceptVisible: true
    property string rejectText: qsTr("Cancel")
    property bool rejectVisible: true
    default property alias content: extraColumn.data

    signal accepted()

    function open(parentWindow) {
        transientParent = parentWindow
        gameModel.watchDialogKeys(dialogWindow)
        visible = true
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.smallSpacing
        focus: true
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        // Enter hits the default button like the widgets QDialog; a body
        // with its own default action keeps Return.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(dialogWindow, ["dialogOk"])
        }
        ColumnLayout {
            id: extraColumn
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "dialogOk"
                visible: dialogWindow.acceptVisible
                text: dialogWindow.acceptText
                highlighted: true
                onClicked: dialogWindow.accepted()
            }
            Controls.Button {
                objectName: "dialogCancel"
                visible: dialogWindow.rejectVisible
                text: dialogWindow.rejectText
                onClicked: dialogWindow.close()
            }
        }
    }
}
