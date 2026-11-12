// One artwork thumbnail in the game dialog: what the views draw for that
// slot, inside a frame that hugs the loaded picture with an equal margin
// on every side, so the art never touches the rounded corner. The picture
// is drawn at its own size (never upscaled, never cropped). Clicking it
// picks a file; the two buttons below open the URL prompt and clear the
// slot; hovering shows the whole picture with its origin.
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
    // What the slot draws ("Icon", "Banner"…): names the tooltip's art.
    property string artLabel: ""
    // Slot shape, used while the slot is empty: 1 icon, 2/3 cover,
    // ~2.14 banner, ~3.1 background.
    property real artRatio: 1
    // Box this kind allows; the frame never grows past it.
    property real maxWidth: Kirigami.Units.gridUnit * 2.7
    readonly property real maxHeight: maxWidth / artRatio
    readonly property bool filled: artUrl !== ""

    // Aspect of the loaded picture: the slot shape while empty or before
    // the asynchronous load reports its size, the picture's own after.
    readonly property real sourceRatio: {
        var w = picture.implicitWidth
        var h = picture.implicitHeight
        return w > 0 && h > 0 ? w / h : artRatio
    }
    // Small margin between the art and the frame edge, on every side.
    readonly property real framePadding: Kirigami.Units.smallSpacing
    // Filled: the picture plus an equal margin all around, capped by the
    // kind's box. Empty: the kind's shape.
    readonly property real frameWidth: {
        if (!filled) {
            return Math.round(maxWidth)
        }
        var pad = framePadding * 2
        var ratio = sourceRatio > 0 ? sourceRatio : 1
        var w = Math.max(1, maxWidth - pad)
        if (w / ratio > maxHeight - pad) {
            w = Math.max(1, (maxHeight - pad) * ratio)
        }
        return Math.round(w + pad)
    }
    readonly property real frameHeight: {
        if (!filled) {
            return Math.round(maxHeight)
        }
        var pad = framePadding * 2
        var ratio = sourceRatio > 0 ? sourceRatio : 1
        return Math.round((frameWidth - pad) / ratio + pad)
    }

    signal picked()
    signal urlRequested()
    signal clearRequested()

    spacing: Kirigami.Units.smallSpacing

    // The picture keeps its own pixels, capped by the frame inside an
    // equal margin: a 16x16 icon stays 16x16 instead of being stretched.
    readonly property size pictureSize: {
        var w = preview.filled ? picture.implicitWidth : 0
        var h = preview.filled ? picture.implicitHeight : 0
        if (w <= 0 || h <= 0) {
            return Qt.size(0, 0)
        }
        var pad = framePadding * 2
        var scale = Math.min(
            1,
            Math.max(0, frameWidth - pad) / w,
            Math.max(0, frameHeight - pad) / h)
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
        implicitWidth: preview.frameWidth
        implicitHeight: preview.frameHeight
        Layout.alignment: Qt.AlignHCenter

        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.smallSpacing
            color: Kirigami.Theme.alternateBackgroundColor
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
        // The picture fills the frame now, so the outline is drawn over it.
        Rectangle {
            anchors.fill: parent
            radius: Kirigami.Units.smallSpacing
            color: "transparent"
            border.width: 1
            border.color: Kirigami.Theme.disabledTextColor
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
            "cache:igdb": qsTr("Downloaded From IGDB"),
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
            // Names the kind at the tooltip's top-left corner: the picture
            // alone does not say which slot it belongs to.
            Controls.Label {
                objectName: "artPreviewKind"
                Layout.fillWidth: true
                font: Kirigami.Theme.smallFont
                opacity: 0.8
                text: preview.artLabel
            }
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
