// The provider candidates behind Fetch Artwork, before anything reaches
// the cache: one section per kind, the automatic pick preselected and
// marked, and only the selected URLs downloaded on confirm. The images
// load straight from the provider; a blank thumb still leaves the row
// selectable.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

DialogWindow {
    id: chooser
    objectName: "artChooser"
    title: qsTr("Choose Artwork")
    width: Kirigami.Units.gridUnit * 44
    minimumWidth: Kirigami.Units.gridUnit * 36
    height: Kirigami.Units.gridUnit * 34
    acceptText: qsTr("Download")
    acceptEnabled: groups.length > 0 && !applied
    bodyFillHeight: true

    // Effective source of the candidates (steam, sgdb, igdb or vndb).
    property string provider: ""
    // [{kind, label, items: [{url, thumb, auto, label, note}]}]
    property var groups: []
    // kind -> chosen URL; the automatic row starts selected.
    property var selections: ({})
    // Set by apply(): a close after it is not a cancel.
    property bool applied: false

    signal applyRequested(var picks)
    signal cancelled()

    readonly property var providerNames: ({
        "steam": qsTr("Steam"),
        "sgdb": qsTr("SteamGridDB"),
        "igdb": qsTr("IGDB"),
        "vndb": qsTr("VNDB")
    })

    function openWith(parentWindow, providerToken, rows) {
        applied = false
        provider = String(providerToken || "")
        groups = rows || []
        var picks = ({})
        for (var i = 0; i < groups.length; i++) {
            var items = groups[i].items || []
            for (var j = 0; j < items.length; j++) {
                if (items[j].auto === true) {
                    picks[groups[i].kind] = String(items[j].url)
                    break
                }
            }
            if (!picks[groups[i].kind] && items.length > 0) {
                picks[groups[i].kind] = String(items[0].url)
            }
        }
        selections = picks
        open(parentWindow)
    }

    function select(kind, url) {
        var next = ({})
        for (var key in selections) {
            next[key] = selections[key]
        }
        next[kind] = String(url)
        selections = next
    }

    function isSelected(kind, url) {
        return String(selections[kind] || "") === String(url)
    }

    function apply() {
        var picks = []
        for (var i = 0; i < groups.length; i++) {
            var kind = groups[i].kind
            var chosen = String(selections[kind] || "")
            if (chosen === "" && groups[i].items.length > 0) {
                chosen = String(groups[i].items[0].url)
            }
            if (chosen !== "") {
                picks.push({"kind": kind, "url": chosen, "provider": provider})
            }
        }
        if (picks.length === 0) {
            return
        }
        applied = true
        applyRequested(picks)
        close()
    }

    // The thumbnail box per kind, and the preview pixels Qt keeps.
    function cellWidth(kind) {
        return kind === "icon" ? Kirigami.Units.gridUnit * 4
            : (kind === "cover" ? Kirigami.Units.gridUnit * 6
            : Kirigami.Units.gridUnit * 11)
    }

    function cellHeight(kind) {
        return kind === "icon" ? Kirigami.Units.gridUnit * 4
            : (kind === "cover" ? Kirigami.Units.gridUnit * 9
            : Kirigami.Units.gridUnit * 6.2)
    }

    function previewLimit(kind) {
        return kind === "icon" ? 256 : (kind === "cover" ? 512 : 1024)
    }

    onAccepted: chooser.apply()
    onClosing: {
        if (!applied) {
            cancelled()
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: qsTr("Images from %1. The marked image is the automatic pick; only the selected images are downloaded now. Kinds this source cannot fill are completed by the next provider.").arg(chooser.providerNames[chooser.provider] || chooser.provider)
    }

    Controls.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            Repeater {
                model: chooser.groups

                delegate: ColumnLayout {
                    id: section
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Label {
                        font.bold: true
                        text: String(section.modelData.label || "")
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Repeater {
                            model: section.modelData.items

                            delegate: ColumnLayout {
                                id: tile
                                required property var modelData
                                spacing: Kirigami.Units.smallSpacing / 2

                                Item {
                                    implicitWidth: chooser.cellWidth(section.modelData.kind)
                                    implicitHeight: chooser.cellHeight(section.modelData.kind)

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Kirigami.Units.smallSpacing
                                        color: Kirigami.Theme.alternateBackgroundColor
                                    }
                                    Image {
                                        anchors.fill: parent
                                        anchors.margins: 2
                                        source: String(tile.modelData.thumb || "")
                                        sourceSize.width: chooser.previewLimit(section.modelData.kind)
                                        sourceSize.height: chooser.previewLimit(section.modelData.kind)
                                        fillMode: Image.PreserveAspectFit
                                        asynchronous: true
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Kirigami.Units.smallSpacing
                                        color: "transparent"
                                        border.width: chooser.isSelected(section.modelData.kind, tile.modelData.url) ? 2 : 1
                                        border.color: chooser.isSelected(section.modelData.kind, tile.modelData.url)
                                            ? Kirigami.Theme.highlightColor
                                            : Kirigami.Theme.disabledTextColor
                                    }
                                    Rectangle {
                                        visible: tile.modelData.auto === true
                                        anchors.left: parent.left
                                        anchors.top: parent.top
                                        anchors.margins: 2
                                        radius: 2
                                        color: Kirigami.Theme.highlightColor
                                        implicitWidth: autoLabel.implicitWidth + Kirigami.Units.smallSpacing
                                        implicitHeight: autoLabel.implicitHeight
                                        Controls.Label {
                                            id: autoLabel
                                            anchors.centerIn: parent
                                            text: qsTr("Automatic")
                                            color: Kirigami.Theme.highlightedTextColor
                                            font: Kirigami.Theme.smallFont
                                        }
                                    }
                                    HoverHandler {
                                        cursorShape: Qt.PointingHandCursor
                                    }
                                    TapHandler {
                                        onTapped: chooser.select(section.modelData.kind, tile.modelData.url)
                                    }
                                }

                                Controls.Label {
                                    visible: text !== ""
                                    Layout.maximumWidth: chooser.cellWidth(section.modelData.kind)
                                    wrapMode: Text.WordWrap
                                    font: Kirigami.Theme.smallFont
                                    text: String(tile.modelData.label || "")
                                }
                                Controls.Label {
                                    visible: text !== ""
                                    Layout.maximumWidth: chooser.cellWidth(section.modelData.kind)
                                    wrapMode: Text.WordWrap
                                    font: Kirigami.Theme.smallFont
                                    opacity: 0.7
                                    text: String(tile.modelData.note || "")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
