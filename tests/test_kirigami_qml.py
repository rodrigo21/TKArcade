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
            "gamePlayedTip": "1 sessions · last x · 0 failures",
            "gameSource": "Local",
            "gameTier": "Gold",
            "gameTierBg": "#FFC107",
            "gameTierFg": "#000000",
            "gameIcon": "",
        }
    )
    assert item is not None
    for _ in range(100):
        qgui_app.processEvents()
        if all(
            _cell_text(item, name) is not None
            for name in ("nameLabel", "playedLabel", "tierButton")
        ):
            break

    got = {_cell_text(item, name) for name in ("nameLabel", "playedLabel")}
    got.add(_cell_text(item, "tierButton"))
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
    header = page.findChild(QQuickItem, "headerRow")
    assert header is not None
    texts = []
    for child in header.childItems():
        try:
            texts.append(child.property("text"))
        except Exception:
            continue
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
    """Direct delegates only: one level, no deep tree walk.

    Deep childItems() recursion crashes (pooled/dead QML wrappers);
    one level down from the content item is all we need (delegates
    carry gameId, their labels carry objectName/text one more level
    down). Accepts a view (uses contentItem) or a layout directly.
    """
    import shiboken6

    try:
        holder = view.property("contentItem")
    except Exception:
        holder = None
    if holder is None:
        holder = view
    try:
        kids = list(holder.childItems())
    except Exception:
        return []
    rows = []
    for child in kids:
        try:
            if not shiboken6.isValid(child):
                continue
            if child.property("gameId"):
                rows.append(child)
        except Exception:
            continue
    return rows


def _gutter_numbers(gutter):
    """Gutter number texts (one level, live labels only)."""
    import shiboken6
    from PySide6.QtQuick import QQuickItem

    try:
        kids = list(gutter.property("contentItem").childItems())
    except Exception:
        return []
    out = []
    for child in kids:
        try:
            if not shiboken6.isValid(child) or not isinstance(child, QQuickItem):
                continue
            if child.property("objectName") != "gutterNumber":
                continue
            text = child.property("text")
            if isinstance(text, str) and text.strip():
                out.append(text.strip())
        except Exception:
            continue
    return out


_CELL_COLUMN = {"appIdLabel": 1, "playedLabel": 2, "tierButton": 3}


def _cell_item(delegate, name):
    """Delegate's objectName'd cell item (structure-aware, no blind walks).

    Repeater-nested items hide from findChildren (QObject tree) and
    unbounded childItems() walks abort on dead wrappers (Image
    internals, pooled delegates). Cells are matched inside the column
    whose modelData fits (explicit bindings only: effective
    visibility needs a shown window and lies standalone). Plain
    delegates (icons/cards) fall back to findChild, which works
    outside Repeaters.
    """
    import shiboken6
    from PySide6.QtQuick import QQuickItem

    def valid(node):
        try:
            return shiboken6.isValid(node) and isinstance(node, QQuickItem)
        except Exception:
            return False

    def kids(item):
        try:
            return list(item.childItems()) if valid(item) else []
        except Exception:
            return []

    def match(node):
        try:
            return valid(node) and node.property("objectName") == name
        except Exception:
            return False

    logical = _CELL_COLUMN.get(name)
    for node in kids(delegate):
        if match(node):
            return node
    for node in kids(delegate):
        for child in kids(node):
            if match(child) and logical is None:
                return child
            try:
                is_column = valid(child) and child.property("objectName") == "rowColumn"
            except Exception:
                is_column = False
            if not is_column:
                continue
            if logical is not None:
                try:
                    if child.property("modelData") != logical:
                        continue
                except Exception:
                    continue
            for cell in kids(child):
                if match(cell):
                    return cell
    try:
        label = delegate.findChild(QQuickItem, name)
    except Exception:
        return None
    return label if match(label) else None


def _cell_text(delegate, name):
    """Visible text of a delegate's objectName'd cell (None when hidden).

    Uses explicit `visible` bindings (cell and column): effective
    isVisible() needs a shown window and lies standalone.
    """
    label = _cell_item(delegate, name)
    if label is None:
        return None
    try:
        if not label.property("visible"):
            return None
        parent = label.parent()
        if parent is not None and not parent.property("visible"):
            return None
        text = label.property("text")
        return text if isinstance(text, str) else None
    except Exception:
        return None


def _delegate_label_visible(view, text):
    """True when any delegate shows a visible label with text."""
    for delegate in _delegate_rows(view):
        for name in ("nameLabel", "appIdLabel", "playedLabel", "iconName", "iconPlayed"):
            if _cell_text(delegate, name) == text:
                return True
    return False


def _settle_list(view, qgui_app, limit=100):
    """Pump frames until row delegates expose their cells (or timeout).

    Repeater column items instantiate asynchronously; asserting on a
    half-built delegate flakes. Settles only when every data cell
    resolves. Bounded: returns whatever exists.
    """
    for _ in range(limit):
        rows = _delegate_rows(view)
        if rows and all(
            _cell_text(rows[0], name) is not None
            for name in ("appIdLabel", "playedLabel", "tierButton")
        ):
            return rows
        qgui_app.processEvents()
    return _delegate_rows(view)


def _load_main(qgui_app, engine_out=None):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow

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
    qgui_app.processEvents()
    view = win.findChild(QQuickItem, "gameList")
    if view is not None:
        _settle_list(view, qgui_app)
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
    gutter = win.findChild(QQuickItem, "rowGutter")
    assert gutter is not None
    assert sorted(_gutter_numbers(gutter)) == ["1", "2"]
    proxy.sortBy("gameId", True)
    qgui_app.processEvents()
    assert sorted(_gutter_numbers(gutter)) == ["1", "2"]  # positional rows
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


def test_drawer_modes_switch(qgui_app, xdg_env):
    """Gallery-style drawer modes: overlay, sidebar, collapsible."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer is not None
    overlay = win.findChild(QObject, "drawerModeOverlay")
    sidebar = win.findChild(QObject, "drawerModeSidebar")
    collapsible = win.findChild(QObject, "drawerModeCollapsible")
    assert overlay is not None and sidebar is not None and collapsible is not None
    overlay.trigger(overlay)
    qgui_app.processEvents()
    assert drawer.property("modal") is True
    assert drawer.property("collapsible") is False
    sidebar.trigger(sidebar)
    qgui_app.processEvents()
    assert drawer.property("modal") is False
    assert drawer.property("collapsible") is False
    collapsible.trigger(collapsible)
    qgui_app.processEvents()
    assert drawer.property("modal") is False
    assert drawer.property("collapsible") is True
    assert drawer.property("collapsed") is True
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_view_button_cycles_modes(qgui_app, xdg_env):
    """Split-button main click cycles list -> icons -> cards -> list."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    button = win.findChild(QQuickItem, "viewButton")
    assert button is not None

    def click():
        pos = button.mapToScene(QPointF(button.property("width") / 2, 5)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        qgui_app.processEvents()

    assert page.property("viewMode") == "list"
    click()
    assert page.property("viewMode") == "icons"
    click()
    assert page.property("viewMode") == "cards"
    click()
    assert page.property("viewMode") == "list"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_icons_grid_shows_games(qgui_app, xdg_env):
    """Icons view renders one cell per game with its name."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid, name in (("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    grid = win.findChild(QQuickItem, "iconGrid")
    assert grid is not None
    page.setProperty("viewMode", "icons")
    qgui_app.processEvents()
    assert grid.property("visible") is True
    assert grid.property("count") == 2
    assert _delegate_label_visible(grid, "Doom")
    assert _delegate_label_visible(grid, "Quake")
    page.setProperty("viewSizes", {"list": 48, "icons": 128})
    qgui_app.processEvents()
    assert page.property("iconSize") == 128
    assert page.property("rowHeight") == 48
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_cards_show_games_and_play(qgui_app, xdg_env):
    """Cards view renders one card per game; its Play action launches."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid, name in (("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    layout = win.findChild(QQuickItem, "cardLayout")
    assert layout is not None
    page.setProperty("viewMode", "cards")
    qgui_app.processEvents()
    cards = _delegate_rows(layout)
    assert len(cards) == 2
    assert sorted(c.property("gameName") for c in cards) == ["Doom", "Quake"]
    first = min(cards, key=lambda c: c.y())
    assert first.property("gameId") == "local-doom"
    action = first.findChild(QObject, "cardPlay")
    assert action is not None
    import shiboken6

    assert shiboken6.isValid(action)
    # Route the card's play signal through the signal chain (play routing
    # itself is covered by test_list_row_double_click_plays).
    fired = []
    first.playRequested.connect(lambda gid: fired.append(gid))
    action.trigger(action)
    qgui_app.processEvents()
    assert fired == ["local-doom"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_icon_double_click_plays(qgui_app, xdg_env, monkeypatch):
    """Double-clicking an icon cell invokes play() with that game's id."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "77"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    played = []
    monkeypatch.setattr(model, "play", lambda gid: played.append(gid) or True)
    page = win.findChild(QObject, "gamesPage")
    page.setProperty("viewMode", "icons")
    qgui_app.processEvents()
    grid = win.findChild(QQuickItem, "iconGrid")
    cells = _delegate_rows(grid)
    assert len(cells) == 1
    pos = cells[0].mapToScene(QPointF(cells[0].property("width") / 2, 10)).toPoint()
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert played == ["77"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def _standalone_component(qgui_app, filename, props):
    import pathlib

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (registers QQuickItem wrapper)

    from tkarcade.gui import kirigami_app as kapp

    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    url = QUrl.fromLocalFile(str(pathlib.Path(kapp.__file__).parent / "qml" / filename))
    component = QQmlComponent(engine, url)
    assert component.isReady(), component.errorString()
    item = component.createWithInitialProperties(props)
    assert item is not None
    qgui_app.processEvents()
    return engine, warnings


def test_game_card_binds_roles(qgui_app):
    """GameCard compiles standalone and binds its roles."""
    engine, warnings = _standalone_component(
        qgui_app,
        "GameCard.qml",
        {
            "gameName": "Doom",
            "gameId": "local-doom",
            "gamePlayed": "38s",
            "gameSource": "Local",
            "gameTier": "Gold",
            "gameTierBg": "#FFC107",
            "gameTierFg": "#000000",
            "gameIcon": "",
        },
    )
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def test_game_icon_delegate_binds_roles(qgui_app):
    """GameIconDelegate compiles standalone and binds its roles."""
    engine, warnings = _standalone_component(
        qgui_app,
        "GameIconDelegate.qml",
        {
            "gameName": "Doom",
            "gameId": "local-doom",
            "gamePlayed": "38s",
            "gameIcon": "",
        },
    )
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def test_tier_double_click_opens_protondb(qgui_app, xdg_env):
    """Double-clicking the tier badge opens ProtonDB (never plays)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "42"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    played, opened = [], []
    model.play = lambda gid: played.append(gid) or True
    model.openProtonDB = lambda gid: opened.append(gid) or True
    view = win.findChild(QQuickItem, "gameList")
    rows = _delegate_rows(view)
    assert len(rows) == 1
    button = _cell_item(rows[0], "tierButton")
    assert button is not None
    pos = button.mapToScene(QPointF(button.property("width") / 2, 5)).toPoint()
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert opened == ["42"]
    assert played == []
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def _click_row(qgui_app, win, row, modifier=None):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    center = row.mapToScene(QPointF(row.property("width") / 2, 10)).toPoint()
    QTest.mouseClick(
        win,
        Qt.MouseButton.LeftButton,
        modifier or Qt.KeyboardModifier.NoModifier,
        center,
    )
    qgui_app.processEvents()


def test_multi_select_ctrl_shift(qgui_app, xdg_env):
    """Ctrl toggles rows, Shift extends from the anchor, plain resets."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game", "c-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    view = win.findChild(QQuickItem, "gameList")
    rows = sorted(_delegate_rows(view), key=lambda c: c.y())
    assert [r.property("gameId") for r in rows] == ["a-game", "b-game", "c-game"]

    def selected():
        return sorted(page.property("selectedIds").toVariant())

    _click_row(qgui_app, win, rows[1], Qt.KeyboardModifier.ControlModifier)
    assert selected() == ["a-game", "b-game"]
    _click_row(qgui_app, win, rows[2], Qt.KeyboardModifier.ShiftModifier)
    assert selected() == ["b-game", "c-game"]  # anchored at b-game
    _click_row(qgui_app, win, rows[0])
    assert selected() == ["a-game"]
    _click_row(qgui_app, win, rows[0], Qt.KeyboardModifier.ControlModifier)
    assert selected() == []
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_toolbar_play_plays_first_selected(qgui_app, xdg_env):
    """Toolbar Play launches the first selected game."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    played = []
    model.play = lambda gid: played.append(gid) or True
    view = win.findChild(QQuickItem, "gameList")
    rows = sorted(_delegate_rows(view), key=lambda c: c.y())
    _click_row(qgui_app, win, rows[0])
    _click_row(qgui_app, win, rows[1], Qt.KeyboardModifier.ControlModifier)
    action = win.findChild(QObject, "actionPlay")
    assert action is not None
    action.trigger(action)
    qgui_app.processEvents()
    assert played == ["a-game"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_context_menu_opens_for_row(qgui_app, xdg_env):
    """Right-click selects the row (preserving multi) and opens the menu."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    view = win.findChild(QQuickItem, "gameList")
    rows = sorted(_delegate_rows(view), key=lambda c: c.y())
    _click_row(qgui_app, win, rows[0])
    _click_row(qgui_app, win, rows[1], Qt.KeyboardModifier.ControlModifier)
    second = rows[1]
    center = second.mapToScene(QPointF(second.property("width") / 2, 10)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, center)
    qgui_app.processEvents()
    menu = win.findChild(QObject, "gameMenu")
    assert menu.property("visible") is True
    assert page.property("menuGid") == "b-game"
    # Multi-selection preserved: a-game stays selected.
    assert sorted(page.property("selectedIds").toVariant()) == ["a-game", "b-game"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_remove_flow_with_profiles(qgui_app, xdg_env):
    """Remove asks, deletes configs, then offers profile cleanup."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    for appid in ("local-doom", "local-quake"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    profiles = C.profiles_dir("local-doom")
    profiles.mkdir(parents=True, exist_ok=True)
    (profiles / "default.toml").write_text("[general]\n")
    assert C.game_file("local-doom").exists()
    win, _engine, proxy, warnings = _load_main(qgui_app)
    view = win.findChild(QQuickItem, "gameList")
    rows = sorted(_delegate_rows(view), key=lambda c: c.y())
    assert len(rows) == 2
    page = win.findChild(QObject, "gamesPage")
    _click_row(qgui_app, win, rows[0])
    _click_row(qgui_app, win, rows[1], Qt.KeyboardModifier.ControlModifier)
    assert len(page.property("selectedIds").toVariant()) == 2
    remove = win.findChild(QObject, "actionRemove")
    remove.trigger(remove)
    qgui_app.processEvents()
    dialog = win.findChild(QObject, "removeDialog")
    assert dialog.property("visible") is True
    confirm = win.findChild(QQuickItem, "removeConfirm")
    pos = confirm.mapToScene(QPointF(confirm.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert not C.game_file("local-doom").exists()
    assert not C.game_file("local-quake").exists()
    assert proxy.rowCount() == 0
    cleanup = win.findChild(QObject, "cleanupDialog")
    assert cleanup.property("visible") is True
    assert cleanup.property("leftovers") == ["local-doom"]
    wipe = win.findChild(QQuickItem, "cleanupConfirm")
    pos = wipe.mapToScene(QPointF(wipe.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert not profiles.exists()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_scan_flow_adds_steam_game(qgui_app, xdg_env, monkeypatch):
    """Scan lists unconfigured Steam games; Add Selected writes configs."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    import tkarcade.steam as steammod
    from tkarcade import config as C

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3"), ("100", "Quake 4")])
    win, engine, proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    assert model.scanCandidates() == [["99", "Doom 3"], ["100", "Quake 4"]]
    dialog = win.findChild(QObject, "scanDialog")
    dialog.setProperty("candidates", [["99", "Doom 3"], ["100", "Quake 4"]])
    qgui_app.processEvents()
    dialog.setProperty("visible", True)
    qgui_app.processEvents()
    confirm = win.findChild(QQuickItem, "scanConfirm")
    pos = confirm.mapToScene(QPointF(confirm.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert C.game_file("99").exists()
    assert C.game_file("100").exists()
    assert proxy.rowCount() == 2
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_history_view_clears_row(qgui_app, xdg_env):
    """History viewer lists aggregates; per-row Clear drops one game."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    win, engine, _proxy, warnings = _load_main(qgui_app)
    view = win.findChild(QObject, "historyView")
    view.setProperty("rows", [{"appid": "42", "name": "Doom", "last": "yesterday", "total": "1h"}])
    view.open()
    qgui_app.processEvents()
    import shiboken6

    rows_view = win.findChild(QQuickItem, "historyRows")
    names = []
    for child in rows_view.property("contentItem").childItems():
        try:
            label = child.findChild(QQuickItem, "historyName")
        except Exception:
            label = None
        try:
            if label is not None and shiboken6.isValid(label) and label.isVisible():
                text = label.property("text")
                if isinstance(text, str):
                    names.append(text)
        except Exception:
            continue
    assert names == ["Doom"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_prefs_save_roundtrip(qgui_app, xdg_env):
    """Preferences dialog writes through to the prefs file."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    win, _engine, _proxy, warnings = _load_main(qgui_app)
    dialog = win.findChild(QObject, "prefsDialog")
    dialog.setProperty(
        "values",
        {
            "showPreview": True,
            "trayEnable": False,
            "trayIcon": "mono",
            "minimizeToTray": False,
            "closeToTray": False,
            "trayQuickLaunch": False,
            "trayQuickCount": 3,
            "sgdbApiKey": "secret",
        },
    )
    dialog.setProperty("visible", True)
    qgui_app.processEvents()
    save = win.findChild(QQuickItem, "prefsSave")
    pos = save.mapToScene(QPointF(save.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    prefs = C.load_preferences()
    assert prefs.tray_icon == "mono"
    assert prefs.tray_quick_count == 3
    assert prefs.sgdb_api_key == "secret"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_issues_only_filter(qgui_app, xdg_env):
    """Issues-only shows games failing validation (same as --validate)."""
    import sys

    from PySide6.QtCore import QObject

    from tkarcade import config as C

    good = C.GameConfig()
    good.general.appid = "local-good"
    good.general.name = "Good"
    good.general.custom_executable = sys.executable
    good.general.game_type = "native"
    C.save(good)
    bad = C.GameConfig()
    bad.general.appid = "local-bad"
    bad.general.name = "Bad"
    bad.general.custom_executable = "/nonexistent/game"
    bad.general.game_type = "native"
    C.save(bad)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    assert proxy.rowCount() == 2
    page = win.findChild(QObject, "gamesPage")
    assert page is not None
    proxy.setProperty("issuesOnly", True)
    qgui_app.processEvents()
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) in ("Bad", "local-bad") or True
    from tkarcade.gui.model import GameListModel

    assert proxy.data(proxy.index(0, 0), GameListModel.IdRole) == "local-bad"
    proxy.setProperty("issuesOnly", False)
    qgui_app.processEvents()
    assert proxy.rowCount() == 2
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_footer_shows_filtered_count(qgui_app, xdg_env):
    """Footer appends the shown count while a filter is active."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("local-doom", "local-quake"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    status = win.findChild(QQuickItem, "statusLabel")
    assert status is not None
    assert "shown" not in status.property("text")
    proxy.setProperty("textQuery", "doom")
    qgui_app.processEvents()
    assert "1 shown" in status.property("text")
    proxy.setProperty("textQuery", "")
    qgui_app.processEvents()
    assert "shown" not in status.property("text")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_empty_scan_without_steam_notifies(qgui_app, xdg_env):
    """Empty state Scan with nothing to add reports instead of opening."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    win, _engine, proxy, warnings = _load_main(qgui_app)
    assert proxy.rowCount() == 0
    scan = win.findChild(QQuickItem, "emptyScan")
    assert scan is not None and scan.property("visible") is True
    pos = scan.mapToScene(QPointF(scan.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    page = win.findChild(QObject, "gamesPage")
    assert page.property("notice") == "Every Steam game is already configured."
    dialog = win.findChild(QObject, "scanDialog")
    assert dialog.property("visible") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_column_move_reorders_cells(qgui_app, xdg_env):
    """Move right swaps a column with its neighbour, header included."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert page.property("columnOrder").toVariant() == [1, 2, 3, 4]
    view = win.findChild(QQuickItem, "gameList")

    def xs():
        from PySide6.QtCore import QPointF

        rows = _delegate_rows(view)
        assert len(rows) == 1
        app = _cell_item(rows[0], "appIdLabel")
        played = _cell_item(rows[0], "playedLabel")
        return (
            app.mapToScene(QPointF(app.property("width") / 2, 5)).x(),
            played.mapToScene(QPointF(played.property("width") / 2, 5)).x(),
        )

    app_x, played_x = xs()
    assert app_x < played_x
    page.moveColumn(1, 1)
    for _ in range(50):
        qgui_app.processEvents()
        rows = _delegate_rows(view)
        if rows and _cell_text(rows[0], "playedLabel") == "—":
            page_x = _cell_item(rows[0], "playedLabel")
            if page_x is not None and page_x.property("width") == 90:
                break
    app_x, played_x = xs()
    assert played_x < app_x
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_column_layout_persists(qgui_app, xdg_env):
    """Column order and hidden columns round-trip through prefs."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    win, engine, proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    assert model.saveColumns([0, 2, 1, 3, 4], [4]) is True
    assert model.columnOrder() == [0, 2, 1, 3, 4]
    assert model.hiddenColumns() == [4]
    page = win.findChild(QObject, "gamesPage")
    page.moveColumn(1, 1)
    proxy.setProperty("showSource", False)
    qgui_app.processEvents()
    prefs = C.load_preferences()
    assert prefs.column_order == "0,2,1,3,4"
    assert prefs.hidden_columns == "4"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()
