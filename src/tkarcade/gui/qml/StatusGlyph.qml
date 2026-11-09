import QtQuick

// One status glyph centered by its ink, not by the font's line box. The
// tight bounding rect makes the star and the pause bars sit in the same
// optical center as the checks and circles, whatever fallback font wins.
Item {
    id: root
    property string glyph: ""
    property color color: "black"
    property string glyphFont: gameModel.symbolFontFamily()
    readonly property real glyphSize: Math.max(9, Math.round(height * 0.72))

    TextMetrics {
        id: metrics
        font.family: root.glyphFont
        font.pixelSize: root.glyphSize
        font.bold: true
        text: root.glyph
    }

    FontMetrics {
        id: fontMetrics
        font.family: root.glyphFont
        font.pixelSize: root.glyphSize
        font.bold: true
    }

    readonly property rect inkRect: metrics.tightBoundingRect
    readonly property real inkCenterX: glyphText.x + inkRect.x + inkRect.width / 2
    readonly property real inkCenterY: glyphText.y + fontMetrics.ascent
        + inkRect.y + inkRect.height / 2

    Text {
        id: glyphText
        text: root.glyph
        color: root.color
        font.family: root.glyphFont
        font.pixelSize: root.glyphSize
        font.bold: true
        x: Math.round((root.width - metrics.tightBoundingRect.width) / 2
            - metrics.tightBoundingRect.x)
        y: Math.round((root.height - metrics.tightBoundingRect.height) / 2
            - fontMetrics.ascent - metrics.tightBoundingRect.y)
    }
}
