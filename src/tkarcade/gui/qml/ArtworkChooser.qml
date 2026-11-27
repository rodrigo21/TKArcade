// The provider candidates behind Fetch Artwork, before anything reaches
// the cache: one section per kind, the automatic pick preselected and
// marked, and only the selected URLs downloaded on confirm. Clicking the
// selected row again keeps that kind. The background section mirrors the
// banner and starts empty. The images load straight from the provider; a
// blank thumb still leaves the row selectable.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

DialogWindow {
    id: chooser
    objectName: "artChooser"
    title: qsTr("Choose Artwork")
    width: Kirigami.Units.gridUnit * 56
    minimumWidth: Kirigami.Units.gridUnit * 44
    height: Kirigami.Units.gridUnit * 46
    acceptText: qsTr("Download")
    acceptEnabled: groups.length > 0 && !applied && selectionCount > 0
    bodyFillHeight: true

    // Effective source of the candidates (steam, sgdb, igdb or vndb).
    property string provider: ""
    // [{kind, label, items: [{url, thumb, auto, label, note}]}]
    property var groups: []
    // kind -> chosen URL; the automatic row starts selected, except for
    // the background, which waits for an explicit pick.
    property var selections: ({})
    // Set by apply(): a close after it is not a cancel.
    property bool applied: false

    // Kinds the confirm will download: at least one is required.
    readonly property int selectionCount: {
        var total = 0
        for (var key in selections) {
            if (String(selections[key] || "") !== "") {
                total += 1
            }
        }
        return total
    }

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
            // The Background list mirrors the banner and is a choice
            // only: it starts unselected, so the fallback stays until the
            // user asks for a picture of its own.
            if (groups[i].kind === "background") {
                continue
            }
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
        if (String(next[kind] || "") === String(url)) {
            // A second click keeps that kind: no download, no chain fill.
            delete next[kind]
        } else {
            next[kind] = String(url)
        }
        selections = next
    }

    function isSelected(kind, url) {
        return String(selections[kind] || "") === String(url)
    }

    function apply() {
        // Every offered kind goes in the payload: an empty URL means the
        // user kept that kind, so the model must not fill it either.
        var picks = []
        for (var i = 0; i < groups.length; i++) {
            picks.push({
                "kind": groups[i].kind,
                "url": String(selections[groups[i].kind] || ""),
                "provider": provider
            })
        }
        if (selectionCount === 0) {
            return
        }
        applied = true
        applyRequested(picks)
        close()
    }

    // The thumbnail box per kind, and the preview pixels Qt keeps. The
    // icon is already readable at its size; the wide picture and the
    // cover grow enough to judge detail.
    function cellWidth(kind) {
        return kind === "icon" ? Kirigami.Units.gridUnit * 4
            : (kind === "cover" ? Kirigami.Units.gridUnit * 9
            : Kirigami.Units.gridUnit * 20)
    }

    function cellHeight(kind) {
        return kind === "icon" ? Kirigami.Units.gridUnit * 4
            : (kind === "cover" ? Kirigami.Units.gridUnit * 13.5
            : Kirigami.Units.gridUnit * 9.3)
    }

    function previewLimit(kind) {
        return kind === "icon" ? 256 : (kind === "cover" ? 768 : 1024)
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
        text: qsTr("Images from %1. The marked image is the automatic pick; only the selected images are downloaded now. Click a selected image again to keep that kind as it is. Kinds this source cannot fill are completed by the next provider.").arg(chooser.providerNames[chooser.provider] || chooser.provider)
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

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Label {
                            font.bold: true
                            text: String(section.modelData.label || "")
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        // The background reuses the banner rows: this
                        // copies the banner pick without a second download.
                        Controls.Button {
                            objectName: section.modelData.kind === "background" ? "artUseBanner" : ""
                            visible: section.modelData.kind === "background"
                                && String(chooser.selections["banner"] || "") !== ""
                            text: qsTr("Use the Banner")
                            onClicked: chooser.select("background", String(chooser.selections["banner"]))
                        }
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
