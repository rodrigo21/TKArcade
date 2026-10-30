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
    // Focus-chain quit: fires even where the Shortcut map stays silent.
    // Ctrl+A only reaches here when the focused item did not take it (a
    // text field selects its own text first).
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Q && (event.modifiers & Qt.ControlModifier)) {
            event.accepted = true
            Qt.quit()
        } else if (event.matches(StandardKey.SelectAll)) {
            event.accepted = true
            gamesPage.selectAllGames()
        }
    }
    title: qsTr("Games")
    // Title slot carries buttons + filter (TKS has no title text): a
    // plain RowLayout honors fillWidth, so the filter stays centered
    // while the actions row (view icons) pins right at any width.
    titleDelegate: RowLayout {
        id: titleRow
        // Content-sized (no fill/preferred tug-of-war with the toolbar):
        // fixed elastics + fixed filter keep geometry identical at any
        // width, so nothing ever hides or overflows.
        spacing: Kirigami.Units.smallSpacing
        // The filter cap follows the real button widths. A fixed guess
        // left translated labels (wider than English) pushing the
        // actions row into overflow; the ids live in this Component,
        // so the page scope cannot measure them.
        property real buttonsWidth: btnPlay.implicitWidth + btnAdd.implicitWidth + btnEdit.implicitWidth + btnRemove.implicitWidth
        property int filterWidth: Math.max(240, Math.min(gamesPage.titleFilterWant, gamesPage.width - gamesPage.titleReserve - 2 * buttonsWidth - 6 * Kirigami.Units.smallSpacing))
        Controls.ToolButton {
            id: btnPlay
            objectName: "titlePlay"
            text: actionPlay.text
            icon.name: actionPlay.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered && gamesPage.compactToolbar
            onClicked: gamesPage.playSelected()
        }
        Controls.ToolButton {
            id: btnAdd
            objectName: "titleAdd"
            text: actionAdd.text
            icon.name: actionAdd.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered && gamesPage.compactToolbar
            onClicked: addGameDialog.open()
        }
        Controls.ToolButton {
            id: btnEdit
            objectName: "titleEdit"
            text: actionEdit.text
            icon.name: actionEdit.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered && gamesPage.compactToolbar
            onClicked: gamesPage.openSettingsForSelection()
        }
        Controls.ToolButton {
            id: btnRemove
            objectName: "titleRemove"
            text: actionRemove.text
            icon.name: actionRemove.icon.name
            display: gamesPage.compactToolbar ? Controls.AbstractButton.IconOnly : Controls.AbstractButton.TextBesideIcon
            Controls.ToolTip.text: gamesPage.compactToolbar ? text : ""
            Controls.ToolTip.visible: hovered && gamesPage.compactToolbar
            onClicked: gamesPage.openRemoveDialog()
        }
        Item {
            objectName: "toolbarSpacerA"
            // Smaller twin: equal elastics center the filter B/2 off
            // (the buttons width pushes it right), so the left one
            // absorbs the buttons width back out. Zeroed on tiny
            // pages: fitting beats centering there.
            implicitWidth: gamesPage.width < 800 ? 0 : Math.max(0, (gamesPage.width - titleReserve - 2 * (titleRow.buttonsWidth
                + 3 * Kirigami.Units.smallSpacing) - titleRow.filterWidth) / 2)
        }
        Kirigami.SearchField {
            objectName: "searchField"
            // Page-based (never our own row width: that loops). Narrow
            // pages get a shorter filter so the icons still fit.
            // Shared with the elastics below (single source of truth).
            implicitWidth: titleRow.filterWidth
            placeholderText: qsTr("Filter by Name or ID…")
            onTextChanged: gameFilter.textQuery = text
        }
        Item {
            objectName: "toolbarSpacerB"
            // Larger twin (see spacerA): with buttons+filter+title all
            // fixed, the icons toolbar keeps a constant ~170px room.
            // Zeroed on tiny pages with its twin.
            implicitWidth: gamesPage.width < 800 ? 0 : Math.max(0, (gamesPage.width - titleReserve - titleRow.filterWidth) / 2)
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
    // Sticky status line (widgets QLabel): "Launched X." stayed until the
    // next message, while `notice` is the transient one.
    property string statusMessage: ""
    property var appDrawer: null
    property var viewArrowItem: null
    property var toolbarIconsItem: null
    // Narrow windows show the four action buttons icon-only so the
    // filter and view icons still fit. Window-based (not page-based):
    // a collapsed drawer must not flip narrow windows back to text.
    property bool compactToolbar: (Controls.ApplicationWindow.window?.width ?? 0) < 1600
    // Title-row geometry (single source of truth). The reserve keeps
    // room for the icons toolbar at any size (+handle room in overlay,
    // where the drawer button joins the header); the filter clamps to
    // [600, 1200] with a fit cap so the corner never overflows. The cap
    // itself lives on the title row, which can measure the buttons.
    property int titleReserve: (gamesPage.appDrawer && gamesPage.appDrawer.modal && !gamesPage.appDrawer.collapsible) ? 218 : 170
    property int titleFilterWant: Math.min(1200, Math.max(gamesPage.width < 1000 ? 240 : 600, gamesPage.width * 0.45))

    onViewModeChanged: {
        if (viewMode === "list") {
            // `selectedIds` is the only source of truth: the TableView clears
            // its selection model while it is hidden and clears it again when
            // it comes back (measured), so the mirror is re-applied once the
            // view has settled and never read back.
            Qt.callLater(gamesPage.applySelectionToTable)
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
        // QSortFilterProxyModel.sort() does not make TableView re-request
        // its rows (measured: the view stays one order behind). Force the
        // layout so the first click already shows the new order.
        gameTable.forceLayout()
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

    // Qt item views scrollTo() only reveal an off-screen row, and by the
    // least amount. Centering on every selection moved the clicked row out
    // from under the cursor, so a double-click's second click landed on a
    // different game. Mouse paths never scroll; the keyboard pairs this
    // with tableSelectAndReveal().
    function ensureTableRowVisible(row) {
        var h = tableRowHeight()
        var top = h * row
        var maxY = Math.max(0, gameTable.contentHeight - gameTable.height)
        if (top < gameTable.contentY) {
            gameTable.contentY = Math.min(maxY, top)
        } else if (top + h > gameTable.contentY + gameTable.height) {
            gameTable.contentY = Math.min(maxY, top + h - gameTable.height)
        }
    }

    // Keyboard parity with QTableView: select, then bring the row into
    // view.
    function tableSelectAndReveal(row) {
        tableSingleSelect(row)
        ensureTableRowVisible(row)
    }

    function tableSingleSelect(row) {
        if (row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var gid = gameFilter.idAt(row)
        selectedIds = [gid]
        anchorId = gid
        var index = gameFilter.proxyIndex(row)
        gameTable.selectionModel.setCurrentIndex(
            index,
            QQmlModels.ItemSelectionModel.ClearAndSelect | selectFlags())
    }

    function tableToggleRow(row) {
        if (row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var index = gameFilter.proxyIndex(row)
        gameTable.selectionModel.setCurrentIndex(
            index, QQmlModels.ItemSelectionModel.Toggle | selectFlags())
    }

    function tableRangeSelect(row) {
        var anchor = gameFilter.indexOf(anchorId)
        if (anchor < 0 || row < 0 || row >= gameFilter.rowCount()) {
            return
        }
        var from = Math.min(anchor, row)
        var to = Math.max(anchor, row)
        var range = []
        for (var r = from; r <= to; r++) {
            range.push(gameFilter.idAt(r))
        }
        selectedIds = range
        gameTable.selectionModel.clearSelection()
        for (var s = from; s <= to; s++) {
            gameTable.selectionModel.select(
                gameFilter.proxyIndex(s),
                QQmlModels.ItemSelectionModel.Select | selectFlags())
        }
        gameTable.selectionModel.setCurrentIndex(
            gameFilter.proxyIndex(row), QQmlModels.ItemSelectionModel.NoUpdate)
    }

    function tablePageRows() {
        // Qt item views page by the rows that fit the viewport.
        return Math.max(1, Math.floor(gameTable.height / tableRowHeight()))
    }

    function moveTableSelectionPage(delta) {
        moveTableSelection(delta * tablePageRows())
    }

    function moveTableSelection(delta) {
        var current = gameTable.selectionModel.currentIndex
        var row = current !== undefined && current.valid ? current.row : 0
        row = Math.max(0, Math.min(gameFilter.rowCount() - 1, row + delta))
        tableSelectAndReveal(row)
    }

    function gridColumns() {
        return Math.max(1, Math.floor(iconGrid.width / iconGrid.cellWidth))
    }

    function moveGridPage(delta) {
        var step = gridColumns() * Math.max(1, Math.floor(iconGrid.height / iconGrid.cellHeight))
        var count = iconGrid.count
        if (count === 0) {
            return
        }
        var target = Math.max(0, Math.min(count - 1, iconGrid.currentIndex + delta * step))
        iconGrid.currentIndex = target
        select(gameFilter.idAt(target))
    }

    function select(gid) {
        selectedIds = [gid]
        anchorId = gid
        syncIndexes(gid)
    }

    // Ctrl+A (widgets QTableView/QListWidget parity): every row the filter
    // shows. The table mirror takes the whole set through
    // applySelectionToTable.
    function selectAllGames() {
        var ids = []
        for (var i = 0; i < gameFilter.rowCount(); i++) {
            ids.push(gameFilter.idAt(i))
        }
        selectedIds = ids
        anchorId = ids.length > 0 ? ids[0] : ""
        if (viewMode === "list") {
            applySelectionToTable()
        } else if (viewMode === "icons") {
            iconGrid.currentIndex = 0
        }
    }

    // Clicking outside the rows drops the selection: the widgets
    // QTableView cleared its selection on a viewport click that hit no
    // model index. Called from the table's and the grid's empty area.
    function clearSelection() {
        selectedIds = []
        anchorId = ""
        if (gameTable.selectionModel !== null) {
            gameTable.selectionModel.clearSelection()
        }
        iconGrid.currentIndex = -1
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
        // The page owns the selection: keep the ids the model still has
        // (nothing is read back from the table's selection model) and put
        // the table mirror back when the list view is the one on screen.
        var kept = []
        for (var i = 0; i < selectedIds.length; i++) {
            if (gameFilter.indexOf(selectedIds[i]) >= 0) {
                kept.push(selectedIds[i])
            }
        }
        selectedIds = kept
        if (selectedIds.length === 0 && gameFilter.rowCount() > 0) {
            select(gameFilter.idAt(0))
        } else if (viewMode === "list") {
            gamesPage.applySelectionToTable()
        }
    }

    function playSelected() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select a Game First."))
            return
        }
        gameModel.play(selectedIds[0])
    }

    function openSettingsForSelection() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select a Game First."))
            return
        }
        gamesPage.openGameSettings(selectedIds[0])
    }

    // Every shell dialog is a separate modal window on the main one
    // (ConfirmDialog.qml, DialogWindow.qml).
    function openDialog(dialog) {
        dialog.open(Controls.ApplicationWindow.window)
    }


    function openRemoveDialog() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select Games First."))
            return
        }
        gamesPage.openDialog(removeDialog)
    }

    property string cloneSrc: ""
    property var cloneRows: []
    property string cloneDest: ""
    property var resetRows: []

    function openCloneDialog(gid) {
        cloneSrc = gid
        var rows = gameModel.cloneTargets(gid)
        var fresh = []
        for (var i = 0; i < rows.length; i++) {
            fresh.push(rows[i][1] + " [" + rows[i][0] + "]")
        }
        cloneRows = fresh
        gamesPage.openDialog(cloneDialog)
    }

    function openResetDialog() {
        if (selectedIds.length === 0) {
            gamesPage.notify(qsTr("Select Games First."))
            return
        }
        resetRows = selectedIds.slice()
        gamesPage.openDialog(resetDialog)
    }

    function acceptBulkCats() {
        gamesPage.notify(gameModel.setCategories(selectedIds, bulkCatsField.text))
        bulkCatsDialog.close()
    }

    function acceptClone() {
        var dest = cloneBox.editText.trim()
        if (dest === "") {
            return
        }
        var msg = gameModel.cloneGameTo(cloneSrc, dest, false)
        if (msg === "OVERWRITE") {
            cloneDest = dest
            gamesPage.openDialog(overwriteDialog)
            return
        }
        if (msg !== "") {
            gamesPage.notify(msg)
        }
        cloneDialog.close()
    }

    property string validateGid: ""
    property string validateName: ""
    property var validateIssues: []

    function openValidateDialog(gid) {
        validateGid = gid
        var report = gameModel.validateReport(gid)
        validateName = report.name ?? gid
        validateIssues = report.issues ?? []
        if (validateIssues.length === 0) {
            gamesPage.notify(qsTr("No Issues Found for %1.").arg(validateName))
            return
        }
        validateDialog.open(Controls.ApplicationWindow.window)
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
        gamesPage.refreshColumnWidths()
        // Fresh profile (nothing fitted yet): show content, capped.
        if (gameFilter.columnWidthsJson() === "{}") {
            gameFilter.fitDefaults()
        }
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
        target: gameFilter
        function onColumnsChanged() {
            gamesPage.refreshColumnOrder()
            gamesPage.fitGameColumn()
        }
        function onWidthsChanged() {
            gamesPage.refreshColumnWidths()
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

    property string browsePurpose: ""

    Connections {
        target: gameModel
        function onBrowseFinished(picked) {
            if (picked === "" || gamesPage.browsePurpose === "") {
                return
            }
            if (gamesPage.browsePurpose === "exportSave") {
                var msg = gameModel.exportTarball(picked)
                if (msg !== "") {
                    gamesPage.notify(msg)
                }
            }
            gamesPage.browsePurpose = ""
        }
    }

    // Terminate feedback: the launcher stops the game and the indicator
    // clears itself on the next poll.
    Connections {
        target: gameModel
        function onTerminateReported(ok, name, detail) {
            if (ok) {
                gamesPage.statusMessage = qsTr("Stopping %1...").arg(name)
            } else if (detail !== "") {
                gamesPage.notify(qsTr("Could Not Stop %1: %2").arg(name).arg(detail))
            } else {
                gamesPage.notify(qsTr("Could Not Stop %1.").arg(name))
            }
        }
    }

    // Launch reporting for every path (toolbar, menus, delegates, tray):
    // the widgets status line said "Launched X." and warned on a failed
    // handoff; the QML shell keeps the warnings transient.
    Connections {
        target: gameModel
        function onLaunchReported(ok, kind, name, detail) {
            if (ok) {
                gamesPage.statusMessage = qsTr("Launched %1.").arg(name)
                return
            }
            if (kind === "steam") {
                gamesPage.notify(qsTr("Could Not Ask Steam to Launch the Game."))
            } else if (detail !== "") {
                gamesPage.notify(qsTr("Could Not Launch %1: %2").arg(name).arg(detail))
            } else {
                gamesPage.notify(qsTr("Could Not Launch %1.").arg(name))
            }
        }
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
            return gameFilter.showOrigin
        }
        if (logical === 6) {
            return gameFilter.showLastPlayed
        }
        if (logical === 7) {
            return gameFilter.showPlatform
        }
        if (logical === 8) {
            return gameFilter.showRuntime
        }
        if (logical === 9) {
            return gameFilter.showWine
        }
        if (logical === 10) {
            return gameFilter.showInstallDir
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
            return "gameOrigin"
        }
        if (logical === 6) {
            return "gameLastSecs"
        }
        if (logical === 7) {
            return "gamePlatform"
        }
        if (logical === 8) {
            return "gameRuntime"
        }
        if (logical === 9) {
            return "gameWine"
        }
        if (logical === 10) {
            return "gameInstallDir"
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
        if (logical === 5) {
            return qsTr("Origin")
        }
        if (logical === 6) {
            return qsTr("Last Played")
        }
        if (logical === 7) {
            return qsTr("Platform")
        }
        if (logical === 8) {
            return qsTr("Runtime")
        }
        if (logical === 9) {
            return qsTr("Wine")
        }
        if (logical === 10) {
            return qsTr("Install Dir")
        }
        return ""
    }

    property var columnOrder: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] // JS mirror of the proxy
    // order (fresh JS array from JSON: QVariantList lays out at zero
    // width). Refreshed on start and on every columnsChanged.
    property var fittedColumnWidths: ({}) // logical -> px, same mirror rule
    property int fittedColumnWidthsRev: 0 // bumped with the mirror:
    // element reads on a var do not retrack reassignment alone
    property real columnShrink: 1.0 // <1 squeezes fixed columns to fit
    property int gameColumnWidth: 400

    function refreshColumnOrder() {
        columnOrder = JSON.parse(gameFilter.columnOrderJson())
    }

    function refreshColumnWidths() {
        fittedColumnWidths = JSON.parse(gameFilter.columnWidthsJson())
        fittedColumnWidthsRev += 1
    }

    // A QVariantList straight from the model lays out at zero width in a
    // Repeater: callers get a fresh JS array (docs/QML-NOTES.md).
    function freshRows(rows) {
        return JSON.parse(JSON.stringify(rows))
    }

    function headerCellX(logical) {
        // Cumulative offset in view order (hidden columns take no
        // space). Reads live widths every run; callers pin a rev
        // read so the binding reschedules on width changes.
        var x = 0
        var order = columnOrder
        for (var i = 0; i < order.length; i++) {
            if (order[i] === logical) {
                return x
            }
            x += tableColumnWidth(order[i])
        }
        return x
    }

    function autofitColumn(logical) {
        gameFilter.autofitColumn(logical)
    }

    function moveColumn(logical, dir) {
        gameFilter.moveColumn(logical, dir)
    }

    function dropColumn(logical, dx) {
        // Reorder by drag: convert the cell-local drag distance into a
        // drop slot in view order, then step-swap there (each step
        // persists through moveColumn).
        var from = columnOrder.indexOf(logical)
        if (from < 0) {
            return
        }
        var dropX = headerCellX(logical) + tableColumnWidth(logical) / 2 + dx
        var x = 0
        var to = columnOrder.length - 1
        for (var i = 0; i < columnOrder.length; i++) {
            var w = tableColumnWidth(columnOrder[i])
            if (dropX < x + w) {
                to = i
                break
            }
            x += w
        }
        var step = to > from ? 1 : -1
        var guard = columnOrder.length + 1
        while (from !== to && guard-- > 0) {
            gameFilter.moveColumn(logical, step)
            refreshColumnOrder()
            from = columnOrder.indexOf(logical)
        }
    }

    function resetColumns() {
        gameFilter.resetColumns()
        gameFilter.showAppId = true
        gameFilter.showPlayed = true
        gameFilter.showTier = true
        gameFilter.showOrigin = true
        gameFilter.showLastPlayed = true
        gameFilter.showPlatform = false
        gameFilter.showRuntime = false
        gameFilter.showWine = false
        gameFilter.showInstallDir = false
    }

    function defaultColumnWidth(logical) {
        // Static fallback (px, unshrunk) for columns with no fitted
        // width. Single source of truth: baseColumnWidth feeds
        // columnWidthProvider (what the table renders), and the header
        // cells plus the delegate implicitWidth must match it exactly.
        // They diverged when the 6-11 library columns landed (the
        // header lumped them with 2/3 at 90px, the table used 80px), so
        // every such column shifted its title by 10px.
        if (logical === 2 || logical === 3) {
            return 90
        }
        if (logical === 4) {
            return 110
        }
        return 80
    }

    function baseColumnWidth(logical) {
        // Unshrunk fitted-or-default (0 when hidden); game excluded,
        // it fills elastically with its fitted value as floor.
        if (!columnVisible(logical) || logical === 1) {
            return 0
        }
        if (logical === 0) {
            return 36
        }
        var fitted = gameFilter.columnWidth(logical)
        if (fitted > 0) {
            return fitted
        }
        return defaultColumnWidth(logical)
    }

    function tableColumnWidth(logical) {
        if (!columnVisible(logical)) {
            return 0
        }
        // Game always rides gameColumnWidth (fitted floor, fills rest).
        if (logical === 1) {
            return gameColumnWidth
        }
        return Math.max(24, baseColumnWidth(logical) * columnShrink)
    }

    function fitGameColumn() {
        if (gameTable.width <= 0) {
            return
        }
        var base = 0
        for (var l of [2, 3, 4, 5, 6, 7, 8, 9, 10]) {
            base += baseColumnWidth(l)
        }
        var gameFit = gameFilter.columnWidth(1)
        var gameMin = gameFit > 0 ? gameFit : 120
        var avail = gameTable.width - 36 - gameMin
        columnShrink = (base <= 0 || avail >= base) ? 1.0 : Math.max(0.15, avail / base)
        var fixed = 36
        for (var l2 of [2, 3, 4, 5, 6, 7, 8, 9, 10]) {
            // Hidden columns take no space (the 24px floor is for
            // visible narrow columns only).
            if (columnVisible(l2)) {
                fixed += Math.max(24, baseColumnWidth(l2) * columnShrink)
            }
        }
        gameColumnWidth = Math.max(gameMin, gameTable.width - fixed)
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
        text: qsTr("Add Game")
        icon.name: "list-add"
        onTriggered: addGameDialog.open()
    }
    Kirigami.Action {
        id: actionEdit
        objectName: "actionEdit"
        text: qsTr("Edit...")
        icon.name: "document-edit"
        onTriggered: gamesPage.openSettingsForSelection()
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
                    icon.name: gameModel.iconName(["view-column", "view-split-left-right", "configure"])
                    display: Controls.AbstractButton.IconOnly
                    onClicked: gamesPage.openDialog(columnsDialog)
                }
                Controls.ToolButton {
                    objectName: "hamburgerButton"
                    icon.name: gameModel.iconName(["overflow-menu", "application-menu"])
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
                                                    qsTr("Every Steam Game Is Already Configured."))
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
                                        text: qsTr("With Issues Only")
                                        checkable: true
                                        checked: gameFilter.issuesOnly
                                        onTriggered: gameFilter.issuesOnly = checked
                                    }
                                    Controls.MenuSeparator {
                                    }
                                    // Widgets Tools menu, same order: Validate
                                    // Game leads the tool entries.
                                    Controls.MenuItem {
                                        objectName: "menuValidate"
                                        text: qsTr("Validate Game")
                                        onTriggered: {
                                            if (gamesPage.selectedIds.length === 0) {
                                                gamesPage.notify(qsTr("Select a Game First."))
                                                return
                                            }
                                            gamesPage.openValidateDialog(gamesPage.selectedIds[0])
                                        }
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
                                                gamesPage.notify(qsTr("Could Not Open the Logs Folder."))
                                            }
                                        }
                                    }
                                    Controls.MenuItem {
                                        text: qsTr("Clean Up Leftovers...")
                                        onTriggered: {
                                            var rows = gamesPage.freshRows(
                                                gameModel.orphanedLeftovers())
                                            if (rows.length === 0) {
                                                gamesPage.notify(qsTr("No Leftovers Found."))
                                                return
                                            }
                                            cleanupDialog.rows = rows
                                            gamesPage.openDialog(cleanupDialog)
                                        }
                                    }
                                    Controls.MenuItem {
                                        objectName: "menuExport"
                                        text: qsTr("Export...")
                                        onTriggered: {
                                            gamesPage.browsePurpose = "exportSave"
                                            gameModel.pickSavePath(qsTr("Export Configurations"), qsTr("Save"), "tkarcade-configs.tar.gz")
                                        }
                                    }
                                    Controls.MenuItem {
                                        objectName: "menuImport"
                                        text: qsTr("Import...")
                                        onTriggered: importDialog.open()
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
                                        objectName: "menuDefaults"
                                        text: qsTr("Global Defaults...")
                                        onTriggered: gamesPage.openDefaultsSettings()
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
                text: qsTr("Sort By")
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
                text: qsTr("Origin")
                checked: gamesPage.sortRole === "gameOrigin"
                Controls.ButtonGroup.group: sortGroup
                onToggled: gamesPage.setSort("gameOrigin", gamesPage.sortDescending)
            }
            Controls.CheckBox {
                text: qsTr("Reverse Order")
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
            objectName: "menuTerminate"
            // runningIds is the notifying half: isRunning() is a plain call.
            visible: gamesPage.selectedIds.length <= 1
                && gameModel.runningIds.indexOf(gamesPage.menuGid) >= 0
            text: qsTr("Terminate")
            onTriggered: gameModel.terminate(gamesPage.menuGid)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Edit Settings")
            onTriggered: gamesPage.openGameSettings(gamesPage.menuGid)
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
            onTriggered: {
                if (!gameModel.openPath(gamesPage.menuInstall)) {
                    gamesPage.notify(qsTr("Could Not Open the Install Folder."))
                }
            }
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            enabled: gamesPage.menuPrefix !== ""
            text: qsTr("Open Proton Prefix")
            onTriggered: {
                if (!gameModel.openPath(gamesPage.menuPrefix)) {
                    gamesPage.notify(qsTr("Could Not Open the Prefix Folder."))
                }
            }
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            enabled: gamesPage.menuShader !== ""
            text: qsTr("Clear Shader Cache")
            onTriggered: gamesPage.openDialog(shaderDialog)
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
            onTriggered: gamesPage.openDialog(historyDialog)
        }
        Controls.MenuItem {
            visible: gamesPage.selectedIds.length <= 1
            text: qsTr("Clone Settings To...")
            onTriggered: gamesPage.openCloneDialog(gamesPage.menuGid)
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
        Controls.MenuItem {
            text: qsTr("Reset to Global Defaults")
            onTriggered: gamesPage.openResetDialog()
        }
        Controls.MenuItem {
            text: qsTr("Set Categories…")
            onTriggered: {
                if (gamesPage.selectedIds.length === 0) {
                    gamesPage.notify(qsTr("Select Games First."))
                    return
                }
                bulkCatsField.text = ""
                gamesPage.openDialog(bulkCatsDialog)
            }
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
            // Widgets parity: no table header over the empty state.
            visible: gameFilter.rowCount() > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2
            clip: true
            Kirigami.Theme.colorSet: Kirigami.Theme.Button
            Kirigami.Theme.inherit: false
            Rectangle {
                // Full-bleed bar behind the titles (covers the row).
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }
            Item {
                id: headerRow
                objectName: "headerRow"
                // Manual x per cell below (headerCellX): neither Row
                // nor RowLayout reschedules on child width edits.
                // Follows the table sideways so titles stay over
                // their columns when the bar scrolls past the edge.
                x: -gameTable.contentX
                anchors.top: parent.top
                anchors.bottom: parent.bottom
            Repeater {
                id: headerRepeater
                model: gamesPage.columnOrder
                delegate: Item {
                    required property int modelData
                    property int logical: modelData
                    objectName: "headerCell" + logical
                    // Manual tiling: positioners do not reschedule on
                    // child width edits, so x tracks the live widths.
                    x: {
                        gamesPage.fittedColumnWidthsRev
                        return gamesPage.headerCellX(logical)
                    }
                    // Plain width tracked live (see x above); kept out
                    // of any positioner on purpose.
                    width: {
                        gamesPage.fittedColumnWidthsRev
                        if (!columnVisible(logical)) {
                            return 0
                        }
                        if (logical === 0) {
                            return 36
                        }
                        // Game always rides gameColumnWidth (see above).
                        if (logical === 1) {
                            return gamesPage.gameColumnWidth
                        }
                        var fw = gamesPage.fittedColumnWidths[logical] || 0
                        var base = fw > 0 ? fw : gamesPage.defaultColumnWidth(logical)
                        return Math.max(24, base * gamesPage.columnShrink)
                    }
                    height: parent.height
                    visible: width > 0
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
                    MouseArea {
                        // Separator interaction: hover cursor, drag to
                        // resize, double-click to autofit. Accepts the
                        // press, so the cell TapHandler never sees this
                        // 9px strip (no sorting from the divider).
                        objectName: "headerDivider" + logical
                        visible: logical !== 0
                        z: 10
                        anchors.right: parent.right
                        anchors.rightMargin: -4
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 9
                        acceptedButtons: Qt.LeftButton
                        hoverEnabled: true
                        cursorShape: Qt.SplitHCursor
                        preventStealing: true
                        property real dragStartX: 0
                        property int dragStartW: 0
                        // Double-click autofits on second press; the
                        // release that follows must not re-apply the
                        // drag position over it.
                        property bool autofitted: false
                        onPressed: (mouse) => {
                            dragStartX = mouse.x
                            dragStartW = gamesPage.tableColumnWidth(logical)
                        }
                        onPositionChanged: (mouse) => {
                            if (pressed) {
                                gameFilter.setColumnWidth(logical, Math.round(Math.max(40, dragStartW + mouse.x - dragStartX)))
                            }
                        }
                        onReleased: (mouse) => {
                            if (autofitted) {
                                autofitted = false
                                return
                            }
                            // Re-apply at release: the final move can
                            // coalesce behind the release event.
                            gameFilter.setColumnWidth(logical, Math.round(Math.max(40, dragStartW + mouse.x - dragStartX)))
                            gameFilter.saveColumnWidths()
                        }
                        // Double-click autofits (the TapHandler below
                        // never sees this strip: the press is ours).
                        onDoubleClicked: {
                            autofitted = true
                            gamesPage.autofitColumn(logical)
                        }
                    }
                    MouseArea {
                        // Title drag: press-move past the threshold reorders
                        // the column on release; a plain tap sorts instead
                        // (the old TapHandler folded in here so one gesture
                        // owns the press). Never from the divider strip.
                        objectName: "headerMove" + logical
                        anchors.fill: parent
                        anchors.rightMargin: 9
                        acceptedButtons: Qt.LeftButton
                        preventStealing: true
                        property real pressX: 0
                        property bool dragging: false
                        onPressed: (mouse) => {
                            pressX = mouse.x
                            dragging = false
                        }
                        onPositionChanged: (mouse) => {
                            if (pressed && !dragging && Math.abs(mouse.x - pressX) > 12) {
                                dragging = true
                            }
                        }
                        onReleased: (mouse) => {
                            if (!dragging) {
                                if (mouse.x < parent.width - 9) {
                                    gamesPage.headerClicked(logical)
                                }
                                return
                            }
                            dragging = false
                            gamesPage.dropColumn(logical, mouse.x - pressX)
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.RightButton
                        onClicked: headerMenu.popup()
                    }
                }
            }
        }
        // Grid line under the header row, full width like the foot rule.
        Rectangle {
            objectName: "tableHeaderBottomLine"
            anchors.left: parent.left
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
            // The view owns the arrow keys (the widgets QTableView had
            // focus): the built-in navigation would move the current
            // index behind the page's own selection bookkeeping.
            focus: gamesPage.viewMode === "list"
            keyNavigationEnabled: false
            // Drag/autofit can push content past the edge: an
            // as-needed bar brings the outer columns back.
            Controls.ScrollBar.horizontal: Controls.ScrollBar {
                objectName: "tableHScroll"
                policy: Controls.ScrollBar.AsNeeded
            }
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
                    gamesPage.fittedColumnWidthsRev
                    if (!gamesPage.columnVisible(logical)) {
                        return 0
                    }
                    if (logical === 0) {
                        return 36
                    }
                    // Game always rides gameColumnWidth (see above).
                    if (logical === 1) {
                        return gamesPage.gameColumnWidth
                    }
                    var fw = gamesPage.fittedColumnWidths[logical] || 0
                    var base = fw > 0 ? fw : gamesPage.defaultColumnWidth(logical)
                    return Math.max(24, base * gamesPage.columnShrink)
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
                                // Fill the 32x32 cell: official Steam art is
                                // the client icon (square) or a 460x215
                                // header, which would otherwise become a
                                // thin band with empty bars around it.
                                fillMode: Image.PreserveAspectCrop
                            }
                            Kirigami.Icon {
                                anchors.centerIn: parent
                                visible: (model?.gameIcon ?? "") === ""
                                source: gameModel.iconName(["input-gamepad", "applications-games"])
                                width: 20
                                height: 20
                            }
                        }
                        Controls.Label {
                            objectName: "gameNameCell"
                            Layout.fillWidth: true
                            verticalAlignment: Text.AlignVCenter
                            text: model?.gameName ?? ""
                            color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                            elide: Text.ElideRight
                        }
                        // Running indicator: a small play glyph, so the
                        // name column keeps its width for the name.
                        Kirigami.Icon {
                            objectName: "runningIndicator"
                            visible: model?.gameRunning ?? false
                            source: "media-playback-start"
                            color: Kirigami.Theme.positiveTextColor
                            Layout.preferredWidth: Kirigami.Units.iconSizes.small
                            Layout.preferredHeight: Kirigami.Units.iconSizes.small
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }
                }
                // plain text columns (App ID, Source and the library
                // columns: Last Played, Platform, Runtime, Wine, Install
                // Dir)
                Controls.Label {
                    objectName: "cellText" + logical
                    visible: [2, 5, 6, 7, 8, 9, 10].indexOf(logical) >= 0
                    anchors.fill: parent
                    verticalAlignment: Text.AlignVCenter
                    leftPadding: Kirigami.Units.smallSpacing
                    text: {
                        if (logical === 2) {
                            return model?.gameId ?? ""
                        }
                        if (logical === 5) {
                            return model?.gameOrigin ?? ""
                        }
                        if (logical === 6) {
                            return model?.gameLastPlayed ?? ""
                        }
                        if (logical === 7) {
                            return model?.gamePlatform ?? ""
                        }
                        if (logical === 8) {
                            return model?.gameRuntime ?? ""
                        }
                        if (logical === 9) {
                            return model?.gameWine ?? ""
                        }
                        if (logical === 10) {
                            return model?.gameInstallDir ?? ""
                        }
                        return ""
                    }
                    color: gamesPage.selectedIds.indexOf(model?.gameId ?? '') >= 0 ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
                    elide: Text.ElideRight
                    RowClickHandler {
                        page: gamesPage
                        gid: model?.gameId ?? ""
                    }
                    HoverHandler {
                        id: textColumnHover
                    }
                    // Truncated paths/tags: show the whole value.
                    Controls.ToolTip.visible: textColumnHover.hovered
                        && logical === 10 && text !== ""
                    Controls.ToolTip.text: text
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
                    Controls.ToolTip.visible: playedHover.hovered && (model?.gamePlayedTip ?? "") !== ""
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
                    Controls.ToolTip.text: qsTr("Open ProtonDB Page")
                }
                // source (logical 5 shares the plain label above)
            }
            Keys.onUpPressed: {
                gamesPage.moveTableSelection(-1)
            }
            Keys.onDownPressed: {
                gamesPage.moveTableSelection(1)
            }
            // Qt item-view keys (QTableView parity): Home/End and a page.
            // The Keys type has no home/end/page signals, so these arrive
            // through the generic handler.
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Home) {
                    event.accepted = true
                    gamesPage.tableSelectAndReveal(0)
                } else if (event.key === Qt.Key_End) {
                    event.accepted = true
                    gamesPage.tableSelectAndReveal(gameFilter.rowCount() - 1)
                } else if (event.key === Qt.Key_PageUp) {
                    event.accepted = true
                    gamesPage.moveTableSelectionPage(-1)
                } else if (event.key === Qt.Key_PageDown) {
                    event.accepted = true
                    gamesPage.moveTableSelectionPage(1)
                }
            }
            onWidthChanged: gamesPage.fitGameColumn()

            // Empty area of the viewport (below the last row): a tap there
            // drops the selection. A handler, not a MouseArea: the view's
            // Flickable swallows clicks on its own background, and a
            // Flickable's children live in the scrolling content (which
            // here is shorter than the viewport).
            TapHandler {
                objectName: "tableEmptyTap"
                onTapped: gamesPage.clearSelection()
            }
        }
        }
        // Foot rule above the status line: same hairline family as
        // the header lines (the status label reserves its padding).
        Rectangle {
            objectName: "tableFooterTopLine"
            anchors.left: listLayout.left
            anchors.right: listLayout.right
            anchors.bottom: listLayout.bottom
            height: 1
            color: Kirigami.Theme.textColor
            opacity: 0.18
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
            text: qsTr("Show Origin")
            checkable: true
            checked: gameFilter.showOrigin
            onTriggered: gameFilter.showOrigin = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Last Played")
            checkable: true
            checked: gameFilter.showLastPlayed
            onTriggered: gameFilter.showLastPlayed = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Platform")
            checkable: true
            checked: gameFilter.showPlatform
            onTriggered: gameFilter.showPlatform = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Runtime")
            checkable: true
            checked: gameFilter.showRuntime
            onTriggered: gameFilter.showRuntime = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Wine")
            checkable: true
            checked: gameFilter.showWine
            onTriggered: gameFilter.showWine = checked
        }
        Controls.MenuItem {
            text: qsTr("Show Install Dir")
            checkable: true
            checked: gameFilter.showInstallDir
            onTriggered: gameFilter.showInstallDir = checked
        }
        Controls.MenuSeparator {
        }
        Controls.MenuItem {
            text: qsTr("Configure Columns…")
            onTriggered: gamesPage.openDialog(columnsDialog)
        }
        Controls.MenuItem {
            // Widgets header menu closed with Reset Columns.
            objectName: "menuResetColumns"
            text: qsTr("Reset Columns")
            onTriggered: gamesPage.resetColumns()
        }
    }
    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        visible: gamesPage.viewMode === "list" && gameFilter.rowCount() === 0
        text: qsTr("No Games Configured Yet")
        explanation: qsTr("1. Add a Steam Game · 2. Edit Its Settings · 3. Set Its Steam Launch Options to tkarcade %command%")
    }
    RowLayout {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 80
        visible: gamesPage.viewMode === "list" && gameFilter.rowCount() === 0
        Controls.Button {
            text: qsTr("Add Game...")
            onClicked: addGameDialog.open()
        }
        Controls.Button {
            objectName: "emptyImport"
            text: qsTr("Import...")
            onClicked: importDialog.open()
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
        // The view in front owns the keys (the widgets QListWidget in icon
        // mode had focus); the arrows were dead without it.
        focus: gamesPage.viewMode === "icons"
        model: gameFilter
        clip: true
        cellWidth: gamesPage.iconSize + Kirigami.Units.largeSpacing * 2
        cellHeight: gamesPage.iconSize + 64
        onCountChanged: gamesPage.ensureSelection()
        // Qt item-view keys: arrows move the current cell, Home/End jump
        // to the ends, Page keys move a screenful.
        Keys.onUpPressed: {
            iconGrid.moveCurrentIndexUp()
            gamesPage.select(gameFilter.idAt(iconGrid.currentIndex))
        }
        Keys.onDownPressed: {
            iconGrid.moveCurrentIndexDown()
            gamesPage.select(gameFilter.idAt(iconGrid.currentIndex))
        }
        Keys.onLeftPressed: {
            iconGrid.moveCurrentIndexLeft()
            gamesPage.select(gameFilter.idAt(iconGrid.currentIndex))
        }
        Keys.onRightPressed: {
            iconGrid.moveCurrentIndexRight()
            gamesPage.select(gameFilter.idAt(iconGrid.currentIndex))
        }
        // Keys has no home/end/page signals: the generic handler.
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Home) {
                event.accepted = true
                iconGrid.currentIndex = 0
                gamesPage.select(gameFilter.idAt(0))
            } else if (event.key === Qt.Key_End) {
                event.accepted = true
                iconGrid.currentIndex = iconGrid.count - 1
                gamesPage.select(gameFilter.idAt(iconGrid.count - 1))
            } else if (event.key === Qt.Key_PageUp) {
                event.accepted = true
                gamesPage.moveGridPage(-1)
            } else if (event.key === Qt.Key_PageDown) {
                event.accepted = true
                gamesPage.moveGridPage(1)
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
            onSettingsRequested: (gid) => gamesPage.openGameSettings(gid)
        }
        // Empty area of the viewport: a tap drops the selection (handler,
        // not a MouseArea -- see the table's empty-area handler).
        TapHandler {
            objectName: "gridEmptyTap"
            onTapped: gamesPage.clearSelection()
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: iconGrid.count === 0
            text: qsTr("No Games Yet")
            explanation: qsTr("Add a Native Linux Game to Get Started.")
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
                        onSettingsRequested: (gid) => gamesPage.openGameSettings(gid)
                        onTerminateRequested: (gid) => gameModel.terminate(gid)
                    }
                }
            }
            Kirigami.PlaceholderMessage {
                Layout.fillWidth: true
                visible: gameFilter.rowCount() === 0
                text: qsTr("No Games Yet")
                explanation: qsTr("Add a Native Linux Game to Get Started.")
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
                if (gamesPage.statusMessage !== "") {
                    return gamesPage.statusMessage
                }
                var base = qsTr("%1 Configured · %2 Steam Games Detected").arg(
                    gameModel.totalCount).arg(gameModel.steamDetectedCount)
                var filtered = gameFilter.textQuery !== ""
                    || gameFilter.issuesOnly
                    || gameFilter.sourceKey !== "all"
                    || gameFilter.categoryKey !== ""
                if (filtered) {
                    return base + qsTr(" · %1 Shown").arg(gameFilter.rowCount())
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

    GameSettings {
        id: gameSettings
    }

    AddDialog {
        id: addGameDialog
        page: gamesPage
    }

    ImportDialog {
        id: importDialog
        page: gamesPage
    }

    function openGameSettings(appid) {
        gameSettings.page = gamesPage
        gameSettings.transientParent = Controls.ApplicationWindow.window
        gameSettings.openFor(appid)
    }

    function openNewGameSettings(runtimeType) {
        gameSettings.page = gamesPage
        gameSettings.transientParent = Controls.ApplicationWindow.window
        gameSettings.openNew(runtimeType)
    }

    // The Global Defaults editor (same window in defaults mode), reachable
    // from the tray and the hamburger like the widgets Settings menu.
    function openDefaultsSettings() {
        gameSettings.page = gamesPage
        gameSettings.transientParent = Controls.ApplicationWindow.window
        gameSettings.openDefaults()
    }

    function settingsOpen() {
        return gameSettings.visible
    }

    ConfirmDialog {
        id: removeDialog
        objectName: "removeDialog"
        title: qsTr("Remove Games")
        question: gamesPage.selectedIds.length === 1
            ? qsTr("Remove the Configuration for %1?").arg(
                gameModel.gameNames(gamesPage.selectedIds)[0])
            : qsTr("Remove the Configurations for %1 Games?").arg(
                gamesPage.selectedIds.length)
        acceptText: qsTr("Remove")
        onAccepted: {
            var targets = gamesPage.selectedIds.slice()
            var err = gameModel.removeGames(targets)
            if (err !== "") {
                gamesPage.notify(err)
            }
            var leftovers = gamesPage.freshRows(gameModel.leftoverData(targets))
            gamesPage.ensureSelection()
            removeDialog.close()
            if (leftovers.length > 0) {
                cleanupDialog.rows = leftovers
                gamesPage.openDialog(cleanupDialog)
            }
        }
    }

    ConfirmDialog {
        id: cleanupDialog
        objectName: "cleanupDialog"
        title: qsTr("Clean Up Leftovers")
        question: qsTr("These Games Were Removed but Still Have Profiles or Logs:")
        acceptText: qsTr("Clean Selected")
        rejectText: qsTr("Keep All")
        property var rows: []
        property var picked: []
        property bool deletePrefixes: false

        function label(row) {
            return row.name + " (" + row.appid + ")"
        }

        function summary(row) {
            var parts = []
            if (row.profiles > 0) {
                parts.push(qsTr("%1 Profile(s)").arg(row.profiles))
            }
            if (row.session_log) {
                parts.push(qsTr("Session Log"))
            }
            if (row.proton_log) {
                parts.push(qsTr("Proton Log"))
            }
            if (row.history > 0) {
                parts.push(qsTr("%1 Session(s)").arg(row.history))
            }
            if (row.prefix !== "") {
                parts.push(qsTr("Prefix"))
            }
            return parts.join(" · ")
        }

        function hasPrefix() {
            for (var i = 0; i < rows.length; i++) {
                if ((rows[i].prefix ?? "") !== "") {
                    return true
                }
            }
            return false
        }

        onRowsChanged: {
            var ids = []
            for (var i = 0; i < rows.length; i++) {
                ids.push(rows[i].appid)
            }
            picked = ids
            deletePrefixes = false
        }
        ColumnLayout {
            objectName: "cleanupList"
            Layout.fillWidth: true
            Repeater {
                model: cleanupDialog.rows
                delegate: ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Controls.CheckBox {
                        objectName: "cleanupItem" + modelData.appid
                        Layout.fillWidth: true
                        text: cleanupDialog.label(modelData)
                        checked: cleanupDialog.picked.indexOf(modelData.appid) >= 0
                        onToggled: {
                            var kept = []
                            for (var i = 0; i < cleanupDialog.picked.length; i++) {
                                if (cleanupDialog.picked[i] !== modelData.appid) {
                                    kept.push(cleanupDialog.picked[i])
                                }
                            }
                            if (checked) {
                                kept.push(modelData.appid)
                            }
                            cleanupDialog.picked = kept
                        }
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        Layout.leftMargin: Kirigami.Units.gridUnit * 1.5
                        visible: text !== ""
                        text: cleanupDialog.summary(modelData)
                        font: Kirigami.Theme.smallFont
                        opacity: 0.7
                        wrapMode: Text.WordWrap
                    }
                }
            }
            Controls.CheckBox {
                objectName: "cleanupPrefixes"
                Layout.fillWidth: true
                visible: cleanupDialog.hasPrefix()
                text: qsTr("Also Delete the Proton/Wine Prefix (Large and Cannot Be Undone)")
                checked: cleanupDialog.deletePrefixes
                onToggled: cleanupDialog.deletePrefixes = checked
            }
        }
        onAccepted: {
            var n = gameModel.cleanLeftovers(
                cleanupDialog.picked, cleanupDialog.deletePrefixes)
            gamesPage.notify(
                qsTr("Cleaned Leftovers for %1 Game(s).").arg(n))
            cleanupDialog.close()
        }
    }

    ConfirmDialog {
        id: shaderDialog
        objectName: "shaderDialog"
        title: qsTr("Clear Shader Cache")
        question: qsTr("Delete %1 of Shader Cache for %2? Steam Rebuilds It on Demand.").arg(
            gamesPage.menuShaderSize).arg(gamesPage.menuGid)
        acceptText: qsTr("Delete")
        onAccepted: {
            gamesPage.notify(gameModel.clearShaderCache(gamesPage.menuGid))
            shaderDialog.close()
        }
    }

    ConfirmDialog {
        id: historyDialog
        objectName: "historyDialog"
        title: qsTr("Clear History")
        question: qsTr("Clear Session History for %1? This Cannot Be Undone.").arg(
            gamesPage.menuGid)
        acceptText: qsTr("Clear")
        onAccepted: {
            var n = gameModel.clearHistory(gamesPage.menuGid)
            gamesPage.notify(qsTr("Cleared %1 Session(s).").arg(n))
            historyDialog.close()
        }
    }

    DialogWindow {
        id: validateDialog
        objectName: "validateDialog"
        title: qsTr("Validate Game: %1").arg(gamesPage.validateName)
        acceptVisible: false
        rejectText: qsTr("Close")
        Controls.Label {
            objectName: "validateIssues"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: gamesPage.validateIssues.map(function(issue) {
                return "• " + issue
            }).join("\n")
        }
    }

    DialogWindow {
        id: cloneDialog
        objectName: "cloneDialog"
        title: qsTr("Clone Settings")
        acceptText: qsTr("Clone")
        onAccepted: gamesPage.acceptClone()
        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Clone into Game:")
        }
        Controls.ComboBox {
            id: cloneBox
            objectName: "cloneBox"
            editable: true
            Layout.fillWidth: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            model: gamesPage.cloneRows
        }
    }

    ConfirmDialog {
        id: overwriteDialog
        objectName: "overwriteDialog"
        title: qsTr("Clone Settings")
        question: qsTr("Overwrite the Saved Settings for %1?").arg(gamesPage.cloneDest)
        acceptText: qsTr("Overwrite")
        onAccepted: {
            var msg = gameModel.cloneGameTo(gamesPage.cloneSrc, gamesPage.cloneDest, true)
            if (msg !== "") {
                gamesPage.notify(msg)
            }
            overwriteDialog.close()
            cloneDialog.close()
        }
    }

    DialogWindow {
        id: bulkCatsDialog
        objectName: "bulkCatsDialog"
        title: qsTr("Set Categories")
        acceptText: qsTr("OK")
        onAccepted: gamesPage.acceptBulkCats()
        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Comma-Separated Tags (Empty Clears). Applies to %1 Game(s).").arg(
                gamesPage.selectedIds.length)
        }
        Controls.TextField {
            id: bulkCatsField
            objectName: "bulkCatsField"
            placeholderText: qsTr("Action, Retro")
            Layout.fillWidth: true
            Layout.preferredWidth: Kirigami.Units.gridUnit * 20
            onAccepted: gamesPage.acceptBulkCats()
        }
    }

    ConfirmDialog {
        id: resetDialog
        objectName: "resetDialog"
        title: qsTr("Reset to Global Defaults")
        question: qsTr("Reset %1 Game(s) to the Global Defaults Template Now?").arg(
            gamesPage.resetRows.length)
        detail: qsTr("This Overwrites Their Saved Configs (Profiles Are Kept).")
        acceptText: qsTr("Reset")
        onAccepted: {
            gamesPage.notify(gameModel.resetGames(gamesPage.resetRows))
            resetDialog.close()
        }
    }

    ScanDialog {
        id: scanDialog
        page: gamesPage
    }

    HistoryView {
        id: historyView
    }

    PrefsDialog {
        id: prefsDialog
        page: gamesPage
    }

    AboutDialog {
        id: aboutDialog
    }
}
