import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Download Metadata for a library selection: one row per selected game,
// resolved off the GUI thread. The worker only reads configs and the
// providers; Apply is the only writer. A searched match is checked by
// default only when its title is the game's own, so a near miss waits
// for the user's look at the row.
DialogWindow {
    id: batch
    objectName: "bulkMetadataDialog"
    title: qsTr("Download Metadata")
    width: Kirigami.Units.gridUnit * 40
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 20
    height: Kirigami.Units.gridUnit * 30
    bodyFillHeight: true
    acceptText: qsTr("Apply")
    acceptEnabled: batch.checkedCount > 0
    rejectText: qsTr("Close")

    // Source for games without an identity; a stored identity always wins
    // for the others. Re-read on every open, because it follows the IGDB
    // credentials from Preferences.
    property string source: "steam"
    property bool busy: false
    property int total: 0
    property int resolved: 0
    property int checkedCount: 0
    property string status: ""
    property var ids: []

    // The message of the finished Apply, for the page's status line.
    signal applied(string message)

    function reset(gameIds) {
        ids = gameIds.slice()
        total = ids.length
        resolved = 0
        checkedCount = 0
        busy = false
        status = ""
        source = gameModel.igdbConfigured() ? "igdb" : "steam"
        sourceBox.currentIndex = sourceBox.ids.indexOf(source)
        rowModel.clear()
        var names = gameModel.gameNames(ids)
        for (var i = 0; i < ids.length; i++) {
            rowModel.append({
                "gid": ids[i],
                "gameName": names[i],
                "picked": false,
                "phase": "pending",
                "provider": "",
                "target": "",
                "matchName": "",
                "fieldText": "",
                "searched": false,
                "exact": false
            })
        }
    }

    function start() {
        if (busy || ids.length === 0) {
            return
        }
        if (source === "igdb" && !gameModel.igdbConfigured()) {
            status = qsTr("Set the IGDB Client ID and Secret in Preferences → Artwork → API Keys.")
            return
        }
        busy = true
        resolved = 0
        checkedCount = 0
        status = qsTr("Looking Up…")
        for (var i = 0; i < rowModel.count; i++) {
            rowModel.setProperty(i, "picked", false)
            rowModel.setProperty(i, "phase", "pending")
            rowModel.setProperty(i, "provider", "")
            rowModel.setProperty(i, "target", "")
            rowModel.setProperty(i, "matchName", "")
            rowModel.setProperty(i, "fieldText", "")
            rowModel.setProperty(i, "searched", false)
            rowModel.setProperty(i, "exact", false)
        }
        gameModel.resolveMetadataBatch(ids, source)
    }

    function apply() {
        // Apply stops the worker first: the rest of the selection keeps a
        // pending row and is not written.
        if (busy) {
            gameModel.cancelMetadataBatch()
        }
        var entries = []
        for (var i = 0; i < rowModel.count; i++) {
            var row = rowModel.get(i)
            if (row.picked && row.phase === "ok") {
                entries.push({
                    "id": row.gid,
                    "provider": row.provider,
                    "target": row.target,
                    "searched": row.searched
                })
            }
        }
        if (entries.length === 0) {
            status = qsTr("Check at Least One Resolved Game.")
            return
        }
        var message = gameModel.applyMetadataBatch(entries)
        batch.close()
        batch.applied(message)
    }

    function refreshChecked() {
        var count = 0
        for (var i = 0; i < rowModel.count; i++) {
            if (rowModel.get(i).picked && rowModel.get(i).phase === "ok") {
                count++
            }
        }
        checkedCount = count
    }

    function providerLabel(provider) {
        if (provider === "vndb") {
            return "VNDB"
        }
        if (provider === "igdb") {
            return "IGDB"
        }
        return "Steam"
    }

    function rowDetail(row) {
        if (row.phase === "pending") {
            return qsTr("Not Resolved")
        }
        if (row.phase === "no-match") {
            return qsTr("No Match Found")
        }
        if (row.phase === "no-data") {
            return qsTr("No Metadata Found")
        }
        if (row.phase === "failed") {
            return qsTr("Failed")
        }
        if (row.phase === "empty") {
            return qsTr("Nothing to Fill")
        }
        var parts = [providerLabel(row.provider)]
        if (row.matchName !== "") {
            parts.push(row.matchName)
        }
        if (row.fieldText !== "") {
            parts.push(row.fieldText)
        }
        return parts.join(" · ")
    }

    onVisibleChanged: {
        if (!visible) {
            gameModel.cancelMetadataBatch()
        }
    }

    onAccepted: batch.apply()

    leadingActions: Controls.Button {
        objectName: "bulkMetadataFind"
        text: qsTr("Find Matches")
        enabled: !batch.busy
        onClicked: batch.start()
    }

    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: qsTr("Check the games to fill. Empty fields take the provider answer; locked fields stay; tags and age ratings fill only when the game has none.")
    }
    RowLayout {
        Layout.fillWidth: true
        Controls.Label {
            text: qsTr("Source:")
        }
        AppComboBox {
            id: sourceBox
            objectName: "bulkMetadataSource"
            Layout.fillWidth: true
            readonly property var ids: ["steam", "vndb", "igdb"]
            model: [
                { "text": qsTr("Steam"), "data": "steam" },
                { "text": qsTr("VNDB"), "data": "vndb" },
                { "text": qsTr("IGDB"), "data": "igdb" }
            ]
            textRole: "text"
            valueRole: "data"
            enabled: !batch.busy
            onActivated: batch.source = currentValue
            Controls.ToolTip.text: qsTr("Provider for Games Without an Identity. A Stored Steam, VNDB or IGDB ID Always Wins.")
            Controls.ToolTip.visible: hovered
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: batch.busy || batch.resolved < batch.total || batch.status !== ""
        Controls.ProgressBar {
            Layout.fillWidth: true
            from: 0
            to: Math.max(1, batch.total)
            value: batch.resolved
        }
        Controls.Label {
            text: qsTr("%1 / %2").arg(batch.resolved).arg(batch.total)
        }
    }
    Controls.Label {
        Layout.fillWidth: true
        visible: batch.status !== ""
        wrapMode: Text.WordWrap
        text: batch.status
    }
    ListView {
        id: list
        objectName: "bulkMetadataList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        clip: true
        spacing: Kirigami.Units.smallSpacing
        model: ListModel {
            id: rowModel
        }
        delegate: ColumnLayout {
            id: rowItem
            required property int index
            required property string gid
            required property string gameName
            required property bool picked
            required property string phase
            required property string provider
            required property string matchName
            required property string fieldText
            width: list.width
            spacing: 0
            Controls.CheckBox {
                Layout.fillWidth: true
                objectName: "bulkMetadataCheck_" + rowItem.gid
                text: rowItem.gameName
                enabled: rowItem.phase === "ok" && !batch.busy
                checked: rowItem.picked
                onToggled: {
                    rowModel.setProperty(rowItem.index, "picked", checked)
                    batch.refreshChecked()
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.gridUnit + Kirigami.Units.smallSpacing
                text: batch.rowDetail(rowItem)
                elide: Text.ElideRight
                opacity: rowItem.phase === "ok" ? 1.0 : 0.6
                Controls.ToolTip.text: rowItem.fieldText
                Controls.ToolTip.visible: hovered && rowItem.fieldText !== ""
            }
        }
    }

    Connections {
        target: gameModel
        function onMetadataBatchRow(index) {
            var row = gameModel.batchMetadataRow(index)
            if (index < 0 || index >= rowModel.count) {
                return
            }
            if (rowModel.get(index).gid !== row.id) {
                return
            }
            rowModel.setProperty(index, "provider", row.provider || "")
            rowModel.setProperty(index, "target", row.target || "")
            rowModel.setProperty(index, "matchName", row.match || "")
            rowModel.setProperty(index, "fieldText", row.fields || "")
            rowModel.setProperty(index, "searched", row.searched === true)
            rowModel.setProperty(index, "exact", row.exact === true)
            rowModel.setProperty(index, "phase", row.state || "failed")
            rowModel.setProperty(index, "picked",
                row.state === "ok" && (!row.searched || row.exact === true))
            batch.resolved += 1
            batch.refreshChecked()
        }
        function onMetadataBatchFinished(total) {
            if (!batch.busy) {
                return
            }
            batch.busy = false
            if (batch.resolved < batch.total) {
                batch.status = qsTr("Stopped After %1 of %2.").arg(batch.resolved).arg(batch.total)
            } else {
                batch.status = ""
            }
        }
    }
}
