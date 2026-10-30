import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Every confirmation of the settings window: a separate modal window on it,
// the widgets QMessageBox shape (information column on the left, one
// right-aligned default button, the box hugging its content). A long detail
// (a path, a note about unsaved edits) gets its own wrapping block: inside a
// single label it dictated the box width and ran into the border.
Window {
    id: confirmDialog
    objectName: "settingsConfirm"
    modality: Qt.WindowModal
    // A floor for narrowing; the height follows the content, so a
    // compositor that honors a taller minimum would pad the box with air.
    minimumWidth: Kirigami.Units.gridUnit * 20
    width: Kirigami.Units.gridUnit * 22
    height: body.implicitHeight + body.anchors.margins * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    // `title` is the Window one; the caller names the purpose.
    property string question: ""
    property string detail: ""
    property string warning: ""
    // QStyle.SP_MessageBoxWarning unless the caller asks for something softer.
    property bool softIcon: false
    property string acceptText: qsTr("OK")
    // The unsaved-changes prompt keeps its edits with a third button.
    property bool saveVisible: false

    signal accepted()
    signal saved()

    function open(parentWindow) {
        // Modal on the settings window it was opened from (the standalone
        // editor has no parent window, so WindowModal stays application-wide).
        transientParent = parentWindow
        gameModel.watchDialogKeys(confirmDialog)
        visible = true
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        // Widgets QMessageBox layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.largeSpacing
        // Ctrl+Q quits the shell from any dialog (see MainPage).
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        focus: true
        // Enter hits the default button like the widgets QMessageBox.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(confirmDialog, ["settingsConfirmOk"])
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                objectName: "settingsConfirmIcon"
                source: confirmDialog.softIcon
                    ? gameModel.iconName(["dialog-information", "help-about"])
                    : gameModel.iconName(["dialog-warning", "dialog-information"])
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: Kirigami.Units.iconSizes.large
                Layout.preferredHeight: Kirigami.Units.iconSizes.large
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing * 2
                Controls.Label {
                    objectName: "settingsConfirmQuestion"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: confirmDialog.question
                }
                Kirigami.SelectableLabel {
                    objectName: "settingsConfirmDetail"
                    visible: text !== ""
                    Layout.fillWidth: true
                    // Paths carry no spaces: WordWrap alone cannot break a
                    // long folder name.
                    wrapMode: Text.WrapAnywhere
                    color: Kirigami.Theme.neutralTextColor
                    text: confirmDialog.detail
                }
                Controls.Label {
                    objectName: "settingsConfirmWarning"
                    visible: text !== ""
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Kirigami.Theme.negativeTextColor
                    text: confirmDialog.warning
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "settingsConfirmSave"
                visible: confirmDialog.saveVisible
                text: qsTr("Save")
                onClicked: confirmDialog.saved()
            }
            Controls.Button {
                objectName: "settingsConfirmOk"
                text: confirmDialog.acceptText
                highlighted: true
                onClicked: confirmDialog.accepted()
            }
            Controls.Button {
                objectName: "settingsConfirmCancel"
                text: qsTr("Cancel")
                onClicked: confirmDialog.close()
            }
        }
    }
}
