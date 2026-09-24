"""Interactive card used for a single production line."""

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsProxyWidget, QComboBox, QSpinBox, QToolButton

from core.data_loader import ProductionData
from core.models import ProductionNode
from ui.controls import ExternalComboControl, ExternalSpinControl
from ui.i18n import tr, unit_label
from .style import (
    COMPLETED_COLOR,
    RAW_RESOURCE_COLOR,
    TARGET_BORDER_COLOR,
    color_for_building,
)


NODE_WIDTH = 230
NODE_HEIGHT = 258


class RecipeComboBox(QComboBox):
    """Raise the whole card while its embedded popup is open."""

    def __init__(self, card: "ProductionNodeItem"):
        super().__init__()
        self.card = card
        self.setMaxVisibleItems(10)

    def configure_popup(self) -> None:
        """Show small recipe sets in full and scroll only larger sets."""

        view = self.view()
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        fallback_height = view.fontMetrics().height() + 8
        row_heights = [view.sizeHintForRow(row) for row in range(self.count())]
        row_heights = [height if height > 0 else fallback_height for height in row_heights]
        if self.count() <= 10:
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            popup_height = sum(row_heights) + view.frameWidth() * 2 + 2
            view.setMinimumHeight(popup_height)
            view.setMaximumHeight(popup_height)
        else:
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            popup_height = sum(row_heights[:10]) + view.frameWidth() * 2 + 2
            view.setMinimumHeight(0)
            view.setMaximumHeight(popup_height)

    def showPopup(self) -> None:
        try:
            self.card.setZValue(100)
        except RuntimeError:
            return
        self.configure_popup()
        super().showPopup()

    def hidePopup(self) -> None:
        super().hidePopup()
        try:
            self.card.setZValue(0)
        except RuntimeError:
            # Qt can destroy the graphics card before its child combo.
            pass


class ProductionNodeItem(QGraphicsItem):
    def __init__(self, node: ProductionNode, data: ProductionData, is_root: bool,
                 completed: bool, recipe_changed: Callable[[str, str], None],
                 completion_toggled: Callable[[str], None],
                 settings_changed: Callable[[str, str, int], None],
                 position_changed: Callable[[str], None],
                 language: str = "ko", movable: bool = True):
        super().__init__()
        self.node = node
        self._data = data
        self._is_root = is_root
        self._completed = completed
        self._related_match = False
        self._recipe_changed = recipe_changed
        self._completion_toggled = completion_toggled
        self._settings_changed = settings_changed
        self._position_changed = position_changed
        self.language = language
        self.setToolTip(node.building_name if node.is_generator else node.item_name)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self._create_controls(data)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_WIDTH, NODE_HEIGHT)

    def _create_controls(self, data: ProductionData) -> None:
        if not self._is_root:
            button = QToolButton()
            button.setText(tr(self.language, "cancel" if self._completed else "complete"))
            button.setToolTip(tr(self.language, "cancel_tip" if self._completed else "complete_tip"))
            button.setFixedSize(58, 28)
            button.setStyleSheet(
                "font-size: 9pt; font-weight: 700; padding: 1px; "
                "background: #25313a; color: #f4f1e9; "
                "border: 1px solid #71808a; border-radius: 4px;"
            )
            button.clicked.connect(lambda: self._completion_toggled(self.node.node_id))
            proxy = QGraphicsProxyWidget(self)
            proxy.setWidget(button)
            proxy.setPos(NODE_WIDTH - 70, 10)

        if not self.node.is_raw_resource and not self._completed:
            combo = RecipeComboBox(self)
            recipes = data.recipes_for(self.node.item_id)
            if self.node.is_generator:
                recipes = [recipe for recipe in recipes if recipe.building_id == self.node.building_id]
            for recipe in recipes:
                combo.addItem(data.recipe_name(recipe, self.language), recipe.recipe_id)
            combo.configure_popup()
            index = combo.findData(self.node.selected_recipe_id)
            combo.setCurrentIndex(max(index, 0))
            combo.currentIndexChanged.connect(
                lambda _: self._recipe_changed(self.node.node_id, str(combo.currentData()))
            )
            combo.setStyleSheet(
                "font-size: 9pt; padding: 2px 7px; "
                "background: #0d171d; color: #f4f1e9; "
                "border: 1px solid #53626d; border-radius: 4px;"
            )
            combo_control = ExternalComboControl(combo)
            combo_control.setFixedSize(NODE_WIDTH - 24, 30)
            proxy = QGraphicsProxyWidget(self)
            proxy.setWidget(combo_control)
            proxy.setPos(12, 46)
            proxy.setZValue(10)

            for x, label, value, maximum, key in (() if self.node.is_generator else (
                (12, tr(self.language, "shards"), self.node.shards, 3, "shards"),
                (119, tr(self.language, "sloops"), self.node.sloops, self.node.sloop_slots, "sloops"),
            )):
                spin = QSpinBox()
                spin.setRange(0, maximum)
                spin.setValue(value)
                spin.setToolTip(tr(self.language, "per_machine_tip", name=label))
                spin.setStyleSheet(
                    "font-size: 9pt; background: #0d171d; color: #f4f1e9; "
                    "border: 1px solid #53626d; border-radius: 4px; padding: 2px 6px;"
                )
                spin.valueChanged.connect(
                    lambda new_value, setting=key: self._settings_changed(self.node.node_id, setting, new_value)
                )
                spin_control = ExternalSpinControl(spin)
                spin_control.setFixedSize(99, 28)
                proxy = QGraphicsProxyWidget(self)
                proxy.setWidget(spin_control)
                proxy.setPos(x, 101)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene():
            self._position_changed(self.node.node_id)
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if self._completed:
            accent = QColor(COMPLETED_COLOR)
        elif self.node.is_raw_resource:
            accent = QColor(RAW_RESOURCE_COLOR)
        else:
            accent = QColor(color_for_building(self.node.building_id))

        background = QColor("#1d2932") if not self._completed else QColor("#18372f")

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border_color = QColor(TARGET_BORDER_COLOR) if self._is_root else QColor("#53626d")
        border_width = 2.0 if self._is_root else 1.0
        if self._related_match:
            border_color = QColor("#e99a43")
            border_width = 3.0
        if self.isSelected():
            border_color = QColor("#ffd18a")
            border_width = 3.5
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(3, 8, 12, 95))
        painter.drawRoundedRect(QRectF(4, 5, NODE_WIDTH - 5, NODE_HEIGHT - 6), 7, 7)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(1, 1, NODE_WIDTH - 5, NODE_HEIGHT - 5), 7, 7)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(3, 9, 4, NODE_HEIGHT - 21), 2, 2)

        painter.setPen(QColor("white"))
        if self._completed:
            item_font = QFont()
            item_font.setBold(True)
            item_font.setPointSize(12)
            painter.setFont(item_font)
            painter.drawText(
                QRectF(16, 76, NODE_WIDTH - 36, 34),
                Qt.AlignmentFlag.AlignCenter,
                self.node.item_name,
            )

            completed_font = QFont()
            completed_font.setBold(True)
            completed_font.setPointSize(18)
            painter.setFont(completed_font)
            painter.drawText(
                QRectF(16, 126, NODE_WIDTH - 36, 42),
                Qt.AlignmentFlag.AlignCenter,
                tr(self.language, "done"),
            )
            return

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        painter.setFont(title_font)
        title_width = NODE_WIDTH - (24 if self._is_root else 92)
        display_name = self.node.building_name if self.node.is_generator else self.node.item_name
        title = painter.fontMetrics().elidedText(display_name, Qt.TextElideMode.ElideRight, title_width)
        painter.drawText(QRectF(14, 11, title_width, 28), Qt.AlignmentFlag.AlignVCenter, title)

        normal_font = QFont()
        normal_font.setPointSize(10)
        painter.setFont(normal_font)
        unit = unit_label(self.node.unit, self.language)
        rate = f"{self.node.required_rate:.2f} {unit}"
        if self.node.is_raw_resource:
            painter.setPen(QColor("#94a3ad"))
            painter.drawText(14, 79, tr(self.language, "output"))
            value_font = QFont()
            value_font.setPointSize(13)
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.setPen(QColor("#f4f1e9"))
            painter.drawText(14, 111, rate)
            painter.setFont(normal_font)
            painter.setPen(QColor("#a8b3ba"))
            raw_line = painter.fontMetrics().elidedText(
                tr(self.language, "raw_input"), Qt.TextElideMode.ElideRight, NODE_WIDTH - 30,
            )
            painter.drawText(14, 142, raw_line)
        else:
            if not self.node.is_generator:
                label_font = QFont()
                label_font.setPointSize(9)
                painter.setFont(label_font)
                painter.setPen(QColor("#94a3ad"))
                painter.drawText(12, 96, tr(self.language, "shards"))
                painter.drawText(119, 96, tr(self.language, "sloops"))
                divider_y = 139
                facility_y = 157
                output_label_y = 176
                output_value_y = 198
                stats_label_y = 216
                stats_value_y = 235
                footer_y = 249
            else:
                painter.setPen(QColor("#94a3ad"))
                painter.drawText(12, 99, tr(self.language, "generation_choice"))
                divider_y = 111
                facility_y = 130
                output_label_y = 149
                output_value_y = 172
                stats_label_y = 191
                stats_value_y = 211
                footer_y = 238

            painter.setPen(QPen(QColor("#3b4953"), 1))
            painter.drawLine(12, divider_y, NODE_WIDTH - 14, divider_y)
            label_font = QFont()
            label_font.setPointSize(8)
            painter.setFont(label_font)
            painter.setPen(QColor("#94a3ad"))
            painter.drawText(12, facility_y, tr(self.language, "facility"))
            facility_font = QFont()
            facility_font.setPointSize(9)
            facility_font.setBold(True)
            painter.setFont(facility_font)
            painter.setPen(accent.lighter(135))
            facility_name = painter.fontMetrics().elidedText(
                self.node.building_name, Qt.TextElideMode.ElideRight, 136,
            )
            painter.drawText(80, facility_y, facility_name)

            painter.setFont(label_font)
            painter.setPen(QColor("#94a3ad"))
            painter.drawText(12, output_label_y, tr(self.language, "generation_output" if self.node.is_generator else "output"))

            value_font = QFont()
            value_font.setPointSize(11)
            value_font.setBold(True)
            painter.setFont(value_font)
            painter.setPen(QColor("#f4f1e9"))
            rate_line = painter.fontMetrics().elidedText(rate, Qt.TextElideMode.ElideRight, NODE_WIDTH - 26)
            painter.drawText(12, output_value_y, rate_line)

            painter.setFont(label_font)
            painter.setPen(QColor("#94a3ad"))
            painter.drawText(12, stats_label_y, tr(self.language, "calculated"))
            painter.drawText(121, stats_label_y, tr(self.language, "installed"))
            actual_count = self.node.installed_count
            stats_font = QFont()
            stats_font.setPointSize(9)
            stats_font.setBold(True)
            painter.setFont(stats_font)
            painter.setPen(QColor("#e8ecee"))
            painter.drawText(12, stats_value_y, f"{self.node.building_count:.2f}{tr(self.language, 'machine_unit')}")
            painter.drawText(121, stats_value_y, f"{actual_count}{tr(self.language, 'machine_unit')}")

            footer_font = QFont()
            footer_font.setPointSize(8)
            painter.setFont(footer_font)
            painter.setPen(QColor("#d9a055"))
            if self.node.is_generator:
                if self.node.generation_kind == "geothermal":
                    note = tr(self.language, "geothermal_note", low=self.node.generation_min_mw,
                              high=self.node.generation_max_mw, average=self.node.generation_mw)
                elif self.node.generation_kind == "augmenter":
                    note = tr(self.language, "augmenter_note", value=self.node.generation_mw)
                elif self.node.byproducts:
                    byproduct = self.node.byproducts[0]
                    note = tr(self.language, "waste_note",
                              name=self._data.item_name(byproduct.item_id, self.language),
                              value=byproduct.amount)
                else:
                    note = tr(self.language, "generator_note")
                note = painter.fontMetrics().elidedText(note, Qt.TextElideMode.ElideRight, NODE_WIDTH - 26)
                painter.drawText(12, footer_y, note)
            else:
                peak = (tr(self.language, "peak_inline", value=self.node.peak_power_mw)
                        if self.node.peak_power_mw > self.node.power_mw + 0.01 else "")
                painter.drawText(12, footer_y, tr(self.language, "power_consumption"))
                power_value = painter.fontMetrics().elidedText(
                    f"{self.node.power_mw:.1f}{peak} MW", Qt.TextElideMode.ElideLeft, 105,
                )
                painter.drawText(QRectF(109, footer_y - 16, 105, 18),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 power_value)

    def set_dimmed(self, dimmed: bool) -> None:
        self.setOpacity(0.26 if dimmed else 1.0)

    def set_related_match(self, related: bool) -> None:
        self._related_match = related
        self.update()
