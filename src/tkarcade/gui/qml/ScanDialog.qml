import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Steam scan results: a separate modal window like the widgets QDialog
// (resizable, transient on the main window). `open()` keeps the old
// Dialog call sites working; `close()` is the native Window one.
Window {
    id: scanDialog
    objectName: "scanDialog"
    title: qsTr("Add Games")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 26
    minimumHeight: Kirigami.Units.gridUnit * 18
    width: Kirigami.Units.gridUnit * 32
    height: Kirigami.Units.gridUnit * 24
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var candidates: []
    property var picked: []
    property var page: null

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchQuitKeys(scanDialog)
        visible = true
    }

    onCandidatesChanged: {
        var all = []
        for (var i = 0; i < candidates.length; i++) {
            all.push(candidates[i][0])
        }
        picked = all
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
        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Steam games without a saved configuration:")
        }
        Controls.ScrollView {
            clip: true
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: scanDialog.candidates
                    Controls.CheckBox {
                        required property var modelData
                        text: modelData[1] + " [" + modelData[0] + "]"
                        checked: scanDialog.picked.indexOf(modelData[0]) >= 0
                        onToggled: {
                            var kept = []
                            for (var i = 0; i < scanDialog.picked.length; i++) {
                                if (scanDialog.picked[i] !== modelData[0]) {
                                    kept.push(scanDialog.picked[i])
                                }
                            }
                            if (checked) {
                                kept.push(modelData[0])
                            }
                            scanDialog.picked = kept
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
                objectName: "scanConfirm"
                text: qsTr("Add Selected")
                // QDialogButtonBox: Add Selected (accept) then Cancel.
                highlighted: true
                onClicked: {
                    var n = gameModel.addScanned(scanDialog.picked)
                    if (page !== null) {
                        page.notify(qsTr("Added %1 game(s).").arg(n))
                    }
                    scanDialog.close()
                }
            }
            Controls.Button {
                objectName: "scanCancel"
                text: qsTr("Cancel")
                onClicked: scanDialog.close()
            }
        }
    }
}
