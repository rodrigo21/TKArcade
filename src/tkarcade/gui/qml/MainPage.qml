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
    property string selectedId: ""
    property string sortRole: "gameName"
    property bool sortDescending: false

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
        selectedId = gid
        var row = gameFilter.indexOf(gid)
        gameList.currentIndex = row
        iconGrid.currentIndex = row
    }

    actions: [
        Kirigami.Action {
            text: qsTr("Add game")
            icon.name: "list-add"
            onTriggered: addDialog.open()
        }
    ]

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

    ListView {
        id: gameList
        objectName: "gameList"
        anchors.fill: parent
        visible: gamesPage.viewMode === "list"
        model: gameFilter
        property int rowHeight: gamesPage.rowHeight
        property var colW: ({appId: 90, played: 90, tier: 110, source: 80})
        clip: true
        focus: true
        onCurrentIndexChanged: {
            if (gameList.currentIndex >= 0) {
                gamesPage.selectedId = gameFilter.idAt(gameList.currentIndex)
            }
        }
        Keys.onUpPressed: {
            gameList.currentIndex = Math.max(0, gameList.currentIndex - 1)
            gameList.positionViewAtIndex(gameList.currentIndex, ListView.Contain)
        }
        Keys.onDownPressed: {
            gameList.currentIndex = Math.min(gameList.count - 1, gameList.currentIndex + 1)
            gameList.positionViewAtIndex(gameList.currentIndex, ListView.Contain)
        }
        header: Item {
            width: gameList.width
            height: headerRow.height
            Rectangle {
                anchors.fill: parent
                color: Kirigami.Theme.alternateBackgroundColor
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Kirigami.Theme.disabledTextColor
                opacity: 0.4
            }
        RowLayout {
            id: headerRow
            anchors.fill: parent
            spacing: Kirigami.Units.largeSpacing
            Controls.Label {
                Layout.preferredWidth: 36
                horizontalAlignment: Text.AlignHCenter
                color: Kirigami.Theme.disabledTextColor
                font.bold: true
                text: "#"
            }
            Item {
                Layout.preferredWidth: gamesPage.rowHeight - 8
                Layout.preferredHeight: 1
            }
            Controls.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
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
                horizontalAlignment: Text.AlignHCenter
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
                horizontalAlignment: Text.AlignHCenter
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
                horizontalAlignment: Text.AlignHCenter
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
                horizontalAlignment: Text.AlignHCenter
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
        }
        delegate: GameDelegate {
            width: ListView.view ? ListView.view.width : 100
            selected: gamesPage.selectedId === gameId
            onPlayRequested: (gid) => gameModel.play(gid)
            onRowTapped: (gid) => gamesPage.select(gid)
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: gameList.count === 0
            text: qsTr("No games yet")
            explanation: qsTr("Add a native Linux game to get started.")
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
        onCurrentIndexChanged: {
            if (iconGrid.currentIndex >= 0) {
                gamesPage.selectedId = gameFilter.idAt(iconGrid.currentIndex)
            }
        }
        Keys.onUpPressed: iconGrid.moveCurrentIndexUp()
        Keys.onDownPressed: iconGrid.moveCurrentIndexDown()
        Keys.onLeftPressed: iconGrid.moveCurrentIndexLeft()
        Keys.onRightPressed: iconGrid.moveCurrentIndexRight()
        delegate: GameIconDelegate {
            width: GridView.view ? GridView.view.cellWidth : 100
            height: GridView.view ? GridView.view.cellHeight : 100
            cellSize: gamesPage.iconSize
            selected: gamesPage.selectedId === gameId
            onPlayRequested: (gid) => gameModel.play(gid)
            onRowTapped: (gid) => gamesPage.select(gid)
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
                        selected: gamesPage.selectedId === gameId
                        onPlayRequested: (gid) => gameModel.play(gid)
                        onRowTapped: (gid) => gamesPage.select(gid)
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
            text: qsTr("%1 configured · %2 Steam games detected").arg(gameModel.totalCount).arg(gameModel.steamDetectedCount)
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
}
