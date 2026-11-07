import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Managed DXVK/vkd3d-proton versions: any release of the chosen source
// (official, a preset fork or a custom repository) and any pasted archive
// URL install here, a directory outside the managed root can be registered
// as an extra source, and old versions are deleted here. Per-game selection
// stays in Game Settings.
DialogWindow {
    id: manager
    title: manager.kind === "vkd3d" ? qsTr("vkd3d-proton Versions") : qsTr("DXVK Versions")
    width: Kirigami.Units.gridUnit * 36
    minimumWidth: Kirigami.Units.gridUnit * 32
    acceptVisible: false
    rejectText: qsTr("Close")
    bodyFillHeight: true

    property string kind: "dxvk"
    property var versions: []
    property var folders: []
    property var releases: []
    property string status: ""
    property string source: "official"
    property bool busy: false
    property bool loadingReleases: false
    property bool browsing: false
    property string pendingName: ""
    property string pendingFolder: ""

    // Presets per layer: id -> label. "custom" reveals the repo field.
    function sourceIds() {
        return manager.kind === "dxvk"
            ? ["official", "sarek", "gplasync", "custom"]
            : ["official", "custom"]
    }

    function sourceLabels() {
        return manager.kind === "dxvk"
            ? [qsTr("Official"), qsTr("DXVK-Sarek"),
               qsTr("DXVK-GPLAsync (Legacy)"), qsTr("Custom Repository")]
            : [qsTr("Official"), qsTr("Custom Repository")]
    }

    function applySource(index) {
        var ids = sourceIds()
        if (index < 0 || index >= ids.length) {
            return
        }
        var message = gameModel.setGraphicsSource(manager.kind, ids[index], repoField.text)
        if (message !== "") {
            manager.status = message
            return
        }
        manager.status = ""
        manager.reload()
        // A new source means a new release list.
        manager.releases = []
        releaseCombo.model = []
        manager.loadingReleases = true
        gameModel.fetchRuntimeReleases(manager.kind)
    }

    function sourceLabel(entry) {
        if (entry.origin === "system") {
            return qsTr("System Version")
        }
        if (entry.origin === "external") {
            return qsTr("External")
        }
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
                "url": raw[i].url,
                "external": raw[i].external === true,
                "default": raw[i].default === true
            })
        }
        versions = rows
        folders = gameModel.graphicsFolders(kind)
        var stored = gameModel.graphicsSource(kind)
        var sourcePart = stored.indexOf("custom:") === 0 ? "custom" : stored
        var ids = sourceIds()
        var at = ids.indexOf(sourcePart)
        source = ids[at >= 0 ? at : 0]
        sourceBox.currentIndex = at >= 0 ? at : 0
        repoField.text = stored.indexOf("custom:") === 0 ? stored.slice(7) : ""
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
        pendingFolder = ""
        status = ""
        busy = false
        browsing = false
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
        function onBrowseFinished(picked) {
            if (!manager.browsing) {
                return
            }
            manager.browsing = false
            if (picked !== "") {
                manager.status = gameModel.addGraphicsFolder(manager.kind, picked)
                manager.reload()
            }
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Download From:")
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Controls.ComboBox {
            id: sourceBox
            objectName: "runtimeSourceCombo"
            Layout.fillWidth: true
            model: manager.sourceLabels()
            onActivated: manager.applySource(currentIndex)
        }
        Controls.TextField {
            id: repoField
            objectName: "runtimeSourceRepo"
            Layout.fillWidth: true
            visible: manager.source === "custom"
            placeholderText: qsTr("owner/repo")
            Controls.ToolTip.text: qsTr("A GitHub Repository Whose Releases Provide This Layer.")
            Controls.ToolTip.visible: hovered
        }
        Controls.Button {
            objectName: "runtimeSourceApply"
            visible: manager.source === "custom"
            text: qsTr("Apply")
            enabled: repoField.text.trim() !== ""
            onClicked: manager.applySource(sourceBox.currentIndex)
        }
    }
    Controls.Label {
        objectName: "runtimeSourceWarning"
        Layout.fillWidth: true
        visible: manager.source === "gplasync"
        wrapMode: Text.WordWrap
        color: Kirigami.Theme.neutralTextColor
        text: qsTr("DXVK-GPLAsync Is Discontinued Upstream: Only Mirrors Remain, and Compatibility Is Not Guaranteed.")
    }
    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Installed Versions:")
    }
    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Kirigami.Theme.disabledTextColor
        text: qsTr("The Radio Marks the Version New Games Use and the One They Fall Back To. Delete Removes Only the Builds TKArcade Installed.")
    }
    Controls.Label {
        Layout.fillWidth: true
        visible: manager.versions.length === 0
        text: qsTr("No Version Is Installed.")
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
            // The vertical scroll bar overlays the viewport: reserve its
            // width so the rightmost button stays clickable.
            width: parent.width - Kirigami.Units.smallSpacing * 3
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
                        Controls.RadioButton {
                            objectName: "runtimeDefault_" + modelData.name
                            Layout.alignment: Qt.AlignTop
                            checked: modelData.default
                            onClicked: {
                                manager.status = gameModel.setGraphicsDefault(
                                    manager.kind, modelData.name)
                                manager.reload()
                            }
                            Controls.ToolTip.text: qsTr("Use This Version by Default")
                            Controls.ToolTip.visible: hovered
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Controls.Label {
                                Layout.fillWidth: true
                                text: modelData.name
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Controls.Label {
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                                color: Kirigami.Theme.disabledTextColor
                                text: modelData.repo !== ""
                                    ? qsTr("%1 · %2").arg(manager.sourceLabel(modelData)).arg(modelData.repo)
                                    : manager.sourceLabel(modelData)
                            }
                        }
                        Controls.Button {
                            objectName: "runtimeRemove_" + modelData.name
                            visible: !modelData.external
                            Layout.alignment: Qt.AlignTop
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
    Controls.Label {
        Layout.fillWidth: true
        text: qsTr("Extra Folders:")
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        Controls.Label {
            Layout.fillWidth: true
            visible: manager.folders.length === 0
            text: qsTr("None: Add a Directory Holding Versions TKArcade Did Not Install.")
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
        }
        Controls.Button {
            objectName: "runtimeAddFolder"
            text: qsTr("Add Folder…")
            onClicked: {
                manager.browsing = true
                gameModel.pickDir(qsTr("Versions Folder"), qsTr("Select"))
            }
        }
    }
    Repeater {
        model: manager.folders
        delegate: RowLayout {
            required property string modelData
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            Controls.Label {
                Layout.fillWidth: true
                text: modelData
                elide: Text.ElideMiddle
                color: Kirigami.Theme.disabledTextColor
                Controls.ToolTip.text: modelData
                Controls.ToolTip.visible: hovered
            }
            Controls.Button {
                objectName: "runtimeFolderRemove_" + modelData
                text: qsTr("Remove")
                onClicked: {
                    manager.pendingFolder = modelData
                    folderDialog.open(manager)
                }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
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

    ConfirmDialog {
        id: folderDialog
        title: qsTr("Remove Versions Folder")
        question: qsTr("Stop Using %1?").arg(manager.pendingFolder)
        warning: qsTr("The Files Stay on Disk.")
        acceptText: qsTr("Remove")
        onAccepted: {
            manager.status = gameModel.removeGraphicsFolder(manager.kind, manager.pendingFolder)
            manager.reload()
            folderDialog.close()
        }
    }
}
