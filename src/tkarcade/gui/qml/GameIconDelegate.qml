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
    required property string gameIssueLevel
    required property string gameIssuesTip
    required property string gameStatus
    required property string gameStatusBg
    required property string gameStatusFg
    property int cellSize: 96
    property bool selected: false

    function statusLabel(code) {
        switch (code) {
        case "abandoned": return qsTr("Abandoned")
        case "beaten": return qsTr("Beaten")
        case "completed": return qsTr("Completed")
        case "not_played": return qsTr("Not Played")
        case "on_hold": return qsTr("On Hold")
        case "plan_to_play": return qsTr("Plan to Play")
        case "played": return qsTr("Played")
        case "playing": return qsTr("Playing")
        default: return ""
        }
    }

    function statusGlyph(code) {
        switch (code) {
        case "abandoned": return "✕"
        case "beaten": return "✓"
        case "completed": return "★"
        case "not_played": return "○"
        case "on_hold": return "Ⅱ"
        case "plan_to_play": return "◷"
        case "played": return "◐"
        case "playing": return "▶"
        default: return ""
        }
    }

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
            // Completion status, top-left so the validation badge keeps
            // the opposite corner. A solid disc keeps the glyph legible
            // on either theme, like the pills in the other views.
            Rectangle {
                objectName: "iconStatusBadge"
                anchors.top: parent.top
                anchors.left: parent.left
                visible: iconCell.gameStatus !== ""
                width: Kirigami.Units.iconSizes.small
                height: width
                radius: width / 2
                color: iconCell.gameStatusBg
                StatusGlyph {
                    objectName: "iconStatusGlyph"
                    anchors.fill: parent
                    glyph: iconCell.statusGlyph(iconCell.gameStatus)
                    color: iconCell.gameStatusFg
                }
                HoverHandler {
                    id: iconStatusHover
                }
                Controls.ToolTip {
                    objectName: "iconStatusBadgeTip"
                    visible: iconStatusHover.hovered
                    text: iconCell.statusLabel(iconCell.gameStatus)
                }
            }
            // Validation badge, same glyph/colors as the table.
            Kirigami.Icon {
                objectName: "iconIssueBadge"
                anchors.top: parent.top
                anchors.right: parent.right
                visible: iconCell.gameIssueLevel !== ""
                source: iconCell.gameIssueLevel === "error"
                    ? gameModel.iconName(["dialog-error", "dialog-warning"])
                    : gameModel.iconName(["dialog-warning", "dialog-information"])
                color: iconCell.gameIssueLevel === "error"
                    ? Kirigami.Theme.negativeTextColor
                    : Kirigami.Theme.neutralTextColor
                width: Kirigami.Units.iconSizes.small
                height: width
                HoverHandler {
                    id: iconIssueHover
                }
                Controls.ToolTip {
                    objectName: "iconIssueBadgeTip"
                    visible: iconIssueHover.hovered
                    text: iconCell.gameIssuesTip
                }
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
