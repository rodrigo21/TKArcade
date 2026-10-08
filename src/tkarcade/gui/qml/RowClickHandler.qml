import QtQuick

// One row-click handler per table cell: manual selection keeps
// Ctrl/Shift behavior identical everywhere (the view itself selects
// nothing). Double-click plays, right-click opens the game menu.
//
// Takes the game id directly: the delegate `row` property does not
// update in TableView delegates (every click reported row 0).
MouseArea {
    required property string gid
    anchors.fill: parent
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: (mouse) => {
        if (TKARCADE_DEBUG_CLICKS === "1") {
            console.log("RowClickHandler clicked gid=" + gid + " button=" + mouse.button)
        }
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
        if (mouse.button === Qt.LeftButton && gid !== "") {
            gameModel.play(gid)
        }
    }
}
