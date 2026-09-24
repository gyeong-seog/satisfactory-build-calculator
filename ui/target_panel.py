"""Target item selection and rate input."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QCompleter, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from core.data_loader import ProductionData
from .controls import ExternalSpinControl
from .i18n import tr, unit_label


class TargetPanel(QWidget):
    calculate_requested = Signal(str, float)
    generator_requested = Signal(str, float, float)
    global_shards_requested = Signal(int)

    def __init__(self, data: ProductionData, parent=None):
        super().__init__(parent)
        self.data = data
        self.language = "ko"
        self.item_input = QLineEdit("슈퍼컴퓨터")
        searchable_items = [item for item in data.items.values() if item.item_id != "Electricity_MW"]
        names = [item.name_ko for item in searchable_items] + [item.name_en for item in searchable_items]
        for building_id in data.generator_building_ids():
            names.extend(self._generator_names(building_id))
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.item_input.setCompleter(completer)

        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0.01, 100000.0)
        self.rate_input.setValue(10.0)
        self.rate_input.setDecimals(2)
        self.rate_label = QLabel()
        self.item_input.textChanged.connect(self._update_target_unit)
        self.grid_input = QDoubleSpinBox()
        self.grid_input.setRange(0, 1000000000)
        self.grid_input.setDecimals(2)
        self.grid_label = QLabel()

        self.create_button = QPushButton()
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._emit_request)
        self.item_input.returnPressed.connect(self._emit_request)

        # All controls live in one horizontal band above the graph.
        self.target_controls = QWidget(self)
        self.target_controls.setObjectName("targetControls")
        target_layout = QHBoxLayout(self.target_controls)
        self.target_layout = target_layout
        target_layout.setContentsMargins(12, 5, 12, 5)
        target_layout.setSpacing(8)
        self.heading = QLabel()
        self.heading.setStyleSheet("color: #e5a254; font-size: 14pt; font-weight: 700;")
        self.heading.setMinimumWidth(90)
        target_layout.addWidget(self.heading)

        self.product_label = QLabel()
        product_box = QVBoxLayout()
        product_box.setSpacing(2)
        product_box.addWidget(self.product_label)
        self.item_input.setFixedHeight(38)
        product_box.addWidget(self.item_input)
        self.item_input.setMinimumWidth(200)
        target_layout.addLayout(product_box, 2)

        rate_box = QVBoxLayout()
        rate_box.setSpacing(2)
        rate_box.addWidget(self.rate_label)
        self.rate_control = ExternalSpinControl(self.rate_input)
        self.rate_control.setMinimumWidth(128)
        self.rate_control.setFixedHeight(38)
        rate_box.addWidget(self.rate_control)
        target_layout.addLayout(rate_box, 1)

        self.grid_group = QWidget(self.target_controls)
        grid_box = QVBoxLayout(self.grid_group)
        grid_box.setContentsMargins(0, 0, 0, 0)
        grid_box.setSpacing(2)
        grid_box.addWidget(self.grid_label)
        self.grid_control = ExternalSpinControl(self.grid_input)
        self.grid_control.setMinimumWidth(148)
        self.grid_control.setFixedHeight(38)
        grid_box.addWidget(self.grid_control)
        target_layout.addWidget(self.grid_group)

        self.create_button.setMinimumWidth(164)
        self.create_button.setFixedHeight(38)
        target_layout.addWidget(self.create_button, alignment=Qt.AlignmentFlag.AlignBottom)

        shard_group = QWidget(self.target_controls)
        shard_group.setObjectName("shardGroup")
        shard_group.setMinimumWidth(172)
        shard_layout = QVBoxLayout(shard_group)
        shard_layout.setContentsMargins(4, 0, 4, 0)
        shard_layout.setSpacing(2)
        self.global_shards_label = QLabel()
        self.global_shards_label.setWordWrap(True)
        shard_layout.addWidget(self.global_shards_label)
        shard_row = QHBoxLayout()
        shard_row.setSpacing(5)
        self.shard_buttons = QButtonGroup(self)
        self.shard_buttons.setExclusive(True)
        for count in range(4):
            shard_button = QPushButton(str(count))
            shard_button.setFixedSize(42, 38)
            shard_button.setCheckable(True)
            shard_button.setChecked(count == 0)
            shard_button.clicked.connect(lambda checked=False, value=count: self.global_shards_requested.emit(value))
            self.shard_buttons.addButton(shard_button, count)
            shard_row.addWidget(shard_button)
        shard_layout.addLayout(shard_row)
        target_layout.addWidget(shard_group)

        self._legend_layout = QHBoxLayout()
        self._legend_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addLayout(self._legend_layout)
        self.set_language("ko")
        self.grid_group.hide()

    def set_legend(self, legend: QWidget) -> None:
        """Show the production-building key at the right end of the top band."""

        self._legend_layout.addWidget(legend)

    def _emit_request(self) -> None:
        query = self.item_input.text().strip()
        if not query:
            self.calculate_requested.emit("", self.rate_input.value())
            return
        generators = self.data.generator_building_ids()
        generator_id = next((building_id for building_id in generators
                             if self._normalized(query) in {
                                 self._normalized(name) for name in self._generator_names(building_id)
                             }), None)
        if generator_id is not None:
            self.item_input.setText(self.data.building_name(generator_id, self.language))
            grid = self.grid_input.value() if generator_id == "Build_AlienPowerBuilding_C" else 0.0
            self.generator_requested.emit(generator_id, self.rate_input.value(), grid)
            return
        matches = [item for item in self.data.search_items(query) if item.item_id != "Electricity_MW"]
        exact = next((item for item in matches if query.casefold() in {item.name_ko.casefold(), item.name_en.casefold()}), None)
        item = exact or (matches[0] if len(matches) == 1 else None)
        if item is None:
            self.calculate_requested.emit("", self.rate_input.value())
            return
        self.item_input.setText(self.data.item_name(item.item_id, self.language))
        self.calculate_requested.emit(item.item_id, self.rate_input.value())

    def _update_target_unit(self, text: str) -> None:
        generator_id = next((building_id for building_id in self.data.generator_building_ids()
                             if self._normalized(text) in {
                                 self._normalized(name) for name in self._generator_names(building_id)
                             }), None)
        exact = next((item for item in self.data.items.values() if item.item_id != "Electricity_MW"
                      if text.strip().casefold() in (item.name_ko.casefold(), item.name_en.casefold())), None)
        unit = "mw" if generator_id else exact.unit if exact else "items"
        self.rate_label.setText(tr(self.language, "target", unit=unit_label(unit, self.language)))
        show_grid = generator_id == "Build_AlienPowerBuilding_C"
        self.grid_group.setVisible(show_grid)

    @staticmethod
    def _normalized(text: str) -> str:
        return "".join(text.casefold().split())

    def _generator_names(self, building_id: str) -> tuple[str, ...]:
        aliases = {
            "Build_GeneratorBiomass_Automated_C": ("바이오매스 발전소", "바이오매스 연소기", "Biomass Generator"),
            "Build_GeneratorCoal_C": ("석탄 발전소", "Coal Generator"),
            "Build_GeneratorFuel_C": ("연료 발전소", "Fuel Generator"),
            "Build_GeneratorNuclear_C": ("원자력 발전소", "Nuclear Generator"),
            "Build_GeneratorGeoThermal_C": ("지열 발전소", "Geothermal Power Plant"),
            "Build_AlienPowerBuilding_C": ("외계 전력 증폭기", "Alien Power Booster"),
        }
        return (self.data.buildings[building_id], self.data.building_names_en[building_id],
                *aliases.get(building_id, ()))

    def set_current_target(self, item_id: str, generator_id: str | None = None) -> None:
        if generator_id:
            self.item_input.setText(self.data.building_name(generator_id, self.language))
        else:
            self.item_input.setText(self.data.item_name(item_id, self.language))

    def set_language(self, language: str) -> None:
        self.language = language
        self.item_input.setPlaceholderText(tr(language, "search_hint"))
        self.heading.setText(tr(language, "target_heading"))
        self.product_label.setText(tr(language, "product"))
        self.grid_label.setText(tr(language, "existing_grid"))
        self.create_button.setText(tr(language, "create"))
        self.global_shards_label.setText(tr(language, "global_shards"))
        for count in range(4):
            self.shard_buttons.button(count).setToolTip(tr(language, "global_shards_tip", count=count))
        self._update_target_unit(self.item_input.text())
