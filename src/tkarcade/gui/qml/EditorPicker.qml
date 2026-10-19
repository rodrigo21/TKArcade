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
    height: Kirigami.Units.gridUnit * 8
    visible: false
    color: Kirigami.Theme.backgroundColor

    // [[appid, name]] from the model; turned into fresh JS arrays here
    // (labels + appids) because a list handed in from Python indexes
    // fine but must not become a model as-is.
    property var games: []
    property var appids: []
    property bool reported: false

    signal finished(string appid)

    function openIt() {
        var labels = []
        appids = []
        for (var i = 0; i < games.length; i++) {
            labels.push(games[i][1] + " [" + games[i][0] + "]")
            appids.push(String(games[i][0]))
        }
        pickBox.model = labels
        pickBox.currentIndex = 0
        pickOk.enabled = labels.length > 0
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
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        Controls.Label {
            text: qsTr("Game:")
            Layout.fillWidth: true
        }
        Controls.ComboBox {
            id: pickBox
            objectName: "editorPickBox"
            Layout.fillWidth: true
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
