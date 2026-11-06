// One artwork thumbnail in the game dialog: what the views draw for that
// slot, inside a fixed frame of the kind's shape so the gaps between the
// previews stay equal. The picture is drawn at its own size (never
// upscaled, never cropped). Clicking it picks a file; the two buttons
// below open the URL prompt and clear the slot; hovering shows the whole
// picture with its origin.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: preview
    // file:// URL of the effective art ("" when the slot is empty).
    property string artUrl: ""
    // Token from gameModel.artworkOrigin: manual, steam, exe, cache:…
    property string artOrigin: ""
    // Shapes the views use: 1 icon, 2/3 cover, ~2.14 banner.
    property real artRatio: 1
    // Frame size for this kind; the picture never grows past it.
    property real maxWidth: Kirigami.Units.gridUnit * 2.7
    readonly property real maxHeight: maxWidth / artRatio
    readonly property bool filled: artUrl !== ""

    signal picked()
    signal urlRequested()
    signal clearRequested()

    spacing: Kirigami.Units.smallSpacing

    // The picture keeps its own pixels, capped by the frame: a 16x16
    // icon stays 16x16 inside the frame instead of being stretched.
    readonly property size pictureSize: {
        var w = preview.filled ? picture.implicitWidth : 0
        var h = preview.filled ? picture.implicitHeight : 0
        if (w <= 0 || h <= 0) {
            return Qt.size(0, 0)
        }
        var scale = Math.min(1, (maxWidth - 4) / w, (maxHeight - 4) / h)
        return Qt.size(Math.round(w * scale), Math.round(h * scale))
    }

    // Zoom box in the tooltip: aspect kept, never past the source size.
    readonly property size zoomSize: {
        var w = preview.filled ? picture.implicitWidth : 0
        var h = preview.filled ? picture.implicitHeight : 0
        if (w <= 0 || h <= 0) {
            return Qt.size(0, 0)
        }
        var scale = Math.min(
            1,
            (Kirigami.Units.gridUnit * 27) / w,
            (Kirigami.Units.gridUnit * 21) / h)
        return Qt.size(Math.round(w * scale), Math.round(h * scale))
    }

    Item {
        id: frame
        objectName: "artPreviewFrame"
        implicitWidth: Math.round(preview.maxWidth)
        implicitHeight: Math.round(preview.maxHeight)
        Layout.alignment: Qt.AlignHCenter

        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.smallSpacing
            color: Kirigami.Theme.alternateBackgroundColor
            border.width: 1
            border.color: Kirigami.Theme.disabledTextColor
        }
        Image {
            id: picture
            objectName: "artPreviewImage"
            anchors.centerIn: parent
            width: preview.pictureSize.width
            height: preview.pictureSize.height
            source: preview.artUrl
            fillMode: Image.PreserveAspectFit
            asynchronous: true
        }
        HoverHandler {
            id: hover
            cursorShape: Qt.PointingHandCursor
        }
        TapHandler {
            onTapped: preview.picked()
        }
    }

    // Both buttons sit under the picture, so the image stays clean. The
    // clear button keeps its space while empty (hidden, disabled) so the
    // row never jumps after a fetch.
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: Kirigami.Units.smallSpacing
        Controls.ToolButton {
            objectName: "artPreviewUrl"
            padding: 0
            width: Kirigami.Units.gridUnit * 1.2
            height: width
            display: Controls.AbstractButton.IconOnly
            icon.name: gameModel.iconName(["insert-link", "link"])
            icon.width: Kirigami.Units.iconSizes.small
            icon.height: Kirigami.Units.iconSizes.small
            onClicked: preview.urlRequested()
            Controls.ToolTip.text: qsTr("Use an Image From a URL")
            Controls.ToolTip.visible: hovered
        }
        Controls.ToolButton {
            objectName: "artPreviewClear"
            padding: 0
            width: Kirigami.Units.gridUnit * 1.2
            height: width
            enabled: preview.filled
            opacity: preview.filled ? 1 : 0
            display: Controls.AbstractButton.IconOnly
            icon.name: gameModel.iconName(["edit-clear", "window-close"])
            icon.width: Kirigami.Units.iconSizes.small
            icon.height: Kirigami.Units.iconSizes.small
            onClicked: preview.clearRequested()
            Controls.ToolTip.text: qsTr("Clear This Artwork")
            Controls.ToolTip.visible: hovered && preview.filled
        }
    }

    readonly property string originText: {
        var map = {
            "manual": qsTr("Manual Image"),
            "cache:steam": qsTr("Downloaded From Steam"),
            "cache:sgdb": qsTr("Downloaded From SteamGridDB"),
            "cache": qsTr("Downloaded Artwork"),
            "steam": qsTr("Steam's Own Artwork"),
            "exe": qsTr("From the Game Executable")
        }
        return map[preview.artOrigin] || qsTr("No Artwork")
    }

    // The tile is small: the tooltip is where the picture is readable and
    // where the click target and the origin explain themselves. It always
    // carries text, so it is never an empty bubble (docs/QML-NOTES.md).
    Controls.ToolTip {
        objectName: "artPreviewTip"
        visible: hover.hovered
        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            // The Image reports its source size as implicit size, which
            // would size the popup to the full artwork; the wrapper gives
            // the layout the size the picture is really drawn at.
            Item {
                objectName: "artPreviewZoomBox"
                implicitWidth: preview.zoomSize.width
                implicitHeight: preview.zoomSize.height
                Image {
                    objectName: "artPreviewZoom"
                    anchors.fill: parent
                    source: preview.artUrl
                    fillMode: Image.PreserveAspectFit
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                text: preview.originText
            }
            Controls.Label {
                Layout.fillWidth: true
                opacity: 0.8
                text: qsTr("Click to Pick an Image")
            }
        }
    }
}
