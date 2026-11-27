import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Game picker for `--edit` without an AppID (widgets QInputDialog parity:
// labels as "name [appid]", Cancel reports the empty AppID).
Window {
    id: picker
    objectName: "editorPicker"
    title: qsTr("Edit Game")
    modality: Qt.WindowModal
    minimumWidth: Kirigami.Units.gridUnit * 22
    width: Kirigami.Units.gridUnit * 26
    // The Game list drives the height (capped at ten rows); the picker
    // has no large window to host an overlay, so the list itself is the
    // content instead of a combo popup clipped to this window.
    height: pickLayout.implicitHeight + pickLayout.anchors.margins * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    // [[appid, name]] from the model; turned into fresh JS arrays here
    // (labels + appids) because a list handed in from Python indexes
    // fine but must not become a model as-is.
    property var games: []
    property var appids: []
    property var labels: []
    property bool reported: false

    signal finished(string appid)

    function openIt() {
        var labels = []
        appids = []
        for (var i = 0; i < games.length; i++) {
            labels.push(games[i][1] + " [" + games[i][0] + "]")
            appids.push(String(games[i][0]))
        }
        picker.labels = labels
        pickBox.currentIndex = 0
        pickOk.enabled = labels.length > 0
        gameModel.watchDialogKeys(picker)
        visible = true
        requestActivate()
    }

    function report(appid) {
        if (reported) {
            return
        }
        reported = true
        visible = false
        finished(appid)
    }

    onClosing: function (close) {
        report("")
    }

    ColumnLayout {
        id: pickLayout
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        focus: true
        // Enter hits the default button like the widgets QDialog (an open
        // popup's accept first, else ours); a focused TextArea keeps Return.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(picker, ["editorPickOk"])
        }
        Controls.Label {
            text: qsTr("Game:")
            Layout.fillWidth: true
        }
        ListView {
            id: pickBox
            objectName: "editorPickBox"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, Kirigami.Units.gridUnit * 10)
            clip: true
            model: picker.labels
            currentIndex: 0
            Controls.ScrollBar.vertical: Controls.ScrollBar {}
            delegate: Controls.RadioDelegate {
                width: ListView.view.width
                text: String(modelData || "")
                checked: ListView.isCurrentItem
                onClicked: pickBox.currentIndex = index
            }
        }
        Item {
            Layout.fillHeight: true
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                id: pickOk
                objectName: "editorPickOk"
                text: qsTr("OK")
                highlighted: true
                onClicked: picker.report(appids[pickBox.currentIndex] || "")
            }
            Controls.Button {
                objectName: "editorPickCancel"
                text: qsTr("Cancel")
                onClicked: picker.report("")
            }
        }
    }
}
