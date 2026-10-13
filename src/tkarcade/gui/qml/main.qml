import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import QtQuick.Window
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
        // Application scope: a modal window/dialog with focus must not
        // swallow it. Explicit Ctrl+Q (StandardKey.Quit resolves empty on
        // some platforms). Qt.quit() skips onClosing, so Close-to-tray
        // never blocks it (widgets parity: Ctrl+Q always quits for real).
        context: Qt.ApplicationShortcut
        sequence: "Ctrl+Q"
        onActivated: Qt.quit()
    }

    onClosing: (close) => {
        if (gameModel.hideOnClose()) {
            close.accepted = false
            root.visible = false
        }
    }

    onVisibilityChanged: {
        if (root.visibility === Window.Minimized && gameModel.hideOnMinimize()) {
            root.visible = false
        }
    }

    function applyDrawerMode(mode) {
        if (mode === "overlay") {
            sourceDrawer.modal = true
            sourceDrawer.collapsible = false
            sourceDrawer.collapsed = false
        } else {
            // Collapsible is the only sidebar: anything else falls here,
            // restoring the persisted collapsed state instead of forcing.
            sourceDrawer.modal = false
            sourceDrawer.collapsible = true
            sourceDrawer.collapsed = gameModel.drawerCollapsed()
        }
    }

    Component.onCompleted: {
        applyDrawerMode(gameModel.drawerMode())
        // Actions row holds the view icons only: right-pin them.
        if (pageStack.globalToolBar) {
            pageStack.globalToolBar.toolbarActionAlignment = Qt.AlignRight
        }
        // Kirigami ships its own Quit action (StandardKey.Quit) that
        // calls close() instead of quitting: with a tray up the close
        // is caught and hidden, so Ctrl+Q never quits. Clear it; our
        // Shortcut below owns the sequence.
        root.quitAction.shortcut = ""
    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: sourceDrawer
        objectName: "sourceDrawer"
        title: qsTr("TKArcade")
        showHeaderWhenCollapsed: true
        // Gamepad handle: the theme draws application-menu as a gear.
        handleClosedIcon.name: "input-gamepad"
        // No built-in close row: the header gamepad toggles collapse.
        collapseButtonVisible: false
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
                anchors.leftMargin: Kirigami.Units.smallSpacing
                anchors.rightMargin: Kirigami.Units.smallSpacing
                // Doubles as the collapse toggle (the footer switch
                // hides with a collapsed drawer, so this stays the
                // only way back out).
                Controls.ToolButton {
                    objectName: "drawerHeaderButton"
                    id: drawerHeaderButton
                    Layout.alignment: Qt.AlignVCenter
                    icon.name: "input-gamepad"
                    enabled: sourceDrawer.collapsible
                    Controls.ToolTip.text: sourceDrawer.collapsed ? qsTr("Expand sidebar") : qsTr("Collapse sidebar")
                    Controls.ToolTip.visible: hovered
                    onClicked: {
                        sourceDrawer.collapsed = !sourceDrawer.collapsed
                        gameModel.saveDrawerCollapsed(sourceDrawer.collapsed)
                    }
                }
                Controls.Label {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    text: qsTr("Library")
                    font.bold: true
                    color: Kirigami.Theme.textColor
                }
                // Balances the header button so Library sits on the
                // true center instead of the remaining space.
                Item {
                    Layout.preferredWidth: drawerHeaderButton.width
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
        // Escape hatch: the hamburger menu (with the drawer switch)
        // can hide inside the overflow button; the footer never does.
        // Hidden with a collapsed drawer (nothing fits its 50px).
        footer: RowLayout {
            visible: !sourceDrawer.collapsed
            Item {
                Layout.fillWidth: true
            }
            Controls.ToolButton {
                objectName: "drawerModeOverlayButton"
                icon.name: "view-fullscreen"
                checkable: true
                checked: sourceDrawer.modal && !sourceDrawer.collapsible
                Controls.ToolTip.text: qsTr("Overlay Drawer")
                Controls.ToolTip.visible: hovered
                onClicked: {
                    applyDrawerMode("overlay")
                    gameModel.saveDrawerMode("overlay")
                }
            }
            Controls.ToolButton {
                objectName: "drawerModeCollapsibleButton"
                icon.name: "sidebar-collapse-left"
                checkable: true
                checked: !sourceDrawer.modal && sourceDrawer.collapsible
                Controls.ToolTip.text: qsTr("Collapsible Sidebar Drawer")
                Controls.ToolTip.visible: hovered
                onClicked: {
                    applyDrawerMode("collapsible")
                    gameModel.saveDrawerMode("collapsible")
                }
            }
            Item {
                Layout.fillWidth: true
            }
        }
    }

    pageStack.initialPage: MainPage {
        appDrawer: sourceDrawer
    }
}
