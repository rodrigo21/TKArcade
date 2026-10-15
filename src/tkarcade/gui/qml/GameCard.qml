import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// One game as a gallery-style card: artwork banner, name, played and
// source lines, Play action. The parent sets `selected` (CardsLayout
// has no currentIndex); click selects, the Play action launches.
// Game-prefixed required properties bind straight to the model roles.
Kirigami.Card {
    id: gameCard
    objectName: "gameCard"
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gameSource
    required property string gameTier
    required property string gameTierBg
    required property string gameTierFg
    required property string gameIcon
    property bool selected: false

    signal playRequested(string gid)
    signal rowTapped(string gid, int modifiers)
    signal menuRequested(string gid)

    Layout.maximumWidth: Kirigami.Units.gridUnit * 18

    banner {
        source: gameIcon !== "" ? "file://" + gameIcon : ""
        title: gameName
        titleIcon: gameModel.iconName(["input-gamepad", "applications-games"])
        titleAlignment: Qt.AlignBottom | Qt.AlignLeft
    }
    contentItem: ColumnLayout {
        Controls.Label {
            objectName: "cardPlayed"
            Layout.fillWidth: true
            text: gamePlayed
            opacity: 0.7
            elide: Text.ElideRight
        }
        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                visible: gameTier !== ""
                color: gameTier !== "" ? gameTierBg : "transparent"
                radius: 4
                Layout.preferredWidth: cardTierLabel.implicitWidth + Kirigami.Units.largeSpacing
                Layout.preferredHeight: cardTierLabel.implicitHeight + Kirigami.Units.smallSpacing
                Controls.Label {
                    id: cardTierLabel
                    anchors.centerIn: parent
                    text: gameCard.gameTier
                    color: gameCard.gameTierFg
                }
            }
            Controls.Label {
                objectName: "cardSource"
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: gameCard.gameSource
                opacity: 0.7
                elide: Text.ElideRight
            }
        }
    }
    actions: [
        Kirigami.Action {
            objectName: "cardPlay"
            text: qsTr("Play")
            icon.name: "media-playback-start"
            onTriggered: gameCard.playRequested(gameCard.gameId)
        }
    ]

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: gameCard.selected ? 2 : 0
        border.color: Kirigami.Theme.highlightColor
    }

    // Kirigami.Card emits clicked() with no event (its accepted buttons
    // are fixed and it exposes no acceptedButtons property), so:
    // - the right-click branch that used to live inside onClicked was
    //   dead (the cards view had no context menu) and
    // - the left-click branch threw "Cannot read property 'modifiers' of
    //   undefined", so a click never selected the card either.
    // The menu gets a right-button-only MouseArea (left clicks fall
    // through to the card and to its Play action); selection goes
    // through clicked() with no modifiers, since the card cannot report
    // them (the icon cell and the table rows read them from a
    // MouseArea, which cannot overlay this card without covering the
    // Play action).
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: (mouse) => gameCard.menuRequested(gameCard.gameId)
    }

    showClickFeedback: true
    onClicked: gameCard.rowTapped(gameCard.gameId, 0)
}
