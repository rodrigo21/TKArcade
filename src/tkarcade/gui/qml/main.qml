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
        title: qsTr("TKArcade")
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

    pageStack.initialPage: MainPage {}
}
