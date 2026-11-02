import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// The checkable category list with a free-form field for new ones, shared
// by the library's Set Categories action and the GameSettings picker.
// Rows are {name, state}: 2 checked, 1 partially (some selected games
// carry it), 0 unchecked. On OK the names with state > 0 plus the typed
// ones go to `picked`; the caller decides where they land.
DialogWindow {
    id: picker
    title: qsTr("Categories")
    acceptText: qsTr("OK")
    bodyFillHeight: true

    property var catRows: []
    property alias newCategories: newField.text
    property string hint: ""
    // Set by addTyped(); the list scrolls once the layout pass has given
    // the column its final height.
    property bool revealPending: false
    signal picked(var names)

    onVisibleChanged: {
        if (!visible) {
            revealPending = false
        }
    }

    onAccepted: {
        var names = []
        for (var i = 0; i < picker.catRows.length; i++) {
            if (picker.catRows[i].state > 0) {
                names.push(picker.catRows[i].name)
            }
        }
        var extra = picker.newCategories.split(",")
        for (var j = 0; j < extra.length; j++) {
            var name = extra[j].trim()
            if (name !== "") {
                names.push(name)
            }
        }
        picker.picked(names)
        picker.close()
    }

    function addTyped() {
        var typed = String(newField.text || "").split(",")
        // Fresh array: the Repeater only updates when the model is
        // reassigned (docs/QML-NOTES.md).
        var rows = picker.catRows.slice()
        for (var i = 0; i < typed.length; i++) {
            var name = typed[i].trim()
            if (name === "") {
                continue
            }
            var found = -1
            for (var j = 0; j < rows.length; j++) {
                if (String(rows[j].name).toLowerCase() === name.toLowerCase()) {
                    found = j
                    break
                }
            }
            // A match keeps the casing the category already uses.
            if (found >= 0) {
                rows[found] = {"name": rows[found].name, "state": 2}
            } else {
                rows.push({"name": name, "state": 2})
            }
        }
        picker.catRows = rows
        newField.text = ""
        newField.forceActiveFocus()
        picker.revealPending = true
    }

    Controls.Label {
        Layout.fillWidth: true
        visible: picker.hint !== ""
        wrapMode: Text.WordWrap
        text: picker.hint
    }
    Controls.ScrollView {
        id: catScroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: picker.catRows.length > 0
        Layout.preferredHeight: Math.min(catColumn.implicitHeight,
            Kirigami.Units.gridUnit * 12)
        clip: true
        Item {
            width: parent.width
            implicitHeight: catColumn.implicitHeight
            ColumnLayout {
                id: catColumn
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: picker.catRows
                    delegate: Controls.CheckBox {
                        required property var modelData
                        required property int index
                        objectName: "categoryPick_" + modelData.name
                        Layout.fillWidth: true
                        text: modelData.name
                        checkState: modelData.state === 2 ? Qt.Checked
                            : (modelData.state === 1 ? Qt.PartiallyChecked : Qt.Unchecked)
                        // modelData is a copy of the row: writing it left the
                        // array untouched and unchecking never removed the
                        // category. Write through the owner array instead.
                        onToggled: picker.catRows[index].state = checked ? 2 : 0
                    }
                }
            }
        }
    }
    Connections {
        target: catScroll.contentItem
        function onContentHeightChanged() {
            if (!picker.revealPending) {
                return
            }
            picker.revealPending = false
            var flick = catScroll.contentItem
            flick.contentY = Math.max(0, flick.contentHeight - flick.height)
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Controls.TextField {
            id: newField
            placeholderText: qsTr("New Categories (Comma Separated)")
            Layout.fillWidth: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            onAccepted: picker.accepted()
        }
        Controls.Button {
            objectName: "categoryAdd"
            text: qsTr("Add")
            enabled: newField.text.trim() !== ""
            onClicked: picker.addTyped()
        }
    }
}
