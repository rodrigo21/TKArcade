import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.iconthemes as IconThemes

// One category: its icon (the theme icon picker, folder by default), the
// games that carry it, and the delete entry. OK applies both the icon and
// the checked games.
DialogWindow {
    id: editor
    title: qsTr("Edit Category")
    bodyFillHeight: true

    property string categoryName: ""
    property string iconName: "folder"
    property bool iconDirty: false
    property var rows: []

    function reload() {
        rows = gameModel.categoryGameRows(categoryName)
        var icons = gameModel.categoryIcons()
        iconName = icons[categoryName] || "folder"
        iconDirty = false
    }

    function checkedIds() {
        var ids = []
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].state === 2) {
                ids.push(rows[i].appid)
            }
        }
        return ids
    }

    onAccepted: {
        if (editor.iconDirty) {
            gameModel.setCategoryIcon(editor.categoryName, editor.iconName)
        }
        gameModel.setCategoryGames(editor.categoryName, editor.checkedIds())
        editor.close()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Controls.Button {
            objectName: "categoryIcon"
            icon.name: editor.iconName
            Controls.ToolTip.text: qsTr("Change Icon")
            Controls.ToolTip.visible: hovered
            onClicked: iconDialog.open()
        }
        Controls.Label {
            Layout.fillWidth: true
            text: editor.categoryName
            font.bold: true
            elide: Text.ElideRight
        }
    }
    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: qsTr("Check the Games That Belong to This Category.")
    }
    Controls.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: editor.rows.length > 0
        Layout.preferredHeight: Math.min(gameColumn.implicitHeight,
            Kirigami.Units.gridUnit * 14)
        clip: true
        Item {
            width: parent.width
            implicitHeight: gameColumn.implicitHeight
            ColumnLayout {
                id: gameColumn
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: editor.rows
                    delegate: Controls.CheckBox {
                        required property var modelData
                        required property int index
                        objectName: "categoryGame_" + modelData.appid
                        Layout.fillWidth: true
                        text: modelData.name
                        checkState: modelData.state === 2 ? Qt.Checked : Qt.Unchecked
                        // modelData is a copy of the row: write through the
                        // owner array or the check never reaches checkedIds().
                        onToggled: editor.rows[index].state = checked ? 2 : 0
                    }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Controls.Button {
            objectName: "categoryDelete"
            text: qsTr("Delete Category")
            icon.name: gameModel.iconName(["edit-delete-symbolic", "edit-delete"])
            onClicked: deleteConfirm.open(editor)
        }
        Item {
            Layout.fillWidth: true
        }
    }

    ConfirmDialog {
        id: deleteConfirm
        objectName: "categoryDeleteConfirm"
        title: qsTr("Delete Category")
        question: qsTr("Delete %1? It Is Removed From Every Game.").arg(editor.categoryName)
        acceptText: qsTr("Delete")
        onAccepted: {
            gameModel.deleteCategory(editor.categoryName)
            deleteConfirm.close()
            editor.close()
        }
    }

    IconThemes.IconDialog {
        id: iconDialog
        title: qsTr("Choose an Icon")
        iconSize: Kirigami.Units.iconSizes.large
        onIconNameChanged: {
            if (iconDialog.iconName !== "") {
                editor.iconName = iconDialog.iconName
                editor.iconDirty = true
            }
        }
    }
}
