import QtQuick
import org.kde.kirigami.layouts as KirigamiLayouts

// Widgets QFormLayout parity.
//
// Kirigami's FormLayout sizes its internal grid to the form's *natural*
// width and centers it inside the item: in a wide dialog that leaves a
// hole to the left of the labels and keeps the fields at their implicit
// width instead of filling the row. The widgets form layout instead
// sizes the label column to its widest label and gives the rest to the
// field column, so bind the implicit width to the actual one and let
// the field items (Layout.fillWidth) take the remaining space.
//
// Use this everywhere a FormLayout mirrors a widgets QFormLayout panel.
KirigamiLayouts.FormLayout {
    implicitWidth: width
}
