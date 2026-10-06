import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as Delegates

Kirigami.ApplicationWindow {
    id: root
    title: qsTr("TKArcade")
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 20
    width: minimumWidth
    height: minimumHeight

    pageStack.initialPage: gamesPage

    Component {
        id: gamesPage
        Kirigami.ScrollablePage {
            id: games
            title: qsTr("Games")
            actions: [
                Kirigami.Action {
                    text: qsTr("Add game")
                    icon.name: "list-add"
                    onTriggered: addDialog.open()
                }
            ]

            ListView {
                id: gameList
                objectName: "gameList"
                model: gameModel
                delegate: GameDelegate {
                    onPlayRequested: (gid) => gameModel.play(gid)
                }
                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    visible: gameList.count === 0
                    text: qsTr("No games yet")
                    explanation: qsTr("Add a native Linux game to get started.")
                }
            }
        }
    }

    Kirigami.Dialog {
        id: addDialog
        objectName: "addDialog"
        title: qsTr("Add local game")
        padding: Kirigami.Units.largeSpacing

        ColumnLayout {
            Controls.TextField {
                id: nameField
                placeholderText: qsTr("Game name")
                Layout.fillWidth: true
            }
            RowLayout {
                Layout.fillWidth: true
                Controls.TextField {
                    id: exeField
                    placeholderText: qsTr("Game executable")
                    Layout.fillWidth: true
                }
                Controls.Button {
                    text: qsTr("Browse…")
                    onClicked: {
                        var picked = gameModel.browseExecutable()
                        if (picked !== "") {
                            exeField.text = picked
                            if (nameField.text === "") {
                                var parts = picked.split("/")
                                nameField.text = parts[parts.length - 1]
                            }
                        }
                    }
                }
            }
            Controls.Label {
                id: addError
                visible: text !== ""
                color: Kirigami.Theme.negativeTextColor
            }
        }

        footer: RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Add")
                onClicked: {
                    var created = gameModel.addLocal(nameField.text, exeField.text)
                    if (created === "") {
                        addError.text = qsTr("Name and a valid executable are required.")
                    } else {
                        nameField.text = ""
                        exeField.text = ""
                        addError.text = ""
                        addDialog.close()
                    }
                }
            }
            Controls.Button {
                text: qsTr("Cancel")
                onClicked: addDialog.close()
            }
        }
    }
}
