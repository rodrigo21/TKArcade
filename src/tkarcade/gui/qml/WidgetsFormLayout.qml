import QtQuick
import QtQuick.Layouts
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
// Kirigami also drops to a one-column form (label above the field) as soon
// as the form is narrower than its *natural* width, which it measures from
// the widest row: a long wrapped hint label that is hidden, or a wide
// placeholder, can trip it in a dialog that fits the screen. A widgets
// QFormLayout keeps the label column at any width and squeezes the fields,
// so pin wideMode instead of letting the width decide.
//
// Use this everywhere a FormLayout mirrors a widgets QFormLayout panel.
KirigamiLayouts.FormLayout {
    id: root

    implicitWidth: width
    wideMode: true

    // Label column width for the whole tab, in pixels: every form in a
    // tab sets the same value so the fields start at one x across the
    // section frames. -1 keeps this form's own natural column.
    property real labelWidth: -1

    // The column this form needs for its own labels. Kirigami's own
    // `buddiesImplicitWidth` truncates to an int while the row container
    // rounds each label up, so recompute it the way the grid does. Tabs
    // take the maximum over their forms and feed it back as `labelWidth`.
    readonly property real naturalLabelWidth: {
        const grid = children.length > 0 ? children[0] : null
        if (!grid || !grid.buddies) {
            return 0
        }
        let hint = 0
        for (let i = 0; i < grid.buddies.length; ++i) {
            const buddy = grid.buddies[i]
            const item = buddy.item
            if (!buddy.visible || !item || item.KirigamiLayouts.FormData.isSection) {
                continue
            }
            hint = Math.max(hint, Math.ceil(buddy.implicitWidth))
        }
        return hint
    }

    function applyLabelWidth(): void {
        if (labelWidth <= 0 || children.length === 0) {
            return
        }
        const grid = children[0]
        // The grid leads with two spacers, one per column; there is no
        // public API for the column widths.
        if (grid.children.length < 2) {
            return
        }
        const width = Math.max(labelWidth, naturalLabelWidth)
        const leading = grid.children[0]
        leading.Layout.minimumWidth = width
        leading.Layout.preferredWidth = width
        leading.Layout.maximumWidth = width
        for (let i = 0; i < grid.buddies.length; ++i) {
            grid.buddies[i].Layout.maximumWidth = width
        }
        // With room to spare the grid shares it between the columns in
        // proportion to their preferred widths, growing the label column
        // past its maximum. Size the field column to the remainder so the
        // two preferred widths add up to the form: no share, no growth.
        grid.children[1].Layout.preferredWidth =
            Math.max(0, root.width - width - grid.columnSpacing)
    }

    Component.onCompleted: applyLabelWidth()
    onLabelWidthChanged: applyLabelWidth()
    onNaturalLabelWidthChanged: applyLabelWidth()
    onWidthChanged: applyLabelWidth()
}
