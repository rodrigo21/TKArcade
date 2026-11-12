import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kirigami.layouts as KirigamiLayouts

// Preferences: a separate modal window like the widgets QDialog
// (resizable, transient on the main window). `open()` keeps the old
// Dialog call sites working; `close()` is the native Window one.
Window {
    id: prefsDialog
    objectName: "prefsDialog"
    title: qsTr("Preferences")
    modality: Qt.WindowModal
    // Widgets PreferencesDialog used a plain QFormLayout and opened at
    // 420px, too narrow for the field placeholders and translated labels
    // (cut content). The form keeps its label column at any width, so the
    // window opens wide enough for the widest row and the fields.
    minimumWidth: Kirigami.Units.gridUnit * 30
    // One page per area (Interface, Artwork, Runtime). The height is
    // fixed like the game dialog: a StackLayout reports its tallest page,
    // so a content-driven height would jump on every tab switch.
    minimumHeight: Kirigami.Units.gridUnit * 24
    width: Kirigami.Units.gridUnit * 34
    height: Kirigami.Units.gridUnit * 30
    visible: false
    color: Kirigami.Theme.backgroundColor

    property var values: ({})
    property var page: null
    property var langCodes: []
    // Runtime archive downloads: one entry per layer, fed by the model
    // signals so the dialog keeps its state across reopenings.
    property var archiveBusy: ({"dxvk": false, "vkd3d": false})
    property var archiveStatus: ({"dxvk": "", "vkd3d": ""})
    property var archiveDirs: gameModel.runtimeArchiveDirs()
    // Which row asked the native picker, so its result lands in one place.
    property string pendingPick: ""

    Connections {
        target: gameModel
        function onBrowseFinished(picked) {
            if (prefsDialog.pendingPick === "") {
                return
            }
            if (prefsDialog.pendingPick === "prefixBase" && picked !== "") {
                prefixBaseField.text = picked
                prefsDialog.setPref("prefixBase", picked)
            }
            prefsDialog.pendingPick = ""
        }
    }

    function setArchiveState(kind, busy, message) {
        var busyCopy = {}
        var statusCopy = {}
        for (var k in archiveBusy) {
            busyCopy[k] = archiveBusy[k]
            statusCopy[k] = archiveStatus[k]
        }
        busyCopy[kind] = busy
        statusCopy[kind] = message
        archiveBusy = busyCopy
        archiveStatus = statusCopy
    }

    Connections {
        target: gameModel
        function onArchiveProgress(kind, message) {
            prefsDialog.setArchiveState(kind, true, message)
        }
        function onArchiveFinished(kind, message) {
            prefsDialog.setArchiveState(kind, false, message === "" ? qsTr("Installed.") : message)
        }
    }

    function open() {
        transientParent = Controls.ApplicationWindow.window
        gameModel.watchDialogKeys(prefsDialog)
        visible = true
    }

    function load() {
        values = gameModel.loadPrefs()
        archiveBusy = ({"dxvk": false, "vkd3d": false})
        archiveStatus = ({"dxvk": "", "vkd3d": ""})
        quickSpin.value = values.trayQuickCount ?? 5
        var opts = gameModel.languageOptions()
        langCodes = []
        var labels = []
        for (var i = 0; i < opts.length; i++) {
            langCodes.push(opts[i][0])
            labels.push(opts[i][1])
        }
        langCombo.model = labels
        var at = langCodes.indexOf(values.language ?? "system")
        langCombo.currentIndex = at >= 0 ? at : 0
    }

    function setPref(key, value) {
        var copy = {}
        for (var k in values) {
            copy[k] = values[k]
        }
        copy[key] = value
        values = copy
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
            gameModel.pressDefault(prefsDialog, ["prefsSave"])
        }
        Controls.TabBar {
            id: tabBar
            objectName: "prefsTabs"
            Layout.fillWidth: true
            Controls.TabButton {
                text: qsTr("Interface")
            }
            Controls.TabButton {
                text: qsTr("Artwork")
            }
            Controls.TabButton {
                text: qsTr("Runtime")
            }
        }
        StackLayout {
            objectName: "prefsStack"
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex
            Controls.ScrollView {
                clip: true
                objectName: "prefsInterfaceScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                // ScrollView takes its scrollable size from the content's
                // implicitHeight; a plain Item has none, so sizing the
                // wrapper with `height:` leaves contentHeight at -1 and the
                // content is squeezed into the viewport (nothing scrolls).
                Item {
                    width: parent.width
                    implicitHeight: interfaceColumn.implicitHeight
                    ColumnLayout {
                        id: interfaceColumn
                        objectName: "prefsInterfaceColumn"
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing
                        // One label column per tab, so the fields of every
                        // frame start at one x inside it (GameSettings).
                        property real labelWidth: Math.max(
                            prefsInterfaceForm.naturalLabelWidth,
                            prefsTrayForm.naturalLabelWidth)
                        SectionBox {
                            title: qsTr("Interface")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: prefsInterfaceForm
                                labelWidth: interfaceColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.CheckBox {
                                    objectName: "prefsShowPreview"
                                    text: qsTr("Show Launch Command Preview")
                                    checked: prefsDialog.values.showPreview ?? true
                                    onClicked: prefsDialog.setPref("showPreview", checked)
                                    Controls.ToolTip.text: qsTr("Live Preview Box at the Bottom of Game Dialogs.")
                                    Controls.ToolTip.visible: hovered
                                }
                                AppComboBox {
                                    id: langCombo
                                    objectName: "prefsLanguage"
                                    Layout.fillWidth: true
                                    KirigamiLayouts.FormData.label: qsTr("Language:")
                                    onActivated: (index) => prefsDialog.setPref(
                                        "language", prefsDialog.langCodes[index] || "system")
                                    Controls.ToolTip.text: qsTr("Takes Effect on Restart.")
                                    Controls.ToolTip.visible: hovered
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Tray")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: prefsTrayForm
                                labelWidth: interfaceColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.CheckBox {
                                    id: trayCheck
                                    objectName: "prefsTray"
                                    text: qsTr("Enable Status Bar Icon")
                                    checked: prefsDialog.values.trayEnable ?? false
                                    onClicked: prefsDialog.setPref("trayEnable", checked)
                                    Controls.ToolTip.text: qsTr("Keep TKArcade in the System Tray.")
                                    Controls.ToolTip.visible: hovered
                                }
                                AppComboBox {
                                    objectName: "prefsTrayIcon"
                                    Layout.fillWidth: true
                                    enabled: trayCheck.checked
                                    model: [qsTr("Normal"), qsTr("Monochrome")]
                                    KirigamiLayouts.FormData.label: qsTr("Tray Icon Style:")
                                    currentIndex: prefsDialog.values.trayIcon === "mono" ? 1 : 0
                                    onActivated: (index) => prefsDialog.setPref(
                                        "trayIcon", index === 1 ? "mono" : "normal")
                                }
                                Controls.CheckBox {
                                    text: qsTr("Minimize to Tray")
                                    enabled: trayCheck.checked
                                    checked: prefsDialog.values.minimizeToTray ?? false
                                    onClicked: prefsDialog.setPref("minimizeToTray", checked)
                                }
                                Controls.CheckBox {
                                    text: qsTr("Close to Tray")
                                    enabled: trayCheck.checked
                                    checked: prefsDialog.values.closeToTray ?? false
                                    onClicked: prefsDialog.setPref("closeToTray", checked)
                                }
                                Controls.CheckBox {
                                    id: quickCheck
                                    text: qsTr("Show Recent Games in Tray Menu")
                                    enabled: trayCheck.checked
                                    checked: prefsDialog.values.trayQuickLaunch ?? false
                                    onClicked: prefsDialog.setPref("trayQuickLaunch", checked)
                                    Controls.ToolTip.text: qsTr("Launch Recent Games Through Steam (steam:// URL).")
                                    Controls.ToolTip.visible: hovered
                                }
                                Controls.SpinBox {
                                    id: quickSpin
                                    objectName: "prefsQuickCount"
                                    from: 1
                                    to: 10
                                    enabled: trayCheck.checked && quickCheck.checked
                                    onValueModified: prefsDialog.setPref("trayQuickCount", value)
                                    Controls.ToolTip.text: qsTr("How Many Recent Games to List.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("Recent Games:")
                                }
                            }
                        }
                    }
                }
            }
            Controls.ScrollView {
                clip: true
                objectName: "prefsArtworkScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Item {
                    width: parent.width
                    implicitHeight: artworkColumn.implicitHeight
                    ColumnLayout {
                        id: artworkColumn
                        objectName: "prefsArtworkColumn"
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing
                        property real labelWidth: Math.max(
                            prefsArtworkForm.naturalLabelWidth,
                            prefsMetadataForm.naturalLabelWidth)
                        SectionBox {
                            title: qsTr("Artwork")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: prefsArtworkForm
                                labelWidth: artworkColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.TextField {
                                    objectName: "prefsSgdb"
                                    Layout.fillWidth: true
                                    echoMode: Controls.TextField.Password
                                    placeholderText: qsTr("Free Key from steamgriddb.com")
                                    text: prefsDialog.values.sgdbApiKey ?? ""
                                    onTextChanged: {
                                        if (prefsDialog.values.sgdbApiKey !== text) {
                                            prefsDialog.setPref("sgdbApiKey", text)
                                        }
                                    }
                                    Controls.ToolTip.text: qsTr("SteamGridDB API Key for Missing Artwork Fallback.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("SteamGridDB Key:")
                                }
                                AppComboBox {
                                    id: artSourceCombo
                                    objectName: "prefsArtworkSource"
                                    Layout.fillWidth: true
                                    model: [
                                        { "text": qsTr("Steam (Official)"), "data": "steam" },
                                        { "text": qsTr("SteamGridDB (Community)"), "data": "sgdb" }
                                    ]
                                    textRole: "text"
                                    valueRole: "data"
                                    onActivated: (index) => prefsDialog.setPref(
                                        "artworkSource", model[index].data)
                                    // The form is filled from a property, not by the
                                    // combo itself: a binding keeps the row in step
                                    // with the stored value (and restores itself after
                                    // the user picks another entry).
                                    Binding {
                                        target: artSourceCombo
                                        property: "currentIndex"
                                        value: (prefsDialog.values.artworkSource ?? "steam") === "sgdb" ? 1 : 0
                                    }
                                    Controls.ToolTip.text: qsTr("Steam Assets Are the Official Ones; SteamGridDB Is Community Artwork (Needs a Key). Fetch Artwork Re-Downloads With the Chosen Source.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("Artwork Source:")
                                }
                            }
                        }
                        SectionBox {
                            title: qsTr("Metadata")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: prefsMetadataForm
                                labelWidth: artworkColumn.labelWidth
                                Layout.fillWidth: true
                                Controls.TextField {
                                    objectName: "prefsIgdbClientId"
                                    Layout.fillWidth: true
                                    placeholderText: qsTr("Twitch Application Client ID")
                                    text: prefsDialog.values.igdbClientId ?? ""
                                    onTextChanged: {
                                        if (prefsDialog.values.igdbClientId !== text) {
                                            prefsDialog.setPref("igdbClientId", text)
                                        }
                                    }
                                    Controls.ToolTip.text: qsTr("IGDB Reads a Free Twitch Application: Client ID From dev.twitch.tv.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("IGDB Client ID:")
                                }
                                Controls.TextField {
                                    objectName: "prefsIgdbClientSecret"
                                    Layout.fillWidth: true
                                    echoMode: Controls.TextField.Password
                                    placeholderText: qsTr("Twitch Application Client Secret")
                                    text: prefsDialog.values.igdbClientSecret ?? ""
                                    onTextChanged: {
                                        if (prefsDialog.values.igdbClientSecret !== text) {
                                            prefsDialog.setPref("igdbClientSecret", text)
                                        }
                                    }
                                    Controls.ToolTip.text: qsTr("IGDB Client Secret: Kept in the Preferences File, Never Sent Anywhere Else.")
                                    Controls.ToolTip.visible: hovered
                                    KirigamiLayouts.FormData.label: qsTr("IGDB Client Secret:")
                                }
                            }
                        }
                    }
                }
            }
            Controls.ScrollView {
                clip: true
                objectName: "prefsRuntimeScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Item {
                    width: parent.width
                    implicitHeight: runtimeColumn.implicitHeight
                    ColumnLayout {
                        id: runtimeColumn
                        objectName: "prefsRuntimeColumn"
                        width: parent.width
                        spacing: Kirigami.Units.largeSpacing
                        property real labelWidth: prefsRuntimeForm.naturalLabelWidth
                        SectionBox {
                            title: qsTr("Runtime")
                            Layout.fillWidth: true
                            WidgetsFormLayout {
                                id: prefsRuntimeForm
                                objectName: "prefsRuntimeForm"
                                labelWidth: runtimeColumn.labelWidth
                                Layout.fillWidth: true
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("Prefix Base:")
                                    Controls.TextField {
                                        id: prefixBaseField
                                        objectName: "prefsPrefixBase"
                                        Layout.fillWidth: true
                                        placeholderText: qsTr("Default: $XDG_DATA_HOME/tkarcade/prefixes")
                                        text: prefsDialog.values.prefixBase ?? ""
                                        onTextChanged: {
                                            if (prefsDialog.values.prefixBase !== text) {
                                                prefsDialog.setPref("prefixBase", text)
                                            }
                                        }
                                        Controls.ToolTip.text: qsTr("Local Games Use <base>/<Game ID> Unless the Game Overrides the Path.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "prefsPrefixBaseBrowse"
                                        text: qsTr("Browse…")
                                        onClicked: {
                                            prefsDialog.pendingPick = "prefixBase"
                                            gameModel.pickDir(qsTr("Prefix Base"), qsTr("Select"))
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("Wine Versions:")
                                    Controls.Label {
                                        objectName: "prefsWineDefault"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        text: (prefsDialog.values.wineDefault ?? "") === ""
                                            ? qsTr("Wine From PATH")
                                            : prefsDialog.values.wineDefault
                                        Controls.ToolTip.text: qsTr("New Local Games Use This Build. Manage the List to Add or Remove Installs.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "prefsWineManage"
                                        text: qsTr("Manage…")
                                        onClicked: wineVersionsDialog.openFor(prefsDialog)
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("Proton:")
                                    Controls.Label {
                                        objectName: "prefsProtonDefault"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        text: (prefsDialog.values.protonDefault ?? "") === ""
                                            ? qsTr("First Installed")
                                            : prefsDialog.values.protonDefault
                                        Controls.ToolTip.text: qsTr("Local Games Preselect This Build. Steam Games Keep Steam's Own Choice.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "prefsManageProton"
                                        text: qsTr("Manage…")
                                        onClicked: protonVersionsDialog.openFor(prefsDialog)
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("DXVK:")
                                    Controls.Label {
                                        objectName: "prefsDxvkDefault"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        text: (prefsDialog.values.dxvkDefault ?? "") === ""
                                            ? qsTr("Newest Installed")
                                            : prefsDialog.values.dxvkDefault
                                        Controls.ToolTip.text: qsTr("New Games Preselect This Version. Manage the List to Download or Remove Builds.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "prefsManageDxvk"
                                        text: qsTr("Manage Versions…")
                                        onClicked: runtimeManagerDialog.openFor(prefsDialog, "dxvk")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("vkd3d-proton:")
                                    Controls.Label {
                                        objectName: "prefsVkd3dDefault"
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        text: (prefsDialog.values.vkd3dDefault ?? "") === ""
                                            ? qsTr("Newest Installed")
                                            : prefsDialog.values.vkd3dDefault
                                        Controls.ToolTip.text: qsTr("New Games Preselect This Version. Manage the List to Download or Remove Builds.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                    Controls.Button {
                                        objectName: "prefsManageVkd3d"
                                        text: qsTr("Manage Versions…")
                                        onClicked: runtimeManagerDialog.openFor(prefsDialog, "vkd3d")
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.smallSpacing
                                    KirigamiLayouts.FormData.label: qsTr("Download Mirror:")
                                    Controls.TextField {
                                        objectName: "prefsDownloadMirror"
                                        Layout.fillWidth: true
                                        placeholderText: qsTr("Empty Uses GitHub Directly")
                                        text: prefsDialog.values.downloadMirror ?? ""
                                        onTextChanged: {
                                            if (prefsDialog.values.downloadMirror !== text) {
                                                prefsDialog.setPref("downloadMirror", text)
                                            }
                                        }
                                        Controls.ToolTip.text: qsTr("https:// Prefix Prepended to GitHub Download URLs.")
                                        Controls.ToolTip.visible: hovered
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            id: footer
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            Controls.Button {
                objectName: "prefsSave"
                text: qsTr("Save")
                // QDialogButtonBox(Save | Cancel): accept first, default.
                highlighted: true
                onClicked: {
                    // The Wine manager saves its list on every action; take
                    // those two keys fresh so Save cannot write stale ones.
                    var fresh = gameModel.loadPrefs()
                    prefsDialog.setPref("wineVersions", fresh.wineVersions ?? "")
                    prefsDialog.setPref("wineDefault", fresh.wineDefault ?? "")
                    prefsDialog.setPref("protonDefault", fresh.protonDefault ?? "")
                    if (gameModel.savePrefs(prefsDialog.values)) {
                        prefsDialog.close()
                    } else if (page !== null) {
                        page.notify(qsTr("Could Not Save Preferences."))
                    }
                }
            }
            Controls.Button {
                objectName: "prefsCancel"
                text: qsTr("Cancel")
                onClicked: prefsDialog.close()
            }
        }
    }

    RuntimeManagerDialog {
        id: runtimeManagerDialog
    }

    ProtonVersionsDialog {
        id: protonVersionsDialog
        onListChanged: {
            var fresh = gameModel.loadPrefs()
            prefsDialog.setPref("protonDefault", fresh.protonDefault ?? "")
        }
    }

    WineVersionsDialog {
        id: wineVersionsDialog
        onListChanged: {
            var fresh = gameModel.loadPrefs()
            prefsDialog.setPref("wineVersions", fresh.wineVersions ?? "")
            prefsDialog.setPref("wineDefault", fresh.wineDefault ?? "")
        }
    }
}
