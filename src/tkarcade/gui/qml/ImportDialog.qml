import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Import configurations (tarball / SteamTinkerLaunch / predecessor):
// one modal window like the widgets flows (resizable, transient on
// the main window). `open()` keeps the call sites working.
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
            : predPage.implicitHeight
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 10
    width: Kirigami.Units.gridUnit * 30
    height: Math.max(
        minimumHeight,
        sourceRow.implicitHeight + Math.min(importListCap, pageHeight)
            + importFooter.implicitHeight
            + body.spacing * 2 + body.anchors.margins * 2)
    visible: false
    color: Kirigami.Theme.backgroundColor

    property int source: 0 // 0 tarball, 1 STL, 2 predecessor
    property var stlRows: []
    property var stlPicked: []
    property string tarballPath: ""
    property string pickPurpose: ""
    property var page: null

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(importDialog)
        visible = true
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
        RowLayout {
            id: sourceRow
            Layout.fillWidth: true
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
                    text: qsTr("A tarball created by Export:")
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
                    text: qsTr("Configured games with an STL config (imports as profiles):")
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
                    text: qsTr("Copy configs from the predecessor project (missing files only, never overwrites):")
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
