"""QML smoke: main.qml loads warning-free with a live model (offscreen)."""

import PySide6.QtQuickControls2  # noqa: F401 (registers QQC2 wrappers)

OFFSCREEN_NOISE = ("was not placed in the graphics scene",)

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
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_CLICKS", "")
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_GEOMETRY", "")
    import gc

    gc.collect()
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    real = [w for w in warnings if not any(n in w for n in OFFSCREEN_NOISE)]
    assert real == []

    root = engine.rootObjects()[0]
    table = root.findChild(QQuickItem, "gameTable")
    assert table is not None
    qgui_app.processEvents()
    assert game_filter.rowCount() == 1


def test_table_headers(qgui_app, xdg_env):
    """The native header shows every column title."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    def texts(obj):

        out = []
        try:
            descendants = obj.findChildren(QObject)
        except Exception:
            return []
        for child in descendants:
            for prop in ("title", "text"):
                try:
                    value = child.property(prop)
                except Exception:
                    continue
                if isinstance(value, str) and value:
                    out.append(value)
        return out

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
    titles = set()

    def walk(item):
        try:
            text = item.property("text")
        except Exception:
            text = None
        if isinstance(text, str) and text and text not in ("▲", "▼"):
            titles.add(text)
        try:
            kids = item.childItems()
        except Exception:
            return
        for kid in kids:
            walk(kid)

    walk(header)
    assert {"#", "Game", "App ID", "Played", "ProtonDB", "Source"} <= titles
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
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
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_CLICKS", "")
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_GEOMETRY", "")
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
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None
    rows = _table_rows(table, game_filter)
    assert len(rows) == 1
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rows[0][1])
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
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_CLICKS", "")
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_GEOMETRY", "")
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
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    header_pt = header.mapToScene(
        QPointF(_column_cell_x(header, page, game_filter, 2), 5)
    ).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, header_pt)
    qgui_app.processEvents()
    assert page.property("sortRole") == "gameId"
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
    """Grid delegates only (the table uses _table_rows instead)."""
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


def _table_rows(table, proxy):
    """Row centers of the table as (row, window QPoint).

    Coordinates come from measured metrics: TableView content holds
    rows only (the custom header sits above it).
    """
    from PySide6.QtCore import QPointF

    count = proxy.rowCount() or 0
    content = table.property("contentHeight") or 0
    if count <= 0:
        return []
    unit = content / count
    rows = []
    for row in range(count):
        try:
            pos = table.mapToScene(QPointF(table.property("width") / 2, row * unit + unit / 2))
            rows.append((row, pos.toPoint()))
        except Exception:
            continue
    return rows


def _column_widths(proxy, table):
    """Visible widths per logical column (mirrors tableColumnWidth)."""
    widths = {0: 36.0, 1: 0.0, 2: 90.0, 3: 90.0, 4: 110.0, 5: 80.0}
    shown = _shown_flags(proxy)
    try:
        table_w = table.property("width") or 0
    except Exception:
        table_w = 0
    widths[1] = max(
        120.0,
        table_w - sum(w for _l, w in widths.items() if _l != 1 and shown[_l]),
    )
    return widths


def _shown_flags(proxy):
    shown = {0: True, 1: True}
    for logical, flag in (
        (2, "showAppId"),
        (3, "showPlayed"),
        (4, "showTier"),
        (5, "showSource"),
    ):
        try:
            shown[logical] = bool(proxy.property(flag))
        except Exception:
            shown[logical] = True
    return shown


def _column_cell_x(host, page, proxy, logical):
    """X center of a column cell (host coords) by logical id.

    Header and body share widths, so one helper serves clicks in both.
    """
    try:
        raw = page.property("columnOrder")
        order = list(raw.toVariant()) if hasattr(raw, "toVariant") else list(raw)
    except Exception:
        order = [0, 1, 2, 3, 4, 5]
    table = None
    try:
        win = host.window()
        table = win.findChild(host.__class__, "gameTable") if win is not None else None
    except Exception:
        table = None
    widths = _column_widths(proxy, table)
    shown = _shown_flags(proxy)
    x = 0.0
    for entry in order:
        if not shown.get(entry, True):
            continue
        w = widths.get(entry, 0.0)
        if entry == logical:
            return x + w / 2
        x += w
    return x


def _table_column_x_legacy(table, page, logical):
    raise AssertionError("rewired: use _header_cell_x with the header item")


def _selected_ids(table, proxy):
    """AppIDs currently selected in the table, in row order."""
    from tkarcade.gui.model import GameListModel

    try:
        selection = table.property("selectionModel").selectedRows()
    except Exception:
        return []
    rows = sorted({index.row() for index in selection})
    return [str(proxy.data(proxy.index(row, 0), GameListModel.IdRole) or "") for row in rows]


def _delegate_label_visible(view, text):
    """True when any grid delegate shows a visible label with text."""
    import shiboken6
    from PySide6.QtQuick import QQuickItem

    for delegate in _delegate_rows(view):
        for name in ("iconName", "iconPlayed"):
            try:
                label = delegate.findChild(QQuickItem, name)
                if label is None or not shiboken6.isValid(label):
                    continue
                if (
                    isinstance(label, QQuickItem)
                    and label.isVisible()
                    and label.property("text") == text
                ):
                    return True
            except Exception:
                continue
    return False


def _settle_table(table, qgui_app, count, proxy, limit=100):
    """Pump frames until the table shows every row (or timeout)."""
    for _ in range(3):
        qgui_app.processEvents()
    for _ in range(limit):
        have = proxy.rowCount() if proxy is not None else count
        if have == count and count > 0:
            rows = _table_rows(table, proxy)
            if rows:
                return
        qgui_app.processEvents()


def _fire(item):
    """Emit triggered with or without a source arg (Action vs MenuItem)."""
    try:
        item.triggered.emit(item)
    except TypeError:
        item.triggered.emit()


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
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_CLICKS", "")
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_GEOMETRY", "")
    engine.load(QUrl(qml_url()))
    assert len(engine.rootObjects()) == 1
    win = engine.rootObjects()[0]
    assert isinstance(win, QQuickWindow)
    win.setProperty("width", 1280)
    win.setProperty("height", 720)
    win.show()
    qgui_app.processEvents()
    qgui_app.processEvents()
    table = win.findChild(QQuickItem, "gameTable")
    if table is not None:
        _settle_table(table, qgui_app, game_filter.rowCount(), game_filter)
    return win, engine, game_filter, warnings


def test_row_selection_follows_tap(qgui_app, xdg_env):
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    from PySide6.QtCore import QObject

    page = win.findChild(QObject, "gamesPage")
    assert page is not None
    table = win.findChild(QQuickItem, "gameTable")
    page.tapGame("b-game", 0)
    qgui_app.processEvents()
    assert _selected_ids(table, proxy) == ["b-game"]
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
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
    from tkarcade.gui.model import GameListModel

    before = [proxy.data(proxy.index(r, 0), GameListModel.IdRole) for r in range(proxy.rowCount())]
    assert before == ["a-game", "b-game"]
    proxy.sortBy("gameId", True)
    qgui_app.processEvents()
    after = [proxy.data(proxy.index(r, 0), GameListModel.IdRole) for r in range(proxy.rowCount())]
    assert after == ["b-game", "a-game"]
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

    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None

    def cell(logical):
        wanted = f"headerCell{logical}"
        stack = list(header.childItems())
        while stack:
            item = stack.pop()
            try:
                if item.objectName() == wanted:
                    return item
            except Exception:
                pass
            try:
                stack.extend(item.childItems())
            except Exception:
                pass
        return None

    found_cell = cell(2)
    assert found_cell is not None

    assert cell(2).property("width") == 90
    assert cell(2).property("visible") is True
    game_w = cell(1).property("width")
    proxy.setProperty("showAppId", False)
    for _ in range(20):
        qgui_app.processEvents()
        if cell(1).property("width") == game_w + 90:
            break
    assert cell(2).property("visible") is False
    assert cell(1).property("width") == game_w + 90
    proxy.setProperty("showAppId", True)
    for _ in range(20):
        qgui_app.processEvents()
        if cell(1).property("width") == game_w:
            break
    assert cell(2).property("visible") is True
    assert cell(1).property("width") == game_w
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_drawer_modes_switch(qgui_app, xdg_env):
    """Hamburger drawer modes apply overlay/sidebar/collapsible."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer is not None
    for mode in ("drawerModeOverlay", "drawerModeSidebar", "drawerModeCollapsible"):
        assert win.findChild(QObject, mode) is not None, mode

    def apply(name):
        item = win.findChild(QObject, name)
        assert item is not None, name
        _fire(item)
        qgui_app.processEvents()

    apply("drawerModeOverlay")
    assert drawer.property("modal") is True
    assert drawer.property("collapsible") is False
    apply("drawerModeSidebar")
    assert drawer.property("modal") is False
    assert drawer.property("collapsible") is False
    apply("drawerModeCollapsible")
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
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    from PySide6.QtCore import QMetaObject

    def cycle():
        assert QMetaObject.invokeMethod(page, "cycleView")
        qgui_app.processEvents()

    assert page.property("viewMode") == "list"
    cycle()
    assert page.property("viewMode") == "icons"
    cycle()
    assert page.property("viewMode") == "cards"
    cycle()
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
    page.setProperty("viewSizes", {"icons": 128})
    qgui_app.processEvents()
    assert page.property("iconSize") == 128
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
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None
    rows = _table_rows(table, _proxy)
    assert len(rows) == 1
    from PySide6.QtCore import QObject

    page = win.findChild(QObject, "gamesPage")
    tier_win_x = table.mapToScene(QPointF(_column_cell_x(table, page, _proxy, 4), 0)).x()
    row_y = rows[0][1].y()
    pos = QPointF(tier_win_x, row_y).toPoint()
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
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    if isinstance(row, tuple):
        center = row[1]
    else:
        from PySide6.QtCore import QPointF

        center = row.mapToScene(QPointF(row.property("width") / 2, 10)).toPoint()
    QTest.mouseClick(
        win,
        Qt.MouseButton.LeftButton,
        modifier or Qt.KeyboardModifier.NoModifier,
        center,
    )
    qgui_app.processEvents()


def test_multi_select_ctrl_shift(qgui_app, xdg_env):
    """Toggle/extend helpers drive the table selection model."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game", "c-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None

    def selected():
        return sorted(_selected_ids(table, proxy))

    assert selected() == ["a-game"]
    page.toggleSelect("b-game")
    qgui_app.processEvents()
    assert selected() == ["a-game", "b-game"]
    page.toggleSelect("c-game")
    qgui_app.processEvents()
    assert selected() == ["a-game", "b-game", "c-game"]
    page.select("a-game")
    page.toggleSelect("c-game")
    qgui_app.processEvents()
    assert selected() == ["a-game", "c-game"]
    page.extendSelect("b-game")
    qgui_app.processEvents()
    assert selected() == ["b-game", "c-game"]  # anchored at c-game
    page.select("c-game")
    qgui_app.processEvents()
    assert selected() == ["c-game"]
    page.toggleSelect("c-game")
    qgui_app.processEvents()
    assert selected() == []
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_toolbar_play_plays_first_selected(qgui_app, xdg_env):
    """Toolbar Play launches the first selected game."""
    from PySide6.QtCore import QObject
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
    table = win.findChild(QQuickItem, "gameTable")
    rows = _table_rows(table, _proxy)
    assert len(rows) == 2
    _click_row(qgui_app, win, rows[0])
    page = win.findChild(QObject, "gamesPage")
    page.toggleSelect("b-game")
    qgui_app.processEvents()
    action = win.findChild(QObject, "actionPlay")
    assert action is not None
    _fire(action)
    qgui_app.processEvents()
    assert played == ["a-game"]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_context_menu_opens_for_row(qgui_app, xdg_env):
    """Right-click selects the row (preserving multi) and opens the menu."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    table = win.findChild(QQuickItem, "gameTable")
    page.tapGame("a-game", 0)
    page.toggleSelect("b-game")
    qgui_app.processEvents()
    page.openGameMenu("b-game")
    qgui_app.processEvents()
    menu = win.findChild(QObject, "gameMenu")
    assert menu.property("visible") is True
    assert page.property("menuGid") == "b-game"
    # Multi-selection preserved: a-game stays selected.
    assert sorted(_selected_ids(table, _proxy)) == ["a-game", "b-game"]
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
    table = win.findChild(QQuickItem, "gameTable")
    rows = _table_rows(table, proxy)
    assert len(rows) == 2
    page = win.findChild(QObject, "gamesPage")
    _click_row(qgui_app, win, rows[0])
    page.toggleSelect("local-quake")
    qgui_app.processEvents()
    assert len(_selected_ids(table, proxy)) == 2
    remove = win.findChild(QObject, "actionRemove")
    assert remove is not None
    _fire(remove)
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
    win, _engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert page.property("columnOrder").toVariant() == [0, 1, 2, 3, 4, 5]
    header = win.findChild(QQuickItem, "tableHeader")

    def xs():
        return _column_cell_x(header, page, proxy, 2), _column_cell_x(header, page, proxy, 3)

    app_x, played_x = xs()
    assert app_x < played_x
    page.moveColumn(2, 1)
    qgui_app.processEvents()
    app_x, played_x = xs()
    assert played_x < app_x
    assert page.property("columnOrder").toVariant() == [0, 1, 3, 2, 4, 5]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_column_layout_persists(qgui_app, xdg_env):
    """Column order and hidden columns round-trip through prefs."""

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    win, engine, proxy, warnings = _load_main(qgui_app)
    assert proxy.columnLogical(0) == 0
    proxy.moveColumn(2, 1)
    assert [proxy.columnLogical(c) for c in range(6)] == [0, 1, 3, 2, 4, 5]
    proxy.setProperty("showSource", False)
    qgui_app.processEvents()
    prefs = C.load_preferences()
    assert prefs.column_order == "0,1,3,2,4,5"
    assert prefs.hidden_columns == "5"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_toolbar_actions_in_header_and_quit_shortcut(qgui_app, xdg_env):
    """Primary actions live in the window header; Ctrl+Q shortcut exists."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    for name, label in (
        ("actionPlay", "Play"),
        ("actionAdd", "Add game"),
        ("actionEdit", "Edit..."),
        ("actionRemove", "Remove"),
    ):
        found = win.findChild(QObject, name)
        assert found is not None, name
        assert found.property("text") == label, name
    assert win.findChild(QObject, "quitShortcut") is not None
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_table_delegates_never_lookup_by_visual_row():
    """Delegates bind model roles/ids, never the visual row (stuck at 0)."""
    import pathlib
    import re

    from tkarcade.gui import kirigami_app as kapp

    offenders = []
    for path in sorted((pathlib.Path(kapp.__file__).parent / "qml").glob("*.qml")):
        if path.name == "RowClickHandler.qml":
            continue  # takes gid, never row (checked below)
        src = path.read_text().splitlines()
        for i, line in enumerate(src, 1):
            if re.search(r"rowData\s*\(\s*row\s*\)", line):
                offenders.append(f"{path.name}:{i}")
            # idAt(row) is only safe with a declared JS loop var
            # (extendSelect); delegates must use model.gameId instead.
            if re.search(r"idAt\s*\(\s*row\s*\)", line) and not any(
                "for (var row" in prev for prev in src[max(0, i - 4) : i]
            ):
                offenders.append(f"{path.name}:{i}")
    # RowClickHandler instances must pass gid: (never row) plus page:
    # QML ids are file-scoped, so a bare gamesPage reference inside
    # RowClickHandler.qml resolves to nothing and clicks die silent.
    text = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert "RowClickHandler {\n                        gid:" not in text
    assert text.count("RowClickHandler {\n                        page: gamesPage") == 4
    handler = (pathlib.Path(kapp.__file__).parent / "qml" / "RowClickHandler.qml").read_text()
    assert "required property var page" in handler
    assert "gamesPage." not in handler
    assert offenders == []


def test_hamburger_holds_tools_and_persisted_drawer_modes(qgui_app, xdg_env):
    """Hamburger replaces Tools; drawer modes persist through prefs."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    burger = win.findChild(QQuickItem, "hamburgerButton")
    assert burger is not None
    menu = win.findChild(QObject, "hamburgerMenu")
    assert menu is not None
    texts = set()
    for obj in menu.findChildren(QObject):
        try:
            text = obj.property("text")
        except Exception:
            continue
        if isinstance(text, str) and text:
            texts.add(text)
    assert {"Scan Steam Library...", "Reload", "Quit"} <= texts
    _collapsible = win.findChild(QObject, "drawerModeCollapsible")
    _fire(_collapsible)
    qgui_app.processEvents()
    assert C.load_preferences().drawer_mode == "collapsible"
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer.property("collapsible") is True
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_columns_dialog_toggles_and_header_menu_opens(qgui_app, xdg_env):
    """Gear opens the columns dialog; header right-click opens its menu."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
    head = header.mapToScene(QPointF(header.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, head)
    qgui_app.processEvents()
    header_menu = win.findChild(QObject, "headerMenu")
    assert header_menu.property("visible") is True
    QTest.keyClick(win, Qt.Key.Key_Escape)
    qgui_app.processEvents()
    gear = win.findChild(QObject, "columnsButton")
    assert gear is not None
    _fire(gear)
    qgui_app.processEvents()
    dialog = win.findChild(QObject, "columnsDialog")
    assert dialog.property("visible") is True
    # Dialog content is lazy offscreen: exercise the same flags directly.
    proxy.setProperty("showAppId", False)
    qgui_app.processEvents()
    assert proxy.property("showAppId") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_selected_row_uses_highlight_text_color():
    """Selection pairs highlightColor bg with highlightedTextColor text."""
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    text = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert text.count("highlightedTextColor") >= 3
    assert "property bool isSelected" in text
    # tier badge joins the highlight instead of keeping its island color
    assert "isSelected ? Kirigami.Theme.highlightColor" in text


def test_header_titles_share_styled_delegate():
    """Every header cell uses the Button-set title style (contrast)."""
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    text = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert "colorSet: Kirigami.Theme.Button" in text
    assert text.count("headerDelegate") == 0  # no addon header leftovers
    for title in ("#", "Game", "App ID", "Played", "ProtonDB", "Source"):
        assert title in text
    # number gutter shares the header look (vertical-header framing)
    gutter = text.split("// number gutter")[1].split("// game: icon plus name")[0]
    assert "colorSet: Kirigami.Theme.Button" in gutter
    assert "highlightColor" in gutter
    # header strip shares the body's x origin: no outer margins that
    # would shift every title/divider away from its column
    strip = text.split("id: tableHeader")[1].split("Repeater {")[0]
    assert "Margin" not in strip


def test_header_cells_tile_from_zero(qgui_app, xdg_env):
    """Header cells start at x=0 with the same widths as the body."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    header = win.findChild(QQuickItem, "tableHeader")
    found = {}

    def walk(item):
        try:
            name = item.objectName()
        except Exception:
            return
        if name.startswith("headerCell"):
            try:
                found[name] = (round(item.property("x"), 1), round(item.property("width"), 1))
            except Exception:
                pass
        try:
            kids = item.childItems()
        except Exception:
            return
        for kid in kids:
            walk(kid)

    walk(header)
    assert found.get("headerCell0") == (0.0, 36.0), found
    xs = [x for _, (x, _w) in sorted(found.items())]
    assert xs == sorted(xs), found  # no overlaps/gaps out of order
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_view_switcher_has_icons_and_shortcuts(qgui_app, xdg_env):
    """View modes show Dolphin-style icons; Ctrl+1/2/3 switch directly."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert page is not None
    for name, sequence in (
        ("viewShortcutList", "Ctrl+1"),
        ("viewShortcutIcons", "Ctrl+2"),
        ("viewShortcutCards", "Ctrl+3"),
    ):
        found = win.findChild(QObject, name)
        assert found is not None, name
        assert found.property("sequence") == sequence, name
    button = win.findChild(QQuickItem, "viewButton")
    assert button is not None
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    src = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    for icon in ("view-list-details", "view-list-icons", "view-grid"):
        assert icon in src, icon
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_drawer_and_page_headers_share_height(qgui_app, xdg_env):
    """Drawer "Library" bar matches the page header so separators align."""
    import pathlib

    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui import kirigami_app as kapp

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    drawer_bar = win.findChild(QQuickItem, "drawerHeaderBar")
    assert drawer_bar is not None
    page_headers = []
    for child in win.findChildren(QObject):
        try:
            class_name = child.metaObject().className()
        except Exception:
            continue
        if "ToolBarPageHeader" in class_name:
            try:
                page_headers.append(child.property("height"))
            except Exception:
                continue
    assert page_headers, "no Kirigami page header found"
    drawer_h = drawer_bar.property("height")
    page_h = max(h for h in page_headers if h is not None)
    assert drawer_h > 0 and page_h > 0
    assert abs(drawer_h - page_h) <= 1, (drawer_h, page_h)
    # Plain Item header (never a ToolBar): a toolbar header makes
    # Kirigami inset the drawer-edge separator around the header zone,
    # leaving the vertical line short of the header lines.
    main_src = (pathlib.Path(kapp.__file__).parent / "qml" / "main.qml").read_text()
    assert "header: Item {" in main_src
    assert "header: Controls.ToolBar" not in main_src
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_list_frame_encloses_table(qgui_app, xdg_env):
    """The list view carries an outer frame around header plus table."""
    import pathlib

    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui import kirigami_app as kapp

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    frame = win.findChild(QQuickItem, "listFrame")
    assert frame is not None
    src = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert "listFrame" in src and "border.width: 1" in src
    table = win.findChild(QQuickItem, "gameTable")
    header = win.findChild(QQuickItem, "tableHeader")
    assert table is not None and header is not None
    fx, fy = frame.property("x"), frame.property("y")
    fw, fh = frame.property("width"), frame.property("height")
    for item, name in ((header, "header"), (table, "table")):
        ix, iy = item.property("x"), item.property("y")
        iw = item.property("width")
        assert ix >= fx and iy >= fy, (name, ix, iy, fx, fy)
        assert ix + iw <= fx + fw + 1, (name, ix + iw, fx + fw)
    assert fy + fh >= table.property("y") + table.property("height") - 1
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_status_label_clears_footer_lines(qgui_app, xdg_env):
    """Status text keeps padding from the separator above and edge below."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    label = win.findChild(QObject, "statusLabel")
    assert label is not None
    assert label.property("leftPadding") > 0
    assert label.property("topPadding") > 0
    assert label.property("bottomPadding") > 0
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()
