import QtQuick

// One row-click handler per table cell: manual selection keeps
// Ctrl/Shift behavior identical everywhere (the view itself selects
// nothing). Double-click plays, right-click opens the game menu.
MouseArea {
    required property int row
    anchors.fill: parent
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: (mouse) => {
        if (TKARCADE_DEBUG_CLICKS === "1") {
            console.log("RowClickHandler clicked row=" + row + " button=" + mouse.button)
        }
        var gid = gameFilter.idAt(row)
        if (gid === "") {
            return
        }
        if (mouse.button === Qt.RightButton) {
            gamesPage.openGameMenu(gid)
        } else {
            gamesPage.tapGame(gid, mouse.modifiers)
        }
    }
    onDoubleClicked: (mouse) => {
        if (mouse.button === Qt.LeftButton) {
            var gid = gameFilter.idAt(row)
            if (gid !== "") {
                gameModel.play(gid)
            }
        }
    }
}
