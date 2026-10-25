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
    // Widgets _ScanDialog hugged its table (278x268 for two entries):
    // the window follows the checkbox list and scrolls once the list
    // would grow past the cap.
    readonly property real scanListCap: Kirigami.Units.gridUnit * 20
    // Width follows the widest "name [appid]" so nothing is clipped; the
    // inner column may exceed the viewport, which gives the ScrollView a
    // horizontal bar once the screen cap kicks in.
    readonly property real screenCap: screen ? screen.width * 0.9
                                             : Kirigami.Units.gridUnit * 80
    FontMetrics {
        id: scanMetrics
        font: Kirigami.Theme.defaultFont
    }
    function labelFor(row) {
        return row[1] + " [" + row[0] + "]"
    }
    function contentWidth() {
        var widest = 0
        for (var i = 0; i < candidates.length; i++) {
            widest = Math.max(widest, scanMetrics.advanceWidth(labelFor(candidates[i])))
        }
        // Check indicator, check padding and the scroll bar.
        return widest + Kirigami.Units.gridUnit * 3
    }
    minimumWidth: Kirigami.Units.gridUnit * 18
    minimumHeight: Kirigami.Units.gridUnit * 10
    width: Math.min(
        screenCap, Math.max(minimumWidth, contentWidth() + body.anchors.margins * 2))
    height: Math.max(
        minimumHeight,
        scanHeader.implicitHeight + Math.min(scanListCap, scanList.implicitHeight)
            + scanFooter.implicitHeight
            + body.spacing * 2 + body.anchors.margins * 2)
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var candidates: []
    property var picked: []
    property var page: null

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(scanDialog)
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
        id: body
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
            gameModel.pressDefault(scanDialog, ["scanConfirm"])
        }
        Controls.Label {
            id: scanHeader
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Steam Games without a Saved Configuration:")
        }
        Controls.ScrollView {
            clip: true
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                id: scanList
                width: Math.max(parent.width, implicitWidth)
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: scanDialog.candidates
                    Controls.CheckBox {
                        required property var modelData
                        text: scanDialog.labelFor(modelData)
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
            id: scanFooter
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
                        page.notify(qsTr("Added %1 Game(s).").arg(n))
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
