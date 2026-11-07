import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Wine builds stay where the system keeps them: this dialog only holds the
// list and one default. Per-game selection stays in Game Settings, and the
// PATH entry is always first and cannot be removed.
DialogWindow {
    id: manager
    title: qsTr("Wine Versions")
    // The width follows the widest row, so a path is never wrapped; the cap
    // only exists for a path longer than the screen.
    width: Math.max(minimumWidth, Math.min(preferredWidth, Kirigami.Units.gridUnit * 90))
    minimumWidth: Kirigami.Units.gridUnit * 32
    acceptVisible: false
    rejectText: qsTr("Close")

    // Raised after a successful change so Preferences keeps its values fresh.
    signal listChanged()

    property var rows: []
    // The name column is as wide as the longest label in the list, so every
    // path starts at the same x without a fixed, distant column.
    property real nameColumn: Kirigami.Units.gridUnit * 8
    property real preferredWidth: Kirigami.Units.gridUnit * 36
    property string status: ""
    property string pendingName: ""
    property bool browsing: false

    function measure(text) {
        nameMeasure.text = text
        return nameMeasure.advanceWidth
    }

    function measurePath(text) {
        pathMeasure.text = text
        return pathMeasure.advanceWidth
    }

    function detail(modelData) {
        return (modelData.ok
            ? (modelData.version !== "" ? modelData.version : qsTr("No Version Reported"))
            : qsTr("Not Found")) + " · " + modelData.path
    }

    function reload() {
        var raw = gameModel.wineVersionRows()
        var out = []
        var widest = 0
        var widestPath = 0
        for (var i = 0; i < raw.length; i++) {
            out.push({
                "name": raw[i].name,
                "path": raw[i].path,
                "version": raw[i].version,
                "ok": raw[i].ok,
                "default": raw[i].default
            })
            var label = raw[i].name === "" ? qsTr("Wine From PATH") : raw[i].name
            widest = Math.max(widest, measure(label))
            widestPath = Math.max(widestPath, measurePath(detail(out[i])))
        }
        nameColumn = Math.min(widest + Kirigami.Units.smallSpacing * 2 + 8,
                              Kirigami.Units.gridUnit * 16)
        preferredWidth = radioSizer.implicitWidth + Kirigami.Units.smallSpacing
            + nameColumn + Kirigami.Units.smallSpacing + widestPath
            + Kirigami.Units.smallSpacing + removeSizer.implicitWidth
            + Kirigami.Units.smallSpacing * 3 * 2 + Kirigami.Units.smallSpacing * 3
        rows = out
    }

    TextMetrics {
        id: nameMeasure
        font: Kirigami.Theme.defaultFont
    }

    TextMetrics {
        id: pathMeasure
        font: Kirigami.Theme.defaultFont
    }

    // Invisible sizers: the row width the window must accommodate.
    Controls.RadioButton {
        id: radioSizer
        visible: false
    }

    Controls.Button {
        id: removeSizer
        visible: false
        text: qsTr("Remove")
    }

    function after(message) {
        if (message !== "") {
            status = message
            return
        }
        status = ""
        reload()
        listChanged()
    }

    function openFor(parentWindow) {
        status = ""
        browsing = false
        reload()
        open(parentWindow)
    }

    Connections {
        target: gameModel
        function onBrowseFinished(picked) {
            if (!manager.browsing) {
                return
            }
            manager.browsing = false
            if (picked !== "") {
                manager.after(gameModel.addWineVersion(picked))
            }
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Installed Builds:")
    }
    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Kirigami.Theme.disabledTextColor
        text: qsTr("The Radio Marks the Build New Games Use and the One They Fall Back To. The First Row Is Always the Wine From PATH.")
    }
    Controls.ScrollView {
        objectName: "wineVersionList"
        Layout.fillWidth: true
        Layout.minimumHeight: 0
        Layout.preferredHeight: Math.min(list.implicitHeight, Kirigami.Units.gridUnit * 10)
        clip: true
        Item {
            // The vertical scroll bar overlays the viewport: reserve its
            // width so the rightmost button stays clickable.
            width: parent.width - Kirigami.Units.smallSpacing * 3
            implicitHeight: list.implicitHeight
            ColumnLayout {
                id: list
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: manager.rows
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Controls.RadioButton {
                            id: defaultChoice
                            objectName: "wineDefaultChoice_" + (modelData.name === "" ? "path" : modelData.name)
                            checked: modelData.default
                            onClicked: manager.after(gameModel.setWineDefault(modelData.name))
                            Controls.ToolTip.text: qsTr("Use This Build by Default")
                            Controls.ToolTip.visible: hovered
                        }
                        Controls.TextField {
                            objectName: "wineVersionName_" + modelData.name
                            Layout.preferredWidth: manager.nameColumn
                            visible: modelData.name !== ""
                            text: modelData.name
                            onEditingFinished: {
                                if (text !== modelData.name) {
                                    manager.after(
                                        gameModel.renameWineVersion(modelData.name, text))
                                }
                            }
                        }
                        Controls.Label {
                            visible: modelData.name === ""
                            Layout.preferredWidth: manager.nameColumn
                            elide: Text.ElideRight
                            font.bold: true
                            text: qsTr("Wine From PATH")
                        }
                        Controls.Label {
                            Layout.fillWidth: true
                            // One line, never wrapped: the window is sized to
                            // fit it. Elision is only the last resort past the
                            // width cap.
                            elide: Text.ElideMiddle
                            color: Kirigami.Theme.disabledTextColor
                            text: manager.detail(modelData)
                            Controls.ToolTip.text: modelData.path
                            Controls.ToolTip.visible: hovered
                        }
                        Controls.Button {
                            objectName: "wineVersionRemove_" + modelData.name
                            visible: modelData.name !== ""
                            text: qsTr("Remove")
                            onClicked: {
                                manager.pendingName = modelData.name
                                removeDialog.open(manager)
                            }
                        }
                    }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Controls.Button {
            objectName: "wineVersionAdd"
            text: qsTr("Add Wine Binary…")
            onClicked: {
                manager.browsing = true
                gameModel.pickPath(qsTr("Wine Binary"), qsTr("Select"))
            }
        }
        Item {
            Layout.fillWidth: true
        }
    }
    Controls.Label {
        objectName: "wineManagerStatus"
        Layout.fillWidth: true
        visible: text !== ""
        text: manager.status
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
    }

    ConfirmDialog {
        id: removeDialog
        title: qsTr("Remove Wine Build")
        question: qsTr("Remove %1 From the List?").arg(manager.pendingName)
        warning: qsTr("The Build Stays on Disk; Games That Select It Warn at Launch.")
        acceptText: qsTr("Remove")
        onAccepted: {
            manager.after(gameModel.removeWineVersion(manager.pendingName))
            removeDialog.close()
        }
    }
}
