import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// One game cell for the icons grid: artwork (or fallback icon), bold
// name, dimmed played time. The GridView drives size through cellSize;
// the page drives `selected` for the highlight overlay. Tap selects,
// double-tap launches, right-click opens the menu, middle-click the
// settings. Game-prefixed required properties bind straight to the
// model roles.
Item {
    id: iconCell
    objectName: "gameIconCell"
    required property string gameName
    required property string gameId
    required property string gamePlayed
    required property string gameIcon
    required property bool gameRunning
    property int cellSize: 96
    property bool selected: false

    signal playRequested(string gid)
    signal rowTapped(string gid, int modifiers)
    signal menuRequested(string gid)
    signal settingsRequested(string gid)

    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.highlightColor
        opacity: 0.3
        visible: iconCell.selected
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onClicked: (mouse) => {
            if (mouse.button === Qt.RightButton) {
                iconCell.menuRequested(iconCell.gameId)
            } else if (mouse.button === Qt.MiddleButton) {
                iconCell.settingsRequested(iconCell.gameId)
            } else {
                iconCell.rowTapped(iconCell.gameId, mouse.modifiers)
            }
        }
        onDoubleClicked: (mouse) => {
            if (mouse.button === Qt.LeftButton) {
                iconCell.playRequested(iconCell.gameId)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Image {
                anchors.centerIn: parent
                visible: iconCell.gameIcon !== ""
                source: visible ? "file://" + iconCell.gameIcon : ""
                width: Math.min(parent.width, parent.height, iconCell.cellSize)
                height: width
                fillMode: Image.PreserveAspectFit
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                visible: iconCell.gameIcon === ""
                source: gameModel.iconName(["input-gamepad", "applications-games"])
                width: Math.min(parent.width, parent.height, iconCell.cellSize) * 0.6
                height: width
            }
        }
        Controls.Label {
            objectName: "iconName"
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            font.bold: true
            text: iconCell.gameName
            elide: Text.ElideRight
        }
        Controls.Label {
            objectName: "iconPlayed"
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: iconCell.gameRunning ? qsTr("Running") : iconCell.gamePlayed
            color: iconCell.gameRunning ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.textColor
            opacity: 0.7
            elide: Text.ElideRight
        }
    }
}
