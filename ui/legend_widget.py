"""Compact multi-column legend for the top control band."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QWidget

from core.data_loader import ProductionData
from core.models import ProductionNode
from graphics.style import BUILDING_COLORS, COMPLETED_COLOR, RAW_RESOURCE_COLOR
from .i18n import tr


class BuildingLegend(QFrame):
    def __init__(self, data: ProductionData, parent=None):
        super().__init__(parent)
        self.data = data
        self.language = "ko"
        self.setObjectName("buildingLegend")
        self.setStyleSheet(
            "#buildingLegend { background: #101a21; "
            "border: 1px solid #34434d; border-radius: 6px; }"
            "#buildingLegend QWidget, #buildingLegend QLabel { background: transparent; border: none; }"
            "#buildingLegend QLabel { color: #e7eaec; font-size: 8pt; }"
        )
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(7, 4, 7, 4)
        self.layout.setHorizontalSpacing(7)
        self.layout.setVerticalSpacing(1)
        self._entry_index = 0

    def set_tree(self, root: ProductionNode, completed: set[str]) -> None:
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        title = QLabel(tr(self.language, "legend_title"))
        title.setStyleSheet("background: transparent; color: #e5a254; font-weight: 700; font-size: 8pt;")
        self.layout.addWidget(title, 0, 0, 1, 3)
        self._entry_index = 0

        building_ids: set[str] = set()
        includes_raw = False

        def visit(node: ProductionNode) -> None:
            nonlocal includes_raw
            if node.is_raw_resource:
                includes_raw = True
            elif node.building_id:
                building_ids.add(node.building_id)
            if node.node_id in completed:
                return
            for child_node in node.children:
                visit(child_node)

        visit(root)
        for building_id in sorted(building_ids, key=lambda value: self.data.building_name(value, self.language)):
            self._add_entry(BUILDING_COLORS.get(building_id, "#5E6875"),
                            self.data.building_name(building_id, self.language))
        if includes_raw:
            self._add_entry(RAW_RESOURCE_COLOR, tr(self.language, "legend_raw"))
        if completed:
            self._add_entry(COMPLETED_COLOR, tr(self.language, "legend_done"))

        self.adjustSize()

    def _add_entry(self, color: str, text: str) -> None:
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        swatch = QFrame(row)
        swatch.setFixedSize(11, 11)
        swatch.setStyleSheet(f"background: {color}; border: 1px solid #52616b; border-radius: 3px;")
        row_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(QLabel(text, row))
        grid_row = 1 + self._entry_index // 3
        grid_column = self._entry_index % 3
        self.layout.addWidget(row, grid_row, grid_column)
        self._entry_index += 1
