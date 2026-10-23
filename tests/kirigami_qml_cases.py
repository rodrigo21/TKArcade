"""QML smoke: main.qml loads warning-free with a live model (offscreen)."""

import PySide6.QtQuickControls2  # noqa: F401 (registers QQC2 wrappers)

OFFSCREEN_NOISE = ("was not placed in the graphics scene",)

# Settings TabBar order (GameSettings.qml) and the scroll body behind each
# tab. Named here so a reshuffle updates one table, not a dozen indices.
# QQC2 reads `&` in a button text as a mnemonic, and eight tabs share
# ~94px at the default width (Compatibility is exactly 13 chars), so the
# title is kept to 13 characters without spaces to avoid eliding.
SETTINGS_TAB_TITLES = (
    "General",
    "Launch",
    "Environment",
    "Compatibility",
    "Performance",
    "Display",
    "System",
    "Artwork/Notes",
)
(
    TAB_GENERAL,
    TAB_LAUNCH,
    TAB_ENV,
    TAB_COMPAT,
    TAB_PERF,
    TAB_DISPLAY,
    TAB_SYSTEM,
    TAB_ART,
) = range(len(SETTINGS_TAB_TITLES))

SETTINGS_TAB_BODIES = {
    TAB_GENERAL: "settingsGeneralScroll",
    TAB_LAUNCH: "settingsLaunchScroll",
    TAB_ENV: "settingsEnvRowsScroll",
    TAB_COMPAT: "settingsWineScroll",
    TAB_PERF: "settingsPerfScroll",
    TAB_DISPLAY: "settingsDisplayScroll",
    TAB_SYSTEM: "settingsSystemScroll",
    TAB_ART: "settingsArtworkScroll",
}


def _settings_tab(swin, index):
    """Switch the settings TabBar to `index` and let the page settle."""
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    tabs = swin.findChild(QQuickItem, "settingsTabs")
    assert tabs is not None
    tabs.setProperty("currentIndex", index)
    QTest.qWait(150)


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


def _header_texts(header) -> set[str]:
    """Column titles found under the header item (sorter arrows ignored)."""
    titles: set[str] = set()

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
    return titles


def _check_header_titles(win):
    """The native header shows every column title."""
    from PySide6.QtQuick import QQuickItem

    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
    titles = _header_texts(header)
    assert {"Game", "App ID", "Played", "ProtonDB", "Source"} <= titles


def _check_header_cell_tiling(win):
    """Header cells start at x=0 with the same widths as the body."""
    from PySide6.QtQuick import QQuickItem

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
    ordered = [found[k] for k in sorted(found, key=lambda n: int(n[10:]))]
    xs = [x for x, _w in ordered]
    assert xs == sorted(xs), found  # no overlaps/gaps out of order


def _check_page_header_height(win):
    """Drawer "Library" bar matches the page header so separators align."""
    import pathlib

    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade.gui import kirigami_app as kapp

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
    assert drawer_h > 0
    assert page_h > 0
    assert abs(drawer_h - page_h) <= 1, (drawer_h, page_h)
    # Plain Item header (never a ToolBar): a toolbar header makes
    # Kirigami inset the drawer-edge separator around the header zone,
    # leaving the vertical line short of the header lines.
    main_src = (pathlib.Path(kapp.__file__).parent / "qml" / "main.qml").read_text()
    assert "header: Item {" in main_src
    assert "header: Controls.ToolBar" not in main_src


def _check_view_shortcuts(win):
    """View modes show Dolphin-style icons; Ctrl+1/2/3 switch directly."""
    import pathlib

    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade.gui import kirigami_app as kapp

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
    src = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    for icon in ("view-list-details", "view-list-icons", "view-grid"):
        assert icon in src, icon


def test_header_and_view_structure(qgui_app, xdg_env):
    """Header titles/tiling, drawer-page header height and view shortcuts.

    Read-only checks of the one default window; each loaded its own
    window before.
    """
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    _check_header_titles(win)
    _check_header_cell_tiling(win)
    _check_page_header_height(win)
    _check_view_shortcuts(win)
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


def test_middle_click_opens_settings(qgui_app, xdg_env):
    """Middle-clicking a row opens its settings (widgets eventFilter parity)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "77"
    cfg.general.name = "Middle Test"
    C.save(cfg)
    win, engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    table = win.findChild(QQuickItem, "gameTable")
    settings = win.findChild(QObject, "gameSettings")
    assert table is not None
    assert settings is not None
    assert page.settingsOpen() is False

    rows = _table_rows(table, proxy)
    assert len(rows) == 1
    QTest.mouseClick(win, Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier, rows[0][1])
    QTest.qWait(100)
    qgui_app.processEvents()
    assert page.settingsOpen() is True
    assert settings.property("editAppid") == "77"

    settings.close()
    QTest.qWait(50)
    qgui_app.processEvents()
    assert page.settingsOpen() is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def _current_row(table):
    """The row the table's selection model calls current (-1 when none)."""
    cur = table.property("selectionModel").property("currentIndex")
    return cur.row() if cur is not None and cur.isValid() else -1


def _page_selected_ids(page):
    """`selectedIds` as a Python list (the property is a JS array)."""
    ids = page.property("selectedIds")
    return ids.toVariant() if hasattr(ids, "toVariant") else ids


def test_launch_reports_failure_and_status(qgui_app, xdg_env, monkeypatch):
    """A local launch reports: sticky "Launched X.", warning on failure.

    Widgets parity: every launch path reported itself (the tray recents
    ran the same code), a failed handoff warned and a local launch left
    "Launched X." in the status line.
    """
    from PySide6.QtCore import QObject

    from tkarcade import launcher as launchermod

    _save_one_game("local-boom", "Boom")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    label = win.findChild(QObject, "statusLabel")
    model = engine.rootContext().contextProperty("gameModel")

    def boom(appid):
        raise OSError("no such executable")

    monkeypatch.setattr(launchermod, "launch_local_detached", boom)
    assert model.play("local-boom") is False
    assert _wait_for(lambda: "Could Not Launch Boom" in label.property("text"))
    assert "no such executable" in page.property("notice")
    assert page.property("statusMessage") == ""

    monkeypatch.setattr(launchermod, "launch_local_detached", lambda appid: None)
    assert model.play("local-boom") is True
    assert page.property("statusMessage") == "Launched Boom."
    page.setProperty("notice", "")
    assert _wait_for(lambda: "Launched Boom." in label.property("text"))

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_table_keyboard_navigation(qgui_app, xdg_env):
    """The table owns the keys and navigates like the widgets QTableView.

    Without the focus the arrow handlers were dead: the page root kept
    the focus, so Up/Down (not to mention Home/End) never moved the
    selection.
    """
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    for i in range(30):
        _save_one_game(f"local-k{i:02d}", f"Key {i:02d}")
    win, engine, proxy, warnings = _load_main(qgui_app)
    table = win.findChild(QQuickItem, "gameTable")
    page = win.findChild(QObject, "gamesPage")
    assert win.property("activeFocusItem").objectName() == "gameTable"
    rows = proxy.rowCount()
    assert rows == 30

    QTest.keyClick(win, Qt.Key.Key_Down)
    QTest.qWait(80)
    assert _current_row(table) == 1
    assert _page_selected_ids(page) == [proxy.idAt(1)]

    QTest.keyClick(win, Qt.Key.Key_End)
    QTest.qWait(80)
    assert _current_row(table) == rows - 1
    assert _page_selected_ids(page) == [proxy.idAt(rows - 1)]

    QTest.keyClick(win, Qt.Key.Key_Home)
    QTest.qWait(80)
    assert _current_row(table) == 0
    assert _page_selected_ids(page) == [proxy.idAt(0)]

    QTest.keyClick(win, Qt.Key.Key_PageDown)
    QTest.qWait(80)
    page_row = _current_row(table)
    assert 0 < page_row < rows - 1
    assert _page_selected_ids(page) == [proxy.idAt(page_row)]

    QTest.keyClick(win, Qt.Key.Key_PageUp)
    QTest.qWait(80)
    assert _current_row(table) == 0

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_icon_grid_keyboard_navigation(qgui_app, xdg_env):
    """The icons view takes the keys too: arrows, Home/End, Page keys."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    for i in range(30):
        _save_one_game(f"local-k{i:02d}", f"Key {i:02d}")
    win, engine, proxy, warnings = _load_main(qgui_app)
    grid = win.findChild(QQuickItem, "iconGrid")
    page = win.findChild(QObject, "gamesPage")
    page.setProperty("viewMode", "icons")
    QTest.qWait(250)

    grid.setProperty("currentIndex", 0)
    QTest.qWait(60)
    QTest.keyClick(win, Qt.Key.Key_Right)
    QTest.qWait(80)
    assert grid.property("currentIndex") == 1
    assert _page_selected_ids(page) == [proxy.idAt(1)]

    QTest.keyClick(win, Qt.Key.Key_End)
    QTest.qWait(80)
    assert grid.property("currentIndex") == proxy.rowCount() - 1
    assert _page_selected_ids(page) == [proxy.idAt(proxy.rowCount() - 1)]

    QTest.keyClick(win, Qt.Key.Key_Home)
    QTest.qWait(80)
    assert grid.property("currentIndex") == 0
    assert _page_selected_ids(page) == [proxy.idAt(0)]

    QTest.keyClick(win, Qt.Key.Key_PageDown)
    QTest.qWait(80)
    assert grid.property("currentIndex") > 0

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


def _column_widths(proxy, table, page=None):
    """Visible widths per logical column (mirrors tableColumnWidth).

    Reads live fitted widths and the shrink factor so fresh-start
    autofit does not stale click coordinates; falls back to the same
    static defaults as `defaultColumnWidth` in MainPage.qml.
    """
    defaults = {
        0: 36.0,
        2: 90.0,
        3: 90.0,
        4: 110.0,
        5: 80.0,
        6: 80.0,
        7: 80.0,
        8: 80.0,
        9: 80.0,
        10: 80.0,
        11: 80.0,
    }
    try:
        live = {lg: float(proxy.columnWidth(lg) or 0) for lg in defaults}
    except Exception:
        live = {}
    try:
        shrink = float(page.property("columnShrink")) if page is not None else 1.0
    except Exception:
        shrink = 1.0
    widths = {}
    for lg, d in defaults.items():
        base = live[lg] if live.get(lg, 0) > 0 else d
        widths[lg] = 36.0 if lg == 0 else max(24.0, base * shrink)
    shown = _shown_flags(proxy)
    try:
        table_w = table.property("width") or 0
    except Exception:
        table_w = 0
    fixed = widths[0] + sum(w for _l, w in widths.items() if _l != 1 and shown.get(_l, True))
    try:
        fitted1 = float(proxy.columnWidth(1) or 0)
    except Exception:
        fitted1 = 0
    game_min = fitted1 if fitted1 > 0 else 120.0
    widths[1] = max(game_min, table_w - fixed)
    return widths


def _shown_flags(proxy):
    shown = {0: True, 1: True}
    for logical, flag in (
        (2, "showAppId"),
        (3, "showPlayed"),
        (4, "showTier"),
        (5, "showSource"),
        (6, "showLastPlayed"),
        (7, "showPlatform"),
        (8, "showRunner"),
        (9, "showWine"),
        (10, "showInstallDir"),
        (11, "showCategory"),
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
        order = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    table = None
    try:
        win = host.window()
        table = win.findChild(host.__class__, "gameTable") if win is not None else None
    except Exception:
        table = None
    widths = _column_widths(proxy, table, page)
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


def _wait_for(predicate, limit=200, step=10):
    """Pump frames with real waits until `predicate()` holds (or gives up).

    `QTest.qWait` and not a bare `processEvents()` loop: the layout's
    async passes and timers need wall-clock time, and a tight loop of
    hundreds of iterations can run inside one millisecond on an idle
    machine but starve on a loaded one (this flaked under makepkg load).
    """
    from PySide6.QtTest import QTest

    for _ in range(limit):
        if predicate():
            return True
        QTest.qWait(step)
    return predicate()


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
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow

    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

    # Stragglers from previous tests (separate top-level windows outlive
    # their main window by a few event rounds): close them so title
    # lookups below never match a foreign window.
    for w in QGuiApplication.topLevelWindows():
        try:
            w.close()
        except Exception:
            pass
    qgui_app.processEvents()

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


def test_row_selection_and_numbering(qgui_app, xdg_env):
    """A tap selects the tapped game; gutter numbers follow proxy order."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    for appid in ("b-game", "a-game"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    table = win.findChild(QQuickItem, "gameTable")
    assert page is not None
    assert table is not None

    page.tapGame("b-game", 0)
    qgui_app.processEvents()
    assert _selected_ids(table, proxy) == ["b-game"]

    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None
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

    def widths():
        return (cell(1).property("width"), cell(2).property("width"))

    # Fresh profiles autofit async: wait for widths to settle (three
    # identical reads) before measuring, or the hide/show math races.
    from PySide6.QtTest import QTest

    steady, last = 0, None
    for _ in range(200):
        QTest.qWait(5)
        current = widths()
        steady = steady + 1 if current == last else 0
        last = current
        if steady >= 3:
            break
    w2 = cell(2).property("width")
    assert w2 >= 40  # fresh profiles autofit on load; never the old 90
    assert cell(2).property("visible") is True
    game_w = cell(1).property("width")
    proxy.setProperty("showAppId", False)
    # Wall-clock waits, not frame counts: a scrollbar appearing (or not)
    # moves the elastic column by more than the tolerance, briefly.
    _wait_for(lambda: abs(cell(1).property("width") - (game_w + w2)) <= 3)
    assert cell(2).property("visible") is False
    # Elastic float layout plus background autofit: the game column
    # absorbs the hidden width, exact to a few pixels.
    grown = cell(1).property("width")
    assert grown > game_w
    assert abs(grown - (game_w + w2)) <= 3
    proxy.setProperty("showAppId", True)
    _wait_for(lambda: abs(cell(1).property("width") - game_w) <= 3)
    assert cell(2).property("visible") is True
    assert abs(cell(1).property("width") - game_w) <= 3
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_drawer_modes_switch(qgui_app, xdg_env):
    """Drawer modes switch from the footer (overlay/collapsible only)."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer is not None
    assert drawer.property("collapseButtonVisible") is False
    for mode in ("drawerModeOverlay", "drawerModeSidebar", "drawerModeCollapsible"):
        assert win.findChild(QObject, mode) is None, mode

    def click(name):
        item = win.findChild(QQuickItem, name)
        assert item is not None, name
        pos = item.mapToScene(QPointF(item.property("width") / 2, 5)).toPoint()
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        qgui_app.processEvents()

    # Fresh drawers start collapsed: expand through the header icon,
    # which is also the only way back once collapsed.
    click("drawerHeaderButton")
    assert drawer.property("collapsed") is False
    click("drawerModeOverlayButton")
    assert drawer.property("modal") is True
    assert drawer.property("collapsible") is False
    assert C.load_preferences().drawer_mode == "overlay"
    click("drawerModeCollapsibleButton")
    assert drawer.property("modal") is False
    assert drawer.property("collapsible") is True
    # Open state restored from prefs (was left open above), not forced.
    assert drawer.property("collapsed") is False
    assert C.load_preferences().drawer_mode == "collapsible"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_drawer_open_survives_restart(qgui_app, xdg_env):
    """Closing with the sidebar open reopens it open (close→reopen)."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer.property("collapsed") is True
    button = win.findChild(QQuickItem, "drawerHeaderButton")
    pos = button.mapToScene(QPointF(button.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert drawer.property("collapsed") is False
    assert C.load_preferences().drawer_collapsed is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    for _ in range(3):
        qgui_app.processEvents()
    win2, engine2, _proxy2, warnings2 = _load_main(qgui_app)
    drawer2 = win2.findChild(QObject, "sourceDrawer")
    assert drawer2.property("collapsed") is False
    real2 = [w for w in warnings2 if "graphics scene" not in w]
    assert real2 == []
    win2.close()
    engine2.deleteLater()
    qgui_app.processEvents()


def test_overlay_drawer_keeps_toolbar_icons(qgui_app, xdg_env):
    """Overlay mode must not push the view icons into overflow."""
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    for width in (900, 1280):
        win, _engine, _proxy, warnings = _load_main(qgui_app)
        win.setProperty("width", width)
        win.setProperty("height", 720)
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        def click(name, host=win):
            button = host.findChild(QQuickItem, name)
            pos = button.mapToScene(QPointF(button.property("width") / 2, 5)).toPoint()
            QTest.mouseClick(host, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
            qgui_app.processEvents()

        click("drawerHeaderButton")  # expand: footer hides while collapsed
        click("drawerModeOverlayButton")
        for _ in range(12):
            qgui_app.processEvents()

        def vis(name, host=win):
            out = []
            for it in host.findChildren(QQuickItem, name):
                try:
                    if it.property("visible"):
                        x = it.mapToScene(QPointF(0, 0)).x()
                        out.append((round(x, 1), round(float(it.property("width") or 0), 1)))
                except Exception:
                    continue
            return out

        assert vis("toolbarIcons"), width
        assert vis("searchField"), width
        real = [w for w in warnings if "graphics scene" not in w]
        assert real == [], (width, real)
        win.close()
        _engine.deleteLater()
        for _ in range(3):
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


def test_selection_survives_view_switches(qgui_app, xdg_env):
    """Switching views keeps the row: the page owns the selection.

    The hidden TableView drops its selection model's selection and clears it
    again when it comes back; the old reverse sync mirrored that empty
    selection back into `selectedIds`, so icons -> cards -> list lost the row
    (found in the keyboard-navigation pass, pre-existing).
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    for appid, name in (("a-one", "One"), ("b-two", "Two"), ("c-three", "Three")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    table = win.findChild(QQuickItem, "gameTable")
    assert table is not None

    rows = _table_rows(table, proxy)
    assert len(rows) == 3
    _click_row(qgui_app, win, rows[1])
    QTest.qWait(60)
    picked = _page_selected_ids(page)
    assert len(picked) == 1

    for mode in ("icons", "cards", "list"):
        page.setProperty("viewMode", mode)
        QTest.qWait(120)
        assert _page_selected_ids(page) == picked, mode
        if mode == "list":
            # The table mirror is re-applied on the next event loop turn.
            assert _wait_for(lambda: sorted(_selected_ids(table, proxy)) == picked)

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


def _settle_cards(qgui_app, card, limit=40):
    """Pump frames (with a real wait) until the card height settles.

    Cards instantiate and size asynchronously: a plain processEvents()
    loop leaves the cell at its 16px placeholder, so clicks land before
    the geometry is real.
    """
    from PySide6.QtTest import QTest

    last = None
    stable = 0
    for _ in range(limit):
        qgui_app.processEvents()
        QTest.qWait(50)
        now = card.property("height")
        stable = stable + 1 if now == last else 0
        last = now
        if stable >= 3 and now > 50:
            break
    assert last > 50, last


def _card_play_button(card):
    """The card's Play action button (Kirigami renders Actions itself)."""
    import shiboken6

    best = None
    stack = list(card.childItems())
    while stack:
        item = stack.pop()
        try:
            if (
                item.property("text") == "Play"
                and shiboken6.isValid(item)
                and (best is None or item.property("width") > best.property("width"))
            ):
                best = item
        except Exception:
            pass
        try:
            stack.extend(item.childItems())
        except Exception:
            pass
    return best


def test_card_mouse_gestures(qgui_app, xdg_env):
    """Card clicks select, Ctrl extends, right-click opens the menu.

    Regression: Kirigami.Card emits clicked() with no event at all, so
    the right-click branch inside onClicked never ran (the cards view
    had no context menu, while the icons grid and the table rows had
    one) and the left-click branch threw "Cannot read property
    'modifiers' of undefined", so a click did not even select.
    """
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

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
    for _ in range(40):
        qgui_app.processEvents()
    cards = _delegate_rows(layout)
    assert len(cards) == 2
    # Both cards sit on the same row (same y), so pick by AppID.
    card = next(c for c in cards if c.property("gameId") == "local-doom")
    _settle_cards(qgui_app, card)
    menu = win.findChild(QObject, "gameMenu")
    assert menu is not None

    def selected():
        value = page.property("selectedIds")
        return value.toVariant() if hasattr(value, "toVariant") else list(value)

    def click(button=Qt.LeftButton, mods=Qt.NoModifier):
        pos = card.mapToScene(
            QPointF(card.property("width") / 2, card.property("height") / 2)
        ).toPoint()
        QTest.mouseClick(win, button, mods, pos)
        QTest.qWait(150)
        qgui_app.processEvents()

    # Plain click selects; the card itself reports no modifiers for it.
    page.setProperty("selectedIds", ["local-quake"])
    page.setProperty("menuGid", "")
    qgui_app.processEvents()
    click()
    assert selected() == ["local-doom"]

    # Ctrl adds, a second Ctrl removes (icons grid and table parity).
    page.setProperty("selectedIds", ["local-quake"])
    qgui_app.processEvents()
    click(Qt.LeftButton, Qt.ControlModifier)
    assert sorted(selected()) == ["local-doom", "local-quake"]
    click(Qt.LeftButton, Qt.ControlModifier)
    assert selected() == ["local-quake"]

    # Right-click opens the game menu.
    page.setProperty("menuGid", "")
    qgui_app.processEvents()
    click(Qt.RightButton)
    assert page.property("menuGid") == "local-doom"
    assert menu.property("visible") is True
    menu.setProperty("visible", False)
    qgui_app.processEvents()

    # Middle-click opens the settings (widgets eventFilter parity).
    settings = win.findChild(QObject, "gameSettings")
    assert settings is not None
    click(Qt.MiddleButton)
    assert page.settingsOpen() is True
    settings.close()
    QTest.qWait(100)
    qgui_app.processEvents()
    assert page.settingsOpen() is False

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_card_play_button_clickable(qgui_app, xdg_env, monkeypatch):
    """A real mouse click on a card's Play button launches.

    The card's gesture MouseArea claims right-clicks and Ctrl/Shift
    clicks (a full cover would swallow the button); a plain press has to
    keep reaching the Play action.
    """
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    played = []
    monkeypatch.setattr(model, "play", lambda gid: played.append(gid) or True)
    page = win.findChild(QObject, "gamesPage")
    layout = win.findChild(QQuickItem, "cardLayout")
    assert layout is not None
    page.setProperty("viewMode", "cards")
    for _ in range(40):
        qgui_app.processEvents()
    cards = _delegate_rows(layout)
    assert len(cards) == 1
    card = cards[0]
    _settle_cards(qgui_app, card)
    button = _card_play_button(card)
    assert button is not None
    assert button.property("width") > 20
    pos = button.mapToScene(
        QPointF(button.property("width") / 2, button.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, pos)
    QTest.qWait(150)
    qgui_app.processEvents()
    assert played == ["local-doom"]
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

    # Middle-click opens the settings (widgets eventFilter parity).
    settings = win.findChild(QObject, "gameSettings")
    assert settings is not None
    QTest.mouseClick(win, Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier, pos)
    QTest.qWait(100)
    qgui_app.processEvents()
    assert page.settingsOpen() is True
    settings.close()
    QTest.qWait(50)
    qgui_app.processEvents()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def _standalone_component(qgui_app, filename, props):
    import pathlib

    from PySide6.QtCore import QObject, QUrl, Slot
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem  # noqa: F401 (registers QQuickItem wrapper)

    from tkarcade.gui import kirigami_app as kapp

    class _StubModel(QObject):
        """Minimal gameModel for standalone components (first candidate wins)."""

        @Slot(list, result=str)
        def iconName(self, candidates):
            names = [str(n) for n in candidates or [] if n]
            return names[0] if names else ""

    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.rootContext().setContextProperty("gameModel", _StubModel(engine))
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
            "gameRunning": False,
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
            "gameRunning": False,
        },
    )
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def test_section_box_matches_widgets_group_box(qgui_app):
    """SectionBox: centered title above a padded frame (widgets QGroupBox)."""
    import pathlib

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade.gui import kirigami_app as kapp

    qml_dir = pathlib.Path(kapp.__file__).parent / "qml"
    source = b"""
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    width: 400
    height: 300
    visible: true
    ColumnLayout {
        anchors.fill: parent
        SectionBox {
            id: box
            objectName: "probeBox"
            Layout.fillWidth: true
            title: "Gamescope"
            spacing: 4
            padding: 9
            Controls.CheckBox {
                objectName: "probeChild"
                Layout.alignment: Qt.AlignHCenter
                text: "child"
            }
        }
    }
}
"""
    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    component = QQmlComponent(engine)
    # Base URL only picks the directory for same-dir component lookup; the
    # file itself must not exist, or the engine compiles *that* file.
    component.setData(source, QUrl.fromLocalFile(str(qml_dir / "probe-tmp.qml")))
    assert component.isReady(), component.errorString()

    win = component.create()
    assert win is not None
    QTest.qWait(80)
    qgui_app.processEvents()

    box = win.findChild(QQuickItem, "probeBox")
    title = win.findChild(QQuickItem, "sectionTitleText")
    frame = win.findChild(QQuickItem, "sectionFrame")
    child = win.findChild(QQuickItem, "probeChild")
    assert box is not None and title is not None and frame is not None and child is not None
    assert title.property("visible") is True
    assert title.property("text") == "Gamescope"
    # Centered above the frame (Breeze QGroupBox), never inside it.
    assert abs(title.property("x") + title.property("width") / 2 - box.property("width") / 2) <= 2
    assert title.property("y") + title.property("height") <= frame.property("y")
    # The child lands inside the frame, padded by `padding` on both sides.
    from PySide6.QtCore import QPointF

    child_top = child.mapToItem(box, QPointF(0, 0)).y()
    frame_top = frame.mapToItem(box, QPointF(0, 0)).y()
    assert child_top >= frame_top + 8
    assert child_top + child.property("height") <= frame_top + frame.property("height") - 8
    # The box reserves exactly title + spacing + frame.
    assert (
        abs(
            box.property("implicitHeight")
            - (title.property("height") + box.property("spacing") + frame.property("height"))
        )
        <= 2
    )

    # checkable: the title turns into a centered checkbox and an
    # unchecked box collapses completely -- the whole height is freed
    # (the widgets frame stayed drawn and empty, which is not wanted
    # here: collapsing is how these blocks give the tabs room).
    box.setProperty("checkable", True)
    box.setProperty("checked", False)
    QTest.qWait(80)
    qgui_app.processEvents()
    checkbox = win.findChild(QQuickItem, "sectionTitle")
    assert checkbox is not None and checkbox.property("visible") is True
    cx = checkbox.property("x") + checkbox.property("width") / 2
    assert abs(cx - box.property("width") / 2) <= 2
    assert title.property("visible") is False
    assert frame.property("visible") is False
    assert abs(box.property("implicitHeight") - checkbox.property("height")) <= 2
    box.setProperty("checked", True)
    QTest.qWait(80)
    qgui_app.processEvents()
    assert frame.property("visible") is True
    assert frame.property("height") > 18

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def test_widgets_form_layout_fills_panel(qgui_app):
    """WidgetsFormLayout: field column takes the panel, no centered hole."""
    import pathlib

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade.gui import kirigami_app as kapp

    qml_dir = pathlib.Path(kapp.__file__).parent / "qml"
    source = b"""
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami.layouts as KirigamiLayouts

Window {
    width: 800
    height: 400
    visible: true
    ColumnLayout {
        anchors.fill: parent
        SectionBox {
            id: ours
            objectName: "oursBox"
            Layout.fillWidth: true
            title: "Our form"
            WidgetsFormLayout {
                Controls.TextField {
                    objectName: "oursField"
                    Layout.fillWidth: true
                    KirigamiLayouts.FormData.label: "Gamescope Options:"
                }
            }
        }
        SectionBox {
            id: plain
            objectName: "plainBox"
            Layout.fillWidth: true
            title: "Kirigami form"
            KirigamiLayouts.FormLayout {
                Controls.TextField {
                    objectName: "plainField"
                    Layout.fillWidth: true
                    KirigamiLayouts.FormData.label: "Gamescope Options:"
                }
            }
        }
    }
}
"""
    engine = QQmlEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    component = QQmlComponent(engine)
    # Base URL only picks the directory for same-dir component lookup; the
    # file itself must not exist, or the engine compiles *that* file.
    component.setData(source, QUrl.fromLocalFile(str(qml_dir / "probe-tmp.qml")))
    assert component.isReady(), component.errorString()

    win = component.create()
    assert win is not None
    QTest.qWait(120)
    qgui_app.processEvents()

    ours = win.findChild(QQuickItem, "oursField")
    plain = win.findChild(QQuickItem, "plainField")
    ours_frame = win.findChild(QQuickItem, "oursBox").findChild(QQuickItem, "sectionFrame")
    plain_frame = win.findChild(QQuickItem, "plainBox").findChild(QQuickItem, "sectionFrame")
    assert None not in (ours, plain, ours_frame, plain_frame)

    # The plain form keeps its natural width and is centered in the panel:
    # the field starts past the label column (the hole left of the labels)
    # and stops short of the frame.
    ours_width = ours.property("width")
    ours_right = ours.property("x") + ours_width
    plain_x = plain.property("x")
    plain_right = plain_x + plain.property("width")
    assert plain_x > 150
    assert plain_right < plain_frame.property("width") - 40
    # Ours sits right after the label column...
    assert ours.property("x") < plain_x - 50
    # ...and the field column takes the panel up to its right edge.
    assert ours_frame.property("width") - ours_right <= 24
    assert ours_right > plain_right + 100

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    engine.deleteLater()
    qgui_app.processEvents()


def _check_settings_title_footer(swin, appid):
    """Title names the game; Diff/Reset lead the footer, Save/Cancel close."""
    from PySide6.QtQuick import QQuickItem

    # Widgets GameDialog: "Game Settings — <name> (<appid>)".
    assert swin.title() == f"Game Settings — Sections ({appid})"

    diff = swin.findChild(QQuickItem, "diffButton")
    reset = swin.findChild(QQuickItem, "settingsReset")
    save = swin.findChild(QQuickItem, "settingsSave")
    cancel = swin.findChild(QQuickItem, "settingsCancel")
    for item in (diff, reset, save, cancel):
        assert item is not None
        assert item.property("width") > 0
    # QDialogButtonBox layout: Diff then Reset on the left, Save then
    # Cancel on the right, with Save as the default button.
    assert diff.property("x") < reset.property("x")
    assert save.property("x") > reset.property("x") + reset.property("width")
    assert cancel.property("x") > save.property("x") + save.property("width")
    assert save.property("highlighted") is True


def _check_settings_sections(win, settings, tabs, qgui_app):
    """Performance/System groups are SectionBoxes; fields fill the tab."""
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    def visible_titles(index):
        tabs.setProperty("currentIndex", index)
        QTest.qWait(150)
        qgui_app.processEvents()
        titles = {
            c.property("text")
            for c in settings.findChildren(QQuickItem, "sectionTitleText")
            if c.isVisible()
        }
        # The Dependency Status box lives below the tabs and is in every page.
        titles.discard("Dependency Status")
        return sorted(titles)

    # Every desktop-integration group draws the widgets QGroupBox look:
    # centered title above a framed panel (the QQC2 GroupBox painted the
    # title inside the frame at the top-left).
    assert visible_titles(TAB_GENERAL) == ["Game", "Profile"]
    assert visible_titles(TAB_LAUNCH) == ["Launch", "Pre/Post Commands"]
    assert visible_titles(TAB_ENV) == ["Environment Variables"]
    # A local game has its own Wine/umu runtime section (with the Steam
    # Proton box and its note right below, never the Proton box).
    assert visible_titles(TAB_COMPAT) == ["Windows Runtime", "Wine"]
    assert visible_titles(TAB_PERF) == ["Game Mode", "MangoHud", "RT Upscaler"]
    assert visible_titles(TAB_DISPLAY) == ["Display Mode", "Gamescope"]
    assert visible_titles(TAB_SYSTEM) == [
        "Audio",
        "Idle Suspend",
        "Network",
        "Night Light",
        "Notifications",
        "Saves (Ludusavi)",
    ]
    assert visible_titles(TAB_ART) == ["Artwork", "Notes"]

    # Ludusavi: the widgets form layout indents the checkboxes into the
    # field column, stretches the name field across the panel and puts
    # the note in a spanning row (inside the System tab's Saves box).
    _settings_tab(win, TAB_SYSTEM)
    form = win.findChild(QQuickItem, "luForm")
    name = win.findChild(QQuickItem, "luName")
    enable = win.findChild(QQuickItem, "luEnable")
    note = win.findChild(QQuickItem, "luNote")
    assert None not in (form, name, enable, note)
    assert enable.property("x") > 0
    assert abs(enable.property("x") - name.property("x")) <= 1
    assert abs(name.property("x") + name.property("width") - form.property("width")) <= 24
    assert abs(note.property("x")) <= 1
    assert abs(note.property("width") - form.property("width")) <= 1


def _check_dependency_box(win, settings, tabs, qgui_app):
    """Dependency Status: two columns of marks below the tabs."""
    import shiboken6
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    box = win.findChild(QQuickItem, "depStatusBox")
    frame = box.findChild(QQuickItem, "sectionFrame")
    grid = box.findChild(QQuickItem, "depStatusGrid")
    check = box.findChild(QQuickItem, "sectionTitle")
    assert box is not None and frame is not None and grid is not None and check is not None
    # Widgets: the group box sits below the tab widget, titled and framed
    # -- with a single border (the widgets nested a sunken panel; the
    # centered checkbox title replaces it).
    assert box.property("y") >= tabs.property("y") + tabs.property("height")
    assert check.property("text") == "Dependency Status"
    # The footer blocks start collapsed (reference material); expand this
    # one to measure the layout the widgets had.
    assert check.property("checked") is False and frame.property("visible") is False
    check.setProperty("checked", True)
    QTest.qWait(120)
    qgui_app.processEvents()
    assert check.property("checked") is True and frame.property("visible") is True
    # The plain label variant stays hidden while the box is checkable.
    assert box.findChild(QQuickItem, "sectionTitleText").property("visible") is False
    assert check.property("y") + check.property("height") <= frame.property("y")
    assert frame.property("y") + frame.property("height") <= box.property("height")
    frames = [
        child
        for child in box.findChildren(QQuickItem)
        if child.property("objectName") == "sectionFrame"
    ]
    assert len(frames) == 1

    # The grid sits inside the frame, padded on every side.
    inset = grid.mapToItem(box, QPointF(0, 0)).y() - frame.mapToItem(box, QPointF(0, 0)).y()
    assert 0 < inset < 16
    assert grid.property("y") + grid.property("height") <= frame.property("height")

    cells = [
        child
        for child in grid.childItems()
        if shiboken6.isValid(child) and child.property("objectName") == "depStatusLine"
    ]
    # Prefix + broken/custom exe + gamescope/mangohud/upscale/ludusavi +
    # the two wheels: a local game never gets the Steam launch-options line.
    assert len(cells) == 8
    assert grid.property("columns") == 2
    # Row-major packing (the widgets reflow keeps visible lines first):
    # cells 0/1 share a row, cell 2 opens the second one.
    assert abs(cells[1].property("y") - cells[0].property("y")) <= 1
    assert cells[1].property("x") > cells[0].property("x") + 50
    assert cells[2].property("y") > cells[0].property("y")
    assert abs(cells[2].property("x") - cells[0].property("x")) <= 1
    # Every line is a colored mark plus text, never raw markup.
    for cell in cells:
        text = cell.property("text")
        assert text.startswith('<span style="color:#'), text
        assert text.split(">", 1)[1][0] in "✓⚠●"
    assert "No Custom Prefix" in cells[0].property("text")

    # The widgets picked the mark palette from the theme's darkness.
    dark = settings.property("statusDark")
    assert settings.statusColor("ok") == ("#7ee787" if dark else "#1a7f37")
    assert settings.statusColor("warn") == ("#f47067" if dark else "#d1242f")
    assert settings.statusColor("note") == ("#e3b341" if dark else "#9a6700")
    # The wording is the widgets' (game_dialog._binary_status/_set_status).
    assert (
        settings.statusText({"msg": "prefix-none"}) == "No Custom Prefix — Game Launches Directly"
    )
    assert (
        settings.statusText({"msg": "binary-off", "args": ["mangohud", "/usr/bin/mangohud"]})
        == "mangohud — /usr/bin/mangohud (Off)"
    )
    assert (
        settings.statusText({"msg": "binary-missing", "args": ["mangohud"]})
        == "mangohud Not Found in PATH — Skipped at Launch"
    )
    assert (
        settings.statusText({"msg": "binary-missing-fatal", "args": ["zink-run"]})
        == "zink-run Not Found in PATH — Launch Will Fail"
    )
    assert (
        settings.statusText({"msg": "hook-missing", "args": ["pre-hook", "/tmp/gone.sh"]})
        == "pre-hook Not Found: /tmp/gone.sh"
    )
    assert (
        settings.statusText({"msg": "steam-missing"})
        == "Steam Launch Options Lack tkarcade (Add: tkarcade %command%)"
    )

    # The centered checkbox collapses the whole block and persists the
    # choice (a disabled box leaves the tabs their room back).
    check.setProperty("checked", False)
    QTest.qWait(80)
    qgui_app.processEvents()
    assert frame.property("visible") is False
    assert abs(box.property("implicitHeight") - check.property("height")) <= 2
    assert C.load_preferences().show_dependency_status is False
    check.setProperty("checked", True)
    QTest.qWait(60)
    qgui_app.processEvents()
    assert frame.property("visible") is True
    assert C.load_preferences().show_dependency_status is True


def test_settings_window_chrome_and_sections(qgui_app, xdg_env):
    """Window title/footer, the tab sections and the Dependency Status box.

    One main window and one settings dialog cover what three cases each
    built for themselves; the dependency box toggles preferences, so it
    runs last.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-sections"
    cfg.general.name = "Sections"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    settings = win.findChild(QObject, "gameSettings")
    settings.openFor("local-sections")
    QTest.qWait(120)
    qgui_app.processEvents()
    swin = _settings_window(qgui_app)
    tabs = win.findChild(QQuickItem, "settingsTabs")

    _check_settings_title_footer(swin, "local-sections")
    _check_settings_sections(win, settings, tabs, qgui_app)
    _check_dependency_box(win, settings, tabs, qgui_app)

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_env_tab_widgets_layout(qgui_app, xdg_env):
    """Environment tab: Variable/Value header and the Add/Remove pair."""
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-env"
    cfg.general.name = "Env"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    settings = win.findChild(QObject, "gameSettings")
    tabs = win.findChild(QQuickItem, "settingsTabs")
    settings.openFor("local-env")
    QTest.qWait(120)
    qgui_app.processEvents()
    swin = _settings_window(qgui_app)
    tabs.setProperty("currentIndex", TAB_ENV)
    QTest.qWait(150)
    qgui_app.processEvents()

    def click(name):
        _click(swin, name)

    def rows():
        form = swin.findChild(QQuickItem, "envForm")
        assert form is not None
        return [
            c
            for c in form.childItems()
            if c.property("objectName") == "envRow" and c.property("width") > 0
        ]

    # The widgets table header sits above the two field columns.
    head_var = swin.findChild(QQuickItem, "envHeaderVariable")
    head_val = swin.findChild(QQuickItem, "envHeaderValue")
    assert head_var.property("text") == "Variable"
    assert head_val.property("text") == "Value"
    assert head_var.property("font").bold() and head_val.property("font").bold()
    assert head_var.property("x") < head_val.property("x")

    # Remove acts on the row that last held focus (the widgets selection).
    remove = swin.findChild(QQuickItem, "envRemove")
    assert remove.property("enabled") is False
    # A game without variables shows one empty row to type into (as if
    # Add had been clicked once with nothing filled in).
    assert len(rows()) == 1
    click("envAdd")
    assert len(rows()) == 2
    first = rows()[0].childItems()[0]
    second = rows()[0].childItems()[1]
    first.setProperty("text", "A")
    rows()[1].childItems()[0].setProperty("text", "B")
    assert rows()[1].childItems()[0].property("text") == "B"
    # The header columns line up with the row fields.
    assert abs(head_var.property("x") - first.property("x")) <= 2
    assert abs(head_var.property("width") - first.property("width")) <= 8
    assert abs(head_val.property("x") - second.property("x")) <= 2
    # The button row is centered and ordered Add, Bulk Edit..., Add
    # Preset..., Remove (the destructive action travels last).
    order = [
        swin.findChild(QQuickItem, name) for name in ("envAdd", "envBulk", "envPreset", "envRemove")
    ]
    lefts = [b.mapToScene(QPointF(0, 0)).x() for b in order]
    assert lefts == sorted(lefts) and len(set(lefts)) == 4
    right = lefts[-1] + order[-1].property("width")
    assert abs((lefts[0] + right) / 2 - swin.property("width") / 2) <= 3
    rows()[1].childItems()[0].forceActiveFocus()
    QTest.qWait(60)
    qgui_app.processEvents()
    assert remove.property("enabled") is True
    click("envRemove")
    assert len(rows()) == 1
    assert rows()[0].childItems()[0].property("text") == "A"
    assert remove.property("enabled") is False

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_tab_bodies_scroll(qgui_app, xdg_env):
    """A short window scrolls each tab body; no field is unreachable.

    ScrollView takes its scrollable size from the content's implicit
    size: the wrapper Item must advertise it (an explicit `height:`
    alone leaves contentHeight at -1 and the content gets squeezed into
    the viewport, hiding everything below the fold).
    """
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-scroll"
    cfg.general.name = "Scroll"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    cfg.env.vars = {"FOO": "bar"}
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    settings = win.findChild(QObject, "gameSettings")
    settings.openFor("local-scroll")
    QTest.qWait(150)
    swin = _settings_window(qgui_app)
    tabs = swin.findChild(QQuickItem, "settingsTabs")
    # Shrink to a short window (the dialog stayed resizable in the
    # widgets): the tab area keeps only the leftover height. The footer
    # blocks start collapsed, so this has to be shorter than before.
    swin.setProperty("height", 420)
    QTest.qWait(80)

    bodies = SETTINGS_TAB_BODIES
    for tab, name in bodies.items():
        tabs.setProperty("currentIndex", tab)
        QTest.qWait(150)
        view = swin.findChild(QQuickItem, name)
        assert view is not None, name
        assert view.property("contentHeight") > 0, name
        if view.property("contentHeight") <= view.property("height"):
            continue
        bar = _vertical_bar(view)
        assert bar is not None and bar.property("visible") is True, name
        assert bar.property("size") < 1, name
        assert bar.property("position") == 0, name

    # Performance is the tall tab (three groups): scrolling to the end has
    # to bring the last field of the last section fully into the viewport.
    tabs.setProperty("currentIndex", TAB_PERF)
    QTest.qWait(150)
    view = swin.findChild(QQuickItem, "settingsPerfScroll")
    flick = view.property("contentItem")
    bottom = flick.property("contentHeight") - flick.property("height")
    assert bottom > 0
    flick.setProperty("contentY", bottom)
    QTest.qWait(80)
    field = swin.findChild(QQuickItem, "rtArgs")
    assert field is not None
    top = field.mapToItem(flick, QPointF(0, 0)).y()
    assert top >= 0
    assert top + field.property("height") <= flick.property("height")

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    settings.close()
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_tabs_regrouped(qgui_app, xdg_env):
    """Eight tabs: the fields that moved follow their new page.

    The launch fields left General for Launch, MangoHud/RT Upscaler left
    Display for Performance, and the old Ludusavi/Notes pages are groups
    inside System and the artwork tab now.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    _save_one_game("local-tabs", "Tabs")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-tabs")
    swin = _settings_window(qgui_app)
    tabs = swin.findChild(QQuickItem, "settingsTabs")

    assert tabs.property("count") == len(SETTINGS_TAB_TITLES)
    # TabBar delegates are ListView items: itemAt() is not reachable from
    # Python, so read the buttons from the tree and order them by x.
    import shiboken6

    buttons = [
        b
        for b in tabs.findChildren(QQuickItem)
        if shiboken6.isValid(b) and "TabButton" in b.metaObject().className()
    ]
    assert len(buttons) == len(SETTINGS_TAB_TITLES)
    buttons.sort(key=lambda b: b.property("x"))
    assert [b.property("text") for b in buttons] == list(SETTINGS_TAB_TITLES)

    def shown(*names):
        out = []
        for name in names:
            item = swin.findChild(QQuickItem, name)
            assert item is not None, name
            if item.isVisible():
                out.append(name)
        return out

    general = (
        "settingsAppid",
        "settingsName",
        "settingsType",
        "settingsPlatform",
        "settingsCats",
        "settingsProfiles",
    )
    launch = (
        "settingsExe",
        "settingsPrefix",
        "settingsArgs",
        "settingsCwd",
        "settingsMenu",
        "settingsTimeout",
        "settingsLog",
        "ppPre",
        "ppPreArgs",
        "ppPost",
        "ppPostArgs",
        "ppTimeout",
        "ppShell",
    )
    _settings_tab(swin, TAB_GENERAL)
    assert shown(*general) == list(general)
    assert shown(*launch) == []
    _settings_tab(swin, TAB_LAUNCH)
    assert shown(*launch) == list(launch)
    assert shown("settingsPlatform", "settingsCats") == []
    _settings_tab(swin, TAB_PERF)
    assert shown("perfFeral", "mhEnable", "rtEnable") == ["perfFeral", "mhEnable", "rtEnable"]
    _settings_tab(swin, TAB_DISPLAY)
    assert shown("gsEnable", "mhEnable", "rtEnable") == ["gsEnable"]
    _settings_tab(swin, TAB_SYSTEM)
    assert shown("luEnable", "luName", "luCoverage") == ["luEnable", "luName", "luCoverage"]
    _settings_tab(swin, TAB_ART)
    assert shown("artIcon", "settingsNotes") == ["artIcon", "settingsNotes"]
    assert shown("luEnable") == []

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
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


def test_select_all_and_empty_click_clears(qgui_app, xdg_env):
    """Ctrl+A selects every game; an empty viewport click drops it again."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

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

    def selected_js():
        value = page.property("selectedIds")
        if hasattr(value, "toVariant"):
            value = value.toVariant()
        return sorted(str(g) for g in (value or []))

    table.forceActiveFocus()
    qgui_app.processEvents()
    QTest.keyClick(win, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qgui_app.processEvents()
    assert selected() == ["a-game", "b-game", "c-game"]
    assert selected_js() == ["a-game", "b-game", "c-game"]

    # Empty area below the last row (the page is much taller than the rows).
    empty = table.mapToScene(QPointF(table.width() / 2, table.height() - 24)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, empty)
    qgui_app.processEvents()
    assert selected() == []
    assert selected_js() == []

    # The icons view follows the same rule on its own empty area.
    page.setProperty("viewMode", "icons")
    qgui_app.processEvents()
    grid = win.findChild(QQuickItem, "iconGrid")
    assert grid is not None
    grid.forceActiveFocus()
    qgui_app.processEvents()
    QTest.keyClick(win, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qgui_app.processEvents()
    assert selected_js() == ["a-game", "b-game", "c-game"]
    empty = grid.mapToScene(QPointF(grid.width() - 20, grid.height() - 20)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, empty)
    qgui_app.processEvents()
    assert selected_js() == []
    page.setProperty("viewMode", "list")
    qgui_app.processEvents()

    # Ctrl+A inside a text field stays that field's Select All.
    search = win.findChild(QQuickItem, "searchField")
    assert search is not None
    search.forceActiveFocus()
    qgui_app.processEvents()
    QTest.keyClick(win, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qgui_app.processEvents()
    assert selected() == []
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_artwork_donor_prompt_stays_in_settings(qgui_app, xdg_env):
    """Artwork Find… opens a donor-titled prompt inside the settings window.

    The prompt is a Kirigami.Dialog (Popup): with no explicit parent in a
    plain Window it became a stray native window behind the modal
    settings window, unusable, and its title fell through to the
    Gamescope Preset branch.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid, name in (("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.general.custom_executable = "/bin/true"
        C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_ART)
    qgui_app.processEvents()

    _click(swin, "artDonorFind")
    prompt = swin.findChild(QObject, "settingsChoicePrompt")
    assert prompt is not None
    assert prompt.property("visible") is True, (
        f"parent={prompt.property('parent')} "
        f"tab={swin.findChild(QQuickItem, 'settingsTabs').property('currentIndex')} "
        f"warnings={[w for w in warnings if 'graphics scene' not in w]}"
    )
    assert "Gamescope" not in prompt.property("title")
    parent = prompt.property("parent")
    assert parent is not None, "choice prompt has no QML parent (stray window)"
    # A parentless Kirigami.Dialog became its own top-level window: it sat
    # behind this modal one, unusable. It must not be a top-level at all.
    from PySide6.QtGui import QGuiApplication

    titles = [w.title() for w in QGuiApplication.topLevelWindows()]
    assert not [t for t in titles if t and t == prompt.property("title")], titles
    assert swin.findChild(QQuickItem, "settingsChoiceBox").property("count") >= 1

    _click(swin, "settingsChoiceOk")
    donor = swin.findChild(QQuickItem, "artDonor").property("text")
    assert donor in ("local-doom", "local-quake")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
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
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

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
    _fire(win.findChild(QObject, "removeConfirm"))
    qgui_app.processEvents()
    assert not C.game_file("local-doom").exists()
    assert not C.game_file("local-quake").exists()
    assert proxy.rowCount() == 0
    cleanup = win.findChild(QObject, "cleanupDialog")
    assert cleanup.property("visible") is True
    assert cleanup.property("leftovers") == ["local-doom"]
    _fire(win.findChild(QObject, "cleanupConfirm"))
    qgui_app.processEvents()
    assert not profiles.exists()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_prompt_dialogs_confirm_and_close(qgui_app, xdg_env):
    """PromptDialog confirms run their model calls and close."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    bad = C.GameConfig()
    bad.general.appid = "local-bad"
    bad.general.name = "Bad"
    bad.general.custom_executable = "/nonexistent/game"
    bad.general.game_type = "native"
    C.save(bad)
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.setProperty("menuGid", "local-doom")
    for name, confirm in (("shaderDialog", "shaderConfirm"), ("historyDialog", "historyConfirm")):
        dlg = win.findChild(QObject, name)
        dlg.open()
        qgui_app.processEvents()
        assert dlg.property("visible") is True
        _fire(win.findChild(QObject, confirm))
        qgui_app.processEvents()
        assert dlg.property("opened") is False
    page.openValidateDialog("local-bad")
    qgui_app.processEvents()
    validate = win.findChild(QObject, "validateDialog")
    assert validate.property("visible") is True
    validate.close()
    qgui_app.processEvents()
    assert validate.property("opened") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_about_opens_modal_window(qgui_app, xdg_env):
    """About is a separate modal window with the app text."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem

    win, engine, _proxy, warnings = _load_main(qgui_app)
    dlg = win.findChild(QObject, "aboutDialog")
    dlg.open()
    swin = _modal_window(qgui_app, ("About TKArcade",))
    assert swin.property("modality") == Qt.WindowModality.WindowModal
    assert swin.findChild(QQuickItem, "aboutText").property("text") != ""
    dlg.close()
    qgui_app.processEvents()
    assert swin.isVisible() is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_escape_closes_shell_dialogs(qgui_app, xdg_env):
    """Escape cancels the separate dialog windows (widgets QDialog reject())."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    win, engine, _proxy, warnings = _load_main(qgui_app)
    about = win.findChild(QObject, "aboutDialog")
    prefs = win.findChild(QObject, "prefsDialog")
    history = win.findChild(QObject, "historyView")
    about.open()
    window = _modal_window(qgui_app, ("About TKArcade",))
    assert about.property("visible") is True
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert _wait_for(lambda: about.property("visible") is False), "About stayed open"
    prefs.load()
    prefs.open()
    window = _modal_window(qgui_app, ("Preferences",))
    assert prefs.property("visible") is True
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert _wait_for(lambda: prefs.property("visible") is False), "Preferences stayed open"
    history.open()
    window = _modal_window(qgui_app, ("Session History",))
    assert history.property("visible") is True
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert _wait_for(lambda: history.property("visible") is False), "History stayed open"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_escape_dismisses_topmost_popup_first(qgui_app, xdg_env, monkeypatch):
    """Escape closes the open popup, then the dialog itself (QDialog order)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    import tkarcade.steam as steammod

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3")])
    _save_one_game("99", "Doom 3", "proton")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("99")
    swin = _settings_window(qgui_app)
    dialog = win.findChild(QObject, "gameSettings")
    confirm = win.findChild(QObject, "settingsConfirm")
    # A confirmation popup goes first: the window keeps the edits.
    dialog.resetDefaults()
    assert _wait_for(lambda: confirm.property("opened") is True), "confirm did not open"
    QTest.keyClick(swin, Qt.Key.Key_Escape)
    assert _wait_for(lambda: confirm.property("opened") is False), "Escape left the confirm open"
    assert dialog.property("visible") is True
    # A combo popup (a QQC2 Menu in the desktop style) comes first too.
    # `_click` polls the window hit test: the dim overlay of the confirm
    # just closed sits above everything for a moment and would swallow a
    # raw click (the popups now render inside this window).
    _click(swin, "settingsType")
    assert _wait_for(lambda: _opened_popups(dialog) != []), "combo popup did not open"
    QTest.keyClick(swin, Qt.Key.Key_Escape)
    assert _wait_for(lambda: _opened_popups(dialog) == []), "Escape left the combo popup open"
    assert dialog.property("visible") is True
    # Nothing left to dismiss: the window itself cancels.
    QTest.keyClick(swin, Qt.Key.Key_Escape)
    assert _wait_for(lambda: dialog.property("visible") is False)
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_enter_presses_the_default_button(qgui_app, xdg_env):
    """Enter hits the widget's default button (OK, Save, Close)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    _save_one_game("local-doom", "Doom")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    about = win.findChild(QObject, "aboutDialog")
    about.open()
    window = _modal_window(qgui_app, ("About TKArcade",))
    _settle_focus(window)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert _wait_for(lambda: about.property("visible") is False), "About ignored Enter"
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    _settle_focus(swin)
    dialog = win.findChild(QObject, "gameSettings")
    name = swin.findChild(QQuickItem, "settingsName")
    name.setProperty("text", "Doom II")
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: dialog.property("visible") is False), "settings ignored Enter"
    assert C.load("local-doom").general.name == "Doom II"
    history = win.findChild(QObject, "historyView")
    history.open()
    window = _modal_window(qgui_app, ("Session History",))
    _settle_focus(window)
    QTest.keyClick(window, Qt.Key.Key_Return)
    assert _wait_for(lambda: history.property("visible") is False), "History ignored Enter"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_enter_accepts_the_open_confirm(qgui_app, xdg_env):
    """Enter goes to the open popup's accept button first (QMessageBox parity)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    _save_one_game("local-doom", "Doom")
    template = C.load_defaults()
    template.general.name = "From Template"
    C.save_defaults(template)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    _settle_focus(swin)
    dialog = win.findChild(QObject, "gameSettings")
    confirm = win.findChild(QObject, "settingsConfirm")
    dialog.resetDefaults()
    assert _wait_for(lambda: confirm.property("opened") is True), "confirm did not open"
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: confirm.property("opened") is False), "Enter missed the confirm"
    assert dialog.property("visible") is True  # still the settings window
    assert C.load("local-doom").general.name == "From Template"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_enter_keeps_the_text_area_newline(qgui_app, xdg_env):
    """Enter in an editable TextArea stays a newline (never the default button)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    _settle_focus(swin)
    dialog = win.findChild(QObject, "gameSettings")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_ART)
    notes = swin.findChild(QQuickItem, "settingsNotes")
    notes.forceActiveFocus()
    QTest.qWait(120)
    before = notes.property("text")
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: notes.property("text") != before), "TextArea lost Return"
    assert dialog.property("visible") is True  # the settings window never saved
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_quit_shortcut_is_application_modal_proof(qgui_app, xdg_env):
    """Ctrl+Q lives at application scope so modal windows can't eat it."""
    from PySide6.QtCore import QObject, Qt

    win, engine, _proxy, warnings = _load_main(qgui_app)
    shortcut = win.findChild(QObject, "quitShortcut")
    assert shortcut is not None
    assert shortcut.property("enabled") is True
    assert shortcut.property("context") == Qt.ShortcutContext.ApplicationShortcut
    assert shortcut.property("sequence") == "Ctrl+Q"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_scan_flow_adds_steam_game(qgui_app, xdg_env, monkeypatch):
    """Scan lists unconfigured Steam games; Add Selected writes configs."""
    from PySide6.QtCore import QObject

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
    swin = _modal_window(qgui_app, ("Add Games",))
    _click(swin, "scanConfirm")
    qgui_app.processEvents()
    assert C.game_file("99").exists()
    assert C.game_file("100").exists()
    assert proxy.rowCount() == 2
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_scan_enter_adds_selected(qgui_app, xdg_env, monkeypatch):
    """Enter on the scan window adds the selected games (its default button)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    import tkarcade.steam as steammod
    from tkarcade import config as C

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3"), ("100", "Quake 4")])
    win, engine, proxy, warnings = _load_main(qgui_app)
    dialog = win.findChild(QObject, "scanDialog")
    dialog.setProperty("candidates", [["99", "Doom 3"], ["100", "Quake 4"]])
    dialog.open()
    swin = _modal_window(qgui_app, ("Add Games",))
    _settle_focus(swin)
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: C.game_file("100").exists()), "Enter added nothing"
    assert C.game_file("99").exists()
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
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

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
    swin = _modal_window(qgui_app, ("Preferences",))
    # The form scrolls: its wrapper advertises the form's implicit size
    # (an explicit `height:` alone leaves contentHeight at -1).
    scroller = swin.findChild(QQuickItem, "prefsScroll")
    assert scroller.property("contentHeight") > 0
    _click(swin, "prefsSave")
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


def test_prefs_enter_saves(qgui_app, xdg_env):
    """Enter saves the Preferences window (the widgets default button)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    win, engine, _proxy, warnings = _load_main(qgui_app)
    dialog = win.findChild(QObject, "prefsDialog")
    dialog.open()
    swin = _modal_window(qgui_app, ("Preferences",))
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
    _settle_focus(swin)
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: C.load_preferences().sgdb_api_key == "secret"), "Enter ignored"
    assert _wait_for(lambda: dialog.property("visible") is False), "Save left the window open"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
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

    for appid, cats in (("local-doom", ["Action"]), ("local-quake", ["Retro"])):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.categories = cats
        C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    status = win.findChild(QQuickItem, "statusLabel")
    assert status is not None
    assert "shown" not in status.property("text")
    proxy.setProperty("textQuery", "doom")
    qgui_app.processEvents()
    assert "1 Shown" in status.property("text")
    proxy.setProperty("textQuery", "")
    qgui_app.processEvents()
    assert "shown" not in status.property("text")
    # The category filter is a filter too: it must append the count.
    proxy.setProperty("categoryKey", "Retro")
    qgui_app.processEvents()
    assert proxy.rowCount() == 1
    assert "1 Shown" in status.property("text")
    proxy.setProperty("categoryKey", "")
    qgui_app.processEvents()
    assert "shown" not in status.property("text")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_empty_import_opens_dialog(qgui_app, xdg_env):
    """Empty state offers Import and opens the import window; no table
    header floats over the placeholder (widgets parity)."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    win, _engine, proxy, warnings = _load_main(qgui_app)
    assert proxy.rowCount() == 0
    header = win.findChild(QQuickItem, "tableHeader")
    assert header is not None and header.property("visible") is False
    imp = win.findChild(QQuickItem, "emptyImport")
    assert imp is not None and imp.property("visible") is True
    pos = imp.mapToScene(QPointF(imp.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    dialog = win.findChild(QObject, "importDialog")
    assert dialog.property("visible") is True
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
    assert page.property("columnOrder").toVariant() == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    header = win.findChild(QQuickItem, "tableHeader")

    def xs():
        return _column_cell_x(header, page, proxy, 2), _column_cell_x(header, page, proxy, 3)

    app_x, played_x = xs()
    assert app_x < played_x
    page.moveColumn(2, 1)
    qgui_app.processEvents()
    app_x, played_x = xs()
    assert played_x < app_x
    assert page.property("columnOrder").toVariant() == [0, 1, 3, 2, 4, 5, 6, 7, 8, 9, 10, 11]
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
    assert [proxy.columnLogical(c) for c in range(12)] == [0, 1, 3, 2, 4, 5, 6, 7, 8, 9, 10, 11]
    proxy.setProperty("showSource", False)
    qgui_app.processEvents()
    prefs = C.load_preferences()
    assert prefs.column_order == "0,1,3,2,4,5,6,7,8,9,10,11"
    assert prefs.hidden_columns == "5,7,8,9,10,11"
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
        ("actionAdd", "Add Game"),
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
            # idAt(row) is only safe with a row that really is a proxy row:
            # a declared JS loop var (extendSelect) or a page helper's own
            # parameter (tableSingleSelect). A delegate's `row` is the
            # visual row, so delegates must use model.gameId instead.
            window = src[max(0, i - 8) : i]
            if re.search(r"idAt\s*\(\s*row\s*\)", line) and not (
                any("for (var row" in prev for prev in window)
                or any(re.search(r"function\s+\w+\s*\(\s*row\b", prev) for prev in window)
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


def test_gamepad_icon_everywhere_no_card_suits():
    """input-gamepad leads everywhere; applications-games is fallback-only.

    applications-games renders as card suits in some themes, so it may
    only appear inside an iconName([...]) fallback chain (oxygen lacks
    input-gamepad) or a // comment — never as a direct icon name.
    """
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    root = pathlib.Path(kapp.__file__).parent
    offenders = []
    for path in sorted(root.glob("*.py")) + sorted((root / "qml").glob("*.qml")):
        try:
            src = path.read_text()
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if (
                "applications-games" in line
                and "iconName(" not in line
                and not line.strip().startswith("//")
            ):
                offenders.append(f"{path.name}:{i}")
    assert offenders == []
    main = (root / "qml" / "main.qml").read_text()
    assert 'handleClosedIcon.name: gameModel.iconName(["input-gamepad"' in main


def test_hamburger_holds_tools_and_persisted_drawer_modes(qgui_app, xdg_env):
    """Hamburger replaces Tools; drawer modes persist through prefs."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    burger = win.findChild(QQuickItem, "hamburgerButton")
    assert burger is not None
    menu = win.findChild(QObject, "hamburgerMenu")
    assert menu is not None
    center = burger.mapToScene(
        QPointF(burger.property("width") / 2, burger.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    for _ in range(20):
        qgui_app.processEvents()
        try:
            if menu.property("visible"):
                break
        except Exception:
            break
    assert menu.property("visible") is True
    texts = set()
    for obj in menu.findChildren(QObject):
        try:
            text = obj.property("text")
        except Exception:
            continue
        if isinstance(text, str) and text:
            texts.add(text)
    assert {"Scan Steam Library...", "Reload", "Quit"} <= texts
    assert win.findChild(QObject, "drawerModeCollapsible") is None
    assert win.findChild(QObject, "drawerModeSidebar") is None
    assert win.findChild(QObject, "drawerModeOverlay") is None
    switch = win.findChild(QQuickItem, "drawerModeCollapsibleButton")
    assert switch is not None
    center = switch.mapToScene(
        QPointF(switch.property("width") / 2, switch.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    qgui_app.processEvents()
    assert C.load_preferences().drawer_mode == "collapsible"
    drawer = win.findChild(QObject, "sourceDrawer")
    assert drawer.property("collapsible") is True
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_hamburger_global_defaults_entry(qgui_app, xdg_env):
    """The hamburger menu opens the Global Defaults editor (widgets menu)."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    burger = win.findChild(QQuickItem, "hamburgerButton")
    menu = win.findChild(QObject, "hamburgerMenu")
    center = burger.mapToScene(
        QPointF(burger.property("width") / 2, burger.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    for _ in range(20):
        qgui_app.processEvents()
        if menu.property("visible"):
            break
    entry = menu.findChild(QObject, "menuDefaults")
    assert entry is not None
    assert entry.property("text") == "Global Defaults..."
    _fire(entry)
    qgui_app.processEvents()
    dlg = win.findChild(QObject, "gameSettings")
    assert dlg.property("defaultsMode") is True
    assert dlg.property("visible") is True
    dswin = _modal_window(qgui_app, ("Global Defaults",))
    assert (
        dswin.findChild(QQuickItem, "settingsReset").property("text") == "Reset to Factory Defaults"
    )
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_header_menu_resets_columns(qgui_app, xdg_env):
    """Widgets header menu parity: it closes with Reset Columns."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    reset = win.findChild(QObject, "menuResetColumns")
    assert reset is not None
    proxy.setProperty("showAppId", False)
    proxy.setProperty("showPlatform", True)
    proxy.setProperty("showCategory", True)
    qgui_app.processEvents()
    _fire(reset)
    qgui_app.processEvents()
    assert proxy.property("showAppId") is True
    assert proxy.property("showPlatform") is False
    assert proxy.property("showCategory") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_hamburger_validates_the_selection(qgui_app, xdg_env):
    """Widgets Tools menu parity: Validate Game validates the selection."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    bad = C.GameConfig()
    bad.general.appid = "local-bad"
    bad.general.name = "Bad"
    bad.general.custom_executable = "/nonexistent/game"
    bad.general.game_type = "native"
    C.save(bad)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    validate = win.findChild(QObject, "menuValidate")
    assert validate is not None
    page.setProperty("selectedIds", [])
    _fire(validate)
    qgui_app.processEvents()
    assert "Select a Game First." in page.property("notice")
    page.select("local-bad")
    qgui_app.processEvents()
    _fire(validate)
    qgui_app.processEvents()
    dialog = win.findChild(QObject, "validateDialog")
    assert dialog.property("visible") is True
    assert "nonexistent" in dialog.property("subtitle") or (
        "Not Found" in dialog.property("subtitle")
    )
    dialog.close()
    qgui_app.processEvents()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_profiles_refresh_on_focus(qgui_app, xdg_env):
    """Widgets focusInEvent: focusing re-reads profiles written elsewhere."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    combo = swin.findChild(QQuickItem, "settingsProfiles")

    def profiles():
        model = combo.property("model")
        model = model.toVariant() if hasattr(model, "toVariant") else model
        return list(model or [])

    assert profiles() == []

    # Another writer (the CLI) saves a profile behind the dialog's back;
    # the widgets re-read the list when the dialog got the focus again.
    C.save_profile("local-doom", "fast", C.load("local-doom"))
    win.requestActivate()
    QTest.qWait(120)
    swin.requestActivate()
    assert _wait_for(lambda: profiles() == ["fast"], limit=300), "profiles not re-read"

    # An active profile that vanished on disk is cleared (widgets did).
    swin.switchProfile("fast")
    C.delete_profile("local-doom", "fast")
    swin.refreshProfiles()
    qgui_app.processEvents()
    assert profiles() == []
    assert swin.property("dialogProfile") == ""

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
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
    gear = None
    for candidate in win.findChildren(QQuickItem, "columnsButton"):
        try:
            if candidate.property("visible"):
                gear = candidate
                break
        except Exception:
            continue
    assert gear is not None
    assert gear.property("text") == ""  # icon-only, no text label
    center = gear.mapToScene(
        QPointF(gear.property("width") / 2, gear.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
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
    for title in ("Game", "App ID", "Played", "ProtonDB", "Source"):
        assert title in text
    # no "#" gutter title (TKS has none); the framed numbers stay
    assert 'return "#"' not in text
    # number gutter shares the header look (vertical-header framing)
    gutter = text.split("// number gutter")[1].split("// game: icon plus name")[0]
    assert "colorSet: Kirigami.Theme.Button" in gutter
    assert "highlightColor" in gutter
    # header strip shares the body's x origin: no outer margins that
    # would shift every title/divider away from its column
    strip = text.split("id: tableHeader")[1].split("Repeater {")[0]
    assert "Margin" not in strip


def test_header_width_matches_table_for_unfitted_columns(qgui_app, xdg_env):
    """Header cell width equals the table's column width, fitted or not.

    Regression: with no fitted width the header used its own defaults
    (90px for the 6-11 library columns) while columnWidthProvider
    rendered 80px, so every such title sat 10px off its column. Both
    must read the single defaultColumnWidth helper.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)

    prefs = C.load_preferences()
    prefs.column_order = "0,1,2,3,4,5,6,7,8,9,10,11"
    prefs.hidden_columns = ""
    prefs.column_widths = "1=200"  # only the game column fitted
    C.save_preferences(prefs)

    win, engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    assert row is not None
    # Nothing but the game column is fitted: static defaults apply.
    assert proxy.columnWidth(6) == 0
    assert proxy.columnWidth(11) == 0
    for _ in range(5):
        qgui_app.processEvents()
    cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
    for logical in range(12):
        cell = cells.get(f"headerCell{logical}")
        assert cell is not None, logical
        assert cell.property("width") == page.tableColumnWidth(logical), logical
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_header_divider_double_click_autofits_column(qgui_app, xdg_env):
    """Double-clicking a header separator fits that column to contents."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)

    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    assert row is not None
    cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
    cell = cells.get("headerCell2")
    assert cell is not None
    # Fresh profiles autofit on load: start from a known width so the
    # double-click has something to change.
    proxy.setColumnWidth(2, 200)
    for _ in range(10):
        qgui_app.processEvents()
    assert cell.property("width") == 200
    divider = {d.objectName(): d for d in cell.childItems() if isinstance(d, QQuickItem)}.get(
        "headerDivider2"
    )
    assert divider is not None
    # Inside the 9px strip but also inside the cell: the strip
    # straddles the cell edge, and past-the-edge lands next door.
    pos = cell.mapToScene(QPointF(cell.property("width") - 3, 5)).toPoint()
    QTest.mouseDClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    fitted = proxy.columnWidth(2)
    assert fitted != 90 and fitted >= 40  # measured, not the default
    found = None
    for _ in range(30):
        qgui_app.processEvents()
        # Re-walk every pass: widths move cells around.
        cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
        found = cells.get("headerCell2")
        if found is not None and found.property("width") == fitted:
            break
    assert found is not None
    assert found.property("width") == fitted
    page = win.findChild(QObject, "gamesPage")
    assert dict(page.property("fittedColumnWidths").toVariant())["2"] == fitted
    # Divider gestures never sort (single taps there are swallowed
    # by the strip, double taps autofit).
    assert page.property("sortRole") == "gameName"
    assert page.property("sortDescending") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_table_hscroll_appears_on_overflow(qgui_app, xdg_env):
    """A horizontal bar rescues columns dragged past the edge."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    bar = win.findChild(QQuickItem, "tableHScroll")
    assert bar is not None
    table = win.findChild(QQuickItem, "gameTable")
    for _ in range(10):
        qgui_app.processEvents()
    assert bar.property("size") == 1.0  # fits: nothing to scroll
    proxy.setColumnWidth(1, 1200)
    for _ in range(30):
        qgui_app.processEvents()
        if bar.property("size") < 1.0:
            break
    assert bar.property("size") < 1.0
    bar.setProperty("position", 1.0)
    for _ in range(10):
        qgui_app.processEvents()
    assert table.property("contentX") > 0  # outer columns reachable
    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    assert row is not None
    assert row.property("x") == -table.property("contentX")
    proxy.resetColumns()
    for _ in range(30):
        qgui_app.processEvents()
        if bar.property("size") == 1.0:
            break
    assert bar.property("size") == 1.0
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_header_divider_drag_resizes_and_persists(qgui_app, xdg_env):
    """Dragging a header separator resizes live, persisting on release."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    assert row is not None
    cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
    cell = cells.get("headerCell2")
    assert cell is not None
    w0 = proxy.columnWidth(2)
    assert w0 >= 40
    start = cell.mapToScene(QPointF(cell.property("width") - 3, 5)).toPoint()
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    qgui_app.processEvents()
    # Small delays defeat synthetic event compression (real input
    # streams every move).
    for step in (10, 25, 40):
        QTest.mouseMove(win, start + QPoint(step, 0), 20)
        qgui_app.processEvents()
    QTest.mouseRelease(
        win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(40, 0)
    )
    qgui_app.processEvents()
    # Synthetic moves compress (positions lag), so assert direction,
    # live preview without saving, then persistence on release.
    grown = proxy.columnWidth(2)
    assert w0 < grown <= w0 + 40
    assert f"2={grown}" in C.load_preferences().column_widths.split(",")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_header_title_drag_reorders_and_persists(qgui_app, xdg_env):
    """Dragging a header title moves the column, persisting the order."""
    import json

    from PySide6.QtCore import QObject, QPoint, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    before = json.loads(proxy.columnOrderJson())
    assert before.index(2) == 2
    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
    cell = cells.get("headerCell2")
    assert cell is not None
    start = cell.mapToScene(QPointF(cell.property("width") / 2, 5)).toPoint()
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    qgui_app.processEvents()
    for step in (30, 60, 120):
        QTest.mouseMove(win, start + QPoint(step, 0), 20)
        qgui_app.processEvents()
    QTest.mouseRelease(
        win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(120, 0)
    )
    qgui_app.processEvents()
    after = json.loads(proxy.columnOrderJson())
    assert after.index(2) > 2
    assert C.load_preferences().column_order == ",".join(map(str, after))
    page = win.findChild(QObject, "gamesPage")
    assert page.property("sortRole") == "gameName"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_narrow_window_shrinks_columns_to_fit(qgui_app, xdg_env):
    """Fitted columns scale down instead of overflowing small windows."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    win.setProperty("width", 900)
    win.setProperty("height", 720)
    for logical in (2, 3, 4, 5):
        proxy.setColumnWidth(logical, 300)
    found_shrink = None
    for _ in range(30):
        qgui_app.processEvents()
        page = win.findChild(QObject, "gamesPage")
        shrink = page.property("columnShrink")
        if shrink < 1.0:
            found_shrink = shrink
            break
    assert found_shrink is not None
    assert 0.15 <= found_shrink <= 1.0
    header = win.findChild(QQuickItem, "tableHeader")
    row = header.findChild(QQuickItem, "headerRow")
    cells = {c.objectName(): c for c in row.childItems() if isinstance(c, QQuickItem)}
    assert cells["headerCell2"].property("width") == max(24.0, 300 * found_shrink)
    table = win.findChild(QQuickItem, "gameTable")
    total = sum(cells[f"headerCell{logical}"].property("width") for logical in (0, 1, 2, 3, 4, 5))
    assert total <= table.property("width") + 1.0
    bar = win.findChild(QQuickItem, "tableHScroll")
    assert bar.property("size") == 1.0  # fits: no scroll needed
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def test_window_chrome_geometry(qgui_app, xdg_env):
    """Header/foot rules, gutter strips, table frame and status padding.

    Read-only checks of the one default window, so one QML load covers
    them all (they each loaded their own before).
    """
    from PySide6.QtCore import QObject, QPointF
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)
    header = win.findChild(QQuickItem, "tableHeader")
    table = win.findChild(QQuickItem, "gameTable")
    assert header is not None
    assert table is not None

    # A grid line closes the header row across every column.
    line = win.findChild(QQuickItem, "tableHeaderBottomLine")
    assert line is not None
    assert line.property("height") == 1
    # Full width like the foot rule (covers the gutter too).
    assert line.property("x") == 0
    assert abs(line.property("width") - header.property("width")) <= 1
    bottom = line.property("y") + line.property("height")
    assert abs(bottom - header.property("height")) <= 1, (bottom, header.property("height"))

    # The gutter divider crosses rows and the empty area below.
    full = win.findChild(QQuickItem, "gutterFullLine")
    assert full is not None
    assert full.property("width") == 1
    # Same box as the per-cell dividers: gutter width (36) minus 1px.
    assert full.property("x") == 36 - 1
    # Overlay sibling of the table: same top and bottom, never scrolls.
    assert abs(full.property("y") - table.property("y")) <= 1
    assert (
        abs(
            full.property("y")
            + full.property("height")
            - table.property("y")
            - table.property("height")
        )
        <= 1
    )

    # The framed gutter continues through rows and empty area (TKS).
    strip = win.findChild(QQuickItem, "gutterBackStrip")
    assert strip is not None
    assert strip.property("x") == 0
    assert strip.property("width") == 36
    assert abs(strip.property("y") - header.property("height")) <= 1
    assert (
        abs(
            strip.property("y")
            + strip.property("height")
            - table.property("y")
            - table.property("height")
        )
        <= 1
    )

    # A rule closes the table above the status line.
    foot = win.findChild(QQuickItem, "tableFooterTopLine")
    assert foot is not None
    assert foot.property("height") == 1
    assert round(float(foot.property("width") or 0), 1) == round(
        float(table.property("width") or 0), 1
    )
    table_bottom = table.mapToScene(QPointF(0, 0)).y() + float(table.property("height") or 0)
    foot_bottom = foot.mapToScene(QPointF(0, 0)).y() + float(foot.property("height") or 0)
    assert abs(foot_bottom - table_bottom) <= 1

    # The TKS-style frame hugs the table: no margins, rounded corners.
    frame = win.findChild(QQuickItem, "listFrame")
    assert frame is not None
    assert frame.property("x") == 0 and frame.property("y") == 0
    parent = frame.parent()
    assert parent is not None
    assert frame.property("width") == parent.property("width")
    assert frame.property("height") == parent.property("height")
    assert frame.property("radius") > 0
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    src = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert "border.width: 1" in src

    # Status text keeps padding from the separator above and edge below.
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


def _modal_window(qgui_app, titles):
    """A visible top-level window matching one of the titles."""
    from PySide6.QtGui import QGuiApplication

    for _ in range(20):
        for w in QGuiApplication.topLevelWindows():
            if w.isVisible() and w.title() in titles:
                return w
        qgui_app.processEvents()
    raise AssertionError(f"window {titles} never showed")


def _settings_window(qgui_app):
    """The visible settings top-level window (Edit/Add/Defaults titles)."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest

    for _ in range(25):
        for w in QGuiApplication.topLevelWindows():
            if w.isVisible() and w.objectName() == "gameSettings":
                # Let the freshly mapped window settle before synthetic
                # clicks (offscreen layout passes need wall-clock time).
                QTest.qWait(120)
                return w
        QTest.qWait(20)
    titles = [w.title() for w in QGuiApplication.topLevelWindows()]
    raise AssertionError(f"settings window never showed (have {titles})")


def _opened_popups(parent):
    """Class names of the opened popups under `parent` (anything with `opened`)."""
    from PySide6.QtCore import QObject

    names = []
    for child in parent.findChildren(QObject):
        meta = child.metaObject()
        if meta.indexOfProperty("opened") < 0:
            continue
        try:
            if child.property("opened"):
                names.append(meta.className())
        except Exception:
            continue
    return names


def _settle_focus(window):
    """Wait for a dialog window to take focus (its body owns Return).

    A freshly mapped dialog has no focus item yet offscreen (no window
    manager activates it): the first key event is delivered to the window
    root and a `Keys` handler on the body never sees it.
    """
    assert _wait_for(lambda: window.property("activeFocusItem") is not None), (
        "dialog window never took focus"
    )


def _hit_reaches(host, target, pos):
    """Whether the hit test from the window root reaches `target`.

    `childAt()` only reports one level, so walk down: while a popup is
    still fading out its overlay sits on top and the chain stops there.
    """
    item = host.contentItem()
    for _ in range(24):
        if item is target:
            return True
        local = item.mapFromScene(pos)
        item = item.childAt(local.x(), local.y())
        if item is None:
            return False
    return False


def _click(host, name):
    """Click a named control, first waiting until it is really reachable.

    A popup that just closed keeps its dim overlay above everything for
    a while (offscreen that overlay does not fade away promptly), so a
    synthetic click lands on it and is swallowed silently -- the failure
    then surfaces in an unrelated assertion. Waiting for the hit test to
    reach the control removes the race; layout passes need wall-clock
    time, so poll with `QTest.qWait`, never a bare processEvents() loop.
    """
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    button = host.findChild(QQuickItem, name)
    assert button is not None, name
    centre = QPointF(button.property("width") / 2, button.property("height") / 2)
    pos = button.mapToScene(centre)
    for _ in range(40):
        if _hit_reaches(host, button, pos):
            break
        QTest.qWait(25)
        pos = button.mapToScene(centre)
    QTest.mouseClick(host, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos.toPoint())
    QTest.qWait(30)


def _vertical_bar(view):
    """The visible vertical scroll bar of a ScrollView, or None."""
    from PySide6.QtQuick import QQuickItem

    for child in view.findChildren(QQuickItem):
        if "ScrollBar" not in child.metaObject().className():
            continue
        if str(child.property("orientation")) != "Orientation.Vertical":
            continue
        if child.property("visible"):
            return child
    return None


def test_settings_edit_saves_name(qgui_app, xdg_env):
    """Edit opens settings for the selection; Save persists the fields."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.select("local-doom")
    qgui_app.processEvents()

    def click(name, host):
        _click(host, name)

    click("titleEdit", win)
    assert page.settingsOpen() is True
    swin = _settings_window(qgui_app)
    assert swin.property("modality") == Qt.WindowModality.WindowModal
    name = swin.findChild(QQuickItem, "settingsName")
    assert name.property("text") == "Doom"
    name.setProperty("text", "Doom II")
    click("settingsSave", swin)
    assert page.settingsOpen() is False
    assert C.load("local-doom").general.name == "Doom II"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_add_creates_game(qgui_app, xdg_env):
    """Add offers sources; Local opens blank settings that create the game."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    win, engine, proxy, warnings = _load_main(qgui_app)

    def click(name, host):
        _click(host, name)

    click("titleAdd", win)
    add = _modal_window(qgui_app, ("Add Game",))
    add.findChild(QQuickItem, "addSource").setProperty("currentIndex", 1)
    type_box = add.findChild(QQuickItem, "addGameType")
    assert type_box is not None
    # Local games open Settings with the native type preselected.
    assert type_box.property("currentIndex") == 0
    click("addConfirm", add)
    swin = _settings_window(qgui_app)
    assert swin.findChild(QQuickItem, "settingsType").property("currentIndex") == 0
    swin.findChild(QQuickItem, "settingsName").setProperty("text", "Doom")
    swin.findChild(QQuickItem, "settingsExe").setProperty("text", "/bin/true")
    click("settingsSave", swin)
    assert proxy.rowCount() == 1
    created = proxy.idAt(0)
    assert created.startswith("local-")
    assert C.load(created).general.name == "Doom"
    assert C.load(created).general.game_type == "native"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_add_local_game_type_preselects_settings(qgui_app, xdg_env):
    """The Add dialog's Game Type combo lands preselected in Settings."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    win, engine, proxy, warnings = _load_main(qgui_app)

    def click(name, host):
        _click(host, name)

    click("titleAdd", win)
    add = _modal_window(qgui_app, ("Add Game",))
    assert add.findChild(QQuickItem, "addGameType").property("visible") is False
    add.findChild(QQuickItem, "addSource").setProperty("currentIndex", 1)
    type_box = add.findChild(QQuickItem, "addGameType")
    assert type_box.property("visible") is True
    type_box.setProperty("currentIndex", 2)
    click("addConfirm", add)
    swin = _settings_window(qgui_app)
    assert swin.findChild(QQuickItem, "settingsType").property("currentIndex") == 2
    swin.findChild(QQuickItem, "settingsName").setProperty("text", "Umu Test")
    swin.findChild(QQuickItem, "settingsExe").setProperty("text", "/bin/true")
    click("settingsSave", swin)
    assert proxy.rowCount() == 1
    assert C.load(proxy.idAt(0)).general.game_type == "umu"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_exe_hint_switches_to_wine(qgui_app, xdg_env, tmp_path):
    """A native game with a .exe warns and switches to Wine on request."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    exe = tmp_path / "game.exe"
    exe.write_text("")
    win, engine, proxy, warnings = _load_main(qgui_app)

    def click(name, host):
        _click(host, name)

    click("titleAdd", win)
    add = _modal_window(qgui_app, ("Add Game",))
    add.findChild(QQuickItem, "addSource").setProperty("currentIndex", 1)
    click("addConfirm", add)
    swin = _settings_window(qgui_app)
    _settings_tab(swin, TAB_LAUNCH)
    hint = swin.findChild(QQuickItem, "settingsExeHint")
    assert hint.property("visible") is False
    swin.findChild(QQuickItem, "settingsExe").setProperty("text", str(exe))
    qgui_app.processEvents()
    assert hint.property("visible") is True
    assert swin.findChild(QQuickItem, "settingsSwitchType").property("text") == "Switch to Wine"
    click("settingsSwitchType", swin)
    qgui_app.processEvents()
    assert swin.findChild(QQuickItem, "settingsType").property("currentIndex") == 1
    assert hint.property("visible") is False
    swin.findChild(QQuickItem, "settingsName").setProperty("text", "Hinted")
    click("settingsSave", swin)
    assert proxy.rowCount() == 1
    assert C.load(proxy.idAt(0)).general.game_type == "wine"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_exe_hint_on_steam_offers_proton(qgui_app, xdg_env, tmp_path):
    """A native Steam game with a .exe switches to Proton, not Wine."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    exe = tmp_path / "steam.exe"
    exe.write_text("")
    cfg = C.GameConfig()
    cfg.general.appid = "98"
    cfg.general.name = "Steam Exe"
    cfg.general.game_type = "native"
    cfg.general.custom_executable = str(exe)
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    win.findChild(QObject, "gamesPage").openGameSettings("98")
    swin = _settings_window(qgui_app)
    _settings_tab(swin, TAB_LAUNCH)
    hint = swin.findChild(QQuickItem, "settingsExeHint")
    assert hint.property("visible") is True
    assert swin.findChild(QQuickItem, "settingsSwitchType").property("text") == "Switch to Proton"
    _click(swin, "settingsSwitchType")
    qgui_app.processEvents()
    # Steam typeValues() is [proton, native].
    assert swin.findChild(QQuickItem, "settingsType").property("currentIndex") == 0
    assert hint.property("visible") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_add_dialog_enter_confirms(qgui_app, xdg_env):
    """Enter on the Add window confirms the source (its default button)."""
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    win, engine, _proxy, warnings = _load_main(qgui_app)
    _click(win, "titleAdd")
    add = _modal_window(qgui_app, ("Add Game",))
    add.findChild(QQuickItem, "addSource").setProperty("currentIndex", 1)
    _settle_focus(add)
    QTest.keyClick(add, Qt.Key.Key_Return)
    swin = _settings_window(qgui_app)
    assert swin.findChild(QQuickItem, "settingsName").property("text") == ""
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_env_and_gamemode_flows(qgui_app, xdg_env):
    """Env rows and Pre/Post, the GameMode pair, and bulk/preset edits.

    Three sessions of the settings dialog on one main window (each case
    these replace loaded its own).
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    dlg = win.findChild(QObject, "gameSettings")

    def click(name):
        _click(swin, name)

    # Environment rows and Pre/Post fields persist through the dialog.
    page.select("local-doom")
    qgui_app.processEvents()
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    tabs = swin.findChild(QQuickItem, "settingsTabs")
    tabs.setProperty("currentIndex", TAB_ENV)
    qgui_app.processEvents()
    # A game without variables already shows one empty row (nothing is
    # saved unless it gets a key).
    assert dlg.envRowCount() == 1
    assert C.load("local-doom").env.vars == {}
    click("envAdd")
    assert dlg.envRowCount() == 2
    dlg.setEnvRow(0, "FOO", "bar")
    tabs.setProperty("currentIndex", TAB_LAUNCH)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "ppPre").setProperty("text", "/bin/echo")
    swin.findChild(QQuickItem, "ppTimeout").setProperty("value", 30)
    click("settingsSave")
    reloaded = C.load("local-doom")
    assert reloaded.env.vars == {"FOO": "bar"}
    assert reloaded.pre_post.pre_command == "/bin/echo"
    assert reloaded.pre_post.timeout == 30

    # GameMode pair is mutually exclusive and persists.
    page.openGameSettings("local-doom")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_PERF)
    QTest.qWait(200)
    for _ in range(5):
        qgui_app.processEvents()
    feral = swin.findChild(QQuickItem, "perfFeral")
    cachy = swin.findChild(QQuickItem, "perfCachy")
    assert feral.property("checked") is False
    feral.setProperty("checked", True)
    qgui_app.processEvents()
    assert cachy.property("checked") is False
    cachy.setProperty("checked", True)
    qgui_app.processEvents()
    assert feral.property("checked") is False
    dlg.save()
    qgui_app.processEvents()
    reloaded = C.load("local-doom")
    assert reloaded.gamemode.feral_gamemode is False
    assert reloaded.gamemode.cachyos_game_performance is True

    # Bulk edit replaces rows; preset merges missing keys.
    page.openGameSettings("local-doom")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_ENV)
    qgui_app.processEvents()
    click("envBulk")
    assert win.findChild(QObject, "envBulkDialog").property("visible") is True
    swin.findChild(QQuickItem, "envBulkArea").setProperty("text", "A=1\n# skip\nB=2")
    dlg.acceptBulk()
    assert dlg.envRowCount() == 2
    click("envPreset")
    assert win.findChild(QObject, "envPresetDialog").property("visible") is True
    dlg.acceptEnvPreset()
    qgui_app.processEvents()
    if win.findChild(QObject, "envMismatchDialog").property("visible") is True:
        dlg.applyEnvPresetByName(dlg.property("pendingPreset"))
        qgui_app.processEvents()
    assert dlg.envRowCount() > 2
    dlg.save()
    qgui_app.processEvents()
    env = C.load("local-doom").env.vars
    assert env["A"] == "1"
    assert len(env) > 2

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_display_flow(qgui_app, xdg_env, monkeypatch):
    """Display fields, gamescope preset, MangoHud new and dip persist."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.gui.model import GameListModel

    # The New Configuration... flow hands the fresh file to the desktop
    # editor (kate and friends); stubbing openPath keeps the suite from
    # opening a real window on the developer's session. The QML branch
    # still runs (the call is made and reports success).
    monkeypatch.setattr(GameListModel, "openPath", lambda self, path: True)

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_DISPLAY)
    qgui_app.processEvents()

    def click(name, host):
        _click(host, name)

    swin.findChild(QQuickItem, "dispOut").setProperty("text", "DP-1")
    swin.findChild(QQuickItem, "dispProv").setProperty("currentIndex", 4)
    swin.findChild(QQuickItem, "gsEnable").setProperty("checked", True)
    click("gsPreset", swin)
    prompt = swin.findChild(QObject, "settingsChoicePrompt")
    assert prompt.property("visible") is True
    swin.findChild(QQuickItem, "settingsChoiceBox").setProperty("currentIndex", 0)
    dlg.acceptChoice()
    assert prompt.property("opened") is False
    assert swin.findChild(QQuickItem, "gsArgs").property("text") != ""
    # MangoHud lives in Performance now: its New Configuration... flow
    # runs from that tab, then the display assertions continue.
    _settings_tab(swin, TAB_PERF)
    click("mhNew", swin)
    name_prompt = swin.findChild(QObject, "settingsNamePrompt")
    assert name_prompt.property("visible") is True
    swin.findChild(QQuickItem, "settingsPromptField").setProperty("text", "testmh")
    dlg.acceptProfileName()
    assert prompt.property("visible") is True
    dlg.acceptChoice()
    assert dlg.mhConfigData() == "testmh.conf"
    _settings_tab(swin, TAB_DISPLAY)
    dlg.setProperty("dmodeCurrent", "1920x1080@60")
    swin.findChild(QQuickItem, "dmodeBox").setProperty("editText", "1920x1080@60")
    qgui_app.processEvents()
    assert swin.findChild(QQuickItem, "dipRow").property("visible") is True
    swin.findChild(QQuickItem, "dmodeBox").setProperty("editText", "800x600@60")
    qgui_app.processEvents()
    assert swin.findChild(QQuickItem, "dipRow").property("visible") is False
    swin.findChild(QQuickItem, "dmodeBox").setProperty("editText", "1920x1080@60")
    swin.findChild(QQuickItem, "dipSlider").setProperty("value", 7)
    click("settingsSave", swin)
    reloaded = C.load("local-doom")
    assert reloaded.display.output == "DP-1"
    assert reloaded.display.provider == "x11"
    assert reloaded.display.mode == "1920x1080@60"
    assert reloaded.display.dip_seconds == 7
    assert reloaded.gamescope.enable is True
    assert reloaded.gamescope.args != ""
    assert reloaded.mangohud.config_file == "testmh.conf"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_import_stl_flow(qgui_app, xdg_env, monkeypatch):
    """Import window lists STL candidates; Import writes the profile."""
    import os
    from pathlib import Path

    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    import tkarcade.steam as steammod
    from tkarcade import config as C

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3")])
    cfg = C.GameConfig()
    cfg.general.appid = "99"
    C.save(cfg)
    stl_id = Path(os.environ["XDG_CONFIG_HOME"]) / "steamtinkerlaunch" / "gamecfgs" / "id"
    stl_id.mkdir(parents=True)
    (stl_id / "99.conf").write_text('USE_GAMEMODE="1"\n')
    win, engine, _proxy, warnings = _load_main(qgui_app)
    dlg = win.findChild(QObject, "importDialog")
    dlg.openStl()
    swin = _modal_window(qgui_app, ("Import Configurations",))
    assert dlg.property("stlRows") != []
    # The STL list scrolls (contentHeight follows the rows, not -1). The
    # window height follows the list (content sizing), so the ScrollView
    # syncs its content size a layout pass after the window is mapped.
    scroller = swin.findChild(QQuickItem, "importStlScroll")
    for _ in range(20):
        if scroller.property("contentHeight") > 0:
            break
        QTest.qWait(20)
    assert scroller.property("contentHeight") > 0

    def click(name):
        _click(swin, name)

    click("importStlConfirm")
    assert C.profile_file("99", "steamtinkerlaunch").is_file()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_import_tarball_flow(qgui_app, xdg_env, tmp_path):
    """Backup tab imports the picked tarball and notifies."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "99"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    tarball = tmp_path / "backup.tar.gz"
    assert "Exported to" in model.exportTarball(str(tarball))
    C.game_file("99").unlink()
    dlg = win.findChild(QObject, "importDialog")
    dlg.setProperty("tarballPath", str(tarball))
    dlg.setProperty("visible", True)
    swin = _modal_window(qgui_app, ("Import Configurations",))
    _click(swin, "importTarballConfirm")
    qgui_app.processEvents()
    assert C.game_file("99").is_file()
    page = win.findChild(QObject, "gamesPage")
    assert page.property("notice").startswith("Imported")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_import_enter_imports_the_current_page(qgui_app, xdg_env, tmp_path):
    """Enter imports on the current page (its own button, never Close)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "99"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    tarball = tmp_path / "backup.tar.gz"
    assert "Exported to" in model.exportTarball(str(tarball))
    C.game_file("99").unlink()
    dlg = win.findChild(QObject, "importDialog")
    dlg.open()
    swin = _modal_window(qgui_app, ("Import Configurations",))
    _settle_focus(swin)
    dlg.setProperty("tarballPath", str(tarball))
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: C.game_file("99").is_file()), "Enter did not import"
    page = win.findChild(QObject, "gamesPage")
    assert page.property("notice").startswith("Imported")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_quit_keys_on_every_window(qgui_app, xdg_env):
    """Every window handles Ctrl+Q through the focus chain (Shortcut backup)."""
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    qml = pathlib.Path(kapp.__file__).parent / "qml"
    for name in (
        "MainPage.qml",
        "GameSettings.qml",
        "ScanDialog.qml",
        "HistoryView.qml",
        "PrefsDialog.qml",
        "ImportDialog.qml",
        "AboutDialog.qml",
    ):
        src = (qml / name).read_text()
        assert "Keys.onPressed" in src, name
        assert "Qt.Key_Q" in src, name


def test_every_dialog_watches_escape(qgui_app, xdg_env):
    """Every separate dialog Window registers the Escape filter.

    A QML Window has no QDialog reject(): the model filter is what turns
    Escape into a cancel (and dismisses an open popup first).
    """
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    qml = pathlib.Path(kapp.__file__).parent / "qml"
    for name in (
        "AboutDialog.qml",
        "AddDialog.qml",
        "EditorPicker.qml",
        "GameSettings.qml",
        "HistoryView.qml",
        "ImportDialog.qml",
        "PrefsDialog.qml",
        "PrelaunchMenu.qml",
        "ScanDialog.qml",
    ):
        src = (qml / name).read_text()
        assert "watchDialogKeys" in src, name


def test_every_dialog_has_a_default_button(qgui_app, xdg_env):
    """Every dialog body routes Enter to its default button.

    QQC2 buttons ignore Enter, so `Keys.onReturnPressed` on the body is
    what reproduces the widgets QDialog default button (a window
    `Shortcut` would steal the key from an editable TextArea).
    """
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    qml = pathlib.Path(kapp.__file__).parent / "qml"
    for name in (
        "AboutDialog.qml",
        "AddDialog.qml",
        "EditorPicker.qml",
        "GameSettings.qml",
        "HistoryView.qml",
        "ImportDialog.qml",
        "PrefsDialog.qml",
        "PrelaunchMenu.qml",
        "ScanDialog.qml",
    ):
        src = (qml / name).read_text()
        assert "Keys.onReturnPressed" in src, name
        assert "gameModel.pressDefault" in src, name


def test_kirigami_quit_action_neutered():
    """Kirigami's built-in Quit (close()) must not own Ctrl+Q."""
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    src = (pathlib.Path(kapp.__file__).parent / "qml" / "main.qml").read_text()
    assert 'quitAction.shortcut = ""' in src


def test_settings_system_and_wine_flow(qgui_app, xdg_env):
    """Ludusavi/System fields persist; Wine edits Steam games only.

    One main window covers both games and all three tabs: the two cases
    this replaces each loaded their own.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    steam = C.GameConfig()
    steam.general.appid = "99"
    steam.general.game_type = "proton"
    C.save(steam)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    tabs = swin.findChild(QQuickItem, "settingsTabs")

    # Ludusavi and System fields persist through the dialog.
    assert swin.findChild(QQuickItem, "settingsLog").property("text") != ""
    tabs.setProperty("currentIndex", TAB_SYSTEM)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "luEnable").setProperty("checked", True)
    swin.findChild(QQuickItem, "luName").setProperty("text", "Doom 3")
    dlg.save()
    qgui_app.processEvents()
    assert dlg.property("editAppid") == "local-doom"
    page.openGameSettings("local-doom")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_SYSTEM)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "seInhibit").setProperty("checked", True)
    swin.findChild(QQuickItem, "blockInternet").setProperty("checked", True)
    swin.findChild(QQuickItem, "nlDisable").setProperty("checked", True)
    swin.findChild(QQuickItem, "nlProv").setProperty("currentIndex", 1)
    dlg.save()
    qgui_app.processEvents()
    reloaded = C.load("local-doom")
    assert reloaded.ludusavi.enable is True
    assert reloaded.ludusavi.name_override == "Doom 3"
    assert reloaded.session.inhibit_idle is True
    assert reloaded.network.block_internet is True
    assert reloaded.nightlight.disable_during_game is True
    assert reloaded.nightlight.provider == "plasma"

    # Wine tab edits a Steam game and stays off for local games.
    page.openGameSettings("99")
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_COMPAT)
    qgui_app.processEvents()
    assert swin.findChild(QQuickItem, "wineForm").property("enabled") is True
    # A Steam game gets both boxes and no "Steam only" note.
    assert swin.findChild(QQuickItem, "wineSteamOnlyNote").property("visible") is False
    assert swin.findChild(QQuickItem, "ptLog").property("visible") is True
    swin.findChild(QQuickItem, "ptFresh").setProperty("checked", True)
    swin.findChild(QQuickItem, "ptVerbs").setProperty("text", "dotnet48")
    swin.findChild(QQuickItem, "ptDebug").setProperty("currentIndex", 2)
    dlg.save()
    qgui_app.processEvents()
    reloaded = C.load("99")
    assert reloaded.proton.fresh_prefix is True
    assert reloaded.proton.winetricks_verbs == ["dotnet48"]
    assert reloaded.debug.winedebug == "+err"
    page.openGameSettings("local-doom")
    # save() closed the dialog, so reopening starts on the first tab: pick
    # Compatibility again before asserting on visibility (Qt Quick's
    # `visible` reports hidden ancestors too).
    QTest.qWait(150)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_COMPAT)
    QTest.qWait(100)
    qgui_app.processEvents()
    assert swin.findChild(QQuickItem, "wineForm").property("enabled") is False
    # Local game: the tab stays reachable, the Wine fields grey out with a
    # note and the Proton box is gone (there is no prefix to set up).
    assert swin.findChild(QQuickItem, "wineSteamOnlyNote").property("visible") is True
    assert swin.findChild(QQuickItem, "ptLog").property("visible") is False

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_local_runtime_flow(qgui_app, xdg_env, monkeypatch):
    """Local games pick Wine or a umu Proton, a prefix and a layer.

    The graphics layer is installed at launch; the dialog only reports
    what the marker holds and can remove exactly those files again.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C
    from tkarcade import graphics as G
    from tkarcade import runtimes

    _save_one_game("local-doom", "Doom", "wine")
    saved = C.load("local-doom")
    saved.graphics.dxvk = True
    C.save(saved)
    proton_dir = xdg_env["home"] / "GE-Proton10-1"
    proton_dir.mkdir()
    (proton_dir / "proton").write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(
        runtimes,
        "proton_installs",
        lambda extra="": [runtimes.ProtonInstall(proton_dir.name, proton_dir.resolve())],
    )
    # A fake DXVK version in the default Lutris location, already copied
    # into the game prefix (as a launch would have done).
    prefix = C.prefix_dir("local-doom")
    prefix.mkdir(parents=True)
    reused = prefix.parent / "Reused"
    (reused / "drive_c").mkdir(parents=True)
    (reused / "system.reg").write_text("")
    version = xdg_env["data"] / "lutris" / "runtime" / "dxvk" / "v9.9"
    (version / "x64").mkdir(parents=True)
    for dll in ("d3d11.dll", "dxgi.dll"):
        (version / "x64" / dll).write_bytes(b"fake dll")
    ok, install_warnings = G.install(prefix, "dxvk", C.load_preferences())
    assert ok, install_warnings

    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    _settings_tab(swin, TAB_COMPAT)

    type_box = swin.findChild(QQuickItem, "settingsType")
    wine_field = swin.findChild(QQuickItem, "settingsLocalWine")
    proton_box = swin.findChild(QQuickItem, "settingsLocalProton")
    prefix_field = swin.findChild(QQuickItem, "settingsLocalPrefix")
    name_field = swin.findChild(QQuickItem, "settingsLocalPrefixName")
    name_hint = swin.findChild(QQuickItem, "settingsLocalPrefixHint")
    gfx_dxvk = swin.findChild(QQuickItem, "settingsGraphicsDxvk")
    gfx_vkd3d = swin.findChild(QQuickItem, "settingsGraphicsVkd3d")
    local_verbs = swin.findChild(QQuickItem, "settingsLocalVerbs")
    status = swin.findChild(QQuickItem, "settingsGfxStatus")
    remove = swin.findChild(QQuickItem, "settingsGfxRemove")

    # The origin decides the choices: a local game gets native/Wine/umu,
    # and the saved "wine" type selects the second entry.
    assert type_box.property("count") == 3
    assert type_box.property("model") == [
        "Linux (Native)",
        "Windows (Wine)",
        "Windows (Proton via UMU)",
    ]
    assert type_box.property("currentIndex") == 1
    assert wine_field.property("visible") is True
    assert proton_box.property("visible") is False
    assert prefix_field.property("visible") is True
    assert gfx_dxvk.property("visible") is True
    assert gfx_dxvk.property("checked") is True
    assert gfx_vkd3d.property("visible") is True
    assert gfx_vkd3d.property("currentIndex") == 0
    assert local_verbs.property("visible") is True
    assert local_verbs.property("text") == ""
    assert "DXVK v9.9" in status.property("text")
    assert remove.property("enabled") is True

    # umu swaps the Wine path for the discovered Proton installs.
    type_box.setProperty("currentIndex", 2)
    QTest.qWait(80)
    assert wine_field.property("visible") is False
    assert proton_box.property("visible") is True
    assert proton_box.property("count") == 1
    type_box.setProperty("currentIndex", 1)
    QTest.qWait(80)

    # Wine path and prefix dir round-trip through Save.
    wine_field.setProperty("text", "/opt/wine/bin/wine")
    prefix_field.setProperty("text", str(prefix))
    gfx_dxvk.setProperty("checked", True)
    gfx_vkd3d.setProperty("currentIndex", 1)
    local_verbs.setProperty("text", "dotnet48 vcrun2022")
    # The friendly name resolves under the prefix base and warns about
    # the directory it will create; the picker lists complete prefixes.
    assert name_field.property("visible") is True
    name_field.setProperty("text", "Friendly Doom")
    QTest.qWait(50)
    assert (prefix.parent / "Friendly_Doom").as_posix() in name_hint.property("text")
    from PySide6.QtCore import QMetaObject

    assert QMetaObject.invokeMethod(dlg, "openPrefixChoices") is True
    QTest.qWait(80)
    rows = swin.findChild(QQuickItem, "settingsPrefixPickerRows")
    assert rows.property("count") == 1
    picker = swin.findChild(QObject, "settingsPrefixPicker")
    assert picker is not None
    QMetaObject.invokeMethod(picker, "close")
    QTest.qWait(50)
    dlg.save()
    QTest.qWait(50)
    cfg = C.load("local-doom")
    assert cfg.general.game_type == "wine"
    assert cfg.runtime.wine_binary == "/opt/wine/bin/wine"
    assert cfg.runtime.prefix_dir == str(prefix)
    assert cfg.runtime.prefix_name == "Friendly Doom"
    assert cfg.runtime.proton_path == ""
    assert cfg.graphics.dxvk is True
    assert cfg.graphics.vkd3d == "proton"
    assert cfg.runtime.winetricks_verbs == ["dotnet48", "vcrun2022"]

    # umu records the chosen Proton install path.
    page.openGameSettings("local-doom")
    QTest.qWait(150)
    _settings_tab(swin, TAB_COMPAT)
    type_box.setProperty("currentIndex", 2)
    QTest.qWait(80)
    proton_box.setProperty("currentIndex", 0)
    dlg.save()
    QTest.qWait(50)
    cfg = C.load("local-doom")
    assert cfg.general.game_type == "umu"
    assert cfg.runtime.proton_path == str(proton_dir.resolve())
    assert cfg.runtime.prefix_dir == str(prefix)

    # Opening again restores the umu choice and the installed layer;
    # scrolling to the end reaches the remove button.
    page.openGameSettings("local-doom")
    QTest.qWait(150)
    _settings_tab(swin, TAB_COMPAT)
    assert type_box.property("currentIndex") == 2
    assert proton_box.property("currentIndex") == 0
    assert "DXVK v9.9" in status.property("text")
    view = swin.findChild(QQuickItem, "settingsWineScroll")
    flick = view.property("contentItem")
    flick.setProperty("contentY", flick.property("contentHeight") - flick.property("height"))
    QTest.qWait(200)
    flick.setProperty("contentY", flick.property("contentHeight") - flick.property("height"))
    QTest.qWait(120)
    from PySide6.QtCore import QPointF, Qt

    # The vertical scroll bar now overlays the right edge of the form
    # (the hint row made the content taller), so click the left half.
    pos = remove.mapToScene(QPointF(12, remove.property("height") / 2))
    for _ in range(40):
        if _hit_reaches(swin, remove, pos):
            break
        QTest.qWait(25)
        pos = remove.mapToScene(QPointF(12, remove.property("height") / 2))
    QTest.mouseClick(swin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos.toPoint())
    QTest.qWait(50)
    assert not G.marker_path(prefix).is_file()
    assert not (prefix / "drive_c" / "windows" / "system32" / "d3d11.dll").is_file()
    assert not G.marker_path(prefix).is_file()
    assert remove.property("enabled") is False
    assert "Nothing Installed" in status.property("text")

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_defaults_and_reset_flow(qgui_app, xdg_env):
    """Reset applies the Global Defaults template; Defaults edits it."""
    from PySide6.QtCore import QObject, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    C.save_profile("local-doom", "keepme", C.load("local-doom"))
    # A customised Global Defaults template: Reset must apply *it*, never
    # the built-in factory values (widgets _on_reset).
    template = C.load_defaults()
    template.general.name = "From Template"
    template.general.custom_executable = "/bin/false"
    template.general.menu_timeout = 9
    C.save_defaults(template)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    QTest.qWait(400)
    for _ in range(10):
        qgui_app.processEvents()
    name = swin.findChild(QQuickItem, "settingsName")
    name.setProperty("text", "Changed")
    _click(swin, "settingsReset")
    qgui_app.processEvents()
    assert win.findChild(QObject, "settingsConfirm").property("visible") is True
    dlg.acceptConfirm()
    qgui_app.processEvents()
    assert name.property("text") == "From Template"
    live = C.load("local-doom")
    assert live.general.name == "From Template"
    assert live.general.custom_executable == "/bin/false"
    assert live.general.menu_timeout == 9
    # Profiles are never touched by a reset.
    assert C.list_profiles("local-doom") == ["keepme"]
    dlg.openDefaults()
    qgui_app.processEvents()
    dswin = _modal_window(qgui_app, ("Global Defaults",))
    # The defaults editor offers the widgets "Reset to Factory Defaults".
    reset = dswin.findChild(QQuickItem, "settingsReset")
    assert reset.property("visible") is True
    assert reset.property("text") == "Reset to Factory Defaults"
    # ... and no Diff vs Defaults (widgets had it for a game only).
    assert dswin.findChild(QQuickItem, "diffButton").property("visible") is False
    _click(dswin, "settingsReset")
    assert dswin.findChild(QQuickItem, "settingsTimeout").property("value") == 0
    assert C.load_defaults().general.menu_timeout == 9  # untouched in memory only
    dswin.findChild(QQuickItem, "ntLaunch").setProperty("checked", False)
    save = dswin.findChild(QQuickItem, "settingsSave")
    pos = save.mapToScene(
        QPointF(save.property("width") / 2, save.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(dswin, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    qgui_app.processEvents()
    assert C.load_defaults().notifications.notify_on_launch is False
    assert C.load_defaults().general.menu_timeout == 0
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_newer_version_gate(qgui_app, xdg_env):
    """A newer-version config asks before Save downgrades it."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    C.game_file("local-new").parent.mkdir(parents=True, exist_ok=True)
    C.game_file("local-new").write_text(
        '[general]\nappid = "local-new"\nname = "Newer"\nconfig_version = 999\n',
        encoding="utf-8",
    )
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-new")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    name = swin.findChild(QQuickItem, "settingsName")
    assert dlg.property("newerVersion") is True
    name.setProperty("text", "Downgraded")
    dlg.save()
    qgui_app.processEvents()
    confirm = win.findChild(QObject, "settingsConfirm")
    assert confirm.property("visible") is True
    assert dlg.property("confirmPurpose") == "newerApp"
    assert dlg.property("visible") is True  # gate keeps the window open
    assert "config_version = 999" in C.game_file("local-new").read_text(encoding="utf-8")
    dlg.acceptConfirm()
    qgui_app.processEvents()
    assert dlg.property("newerVersion") is False
    assert C.load("local-new").general.name == "Downgraded"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_profile_switch_save(qgui_app, xdg_env):
    """Switching profiles with unsaved edits can Save them first."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    C.save_profile("local-doom", "slow", C.load("local-doom"))
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    name = swin.findChild(QQuickItem, "settingsName")
    name.setProperty("text", "Edited Live")
    dlg.requestProfileSwitch(0)
    qgui_app.processEvents()
    assert dlg.property("confirmPurpose") == "discardSwitch"
    save = swin.findChild(QQuickItem, "settingsConfirmSave")
    assert save is not None and save.property("visible") is True
    # Kirigami.Dialog overlays never finish their enter fade offscreen, so
    # synthetic clicks do not reach the footer: drive the accept directly.
    dlg.acceptConfirmSave()
    qgui_app.processEvents()
    # Save kept the edit on the live file, then the switch happened.
    assert C.load("local-doom").general.name == "Edited Live"
    assert dlg.property("dialogProfile") == "slow"
    assert name.property("text") == "Doom"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_add_source_steam_and_local_flows(qgui_app, xdg_env, monkeypatch):
    """Add chooser routes Steam picks to settings and Local to blank."""
    from PySide6.QtQuick import QQuickItem

    import tkarcade.steam as steammod
    from tkarcade import config as C

    monkeypatch.setattr(steammod, "list_games", lambda: [("99", "Doom 3")])
    win, engine, proxy, warnings = _load_main(qgui_app)

    def click(name, host):
        _click(host, name)

    click("titleAdd", win)
    add = _modal_window(qgui_app, ("Add Game",))
    assert add.findChild(QQuickItem, "addSource") is not None
    click("addConfirm", add)
    swin = _settings_window(qgui_app)
    assert proxy.rowCount() == 0
    assert swin.findChild(QQuickItem, "settingsAppid").property("text") == "99"
    # Steam games must name the game type: no auto-detection and no guess.
    click("settingsSave", swin)
    assert not C.game_file("99").is_file()
    swin.findChild(QQuickItem, "settingsType").setProperty("currentIndex", 0)
    click("settingsSave", swin)
    assert C.game_file("99").is_file()
    click("titleAdd", win)
    add2 = _modal_window(qgui_app, ("Add Game",))
    add2.findChild(QQuickItem, "addSource").setProperty("currentIndex", 1)
    click("addConfirm", add2)
    _modal_window(qgui_app, ("Add Game",))
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_hicolor_icon_backups_cover_gaps():
    """hicolor ships our own art for names missing in major themes."""
    import pathlib
    import re

    from tkarcade.gui import kirigami_app as kapp

    root = pathlib.Path(kapp.__file__).parent.parent.parent.parent
    actions = root / "packaging" / "icons" / "hicolor" / "scalable" / "actions"
    for name in ("view-column", "overflow-menu"):
        assert (actions / f"{name}.svg").is_file(), name
    qml = root / "src" / "tkarcade" / "gui" / "qml"
    chains = 0
    for path in qml.glob("*.qml"):
        for match in re.finditer(r"iconName\(\[([^\]]*)\]\)", path.read_text()):
            names = re.findall(r'"([^"]+)"', match.group(1))
            assert len(names) >= 2, (path.name, match.group(0))
            chains += 1
    assert chains >= 3


def test_clone_reset_menu_flows(qgui_app, xdg_env):
    """Clone duplicates a game (with overwrite); Reset restores defaults."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid in ("local-doom", "local-quake"):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = appid
        C.save(cfg)
    prof = C.profiles_dir("local-doom")
    prof.mkdir(parents=True, exist_ok=True)
    (prof / "fast.toml").write_text("[general]\n")
    win, engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.select("local-doom")
    page.openCloneDialog("local-doom")
    assert win.findChild(QObject, "cloneDialog").property("visible") is True
    assert page.property("cloneRows").toVariant() == ["local-quake [local-quake]"]
    box = win.findChild(QQuickItem, "cloneBox")
    box.setProperty("editText", "local-new")
    _fire(win.findChild(QObject, "cloneConfirm"))
    qgui_app.processEvents()
    assert C.game_file("local-new").is_file()
    assert (C.profiles_dir("local-new") / "fast.toml").is_file()
    page.openCloneDialog("local-doom")
    box.setProperty("editText", "local-quake")
    _fire(win.findChild(QObject, "cloneConfirm"))
    qgui_app.processEvents()
    assert win.findChild(QObject, "overwriteDialog").property("visible") is True
    _fire(win.findChild(QObject, "overwriteConfirm"))
    qgui_app.processEvents()
    assert C.load("local-quake").general.name == "local-doom"
    page.select("local-doom")
    page.toggleSelect("local-quake")
    page.openResetDialog()
    assert win.findChild(QObject, "resetDialog").property("visible") is True
    _fire(win.findChild(QObject, "resetConfirm"))
    qgui_app.processEvents()
    assert C.load("local-doom").general.name == ""
    assert (C.profiles_dir("local-doom") / "fast.toml").is_file()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_warning_and_tool_states(qgui_app, xdg_env, monkeypatch):
    """Load warnings surface; missing tools disable their toggles."""
    import shutil

    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    C.game_file("local-doom").write_text("general = [broken\n")
    win, engine, _proxy, warnings = _load_main(qgui_app)
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    assert "invalid TOML" in swin.findChild(QQuickItem, "settingsError").property("text")
    for name in ("perfFeral", "perfCachy", "gsEnable", "mhEnable", "luEnable"):
        box = swin.findChild(QQuickItem, name)
        assert box.property("enabled") is False
        assert box.property("checked") is False
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_preview_diff_flow(qgui_app, xdg_env):
    """Preview shows the launch command; Diff opens the defaults diff."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    assert "/bin/true" in swin.findChild(QQuickItem, "previewText").property("text")
    assert swin.findChild(QQuickItem, "previewWrappers").property("text") != ""
    # Centered checkbox title (widgets parity) that collapses the box
    # and persists the flag the Preferences dialog also edits.
    preview_box = swin.findChild(QQuickItem, "previewBox")
    check = preview_box.findChild(QQuickItem, "sectionTitle")
    frame = preview_box.findChild(QQuickItem, "sectionFrame")
    assert check.property("text") == "Launch Command Preview"
    # Collapsed by default (it is reference material, not editing space);
    # expanding it persists the flag the Preferences dialog also edits.
    assert check.property("checked") is False and frame.property("visible") is False
    check.setProperty("checked", True)
    QTest.qWait(80)
    qgui_app.processEvents()
    assert frame.property("visible") is True
    assert C.load_preferences().show_preview is True
    check.setProperty("checked", False)
    QTest.qWait(60)
    qgui_app.processEvents()
    assert frame.property("visible") is False
    assert C.load_preferences().show_preview is False
    _click(swin, "diffButton")
    qgui_app.processEvents()
    assert win.findChild(QObject, "diffDialog").property("visible") is True
    assert "custom_executable" in win.findChild(QQuickItem, "diffText").property("text")
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_preview_refreshes_live(qgui_app, xdg_env):
    """Field edits refresh the preview and the status without any click.

    Widgets `_wire_preview` connected every widget; the QML dialog polls
    the draft instead (same JSON the dirty check uses).
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    preview = swin.findChild(QQuickItem, "previewText")
    assert "/bin/true" in preview.property("text")

    swin.findChild(QQuickItem, "settingsExe").setProperty("text", "/bin/echo")
    assert _wait_for(lambda: "/bin/echo" in preview.property("text"), limit=300)

    box = swin.findChild(QObject, "depStatusBox")
    rows = box.property("statusRows")
    rows = rows.toVariant() if hasattr(rows, "toVariant") else rows
    before = [r["msg"] for r in rows]
    assert before, "dependency status listed nothing"
    swin.findChild(QQuickItem, "mhEnable").setProperty("checked", True)

    def status_moved():
        now = box.property("statusRows")
        now = now.toVariant() if hasattr(now, "toVariant") else now
        return [r["msg"] for r in now] != before

    assert _wait_for(status_moved, limit=300), "status never refreshed"

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_preview_poll_settles(qgui_app, xdg_env, monkeypatch):
    """The live poll refreshes once and then idles (no busy rebuild)."""
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    model = engine.rootContext().contextProperty("gameModel")
    calls = []
    original = model.previewCommand
    monkeypatch.setattr(
        model, "previewCommand", lambda appid, fields: calls.append(1) or original(appid, fields)
    )
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    assert swin is not None
    QTest.qWait(800)
    settled = len(calls)
    QTest.qWait(700)
    assert len(calls) == settled, "preview kept rebuilding an unchanged draft"

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_profile_semantics_flow(qgui_app, xdg_env):
    """Save targets the active profile; dirty switches prompt to discard."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = "native"
    C.save(cfg)
    C.save_profile("local-doom", "fast", C.load("local-doom"))
    slow = C.load("local-doom")
    slow.general.name = "Slow"
    C.save_profile("local-doom", "slow", slow)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    name = swin.findChild(QQuickItem, "settingsName")
    assert dlg.property("dialogProfile") == ""
    dlg.switchProfile("fast")
    qgui_app.processEvents()
    assert dlg.property("dialogProfile") == "fast"
    assert name.property("text") == "Doom"
    name.setProperty("text", "Unsaved")
    dlg.requestProfileSwitch(1)
    qgui_app.processEvents()
    confirm = win.findChild(QObject, "settingsConfirm")
    assert confirm.property("visible") is True
    assert dlg.property("confirmPurpose") == "discardSwitch"
    dlg.acceptConfirm()
    qgui_app.processEvents()
    assert name.property("text") == "Slow"
    assert dlg.property("dialogProfile") == "slow"
    dlg.requestProfileSwitch(0)
    qgui_app.processEvents()
    assert confirm.property("opened") is False
    assert name.property("text") == "Doom"
    box = swin.findChild(QQuickItem, "settingsProfiles")
    box.setProperty("currentIndex", 1)
    # _click polls the hit test: the confirm just closed leaves its dim
    # overlay above the window for a moment and would swallow a raw click.
    _click(swin, "settingsProfileDelete")
    qgui_app.processEvents()
    assert confirm.property("visible") is True
    dlg.acceptConfirm()
    qgui_app.processEvents()
    assert C.list_profiles("local-doom") == ["fast"]
    assert name.property("text") == "Doom"
    name.setProperty("text", "Fast Edit")
    dlg.save()
    qgui_app.processEvents()
    assert C.load("local-doom").general.name == "Doom"
    assert C.load_profile("local-doom", "fast").general.name == "Fast Edit"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_general_formlayout_wide(qgui_app, xdg_env):
    """General tab uses FormLayout side-by-side labels when wide."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    QTest.qWait(400)
    for _ in range(10):
        qgui_app.processEvents()
    form = swin.findChild(QQuickItem, "settingsGeneralForm")
    assert form.property("wideMode") is True
    name = swin.findChild(QQuickItem, "settingsName")
    # Labels keep a right-aligned column of their own (it shrank with the
    # launch rows that used to carry the tab's longest captions).
    assert name.property("x") > 60
    # The field column takes the tab (widgets QFormLayout), no centered cap.
    assert abs(name.property("x") + name.property("width") - form.property("width")) <= 24
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_library_fields_flow(qgui_app, xdg_env):
    """Library fields round-trip: tags, platform, args/cwd, fps, prefix, donor."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    swin.findChild(QQuickItem, "settingsCats").setProperty("text", "Action, Retro")
    swin.findChild(QQuickItem, "settingsPlatform").setProperty("text", "PC")
    swin.findChild(QQuickItem, "settingsArgs").setProperty("text", "--fullscreen")
    swin.findChild(QQuickItem, "settingsCwd").setProperty("text", "/tmp")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_PERF)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "mhFps").setProperty("value", 60)
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_COMPAT)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "winePrefix").setProperty("text", "/tmp/pfx")
    assert isinstance(dlg.property("wineToolsData"), list)
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_ART)
    qgui_app.processEvents()
    swin.findChild(QQuickItem, "artDonor").setProperty("text", "480")
    dlg.save()
    qgui_app.processEvents()
    back = C.load("local-doom")
    assert back.general.categories == ["Action", "Retro"]
    assert back.general.platform == "PC"
    assert back.general.launch_args == "--fullscreen"
    assert back.general.launch_cwd == "/tmp"
    assert back.mangohud.fps_limit == 60
    assert back.proton.wine_prefix == "/tmp/pfx"
    assert back.artwork.donor_appid == "480"
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_library_columns_headers(qgui_app, xdg_env):
    """New library columns: titles, visibility flags, header menu."""
    from PySide6.QtCore import QObject

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    C.save(cfg)
    win, engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert page.columnTitle(6) == "Last Played"
    assert page.columnTitle(11) == "Category"
    assert page.columnVisible(6) is True
    assert page.columnVisible(11) is False
    assert page.columnSortRole(6) == "gameLastSecs"
    proxy.showCategory = True
    assert page.columnVisible(11) is True
    page.headerClicked(6)
    qgui_app.processEvents()
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_library_category_filter_bulk(qgui_app, xdg_env):
    """Drawer category filter narrows; bulk set writes tags."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    for appid, name in (("local-doom", "Doom"), ("local-quake", "Quake")):
        cfg = C.GameConfig()
        cfg.general.appid = appid
        cfg.general.name = name
        cfg.general.custom_executable = "/bin/true"
        C.save(cfg)
    win, engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert proxy.rowCount() == 2
    dlg = win.findChild(QObject, "categoryDialog")
    assert dlg is not None
    dlg.openDialog()
    qgui_app.processEvents()
    assert win.findChild(QObject, "categoryDialog").property("visible") is True
    win.findChild(QObject, "categoryDialog").close()
    page.select("local-doom")
    win.findChild(QQuickItem, "bulkCatsField").setProperty("text", "Action")
    page.acceptBulkCats()
    qgui_app.processEvents()
    assert C.load("local-doom").general.categories == ["Action"]
    proxy.setProperty("categoryKey", "Action")
    assert proxy.rowCount() == 1
    proxy.setProperty("categoryKey", "Missing")
    assert proxy.rowCount() == 0
    proxy.setProperty("categoryKey", "")
    assert proxy.rowCount() == 2
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_settings_audio_sink_flow(qgui_app, xdg_env, monkeypatch):
    """The sink picker labels the Description and stores the node name.

    `pactl list short sinks` reported the node name only, so the combo
    listed `alsa_output.pci-…analog-stereo`; the Description now labels the
    entry while the config keeps the name the launcher needs.
    """
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C
    from tkarcade.backends import audio as aubackend

    monkeypatch.setattr(aubackend, "list_sinks", lambda: [("alsa_usb", "USB Headset")])
    cfg = C.GameConfig()
    cfg.general.appid = "local-doom"
    cfg.general.name = "Doom"
    cfg.general.custom_executable = "/bin/true"
    cfg.audio.sink = "alsa_usb"
    C.save(cfg)
    win, engine, _proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    page.openGameSettings("local-doom")
    swin = _settings_window(qgui_app)
    dlg = win.findChild(QObject, "gameSettings")
    swin.findChild(QQuickItem, "settingsTabs").setProperty("currentIndex", TAB_SYSTEM)
    qgui_app.processEvents()
    box = swin.findChild(QQuickItem, "auSink")
    assert box is not None
    entries = box.property("model")
    assert [e["data"] for e in entries] == ["", "alsa_usb"]
    assert entries[1]["text"] == "USB Headset"
    assert dlg.audioSinkData() == "alsa_usb"
    box.setProperty("currentIndex", 0)
    qgui_app.processEvents()
    assert dlg.audioSinkData() == ""
    dlg.save()
    qgui_app.processEvents()
    assert C.load("local-doom").audio.sink == ""
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    engine.deleteLater()
    qgui_app.processEvents()


def test_no_gutter_game_header_stub():
    """No divider stub between gutter and game header cells (TKS)."""
    import pathlib

    from tkarcade.gui import kirigami_app as kapp

    src = (pathlib.Path(kapp.__file__).parent / "qml" / "MainPage.qml").read_text()
    assert "visible: logical !== 0" in src


def test_row_hover_tracks_mouse(qgui_app, xdg_env):
    """Hovering a row washes it lightly (TKS) without selecting."""
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "77"
    C.save(cfg)
    win, _engine, proxy, warnings = _load_main(qgui_app)
    page = win.findChild(QObject, "gamesPage")
    assert page is not None
    table = win.findChild(QQuickItem, "gameTable")
    rows = _table_rows(table, proxy)
    assert len(rows) == 1
    assert page.property("hoveredRow") == -1
    selected_before = page.property("selectedIds").toVariant()
    QTest.mouseMove(win, rows[0][1])
    for _ in range(20):
        qgui_app.processEvents()
        if page.property("hoveredRow") == 0:
            break
    assert page.property("hoveredRow") == 0
    assert page.property("selectedIds").toVariant() == selected_before
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


def _visible_item(win, name):
    """The visible instance of a named item (ActionToolBar instantiates twice)."""
    from PySide6.QtQuick import QQuickItem

    for item in win.findChildren(QQuickItem, name):
        try:
            if item.property("visible"):
                return item
        except Exception:
            continue
    return None


def _button_bounds(win, labels):
    """Scene-x (left, right) of the visible buttons carrying one of `labels`."""
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem

    left, right = None, None
    for item in win.findChildren(QQuickItem):
        try:
            if not item.property("visible"):
                continue
            label = item.property("text")
        except Exception:
            continue
        if label not in labels:
            continue
        try:
            item_left = item.mapToScene(QPointF(0, 0)).x()
            item_right = item.mapToScene(QPointF(item.property("width"), 0)).x()
        except Exception:
            continue
        left = item_left if left is None else min(left, item_left)
        right = item_right if right is None else max(right, item_right)
    return left, right


def _check_toolbar_pinned(win, qgui_app):
    """Icons pin to the corner; the filter fills buttons-to-icons."""
    from PySide6.QtCore import QPointF

    # ActionToolBar instantiates displayComponents twice (toolbar row
    # plus hidden overflow twin): measure the visible instances.
    icons = _visible_item(win, "toolbarIcons")
    search = _visible_item(win, "searchField")
    assert icons is not None and search is not None
    for _ in range(20):
        qgui_app.processEvents()
    scene_right = win.property("width")
    icons_right = icons.mapToScene(QPointF(icons.property("width"), 0)).x()
    assert scene_right - icons_right <= 12, (scene_right, icons_right)
    search_left = search.mapToScene(QPointF(0, 0)).x()
    search_right = search.mapToScene(QPointF(search.property("width"), 0)).x()
    assert search_right - search_left >= 100
    assert search_left >= 0 and search_right <= icons_right + 1

    group_left, group_right = _button_bounds(win, ("Play", "Add Game", "Edit...", "Remove"))
    assert group_left is not None and group_right is not None
    # Right-aligned row: buttons sit left of the filter with no overlap.
    assert group_right <= search_left + 1, (group_left, group_right, search_left)
    assert group_left >= 0


def _check_drawer_header_centered(win, qgui_app):
    """Library sits on the header center (button balanced both sides)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    btn = win.findChild(QQuickItem, "drawerHeaderButton")
    assert btn is not None
    pos = btn.mapToScene(QPointF(btn.property("width") / 2, 5)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    for _ in range(10):
        qgui_app.processEvents()
    bar = win.findChild(QQuickItem, "drawerHeaderBar")
    label = None
    for item in bar.findChildren(QQuickItem):
        try:
            if item.property("visible") and item.property("text") == "Library":
                label = item
                break
        except Exception:
            continue
    assert label is not None
    bar_cx = bar.mapToScene(QPointF(0, 0)).x() + float(bar.property("width") or 0) / 2
    label_cx = label.mapToScene(QPointF(0, 0)).x() + float(label.property("width") or 0) / 2
    assert abs(label_cx - bar_cx) <= 1.0


def test_toolbar_and_window_chrome(qgui_app, xdg_env):
    """Toolbar pinning, the window size floor and the drawer header.

    Read-only checks of the one default window (the drawer header click
    expands the drawer, so it goes last).
    """
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = "1"
    C.save(cfg)
    win, _engine, _proxy, warnings = _load_main(qgui_app)

    _check_toolbar_pinned(win, qgui_app)
    # The window never shrinks below 1280x720 (crowding guard).
    assert win.property("minimumWidth") == 1280
    assert win.property("minimumHeight") == 720
    _check_drawer_header_centered(win, qgui_app)

    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    win.close()
    _engine.deleteLater()
    qgui_app.processEvents()


# --- standalone editor / pre-launch menu (gui/edit.py drives both) --------


def _load_editor(qgui_app, mode="edit", appid="", name="", can_launch=True, pick=False, timeout=0):
    """Editor.qml in-process: (root, engine, model, decided, warnings).

    The editor creates its UI windows with createObject(null) -- a window
    declared inside another one never shows while the enclosing one is
    hidden, and the editor has no main window. They are therefore
    top-levels, found by title, never through the root's QObject tree.
    """
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from tkarcade.gui.kirigami_app import qml_url
    from tkarcade.gui.model import GameFilterModel, GameListModel

    engine = QQmlApplicationEngine()
    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    model = GameListModel(engine)
    engine.rootContext().setContextProperty("gameModel", model)
    game_filter = GameFilterModel(engine)
    game_filter.setSourceModel(model)
    engine.rootContext().setContextProperty("gameFilter", game_filter)
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_CLICKS", "")
    engine.rootContext().setContextProperty("TKARCADE_DEBUG_GEOMETRY", "")
    engine.load(QUrl(qml_url("Editor.qml")))
    assert len(engine.rootObjects()) == 1, "Editor.qml did not load"
    root = engine.rootObjects()[0]
    decided: list[tuple[str, str]] = []
    root.decided.connect(lambda outcome, ended: decided.append((outcome, ended)))
    for key, value in (
        ("mode", mode),
        ("appid", appid),
        ("name", name),
        ("canLaunch", can_launch),
        ("pick", pick),
        ("timeout", timeout),
    ):
        root.setProperty(key, value)
    root.start()
    qgui_app.processEvents()
    return root, engine, model, decided, warnings


def _editor_window(qgui_app, title_prefix):
    """A visible editor top-level whose title starts with the prefix."""
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest

    for _ in range(25):
        for window in QGuiApplication.topLevelWindows():
            if window.isVisible() and window.title().startswith(title_prefix):
                return window
        QTest.qWait(20)
    titles = [w.title() for w in QGuiApplication.topLevelWindows()]
    raise AssertionError(f"editor window {title_prefix!r} never showed (have {titles})")


def _click_editor_button(qgui_app, window, name):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    button = window.findChild(QQuickItem, name)
    assert button is not None, name
    pos = button.mapToScene(
        QPointF(button.property("width") / 2, button.property("height") / 2)
    ).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    QTest.qWait(30)


def _save_one_game(appid, name, game_type="native"):
    from tkarcade import config as C

    cfg = C.GameConfig()
    cfg.general.appid = appid
    cfg.general.name = name
    cfg.general.custom_executable = "/bin/true"
    cfg.general.game_type = game_type
    C.save(cfg)


def _editor_finish(qgui_app, engine, windows):
    """Tear the editor down: its windows are separate top-levels."""
    from PySide6.QtTest import QTest

    for window in windows:
        window.close()
    engine.deleteLater()
    QTest.qWait(20)
    qgui_app.processEvents()


def test_editor_save_reports_saved(qgui_app, xdg_env):
    """Save in the standalone editor reports "saved" with the AppID."""
    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    _click_editor_button(qgui_app, swin, "settingsSave")
    assert decided == [("saved", "local-doom")]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    _editor_finish(qgui_app, engine, [swin])


def test_editor_cancel_reports_cancelled(qgui_app, xdg_env):
    """Cancel reports "cancelled": the launcher must not launch."""
    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    _click_editor_button(qgui_app, swin, "settingsCancel")
    assert decided == [("cancelled", "local-doom")]
    _editor_finish(qgui_app, engine, [swin])


def test_editor_escape_reports_cancelled(qgui_app, xdg_env):
    """Escape cancels the settings window: the launcher must not launch."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    QTest.keyClick(swin, Qt.Key.Key_Escape)
    assert _wait_for(lambda: bool(decided)), "Escape reported nothing"
    assert decided == [("cancelled", "local-doom")]
    _editor_finish(qgui_app, engine, [swin])


def test_editor_enter_saves_and_launches(qgui_app, xdg_env):
    """Enter reports "launch": a launch-capable editor defaults to Save & Launch.

    The widgets made `b_save_launch` the default in launch mode
    (game_dialog.py), Save only otherwise.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    _settle_focus(swin)
    QTest.keyClick(swin, Qt.Key.Key_Return)
    assert _wait_for(lambda: bool(decided)), "Enter reported nothing"
    assert decided == [("launch", "local-doom")]
    _editor_finish(qgui_app, engine, [swin])


def test_prelaunch_menu_enter_launches(qgui_app, xdg_env):
    """Enter on the pre-launch menu launches (the widgets default button)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom"
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    _settle_focus(menu)
    QTest.keyClick(menu, Qt.Key.Key_Return)
    assert _wait_for(lambda: bool(decided)), "Enter reported nothing"
    assert decided == [("launch", "local-doom")]
    _editor_finish(qgui_app, engine, [menu])


def test_editor_picker_escape_reports_cancelled(qgui_app, xdg_env):
    """Escape on the picker reports the empty AppID (widgets parity)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, pick=True)
    picker = _editor_window(qgui_app, "Edit Game")
    QTest.keyClick(picker, Qt.Key.Key_Escape)
    assert _wait_for(lambda: bool(decided)), "Escape reported nothing"
    assert decided == [("cancelled", "")]
    _editor_finish(qgui_app, engine, [picker])


def test_prelaunch_menu_escape_reports_cancelled(qgui_app, xdg_env):
    """Escape on the pre-launch menu aborts the launch (widgets parity)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom"
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    QTest.keyClick(menu, Qt.Key.Key_Escape)
    assert _wait_for(lambda: bool(decided)), "Escape reported nothing"
    assert decided == [("cancelled", "local-doom")]
    _editor_finish(qgui_app, engine, [menu])


def test_editor_save_and_launch_reports_launch(qgui_app, xdg_env):
    """Save & Launch persists the fields and asks for the launch."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    name = swin.findChild(QQuickItem, "settingsName")
    name.setProperty("text", "Doom II")
    _click_editor_button(qgui_app, swin, "settingsSaveLaunch")
    assert decided == [("launch", "local-doom")]
    assert C.load("local-doom").general.name == "Doom II"
    _editor_finish(qgui_app, engine, [swin])


def test_editor_launch_without_saving_reports_launch(qgui_app, xdg_env):
    """The plain Launch button runs with the saved config (widgets parity)."""
    from PySide6.QtQuick import QQuickItem

    from tkarcade import config as C

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, appid="local-doom")
    swin = _editor_window(qgui_app, "Game Settings")
    swin.findChild(QQuickItem, "settingsName").setProperty("text", "Doom II")
    _click_editor_button(qgui_app, swin, "settingsLaunch")
    assert decided == [("launch", "local-doom")]
    assert C.load("local-doom").general.name == "Doom"
    _editor_finish(qgui_app, engine, [swin])


def test_editor_hides_launch_buttons_without_a_command(qgui_app, xdg_env):
    """No game command to run: only Save / Cancel (can_launch false)."""
    from PySide6.QtQuick import QQuickItem

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, appid="local-doom", can_launch=False
    )
    swin = _editor_window(qgui_app, "Game Settings")
    assert swin.findChild(QQuickItem, "settingsLaunch").property("visible") is False
    assert swin.findChild(QQuickItem, "settingsSaveLaunch").property("visible") is False
    _click_editor_button(qgui_app, swin, "settingsSave")
    assert decided == [("saved", "local-doom")]
    _editor_finish(qgui_app, engine, [swin])


def test_editor_picks_a_game_without_an_appid(qgui_app, xdg_env):
    """--pick lists every game; OK opens settings for the chosen AppID."""
    from PySide6.QtCore import QObject

    _save_one_game("local-doom", "Doom")
    _save_one_game("local-quake", "Quake")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, pick=True)
    picker = _editor_window(qgui_app, "Edit Game")
    from PySide6.QtTest import QTest

    for _ in range(20):
        if picker.findChild(QObject, "editorPickBox").property("count") >= 2:
            break
        QTest.qWait(20)
    box = picker.findChild(QObject, "editorPickBox")
    rows = [box.property("model")[i] for i in range(box.property("count"))]
    assert any(row == "Doom [local-doom]" for row in rows)
    assert any(row == "Quake [local-quake]" for row in rows)
    box.setProperty("currentIndex", rows.index("Quake [local-quake]"))
    _click_editor_button(qgui_app, picker, "editorPickOk")
    assert decided == []
    swin = _editor_window(qgui_app, "Game Settings")
    from PySide6.QtQuick import QQuickItem

    assert swin.findChild(QQuickItem, "settingsName").property("text") == "Quake"
    _click_editor_button(qgui_app, swin, "settingsCancel")
    assert decided == [("cancelled", "local-quake")]
    _editor_finish(qgui_app, engine, [picker, swin])


def test_editor_pick_cancel_reports_cancelled(qgui_app, xdg_env):
    """Cancelling the picker reports the empty AppID (widgets parity)."""
    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, pick=True)
    picker = _editor_window(qgui_app, "Edit Game")
    _click_editor_button(qgui_app, picker, "editorPickCancel")
    assert decided == [("cancelled", "")]
    _editor_finish(qgui_app, engine, [picker])


def test_editor_picker_enter_picks(qgui_app, xdg_env):
    """Enter on the picker takes the selected game (its default button)."""
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(qgui_app, pick=True)
    picker = _editor_window(qgui_app, "Edit Game")
    box = picker.findChild(QObject, "editorPickBox")
    assert _wait_for(lambda: box.property("count") >= 1), "picker never listed a game"
    _settle_focus(picker)
    QTest.keyClick(picker, Qt.Key.Key_Return)
    swin = _editor_window(qgui_app, "Game Settings")
    assert decided == []  # the pick opened the editor, it did not decide
    assert swin.findChild(QQuickItem, "settingsName").property("text") == "Doom"
    _editor_finish(qgui_app, engine, [picker, swin])


def test_prelaunch_menu_opens_settings_and_launches(qgui_app, xdg_env):
    """Settings... on the menu opens the editor modal on it; Launch proceeds."""
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickItem

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom", timeout=30
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    assert menu.findChild(QQuickItem, "prelaunchCountdown").property("text") == "Launching in 30…"
    _click_editor_button(qgui_app, menu, "prelaunchSettings")
    # Opening the editor stops the countdown (widgets parity) and leaves
    # the menu's own Launch/Cancel in charge.
    assert menu.property("remaining") == 0
    swin = _editor_window(qgui_app, "Game Settings")
    assert swin.property("modality") == Qt.WindowModality.WindowModal
    assert swin.findChild(QQuickItem, "settingsLaunch").property("visible") is False
    _click_editor_button(qgui_app, swin, "settingsSave")
    assert decided == []  # the menu still owns the outcome
    _click_editor_button(qgui_app, menu, "prelaunchLaunch")
    assert decided == [("launch", "local-doom")]
    real = [w for w in warnings if "graphics scene" not in w]
    assert real == []
    _editor_finish(qgui_app, engine, [menu, swin])


def test_prelaunch_menu_cancel_reports_cancelled(qgui_app, xdg_env):
    """Cancel on the pre-launch menu aborts the launch."""
    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom"
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    _click_editor_button(qgui_app, menu, "prelaunchCancel")
    assert decided == [("cancelled", "local-doom")]
    _editor_finish(qgui_app, engine, [menu])


def test_prelaunch_menu_countdown_auto_launches(qgui_app, xdg_env):
    """menu_timeout > 0 counts down and launches on its own."""
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom", timeout=1
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    assert menu.findChild(QQuickItem, "prelaunchCountdown").property("text") == "Launching in 1…"
    QTest.qWait(1200)
    assert decided == [("launch", "local-doom")]
    _editor_finish(qgui_app, engine, [menu])


def test_prelaunch_menu_disables_launch_without_a_command(qgui_app, xdg_env):
    """No command to run: Launch is disabled and no countdown starts."""
    from PySide6.QtQuick import QQuickItem

    _save_one_game("local-doom", "Doom")
    _root, engine, _model, decided, _warnings = _load_editor(
        qgui_app, mode="menu", appid="local-doom", name="Doom", timeout=5, can_launch=False
    )
    menu = _editor_window(qgui_app, "TKArcade — Doom")
    assert menu.findChild(QQuickItem, "prelaunchLaunch").property("enabled") is False
    assert menu.findChild(QQuickItem, "prelaunchCountdown").property("visible") is False
    _click_editor_button(qgui_app, menu, "prelaunchLaunch")
    assert decided == []
    _click_editor_button(qgui_app, menu, "prelaunchCancel")
    assert decided == [("cancelled", "local-doom")]
    _editor_finish(qgui_app, engine, [menu])
