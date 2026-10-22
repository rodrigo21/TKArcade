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
    // Widgets QMessageBox.about: information icon beside the text, one
    // right-aligned default button, and the box hugging its content
    // instead of filling a fixed rectangle.
    // QMessageBox wraps the text at its size hint instead of a wide box
    // (r240: 400x263). The height stays content driven: a QMessageBox
    // reserves an icon column and a wider label minimum, not more
    // padding (its layout margin is the same 10px).
    minimumWidth: Kirigami.Units.gridUnit * 20
    minimumHeight: Kirigami.Units.gridUnit * 14
    width: Kirigami.Units.gridUnit * 22
    height: body.implicitHeight + body.anchors.margins * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(aboutDialog)
        visible = true
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        // Widgets QMessageBox layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.largeSpacing
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
            gameModel.pressDefault(aboutDialog, ["aboutOk"])
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Kirigami.Icon {
                objectName: "aboutIcon"
                // QStyle.SP_MessageBoxInformation (QMessageBox.about).
                source: gameModel.iconName(["dialog-information", "help-about"])
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: Kirigami.Units.iconSizes.large
                Layout.preferredHeight: Kirigami.Units.iconSizes.large
            }
            Kirigami.SelectableLabel {
                objectName: "aboutText"
                Layout.fillWidth: true
                Layout.fillHeight: true
                wrapMode: Text.WordWrap
                text: gameModel.aboutText()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "aboutOk"
                text: qsTr("OK")
                // No extra minimum: the QQC2 style already widens a
                // short label the way QMessageBox does (80px there).
                highlighted: true
                onClicked: aboutDialog.close()
            }
        }
    }
}
