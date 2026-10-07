import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// One row of the games list. Game-prefixed required properties bind
// straight to the model roles (Qt6 has no `model` object in delegates).
RowLayout {
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gameTier
    required property string gameTierBg
    required property string gameTierFg
    // gameSource role exists on the model; unused in this layout.

    signal playRequested(string gid)

    spacing: Kirigami.Units.largeSpacing

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        Controls.Label {
            text: gameName
            font.bold: true
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Controls.Label {
            text: gameId + " · " + gamePlayed
            opacity: 0.7
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
    Rectangle {
        visible: gameTier !== ""
        color: gameTierBg
        radius: 4
        Layout.preferredWidth: tierLabel.implicitWidth + Kirigami.Units.largeSpacing
        Layout.preferredHeight: tierLabel.implicitHeight + Kirigami.Units.smallSpacing
        Controls.Label {
            id: tierLabel
            anchors.centerIn: parent
            text: gameTier
            color: gameTierFg
        }
    }
    Controls.ToolButton {
        icon.name: "media-playback-start"
        text: qsTr("Play")
        display: Controls.AbstractButton.IconOnly
        onClicked: playRequested(gameId)
    }
}
