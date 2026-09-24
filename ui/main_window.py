"""Main overlay window coordinating the calculator and scene."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.calculator import CalculationError, ProductionCalculator
from core.data_loader import DataError, load_production_data
from core.models import MachineSettings
from graphics.production_scene import ProductionGraphicsView, ProductionScene
from .global_hotkey import GlobalHotkeyManager
from .legend_widget import BuildingLegend
from .i18n import tr
from .summary_panel import SummaryPanel
from .target_panel import TargetPanel
from .theme import APP_STYLESHEET


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path):
        super().__init__()
        self.language = "ko"
        self.setWindowTitle(tr(self.language, "window_title"))
        self.resize(1280, 800)
        self.setStyleSheet(APP_STYLESHEET)
        self.data = load_production_data(data_dir)
        self.calculator = ProductionCalculator(self.data)
        self.selected_recipes: dict[str, str] = {}
        self.completed: set[str] = set()
        self.machine_settings: dict[str, MachineSettings] = {}
        self.default_shards = 0
        self.current_target_id = ""
        self.current_rate = 0.0
        self.current_existing_grid_mw = 0.0
        self._rebuild_pending = False
        self._force_quit = False
        self._tray_message_shown = False
        self.settings = QSettings("SatisfactoryBuildCalculator", "SatisfactoryBuildCalculator")
        self.hotkey_manager = GlobalHotkeyManager(self._toggle_visibility)

        self.scene = ProductionScene(self.data, self)
        self.scene.recipe_selection_changed.connect(self._change_recipe)
        self.scene.completion_changed.connect(self._toggle_completion)
        self.scene.settings_changed.connect(self._change_machine_setting)
        self.scene.selection_summary_changed.connect(self._update_selection_summary)
        self.view = ProductionGraphicsView(self.scene, self)
        self.setCentralWidget(self.view)

        self.target_panel = TargetPanel(self.data, self)
        self.target_panel.calculate_requested.connect(self._calculate)
        self.target_panel.generator_requested.connect(self._calculate_generator)
        self.target_panel.global_shards_requested.connect(self._apply_global_shards)
        self.legend = BuildingLegend(self.data, self.target_panel)
        self.target_panel.set_legend(self.legend)
        self.summary_panel = SummaryPanel(self.data, self)
        self._add_docks()
        self._add_toolbar()
        self._setup_tray()
        self._restore_hotkey()
        default_target = next(
            (
                item.item_id
                for item in self.data.items.values()
                if item.name_en == "Supercomputer"
            ),
            next(iter(self.data.items)),
        )
        self._calculate(default_target, 10.0)
        QTimer.singleShot(0, self._fit_initial_layout)

    def _fit_initial_layout(self) -> None:
        self.resizeDocks([self.summary_dock], [330], Qt.Orientation.Horizontal)
        self.resizeDocks([self.target_controls_dock], [92], Qt.Orientation.Vertical)
        QTimer.singleShot(50, self.view.fit_graph)

    def _add_docks(self) -> None:
        self.summary_dock = QDockWidget(tr(self.language, "summary_dock"), self)
        summary_dock = self.summary_dock
        summary_dock.setObjectName("summaryDock")
        self.summary_container = QWidget(summary_dock)
        summary_layout = QHBoxLayout(self.summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)
        self.summary_divider = QFrame(self.summary_container)
        self.summary_divider.setObjectName("summaryDivider")
        self.summary_divider.setFixedWidth(2)
        self.summary_divider.setStyleSheet("background: #60717d; border: none;")
        summary_layout.addWidget(self.summary_divider)
        summary_layout.addWidget(self.summary_panel, 1)
        summary_dock.setWidget(self.summary_container)
        summary_dock.setMinimumWidth(300)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, summary_dock)

        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.TopDockWidgetArea)
        # Keep the existing summary column at full height; the former left
        # settings width is now part of the top controls and graph.
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.target_controls_dock = QDockWidget("", self)
        self.target_controls_dock.setObjectName("targetControlsDock")
        self.target_controls_dock.setWidget(self.target_panel.target_controls)
        self.target_controls_dock.setAllowedAreas(Qt.DockWidgetArea.TopDockWidgetArea)
        self.target_controls_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.target_controls_dock.setTitleBarWidget(QWidget(self.target_controls_dock))
        self.target_controls_dock.setMinimumHeight(88)
        self.target_controls_dock.setMaximumHeight(102)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.target_controls_dock)

    def _add_toolbar(self) -> None:
        toolbar = QToolBar(tr(self.language, "toolbar"), self)
        self.toolbar = toolbar
        self.addToolBar(toolbar)
        self.fit_action = QAction(tr(self.language, "fit"), self)
        self.fit_action.triggered.connect(self.view.fit_graph)
        toolbar.addAction(self.fit_action)
        self.reset_layout_action = QAction(tr(self.language, "reset_layout"), self)
        self.reset_layout_action.triggered.connect(self.scene.reset_layout)
        toolbar.addAction(self.reset_layout_action)
        self.layout_lock_action = QAction(tr(self.language, "lock"), self)
        self.layout_lock_action.setCheckable(True)
        self.layout_lock_action.toggled.connect(self.scene.set_layout_locked)
        toolbar.addAction(self.layout_lock_action)

        self.selection_hint = QLabel(tr(self.language, "selection_hint"))
        self.selection_hint.setMaximumWidth(220)
        self.selection_hint.setStyleSheet("color: #afb9c0; padding: 0 10px;")
        toolbar.addWidget(self.selection_hint)

        self.top_checkbox = QCheckBox(tr(self.language, "always_top"))
        self.top_checkbox.toggled.connect(self._set_always_on_top)
        toolbar.addWidget(self.top_checkbox)

        self.language_spacer = QWidget(toolbar)
        self.language_spacer.setFixedWidth(14)
        self.language_spacer.setStyleSheet("background: transparent; border: none;")
        toolbar.addWidget(self.language_spacer)

        self.language_label = QLabel("🌐")
        self.language_label.setToolTip("Language / 언어")
        self.language_label.setAccessibleName("Language selector")
        self.language_label.setStyleSheet(
            "font-family: 'Segoe UI Emoji', 'Segoe UI'; font-size: 14pt; "
            "color: #d8e2e7; padding: 0 4px;"
        )
        toolbar.addWidget(self.language_label)
        self.language_combo = QComboBox(toolbar)
        self.language_combo.addItem("한국어", "ko")
        self.language_combo.addItem("English", "en")
        self.language_combo.setMinimumWidth(100)
        self.language_combo.setToolTip("Language / 언어")
        self.language_combo.setAccessibleName("Language selector")
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        toolbar.addWidget(self.language_combo)

        self.shortcut_button = QPushButton(tr(self.language, "shortcut_settings"), toolbar)
        self.shortcut_button.clicked.connect(self._open_shortcut_dialog)
        toolbar.addWidget(self.shortcut_button)

        self.quit_button = QPushButton(tr(self.language, "quit_app"), toolbar)
        self.quit_button.setObjectName("quitButton")
        self.quit_button.setStyleSheet(
            "QPushButton#quitButton { border-color: #9b5a55; color: #f2d7d4; }"
            "QPushButton#quitButton:hover { background: #6f302e; border-color: #d87970; }"
        )
        self.quit_button.clicked.connect(self._quit_application)
        toolbar.addWidget(self.quit_button)

        self.toggle_visibility_action = QAction(tr(self.language, "toggle_visibility"), self)
        self.toggle_visibility_action.triggered.connect(self._toggle_visibility)
        self.addAction(self.toggle_visibility_action)

    def _setup_tray(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(False)

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_menu = QMenu(self)
        self.tray_toggle_action = QAction(tr(self.language, "tray_hide"), self)
        self.tray_toggle_action.triggered.connect(self._toggle_visibility)
        self.tray_menu.addAction(self.tray_toggle_action)
        self.tray_menu.addSeparator()
        self.tray_quit_action = QAction(tr(self.language, "quit_app"), self)
        self.tray_quit_action.triggered.connect(self._quit_application)
        self.tray_menu.addAction(self.tray_quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.setToolTip(tr(self.language, "window_title"))
        self.tray_icon.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _restore_hotkey(self) -> None:
        saved = str(self.settings.value("toggle_hotkey", "Ctrl+Shift+S"))
        sequence = QKeySequence(saved, QKeySequence.SequenceFormat.PortableText)
        if not self.hotkey_manager.register(sequence):
            sequence = QKeySequence("Ctrl+Shift+S")
            self.hotkey_manager.register(sequence)
        self._update_shortcut_tooltip()

    def _open_shortcut_dialog(self) -> None:
        previous_sequence = QKeySequence(self.hotkey_manager.sequence)
        dialog = QDialog(self)
        dialog.setWindowTitle(tr(self.language, "shortcut_title"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr(self.language, "shortcut_prompt"), dialog))
        example = QLabel(tr(self.language, "shortcut_example"), dialog)
        example.setStyleSheet("color: #9eabb3; font-size: 9pt; padding: 2px 0 5px 0;")
        layout.addWidget(example)
        editor = QKeySequenceEdit(self.hotkey_manager.sequence, dialog)
        editor.setMaximumSequenceLength(1)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        # Release the current shortcut while recording so pressing the same
        # combination is captured by the editor instead of hiding the window.
        self.hotkey_manager.unregister()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.hotkey_manager.register(previous_sequence)
            return

        sequence = editor.keySequence()
        if not self.hotkey_manager.register(sequence):
            hotkey_error = self.hotkey_manager.last_error
            self.hotkey_manager.register(previous_sequence)
            message_key = "shortcut_in_use" if hotkey_error == "in_use" else "shortcut_invalid"
            QMessageBox.warning(self, tr(self.language, "shortcut_title"), tr(self.language, message_key))
            return
        portable = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        self.settings.setValue("toggle_hotkey", portable)
        self._update_shortcut_tooltip()

    def _update_shortcut_tooltip(self) -> None:
        shortcut = self.hotkey_manager.sequence.toString(QKeySequence.SequenceFormat.NativeText)
        self.shortcut_button.setToolTip(tr(self.language, "shortcut_current", shortcut=shortcut))

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._toggle_visibility()

    def createPopupMenu(self):
        """Disable Qt's default toolbar/dock visibility menu on right-click."""

        return None

    def _calculate_generator(self, building_id: str, rate: float, existing_grid_mw: float) -> None:
        preferred_suffix = {
            "Build_GeneratorBiomass_Automated_C": "Desc_Biofuel_C",
            "Build_GeneratorGeoThermal_C": "Normal",
        }.get(building_id, "")
        candidates = [value for value in self.data.recipes_for("Electricity_MW")
                      if value.building_id == building_id]
        recipe = next((value for value in candidates if preferred_suffix
                       and value.recipe_id.endswith(preferred_suffix)), None)
        if recipe is None:
            recipe = candidates[0] if candidates else None
        if recipe is None:
            self._show_error(tr(self.language, "invalid_item"))
            return
        grid_mw = existing_grid_mw if building_id == "Build_AlienPowerBuilding_C" else 0.0
        self._calculate("Electricity_MW", rate, initial_recipe_id=recipe.recipe_id,
                        existing_grid_mw=grid_mw)

    def _calculate(self, item_id: str, rate: float, reset_choices: bool = True,
                   initial_recipe_id: str | None = None,
                   existing_grid_mw: float | None = None) -> None:
        if not item_id:
            self._show_error(tr(self.language, "invalid_item"))
            return
        try:
            recipes = {"root": initial_recipe_id} if reset_choices and initial_recipe_id else (
                {} if reset_choices else self.selected_recipes
            )
            settings = {} if reset_choices else self.machine_settings
            grid_mw = (existing_grid_mw or 0.0) if reset_choices else self.current_existing_grid_mw
            root = self.calculator.calculate(item_id, rate, recipes,
                                             settings, self.default_shards,
                                             language=self.language,
                                             existing_grid_mw=grid_mw)
            totals, raw_totals = self.calculator.summarize(root)
            byproducts = self.calculator.summarize_byproducts(root)
            power_summary = self.calculator.summarize_power(root)
            if reset_choices:
                self.selected_recipes = recipes
                self.completed.clear()
                self.machine_settings.clear()
                self.scene.manual_positions.clear()
            self.current_target_id = item_id
            self.current_rate = rate
            self.current_existing_grid_mw = grid_mw
            self.scene.language = self.language
            self.scene.set_tree(root, self.completed)
            self.view.update_pan_bounds()
            self.target_panel.set_current_target(item_id, root.building_id if root.is_generator else None)
            self.summary_panel.language = self.language
            self.legend.language = self.language
            self.summary_panel.show_summary(totals, raw_totals, power_summary,
                                            root if root.is_generator else None, byproducts)
            self.legend.set_tree(root, self.completed)
            if reset_choices:
                QTimer.singleShot(0, self.view.fit_graph)
        except (CalculationError, DataError) as error:
            self._show_error(str(error))

    def _change_recipe(self, node_id: str, recipe_id: str) -> None:
        self.selected_recipes[node_id] = recipe_id
        self._schedule_rebuild()

    def _toggle_completion(self, node_id: str) -> None:
        if node_id in self.completed:
            self.completed.remove(node_id)
        else:
            self.completed.add(node_id)
        self._schedule_rebuild()

    def _change_machine_setting(self, node_id: str, setting: str, value: int) -> None:
        current = self.machine_settings.get(node_id, MachineSettings(self.default_shards, 0))
        if setting == "shards":
            updated = MachineSettings(value, current.sloops)
        else:
            updated = MachineSettings(current.shards, value)
        self.machine_settings[node_id] = updated
        self._schedule_rebuild()

    def _apply_global_shards(self, count: int) -> None:
        self.default_shards = count
        self.machine_settings = {
            node_id: MachineSettings(count, settings.sloops)
            for node_id, settings in self.machine_settings.items()
        }
        self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        """Rebuild after the active Qt widget signal has returned."""

        if self._rebuild_pending:
            return
        self._rebuild_pending = True
        QTimer.singleShot(0, self._rebuild_current)

    def _rebuild_current(self) -> None:
        self._rebuild_pending = False
        self._calculate(self.current_target_id, self.current_rate, reset_choices=False)

    def _language_changed(self) -> None:
        language = str(self.language_combo.currentData())
        if language == self.language:
            return
        self.language = language
        self.setWindowTitle(tr(language, "window_title"))
        self.summary_dock.setWindowTitle(tr(language, "summary_dock"))
        self.toolbar.setWindowTitle(tr(language, "toolbar"))
        self.fit_action.setText(tr(language, "fit"))
        self.reset_layout_action.setText(tr(language, "reset_layout"))
        self.layout_lock_action.setText(tr(language, "lock"))
        self.top_checkbox.setText(tr(language, "always_top"))
        self.toggle_visibility_action.setText(tr(language, "toggle_visibility"))
        self.shortcut_button.setText(tr(language, "shortcut_settings"))
        self.quit_button.setText(tr(language, "quit_app"))
        self.tray_toggle_action.setText(tr(language, "tray_hide" if self.isVisible() else "tray_open"))
        self.tray_quit_action.setText(tr(language, "quit_app"))
        self.tray_icon.setToolTip(tr(language, "window_title"))
        self._update_shortcut_tooltip()
        self._update_selection_summary("")
        self.target_panel.set_language(language)
        self._calculate(self.current_target_id, self.current_rate, reset_choices=False)

    def _set_always_on_top(self, enabled: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
            self.tray_toggle_action.setText(tr(self.language, "tray_open"))
            return
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.tray_toggle_action.setText(tr(self.language, "tray_hide"))

    def _quit_application(self) -> None:
        self._force_quit = True
        self.hotkey_manager.dispose()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._force_quit:
            self.hotkey_manager.dispose()
            event.accept()
            return
        if not self.tray_icon.isVisible():
            self.hotkey_manager.dispose()
            event.accept()
            QApplication.instance().quit()
            return
        event.ignore()
        self.hide()
        self.tray_toggle_action.setText(tr(self.language, "tray_open"))
        if not self._tray_message_shown:
            shortcut = self.hotkey_manager.sequence.toString(QKeySequence.SequenceFormat.NativeText)
            self.tray_icon.showMessage(
                tr(self.language, "window_title"),
                tr(self.language, "tray_message", shortcut=shortcut),
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
            self._tray_message_shown = True

    def _update_selection_summary(self, text: str) -> None:
        self.selection_hint.setText(text or tr(self.language, "selection_hint"))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, tr(self.language, "error_title"), message)
