import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Grouped age-rating checklist, shared by the game dialog. The groups
// come from config.AGE_RATING_GROUPS through gameModel.ageRatingGroups(),
// so the picker and the loader never drift apart. The flat row list keeps
// one Repeater: a nested Repeater inside a delegate did not instantiate
// its checkboxes in this Qt. Secondary boards sit behind one collapsible
// row at the end; an existing selection there is preserved but stays
// hidden until the section is expanded.
DialogWindow {
    id: picker
    title: qsTr("Age Ratings")
    acceptText: qsTr("OK")
    bodyFillHeight: true
    // Show every primary board when the screen has room; otherwise the
    // list scrolls inside the usable work area.
    maximumHeight: Screen.availableHeight > 0 ? Screen.availableHeight
        : (Screen.height > 0 ? Screen.height : 16777215)

    property var groups: []
    property var rows: []
    property var selected: []
    property bool showOthers: false
    signal picked(var ratings)

    onGroupsChanged: picker.rebuild()
    Component.onCompleted: picker.rebuild()

    function groupRows(group, secondary) {
        var rows = [{"header": true, "secondary": secondary,
                     "text": group.name, "rating": ""}]
        var ratings = group.ratings || []
        for (var i = 0; i < ratings.length; i++) {
            rows.push({"header": false, "secondary": secondary,
                       "text": ratings[i], "rating": ratings[i]})
        }
        return rows
    }

    function rebuild() {
        var primary = []
        var secondary = []
        for (var i = 0; i < groups.length; i++) {
            // The model returns the groups alphabetically; keep that order
            // in both sections.
            var target = groups[i]["default"] ? primary : secondary
            var rows = picker.groupRows(groups[i], !groups[i]["default"])
            for (var j = 0; j < rows.length; j++) {
                target.push(rows[j])
            }
        }
        primary.push({"separator": true, "header": false, "secondary": false,
                      "text": "", "rating": ""})
        primary.push({"toggle": true, "header": false, "secondary": false,
                      "text": "", "rating": ""})
        // Fresh array: the Repeater only updates when the model changes.
        picker.rows = primary.concat(secondary)
    }

    function toggle(rating, on) {
        var next = picker.selected.slice()
        var index = next.indexOf(rating)
        if (on && index < 0) {
            next.push(rating)
        } else if (!on && index >= 0) {
            next.splice(index, 1)
        }
        picker.selected = next
    }

    onAccepted: {
        picker.picked(picker.selected.slice())
        picker.close()
    }

    Controls.ScrollView {
        objectName: "ageRatingsScroll"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        Layout.preferredHeight: rowsColumn.implicitHeight
        Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AlwaysOn
        clip: true
        Item {
            width: parent.width
            implicitHeight: rowsColumn.implicitHeight
            ColumnLayout {
                id: rowsColumn
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: picker.rows
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        visible: modelData.separator === true
                            || modelData.toggle === true
                            || !modelData.secondary || picker.showOthers
                        Rectangle {
                            objectName: "ageRatingsSeparator"
                            Layout.fillWidth: true
                            Layout.topMargin: Kirigami.Units.smallSpacing
                            visible: modelData.separator === true
                            height: 1
                            color: Kirigami.Theme.disabledTextColor
                        }
                        Controls.Switch {
                            objectName: modelData.toggle === true ? "ageRatingsShowOthers" : ""
                            Layout.fillWidth: true
                            Layout.topMargin: Kirigami.Units.smallSpacing
                            visible: modelData.toggle === true
                            text: qsTr("Other Rating Boards")
                            checked: picker.showOthers
                            onToggled: picker.showOthers = checked
                        }
                        Controls.Label {
                            Layout.fillWidth: true
                            visible: modelData.header === true
                                && modelData.toggle !== true
                                && modelData.separator !== true
                            font.bold: true
                            text: visible ? modelData.text : ""
                        }
                        Controls.CheckBox {
                            objectName: modelData.header === true
                                || modelData.toggle === true
                                || modelData.separator === true ? ""
                                : "ageRatingPick_"
                                    + modelData.rating.replace(/[^A-Za-z0-9]+/g, "_")
                            Layout.fillWidth: true
                            visible: modelData.header !== true
                                && modelData.toggle !== true
                                && modelData.separator !== true
                            text: modelData.text
                            checked: picker.selected.indexOf(modelData.rating) >= 0
                            onToggled: {
                                if (visible) {
                                    picker.toggle(modelData.rating, checked)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
