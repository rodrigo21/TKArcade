import QtQuick
import QtQml
import QtQml.Models as QQmlModels
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.tableview as KAddons

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
    property var viewSizes: ({icons: 96})
    property int iconSize: viewSizes["icons"] || 96
    property var selectedIds: []
    property string anchorId: ""
    property string sortRole: "gameName"
    property bool sortDescending: false
    property string notice: ""
    property var appDrawer: null
    property var viewArrowItem: null

    function setDrawerMode(mode) {
        if (appDrawer === null) {
            return
        }
        if (mode === "overlay") {
            appDrawer.modal = true
            appDrawer.collapsible = false
            appDrawer.collapsed = false
        } else if (mode === "collapsible") {
            appDrawer.modal = false
            appDrawer.collapsible = true
            appDrawer.collapsed = true
        } else {
            appDrawer.modal = false
            appDrawer.collapsible = false
            appDrawer.collapsed = false
        }
        gameModel.saveDrawerMode(mode)
    }

    onViewModeChanged: {
        if (viewMode === "list") {
            gamesPage.applySelectionToTable()
        }
    }

    function applySelectionToTable() {
        gameTable.selectionModel.clearSelection()
        for (var i = 0; i < selectedIds.length; i++) {
            var row = gameFilter.indexOf(selectedIds[i])
            if (row >= 0) {
                gameTable.selectionModel.select(
                    gameFilter.proxyIndex(row),
                    QQmlModels.ItemSelectionModel.Select | selectFlags())
            }
        }
        if (selectedIds.length > 0) {
            var first = gameFilter.indexOf(selectedIds[0])
            if (first >= 0) {
                gameTable.selectionModel.setCurrentIndex(
                    gameFilter.proxyIndex(first),
                    QQmlModels.ItemSelectionModel.NoUpdate)
            }
        }
    }

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

    function selectFlags() {
        return QQmlModels.ItemSelectionModel.Rows
    }

    function tableRowHeight() {
        return Kirigami.Units.gridUnit * 2
    }

    function scrollTableTo(row) {
        var target = tableRowHeight() * (row + 1) - gameTable.height / 2
        gameTable.contentY = Math.max(0, target)
    }

    function tableSingleSelect(row) {
        if (row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var index = gameFilter.proxyIndex(row)
        gameTable.selectionModel.setCurrentIndex(
            index,
            QQmlModels.ItemSelectionModel.ClearAndSelect | selectFlags())
        gamesPage.scrollTableTo(row)
    }

    function tableToggleRow(row) {
        if (row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var index = gameFilter.proxyIndex(row)
        gameTable.selectionModel.setCurrentIndex(
            index, QQmlModels.ItemSelectionModel.Toggle | selectFlags())
        gamesPage.scrollTableTo(row)
    }

    function tableRangeSelect(row) {
        var anchor = gameFilter.indexOf(anchorId)
        if (anchor < 0 || row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var from = Math.min(anchor, row)
        var to = Math.max(anchor, row)
        gameTable.selectionModel.clearSelection()
        for (var r = from; r <= to; r++) {
            gameTable.selectionModel.select(
                gameFilter.proxyIndex(r),
                QQmlModels.ItemSelectionModel.Select | selectFlags())
        }
        gameTable.selectionModel.setCurrentIndex(
            gameFilter.proxyIndex(row), QQmlModels.ItemSelectionModel.NoUpdate)
        gamesPage.scrollTableTo(row)
    }

    function moveTableSelection(delta) {
        var current = gameTable.selectionModel.currentIndex
        var row = current !== undefined && current.valid ? current.row : 0
        row = Math.max(0, Math.min(gameFilter.rowCount() - 1, row + delta))
        tableSingleSelect(row)
    }

    function select(gid) {
        selectedIds = [gid]
        anchorId = gid
        syncIndexes(gid)
    }

    function syncIndexes(gid) {
        var row = gameFilter.indexOf(gid)
        if (gamesPage.viewMode === "list") {
            tableSingleSelect(row)
        } else {
            iconGrid.currentIndex = row
        }
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
        if (gamesPage.viewMode === "list") {
            tableToggleRow(gameFilter.indexOf(gid))
        } else {
            iconGrid.currentIndex = gameFilter.indexOf(gid)
        }
    }

    function extendSelect(gid) {
        var anchor = gameFilter.indexOf(anchorId)
        var target = gameFilter.indexOf(gid)
        if (anchor < 0 || target < 0) {
            select(gid)
            return
        }
        if (gamesPage.viewMode === "list") {
            tableRangeSelect(target)
            return
        }
        var from = Math.min(anchor, target)
        var to = Math.max(anchor, target)
        var range = []
        for (var row = from; row <= to; row++) {
            range.push(gameFilter.idAt(row))
        }
        selectedIds = range
        iconGrid.currentIndex = target
    }

    function syncSelectedIds() {
        var rows = gameTable.selectionModel.selectedRows()
        var ids = []
        for (var i = 0; i < rows.length; i++) {
            ids.push(gameFilter.idAt(rows[i].row))
        }
        selectedIds = ids
        var current = gameTable.selectionModel.currentIndex
        if (current !== undefined && current.valid) {
            anchorId = gameFilter.idAt(current.row)
        }
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
        var actual = []
        var rows = gameTable.selectionModel.selectedRows()
        for (var i = 0; i < rows.length; i++) {
            var gid = gameFilter.idAt(rows[i].row)
            if (gid !== "" && gameFilter.indexOf(gid) >= 0) {
                actual.push(gid)
            }
        }
        selectedIds = actual
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

    Component.onCompleted: {
        gamesPage.loadColumns()
        gameModel.fetchMissing()
        Qt.callLater(gamesPage.ensureSelection)
    }

    Connections {
        target: gameTable.selectionModel
        function onSelectionChanged() {
            gamesPage.syncSelectedIds()
        }
    }

    Connections {
        target: gameFilter
        function onColumnsChanged() {
            gamesPage.saveColumns()
            gamesPage.fitGameColumn()
        }
        function onRowsInserted() {
            gamesPage.ensureSelection()
        }
        function onRowsRemoved() {
            gamesPage.ensureSelection()
        }
        function onModelReset() {
            gamesPage.ensureSelection()
        }
    }

    onColumnOrderChanged: gamesPage.saveColumns()

    function columnWidth(logical) {
        if (logical === 3) {
            return 110
        }
        if (logical === 4) {
            return 80
        }
        return 90
    }

    function columnVisible(logical) {
        if (logical === 1) {
            return gameFilter.showAppId
        }
        if (logical === 2) {
            return gameFilter.showPlayed
        }
        if (logical === 3) {
            return gameFilter.showTier
        }
        return gameFilter.showSource
    }

    function columnSortRole(logical) {
        if (logical === 1) {
            return "gameId"
        }
        if (logical === 2) {
            return "gamePlayedSecs"
        }
        if (logical === 3) {
            return "gameTier"
        }
        return "gameSource"
    }

    function columnTitle(logical) {
        if (logical === 1) {
            return qsTr("App ID")
        }
        if (logical === 2) {
            return qsTr("Played")
        }
        if (logical === 3) {
            return qsTr("ProtonDB")
        }
        return qsTr("Source")
    }

    property var columnOrder: [1, 2, 3, 4] // JS array only: Repeater models
    // must stay JS (a QVariantList injected from outside lays out at
    // zero width). All writers below build fresh JS arrays.

    function moveColumn(logical, dir) {
        var pos = columnOrder.indexOf(logical)
        var swap = pos + dir
        if (pos < 0 || swap < 0 || swap >= columnOrder.length) {
            return
        }
        var order = columnOrder.slice()
        order[pos] = columnOrder[swap]
        order[swap] = logical
        columnOrder = order
        gamesPage.applyColumnOrder()
    }

    function resetColumns() {
        columnOrder = [1, 2, 3, 4]
        gamesPage.applyColumnOrder()
        gameFilter.showAppId = true
        gameFilter.showPlayed = true
        gameFilter.showTier = true
        gameFilter.showSource = true
    }

    function loadColumns() {
        var order = gameModel.columnOrder()
        var data = []
        for (var i = 0; i < order.length; i++) {
            if (order[i] !== 0) {
                data.push(order[i])
            }
        }
        if (data.length === 4) {
            columnOrder = data
            gamesPage.applyColumnOrder()
        }
        var hidden = gameModel.hiddenColumns()
        gameFilter.showAppId = hidden.indexOf(1) < 0
        gameFilter.showPlayed = hidden.indexOf(2) < 0
        gameFilter.showTier = hidden.indexOf(3) < 0
        gameFilter.showSource = hidden.indexOf(4) < 0
    }

    function fixedColumnsWidth() {
        var total = 36
        if (gameFilter.showAppId) {
            total += 90
        }
        if (gameFilter.showPlayed) {
            total += 90
        }
        if (gameFilter.showTier) {
            total += 110
        }
        if (gameFilter.showSource) {
            total += 80
        }
        return total
    }

    function fitGameColumn() {
        if (gameTable.width > 0) {
            hcGame.width = Math.max(120, gameTable.width - fixedColumnsWidth())
        }
    }

    function columnComponent(logical) {
        if (logical === 0) {
            return hcGame
        }
        if (logical === 1) {
            return hcAppId
        }
        if (logical === 2) {
            return hcPlayed
        }
        if (logical === 3) {
            return hcTier
        }
        return hcSource
    }

    function applyColumnOrder() {
        var comps = [hcNum, hcGame]
        for (var i = 0; i < columnOrder.length; i++) {
            comps.push(columnComponent(columnOrder[i]))
        }
        gameTable.headerComponents = comps
    }

    function saveColumns() {
        var hidden = []
        if (!gameFilter.showAppId) {
            hidden.push(1)
        }
        if (!gameFilter.showPlayed) {
            hidden.push(2)
        }
        if (!gameFilter.showTier) {
            hidden.push(3)
        }
        if (!gameFilter.showSource) {
            hidden.push(4)
        }
        gameModel.saveColumns([0].concat(columnOrder), hidden)
    }

    // Window-header actions (systemmonitor-style): primaries, search,
    // view switcher, columns gear and hamburger — no content toolbar.
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
        },
        Kirigami.Action {
            displayComponent: Kirigami.SearchField {
                objectName: "searchField"
                implicitWidth: Kirigami.Units.gridUnit * 16
                placeholderText: qsTr("Filter by name or ID…")
                onTextChanged: gameFilter.textQuery = text
            }
        },
        Kirigami.Action {
            displayComponent: RowLayout {
                spacing: 0
                Component.onCompleted: {
                    // displayComponent scope hides ids: publish for popups.
                    gamesPage.viewArrowItem = viewArrow
                }
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
        },
        Kirigami.Action {
            objectName: "columnsButton"
            icon.name: "view-column"
            text: qsTr("Columns")
            onTriggered: columnsDialog.open()
        },
        Kirigami.Action {
            displayComponent: Controls.ToolButton {
                objectName: "hamburgerButton"
                icon.name: "application-menu"
                onClicked: hamburgerMenu.open()
                                Controls.Menu {
                                    id: hamburgerMenu
                                    objectName: "hamburgerMenu"
                                    Controls.MenuItem {
                                        text: qsTr("Scan Steam Library...")
                                        onTriggered: {
                                            var cands = gameModel.scanCandidates()
                                            if (cands.length === 0) {
                                                gamesPage.notify(
                                                    qsTr("Every Steam game is already configured."))
                                                return
                                            }
                                            scanDialog.candidates = cands
                                            scanDialog.open()
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("History...")
                                        onTriggered: {
                                            historyView.rows = gameModel.historySummary()
                                            historyView.open()
                                        }
                                    Controls.MenuItem {
                        objectName: "issuesOnly"
                        text: qsTr("With issues only")
                        checkable: true
                        checked: gameFilter.issuesOnly
                        onTriggered: gameFilter.issuesOnly = checked
                    }
                                    }
                                    Controls.MenuSeparator {
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Open Ludusavi...")
                                        onTriggered: {
                                            var msg = gameModel.openLudusavi()
                                            if (msg !== "") {
                                                gamesPage.notify(msg)
                                            }
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Open Logs Folder")
                                        onTriggered: {
                                            if (!gameModel.openPath(gameModel.logsDir())) {
                                                gamesPage.notify(qsTr("Could not open the logs folder."))
                                            }
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Clean Profiles...")
                                        onTriggered: {
                                            var rows = gameModel.orphanedProfiles()
                                            if (rows.length === 0) {
                                                gamesPage.notify(qsTr("No orphaned profiles."))
                                                return
                                            }
                                            var ids = []
                                            for (var i = 0; i < rows.length; i++) {
                                                ids.push(rows[i][0])
                                            }
                                            cleanupDialog.leftovers = ids
                                            cleanupDialog.open()
                                        }
                                    }
                                    Controls.MenuSeparator {
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Reload")
                                        onTriggered: {
                                            gameModel.refresh()
                                            gamesPage.ensureSelection()
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Preferences...")
                                        onTriggered: {
                                            prefsDialog.load()
                                            prefsDialog.open()
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("About...")
                                        onTriggered: aboutDialog.open()
                                    }
                                    Controls.MenuSeparator {
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Quit")
                                        onTriggered: Qt.quit()
                                    }
                                    Controls.MenuSeparator {
                                    }
                                    Controls.MenuItem {
                                        enabled: false
                                        text: qsTr("Drawer Mode")
                                    }
                                    Controls.MenuItem {
                                        objectName: "drawerModeOverlay"
                                        text: qsTr("Overlay Drawer")
                                        checkable: true
                                        checked: gamesPage.appDrawer !== null && gamesPage.appDrawer.modal && !gamesPage.appDrawer.collapsible
                                        onTriggered: gamesPage.setDrawerMode("overlay")
                                    }
                                    Controls.MenuItem {
                                        objectName: "drawerModeSidebar"
                                        text: qsTr("Sidebar Drawer")
                                        checkable: true
                                        checked: gamesPage.appDrawer !== null && !gamesPage.appDrawer.modal && !gamesPage.appDrawer.collapsible
                                        onTriggered: gamesPage.setDrawerMode("sidebar")
                                    }
                                    Controls.MenuItem {
                                        objectName: "drawerModeCollapsible"
                                        text: qsTr("Collapsible Sidebar Drawer")
                                        checkable: true
                                        checked: gamesPage.appDrawer !== null && !gamesPage.appDrawer.modal && gamesPage.appDrawer.collapsible
                                        onTriggered: gamesPage.setDrawerMode("collapsible")
                                    }
                                }
            }
        }
    ]

    Controls.Popup {
        id: viewOptions
        objectName: "viewOptions"
        parent: viewArrowItem
        x: viewArrowItem !== null ? viewArrowItem.width - width : 0
        y: viewArrowItem !== null ? viewArrowItem.height + Kirigami.Units.smallSpacing : 0
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
                enabled: gamesPage.viewMode === "icons"
                from: 64
                to: 192
                stepSize: 8
                value: gamesPage.iconSize
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

    KAddons.ListTableView {
        id: gameTable
        objectName: "gameTable"
        anchors.fill: parent
        visible: gamesPage.viewMode === "list"
        model: gameFilter
        alternatingRows: true
        selectionBehavior: TableView.SelectRows
        selectionMode: TableView.ExtendedSelection
        sortRole: gameModel.roleId(gamesPage.sortRole)
        sortOrder: gamesPage.sortDescending ? Qt.DescendingOrder : Qt.AscendingOrder
        onWidthChanged: gamesPage.fitGameColumn()
        onRowDoubleClicked: (row) => gameModel.play(gameFilter.idAt(row))
        onColumnClicked: (column, hc) => {
            if (hc.textRole !== undefined && hc.textRole !== "") {
                gamesPage.toggleSort(hc.textRole)
            }
        }
        Keys.onUpPressed: {
            gamesPage.moveTableSelection(-1)
        }
        Keys.onDownPressed: {
            gamesPage.moveTableSelection(1)
        }
        KAddons.HeaderComponent {
            id: hcNum
            objectName: "hcNum"
            title: "#"
            width: 36
            itemDelegate: Controls.Label {
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: Kirigami.Theme.disabledTextColor
                text: row + 1
            }
        }
        KAddons.HeaderComponent {
            id: hcGame
            objectName: "hcGame"
            title: qsTr("Game")
            textRole: "gameName"
            role: gameModel.roleId("gameName")
            width: 400
            itemDelegate: Item {
                implicitWidth: hcGame.width
                implicitHeight: Kirigami.Units.gridUnit * 2
                property bool rowSelected: false
                function refreshSelected() {
                    rowSelected = gameTable.selectionModel.isSelected(gameFilter.index(row, 0))
                }
                Component.onCompleted: refreshSelected()
                Connections {
                    target: gameTable.selectionModel
                    function onSelectionChanged() {
                        refreshSelected()
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    onClicked: (mouse) => gamesPage.openGameMenu(gameFilter.idAt(row))
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Kirigami.Units.smallSpacing
                    spacing: Kirigami.Units.smallSpacing
                    Item {
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 32
                        Layout.alignment: Qt.AlignVCenter
                        Image {
                            anchors.fill: parent
                            visible: (model?.gameIcon ?? "") !== ""
                            source: visible ? "file://" + model?.gameIcon : ""
                            fillMode: Image.PreserveAspectFit
                        }
                        Kirigami.Icon {
                            anchors.centerIn: parent
                            visible: (model?.gameIcon ?? "") === ""
                            source: "applications-games"
                            width: 20
                            height: 20
                        }
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        verticalAlignment: Text.AlignVCenter
                        text: modelData ?? ""
                        color: rowSelected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        elide: Text.ElideRight
                    }
                }
            }
        }
        KAddons.HeaderComponent {
            id: hcAppId
            objectName: "hcAppId"
            title: qsTr("App ID")
            textRole: "gameId"
            role: gameModel.roleId("gameId")
            width: 90
            visible: gameFilter.showAppId
        }
        KAddons.HeaderComponent {
            id: hcPlayed
            objectName: "hcPlayed"
            title: qsTr("Played")
            textRole: "gamePlayed"
            role: gameModel.roleId("gamePlayedSecs")
            width: 90
            visible: gameFilter.showPlayed
            itemDelegate: Controls.Label {
                verticalAlignment: Text.AlignVCenter
                text: modelData ?? ""
                elide: Text.ElideRight
                property bool rowSelected: false
                function refreshSelected() {
                    rowSelected = gameTable.selectionModel.isSelected(gameFilter.index(row, 0))
                }
                Component.onCompleted: refreshSelected()
                Connections {
                    target: gameTable.selectionModel
                    function onSelectionChanged() {
                        refreshSelected()
                    }
                }
                color: rowSelected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                HoverHandler {
                    id: playedHover
                }
                Controls.ToolTip.visible: playedHover.hovered
                Controls.ToolTip.text: model?.gamePlayedTip ?? ""
            }
        }
        KAddons.HeaderComponent {
            id: hcTier
            objectName: "hcTier"
            title: qsTr("ProtonDB")
            textRole: "gameTier"
            role: gameModel.roleId("gameTier")
            width: 110
            visible: gameFilter.showTier
            itemDelegate: Controls.ToolButton {
                text: modelData ?? ""
                font.bold: true
                property bool rowSelected: false
                function refreshSelected() {
                    rowSelected = gameTable.selectionModel.isSelected(gameFilter.index(row, 0))
                }
                Component.onCompleted: refreshSelected()
                Connections {
                    target: gameTable.selectionModel
                    function onSelectionChanged() {
                        refreshSelected()
                    }
                }
                background: Rectangle {
                    color: (model?.gameTier ?? "") !== "" ? model?.gameTierBg : "transparent"
                    radius: 4
                }
                contentItem: Controls.Label {
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: modelData ?? ""
                    color: rowSelected ? Kirigami.Theme.highlightedTextColor : ((model?.gameTier ?? "") !== "" ? model?.gameTierFg : Kirigami.Theme.textColor)
                    elide: Text.ElideRight
                }
                onClicked: gamesPage.select(gameFilter.idAt(row))
                onDoubleClicked: gameModel.openProtonDB(gameFilter.idAt(row))
                HoverHandler {
                    id: tierHover
                }
                Controls.ToolTip.visible: tierHover.hovered && (model?.gameTier ?? "") !== ""
                Controls.ToolTip.text: qsTr("Open ProtonDB page")
            }
        }
        KAddons.HeaderComponent {
            id: hcSource
            objectName: "hcSource"
            title: qsTr("Source")
            textRole: "gameSource"
            role: gameModel.roleId("gameSource")
            width: 80
            visible: gameFilter.showSource
        }
        headerComponents: [hcNum, hcGame, hcAppId, hcPlayed, hcTier, hcSource]
    }
    MouseArea {
        // Right-clicks on the header strip only (left passes to sort).
        objectName: "headerRightClick"
        anchors.top: gameTable.top
        anchors.left: gameTable.left
        anchors.right: gameTable.right
        height: gameTable.__rowHeight > 0 ? gameTable.__rowHeight : 36
        acceptedButtons: Qt.RightButton
        onClicked: headerMenu.popup()
    }
    Controls.Menu {
        id: headerMenu
        objectName: "headerMenu"
        Controls.MenuItem {
            text: qsTr("Show App ID")
            checkable: true
            checked: gameFilter.showAppId
            onTriggered: gameFilter.showAppId = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Played")
            checkable: true
            checked: gameFilter.showPlayed
            onTriggered: gameFilter.showPlayed = checked
        }
        Controls.MenuItem {
            text: qsTr("Show ProtonDB")
            checkable: true
            checked: gameFilter.showTier
            onTriggered: gameFilter.showTier = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Source")
            checkable: true
            checked: gameFilter.showSource
            onTriggered: gameFilter.showSource = checked
        }
        Controls.MenuSeparator {
        }
        Controls.MenuItem {
            text: qsTr("Configure Columns…")
            onTriggered: columnsDialog.open()
        }
    }
    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        visible: gamesPage.viewMode === "list" && gameTable.rowCount === 0
        text: qsTr("No games configured yet")
        explanation: qsTr("Add a game, scan the Steam library, or copy the launch options.")
    }
    RowLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 80
        visible: gamesPage.viewMode === "list" && gameTable.rowCount === 0
        Controls.Button {
            text: qsTr("Add Game...")
            onClicked: addDialog.open()
        }
        Controls.Button {
            objectName: "emptyScan"
            text: qsTr("Scan...")
            onClicked: {
                var cands = gameModel.scanCandidates()
                if (cands.length === 0) {
                    gamesPage.notify(
                        qsTr("Every Steam game is already configured."))
                    return
                }
                scanDialog.candidates = cands
                scanDialog.open()
            }
        }
        Controls.Button {
            text: qsTr("Copy Launch Options")
            onClicked: gamesPage.notify(gameModel.copyText("tkarcade %command%"))
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
            objectName: "statusLabel"
            text: {
                if (gamesPage.notice !== "") {
                    return gamesPage.notice
                }
                var base = qsTr("%1 configured · %2 Steam games detected").arg(
                    gameModel.totalCount).arg(gameModel.steamDetectedCount)
                var filtered = gameFilter.textQuery !== ""
                    || gameFilter.issuesOnly
                    || gameFilter.sourceKey !== "all"
                if (filtered) {
                    return base + qsTr(" · %1 shown").arg(gameFilter.rowCount())
                }
                return base
            }
        }
    }

    ColumnsDialog {
        id: columnsDialog
        objectName: "columnsDialog"
        page: gamesPage
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

    Kirigami.Dialog {
        id: scanDialog
        objectName: "scanDialog"
        title: qsTr("Add Games")
        padding: Kirigami.Units.largeSpacing
        property var candidates: []
        property var picked: []
        onCandidatesChanged: {
            var all = []
            for (var i = 0; i < candidates.length; i++) {
                all.push(candidates[i][0])
            }
            picked = all
        }
        ColumnLayout {
            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Steam games without a saved configuration:")
            }
            Repeater {
                model: scanDialog.candidates
                Controls.CheckBox {
                    required property var modelData
                    text: modelData[1] + " [" + modelData[0] + "]"
                    checked: scanDialog.picked.indexOf(modelData[0]) >= 0
                    onToggled: {
                        var kept = []
                        for (var i = 0; i < scanDialog.picked.length; i++) {
                            if (scanDialog.picked[i] !== modelData[0]) {
                                kept.push(scanDialog.picked[i])
                            }
                        }
                        if (checked) {
                            kept.push(modelData[0])
                        }
                        scanDialog.picked = kept
                    }
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "scanConfirm"
                text: qsTr("Add Selected")
                onClicked: {
                    var n = gameModel.addScanned(scanDialog.picked)
                    gamesPage.notify(qsTr("Added %1 game(s).").arg(n))
                    scanDialog.close()
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: scanDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: historyView
        objectName: "historyView"
        title: qsTr("Session History")
        padding: Kirigami.Units.largeSpacing
        property var rows: []
        ColumnLayout {
            ListView {
                objectName: "historyRows"
                Layout.preferredWidth: Kirigami.Units.gridUnit * 32
                Layout.preferredHeight: Kirigami.Units.gridUnit * 16
                clip: true
                model: historyView.rows
                delegate: RowLayout {
                    required property var modelData
                    width: ListView.view ? ListView.view.width : 100
                    Controls.Label {
                        objectName: "historyName"
                        Layout.fillWidth: true
                        text: modelData.name
                        elide: Text.ElideRight
                    }
                    Controls.Label {
                        text: modelData.last
                        opacity: 0.7
                    }
                    Controls.Label {
                        text: modelData.total
                    }
                    Controls.ToolButton {
                        objectName: "historyClear"
                        text: qsTr("Clear")
                        onClicked: {
                            gameModel.clearHistory(modelData.appid)
                            historyView.rows = gameModel.historySummary()
                        }
                    }
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Close")
                onClicked: historyView.close()
            }
        }
    }

    Kirigami.Dialog {
        id: prefsDialog
        objectName: "prefsDialog"
        title: qsTr("Preferences")
        padding: Kirigami.Units.largeSpacing
        property var values: ({})
        function load() {
            values = gameModel.loadPrefs()
            quickSpin.value = values.trayQuickCount ?? 5
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
            Controls.CheckBox {
                text: qsTr("Show launch command preview")
                checked: prefsDialog.values.showPreview ?? true
                onToggled: prefsDialog.setPref("showPreview", checked)
            }
            Controls.CheckBox {
                text: qsTr("Enable status bar icon")
                checked: prefsDialog.values.trayEnable ?? false
                onToggled: prefsDialog.setPref("trayEnable", checked)
            }
            RowLayout {
                Controls.Label {
                    text: qsTr("Tray icon style:")
                }
                Controls.ComboBox {
                    model: [qsTr("Normal"), qsTr("Monochrome")]
                    currentIndex: prefsDialog.values.trayIcon === "mono" ? 1 : 0
                    onActivated: (index) => prefsDialog.setPref(
                        "trayIcon", index === 1 ? "mono" : "normal")
                }
            }
            Controls.CheckBox {
                text: qsTr("Minimize to tray")
                checked: prefsDialog.values.minimizeToTray ?? false
                onToggled: prefsDialog.setPref("minimizeToTray", checked)
            }
            Controls.CheckBox {
                text: qsTr("Close to tray")
                checked: prefsDialog.values.closeToTray ?? false
                onToggled: prefsDialog.setPref("closeToTray", checked)
            }
            Controls.CheckBox {
                text: qsTr("Show recent games in tray menu")
                checked: prefsDialog.values.trayQuickLaunch ?? false
                onToggled: prefsDialog.setPref("trayQuickLaunch", checked)
            }
            RowLayout {
                Controls.Label {
                    text: qsTr("Recent games:")
                }
                Controls.SpinBox {
                    id: quickSpin
                    from: 1
                    to: 10
                    onValueChanged: prefsDialog.setPref("trayQuickCount", value)
                }
            }
            RowLayout {
                Controls.Label {
                    text: qsTr("SteamGridDB key:")
                }
                Controls.TextField {
                    echoMode: Controls.TextField.Password
                    placeholderText: qsTr("Free key from steamgriddb.com")
                    text: prefsDialog.values.sgdbApiKey ?? ""
                    onTextChanged: {
                        if (prefsDialog.values.sgdbApiKey !== text) {
                            prefsDialog.setPref("sgdbApiKey", text)
                        }
                    }
                }
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                objectName: "prefsSave"
                text: qsTr("Save")
                onClicked: {
                    if (gameModel.savePrefs(prefsDialog.values)) {
                        prefsDialog.close()
                    } else {
                        gamesPage.notify(qsTr("Could not save preferences."))
                    }
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: prefsDialog.close()
            }
        }
    }

    Kirigami.Dialog {
        id: aboutDialog
        objectName: "aboutDialog"
        title: qsTr("About TKArcade")
        padding: Kirigami.Units.largeSpacing
        ColumnLayout {
            Kirigami.SelectableLabel {
                Layout.fillWidth: true
                text: gameModel.aboutText()
            }
        }
        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Close")
                onClicked: aboutDialog.close()
            }
        }
    }
}
