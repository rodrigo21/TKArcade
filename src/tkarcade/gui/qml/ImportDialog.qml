import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Import configurations (tarball / SteamTinkerLaunch / predecessor /
// Lutris / Faugus): one modal window like the widgets flows (resizable,
// transient on the main window). `open()` keeps the call sites working.
Window {
    id: importDialog
    objectName: "importDialog"
    title: qsTr("Import Configurations")
    modality: Qt.WindowModal
    // Widgets flows: a 373x101 chooser plus a 520x380 STL dialog. This
    // is one window with a source row, so the height follows the pages
    // and the list scrolls past the cap.
    readonly property real importListCap: Kirigami.Units.gridUnit * 22
    // The height follows the page on screen: a StackLayout reports its
    // tallest child, so the tarball page would stay as tall as an STL
    // list loaded earlier until the window is reopened.
    readonly property real pageHeight: importDialog.source === 0
        ? tarballPage.implicitHeight
        : importDialog.source === 1
            ? stlPage.implicitHeight
            : importDialog.source === 2
                ? predPage.implicitHeight
                : libraryPage.implicitHeight
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 10
    width: Kirigami.Units.gridUnit * 36
    height: Math.max(
        minimumHeight,
        sourceRow.implicitHeight + Math.min(importListCap, pageHeight)
            + importFooter.implicitHeight
            + body.spacing * 2 + body.anchors.margins * 2)
    visible: false
    color: Kirigami.Theme.backgroundColor

    property int source: 0 // 0 tarball, 1 STL, 2 predecessor, 3 foreign library
    property var stlRows: []
    property var stlPicked: []
    property var libraryRows: []
    property var libraryPicked: []
    property string libraryHint: ""
    property string libraryName: ""
    property string librarySource: ""
    property bool libraryLoading: false
    property string tarballPath: ""
    property string pickPurpose: ""
    property var page: null

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(importDialog)
        visible = true
    }

    function openLibrary(kind) {
        libraryRows = []
        libraryPicked = []
        libraryHint = ""
        libraryName = kind === "lutris" ? qsTr("Lutris") : qsTr("Faugus")
        librarySource = kind
        libraryLoading = true
        source = 3
        open()
        gameModel.startLibraryCandidates(kind)
    }

    function applyLibraryData(data) {
        var rows = data.rows || []
        var fresh = []
        var picked = []
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            fresh.push([row[0], row[1], row[2], row[3], row[4]])
            if (row[3] === "new") {
                picked.push(row[0])
            }
        }
        libraryRows = fresh
        libraryPicked = picked
        libraryHint = data.hint || ""
        libraryLoading = false
    }

    function openStl() {
        // Fresh JS array (never hand a QVariantList to the Repeater).
        var rows = gameModel.stlCandidates()
        var fresh = []
        for (var i = 0; i < rows.length; i++) {
            fresh.push([rows[i][0], rows[i][1]])
        }
        stlRows = fresh
        var all = []
        for (var j = 0; j < fresh.length; j++) {
            all.push(fresh[j][0])
        }
        stlPicked = all
        source = 1
        open()
    }

    function notify(text) {
        if (page !== null) {
            page.notify(text)
        }
    }

    Connections {
        target: gameModel
        function onBrowseFinished(picked) {
            if (picked === "" || importDialog.pickPurpose === "") {
                return
            }
            importDialog.pickPurpose = ""
            importDialog.tarballPath = picked
        }
        function onLibraryCandidatesReady(source, data) {
            if (source !== importDialog.librarySource) {
                importDialog.libraryLoading = false
                return
            }
            importDialog.applyLibraryData(data)
        }
        function onLibraryImportFinished(report) {
            importDialog.libraryLoading = false
            gameModel.refresh()
            if (report !== "") {
                importDialog.notify(report)
                importDialog.close()
            }
        }
    }

    ColumnLayout {
        id: body
        anchors.fill: parent
        // Widgets QDialog layout margin: 12px (Breeze uses 10).
        anchors.margins: Kirigami.Units.smallSpacing * 3
        spacing: Kirigami.Units.smallSpacing
        // Focus-chain quit (see MainPage): fires even where the
        // Shortcut map stays silent.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
                event.accepted = true
                Qt.quit()
            }
        }
        focus: true
        // Enter hits the default button like the widgets QDialog (an open
        // popup's accept first, else ours); a focused TextArea keeps Return.
        Keys.onReturnPressed: (event) => {
            event.accepted = true
            gameModel.pressDefault(
                importDialog,
                ["importTarballConfirm", "importStlConfirm", "importPredecessorConfirm",
                 "importLibraryConfirm"]
            )
        }
        Flow {
            id: sourceRow
            objectName: "importSourceRow"
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            Controls.Button {
                text: qsTr("Backup File…")
                onClicked: importDialog.source = 0
            }
            Controls.Button {
                objectName: "importSourceStl"
                text: qsTr("SteamTinkerLaunch…")
                onClicked: importDialog.openStl()
            }
            Controls.Button {
                text: qsTr("TKSteamLaunch…")
                onClicked: importDialog.source = 2
            }
            Controls.Button {
                objectName: "importSourceLutris"
                text: qsTr("Lutris…")
                enabled: !importDialog.libraryLoading
                onClicked: importDialog.openLibrary("lutris")
            }
            Controls.Button {
                objectName: "importSourceFaugus"
                text: qsTr("Faugus…")
                enabled: !importDialog.libraryLoading
                onClicked: importDialog.openLibrary("faugus")
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: importDialog.source
            ColumnLayout {
                id: tarballPage
                spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: qsTr("A Tarball Created by Export:")
                }
                RowLayout {
                    Layout.fillWidth: true
                    Controls.TextField {
                        objectName: "importTarballPath"
                        Layout.fillWidth: true
                        text: importDialog.tarballPath
                        onTextChanged: importDialog.tarballPath = text
                    }
                    Controls.Button {
                        text: qsTr("Browse…")
                        onClicked: {
                            importDialog.pickPurpose = "tarball"
                            gameModel.pickPath(qsTr("Import Configurations"), qsTr("Open"))
                        }
                    }
                }
                Controls.Button {
                    objectName: "importTarballConfirm"
                    text: qsTr("Import")
                    onClicked: {
                        var msg = gameModel.importTarball(importDialog.tarballPath)
                        if (msg !== "") {
                            importDialog.notify(msg)
                            importDialog.close()
                        }
                    }
                }
            }
            ColumnLayout {
                id: stlPage
                spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: qsTr("Configured Games with an STL Config (Imports as Profiles):")
                }
                Controls.ScrollView {
                    clip: true
                    objectName: "importStlScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        implicitHeight: stlForm.implicitHeight
                        ColumnLayout {
                            id: stlForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Repeater {
                                model: importDialog.stlRows
                                delegate: Controls.CheckBox {
                                    required property var modelData
                                    text: modelData[1] + " [" + modelData[0] + "]"
                                    checked: importDialog.stlPicked.indexOf(modelData[0]) >= 0
                                    onToggled: {
                                        var kept = []
                                        for (var i = 0; i < importDialog.stlPicked.length; i++) {
                                            if (importDialog.stlPicked[i] !== modelData[0]) {
                                                kept.push(importDialog.stlPicked[i])
                                            }
                                        }
                                        if (checked) {
                                            kept.push(modelData[0])
                                        }
                                        importDialog.stlPicked = kept
                                    }
                                }
                            }
                        }
                    }
                }
                // Widgets StlImportDialog: Select All / Select None lead,
                // the import button closes the right-aligned row. Outside
                // the scroll area, or a long list pushes it out of view.
                RowLayout {
                    Layout.fillWidth: true
                    Controls.Button {
                        text: qsTr("Select All")
                        onClicked: {
                            var all = []
                            for (var i = 0; i < importDialog.stlRows.length; i++) {
                                all.push(importDialog.stlRows[i][0])
                            }
                            importDialog.stlPicked = all
                        }
                    }
                    Controls.Button {
                        text: qsTr("Select None")
                        onClicked: importDialog.stlPicked = []
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        objectName: "importStlConfirm"
                        text: qsTr("Import from SteamTinkerLaunch")
                        onClicked: {
                            var msg = gameModel.importStl(importDialog.stlPicked)
                            if (msg !== "") {
                                importDialog.notify(msg)
                                importDialog.close()
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                id: predPage
                spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: qsTr("Copy Configs from the Predecessor Project (Missing Files Only, Never Overwrites):")
                }
                Controls.Button {
                    objectName: "importPredecessorConfirm"
                    text: qsTr("Copy")
                    onClicked: {
                        var msg = gameModel.importPredecessor()
                        if (msg !== "") {
                            importDialog.notify(msg)
                            importDialog.close()
                        }
                    }
                }
            }
            ColumnLayout {
                id: libraryPage
                spacing: Kirigami.Units.smallSpacing
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: importDialog.libraryLoading
                        ? qsTr("Reading %1…").arg(importDialog.libraryName)
                        : importDialog.libraryHint !== ""
                            ? importDialog.libraryHint
                            : qsTr("%1 Games (New Games Are Checked; Existing Ones Import as a Profile):").arg(importDialog.libraryName)
                }
                Controls.ScrollView {
                    clip: true
                    objectName: "importLibraryScroll"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Item {
                        width: parent.width
                        implicitHeight: libraryForm.implicitHeight
                        ColumnLayout {
                            id: libraryForm
                            width: parent.width
                            spacing: Kirigami.Units.smallSpacing
                            Repeater {
                                model: importDialog.libraryRows
                                delegate: RowLayout {
                                    id: libraryRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    Controls.CheckBox {
                                        Layout.fillWidth: true
                                        enabled: libraryRow.modelData[3] !== "unavailable"
                                        opacity: enabled ? 1 : 0.55
                                        text: libraryRow.modelData[1]
                                        checked: importDialog.libraryPicked.indexOf(libraryRow.modelData[0]) >= 0
                                        onToggled: {
                                            var kept = []
                                            for (var i = 0; i < importDialog.libraryPicked.length; i++) {
                                                if (importDialog.libraryPicked[i] !== libraryRow.modelData[0]) {
                                                    kept.push(importDialog.libraryPicked[i])
                                                }
                                            }
                                            if (checked) {
                                                kept.push(libraryRow.modelData[0])
                                            }
                                            importDialog.libraryPicked = kept
                                        }
                                    }
                                    Controls.Label {
                                        objectName: "libraryRowState"
                                        visible: libraryRow.modelData[3] === "existing"
                                            || libraryRow.modelData[3] === "unavailable"
                                        text: libraryRow.modelData[3] === "existing"
                                            ? qsTr("In Library") : qsTr("Unavailable")
                                        opacity: libraryRow.modelData[3] === "unavailable" ? 0.55 : 0.7
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                    Kirigami.Icon {
                                        objectName: "libraryRowIcon"
                                        visible: libraryRow.modelData[3] === "existing"
                                            || libraryRow.modelData[3] === "unavailable"
                                        source: libraryRow.modelData[3] === "unavailable"
                                            ? gameModel.iconName(["dialog-warning", "dialog-information"])
                                            : gameModel.iconName(["dialog-information", "dialog-warning"])
                                        color: libraryRow.modelData[3] === "unavailable"
                                            ? Kirigami.Theme.neutralTextColor
                                            : Kirigami.Theme.textColor
                                        opacity: libraryRow.modelData[3] === "unavailable" ? 1 : 0.7
                                        Layout.alignment: Qt.AlignVCenter
                                        Layout.preferredWidth: Kirigami.Units.iconSizes.small
                                        Layout.preferredHeight: Kirigami.Units.iconSizes.small
                                        Layout.minimumWidth: Kirigami.Units.iconSizes.small
                                        Layout.minimumHeight: Kirigami.Units.iconSizes.small
                                    }
                                    HoverHandler {
                                        id: libraryRowHover
                                    }
                                    Controls.ToolTip {
                                        visible: libraryRowHover.hovered
                                        text: libraryRow.modelData[3] === "unavailable"
                                            ? libraryRow.modelData[2]
                                            : libraryRow.modelData[3] === "existing"
                                                ? qsTr("Already in the Library as %1").arg(libraryRow.modelData[4])
                                                : (libraryRow.modelData[2] !== ""
                                                    ? libraryRow.modelData[2] : libraryRow.modelData[1])
                                    }
                                }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Controls.Button {
                        text: qsTr("Select All")
                        Layout.minimumWidth: implicitWidth
                        enabled: !importDialog.libraryLoading
                        onClicked: {
                            var all = []
                            for (var i = 0; i < importDialog.libraryRows.length; i++) {
                                if (importDialog.libraryRows[i][3] !== "unavailable") {
                                    all.push(importDialog.libraryRows[i][0])
                                }
                            }
                            importDialog.libraryPicked = all
                        }
                    }
                    Controls.Button {
                        text: qsTr("Select None")
                        Layout.minimumWidth: implicitWidth
                        enabled: !importDialog.libraryLoading
                        onClicked: importDialog.libraryPicked = []
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Button {
                        objectName: "importLibraryConfirm"
                        text: qsTr("Import from %1").arg(importDialog.libraryName)
                        enabled: !importDialog.libraryLoading
                            && importDialog.libraryPicked.length > 0
                        onClicked: {
                            importDialog.libraryLoading = true
                            gameModel.startLibraryImport(importDialog.librarySource, importDialog.libraryPicked)
                        }
                    }
                }
            }
        }
        RowLayout {
            id: importFooter
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "importClose"
                text: qsTr("Close")
                onClicked: importDialog.close()
            }
        }
    }
}
