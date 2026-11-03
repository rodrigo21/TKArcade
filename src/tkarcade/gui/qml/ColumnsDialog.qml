import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls

// Column visibility + order without nested submenus (Up/Down buttons:
// drag-reorder is fragile in QML layouts). Driven by gamesPage helpers
// and the gameFilter show flags.
DialogWindow {
    id: columnsDialog
    title: qsTr("Configure Columns")
    acceptText: qsTr("Reset Columns")
    rejectText: qsTr("Close")

    property var page: null
    // Table order, so the list follows every Move Up/Down (the bug was a
    // static logical-order model).
    readonly property var listedLogicals: page !== null
        ? page.columnOrder.filter(function(l) { return l >= 2 })
        : []

    onAccepted: {
        if (page !== null) {
            page.resetColumns()
        }
    }

    function flagFor(logical) {
        if (logical === 2) {
            return "showAppId"
        } else if (logical === 3) {
            return "showPlayed"
        } else if (logical === 4) {
            return "showTier"
        } else if (logical === 6) {
            return "showLastPlayed"
        } else if (logical === 7) {
            return "showPlatform"
        } else if (logical === 8) {
            return "showRuntime"
        } else if (logical === 9) {
            return "showWine"
        } else if (logical === 10) {
            return "showInstallDir"
        } else if (logical === 11) {
            return "showReleaseDate"
        } else if (logical === 12) {
            return "showInstalled"
        }
        return "showOrigin"
    }

    Controls.Label {
        text: qsTr("Uncheck to Hide, Arrows to Reorder.")
    }
    Repeater {
        // JS array end to end, never a QVariantList.
        model: columnsDialog.listedLogicals
        delegate: RowLayout {
            required property int modelData
            property int logical: modelData
            property string flag: columnsDialog.flagFor(logical)
            Controls.CheckBox {
                objectName: "colShow" + logical
                checked: gameFilter[flag]
                onToggled: gameFilter[flag] = checked
            }
            Controls.Label {
                Layout.fillWidth: true
                text: page !== null ? page.columnTitle(logical) : ""
            }
            Controls.ToolButton {
                icon.name: "go-up"
                text: qsTr("Move Up")
                display: Controls.AbstractButton.IconOnly
                enabled: page !== null && page.columnOrder.indexOf(logical) > 2
                onClicked: page.moveColumn(logical, -1)
            }
            Controls.ToolButton {
                icon.name: "go-down"
                text: qsTr("Move Down")
                display: Controls.AbstractButton.IconOnly
                enabled: page !== null && page.columnOrder.indexOf(logical) < page.columnOrder.length - 1
                onClicked: page.moveColumn(logical, 1)
            }
        }
    }
}
