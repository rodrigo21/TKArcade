import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Widgets QGroupBox parity: the section title sits centered above a
// framed panel and the content is padded inside the frame (Breeze
// centers the QGroupBox title; the QQC2 GroupBox of the desktop style
// puts it inside the frame at the top-left, which is what made the
// settings tabs look unlike the widgets dialogs). `checkable` mirrors
// QGroupBox::setCheckable: the title becomes a centered checkbox and
// the content hides when unchecked. Unlike the widgets frame (which
// stayed drawn and empty), an unchecked box collapses completely, so
// toggling a block off frees its whole height.
//
// Children go into the frame's ColumnLayout, so each one needs
// `Layout.fillWidth: true` (a nested KirigamiLayouts.FormLayout works
// the same way).
ColumnLayout {
    id: root

    property string title: ""
    property bool checkable: false
    property alias checked: titleBox.checked
    default property alias content: frameColumn.data
    property real padding: Kirigami.Units.largeSpacing

    // A collapsed box (frame hidden) has the title checkbox as its only
    // visible child, and a layout item is then clamped to that implicit
    // width: the box would shrink to the checkbox. The hint keeps it
    // filling whatever the host layout gives it.
    Layout.maximumWidth: Number.POSITIVE_INFINITY

    spacing: Kirigami.Units.smallSpacing

    Controls.CheckBox {
        id: titleBox
        objectName: "sectionTitle"
        Layout.alignment: Qt.AlignHCenter
        visible: root.checkable && root.title !== ""
        text: root.title
    }

    Controls.Label {
        objectName: "sectionTitleText"
        Layout.fillWidth: true
        visible: !root.checkable && root.title !== ""
        text: root.title
        horizontalAlignment: Text.AlignHCenter
    }

    Controls.Frame {
        id: frame
        objectName: "sectionFrame"
        Layout.fillWidth: true
        padding: 0
        visible: !root.checkable || root.checked
        implicitHeight: frameColumn.implicitHeight + root.padding * 2

        ColumnLayout {
            id: frameColumn
            anchors.fill: parent
            anchors.margins: root.padding
            spacing: Kirigami.Units.smallSpacing
        }
    }
}
