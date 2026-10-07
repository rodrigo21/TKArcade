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
// its own selection the same way).
Item {
    id: gameRow
    objectName: "gameRow"
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gameSource
    required property string gameTier
    required property string gameTierBg
    required property string gameTierFg
    required property string gameIcon
    property bool selected: false
    // gamePlayedSecs role exists on the model; sorting only.

    signal playRequested(string gid)
    signal rowTapped(string gid)

    height: (ListView.view?.rowHeight ?? 40)

    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.highlightColor
        opacity: 0.3
        visible: gameRow.selected
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: (eventPoint) => gameRow.rowTapped(gameRow.gameId)
        onDoubleTapped: (eventPoint) => gameRow.playRequested(gameRow.gameId)
    }

    RowLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.largeSpacing

        Controls.Label {
            objectName: "rowNumber"
            text: gameFilter.indexOf(gameRow.gameId) + 1
            color: Kirigami.Theme.disabledTextColor
            horizontalAlignment: Text.AlignHCenter
            Layout.preferredWidth: 36
        }

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
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Controls.Label {
                objectName: "nameLabel"
                text: gameRow.gameName
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Controls.Label {
                text: gameRow.gamePlayed
                opacity: 0.7
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
        Controls.Label {
            objectName: "appIdLabel"
            visible: gameFilter.showAppId
            text: gameRow.gameId
            elide: Text.ElideRight
            Layout.preferredWidth: (ListView.view?.colW ?? {}).appId ?? 90
        }
        Controls.Label {
            visible: gameFilter.showPlayed
            text: gameRow.gamePlayed
            elide: Text.ElideRight
            Layout.preferredWidth: (ListView.view?.colW ?? {}).played ?? 90
        }
        Rectangle {
            visible: gameFilter.showTier
            color: gameRow.gameTier !== "" ? gameRow.gameTierBg : "transparent"
            radius: 4
            Layout.preferredWidth: (ListView.view?.colW ?? {}).tier ?? 110
            Layout.preferredHeight: tierLabel.implicitHeight + Kirigami.Units.smallSpacing
            Controls.Label {
                id: tierLabel
                anchors.centerIn: parent
                text: gameRow.gameTier
                color: gameRow.gameTierFg
            }
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
