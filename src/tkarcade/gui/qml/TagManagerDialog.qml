import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// The global tag store: rename a tag (an existing name merges into it),
// delete one (also strips it from every game that carries it) or prune
// the names no game uses. Tags never reach the sidebar, so this dialog
// is their only maintenance point besides the picker's new-name field.
DialogWindow {
    id: manager
    objectName: "tagManager"
    title: qsTr("Manage Tags")
    acceptVisible: false
    rejectText: qsTr("Close")
    bodyFillHeight: true

    property var rows: []
    // Canonical casing of the row being renamed or deleted.
    property string target: ""
    property string message: ""
    // The initial width follows the longest row, because a tag is user
    // data and the default 24 grid units elides it. The cap is half the
    // screen, so a long name widens the window but never floods it.
    readonly property real maximumContentWidth:
        Screen.availableWidth > 0 ? Screen.availableWidth * 0.5 : Kirigami.Units.gridUnit * 60
    readonly property real chromeWidth: Kirigami.Units.gridUnit + Kirigami.Units.smallSpacing * 6
    width: Math.min(manager.maximumContentWidth,
        Math.max(manager.minimumWidth, list.implicitWidth + manager.chromeWidth))
    // Room for a few rows on open, less scrolling for a large store.
    minimumHeight: Kirigami.Units.gridUnit * 18

    // Emitted after a successful model action, so an open picker can
    // rebuild its rows without losing the checks in progress.
    signal changed()
    // The settings dialog holds a draft of the game's tags: a rename or
    // delete on disk must reach that draft too, or Save writes the old
    // name back.
    signal renamed(string from, string to)
    signal deleted(string name)

    function reload() {
        var tags = gameModel.allTags()
        var counts = gameModel.tagCounts()
        var out = []
        for (var i = 0; i < tags.length; i++) {
            out.push({"name": tags[i], "count": counts[tags[i]] || 0})
        }
        rows = out
    }

    function hasUnused() {
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].count === 0) {
                return true
            }
        }
        return false
    }

    onVisibleChanged: {
        if (visible) {
            message = ""
            manager.reload()
        }
    }

    Connections {
        target: gameModel
        function onRefreshed() {
            if (manager.visible) {
                manager.reload()
            }
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        visible: manager.message !== ""
        wrapMode: Text.WordWrap
        text: manager.message
    }
    Controls.ScrollView {
        objectName: "tagManagerList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: manager.rows.length > 0
        Layout.preferredHeight: Math.min(list.implicitHeight,
            Kirigami.Units.gridUnit * 24)
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
                        Controls.Label {
                            Layout.fillWidth: true
                            objectName: "tagManagerName_" + modelData.name
                            text: qsTr("%1 (%2)").arg(modelData.name).arg(modelData.count)
                            elide: Text.ElideRight
                        }
                        Controls.Button {
                            objectName: "tagRename_" + modelData.name
                            text: qsTr("Rename")
                            onClicked: {
                                manager.target = modelData.name
                                renameField.text = modelData.name
                                renameDialog.open(manager)
                            }
                        }
                        Controls.Button {
                            objectName: "tagDelete_" + modelData.name
                            text: qsTr("Delete")
                            onClicked: {
                                manager.target = modelData.name
                                deleteConfirm.question = modelData.count > 0
                                    ? qsTr("Delete %1 and Remove It from %2 Game(s)?").arg(
                                        modelData.name).arg(modelData.count)
                                    : qsTr("Delete %1?").arg(modelData.name)
                                deleteConfirm.open(manager)
                            }
                        }
                    }
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Controls.Label {
            Layout.fillWidth: true
            visible: manager.rows.length === 0
            wrapMode: Text.WordWrap
            text: qsTr("No Tags")
        }
        Controls.Button {
            objectName: "tagPrune"
            text: qsTr("Prune Unused")
            enabled: manager.hasUnused()
            onClicked: {
                manager.message = gameModel.pruneTags()
                manager.changed()
            }
        }
    }

    // Windows cannot be ColumnLayout children: this zero-size holder
    // keeps the two prompts out of the body layout.
    Item {
        DialogWindow {
            id: renameDialog
            objectName: "tagRenameDialog"
            title: qsTr("Rename Tag")
            width: Kirigami.Units.gridUnit * 24
            Controls.TextField {
                id: renameField
                objectName: "tagRenameField"
                Layout.fillWidth: true
                onAccepted: renameDialog.accepted()
            }
            onAccepted: {
                var from = manager.target
                var typed = renameField.text.trim()
                manager.message = gameModel.renameTag(from, typed)
                if (manager.message.indexOf("Renamed") === 0
                        || manager.message.indexOf("Merged") === 0) {
                    // The store carries the canonical casing (a merge keeps
                    // the existing name's).
                    var target = typed
                    var tags = gameModel.allTags()
                    for (var i = 0; i < tags.length; i++) {
                        if (tags[i].toLowerCase() === typed.toLowerCase()) {
                            target = tags[i]
                        }
                    }
                    manager.renamed(from, target)
                }
                manager.changed()
                renameDialog.close()
            }
        }
        ConfirmDialog {
            id: deleteConfirm
            objectName: "tagDeleteConfirm"
            acceptText: qsTr("Delete")
            onAccepted: {
                var target = manager.target
                manager.message = gameModel.deleteTag(target)
                if (manager.message.indexOf("Deleted") === 0) {
                    manager.deleted(target)
                }
                manager.changed()
                deleteConfirm.close()
            }
        }
    }
}
