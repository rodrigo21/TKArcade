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

    globalDrawer: Kirigami.GlobalDrawer {
        id: sourceDrawer
        objectName: "sourceDrawer"
        title: qsTr("TKArcade")
        showHeaderWhenCollapsed: true
        header: Controls.ToolBar {
            contentItem: RowLayout {
                Layout.fillWidth: true
                Controls.ToolButton {
                    objectName: "drawerCollapseButton"
                    icon.name: "sidebar-collapse-left"
                    visible: sourceDrawer.collapsible
                    checked: !sourceDrawer.collapsed
                    checkable: true
                    onClicked: sourceDrawer.collapsed = !sourceDrawer.collapsed
                }
                Controls.Label {
                    visible: !sourceDrawer.collapsed
                    Layout.fillWidth: true
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
            },
            Kirigami.Action {
                separator: true
            },
            Kirigami.Action {
                text: qsTr("Drawer Mode…")
                icon.name: "sidebar-collapse-left"
                visible: !Kirigami.Settings.isMobile
                expandible: true
                Kirigami.Action {
                    objectName: "drawerModeOverlay"
                    text: qsTr("Overlay Drawer")
                    checked: sourceDrawer.modal && !sourceDrawer.collapsible
                    onTriggered: {
                        sourceDrawer.modal = true
                        sourceDrawer.collapsible = false
                        sourceDrawer.collapsed = false
                    }
                }
                Kirigami.Action {
                    objectName: "drawerModeSidebar"
                    text: qsTr("Sidebar Drawer")
                    checked: !sourceDrawer.modal && !sourceDrawer.collapsible
                    onTriggered: {
                        sourceDrawer.modal = false
                        sourceDrawer.collapsible = false
                        sourceDrawer.collapsed = false
                    }
                }
                Kirigami.Action {
                    objectName: "drawerModeCollapsible"
                    text: qsTr("Collapsible Sidebar Drawer")
                    checked: !sourceDrawer.modal && sourceDrawer.collapsible
                    onTriggered: {
                        sourceDrawer.modal = false
                        sourceDrawer.collapsible = true
                        sourceDrawer.collapsed = true
                    }
                }
            }
        ]
    }

    pageStack.initialPage: MainPage {}
}
