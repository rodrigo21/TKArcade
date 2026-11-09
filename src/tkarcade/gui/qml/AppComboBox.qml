import QtQuick
import QtQuick.Controls as Controls

// The desktop ComboBox style sizes its popup from the widest item, not
// from the field (org.kde.desktop: `Menu.implicitWidth` loops over the
// items). Every combo in this app uses this wrapper so the popup lines
// up with the field, like the widgets QComboBox.
Controls.ComboBox {
    id: root

    popup.width: root.width
    readonly property real popupWidth: popup.width
    readonly property bool popupVisible: popup.visible

    function openPopup() {
        popup.open()
    }

    function closePopup() {
        popup.close()
    }
}
