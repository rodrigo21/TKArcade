import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// TKArcade shell: source drawer on the side, games page in the stack.
// Context properties (set by kirigami_app): gameModel, gameFilter.
Kirigami.ApplicationWindow {
    id: root
    title: qsTr("TKArcade")
    minimumWidth: 1280
    minimumHeight: 720
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

    Component.onCompleted: {
        applyDrawerMode(gameModel.drawerMode())
        // Center the page header actions as a unit (Dolphin-style):
        // with balancing mirror copies around them, the four action
        // buttons land centered at any window width.
        if (pageStack.globalToolBar) {
            pageStack.globalToolBar.toolbarActionAlignment = Qt.AlignRight
        }
    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: sourceDrawer
        objectName: "sourceDrawer"
        title: qsTr("TKArcade")
        showHeaderWhenCollapsed: true
        // Plain Item (not a ToolBar): with a toolbar header Kirigami
        // insets the drawer-edge separator around the header zone, so
        // the vertical line never meets the header lines. A plain
        // header keeps the full-height edge separator, which crosses
        // the header lines at the corner.
        header: Item {
            objectName: "drawerHeaderBar"
            // Same height source the Kirigami page headers clamp to, so
            // both separator lines meet (native, no magic numbers).
            implicitHeight: pageStack.globalToolBar.preferredHeight
            Kirigami.Theme.colorSet: Kirigami.Theme.Header
            Kirigami.Theme.inherit: false
            Rectangle {
                anchors.fill: parent
                color: Kirigami.Theme.backgroundColor
            }
            RowLayout {
                anchors.fill: parent
                // Reserve the button slot even when not collapsible so
                // the Library label keeps its x in every drawer mode.
                Controls.ToolButton {
                    objectName: "drawerCollapseButton"
                    Layout.alignment: Qt.AlignVCenter
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
                    color: Kirigami.Theme.textColor
                }
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Kirigami.Theme.textColor
                opacity: 0.18
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
