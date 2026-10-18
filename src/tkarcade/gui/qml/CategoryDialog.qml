import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Category filter: single-select radio list (All + every tag in use).
// Opened from the drawer; the choice lands on gameFilter.categoryKey.
Kirigami.Dialog {
    id: categoryDialog
    objectName: "categoryDialog"
    title: qsTr("Filter by Category")
    padding: Kirigami.Units.largeSpacing

    property var catModel: []

    function openDialog() {
        var fresh = [""]
        var cats = gameModel.allCategories()
        for (var i = 0; i < cats.length; i++) {
            fresh.push(cats[i])
        }
        catModel = fresh
        categoryDialog.open()
    }

    ColumnLayout {
        Controls.ButtonGroup {
            id: catGroup
        }
        Repeater {
            model: categoryDialog.catModel
            delegate: Controls.RadioButton {
                required property string modelData
                property string cat: modelData
                objectName: "catRadio_" + (cat === "" ? "all" : cat)
                text: cat === "" ? qsTr("All Categories") : cat
                checked: gameFilter.categoryKey === cat
                Controls.ButtonGroup.group: catGroup
                onToggled: {
                    if (checked) {
                        gameFilter.categoryKey = cat
                        categoryDialog.close()
                    }
                }
            }
        }
    }
    footer: RowLayout {
        Layout.fillWidth: true
        Item {
            Layout.fillWidth: true
        }
        Controls.Button {
            objectName: "categoryClose"
            text: qsTr("Close")
            onClicked: categoryDialog.close()
        }
    }
}
