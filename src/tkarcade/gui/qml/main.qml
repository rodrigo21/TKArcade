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
        root.rebuildCategories()
        // Kirigami ships its own Quit action (StandardKey.Quit) that
        // calls close() instead of quitting: with a tray up the close
        // is caught and hidden, so Ctrl+Q never quits. Clear it; our
        // Shortcut below owns the sequence.
        root.quitAction.shortcut = ""
    }

    // Objects from Component.createObject are JavaScript-owned: the
    // children list holds raw pointers and does not root them, so the
    // current batch must stay referenced from JS or the engine collects
    // it (the list entries turn null). The previous batch is destroyed
    // explicitly when replaced.
    property var categoryActions: []
    // Categories outlive their game tags (zero counts stay listed), so the
    // section shows while the store has entries, not while a tag is used.
    property bool hasCategories: false

    // The sidebar Categories section: the drawer paints the header plus
    // these children inline (popup when collapsed), so the list is rebuilt
    // from the categories on record instead of declaring actions up front.
    // Plain string model data from user categories never reaches
    // Qt.createQmlObject.
    Component {
        id: categoryAllComponent
        Kirigami.Action {
            objectName: "categoryAllAction"
            text: qsTr("All Categories (%1)").arg(gameModel.totalCount)
            icon.name: gameModel.iconName(["folder-documents", "folder"])
            checked: gameFilter.categoryKey === ""
            onTriggered: gameFilter.categoryKey = ""
        }
    }
    Component {
        id: categoryEntryComponent
        Kirigami.Action {
            objectName: "categoryAction_" + category
            property string category
            property string iconSource
            icon.name: iconSource
            checked: gameFilter.categoryKey === category
            onTriggered: gameFilter.categoryKey =
                gameFilter.categoryKey === category ? "" : category
        }
    }
    Component {
        id: categoryManageComponent
        Kirigami.Action {
            objectName: "categoryManageAction"
            text: qsTr("Edit Categories")
            icon.name: gameModel.iconName(["applications-system", "applications-system-symbolic"])
            onTriggered: categoryManager.open(root)
        }
    }
    // Lines framing the manage row, so it reads apart from the entries
    // without giving up its place at the top.
    Component {
        id: categoryRuleComponent
        Kirigami.Action {
            separator: true
        }
    }

    function rebuildCategories() {
        var cats = gameModel.allCategories()
        root.hasCategories = cats.length > 0
        if (gameFilter.categoryKey !== "" && cats.indexOf(gameFilter.categoryKey) < 0) {
            gameFilter.categoryKey = ""
        }
        var counts = gameModel.categoryCounts()
        var icons = gameModel.categoryIcons()
        var made = [
            categoryRuleComponent.createObject(categoriesSection, {
                "objectName": "categoryRuleTop"
            }),
            categoryManageComponent.createObject(categoriesSection),
            categoryRuleComponent.createObject(categoriesSection, {
                "objectName": "categoryRuleBottom"
            }),
            categoryAllComponent.createObject(categoriesSection)
        ]
        for (var i = 0; i < cats.length; i++) {
            made.push(categoryEntryComponent.createObject(categoriesSection, {
                "text": qsTr("%1 (%2)").arg(cats[i]).arg(counts[cats[i]] || 0),
                "category": cats[i],
                "iconSource": icons[cats[i]] || "folder"
            }))
        }
        var old = categoryActions
        categoryActions = made
        categoriesSection.children = made
        for (var j = 0; j < old.length; j++) {
            old[j].destroy()
        }
    }

    Connections {
        target: gameModel
        function onRefreshed() {
            root.rebuildCategories()
        }
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
                    Controls.ToolTip.text: sourceDrawer.collapsed ? qsTr("Expand Sidebar") : qsTr("Collapse Sidebar")
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
                id: originsSection
                objectName: "drawerOrigins"
                text: qsTr("Origins")
                icon.name: gameModel.iconName(["folder-games", "applications-games", "input-gamepad"])
                expandible: true
                Kirigami.Action {
                    objectName: "drawerSourceAll"
                    text: qsTr("All Games (%1)").arg(gameModel.totalCount)
                    icon.name: gameModel.iconName(["view-grid", "view-list-details"])
                    checked: gameFilter.sourceKey === "all"
                    onTriggered: gameFilter.sourceKey = "all"
                }
                Kirigami.Action {
                    objectName: "drawerSourceSteam"
                    text: qsTr("Steam (%1)").arg(gameModel.steamCount)
                    icon.name: gameModel.iconName(["steam", "applications-games"])
                    checked: gameFilter.sourceKey === "steam"
                    onTriggered: gameFilter.sourceKey = "steam"
                }
                Kirigami.Action {
                    objectName: "drawerSourceLocal"
                    text: qsTr("Local (%1)").arg(gameModel.localCount)
                    icon.name: gameModel.iconName(["computer", "utilities-terminal"])
                    checked: gameFilter.sourceKey === "local"
                    onTriggered: gameFilter.sourceKey = "local"
                }
            },
            Kirigami.Action {
                // A separating line between the two filter sections.
                objectName: "drawerSeparator"
                separator: true
                visible: root.hasCategories
            },
            Kirigami.Action {
                id: categoriesSection
                objectName: "drawerCategories"
                text: qsTr("Categories")
                icon.name: gameModel.iconName(["tag-symbolic", "tag", "view-grid"])
                expandible: true
                visible: root.hasCategories
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

    // Per-category management: the manager lists every category on record,
    // the editor holds one category's icon, games and delete.
    CategoryManagerDialog {
        id: categoryManager
        objectName: "categoryManager"
        onEditRequested: function(name) {
            categoryEditor.categoryName = name
            categoryEditor.reload()
            categoryEditor.open(categoryManager)
        }
    }

    CategoryEditorDialog {
        id: categoryEditor
        objectName: "categoryEditor"
    }

    pageStack.initialPage: MainPage {
        appDrawer: sourceDrawer
    }
}
