import QtQuick
import QtQml
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Games list page: search on top, rows below, counts at the bottom.
// The page expects `gameModel` (GameListModel) and `gameFilter`
// (GameFilterModel over it) as context properties.
Kirigami.ScrollablePage {
    id: gamesPage
    title: qsTr("Games")

    actions: [
        Kirigami.Action {
            text: qsTr("Add game")
            icon.name: "list-add"
            onTriggered: addDialog.open()
        }
    ]

    header: Controls.Pane {
        padding: 0
        background: null
        RowLayout {
            anchors.fill: parent
            Kirigami.SearchField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: qsTr("Filter by name or ID…")
                onTextChanged: gameFilter.textQuery = text
            }
        }
    }

    ListView {
        id: gameList
        objectName: "gameList"
        model: gameFilter
        delegate: GameDelegate {
            width: ListView.view.width
            onPlayRequested: (gid) => gameModel.play(gid)
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: gameList.count === 0
            text: qsTr("No games yet")
            explanation: qsTr("Add a native Linux game to get started.")
        }
    }

    footer: RowLayout {
        Controls.Label {
            text: qsTr("%1 configured · %2 Steam games detected").arg(gameModel.totalCount).arg(gameModel.steamDetectedCount)
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
                    onClicked: gameModel.browseExecutable()
                }
                Connections {
                    target: gameModel
                    function onBrowseFinished(picked) {
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
