import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Managed DXVK/vkd3d-proton versions: any release of the official repo (or
// the configured fork) and any pasted archive URL install here, and old
// versions are deleted here. Per-game selection stays in Game Settings.
DialogWindow {
    id: manager
    title: manager.kind === "vkd3d" ? qsTr("vkd3d-proton Versions") : qsTr("DXVK Versions")
    width: Kirigami.Units.gridUnit * 32
    minimumWidth: Kirigami.Units.gridUnit * 30
    acceptVisible: false
    rejectText: qsTr("Close")
    bodyFillHeight: true

    property string kind: "dxvk"
    property var versions: []
    property var releases: []
    property string status: ""
    property bool busy: false
    property bool loadingReleases: false
    property string pendingName: ""

    function sourceLabel(entry) {
        if (entry.origin === "github") {
            return qsTr("Official Release")
        }
        if (entry.origin === "repo") {
            return qsTr("Fork: %1").arg(entry.repo)
        }
        if (entry.origin === "url") {
            return qsTr("From URL")
        }
        return qsTr("Unknown Source")
    }

    // Rows stay fresh JS arrays: a QVariantList from Python lays out at
    // zero width on Qt 6.11 (docs/QML-NOTES.md).
    function reload() {
        var raw = gameModel.runtimeVersions(kind)
        var rows = []
        for (var i = 0; i < raw.length; i++) {
            rows.push({
                "name": raw[i].name,
                "origin": raw[i].origin,
                "repo": raw[i].repo,
                "tag": raw[i].tag,
                "url": raw[i].url
            })
        }
        versions = rows
    }

    function setReleases(rows) {
        var assets = []
        var labels = []
        for (var i = 0; i < rows.length; i++) {
            assets.push({
                "tag": rows[i].tag,
                "name": rows[i].name,
                "url": rows[i].url,
                "size": rows[i].size,
                "digest": rows[i].digest
            })
            labels.push(
                rows[i].prerelease
                    ? qsTr("%1 (Pre-Release)").arg(rows[i].tag)
                    : rows[i].tag)
        }
        releases = assets
        releaseCombo.model = labels
        releaseCombo.currentIndex = labels.length > 0 ? 0 : -1
    }

    function openFor(parentWindow, layer) {
        kind = layer
        pendingName = ""
        status = ""
        busy = false
        loadingReleases = true
        releases = []
        releaseCombo.model = []
        reload()
        open(parentWindow)
        gameModel.fetchRuntimeReleases(layer)
    }

    Connections {
        target: gameModel
        function onArchivesChanged() {
            manager.reload()
        }
        function onRuntimeReleases(kind, rows, message) {
            if (kind !== manager.kind) {
                return
            }
            manager.loadingReleases = false
            manager.setReleases(rows)
            if (message !== "") {
                manager.status = message
            }
        }
        function onArchiveProgress(kind, message) {
            if (kind !== manager.kind) {
                return
            }
            manager.busy = true
            manager.status = message
        }
        function onArchiveFinished(kind, message) {
            if (kind !== manager.kind) {
                return
            }
            manager.busy = false
            manager.status = message === "" ? qsTr("Installed.") : message
            manager.reload()
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Installed Versions:")
    }
    Controls.Label {
        Layout.fillWidth: true
        visible: manager.versions.length === 0
        text: qsTr("No Managed Version Is Installed.")
        color: Kirigami.Theme.disabledTextColor
    }
    Controls.ScrollView {
        objectName: "runtimeVersionList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 0
        visible: manager.versions.length > 0
        Layout.preferredHeight: Math.min(list.implicitHeight, Kirigami.Units.gridUnit * 10)
        clip: true
        Item {
            width: parent.width
            implicitHeight: list.implicitHeight
            ColumnLayout {
                id: list
                width: parent.width
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    model: manager.versions
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        Controls.Label {
                            Layout.fillWidth: true
                            text: modelData.name
                            font.bold: true
                            elide: Text.ElideRight
                        }
                        Controls.Label {
                            text: manager.sourceLabel(modelData)
                            color: Kirigami.Theme.disabledTextColor
                            elide: Text.ElideRight
                        }
                        Controls.Button {
                            objectName: "runtimeRemove_" + modelData.name
                            text: qsTr("Delete")
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
            objectName: "runtimeRefreshReleases"
            text: qsTr("Download Release…")
            enabled: !manager.busy && !manager.loadingReleases
            onClicked: {
                manager.loadingReleases = true
                manager.status = ""
                gameModel.fetchRuntimeReleases(manager.kind)
            }
        }
        Controls.BusyIndicator {
            running: manager.loadingReleases || manager.busy
            visible: running
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: Kirigami.Units.iconSizes.small
        }
        Controls.ComboBox {
            id: releaseCombo
            objectName: "runtimeReleaseCombo"
            Layout.fillWidth: true
            enabled: !manager.busy && count > 0
            // The desktop style paints the closed field from displayText
            // with the native style and does not elide it, so shorten the
            // string here. A custom contentItem drew a second copy of the
            // same text on top of it (doubled glyphs, docs/QML-NOTES.md).
            displayText: releaseElide.elidedText
            TextMetrics {
                id: releaseElide
                font: releaseCombo.font
                elide: Text.ElideRight
                // Arrow room: the style draws it inside the field.
                elideWidth: Math.max(0, releaseCombo.width - 2 * releaseCombo.leftPadding
                                     - Kirigami.Units.gridUnit)
                text: releaseCombo.currentIndex >= 0 ? releaseCombo.textAt(releaseCombo.currentIndex) : ""
            }
            Controls.ToolTip.text: releaseCombo.currentIndex >= 0 ? releaseCombo.currentText : ""
            Controls.ToolTip.visible: hovered && text !== ""
        }
        Controls.Button {
            objectName: "runtimeInstallRelease"
            text: qsTr("Install")
            enabled: !manager.busy && releaseCombo.currentIndex >= 0
            onClicked: gameModel.installRuntimeRelease(
                manager.kind, manager.releases[releaseCombo.currentIndex])
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Controls.TextField {
            id: urlField
            objectName: "runtimeUrlField"
            Layout.fillWidth: true
            placeholderText: qsTr("Archive URL (.tar.gz, .tar.zst or .zip)")
            enabled: !manager.busy
        }
        Controls.Button {
            objectName: "runtimeInstallUrl"
            text: qsTr("Install From URL…")
            enabled: !manager.busy && urlField.text.trim() !== ""
            onClicked: gameModel.installRuntimeFromUrl(manager.kind, urlField.text)
        }
    }
    Controls.Label {
        objectName: "runtimeManagerStatus"
        Layout.fillWidth: true
        visible: text !== ""
        text: manager.status
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
    }

    ConfirmDialog {
        id: removeDialog
        title: qsTr("Delete Runtime Version")
        question: qsTr("Delete %1?").arg(manager.pendingName)
        warning: qsTr("Games That Select This Version Will Warn at Launch.")
        acceptText: qsTr("Delete")
        onAccepted: {
            var message = gameModel.removeRuntimeVersion(manager.kind, manager.pendingName)
            if (message !== "") {
                manager.status = message
            }
            removeDialog.close()
        }
    }
}
