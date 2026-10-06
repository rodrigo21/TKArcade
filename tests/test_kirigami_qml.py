"""QML smoke: main.qml loads warning-free with a live model (offscreen)."""

OFFSCREEN_NOISE = ("was not placed in the graphics scene",)


def test_main_qml_loads_with_model(qgui_app, xdg_env):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)

    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    model = GameListModel(engine)  # parented: survives without the Python ref
    engine.rootContext().setContextProperty("gameModel", model)
    del model
    import gc

    gc.collect()
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    real = [w for w in warnings if not any(n in w for n in OFFSCREEN_NOISE)]
    assert real == []

    root = engine.rootObjects()[0]
    view = root.findChild(QQuickItem, "gameList")
    assert view is not None
    qgui_app.processEvents()
    assert view.property("count") == 1


def test_game_delegate_binds_roles(qgui_app):
    """The delegate compiles and binds: this is what broke on Qt6 (`model.`)."""
    import pathlib

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    from tkarcade.gui import kirigami_app as kapp

    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    url = QUrl.fromLocalFile(str(pathlib.Path(kapp.__file__).parent / "qml" / "GameDelegate.qml"))
    component = QQmlComponent(engine, url)
    assert component.isReady(), component.errorString()
    item = component.createWithInitialProperties(
        {"gameName": "Doom", "gameId": "local-doom", "gameSource": "Local"}
    )
    assert item is not None
    qgui_app.processEvents()
    assert item.property("title") == "Doom"
    assert item.property("subtitle") == "local-doom · Local"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
