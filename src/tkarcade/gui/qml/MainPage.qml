import QtQuick
import QtQml
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Games page: search + view split-button on top, the selected view
// below (details list, icons grid, or gallery-style cards), counts at
// the bottom. Plain Page (not ScrollablePage): ScrollablePage adopts a
// single Flickable child, so three switchable views need explicit
// geometry instead. Zoom and sort live in the arrow popup, Lutris-style.
Kirigami.Page {
    id: gamesPage
    objectName: "gamesPage"
    title: qsTr("Games")

    property string viewMode: "list"
    property var viewSizes: ({list: 40, icons: 96})
    property int rowHeight: viewSizes["list"] || 40
    property int iconSize: viewSizes["icons"] || 96
    property var selectedIds: []
    property string anchorId: ""
    property string sortRole: "gameName"
    property bool sortDescending: false
    property string notice: ""

    function notify(text) {
        notice = text
        noticeTimer.restart()
    }

    Timer {
        id: noticeTimer
        interval: 5000
        onTriggered: gamesPage.notice = ""
    }

    function viewName() {
        if (viewMode === "icons") {
            return qsTr("Icons")
        }
        if (viewMode === "cards") {
            return qsTr("Cards")
        }
        return qsTr("List")
    }

    function cycleView() {
        if (viewMode === "list") {
            viewMode = "icons"
        } else if (viewMode === "icons") {
            viewMode = "cards"
        } else {
            viewMode = "list"
        }
    }

    function setViewSize(value) {
        var sizes = {}
        for (var k in viewSizes) {
            sizes[k] = viewSizes[k]
        }
        sizes[viewMode] = value
        viewSizes = sizes
    }

    function setSort(role, descending) {
        sortRole = role
        sortDescending = descending
        gameFilter.sortBy(sortRole, sortDescending)
    }

    function toggleSort(role) {
        if (sortRole === role) {
            setSort(role, !sortDescending)
        } else {
            setSort(role, false)
        }
    }

    function sortMark(role) {
        return sortRole === role ? (sortDescending ? "▼ " : "▲ ") : ""
    }

    function select(gid) {
        selectedIds = [gid]
        anchorId = gid
        syncIndexes(gid)
    }

    function syncIndexes(gid) {
        var row = gameFilter.indexOf(gid)
        gameList.currentIndex = row
        iconGrid.currentIndex = row
    }

    function toggleSelect(gid) {
        var kept = []
        for (var i = 0; i < selectedIds.length; i++) {
            if (selectedIds[i] !== gid) {
                kept.push(selectedIds[i])
            }
        }
        if (kept.length === selectedIds.length) {
            kept.push(gid)
        }
        selectedIds = kept
        anchorId = gid
        syncIndexes(gid)
    }

    function extendSelect(gid) {
        var anchor = gameFilter.indexOf(anchorId)
        var target = gameFilter.indexOf(gid)
        if (anchor < 0 || target < 0) {
            select(gid)
            return
        }
        var from = Math.min(anchor, target)
        var to = Math.max(anchor, target)
        var range = []
        for (var row = from; row <= to; row++) {
            range.push(gameFilter.idAt(row))
        }
        selectedIds = range
        syncIndexes(gid)
    }

    function tapGame(gid, mods) {
        if (mods & Qt.ControlModifier) {
            toggleSelect(gid)
        } else if (mods & Qt.ShiftModifier) {
            extendSelect(gid)
        } else {
            select(gid)
        }
    }

    function ensureSelection() {
        var kept = []
        for (var i = 0; i < selectedIds.length; i++) {
            if (gameFilter.indexOf(selectedIds[i]) >= 0) {
                kept.push(selectedIds[i])
            }
        }
        selectedIds = kept
        if (selectedIds.length === 0 && gameFilter.rowCount() > 0) {
            select(gameFilter.idAt(0))
        }
    }

    function playSelected() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select a game first."))
            return
        }
        gameModel.play(selectedIds[0])
    }

    function openRemoveDialog() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select games first."))
            return
        }
        removeDialog.open()
    }

    property string validateGid: ""
    property var validateIssues: []

    function openValidateDialog(gid) {
        validateGid = gid
        validateIssues = gameModel.validateGame(gid)
        if (validateIssues.length === 0) {
            gamesPage.notify(qsTr("No issues found."))
            return
        }
        validateDialog.open()
    }

    property string menuGid: ""
    property string menuInstall: ""
    property string menuPrefix: ""
    property string menuShader: ""
    property string menuShaderSize: ""
    property bool menuIsSteam: false

    function openGameMenu(gid) {
        if (selectedIds.indexOf(gid) < 0) {
            select(gid)
        }
        menuGid = gid
        menuIsSteam = /^\d+$/.test(gid)
        menuInstall = gameModel.installDir(gid)
        menuPrefix = gameModel.prefixDir(gid)
        menuShader = gameModel.shaderDir(gid)
        menuShaderSize = gameModel.shaderSize(gid)
        gameMenu.popup()
    }

    actions: [
        Kirigami.Action {
            objectName: "actionPlay"
            text: qsTr("Play")
            icon.name: "media-playback-start"
            onTriggered: gamesPage.playSelected()
        },
        Kirigami.Action {
            objectName: "actionAdd"
            text: qsTr("Add game")
            icon.name: "list-add"
            onTriggered: addDialog.open()
        },
        Kirigami.Action {
            // TEMPORARY: opens the local add dialog until the QML
            // game settings UI lands.
            objectName: "actionEdit"
            text: qsTr("Edit...")
            icon.name: "document-edit"
            onTriggered: addDialog.open()
        },
        Kirigami.Action {
            objectName: "actionRemove"
            text: qsTr("Remove")
            icon.name: "edit-delete"
            onTriggered: gamesPage.openRemoveDialog()
        }
    ]

    Component.onCompleted: gamesPage.ensureSelection()

    header: ColumnLayout {
        RowLayout {
            Layout.fillWidth: true
            Kirigami.SearchField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: qsTr("Filter by name or ID…")
                onTextChanged: gameFilter.textQuery = text
            }
            RowLayout {
                spacing: 0
                Controls.ToolButton {
                    id: viewButton
                    objectName: "viewButton"
                    text: gamesPage.viewName()
                    onClicked: gamesPage.cycleView()
                }
                Controls.ToolButton {
                    id: viewArrow
                    objectName: "viewArrow"
                    text: "▼"
                    onClicked: viewOptions.open()
                }
            }
            Controls.ToolButton {
                objectName: "columnsButton"
                text: qsTr("Columns")
                onClicked: columnsMenu.open()
                Controls.Menu {
                    id: columnsMenu
                    Controls.MenuItem {
                        text: qsTr("App ID")
                        checkable: true
                        checked: gameFilter.showAppId
                        onTriggered: gameFilter.showAppId = !gameFilter.showAppId
                    }
                    Controls.MenuItem {
                        text: qsTr("Played")
                        checkable: true
                        checked: gameFilter.showPlayed
                        onTriggered: gameFilter.showPlayed = !gameFilter.showPlayed
                    }
                    Controls.MenuItem {
                        text: qsTr("ProtonDB")
                        checkable: true
                        checked: gameFilter.showTier
                        onTriggered: gameFilter.showTier = !gameFilter.showTier
                    }
                    Controls.MenuItem {
                        text: qsTr("Source")
                        checkable: true
                        checked: gameFilter.showSource
                        onTriggered: gameFilter.showSource = !gameFilter.showSource
                    }
                }
            }
        }
    }

    Controls.Popup {
        id: viewOptions
        objectName: "viewOptions"
        parent: viewArrow
        x: viewArrow.width - width
        y: viewArrow.height + Kirigami.Units.smallSpacing
        closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
        padding: Kirigami.Units.largeSpacing
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Controls.Label {
                text: qsTr("View")
                font.bold: true
            }
            Controls.RadioButton {
                text: qsTr("List")
                checked: gamesPage.viewMode === "list"
                Controls.ButtonGroup.group: viewGroup
                onToggled: gamesPage.viewMode = "list"
            }
            Controls.RadioButton {
                text: qsTr("Icons")
                checked: gamesPage.viewMode === "icons"
                Controls.ButtonGroup.group: viewGroup
                onToggled: gamesPage.viewMode = "icons"
            }
            Controls.RadioButton {
                text: qsTr("Cards")
                checked: gamesPage.viewMode === "cards"
                Controls.ButtonGroup.group: viewGroup
                onToggled: gamesPage.viewMode = "cards"
            }
            Controls.Label {
                text: qsTr("Zoom")
                font.bold: true
            }
            Controls.Slider {
                objectName: "zoomSlider"
                Layout.fillWidth: true
                enabled: gamesPage.viewMode !== "cards"
                from: gamesPage.viewMode === "list" ? 32 : 64
                to: gamesPage.viewMode === "list" ? 64 : 192
                stepSize: gamesPage.viewMode === "list" ? 4 : 8
                value: gamesPage.viewMode === "list" ? gamesPage.rowHeight : gamesPage.iconSize
                onMoved: gamesPage.setViewSize(value)
            }
            Controls.Label {
                text: qsTr("Sort by")
                font.bold: true
            }
            Controls.RadioButton {
                text: qsTr("Name")
                checked: gamesPage.sortRole === "gameName"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gameName", gamesPage.sortDescending)
            }
            Controls.RadioButton {
                text: qsTr("App ID")
                checked: gamesPage.sortRole === "gameId"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gameId", gamesPage.sortDescending)
            }
            Controls.RadioButton {
                text: qsTr("Played")
                checked: gamesPage.sortRole === "gamePlayedSecs"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gamePlayedSecs", gamesPage.sortDescending)
            }
            Controls.RadioButton {
                text: qsTr("ProtonDB")
                checked: gamesPage.sortRole === "gameTier"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gameTier", gamesPage.sortDescending)
            }
            Controls.RadioButton {
                text: qsTr("Source")
                checked: gamesPage.sortRole === "gameSource"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gameSource", gamesPage.sortDescending)
            }
            Controls.CheckBox {
                text: qsTr("Reverse order")
                checked: gamesPage.sortDescending
                onToggled: gamesPage.setSort(gamesPage.sortRole, checked)
            }
        }
        Controls.ButtonGroup {
            id: viewGroup
        }
        Controls.ButtonGroup {
            id: sortGroup
        }
    }

    Controls.Menu {
        id: gameMenu
        objectName: "gameMenu"
        Controls.MenuItem {
            objectName: "menuPlay"
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Play")
            onTriggered: gameModel.play(gamesPage.menuGid)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Edit Settings")
            onTriggered: addDialog.open()
        }
        Controls.MenuSeparator {
            visible: gamesPage.selectedIds.length <= 1
        }
        Controls.MenuItem {
            objectName: "menuCopyLaunch"
            visible: gamesPage.menuIsSteam
            text: qsTr("Copy Launch Options")
            onTriggered: gamesPage.notify(gameModel.copyText("tkarcade %command%"))
        }
        Controls.MenuItem {
            visible: !gamesPage.menuIsSteam && gamesPage.selectedIds.length <= 1
            text: qsTr("Copy Launch Command")
            onTriggered: gamesPage.notify(
                gameModel.copyText("tkarcade --appid " + gamesPage.menuGid))
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Copy App ID")
            onTriggered: gamesPage.notify(
                gameModel.copyText(gamesPage.menuGid))
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Copy Game Name")
            onTriggered: {
                var names = gameModel.gameNames([gamesPage.menuGid])
                gamesPage.notify(gameModel.copyText(names[0]))
            }
        }
        Controls.MenuSeparator {
            visible: gamesPage.selectedIds.length <= 1
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            enabled: gamesPage.menuInstall !== ""
            text: qsTr("Open Install Folder")
            onTriggered: gameModel.openPath(gamesPage.menuInstall)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            enabled: gamesPage.menuPrefix !== ""
            text: qsTr("Open Proton Prefix")
            onTriggered: gameModel.openPath(gamesPage.menuPrefix)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            enabled: gamesPage.menuShader !== ""
            text: qsTr("Clear Shader Cache")
            onTriggered: shaderDialog.open()
        }
        Controls.MenuItem {
            visible: gamesPage.menuIsSteam && gamesPage.selectedIds.length <= 1
            text: qsTr("Open ProtonDB Page")
            onTriggered: gameModel.openProtonDB(gamesPage.menuGid)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Validate Game")
            onTriggered: gamesPage.openValidateDialog(gamesPage.menuGid)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Clear History")
            onTriggered: historyDialog.open()
        }
        Controls.MenuSeparator {
        }
        Controls.MenuItem {
            objectName: "menuRemove"
            text: gamesPage.selectedIds.length === 1
                ? qsTr("Remove Game")
                : qsTr("Remove %1 Games").arg(gamesPage.selectedIds.length)
            onTriggered: gamesPage.openRemoveDialog()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        visible: gamesPage.viewMode === "list"
        spacing: 0
        RowLayout {
            id: headerRow
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Item {
                Layout.preferredWidth: 36
                Layout.preferredHeight: 1
            }
            Item {
                Layout.preferredWidth: gamesPage.rowHeight - 8
                Layout.preferredHeight: 1
            }
            Controls.Label {
                Layout.fillWidth: true
                font.bold: true
                text: gamesPage.sortMark("gameName") + qsTr("Game")
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onTapped: gamesPage.toggleSort("gameName")
                }
            }
            Controls.Label {
                visible: gameFilter.showAppId
                Layout.preferredWidth: 90
                font.bold: true
                text: gamesPage.sortMark("gameId") + qsTr("App ID")
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onTapped: gamesPage.toggleSort("gameId")
                }
            }
            Controls.Label {
                visible: gameFilter.showPlayed
                Layout.preferredWidth: 90
                font.bold: true
                text: gamesPage.sortMark("gamePlayedSecs") + qsTr("Played")
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onTapped: gamesPage.toggleSort("gamePlayedSecs")
                }
            }
            Controls.Label {
                visible: gameFilter.showTier
                Layout.preferredWidth: 110
                font.bold: true
                text: gamesPage.sortMark("gameTier") + qsTr("ProtonDB")
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onTapped: gamesPage.toggleSort("gameTier")
                }
            }
            Controls.Label {
                visible: gameFilter.showSource
                Layout.preferredWidth: 80
                font.bold: true
                text: gamesPage.sortMark("gameSource") + qsTr("Source")
                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    cursorShape: Qt.PointingHandCursor
                    onTapped: gamesPage.toggleSort("gameSource")
                }
            }
            Item {
                Layout.preferredWidth: 40
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0
            ListView {
                id: rowGutter
                objectName: "rowGutter"
                Layout.preferredWidth: 36
                Layout.fillHeight: true
                model: gameFilter
                interactive: false
                contentY: gameList.contentY
                delegate: Controls.Label {
                    objectName: "gutterNumber"
                    width: 36
                    height: gamesPage.rowHeight
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    color: Kirigami.Theme.disabledTextColor
                    text: index + 1
                }
            }
    ListView {
        id: gameList
        objectName: "gameList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        model: gameFilter
        property int rowHeight: gamesPage.rowHeight
        property var colW: ({appId: 90, played: 90, tier: 110, source: 80})
        clip: true
        focus: true
        onCountChanged: gamesPage.ensureSelection()
        Keys.onUpPressed: {
            gameList.currentIndex = Math.max(0, gameList.currentIndex - 1)
            gamesPage.select(gameFilter.idAt(gameList.currentIndex))
            gameList.positionViewAtIndex(gameList.currentIndex, ListView.Contain)
        }
        Keys.onDownPressed: {
            gameList.currentIndex = Math.min(gameList.count - 1, gameList.currentIndex + 1)
            gamesPage.select(gameFilter.idAt(gameList.currentIndex))
            gameList.positionViewAtIndex(gameList.currentIndex, ListView.Contain)
        }
        delegate: GameDelegate {
            width: ListView.view ? ListView.view.width : 100
            selected: gamesPage.selectedIds.indexOf(gameId) >= 0
            onPlayRequested: (gid) => gameModel.play(gid)
            onRowTapped: (gid, mods) => gamesPage.tapGame(gid, mods)
            onMenuRequested: (gid) => gamesPage.openGameMenu(gid)
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: gameList.count === 0
            text: qsTr("No games yet")
            explanation: qsTr("Add a native Linux game to get started.")
        }
    }
        }
    }

    GridView {
        id: iconGrid
        objectName: "iconGrid"
        anchors.fill: parent
        visible: gamesPage.viewMode === "icons"
        model: gameFilter
        clip: true
        cellWidth: gamesPage.iconSize + Kirigami.Units.largeSpacing * 2
        cellHeight: gamesPage.iconSize + 64
        onCountChanged: gamesPage.ensureSelection()
        Keys.onUpPressed: iconGrid.moveCurrentIndexUp()
        Keys.onDownPressed: iconGrid.moveCurrentIndexDown()
        Keys.onLeftPressed: iconGrid.moveCurrentIndexLeft()
        Keys.onRightPressed: iconGrid.moveCurrentIndexRight()
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Up || event.key === Qt.Key_Down
                    || event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                gamesPage.select(gameFilter.idAt(iconGrid.currentIndex))
            }
        }
        delegate: GameIconDelegate {
            width: GridView.view ? GridView.view.cellWidth : 100
            height: GridView.view ? GridView.view.cellHeight : 100
            cellSize: gamesPage.iconSize
            selected: gamesPage.selectedIds.indexOf(gameId) >= 0
            onPlayRequested: (gid) => gameModel.play(gid)
            onRowTapped: (gid, mods) => gamesPage.tapGame(gid, mods)
            onMenuRequested: (gid) => gamesPage.openGameMenu(gid)
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: iconGrid.count === 0
            text: qsTr("No games yet")
            explanation: qsTr("Add a native Linux game to get started.")
        }
    }

    Controls.ScrollView {
        id: cardScroller
        objectName: "cardScroller"
        anchors.fill: parent
        visible: gamesPage.viewMode === "cards"
        clip: true
        ColumnLayout {
            width: cardScroller.availableWidth
            Kirigami.CardsLayout {
                id: cardLayout
                objectName: "cardLayout"
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                Repeater {
                    model: gameFilter
                    delegate: GameCard {
                        selected: gamesPage.selectedIds.indexOf(gameId) >= 0
                        onPlayRequested: (gid) => gameModel.play(gid)
                        onRowTapped: (gid, mods) => gamesPage.tapGame(gid, mods)
            onMenuRequested: (gid) => gamesPage.openGameMenu(gid)
                    }
                }
            }
            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                visible: gameFilter.rowCount() === 0
                text: qsTr("No games yet")
                explanation: qsTr("Add a native Linux game to get started.")
            }
        }
    }

    footer: RowLayout {
        Controls.Label {
            text: gamesPage.notice !== ""
                ? gamesPage.notice
                : qsTr("%1 configured · %2 Steam games detected").arg(gameModel.totalCount).arg(gameModel.steamDetectedCount)
        }
    }

    Kirigami.Dialog {
        id: addDialog
        objectName: "addDialog"
        title: qsTr("Add local game")
        padding: Kirigami.Units.largeSpacing

        ColumnLayout {
            Controls.TextField {
                id: nameField
                placeholderText: qsTr("Game name")
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Controls.TextField {
                    id: exeField
                    placeholderText: qsTr("Game executable")
                    Layout.fillWidth: true
                }
                Controls.Button {
                    text: qsTr("Browse…")
                    onClicked: gameModel.browseExecutable()
                }
                Connections {
                    target: gameModel
                    function onBrowseFinished(picked) {
                        if (picked !== "") {
                            exeField.text = picked
                            if (nameField.text === "") {
                                var parts = picked.split("/")
                                nameField.text = parts[parts.length - 1]
                            }
                        }
                    }
                }
            }
            Controls.Label {
                id: addError
                visible: text !== ""
                color: Kirigami.Theme.negativeTextColor
            }
        }

        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Add")
                onClicked: {
                    var created = gameModel.addLocal(nameField.text, exeField.text)
                    if (created === "") {
                        addError.text = qsTr("Name and a valid executable are required.")
                    } else {
                        nameField.text = ""
                        exeField.text = ""
                        addError.text = ""
                        addDialog.close()
                    }
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: addDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: removeDialog
        objectName: "removeDialog"
        title: qsTr("Remove Games")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: gamesPage.selectedIds.length === 1
                    ? qsTr("Remove the configuration for %1?").arg(
                        gameModel.gameNames(gamesPage.selectedIds)[0])
                    : qsTr("Remove the configurations for %1 games?").arg(
                        gamesPage.selectedIds.length)
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "removeConfirm"
                text: qsTr("Remove")
                onClicked: {
                    var targets = gamesPage.selectedIds.slice()
                    var err = gameModel.removeGames(targets)
                    if (err !== "") {
                        gamesPage.notify(err)
                    }
                    var leftovers = gameModel.leftoverProfiles(targets)
                    gamesPage.ensureSelection()
                    removeDialog.close()
                    if (leftovers.length > 0) {
                        cleanupDialog.leftovers = leftovers
                        cleanupDialog.open()
                    }
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: removeDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: cleanupDialog
        objectName: "cleanupDialog"
        title: qsTr("Clean Up Profiles")
        padding: Kirigami.Units.largeSpacing
        property var leftovers: []
        property var picked: []
        onLeftoversChanged: picked = leftovers.slice()
        ColumnLayout {
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("These games were removed but still have saved profiles:")
            }
            Repeater {
                model: cleanupDialog.leftovers
                Controls.CheckBox {
                    required property string modelData
                    text: modelData
                    checked: cleanupDialog.picked.indexOf(modelData) >= 0
                    onToggled: {
                        var kept = []
                        for (var i = 0; i < cleanupDialog.picked.length; i++) {
                            if (cleanupDialog.picked[i] !== modelData) {
                                kept.push(cleanupDialog.picked[i])
                            }
                        }
                        if (checked) {
                            kept.push(modelData)
                        }
                        cleanupDialog.picked = kept
                    }
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "cleanupConfirm"
                text: qsTr("Clean Selected")
                onClicked: {
                    var n = gameModel.cleanProfiles(cleanupDialog.picked)
                    gamesPage.notify(
                        qsTr("Cleaned profiles for %1 game(s).").arg(n))
                    cleanupDialog.close()
                }
            }
            Controls.Button {
                text: qsTr("Keep All")
                onClicked: cleanupDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: shaderDialog
        objectName: "shaderDialog"
        title: qsTr("Clear Shader Cache")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Delete %1 of shader cache for %2? Steam rebuilds it on demand.").arg(
                    gamesPage.menuShaderSize).arg(gamesPage.menuGid)
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "shaderConfirm"
                text: qsTr("Delete")
                onClicked: {
                    gamesPage.notify(
                        gameModel.clearShaderCache(gamesPage.menuGid))
                    shaderDialog.close()
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: shaderDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: historyDialog
        objectName: "historyDialog"
        title: qsTr("Clear History")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Clear session history for %1? This cannot be undone.").arg(
                    gamesPage.menuGid)
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "historyConfirm"
                text: qsTr("Clear")
                onClicked: {
                    var n = gameModel.clearHistory(gamesPage.menuGid)
                    gamesPage.notify(
                        qsTr("Cleared %1 session(s).").arg(n))
                    historyDialog.close()
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: historyDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: validateDialog
        objectName: "validateDialog"
        title: qsTr("Validate Game")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Repeater {
                model: gamesPage.validateIssues
                Controls.Label {
                    required property string modelData
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "• " + modelData
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Close")
                onClicked: validateDialog.close()
            }
        }
    }
}
