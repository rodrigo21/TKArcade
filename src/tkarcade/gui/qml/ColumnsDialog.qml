import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Column visibility + order without nested submenus (Up/Down buttons:
// drag-reorder is fragile in QML layouts). Driven by gamesPage helpers
// and the gameFilter show flags.
Kirigami.Dialog {
    id: columnsDialog
    title: qsTr("Configure Columns")
    padding: Kirigami.Units.largeSpacing

    property var page: null

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
            return "showRunner"
        } else if (logical === 9) {
            return "showWine"
        } else if (logical === 10) {
            return "showInstallDir"
        }
        return "showOrigin"
    }

    function titleFor(logical) {
        if (logical === 2) {
            return qsTr("App ID")
        } else if (logical === 3) {
            return qsTr("Played")
        } else if (logical === 4) {
            return qsTr("ProtonDB")
        } else if (logical === 6) {
            return qsTr("Last Played")
        } else if (logical === 7) {
            return qsTr("Platform")
        } else if (logical === 8) {
            return qsTr("Runner")
        } else if (logical === 9) {
            return qsTr("Wine")
        } else if (logical === 10) {
            return qsTr("Install Dir")
        }
        return qsTr("Origin")
    }

    ColumnLayout {
        Controls.Label {
            text: qsTr("Uncheck to Hide, Arrows to Reorder.")
        }
        Repeater {
            // Static literal: JS array end to end, never a QVariantList.
            model: [2, 3, 4, 5, 6, 7, 8, 9, 10]
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
                    text: columnsDialog.titleFor(logical)
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

    footer: RowLayout {
        Layout.fillWidth: true
        Controls.Button {
            text: qsTr("Reset Columns")
            onClicked: page.resetColumns()
        }
        Item {
            Layout.fillWidth: true
        }
        Controls.Button {
            text: qsTr("Close")
            onClicked: columnsDialog.close()
        }
    }
}
