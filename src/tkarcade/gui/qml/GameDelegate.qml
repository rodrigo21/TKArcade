import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// One row of the games list, mirroring the widgets table columns:
// Game (icon + name) | App ID | Played | ProtonDB | Source | Play.
// Widths come from the ListView (rowHeight, colW) so header and rows
// match; icon and tier cells always reserve space so rows align with
// each other with and without data. Game-prefixed required properties
// bind straight to the model roles (Qt6 has no `model` object in
// delegates). Selection is a full-row overlay driven by `selected`
// (ListView highlight misbehaves with a header, so every view paints
// its own selection the same way). Row numbers live in the gutter
// beside the list (widgets vertical header), not in the row.
Item {
    id: gameRow
    objectName: "gameRow"
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gamePlayedTip
    required property string gameSource
    required property string gameTier
    required property string gameTierBg
    required property string gameTierFg
    required property string gameIcon
    property bool selected: false
    // gamePlayedSecs role exists on the model; sorting only.

    signal playRequested(string gid)
    signal rowTapped(string gid, int modifiers)
    signal menuRequested(string gid)

    height: (ListView.view?.rowHeight ?? 40)

    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.highlightColor
        opacity: 0.3
        visible: gameRow.selected
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton) {
                gameRow.menuRequested(gameRow.gameId)
            } else {
                gameRow.rowTapped(gameRow.gameId, mouse.modifiers)
            }
        }
        onDoubleClicked: (mouse) => {
            if (mouse.button === Qt.LeftButton) {
                gameRow.playRequested(gameRow.gameId)
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Item {
            Layout.preferredWidth: (ListView.view?.rowHeight ?? 40) - 8
            Layout.preferredHeight: (ListView.view?.rowHeight ?? 40) - 8
            Image {
                anchors.centerIn: parent
                visible: gameRow.gameIcon !== ""
                source: visible ? "file://" + gameRow.gameIcon : ""
                width: parent.width
                height: parent.height
                fillMode: Image.PreserveAspectFit
            }
        }
        Controls.Label {
            objectName: "nameLabel"
            Layout.fillWidth: true
            verticalAlignment: Text.AlignVCenter
            text: gameRow.gameName
            font.bold: true
            elide: Text.ElideRight
        }
        Controls.Label {
            objectName: "appIdLabel"
            visible: gameFilter.showAppId
            text: gameRow.gameId
            elide: Text.ElideRight
            Layout.preferredWidth: (ListView.view?.colW ?? {}).appId ?? 90
        }
        Controls.Label {
            objectName: "playedLabel"
            visible: gameFilter.showPlayed
            text: gameRow.gamePlayed
            elide: Text.ElideRight
            Layout.preferredWidth: (ListView.view?.colW ?? {}).played ?? 90
            HoverHandler {
                id: playedHover
            }
            Controls.ToolTip.visible: playedHover.hovered
            Controls.ToolTip.text: gameRow.gamePlayedTip
        }
        Controls.ToolButton {
            objectName: "tierButton"
            visible: gameFilter.showTier
            Layout.preferredWidth: (ListView.view?.colW ?? {}).tier ?? 110
            Layout.preferredHeight: tierLabel.implicitHeight + Kirigami.Units.smallSpacing
            text: gameRow.gameTier
            font.bold: true
            background: Rectangle {
                color: gameRow.gameTier !== "" ? gameRow.gameTierBg : "transparent"
                radius: 4
            }
            contentItem: Controls.Label {
                id: tierLabel
                objectName: "tierLabel"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: gameRow.gameTier
                color: gameRow.gameTierFg
                elide: Text.ElideRight
            }
            onClicked: gameRow.rowTapped(gameRow.gameId, 0)
            onDoubleClicked: gameModel.openProtonDB(gameRow.gameId)
            Controls.ToolTip.visible: hovered && gameRow.gameTier !== ""
            Controls.ToolTip.text: qsTr("Open ProtonDB page")
        }
        Controls.Label {
            visible: gameFilter.showSource
            text: gameRow.gameSource
            opacity: 0.7
            elide: Text.ElideRight
            Layout.preferredWidth: (ListView.view?.colW ?? {}).source ?? 80
        }
        Controls.ToolButton {
            icon.name: "media-playback-start"
            text: qsTr("Play")
            display: Controls.AbstractButton.IconOnly
            Layout.preferredWidth: 40
            onClicked: gameRow.playRequested(gameRow.gameId)
        }
    }
}
