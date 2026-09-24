"""Compact, movable goal HUD for manual factory progress."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.projects import ProjectManager, ProjectTask
from ui.i18n import tr, unit_label
from ui.theme import APP_STYLESHEET


class ProjectHud(QWidget):
    def __init__(self, manager: ProjectManager, language: str = "ko"):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.manager = manager
        self.language = language
        self.settings = QSettings("SatisfactoryBuildCalculator", "SatisfactoryBuildCalculator")
        self._drag_offset: QPoint | None = None
        self._resize_origin_y: int | None = None
        self._resize_origin_height = 0
        try:
            self._preferred_height = int(self.settings.value("goal_hud_height", 0) or 0)
        except (TypeError, ValueError):
            self._preferred_height = 0
        self._manual_height = self._preferred_height > 0
        self._allow_close = False
        self._collapsed = False
        self.setObjectName("projectHud")
        self.setWindowTitle(tr(language, "quest_hud_title"))
        self.setMinimumWidth(286)
        self.setMaximumWidth(320)
        self.resize(304, 340)
        self.setStyleSheet(APP_STYLESHEET + """
            QWidget#projectHud { background: #111c23; border: 1px solid #5b6a74; }
            QFrame#hudHeader { background: #17232c; border: none; border-bottom: 1px solid #3c4b55; }
            QFrame#questCard { background: #1d2932; border: 1px solid #4d5c66; border-radius: 6px; }
            QFrame#questCard[complete="true"] { background: #18372f; border-color: #438e70; }
            QFrame#questCard QLabel { background: transparent; border: none; }
            QFrame#hudHeader QLabel { background: transparent; border: none; }
            QFrame#hudResizeHandle { background: #34434d; border: none; }
            QFrame#hudResizeHandle:hover { background: #d99b43; }
            QLabel#hudTitle { color: #f0ad49; font-size: 12pt; font-weight: 700; }
            QLabel#questTitle { color: #f4f1e9; font-size: 10pt; font-weight: 700; }
            QLabel#questMeta { color: #aeb9c0; font-size: 9pt; }
            QLabel#questProgress { color: #f0ad49; font-size: 11pt; font-weight: 700; }
            QToolButton { padding: 3px 7px; }
        """)
        self._build_ui()
        self.manager.changed.connect(self.rebuild)
        self.manager.active_project_changed.connect(lambda _: self.rebuild())
        self.rebuild()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("hudHeader")
        self.header.installEventFilter(self)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 8, 8, 8)
        self.title_label = QLabel(self.header)
        self.title_label.setObjectName("hudTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        self.reset_button = QPushButton(self.header)
        self.reset_button.setObjectName("goalResetButton")
        self.reset_button.clicked.connect(self._confirm_reset)
        header_layout.addWidget(self.reset_button)
        self.collapse_button = QToolButton(self.header)
        self.collapse_button.clicked.connect(self._toggle_collapsed)
        header_layout.addWidget(self.collapse_button)
        self.close_button = QToolButton(self.header)
        self.close_button.setText("×")
        self.close_button.clicked.connect(self.hide)
        header_layout.addWidget(self.close_button)
        root.addWidget(self.header)

        self.body = QWidget(self)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 8, 10, 10)
        body_layout.setSpacing(8)
        self.project_combo = QComboBox(self.body)
        self.project_combo.currentIndexChanged.connect(self._project_changed)
        body_layout.addWidget(self.project_combo)

        self.scroll = QScrollArea(self.body)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.task_container = QWidget(self.scroll)
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(7)
        self.scroll.setWidget(self.task_container)
        body_layout.addWidget(self.scroll, 1)
        root.addWidget(self.body, 1)

        self.resize_handle = QFrame(self)
        self.resize_handle.setObjectName("hudResizeHandle")
        self.resize_handle.setFixedHeight(7)
        self.resize_handle.setCursor(Qt.CursorShape.SizeVerCursor)
        self.resize_handle.setToolTip(tr(self.language, "goal_resize_tip"))
        self.resize_handle.installEventFilter(self)
        root.addWidget(self.resize_handle)

    def rebuild(self) -> None:
        scroll_position = self.scroll.verticalScrollBar().value()
        # The clicked +/-/complete button is about to be deleted. Move focus
        # away first so QScrollArea does not follow the replacement widget to
        # the bottom of the list.
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for project in self.manager.projects:
            name = project.name_en if self.language == "en" else project.name_ko
            self.project_combo.addItem(name, project.project_id)
        index = self.project_combo.findData(self.manager.active_project_id)
        self.project_combo.setCurrentIndex(max(0, index))
        self.project_combo.setVisible(len(self.manager.projects) > 1)
        self.project_combo.blockSignals(False)

        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        project = self.manager.active_project
        if project is None or not project.tasks:
            empty = QLabel(tr(self.language, "quest_empty"), self.task_container)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #8f9ba3; padding: 24px;")
            self.task_layout.addWidget(empty)
        else:
            for task in project.tasks:
                self.task_layout.addWidget(self._task_card(task))
        self.task_layout.addStretch(1)
        self._update_header()
        QTimer.singleShot(0, self._resize_to_content)
        QTimer.singleShot(0, lambda value=scroll_position: self._restore_scroll(value))
        QTimer.singleShot(30, lambda value=scroll_position: self._restore_scroll(value))

    def _restore_scroll(self, value: int) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(min(max(value, bar.minimum()), bar.maximum()))

    def _confirm_reset(self) -> None:
        if self.manager.active_project is None:
            return
        answer = QMessageBox.question(
            self,
            tr(self.language, "goal_reset_title"),
            tr(self.language, "goal_reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.manager.clear_active_project()

    def _task_card(self, task: ProjectTask) -> QFrame:
        card = QFrame(self.task_container)
        card.setObjectName("questCard")
        card.setProperty("complete", task.status == "complete")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(9, 6, 9, 7)
        layout.setSpacing(5)

        title_row = QHBoxLayout()
        title = QLabel(task.name_en if self.language == "en" else task.name_ko, card)
        title.setObjectName("questTitle")
        title_row.addWidget(title, 1)
        if task.status == "complete":
            done = QLabel(tr(self.language, "quest_done_compact"), card)
            done.setStyleSheet("color: #73c99f; font-weight: 700;")
            title_row.addWidget(done)
            undo = QPushButton(tr(self.language, "quest_cancel_complete"), card)
            undo.clicked.connect(lambda: self.manager.toggle_complete(task.task_id))
            title_row.addWidget(undo)
            layout.addLayout(title_row)
            return card

        remove = QToolButton(card)
        remove.setText("×")
        remove.setToolTip(tr(self.language, "quest_remove"))
        remove.clicked.connect(lambda: self.manager.remove_task(task.task_id))
        title_row.addWidget(remove)
        layout.addLayout(title_row)

        building = task.building_name_en if self.language == "en" else task.building_name_ko
        recipe = task.recipe_name_en if self.language == "en" else task.recipe_name_ko
        meta = QLabel(f"{building} · {recipe}", card)
        meta.setObjectName("questMeta")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        progress_row = QHBoxLayout()
        progress = QLabel(card)
        progress.setObjectName("questProgress")
        if task.required_buildings:
            progress.setText(tr(self.language, "quest_build_progress",
                                current=task.installed_buildings, total=task.required_buildings))
        else:
            progress.setText(tr(self.language, "quest_checklist"))
        progress_row.addWidget(progress, 1)
        if task.required_buildings:
            minus = QPushButton("−", card)
            minus.setFixedWidth(34)
            minus.setEnabled(not task.manual_locked)
            minus.clicked.connect(lambda: self.manager.adjust_installed(task.task_id, -1))
            plus = QPushButton("+", card)
            plus.setFixedWidth(34)
            plus.setEnabled(not task.manual_locked)
            plus.clicked.connect(lambda: self.manager.adjust_installed(task.task_id, 1))
            progress_row.addWidget(minus)
            progress_row.addWidget(plus)
        complete = QPushButton(
            tr(self.language, "quest_cancel_complete" if task.status == "complete" else "quest_complete"), card
        )
        complete.setCheckable(True)
        complete.setChecked(task.status == "complete")
        complete.clicked.connect(lambda: self.manager.toggle_complete(task.task_id))
        progress_row.addWidget(complete)
        layout.addLayout(progress_row)

        unit = unit_label(task.unit, self.language)
        target = QLabel(tr(self.language, "quest_target_line",
                           value=task.target_rate, unit=unit), card)
        target.setObjectName("questMeta")
        layout.addWidget(target)
        if task.ingredients:
            values = []
            for ingredient in task.ingredients:
                name = ingredient.name_en if self.language == "en" else ingredient.name_ko
                values.append(
                    f"{name} {ingredient.rate:.2f} {unit_label(ingredient.unit, self.language)}"
                )
            inputs = QLabel(tr(self.language, "quest_inputs", values="\n".join(values)), card)
            inputs.setObjectName("questMeta")
            inputs.setWordWrap(True)
            layout.addWidget(inputs)
        return card

    def _update_header(self) -> None:
        project = self.manager.active_project
        total = len(project.tasks) if project else 0
        complete = sum(task.status == "complete" for task in project.tasks) if project else 0
        self.title_label.setText(tr(self.language, "quest_hud_count", complete=complete, total=total))
        self.reset_button.setText(tr(self.language, "goal_reset"))
        self.reset_button.setEnabled(project is not None)
        self.collapse_button.setText("▾" if self._collapsed else "▴")
        self.collapse_button.setToolTip(tr(self.language, "quest_expand" if self._collapsed else "quest_collapse"))

    def _project_changed(self, index: int) -> None:
        project_id = self.project_combo.itemData(index)
        if project_id:
            self.manager.set_active_project(str(project_id))

    def set_language(self, language: str) -> None:
        self.language = language
        self.setWindowTitle(tr(language, "quest_hud_title"))
        self.resize_handle.setToolTip(tr(language, "goal_resize_tip"))
        self.rebuild()

    def show_hud(self) -> None:
        self.rebuild()
        saved = self.settings.value("quest_hud_position")
        if isinstance(saved, QPoint):
            self.move(saved)
        elif not self.isVisible():
            screen = QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.move(area.right() - self.width() - 24, area.top() + 90)
        self._keep_on_screen()
        self.show()
        self.raise_()

    def _toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.body.setVisible(not self._collapsed)
        self.resize_handle.setVisible(not self._collapsed)
        if self._collapsed:
            self.resize(self.width(), self.header.sizeHint().height())
        else:
            self._resize_to_content()
        self._update_header()

    def _resize_to_content(self) -> None:
        if self._collapsed:
            return
        if self._manual_height:
            self.resize(self.width(), self._bounded_height(self._preferred_height))
            return
        project = self.manager.active_project
        card_count = len(project.tasks) if project else 0
        # One selected production card should stay genuinely HUD-sized. More
        # cards grow vertically until the internal list starts scrolling.
        if project and project.tasks:
            task_height = sum(
                58 if task.status == "complete" else 156 + len(task.ingredients) * 18
                for task in project.tasks
            )
        else:
            task_height = 156
        desired = 104 + task_height
        if self.project_combo.isVisible():
            desired += 38
        self.resize(self.width(), min(max(desired, 200), 360))

    def _bounded_height(self, height: int) -> int:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        maximum = max(200, screen.availableGeometry().height() - 24) if screen else 900
        return min(max(height, 180), maximum)

    def _keep_on_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = min(max(self.x(), area.left()), max(area.left(), area.right() - self.width() + 1))
        y = min(max(self.y(), area.top()), max(area.top(), area.bottom() - self.height() + 1))
        self.move(x, y)

    def eventFilter(self, watched, event) -> bool:
        if watched is getattr(self, "resize_handle", None):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._resize_origin_y = event.globalPosition().toPoint().y()
                self._resize_origin_height = self.height()
                return True
            if event.type() == QEvent.Type.MouseMove and self._resize_origin_y is not None:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    delta = event.globalPosition().toPoint().y() - self._resize_origin_y
                    self._preferred_height = self._bounded_height(self._resize_origin_height + delta)
                    self._manual_height = True
                    self.resize(self.width(), self._preferred_height)
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease and self._resize_origin_y is not None:
                self._resize_origin_y = None
                self.settings.setValue("goal_hud_height", self.height())
                self._keep_on_screen()
                return True
        if watched is self.header:
            if event.type() == QEvent.Type.MouseButtonPress:
                mouse = event
                if mouse.button() == Qt.MouseButton.LeftButton:
                    self._drag_offset = mouse.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
                mouse = event
                if mouse.buttons() & Qt.MouseButton.LeftButton:
                    self.move(mouse.globalPosition().toPoint() - self._drag_offset)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                self.settings.setValue("quest_hud_position", self.pos())
                return True
        return super().eventFilter(watched, event)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if self.isVisible():
            self.settings.setValue("quest_hud_position", self.pos())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def dispose(self) -> None:
        self._allow_close = True
        self.close()
