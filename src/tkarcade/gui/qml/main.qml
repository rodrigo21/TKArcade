import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// TKArcade shell: source drawer on the side, games page in the stack.
// Context properties (set by kirigami_app): gameModel, gameFilter.
Kirigami.ApplicationWindow {
    id: root
    title: qsTr("TKArcade")
    minimumWidth: Kirigami.Units.gridUnit * 30
    minimumHeight: Kirigami.Units.gridUnit * 20
    width: minimumWidth
    height: minimumHeight

    Shortcut {
        objectName: "quitShortcut"
        sequence: StandardKey.Quit
        onActivated: Qt.quit()
    }

    function applyDrawerMode(mode) {
        if (mode === "overlay") {
            sourceDrawer.modal = true
            sourceDrawer.collapsible = false
            sourceDrawer.collapsed = false
        } else if (mode === "collapsible") {
            sourceDrawer.modal = false
            sourceDrawer.collapsible = true
            sourceDrawer.collapsed = true
        } else {
            sourceDrawer.modal = false
            sourceDrawer.collapsible = false
            sourceDrawer.collapsed = false
        }
    }

    Component.onCompleted: applyDrawerMode(gameModel.drawerMode())

    globalDrawer: Kirigami.GlobalDrawer {
        id: sourceDrawer
        objectName: "sourceDrawer"
        title: qsTr("TKArcade")
        showHeaderWhenCollapsed: true
        header: Controls.ToolBar {
            objectName: "drawerHeaderBar"
            // Same height source the Kirigami page headers clamp to, so
            // both separator lines meet (native, no magic numbers).
            implicitHeight: pageStack.globalToolBar.preferredHeight
            contentItem: RowLayout {
                Layout.fillWidth: true
                // Reserve the button slot even when not collapsible so
                // this bar matches the page header height (both are then
                // driven by a ToolButton) and the separator lines align.
                Controls.ToolButton {
                    objectName: "drawerCollapseButton"
                    icon.name: "sidebar-collapse-left"
                    opacity: sourceDrawer.collapsible ? 1 : 0
                    enabled: sourceDrawer.collapsible
                    checked: !sourceDrawer.collapsed
                    checkable: true
                    onClicked: sourceDrawer.collapsed = !sourceDrawer.collapsed
                }
                Controls.Label {
                    visible: !sourceDrawer.collapsed
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    text: qsTr("Library")
                    font.bold: true
                }
            }
        }
        actions: [
            Kirigami.Action {
                text: qsTr("All Games (%1)").arg(gameModel.totalCount)
                checked: gameFilter.sourceKey === "all"
                onTriggered: gameFilter.sourceKey = "all"
            },
            Kirigami.Action {
                text: qsTr("Steam (%1)").arg(gameModel.steamCount)
                checked: gameFilter.sourceKey === "steam"
                onTriggered: gameFilter.sourceKey = "steam"
            },
            Kirigami.Action {
                text: qsTr("Local (%1)").arg(gameModel.localCount)
                checked: gameFilter.sourceKey === "local"
                onTriggered: gameFilter.sourceKey = "local"
            }
        ]
    }

    pageStack.initialPage: MainPage {
        appDrawer: sourceDrawer
    }
}
