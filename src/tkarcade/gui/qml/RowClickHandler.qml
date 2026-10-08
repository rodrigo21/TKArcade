import QtQuick

// One row-click handler per table cell: manual selection keeps
// Ctrl/Shift behavior identical everywhere (the view itself selects
// nothing). Double-click plays, right-click opens the game menu.
//
// Takes gid + page explicitly: QML ids are file-scoped, so a bare
// `gamesPage` reference here resolves to nothing (clicks silently
// die). Context properties (gameFilter, gameModel) are fine as-is.
MouseArea {
    required property string gid
    required property var page
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
            page.openGameMenu(gid)
        } else {
            page.tapGame(gid, mouse.modifiers)
        }
    }
    onDoubleClicked: (mouse) => {
        if (mouse.button === Qt.LeftButton && gid !== "") {
            gameModel.play(gid)
        }
    }
}
