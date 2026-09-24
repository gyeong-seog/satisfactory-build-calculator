"""Aggregated production and raw-resource requirements."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.data_loader import ProductionData
from core.models import ProductionNode
from .i18n import tr, unit_label


class SummaryPanel(QScrollArea):
    def __init__(self, data: ProductionData, parent=None):
        super().__init__(parent)
        self.data = data
        self.language = "ko"
        self.setObjectName("summaryPanel")
        self.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName("summaryContent")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(18, 14, 18, 18)
        self.layout.setSpacing(6)
        self.setWidget(self.content)
        self.show_summary({}, {})

    def show_summary(self, totals: dict[str, float], raw_totals: dict[str, float],
                     power_summary: tuple[float, float, int, int] | None = None,
                     generation_node: ProductionNode | None = None,
                     byproducts: dict[str, float] | None = None) -> None:
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._add_title(tr(self.language, "generation_needs" if generation_node is not None else "total_needs"))
        self._add_rates(totals)
        self._add_title(tr(self.language, "raw_totals"))
        self._add_rates(raw_totals)
        if byproducts:
            self._add_title(tr(self.language, "waste_title"))
            self._add_rates(byproducts)
        if power_summary is not None:
            active, peak, shards, sloops = power_summary
            if generation_node is not None:
                generation_mw = generation_node.generation_mw
                self._add_title(tr(self.language, "generation_plan"))
                gross_key = "added_generation" if generation_node.generation_kind == "augmenter" else "gross"
                self._add_metric(tr(self.language, gross_key, value=generation_mw))
                if generation_node.generation_kind == "geothermal":
                    self._add_metric(tr(self.language, "minimum_generation", value=generation_node.generation_min_mw))
                    self._add_metric(tr(self.language, "maximum_generation", value=generation_node.generation_max_mw))
                if generation_node.generation_kind == "augmenter":
                    self._add_metric(tr(self.language, "existing_generation", value=generation_node.existing_grid_mw))
                    self._add_metric(tr(self.language, "augmented_grid", value=generation_node.existing_grid_mw + generation_mw))
                self._add_metric(tr(self.language, "factory_use", value=active))
                self._add_metric(tr(self.language, "net", value=generation_mw - active))
                generator_note = QLabel(tr(self.language, "generator_note_summary"))
                generator_note.setWordWrap(True)
                generator_note.setStyleSheet("color: #aab3b9; font-size: 9pt;")
                self.layout.addWidget(generator_note)
            self._add_title(tr(self.language, "power_resources"))
            if generation_node is None:
                self._add_metric(tr(self.language, "total_power", value=active), emphasized=True)
            if peak > active + 0.01:
                self._add_metric(tr(self.language, "peak_power", value=peak))
            self._add_metric(tr(self.language, "shards_installed", value=shards))
            self._add_metric(tr(self.language, "sloops_installed", value=sloops))
            note = QLabel(tr(self.language, "power_note"))
            note.setWordWrap(True)
            note.setStyleSheet("color: #aab3b9; font-size: 9pt;")
            self.layout.addWidget(note)
        self.layout.addStretch()

    def _add_title(self, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet(
            "background: transparent; color: #e8ad55; font-size: 11pt; font-weight: 700; "
            "border-bottom: 1px solid #3b4953; padding: 10px 0 7px 0;"
        )
        self.layout.addWidget(label)

    def _add_metric(self, text: str, emphasized: bool = False) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        if emphasized:
            label.setStyleSheet("background: transparent; color: #e8ad55; font-size: 11pt; font-weight: 700; padding: 4px 2px;")
        else:
            label.setStyleSheet("background: transparent; color: #dbe1e4; padding: 3px 2px;")
        self.layout.addWidget(label)

    def _add_rates(self, rates: dict[str, float]) -> None:
        if not rates:
            self.layout.addWidget(QLabel(tr(self.language, "no_result")))
            return
        for item_id, rate in sorted(rates.items(), key=lambda value: self.data.item_name(value[0], self.language)):
            item = self.data.items[item_id]
            unit = unit_label(item.unit, self.language)
            row = QWidget(self.content)
            row.setObjectName("summaryRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(2, 3, 2, 3)
            name = QLabel(self.data.item_name(item_id, self.language), row)
            name.setWordWrap(True)
            amount = QLabel(f"{rate:.2f} {unit}", row)
            amount.setStyleSheet("background: transparent; color: #e8ad55; font-weight: 700;")
            row_layout.addWidget(name)
            row_layout.addStretch()
            row_layout.addWidget(amount)
            self.layout.addWidget(row)
