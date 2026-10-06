import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as Delegates

// One row of the games list. Game-prefixed required properties bind
// straight to the model roles (Qt6 has no `model` object in delegates).
Delegates.TitleSubtitleWithActions {
    required property string gameName
    required property string gameId
    required property string gameSource

    signal playRequested(string gid)

    title: gameName
    subtitle: gameId + " · " + gameSource
    actions: [
        Kirigami.Action {
            text: qsTr("Play")
            icon.name: "media-playback-start"
            onTriggered: playRequested(gameId)
        }
    ]
}
