import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// One game as a gallery-style card: artwork banner, name, played and
// source lines, Play action. The parent sets `selected` (CardsLayout
// has no currentIndex); click selects, the Play action launches,
// right-click opens the menu, middle-click the settings.
// Game-prefixed required properties bind straight to the model roles.
Kirigami.Card {
    id: gameCard
    objectName: "gameCard"
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gameOrigin
    required property string gameTier
    required property string gameTierBg
    required property string gameTierFg
    required property string gameIcon
    required property string gameCover
    required property bool gameRunning
    property bool selected: false

    signal playRequested(string gid)
    signal rowTapped(string gid, int modifiers)
    signal menuRequested(string gid)
    signal settingsRequested(string gid)
    signal terminateRequested(string gid)

    Layout.maximumWidth: Kirigami.Units.gridUnit * 18

    banner {
        source: gameCover !== "" ? "file://" + gameCover
            : (gameIcon !== "" ? "file://" + gameIcon : "")
        // The banner keeps the art's own aspect and never crops it;
        // CardsLayout still gives every card in a row one height.
        fillMode: Image.PreserveAspectFit
        title: gameName
        titleIcon: gameModel.iconName(["input-gamepad", "applications-games"])
        titleAlignment: Qt.AlignBottom | Qt.AlignLeft
    }
    contentItem: ColumnLayout {
        Controls.Label {
            objectName: "cardPlayed"
            Layout.fillWidth: true
            // The running game takes the slot the played time occupies.
            text: gameCard.gameRunning ? qsTr("Running") : gameCard.gamePlayed
            color: gameCard.gameRunning ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.textColor
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
                objectName: "cardOrigin"
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: gameCard.gameOrigin
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
        },
        Kirigami.Action {
            objectName: "cardTerminate"
            visible: gameCard.gameRunning
            text: qsTr("Terminate")
            icon.name: "process-stop"
            onTriggered: gameCard.terminateRequested(gameCard.gameId)
        }
    ]

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: gameCard.selected ? 2 : 0
        border.color: Kirigami.Theme.highlightColor
    }

    // Kirigami.Card emits clicked() with no event at all (no modifiers,
    // no button), so the gesture layer is split in two:
    // - a plain left click goes through the card itself, which reports
    //   no modifiers (plain selection), and
    // - this MouseArea takes the presses the card cannot describe: the
    //   context menu, the settings gesture (middle click) and Ctrl/Shift
    //   clicks. It only claims those, so an unmodified press still
    //   reaches the card and the footer's Play action (a full cover
    //   would swallow the button).
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onPressed: (mouse) => {
            mouse.accepted = mouse.button === Qt.RightButton
                || mouse.button === Qt.MiddleButton
                || (mouse.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)) !== 0
        }
        onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton) {
                gameCard.menuRequested(gameCard.gameId)
            } else if (mouse.button === Qt.MiddleButton) {
                gameCard.settingsRequested(gameCard.gameId)
            } else {
                gameCard.rowTapped(gameCard.gameId, mouse.modifiers)
            }
        }
    }

    showClickFeedback: true
    onClicked: gameCard.rowTapped(gameCard.gameId, 0)
}
