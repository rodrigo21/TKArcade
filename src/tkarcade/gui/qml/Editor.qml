import QtQuick
import QtQuick.Window

// Standalone editor host, loaded by gui/edit.py in its own process (the
// CLI --edit / --menu flows spawn it so the launcher stays stdlib-only
// and gets a sanitized environment).
//
// The UI windows are created at runtime with createObject(null): a
// Window declared inside another window is not shown while the enclosing
// one is hidden (measured on Qt 6.12, offscreen and Wayland), and this
// editor deliberately has no main window of its own -- only the settings
// window (or the pre-launch menu, then the settings) is the UI.
Window {
    id: editor
    objectName: "editorRoot"
    visible: false
    width: 1
    height: 1

    property string mode: "edit" // "edit" | "menu" | "firstrun"
    property string appid: ""
    property string name: ""
    property int timeout: 0
    property bool canLaunch: true
    property bool pick: false
    // Runtime inferred from the launch command, preselected on first run.
    property string runtime: ""
    // Kept alive for the whole run: a createObject(null) window dies with
    // its JS reference (it has no QObject parent).
    property var settings: null
    property var prelaunch: null
    property var picker: null
    property var firstrun: null

    // The selected outcome, read by edit.py: "launch" | "saved" |
    // "cancelled", plus the AppID the window ended up editing.
    signal decided(string outcome, string appid)

    function create(file, properties) {
        var component = Qt.createComponent(Qt.resolvedUrl(file))
        if (component.status !== Component.Ready) {
            console.log("tkarcade: cannot load " + file + ": " + component.errorString())
            return null
        }
        return component.createObject(null, properties)
    }

    function start() {
        if (mode === "menu") {
            openMenu()
            return
        }
        if (mode === "firstrun") {
            openFirstRun()
            return
        }
        if (appid !== "") {
            openSettings(appid, null)
            return
        }
        if (pick) {
            openPicker()
            return
        }
        // Nothing to edit: the launcher reads this as a normal cancel.
        decided("cancelled", "")
    }

    function openSettings(forAppid, parentWindow, tab, preselectRuntime) {
        if (settings === null) {
            settings = create("GameSettings.qml", {
                "launchMode": mode === "edit",
                "canLaunch": canLaunch
            })
            if (settings === null) {
                decided(mode === "firstrun" ? "launch" : "cancelled", appid)
                return
            }
            settings.finished.connect(function (outcome) {
                if (editor.mode === "edit") {
                    editor.decided(outcome, editor.appid)
                } else if (editor.mode === "firstrun") {
                    // Saved or dismissed: the user's intent is still to play.
                    editor.decided("launch", editor.appid)
                }
                // In menu mode the settings window is modal on the menu and
                // its result is ignored: Launch/Cancel stay the menu's call
                // (widgets MenuDialog parity -- it ran the editor with no
                // launch buttons).
            })
        }
        editor.appid = forAppid
        settings.transientParent = parentWindow
        settings.initialTab = tab || 0
        settings.preselectRuntime = preselectRuntime || ""
        settings.openFor(forAppid)
    }

    function openFirstRun() {
        var label = runtime === "proton" ? qsTr("Proton") : qsTr("Native (Steam Runtime)")
        firstrun = create("ConfirmDialog.qml", {
            "title": name !== "" ? name : qsTr("TKArcade"),
            "question": qsTr("This game has no runtime configured yet."),
            "detail": qsTr("The launch command uses %1. Configure it now?").arg(label),
            "acceptText": qsTr("Configure"),
            "rejectText": qsTr("Not now"),
            "softIcon": true
        })
        if (firstrun === null) {
            // Creation failure must not cost the launch: infer and play.
            decided("launch", appid)
            return
        }
        firstrun.accepted.connect(function () {
            firstrun.visible = false
            openSettings(appid, null, 1, runtime)
        })
        firstrun.closing.connect(function () {
            decided("launch", appid)
        })
        firstrun.open(null)
    }

    function openPicker() {
        picker = create("EditorPicker.qml", { "games": gameModel.pickableGames() })
        if (picker === null) {
            decided("cancelled", "")
            return
        }
        picker.finished.connect(function (chosen) {
            if (chosen === "") {
                editor.decided("cancelled", "")
                return
            }
            editor.openSettings(chosen, null)
        })
        picker.openIt()
    }

    function openMenu() {
        prelaunch = create("PrelaunchMenu.qml", {
            "appid": appid,
            "name": name,
            "timeout": timeout,
            "canLaunch": canLaunch
        })
        if (prelaunch === null) {
            decided("cancelled", "")
            return
        }
        prelaunch.settingsRequested.connect(function () {
            editor.openSettings(editor.appid, prelaunch)
        })
        prelaunch.finished.connect(function (outcome) {
            editor.decided(outcome, editor.appid)
        })
        prelaunch.openMenu()
    }
}
