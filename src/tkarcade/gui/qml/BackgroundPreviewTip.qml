// Hover preview of a game's wide background art. The owning delegate
// keeps the HoverHandler and binds `visible`; the picture loads only
// while the tooltip shows. The game name keeps the bubble non-empty
// (docs/QML-NOTES.md) and names the art.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Controls.ToolTip {
    id: previewTip
    property string gameId: ""
    property string label: ""
    property bool previewEnabled: false
    // A rest before a large picture covers part of the library.
    delay: 500

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing
        Controls.Label {
            Layout.fillWidth: true
            font: Kirigami.Theme.smallFont
            opacity: 0.8
            text: previewTip.label
        }
        Item {
            objectName: "backgroundPreviewBox"
            implicitWidth: previewImage.implicitWidth
            implicitHeight: previewImage.implicitHeight
            Image {
                id: previewImage
                objectName: "backgroundPreviewImage"
                anchors.fill: parent
                // Empty outside the hover: nothing decodes for a grid.
                source: previewTip.visible && previewTip.previewEnabled && previewTip.gameId !== ""
                    ? gameModel.artworkPreview(previewTip.gameId, "background", "") : ""
                // The wide art is capped, never upscaled.
                sourceSize.width: Kirigami.Units.gridUnit * 27
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
        }
    }
}
