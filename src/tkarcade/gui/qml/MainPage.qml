import QtQuick
import QtQml
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Games list page: view switcher + search on top, sortable column
// header, rows below, counts at the bottom. Future views (icons,
// covers, banner) plug into viewMode/viewSizes; only "list" renders.
Kirigami.ScrollablePage {
    id: gamesPage
    objectName: "gamesPage"
    title: qsTr("Games")

    property string viewMode: "list"
    property var viewSizes: ({list: 40})
    property int rowHeight: viewSizes[viewMode] || 40
    property string sortRole: "gameName"
    property bool sortDescending: false

    function toggleSort(role) {
        if (sortRole === role) {
            sortDescending = !sortDescending
        } else {
            sortRole = role
            sortDescending = false
        }
        gameFilter.sortBy(sortRole, sortDescending)
    }

    function sortMark(role) {
        return sortRole === role ? (sortDescending ? "▼ " : "▲ ") : ""
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
            Controls.ComboBox {
                id: viewPicker
                objectName: "viewPicker"
                Layout.preferredWidth: 140
                model: [qsTr("List"), qsTr("Icons (soon)"), qsTr("Covers (soon)"), qsTr("Banner (soon)")]
                onActivated: (index) => {
                    if (index === 0) {
                        gamesPage.viewMode = "list"
                    } else {
                        // Future views land here; bounce back for now.
                        viewPicker.currentIndex = 0
                    }
                }
            }
            Controls.Slider {
                id: sizeSlider
                objectName: "sizeSlider"
                Layout.preferredWidth: 120
                from: 32
                to: 64
                stepSize: 4
                value: gamesPage.rowHeight
                onMoved: {
                    var sizes = {}
                    for (var k in gamesPage.viewSizes) {
                        sizes[k] = gamesPage.viewSizes[k]
                    }
                    sizes[gamesPage.viewMode] = value
                    gamesPage.viewSizes = sizes
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

    ListView {
        id: gameList
        objectName: "gameList"
        model: gameFilter
        property int rowHeight: gamesPage.rowHeight
        property var colW: ({appId: 90, played: 90, tier: 110, source: 80})
        focus: true
        highlightFollowsCurrentItem: true
        highlight: Rectangle {
            color: Kirigami.Theme.highlightColor
            opacity: 0.3
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
            Item {
                Layout.preferredWidth: gamesPage.rowHeight - 8
                Layout.preferredHeight: 1
            }
            Controls.Label {
                Layout.preferredWidth: 36
                horizontalAlignment: Text.AlignHCenter
                color: Kirigami.Theme.disabledTextColor
                font.bold: true
                text: "#"
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
            onPlayRequested: (gid) => gameModel.play(gid)
            onRowTapped: (gid) => {
                gameList.currentIndex = gameFilter.indexOf(gid)
            }
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: gameList.count === 0
            text: qsTr("No games yet")
            explanation: qsTr("Add a native Linux game to get started.")
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
