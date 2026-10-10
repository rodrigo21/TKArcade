import QtQuick
import QtQml
import QtQml.Models as QQmlModels
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.kirigami.layouts as KL

// Games page: search + view split-button on top, the selected view
// below (details list, icons grid, or gallery-style cards), counts at
// the bottom. Plain Page (not ScrollablePage): ScrollablePage adopts a
// single Flickable child, so three switchable views need explicit
// geometry instead. Zoom and sort live in the arrow popup, Lutris-style.
Kirigami.Page {
    id: gamesPage
    objectName: "gamesPage"
    title: qsTr("Games")
    // Title slot carries buttons + filter (TKS has no title text): a
    // plain RowLayout honors fillWidth, so the filter stays centered
    // while the actions row (view icons) pins right at any width.
    titleDelegate: RowLayout {
        // Content-sized (no fill/preferred tug-of-war with the toolbar):
        // fixed elastics + fixed filter keep geometry identical at any
        // width, so nothing ever hides or overflows.
        spacing: Kirigami.Units.smallSpacing
        Controls.ToolButton {
            id: btnPlay
            objectName: "titlePlay"
            text: actionPlay.text
            icon.name: actionPlay.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered
            onClicked: gamesPage.playSelected()
        }
        Controls.ToolButton {
            id: btnAdd
            objectName: "titleAdd"
            text: actionAdd.text
            icon.name: actionAdd.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered
            onClicked: addDialog.open()
        }
        Controls.ToolButton {
            id: btnEdit
            objectName: "titleEdit"
            text: actionEdit.text
            icon.name: actionEdit.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered
            onClicked: addDialog.open()
        }
        Controls.ToolButton {
            id: btnRemove
            objectName: "titleRemove"
            text: actionRemove.text
            icon.name: actionRemove.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered
            onClicked: gamesPage.openRemoveDialog()
        }
        Item {
            objectName: "toolbarSpacerA"
            // Smaller twin: equal elastics center the filter B/2 off
            // (the buttons width pushes it right), so the left one
            // absorbs the buttons width back out.
            implicitWidth: Math.max(0, (gamesPage.width - titleReserve - 2 * (btnPlay.width + btnAdd.width + btnEdit.width + btnRemove.width
                + 3 * Kirigami.Units.smallSpacing) - gamesPage.titleFilterWidth) / 2)
        }
        Kirigami.SearchField {
            objectName: "searchField"
            // Page-based (never our own row width: that loops). Narrow
            // pages get a shorter filter so the icons still fit.
            // Shared with the elastics below (single source of truth).
            implicitWidth: gamesPage.titleFilterWidth
            placeholderText: qsTr("Filter by name or ID…")
            onTextChanged: gameFilter.textQuery = text
        }
        Item {
            objectName: "toolbarSpacerB"
            // Larger twin (see spacerA): with buttons+filter+title all
            // fixed, the icons toolbar keeps a constant ~170px room.
            implicitWidth: Math.max(0, (gamesPage.width - titleReserve - gamesPage.titleFilterWidth) / 2)
        }
    }
    // Flush against the window toolbar, like plasma-systemmonitor.
    topPadding: 0
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0

    property string viewMode: "list"
    property var viewSizes: ({icons: 96})
    property int iconSize: viewSizes["icons"] || 96
    property var selectedIds: []
    property string anchorId: ""
    property int hoveredRow: -1
    property string sortRole: "gameName"
    property bool sortDescending: false
    property string notice: ""
    property var appDrawer: null
    property var viewArrowItem: null
    property var toolbarIconsItem: null
    // Narrow windows show the four action buttons icon-only so the
    // filter and view icons still fit. Window-based (not page-based):
    // a collapsed drawer must not flip narrow windows back to text.
    property bool compactToolbar: (Controls.ApplicationWindow.window?.width ?? 0) < 1600
    // Title-row geometry (single source of truth). The reserve keeps
    // room for the icons toolbar at any size; the filter clamps to
    // [600, 1200] with a fit cap so the corner never overflows.
    property int titleReserve: 170
    property int titleButtonsGuess: compactToolbar ? 170 : 380
    property int titleFilterWant: Math.min(1200, Math.max(gamesPage.width < 1000 ? 240 : 600, gamesPage.width * 0.45))
    property int titleFilterWidth: gamesPage.width < 1000 ? 240 : Math.min(titleFilterWant, gamesPage.width - titleReserve - 2 * titleButtonsGuess - 20)

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

    function viewIcon() {
        if (viewMode === "icons") {
            return "view-list-icons"
        }
        if (viewMode === "cards") {
            return "view-grid"
        }
        return "view-list-details"
    }

    Shortcut {
        objectName: "viewShortcutList"
        sequence: "Ctrl+1"
        onActivated: gamesPage.viewMode = "list"
    }
    Shortcut {
        objectName: "viewShortcutIcons"
        sequence: "Ctrl+2"
        onActivated: gamesPage.viewMode = "icons"
    }
    Shortcut {
        objectName: "viewShortcutCards"
        sequence: "Ctrl+3"
        onActivated: gamesPage.viewMode = "cards"
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
        gamesPage.refreshColumnOrder()
        gameModel.fetchMissing()
        Qt.callLater(gamesPage.ensureSelection)
        if (TKARCADE_DEBUG_GEOMETRY === "1") {
            console.log("TKARCADE_GEOMETRY armed")
            geometryTimer.start()
        }
    }

    Timer {
        id: geometryTimer
        interval: 500
        repeat: true
        property int shots: 0
        onTriggered: {
            gamesPage.dumpGeometry()
            shots += 1
            if (shots >= 3) {
                stop()
            }
        }
    }

    function dumpGeometry() {
        var parts = []
        parts.push("table=" + gameTable.width + "x" + gameTable.height)
        for (var i = 0; i < headerRepeater.count; i++) {
            var cell = headerRepeater.itemAt(i)
            if (cell !== null) {
                parts.push(cell.logical + ":" + Math.round(cell.x) + "+" + Math.round(cell.width))
            }
        }
        var body = {}
        var stack = Array.prototype.slice.call(gameTable.children)
        while (stack.length > 0) {
            var item = stack.pop()
            if (item.row !== undefined && item.column !== undefined && item.row === 0
                    && body[item.column] === undefined && item.width > 0) {
                body[item.column] = Math.round(item.x) + "+" + Math.round(item.width)
            }
            var kids = item.children
            for (var k = 0; k < kids.length; k++) {
                stack.push(kids[k])
            }
        }
        var cols = Object.keys(body).sort(function(a, b) { return a - b })
        for (var c = 0; c < cols.length; c++) {
            parts.push("b" + cols[c] + ":" + body[cols[c]])
        }
        var bar = gamesPage.toolbarIconsItem !== null ? gamesPage.toolbarIconsItem.parent : null
        if (bar === null) {
            parts.push("bar=missing")
            console.log("TKARCADE_GEOMETRY " + parts.join(" "))
            return
        }
        var barbar = bar.parent
        var drawerW = gamesPage.appDrawer !== null ? Math.round(gamesPage.appDrawer.width) : -1
        parts.push("win=" + Math.round(gamesPage.width + (drawerW < 0 ? 0 : drawerW)))
        parts.push("bar=" + Math.round(barbar.width) + "/" + Math.round(bar.width))
        var counts = {}
        var kids = bar.children
        for (var d = 0; d < kids.length; d++) {
            var dit = kids[d]
            if (!dit.visible || !(dit.width > 0)) {
                continue
            }
            var label = dit.objectName
            if (label === "" && typeof dit.text === "string" && dit.text !== "") {
                label = dit.text
            }
            if (label === "") {
                var asText = String(dit)
                var paren = asText.indexOf("(")
                label = (paren > 0 ? asText.substring(0, paren) : asText) + "?button"
            }
            var key = label + "=" + Math.round(dit.x) + "+" + Math.round(dit.width)
            counts[key] = (counts[key] || 0) + 1
        }
        var seen = Object.keys(counts).sort()
        for (var s = 0; s < seen.length; s++) {
            var times = counts[seen[s]]
            parts.push("t:" + seen[s] + (times > 1 ? "x" + times : ""))
        }
        console.log("TKARCADE_GEOMETRY " + parts.join(" "))
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
            gamesPage.refreshColumnOrder()
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
        if (logical === 2) {
            return gameFilter.showAppId
        }
        if (logical === 3) {
            return gameFilter.showPlayed
        }
        if (logical === 4) {
            return gameFilter.showTier
        }
        if (logical === 5) {
            return gameFilter.showSource
        }
        return true
    }

    function columnSortRole(logical) {
        if (logical === 1) {
            return "gameName"
        }
        if (logical === 2) {
            return "gameId"
        }
        if (logical === 3) {
            return "gamePlayedSecs"
        }
        if (logical === 4) {
            return "gameTier"
        }
        if (logical === 5) {
            return "gameSource"
        }
        return ""
    }

    function sortGlyph(logical) {
        if (logical === 0 || columnSortRole(logical) !== sortRole) {
            return ""
        }
        return sortDescending ? "\u25BC" : "\u25B2"
    }

    function headerClicked(logical) {
        var role = columnSortRole(logical)
        if (role !== "") {
            toggleSort(role)
        }
    }

    function columnTitle(logical) {
        if (logical === 0) {
            // No title cell over the number gutter (TKS has none).
            return ""
        }
        if (logical === 1) {
            return qsTr("Game")
        }
        if (logical === 2) {
            return qsTr("App ID")
        }
        if (logical === 3) {
            return qsTr("Played")
        }
        if (logical === 4) {
            return qsTr("ProtonDB")
        }
        return qsTr("Source")
    }

    property var columnOrder: [0, 1, 2, 3, 4, 5] // JS mirror of the proxy
    // order (fresh JS array from JSON: QVariantList lays out at zero
    // width). Refreshed on start and on every columnsChanged.
    property int gameColumnWidth: 400

    function refreshColumnOrder() {
        columnOrder = JSON.parse(gameFilter.columnOrderJson())
    }

    function moveColumn(logical, dir) {
        gameFilter.moveColumn(logical, dir)
    }

    function resetColumns() {
        gameFilter.resetColumns()
        gameFilter.showAppId = true
        gameFilter.showPlayed = true
        gameFilter.showTier = true
        gameFilter.showSource = true
    }

    function tableColumnWidth(logical) {
        if (!columnVisible(logical)) {
            return 0
        }
        if (logical === 0) {
            return 36
        }
        if (logical === 1) {
            return gameColumnWidth
        }
        if (logical === 2 || logical === 3) {
            return 90
        }
        if (logical === 4) {
            return 110
        }
        return 80
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
            gameColumnWidth = Math.max(120, gameTable.width - fixedColumnsWidth())
        }
        gameTable.forceLayout()
    }

    // Trigger targets feeding the title buttons (labels/icons stay
    // in one place). Only the icons row lives in the actions toolbar.
    Kirigami.Action {
        id: actionPlay
        objectName: "actionPlay"
        text: qsTr("Play")
        icon.name: "media-playback-start"
        onTriggered: gamesPage.playSelected()
    }
    Kirigami.Action {
        id: actionAdd
        objectName: "actionAdd"
        text: qsTr("Add game")
        icon.name: "list-add"
        onTriggered: addDialog.open()
    }
    Kirigami.Action {
        // TEMPORARY: opens the local add dialog until the QML
        // game settings UI lands.
        id: actionEdit
        objectName: "actionEdit"
        text: qsTr("Edit...")
        icon.name: "document-edit"
        onTriggered: addDialog.open()
    }
    Kirigami.Action {
        id: actionRemove
        objectName: "actionRemove"
        text: qsTr("Remove")
        icon.name: "edit-delete"
        onTriggered: gamesPage.openRemoveDialog()
    }
    // View controls only: toolbarActionAlignment pins them right at any
    // window width; buttons + filter live in the title row.
    actions: [
        Kirigami.Action {
            displayHint: KL.DisplayHint.KeepVisible
            displayComponent: RowLayout {
                id: iconsRow
                objectName: "toolbarIcons"
                Layout.minimumWidth: implicitWidth
                spacing: 0
                Component.onCompleted: {
                    // displayComponent scope hides ids: publish for popups.
                    gamesPage.viewArrowItem = viewArrow
                    gamesPage.toolbarIconsItem = iconsRow
                }
                Controls.ToolButton {
                    id: viewButton
                    objectName: "viewButton"
                    icon.name: gamesPage.viewIcon()
                    display: Controls.AbstractButton.IconOnly
                    onClicked: gamesPage.cycleView()
                }
                Controls.ToolButton {
                    id: viewArrow
                    objectName: "viewArrow"
                    text: "▼"
                    // Deferred past the release: opening synchronously
                    // lets the same release dismiss the popup instantly.
                    onClicked: Qt.callLater(viewOptions.open)
                }
                Controls.ToolButton {
                    objectName: "columnsButton"
                    icon.name: "view-column"
                    display: Controls.AbstractButton.IconOnly
                    onClicked: columnsDialog.open()
                }
                Controls.ToolButton {
                    objectName: "hamburgerButton"
                    icon.name: "overflow-menu"
                    // Same release-dismiss race as above.
                    onClicked: Qt.callLater(hamburgerMenu.popup)
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
                                    }
                                    Controls.MenuItem {
                                        objectName: "issuesOnly"
                                        text: qsTr("With issues only")
                                        checkable: true
                                        checked: gameFilter.issuesOnly
                                        onTriggered: gameFilter.issuesOnly = checked
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
                icon.name: "view-list-details"
                checked: gamesPage.viewMode === "list"
                Controls.ButtonGroup.group: viewGroup
                onToggled: gamesPage.viewMode = "list"
            }
            Controls.RadioButton {
                text: qsTr("Icons")
                icon.name: "view-list-icons"
                checked: gamesPage.viewMode === "icons"
                Controls.ButtonGroup.group: viewGroup
                onToggled: gamesPage.viewMode = "icons"
            }
            Controls.RadioButton {
                text: qsTr("Cards")
                icon.name: "view-grid"
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

    // Flush rounded frame around the table (TKS look): no margins, so
    // its top edge never reads as a second header separator.
    Item {
        anchors.fill: parent
        visible: gamesPage.viewMode === "list"
        Rectangle {
            objectName: "listFrame"
            anchors.fill: parent
            color: "transparent"
            border.width: 1
            border.color: Kirigami.Theme.textColor
            opacity: 0.25
            radius: Kirigami.Units.smallSpacing / 2
        }
        // Gutter back strip, full table height: the framed number
        // column continues through rows and the empty area (TKS).
        // Declared below the table so delegates (and selection)
        // paint above it.
        Item {
            objectName: "gutterBackStrip"
            anchors.top: listLayout.top
            anchors.topMargin: tableHeader.height
            anchors.bottom: listLayout.bottom
            anchors.left: parent.left
            width: gamesPage.tableColumnWidth(0)
            Kirigami.Theme.colorSet: Kirigami.Theme.Button
            Kirigami.Theme.inherit: false
            Rectangle {
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }
        }
        ColumnLayout {
            id: listLayout
            anchors.fill: parent
            spacing: 0

        Item {
            id: tableHeader
            objectName: "tableHeader"
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2
            Kirigami.Theme.colorSet: Kirigami.Theme.Button
            Kirigami.Theme.inherit: false
            Rectangle {
                // Full-bleed bar behind the titles (covers the row).
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }
            RowLayout {
                anchors.fill: parent
                spacing: 0
            Repeater {
                id: headerRepeater
                model: gamesPage.columnOrder
                delegate: Item {
                    required property int modelData
                    property int logical: modelData
                    objectName: "headerCell" + logical
                    // Inline expression (reactive): a tableColumnWidth()
                    // call would freeze at first evaluation.
                    Layout.preferredWidth: {
                        if (logical === 0) {
                            return 36
                        }
                        if (logical === 1) {
                            return gamesPage.gameColumnWidth
                        }
                        if (logical === 2) {
                            return gameFilter.showAppId ? 90 : 0
                        }
                        if (logical === 3) {
                            return gameFilter.showPlayed ? 90 : 0
                        }
                        if (logical === 4) {
                            return gameFilter.showTier ? 110 : 0
                        }
                        return gameFilter.showSource ? 80 : 0
                    }
                    Layout.fillHeight: true
                    visible: Layout.preferredWidth > 0
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: Kirigami.Units.smallSpacing
                        anchors.rightMargin: Kirigami.Units.smallSpacing
                        Controls.Label {
                            Layout.fillWidth: true
                            text: gamesPage.columnTitle(logical)
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            font.bold: true
                            color: Kirigami.Theme.textColor
                        }
                    }
                    // TKS-style sort mark: small, overlaid at the right
                    // edge, vertically centered, so the title stays put.
                    Controls.Label {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.rightMargin: Kirigami.Units.smallSpacing
                        text: gamesPage.sortGlyph(logical)
                        visible: text !== ""
                        font: Kirigami.Theme.smallFont
                        color: Kirigami.Theme.textColor
                    }
                    Rectangle {
                        // No stub between gutter and game columns (TKS
                        // has no gutter column); the corner junction of
                        // header line and body line marks the edge.
                        visible: logical !== 0
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 1
                        color: Kirigami.Theme.textColor
                        opacity: 0.18
                    }
                    TapHandler {
                        acceptedButtons: Qt.LeftButton
                        onTapped: gamesPage.headerClicked(logical)
                    }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.RightButton
                        onClicked: headerMenu.popup()
                    }
                }
            }
        }
        // Grid line under the header row: starts past the gutter
        // (TKS has no gutter column) and spans the rest.
        // NOTE: plain call on purpose (gutter width is constant).
        Rectangle {
            objectName: "tableHeaderBottomLine"
            anchors.left: parent.left
            anchors.leftMargin: gamesPage.tableColumnWidth(0)
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Kirigami.Theme.textColor
            opacity: 0.18
        }
        }

        TableView {
            id: gameTable
            objectName: "gameTable"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: gameFilter
            selectionModel: QQmlModels.ItemSelectionModel {
                model: gameFilter
            }
            columnWidthProvider: function(column) {
                return gamesPage.tableColumnWidth(gameFilter.columnLogical(column))
            }
            delegate: Item {
                required property int row
                required property int column
                property int logical: gameFilter.columnLogical(column)
                implicitWidth: {
                    // Match the visible cell: text paints outside a wrong
                    // box, but clicks do not land. Keep in sync with the
                    // header widths above.
                    if (logical === 0) {
                        return 36
                    }
                    if (logical === 1) {
                        return gamesPage.gameColumnWidth
                    }
                    if (logical === 2 || logical === 3) {
                        return 90
                    }
                    if (logical === 4) {
                        return 110
                    }
                    return 80
                }
                implicitHeight: Kirigami.Units.gridUnit * 2
                // Selection highlighting reads page state directly:
                // selectedIds is the single source of truth and stays
                // reactive without any row index.
                property bool isSelected: gamesPage.selectedIds.indexOf(model?.gameId ?? "") >= 0
                Rectangle {
                    anchors.fill: parent
                    visible: isSelected
                    color: Kirigami.Theme.highlightColor
                }
                // TKS-style hover: light wash behind unselected rows.
                Rectangle {
                    anchors.fill: parent
                    visible: !isSelected && gamesPage.hoveredRow === row
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.25
                }
                HoverHandler {
                    onHoveredChanged: {
                        if (hovered) {
                            gamesPage.hoveredRow = row
                        } else if (gamesPage.hoveredRow === row) {
                            gamesPage.hoveredRow = -1
                        }
                    }
                }
                // number gutter: vertical-header look (Button set,
                // like the column titles), clicks still select the row
                Item {
                    visible: logical === 0
                    anchors.fill: parent
                    Kirigami.Theme.colorSet: Kirigami.Theme.Button
                    Kirigami.Theme.inherit: false
                    Rectangle {
                        anchors.fill: parent
                        color: isSelected ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                    }
                    Rectangle {
                        anchors.fill: parent
                        visible: !isSelected && gamesPage.hoveredRow === row
                        color: Kirigami.Theme.highlightColor
                        opacity: 0.25
                    }
                    Controls.Label {
                        anchors.fill: parent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: true
                        color: isSelected ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                        text: row + 1
                    }
                    RowClickHandler {
                        page: gamesPage
                        gid: model?.gameId ?? ""
                    }
                }
                // game: icon plus name
                Item {
                    visible: logical === 1
                    anchors.fill: parent
                    RowClickHandler {
                        page: gamesPage
                        gid: model?.gameId ?? ""
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
                            text: model?.gameName ?? ""
                            color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            elide: Text.ElideRight
                        }
                    }
                }
                // plain text columns
                Controls.Label {
                    visible: logical === 2 || logical === 5
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: Kirigami.Units.smallSpacing
                    text: logical === 2 ? (model?.gameId ?? "") : (model?.gameSource ?? "")
                    color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    elide: Text.ElideRight
                    RowClickHandler {
                        page: gamesPage
                        gid: model?.gameId ?? ""
                    }
                }
                // played (with session tooltip)
                Controls.Label {
                    visible: logical === 3
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: Kirigami.Units.smallSpacing
                    text: model?.gamePlayed ?? ""
                    color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    elide: Text.ElideRight
                    RowClickHandler {
                        page: gamesPage
                        gid: model?.gameId ?? ""
                    }
                    HoverHandler {
                        id: playedHover
                    }
                    Controls.ToolTip.visible: playedHover.hovered
                    Controls.ToolTip.text: model?.gamePlayedTip ?? ""
                }
                // ProtonDB tier badge
                Controls.ToolButton {
                    visible: logical === 4
                    anchors.fill: parent
                    text: model?.gameTier ?? ""
                    font.bold: true
                    background: Rectangle {
                        color: isSelected ? Kirigami.Theme.highlightColor : ((model?.gameTier ?? "") !== "" ? model?.gameTierBg : "transparent")
                        radius: 4
                    }
                    contentItem: Controls.Label {
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        text: model?.gameTier ?? ""
                        color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : ((model?.gameTier ?? "") !== "" ? model?.gameTierFg : Kirigami.Theme.textColor)
                        elide: Text.ElideRight
                    }
                    onClicked: gamesPage.select(model?.gameId ?? "")
                    onDoubleClicked: gameModel.openProtonDB(model?.gameId ?? "")
                    HoverHandler {
                        id: tierHover
                    }
                    Controls.ToolTip.visible: tierHover.hovered && (model?.gameTier ?? "") !== ""
                    Controls.ToolTip.text: qsTr("Open ProtonDB page")
                }
                // source (logical 5 shares the plain label above)
            }
            Keys.onUpPressed: {
                gamesPage.moveTableSelection(-1)
            }
            Keys.onDownPressed: {
                gamesPage.moveTableSelection(1)
            }
            onWidthChanged: gamesPage.fitGameColumn()
        }
        }
        // Gutter divider overlay: above delegates and highlight, never
        // scrolls; same box as the per-cell dividers ([gutter - 1, gutter]).
        Rectangle {
            objectName: "gutterFullLine"
            anchors.top: listLayout.top
            anchors.topMargin: tableHeader.height
            anchors.bottom: listLayout.bottom
            x: gamesPage.tableColumnWidth(0) - 1
            width: 1
            color: Kirigami.Theme.textColor
            opacity: 0.18
        }
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
        visible: gamesPage.viewMode === "list" && gameFilter.rowCount() === 0
        text: qsTr("No games configured yet")
        explanation: qsTr("Add a game, scan the Steam library, or copy the launch options.")
    }
    RowLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 80
        visible: gamesPage.viewMode === "list" && gameFilter.rowCount() === 0
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
            // Clear the footer separator above and the window edge below;
            // left offset steps off the drawer divider tip.
            leftPadding: Kirigami.Units.smallSpacing
            topPadding: Kirigami.Units.smallSpacing
            bottomPadding: Kirigami.Units.smallSpacing
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
