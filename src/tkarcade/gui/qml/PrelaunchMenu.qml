import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

// Pre-launch chooser: the widgets MenuDialog port. Shown by `--menu` and
// by configs with show_menu set, in the standalone editor process
// (gui/edit.py) so the launcher itself stays stdlib-only.
//
// Launch / Settings... / Cancel; with a configured menu_timeout a
// countdown auto-launches, and opening Settings stops it (widgets
// parity: coming back, Launch still proceeds and Cancel still aborts).
Window {
    id: prelaunch
    objectName: "prelaunchMenu"
    title: qsTr("TKArcade — %1").arg(name || appid || qsTr("game"))
    modality: Qt.WindowModal
    // Widgets MenuDialog: setMinimumWidth(480) and a height that hugs
    // the content (480x121 for name + Proton line + buttons). The
    // landscape artwork is a Kirigami addition, so ours stays taller.
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 8
    width: Kirigami.Units.gridUnit * 26
    height: content.implicitHeight + Kirigami.Units.largeSpacing * 2
    visible: false
    color: Kirigami.Theme.backgroundColor

    property string appid: ""
    property string name: ""
    property string details: ""
    property int timeout: 0
    property bool canLaunch: true
    property int remaining: 0
    property bool outcomeReported: false
    // Landcape artwork URL and "Proton: ..." line, filled in openMenu()
    // (widgets MenuDialog parity).
    property string artSource: ""
    property string protonText: ""

    // "Name (appid)" like the widgets dialog header.
    readonly property string heading: name !== "" && appid !== ""
        ? name + " (" + appid + ")"
        : (name || appid)

    // "launch" | "cancelled" -- everything else is a crash, which the
    // launcher reads as "never launch" (run_editor_menu).
    signal finished(string outcome)
    // The editor opens the settings window modal on this one.
    signal settingsRequested()

    function openMenu() {
        outcomeReported = false
        details = detailText()
        var art = appid !== "" ? gameModel.landscapeArt(appid) : ""
        artSource = art !== "" ? "file://" + art : ""
        protonText = qsTr("Proton: %1").arg(gameModel.protonLabel(appid))
        remaining = canLaunch ? Math.max(0, Number(timeout) || 0) : 0
        visible = true
        requestActivate()
        if (remaining > 0) {
            countdown.start()
        }
    }

    function stopCountdown() {
        countdown.stop()
        remaining = 0
    }

    function launch() {
        if (outcomeReported) {
            return
        }
        outcomeReported = true
        stopCountdown()
        visible = false
        finished("launch")
    }

    function cancel() {
        if (outcomeReported) {
            return
        }
        outcomeReported = true
        stopCountdown()
        visible = false
        finished("cancelled")
    }

    function openSettings() {
        stopCountdown()
        settingsRequested()
    }

    onClosing: function (close) {
        // Window-manager close / Escape / Alt+F4: same as Cancel.
        cancel()
    }

    // Playtime and enabled wrappers, formatted by the model so only the
    // frame around them is translated here.
    function detailText() {
        var lines = []
        var stats = gameModel.playStats(appid)
        if (stats && stats.runs) {
            lines.push(qsTr("Played %1 over %2 session(s)").arg(stats.total).arg(stats.runs))
        }
        var wrappers = gameModel.activeWrappers(appid)
        if (wrappers !== "") {
            lines.push(wrappers)
        }
        return lines.join("\n")
    }

    Timer {
        id: countdown
        interval: 1000
        repeat: true
        onTriggered: {
            prelaunch.remaining -= 1
            if (prelaunch.remaining <= 0) {
                prelaunch.launch()
            }
        }
    }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing
            Item {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 8
                Layout.preferredHeight: Kirigami.Units.gridUnit * 5
                Image {
                    objectName: "prelaunchArt"
                    anchors.centerIn: parent
                    visible: prelaunch.artSource !== ""
                    source: visible ? prelaunch.artSource : ""
                    sourceSize.width: Kirigami.Units.gridUnit * 8
                    sourceSize.height: Kirigami.Units.gridUnit * 5
                    width: Math.min(parent.width, parent.height * 3 / 2)
                    height: width * 2 / 3
                    fillMode: Image.PreserveAspectFit
                }
                Kirigami.Icon {
                    objectName: "prelaunchArtFallback"
                    anchors.centerIn: parent
                    visible: prelaunch.artSource === ""
                    source: gameModel.iconName(["media-playback-start", "player-play"])
                    width: Kirigami.Units.gridUnit * 3
                    height: width
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Kirigami.Heading {
                    objectName: "prelaunchTitle"
                    Layout.fillWidth: true
                    level: 3
                    elide: Text.ElideRight
                    text: prelaunch.heading
                }
                Controls.Label {
                    objectName: "prelaunchProton"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    opacity: 0.7
                    font: Kirigami.Theme.smallFont
                    text: prelaunch.protonText
                }
                Controls.Label {
                    objectName: "prelaunchDetails"
                    Layout.fillWidth: true
                    visible: text !== ""
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    font: Kirigami.Theme.smallFont
                    text: prelaunch.details
                }
            }
        }
        Controls.Label {
            objectName: "prelaunchCountdown"
            Layout.fillWidth: true
            visible: prelaunch.remaining > 0
            text: qsTr("Launching in %1…").arg(prelaunch.remaining)
        }
        Item {
            Layout.fillHeight: true
        }
        RowLayout {
            Layout.fillWidth: true
            Item {
                Layout.fillWidth: true
            }
            // Widgets QDialogButtonBox (KDE layout): Settings... (action),
            // then Launch (accept) and Cancel, all right-aligned.
            Controls.Button {
                objectName: "prelaunchSettings"
                text: qsTr("Settings...")
                icon.name: gameModel.iconName(["configure", "settings-configure"])
                onClicked: prelaunch.openSettings()
            }
            Controls.Button {
                objectName: "prelaunchLaunch"
                text: qsTr("Launch")
                enabled: prelaunch.canLaunch
                highlighted: true
                icon.name: gameModel.iconName(["media-playback-start", "player-play"])
                onClicked: prelaunch.launch()
            }
            Controls.Button {
                objectName: "prelaunchCancel"
                text: qsTr("Cancel")
                onClicked: prelaunch.cancel()
            }
        }
    }
}
