"""QML smoke: main.qml loads warning-free with a live model (offscreen)."""

OFFSCREEN_NOISE = ("was not placed in the graphics scene",)


def test_main_qml_loads_with_model(qgui_app, xdg_env):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

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
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    del model
    del game_filter
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
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (registers QQuickItem wrapper)

    from tkarcade.gui import kirigami_app as kapp

    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    from tkarcade.gui.model import GameFilterModel, GameListModel

    grip = GameFilterModel(engine)
    grip.setSourceModel(GameListModel(engine))
    engine.rootContext().setContextProperty("gameFilter", grip)
    url = QUrl.fromLocalFile(str(pathlib.Path(kapp.__file__).parent / "qml" / "GameDelegate.qml"))
    component = QQmlComponent(engine, url)
    assert component.isReady(), component.errorString()
    item = component.createWithInitialProperties(
        {
            "gameName": "Doom",
            "gameId": "local-doom",
            "gamePlayed": "38s",
            "gameSource": "Local",
            "gameTier": "Gold",
            "gameTierBg": "#FFC107",
            "gameTierFg": "#000000",
            "gameIcon": "",
        }
    )
    assert item is not None
    qgui_app.processEvents()

    def texts(obj):
        out = []
        try:
            text = obj.property("text")
        except Exception:
            text = None
        if isinstance(text, str) and text:
            out.append(text)
        for child in obj.childItems():
            out += texts(child)
        return out

    got = set(texts(item))
    assert {"Doom", "38s", "Gold"} <= got
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def test_list_row_double_click_plays(qgui_app, xdg_env, monkeypatch):
    """Double-clicking a row invokes play() with that game's id."""
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QTest

    from tkarcade import config as C
    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

    cfg = C.GameConfig()
    cfg.general.appid = "77"
    C.save(cfg)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    model = GameListModel(engine)
    engine.rootContext().setContextProperty("gameModel", model)
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    played = []
    monkeypatch.setattr(model, "play", lambda gid: played.append(gid) or True)
    win = engine.rootObjects()[0]
    assert isinstance(win, QQuickWindow)
    win.setProperty("width", 1280)
    win.setProperty("height", 720)
    win.show()
    qgui_app.processEvents()
    view = win.findChild(QQuickItem, "gameList")
    assert view is not None
    row = view.childItems()[0]
    from PySide6.QtCore import QPointF

    pos = row.mapToScene(QPointF((row.property("width") or 200) / 2, 10)).toPoint()
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert played == ["77"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_header_sort_toggles_indicator_and_order(qgui_app, xdg_env):
    """Header taps drive proxy sort; the indicator follows the state."""
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow

    from tkarcade import config as C
    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    model = GameListModel(engine)
    engine.rootContext().setContextProperty("gameModel", model)
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    win = engine.rootObjects()[0]
    assert isinstance(win, QQuickWindow)
    win.setProperty("width", 1280)
    win.setProperty("height", 720)
    win.show()
    qgui_app.processEvents()
    page = win.findChild(QObject, "gamesPage")
    assert page is not None
    labels = [
        o for o in page.findChildren(QObject) if o.property("text") in ("Game", "▲ Game", "▼ Game")
    ]
    assert labels, "Game header label missing"
    page.toggleSort("gameId")
    qgui_app.processEvents()
    assert page.property("sortRole") == "gameId"
    texts = [o.property("text") for o in page.findChildren(QObject) if isinstance(o, QQuickItem)]
    assert any(str(t).startswith("▲") and "App ID" in str(t) for t in texts if t)
    rows = [
        game_filter.data(game_filter.index(r, 0), GameListModel.IdRole)
        for r in range(game_filter.rowCount())
    ]
    assert rows == ["a-game", "b-game"]
    page.toggleSort("gameId")
    qgui_app.processEvents()
    rows = [
        game_filter.data(game_filter.index(r, 0), GameListModel.IdRole)
        for r in range(game_filter.rowCount())
    ]
    assert rows == ["b-game", "a-game"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def _delegate_rows(view):
    """Direct ListView delegates only: one level, no deep tree walk.

    Deep childItems() recursion crashes (pooled/dead QML wrappers);
    one level down from contentItem is all we need (delegates carry
    gameId, their labels carry objectName/text one more level down).
    """
    import shiboken6

    rows = []
    try:
        kids = list(view.property("contentItem").childItems())
    except Exception:
        return []
    for child in kids:
        try:
            if not shiboken6.isValid(child):
                continue
            if child.property("gameId"):
                rows.append(child)
        except Exception:
            continue
    return rows


def _row_numbers(view):
    """Row-number label texts, two levels max (delegate -> rowNumber)."""
    import shiboken6
    from PySide6.QtQuick import QQuickItem

    out = []
    for delegate in _delegate_rows(view):
        try:
            kids = list(delegate.childItems())
        except Exception:
            continue
        for label in kids:
            try:
                if not shiboken6.isValid(label):
                    continue
                if not isinstance(label, QQuickItem):
                    continue
                if label.property("objectName") != "rowNumber":
                    continue
                text = label.property("text")
                if isinstance(text, str) and text.strip():
                    out.append(text.strip())
            except Exception:
                continue
    return out


def _delegate_label_visible(view, text):
    """True when any delegate shows a visible direct-child label with text."""
    import shiboken6
    from PySide6.QtQuick import QQuickItem

    for delegate in _delegate_rows(view):
        try:
            kids = list(delegate.childItems())
        except Exception:
            continue
        for label in kids:
            try:
                if not shiboken6.isValid(label):
                    continue
                if not isinstance(label, QQuickItem) or not label.isVisible():
                    continue
                if label.property("text") == text:
                    return True
                # Name lives one level deeper (ColumnLayout -> nameLabel).
                try:
                    grandkids = list(label.childItems())
                except Exception:
                    continue
                for grand in grandkids:
                    try:
                        if not shiboken6.isValid(grand):
                            continue
                        if (
                            isinstance(grand, QQuickItem)
                            and grand.isVisible()
                            and grand.property("text") == text
                        ):
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
    return False


def _load_main(qgui_app, engine_out=None):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow

    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    model = GameListModel(engine)
    engine.rootContext().setContextProperty("gameModel", model)
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    win = engine.rootObjects()[0]
    assert isinstance(win, QQuickWindow)
    win.setProperty("width", 1280)
    win.setProperty("height", 720)
    win.show()
    qgui_app.processEvents()
    return win, engine, game_filter, warnings


def test_row_selection_follows_tap(qgui_app, xdg_env):
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    from PySide6.QtCore import QObject

    page = win.findChild(QObject, "gamesPage")
    view = win.findChild(QQuickItem, "gameList")
    assert view.property("currentIndex") == 0
    from PySide6.QtCore import QPointF

    rows = sorted(_delegate_rows(view), key=lambda c: c.y())
    assert len(rows) >= 2
    second = rows[1]
    center = second.mapToScene(QPointF(second.property("width") / 2, 10)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    qgui_app.processEvents()
    assert view.property("currentIndex") == 1
    assert page is not None
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_row_numbers_follow_proxy_order(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    view = win.findChild(QQuickItem, "gameList")
    assert sorted(_row_numbers(view)) == ["1", "2"]
    proxy.sortBy("gameId", True)
    qgui_app.processEvents()
    assert sorted(_row_numbers(view)) == ["1", "2"]  # positional rows
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_columns_menu_hides_app_id(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    view = win.findChild(QQuickItem, "gameList")
    assert _delegate_label_visible(view, "local-doom")
    proxy.setProperty("showAppId", False)
    qgui_app.processEvents()
    assert not _delegate_label_visible(view, "local-doom")
    assert _delegate_label_visible(view, "Doom")
    proxy.setProperty("showAppId", True)
    qgui_app.processEvents()
    assert _delegate_label_visible(view, "local-doom")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()
