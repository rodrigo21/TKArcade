import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Shared table header title: full-bleed Button background (the lighter
// toolbar bar) with bold centered toolbar text. Carries its own
// implicit size from the label: without it the delegate collapses
// to 0x0 and text+background vanish.
Item {
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Button
    implicitWidth: titleLabel.implicitWidth + Kirigami.Units.smallSpacing * 2
    implicitHeight: titleLabel.implicitHeight + Kirigami.Units.smallSpacing * 2

    Rectangle {
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
    }
    Controls.Label {
        id: titleLabel
        anchors.fill: parent
        text: modelData ?? ""
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        font.bold: true
        color: Kirigami.Theme.textColor
    }
}
