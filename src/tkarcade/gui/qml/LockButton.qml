import QtQuick
import QtQuick.Controls as Controls

// Per-field metadata lock: a locked field is never written by Download
// Metadata, even with "Replace existing values" on. The icon carries the
// state and the tooltip names the click action.
Controls.ToolButton {
    id: root

    //: [metadata] field name this toggle locks, e.g. "developer".
    property string key: ""
    property bool locked: false

    objectName: "settingsLock" + key.charAt(0).toUpperCase() + key.slice(1)
    display: Controls.AbstractButton.IconOnly
    icon.name: gameModel.iconName(locked
        ? ["object-locked", "changes-prevent-symbolic", "lock"]
        : ["object-unlocked", "changes-allow-symbolic", "lock"])
    Controls.ToolTip.text: locked
        ? qsTr("Locked Against Metadata Downloads; Click to Unlock")
        : qsTr("Lock This Field Against Metadata Downloads")
    Controls.ToolTip.visible: hovered
}
