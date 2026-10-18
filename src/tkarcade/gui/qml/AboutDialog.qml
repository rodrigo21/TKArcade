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
    // QMessageBox wraps the text at its size hint instead of a wide box.
    minimumWidth: Kirigami.Units.gridUnit * 22
    minimumHeight: Kirigami.Units.gridUnit * 14
    width: Kirigami.Units.gridUnit * 24
    height: body.implicitHeight + Kirigami.Units.largeSpacing * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchQuitKeys(aboutDialog)
        visible = true
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing
        // Focus-chain quit (see MainPage): fires even where the
        // Shortcut map stays silent.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
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
                // QMessageBox widens its buttons beyond the short label.
                Layout.minimumWidth: Kirigami.Units.gridUnit * 5
                highlighted: true
                onClicked: aboutDialog.close()
            }
        }
    }
}
