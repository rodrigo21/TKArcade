import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Every category on record with its icon and game count. Categories
// outlive their game tags, so rows with a (0) count stay listed here
// until deleted through the editor.
DialogWindow {
    id: manager
    title: qsTr("Edit Categories")
    acceptVisible: false
    rejectText: qsTr("Close")
    bodyFillHeight: true

    property var rows: []

    signal editRequested(string name)

    function reload() {
        var cats = gameModel.allCategories()
        var counts = gameModel.categoryCounts()
        var icons = gameModel.categoryIcons()
        var out = []
        for (var i = 0; i < cats.length; i++) {
            out.push({
                "name": cats[i],
                "icon": icons[cats[i]] || "folder",
                "count": counts[cats[i]] || 0
            })
        }
        rows = out
    }

    onVisibleChanged: if (visible) manager.reload()

    Connections {
        target: gameModel
        function onRefreshed() {
            if (manager.visible) {
                manager.reload()
            }
        }
    }

    Controls.ScrollView {
        objectName: "categoryManagerList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: manager.rows.length > 0
        Layout.preferredHeight: Math.min(list.implicitHeight,
            Kirigami.Units.gridUnit * 16)
        clip: true
        Item {
            width: parent.width
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
                        Kirigami.Icon {
                            source: modelData.icon
                            implicitWidth: Kirigami.Units.iconSizes.smallMedium
                            implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        }
                        Controls.Label {
                            Layout.fillWidth: true
                            text: qsTr("%1 (%2)").arg(modelData.name).arg(modelData.count)
                            elide: Text.ElideRight
                        }
                        Controls.Button {
                            objectName: "categoryEdit_" + modelData.name
                            text: qsTr("Edit")
                            onClicked: manager.editRequested(modelData.name)
                        }
                    }
                }
            }
        }
    }
}
