import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Discovered Proton builds: TKArcade never installs one, so the list is
// read-only and the button opens ProtonPlus (or ProtonUp-Qt) instead.
DialogWindow {
    id: manager
    title: qsTr("Proton Versions")
    // The width follows the widest row, so a path is never wrapped; the cap
    // only exists for a path longer than the screen.
    width: Math.max(minimumWidth, Math.min(preferredWidth, Kirigami.Units.gridUnit * 90))
    minimumWidth: Kirigami.Units.gridUnit * 32
    acceptVisible: false
    rejectText: qsTr("Close")

    signal listChanged()

    property var rows: []
    // As wide as the longest build name: one x for every path.
    property real nameColumn: Kirigami.Units.gridUnit * 10
    property real preferredWidth: Kirigami.Units.gridUnit * 36
    property string status: ""

    function measure(text) {
        nameMeasure.text = text
        return nameMeasure.advanceWidth
    }

    function measurePath(text) {
        pathMeasure.text = text
        return pathMeasure.advanceWidth
    }

    function reload() {
        var raw = gameModel.protonVersionRows()
        var out = []
        var widest = 0
        var widestPath = 0
        for (var i = 0; i < raw.length; i++) {
            out.push({
                "name": raw[i].name,
                "path": raw[i].path,
                "default": raw[i].default
            })
            widest = Math.max(widest, measure(raw[i].name))
            widestPath = Math.max(widestPath, measurePath(raw[i].path))
        }
        nameColumn = Math.min(widest + Kirigami.Units.smallSpacing * 2 + 8,
                              Kirigami.Units.gridUnit * 18)
        preferredWidth = radioSizer.implicitWidth + Kirigami.Units.smallSpacing
            + nameColumn + Kirigami.Units.smallSpacing + widestPath
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

    Controls.RadioButton {
        id: radioSizer
        visible: false
    }

    function openFor(parentWindow) {
        status = ""
        reload()
        open(parentWindow)
    }

    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Installed Builds:")
    }
    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Kirigami.Theme.disabledTextColor
        text: qsTr("The Radio Marks the Build Local Games Preselect. Steam Games Keep Steam's Own Choice.")
    }
    Controls.Label {
        Layout.fillWidth: true
        visible: manager.rows.length === 0
        text: qsTr("No Proton Install Found.")
        color: Kirigami.Theme.disabledTextColor
    }
    Controls.ScrollView {
        objectName: "protonVersionList"
        Layout.fillWidth: true
        Layout.minimumHeight: 0
        visible: manager.rows.length > 0
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
                            objectName: "protonDefaultChoice_" + modelData.name
                            checked: modelData.default
                            onClicked: {
                                var message = gameModel.setProtonDefault(modelData.name)
                                if (message !== "") {
                                    manager.status = message
                                    return
                                }
                                manager.status = ""
                                manager.reload()
                                manager.listChanged()
                            }
                            Controls.ToolTip.text: qsTr("Use This Build by Default")
                            Controls.ToolTip.visible: hovered
                        }
                        Controls.Label {
                            Layout.preferredWidth: manager.nameColumn
                            elide: Text.ElideRight
                            font.bold: true
                            text: modelData.name
                        }
                        Controls.Label {
                            Layout.fillWidth: true
                            // One line, never wrapped: the window is sized to
                            // fit it. Elision is only the last resort past the
                            // width cap.
                            elide: Text.ElideMiddle
                            color: Kirigami.Theme.disabledTextColor
                            text: modelData.path
                            Controls.ToolTip.text: modelData.path
                            Controls.ToolTip.visible: hovered
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
            objectName: "protonOpenManager"
            text: qsTr("Open Proton Manager")
            onClicked: {
                var message = gameModel.openProtonManager()
                manager.status = message
            }
        }
        Item {
            Layout.fillWidth: true
        }
    }
    Controls.Label {
        objectName: "protonManagerStatus"
        Layout.fillWidth: true
        visible: text !== ""
        text: manager.status
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
    }
}
