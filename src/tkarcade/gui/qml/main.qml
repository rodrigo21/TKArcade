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
        // Fallback chain: input-gamepad misses oxygen (applications-games
        // covers it there).
        handleClosedIcon.name: gameModel.iconName(["input-gamepad", "applications-games"])
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
                    icon.name: gameModel.iconName(["input-gamepad", "applications-games"])
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
            },
            Kirigami.Action {
                objectName: "drawerCategory"
                text: gameFilter.categoryKey === "" ? qsTr("Category: All") : qsTr("Category: %1").arg(
                    gameFilter.categoryKey)
                onTriggered: categoryDialog.openDialog()
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

    CategoryDialog {
        id: categoryDialog
    }

    // Tray context menu, opened from the tray controller through the model
    // (the shell runs on a QGuiApplication, so a QtWidgets QMenu is not an
    // option). Forced to its own window: the shell is usually hidden while
    // the tray is in use, and an embedded popup would be clipped to it.
    Connections {
        target: gameModel
        function onTrayMenuRequested(x, y) {
            // Global coordinates from the tray host, mapped into the
            // menu's parent item (the window content item).
            var pos = root.contentItem.mapFromGlobal(x, y)
            trayMenu.popup(root.contentItem, pos.x, pos.y)
        }
    }

    Controls.Menu {
        id: trayMenu
        objectName: "trayMenu"
        popupType: Controls.Popup.Window
        // Recents go right after "Show / Hide" + its separator, so the
        // Instantiator's own indexes get that offset.
        readonly property int recentsBase: 2

        // Freshness: the recents are rebuilt before every open.
        onAboutToShow: recents.model = gameModel.trayRecentGames()

        Controls.MenuItem {
            objectName: "trayShowHide"
            text: qsTr("Show / Hide")
            onTriggered: gameModel.trayAction("toggle")
        }
        Controls.MenuSeparator {
            objectName: "traySepRecentsTop"
            visible: recents.count > 0
        }
        Instantiator {
            id: recents
            model: []
            delegate: Controls.MenuItem {
                objectName: "trayRecent" + index
                text: modelData[1]
                onTriggered: gameModel.trayAction("play:" + modelData[0])
            }
            onObjectAdded: (index, object) => trayMenu.insertItem(trayMenu.recentsBase + index,
                                                                  object)
            onObjectRemoved: (index, object) => trayMenu.removeItem(object)
        }
        Controls.MenuSeparator {
            objectName: "traySepRecentsBottom"
            visible: recents.count > 0
        }
        Controls.MenuItem {
            objectName: "trayDefaults"
            text: qsTr("Global Defaults...")
            visible: gameModel.trayDefaultsAvailable()
            onTriggered: gameModel.trayAction("defaults")
        }
        Controls.MenuItem {
            objectName: "trayPrefs"
            text: qsTr("Preferences...")
            onTriggered: gameModel.trayAction("prefs")
        }
        Controls.MenuItem {
            objectName: "trayAbout"
            text: qsTr("About...")
            onTriggered: gameModel.trayAction("about")
        }
        Controls.MenuSeparator {
        }
        Controls.MenuItem {
            objectName: "trayQuit"
            text: qsTr("Quit")
            // Same as Ctrl+Q: skips onClosing, so Close-to-tray can never
            // swallow the tray quit.
            onTriggered: Qt.quit()
        }
    }
}
