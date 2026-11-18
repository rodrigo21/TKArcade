import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// The checkable name list with a free-form field for new ones, shared by
// the library's Set Categories action, the GameSettings category picker
// and the game's tag picker.
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
    property string newPlaceholder: qsTr("New Categories (Comma Separated)")
    // Namespaced object names keep the two pickers apart in tests.
    property string rowPrefix: "categoryPick_"
    property string addObjectName: "categoryAdd"
    // A long tag list reads better in two columns; a category list stays
    // one column, and the capped height keeps the footer reachable.
    property int columns: 1
    property real listHeight: Kirigami.Units.gridUnit * 12
    // Opt-in for the tag picker: fit the window to the longest row, and
    // drop to one column rather than squeeze a tag onto a second line.
    property bool fitContent: false
    // Opt-in filter field for a store that outgrew one screen. It hides
    // rows only: `catRows` keeps every state, so OK still returns the
    // names checked before the filter was typed.
    property bool searchable: false
    property string filterPlaceholder: qsTr("Filter Names")
    property string filterObjectName: "categoryFilter"
    property alias filterText: filterField.text
    // The optional maintenance action on the footer's left edge (the tag
    // picker opens the manager; the category pickers leave it empty).
    property string manageText: ""
    property string manageObjectName: "categoryManage"
    signal manageRequested()
    property real maximumContentWidth: Math.min(
        Kirigami.Units.gridUnit * 60,
        Screen.availableWidth > 0 ? Screen.availableWidth * 0.8 : Kirigami.Units.gridUnit * 60)
    // Set by addTyped(); the list scrolls once the layout pass has given
    // the column its final height.
    property bool revealPending: false
    signal picked(var names)

    FontMetrics {
        id: nameMetrics
        font: Kirigami.Theme.defaultFont
    }

    readonly property real widestName: {
        var widest = 0
        for (var i = 0; i < picker.catRows.length; i++) {
            widest = Math.max(widest,
                nameMetrics.advanceWidth(String(picker.catRows[i].name || "")))
        }
        return widest
    }
    // Checkbox indicator, spacing and the row's own padding.
    readonly property real rowWidth: widestName + Kirigami.Units.gridUnit * 2
    // Body margins and the scroll bar.
    readonly property real bodyWidth: Kirigami.Units.gridUnit + Kirigami.Units.smallSpacing * 6
    readonly property int fittedColumns: {
        if (!picker.fitContent) {
            return picker.columns
        }
        var two = picker.rowWidth * 2 + Kirigami.Units.smallSpacing + picker.bodyWidth
        return two <= picker.maximumContentWidth ? 2 : 1
    }
    readonly property real fittedWidth: {
        if (!picker.fitContent) {
            return Kirigami.Units.gridUnit * 24
        }
        var needed = picker.rowWidth * picker.fittedColumns
            + Kirigami.Units.smallSpacing * (picker.fittedColumns - 1)
            + picker.bodyWidth
        return Math.min(picker.maximumContentWidth,
            Math.max(picker.minimumWidth, needed))
    }

    width: picker.fittedWidth

    leadingActions: Controls.Button {
        objectName: picker.manageObjectName
        visible: picker.manageText !== ""
        text: picker.manageText
        onClicked: picker.manageRequested()
    }

    onVisibleChanged: {
        if (visible) {
            filterText = ""
        } else {
            revealPending = false
        }
    }

    function nameMatches(name) {
        var query = String(filterText).trim().toLowerCase()
        return query === "" || String(name || "").toLowerCase().indexOf(query) >= 0
    }

    readonly property int matchedRows: {
        var count = 0
        for (var i = 0; i < picker.catRows.length; i++) {
            if (picker.nameMatches(picker.catRows[i].name)) {
                count++
            }
        }
        return count
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
    Controls.TextField {
        id: filterField
        objectName: picker.filterObjectName
        visible: picker.searchable
        Layout.fillWidth: true
        placeholderText: picker.filterPlaceholder
    }
    Controls.Label {
        Layout.fillWidth: true
        visible: picker.searchable && picker.filterText.trim() !== ""
            && picker.matchedRows === 0
        opacity: 0.7
        text: qsTr("No Matching Name.")
    }
    Controls.ScrollView {
        id: catScroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: picker.catRows.length > 0
        Layout.preferredHeight: Math.min(catColumn.implicitHeight, picker.listHeight)
        clip: true
        Item {
            width: parent.width
            implicitHeight: catColumn.implicitHeight
            GridLayout {
                id: catColumn
                width: parent.width
                columns: picker.fittedColumns
                columnSpacing: Kirigami.Units.smallSpacing
                rowSpacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: picker.catRows
                    delegate: Controls.CheckBox {
                        required property var modelData
                        required property int index
                        objectName: picker.rowPrefix + modelData.name
                        visible: !picker.searchable || picker.nameMatches(modelData.name)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
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
            placeholderText: picker.newPlaceholder
            Layout.fillWidth: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            onAccepted: picker.accepted()
        }
        Controls.Button {
            objectName: picker.addObjectName
            text: qsTr("Add")
            enabled: newField.text.trim() !== ""
            onClicked: picker.addTyped()
        }
    }
}
