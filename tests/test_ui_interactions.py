"""Regression tests for widget-triggered scene rebuilds."""

import os
import sys
import unittest
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QComboBox, QGraphicsItem, QGraphicsProxyWidget, QLabel, QSpinBox, QToolButton
from PySide6.QtTest import QTest

from graphics.production_node import RecipeComboBox
from ui.controls import ExternalComboControl, ExternalSpinControl
from ui.global_hotkey import GlobalHotkeyManager
from ui.main_window import MainWindow


def embedded_widgets(item, widget_type):
    result = []
    for child in item.childItems():
        if not isinstance(child, QGraphicsProxyWidget):
            continue
        root = child.widget()
        if isinstance(root, widget_type):
            result.append(root)
        result.extend(root.findChildren(widget_type))
    return result


class UiInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MainWindow(PROJECT_ROOT / "data")

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def test_completion_click_can_rebuild_and_cancel(self) -> None:
        target_node = self.window.scene.root.children[0]
        node_id = target_node.node_id
        child_ids = {
            child.node_id
            for child in target_node.children
        }

        for expected_completed in (True, False):
            item = self.window.scene.node_items[node_id]
            button = next(
                proxy.widget()
                for proxy in item.childItems()
                if isinstance(proxy.widget(), QToolButton)
            )
            button.click()
            self.app.processEvents()

            self.assertEqual(node_id in self.window.completed, expected_completed)
            visible_ids = set(self.window.scene.node_items)
            if expected_completed:
                self.assertTrue(child_ids.isdisjoint(visible_ids))
            else:
                self.assertTrue(child_ids.issubset(visible_ids))

    def test_recipe_combo_rebuild_is_deferred(self) -> None:
        target_node = next(
            node
            for node in self.window.scene.root.children
            if len(self.window.data.recipes_for(node.item_id)) > 1
        )
        node_id = target_node.node_id
        item = self.window.scene.node_items[node_id]
        combo = embedded_widgets(item, QComboBox)[0]

        expected_recipe_id = combo.itemData(1)
        combo.setCurrentIndex(1)
        self.app.processEvents()

        rebuilt_node = next(
            node for node in self.window.scene.root.children if node.node_id == node_id
        )
        self.assertEqual(rebuilt_node.selected_recipe_id, expected_recipe_id)

    def test_parent_and_first_child_are_top_aligned(self) -> None:
        root = self.window.scene.root
        root_y = self.window.scene.node_items[root.node_id].pos().y()
        first_child_y = self.window.scene.node_items[root.children[0].node_id].pos().y()
        second_child_y = self.window.scene.node_items[root.children[1].node_id].pos().y()

        self.assertEqual(root_y, first_child_y)
        self.assertGreater(second_child_y, first_child_y)

    def test_selecting_one_item_marks_other_visible_instances(self) -> None:
        scene = self.window.scene
        counts = Counter(item.node.item_id for item in scene.node_items.values())
        repeated_id = next(item_id for item_id, count in counts.items() if count > 1)
        matches = [item for item in scene.node_items.values() if item.node.item_id == repeated_id]

        matches[0].setSelected(True)
        self.app.processEvents()

        self.assertTrue(all(item.opacity() == 1 for item in matches))
        self.assertTrue(all(item._related_match for item in matches[1:]))
        self.assertIn(f"{len(matches)}곳", self.window.selection_hint.text())

        scene.clearSelection()
        self.app.processEvents()
        self.assertTrue(all(not item._related_match for item in matches))

    def test_all_settings_are_above_graph_and_left_dock_is_removed(self) -> None:
        self.window.show()
        self.app.processEvents()

        self.assertTrue(self.window.target_panel.target_controls.isAncestorOf(self.window.legend))
        self.assertIs(self.window.target_controls_dock.widget(), self.window.target_panel.target_controls)
        self.assertEqual(self.window.dockWidgetArea(self.window.target_controls_dock),
                         Qt.DockWidgetArea.TopDockWidgetArea)
        self.assertFalse(hasattr(self.window, "target_dock"))
        self.assertEqual(self.window.view.geometry().left(), 0)
        self.assertFalse(hasattr(self.window.target_panel, "move_hint"))
        self.assertEqual(self.window.summary_dock.geometry().top(),
                         self.window.target_controls_dock.geometry().top())

    def test_create_and_global_shard_buttons_share_height(self) -> None:
        panel = self.window.target_panel
        heights = [panel.create_button.height()]
        heights.extend(panel.shard_buttons.button(index).height() for index in range(4))
        self.assertEqual(heights, [38, 38, 38, 38, 38])

    def test_target_product_and_rate_fields_share_height(self) -> None:
        panel = self.window.target_panel
        self.assertEqual(panel.item_input.height(), 38)
        self.assertEqual(panel.rate_control.height(), 38)

    def test_input_arrows_are_separate_from_editor_fields(self) -> None:
        self.window.show()
        self.app.processEvents()
        panel = self.window.target_panel
        self.assertIsInstance(panel.rate_control, ExternalSpinControl)
        self.assertEqual(panel.rate_input.buttonSymbols(), panel.rate_input.ButtonSymbols.NoButtons)
        up_left = panel.rate_control.up_button.mapTo(panel.rate_control, QPoint(0, 0)).x()
        self.assertGreater(up_left, panel.rate_input.geometry().right())

        root_item = self.window.scene.node_items["root"]
        combo_control = next(
            child.widget() for child in root_item.childItems()
            if isinstance(child, QGraphicsProxyWidget)
            and isinstance(child.widget(), ExternalComboControl)
        )
        combo_right = combo_control.combo.geometry().right()
        button_left = combo_control.drop_button.geometry().left()
        self.assertGreater(button_left, combo_right)

    def test_generator_display_names_use_generator_term(self) -> None:
        generator_names = [
            self.window.data.buildings[building_id]
            for building_id in self.window.data.generator_building_ids()
            if building_id != "Build_AlienPowerBuilding_C"
        ]
        self.assertTrue(all("발전기" in name for name in generator_names))
        self.assertTrue(all("발전소" not in name for name in generator_names))

    def test_global_shards_and_per_card_override(self) -> None:
        self.window.target_panel.shard_buttons.button(3).click()
        self.app.processEvents()
        root = self.window.scene.root
        self.assertEqual(root.shards, 3)
        self.assertEqual(root.children[0].shards, 3)
        root_item = self.window.scene.node_items[root.node_id]
        spins = embedded_widgets(root_item, QSpinBox)
        spins[0].setValue(1)
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.shards, 1)
        self.assertEqual(self.window.scene.root.children[0].shards, 3)

    def test_moved_card_and_connection_survive_rebuild(self) -> None:
        scene = self.window.scene
        child_id = scene.root.children[0].node_id
        item = scene.node_items[child_id]
        old_pos = item.pos()
        edge = next(connection for parent, child, connection in scene.connection_items
                    if child == child_id)
        old_end = edge.path().pointAtPercent(1)
        item.setPos(old_pos.x() + 80, old_pos.y() + 60)
        self.assertNotEqual(edge.path().pointAtPercent(1), old_end)
        self.window._schedule_rebuild()
        self.app.processEvents()
        self.assertAlmostEqual(scene.node_items[child_id].pos().x(), old_pos.x() + 80)
        self.assertAlmostEqual(scene.node_items[child_id].pos().y(), old_pos.y() + 60)
        scene.reset_layout()
        self.assertEqual(scene.node_items[child_id].pos(), old_pos)

    def test_generator_recipe_list_is_limited_to_selected_building(self) -> None:
        panel = self.window.target_panel
        panel.item_input.setText("석탄 발전소")
        self.assertEqual(panel.rate_label.text(), "목표 (MW)")
        panel.rate_input.setValue(250)
        panel._emit_request()
        self.app.processEvents()
        root = self.window.scene.root
        self.assertTrue(root.is_generator)
        self.assertEqual(root.building_id, "Build_GeneratorCoal_C")
        item = self.window.scene.node_items[root.node_id]
        combo = embedded_widgets(item, QComboBox)[0]
        self.assertEqual(combo.count(), 3)
        self.assertTrue(all(
            self.window.data.recipes[combo.itemData(index)].building_id == "Build_GeneratorCoal_C"
            for index in range(combo.count())
        ))
        self.assertEqual(combo.findData("Power_Build_GeneratorFuel_C_Desc_LiquidFuel_C"), -1)
        self.assertEqual(item.toolTip(), self.window.data.buildings["Build_GeneratorCoal_C"])

        panel.item_input.setText("연료 발전소")
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_GeneratorFuel_C")
        self.assertEqual(panel.item_input.text(), self.window.data.buildings["Build_GeneratorFuel_C"])
        self.assertEqual(self.window.scene.root.children[0].unit, "m3")
        fuel_item = self.window.scene.node_items["root"]
        fuel_combo = embedded_widgets(fuel_item, QComboBox)[0]
        self.assertEqual(fuel_combo.count(), 5)
        self.assertTrue(all(
            self.window.data.recipes[fuel_combo.itemData(index)].building_id == "Build_GeneratorFuel_C"
            for index in range(fuel_combo.count())
        ))
        labels = [label.text() for label in self.window.summary_panel.findChildren(QLabel)]
        self.assertTrue(any("총 발전량: 250.00 MW" in text for text in labels))
        self.assertTrue(any("m³/min" in text for text in labels))
        panel.item_input.setText("석탄")
        self.assertEqual(panel.rate_label.text(), "목표 (개/min)")

    def test_layout_uses_compact_readable_horizontal_gap(self) -> None:
        root = self.window.scene.root
        child = root.children[0]
        root_x = self.window.scene.node_items[root.node_id].pos().x()
        child_x = self.window.scene.node_items[child.node_id].pos().x()
        self.assertEqual(child_x - root_x, 230 + 80)

    def test_fuel_generator_name_starts_with_fuel_recipe(self) -> None:
        panel = self.window.target_panel
        panel.item_input.setText("연료발전소")
        self.assertEqual(panel.rate_label.text(), "목표 (MW)")
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_GeneratorFuel_C")
        self.assertEqual(self.window.scene.root.children[0].item_id, "Desc_LiquidFuel_C")
        self.window.language_combo.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(panel.item_input.text(), "Fuel-Powered Generator")
        self.assertEqual(self.window.scene.root.building_name, "Fuel-Powered Generator")
        root_item = self.window.scene.node_items["root"]
        combo = embedded_widgets(root_item, QComboBox)[0]
        self.assertIn("Fuel-Powered Generator", combo.currentText())

    def test_layout_lock_survives_rebuild(self) -> None:
        self.window.layout_lock_action.setChecked(True)
        item = self.window.scene.node_items["root"]
        self.assertFalse(item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.window._schedule_rebuild()
        self.app.processEvents()
        self.assertFalse(self.window.scene.node_items["root"].flags() &
                         QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.window.layout_lock_action.setChecked(False)
        self.assertTrue(self.window.scene.node_items["root"].flags() &
                        QGraphicsItem.GraphicsItemFlag.ItemIsMovable)

    def test_language_switch_preserves_graph_state(self) -> None:
        scene = self.window.scene
        child_id = scene.root.children[0].node_id
        item = scene.node_items[child_id]
        item.setPos(item.pos().x() + 42, item.pos().y() + 25)
        moved = scene.manual_positions[child_id]
        self.window.completed.add(child_id)
        self.window._schedule_rebuild()
        self.app.processEvents()
        self.window.language_combo.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(self.window.language, "en")
        self.assertEqual(scene.root.item_name, "Supercomputer")
        self.assertIn(child_id, self.window.completed)
        self.assertEqual(scene.manual_positions[child_id], moved)
        self.assertEqual(self.window.target_panel.rate_label.text(), "Target (items/min)")
        self.assertEqual(self.window.fit_action.text(), "Fit All")
        self.window.language_combo.setCurrentIndex(0)
        self.app.processEvents()
        self.assertEqual(scene.root.item_name, "슈퍼컴퓨터")

    def test_recipe_popup_is_raised_above_spinboxes(self) -> None:
        item = self.window.scene.node_items["root"]
        combo = embedded_widgets(item, QComboBox)[0]
        combo_proxy = next(
            child for child in item.childItems()
            if isinstance(child, QGraphicsProxyWidget) and combo in child.widget().findChildren(QComboBox)
        )
        self.assertGreater(combo_proxy.zValue(), 0)
        self.window.show()
        self.app.processEvents()
        combo.showPopup()
        self.assertGreater(item.zValue(), 0)
        combo.hidePopup()
        self.assertEqual(item.zValue(), 0)

    def test_recipe_popup_scrolls_only_after_ten_entries(self) -> None:
        item = self.window.scene.node_items["root"]
        combo = embedded_widgets(item, RecipeComboBox)[0]
        self.assertLessEqual(combo.count(), 10)
        self.assertEqual(combo.view().verticalScrollBarPolicy(),
                         Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        long_combo = RecipeComboBox(item)
        for index in range(11):
            long_combo.addItem(f"Recipe {index}")
        long_combo.configure_popup()
        self.assertEqual(long_combo.maxVisibleItems(), 10)
        self.assertEqual(long_combo.view().verticalScrollBarPolicy(),
                         Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        long_combo.deleteLater()

    def test_compact_top_bars_and_wider_scrollbar(self) -> None:
        self.window.show()
        self.app.processEvents()
        toolbar_gap = (self.window.language_label.geometry().left()
                       - self.window.top_checkbox.geometry().right())
        self.assertGreaterEqual(toolbar_gap, 18)
        self.assertEqual(self.window.language_label.text(), "🌐")
        self.assertEqual(self.window.language_combo.itemText(0), "한국어")
        self.assertEqual(self.window.language_combo.itemText(1), "English")
        self.assertIn("background: transparent", self.window.language_spacer.styleSheet())
        self.assertIsNone(self.window.createPopupMenu())
        self.assertEqual(self.window.summary_dock.objectName(), "summaryDock")
        self.assertEqual(self.window.summary_divider.width(), 2)
        self.assertIn("#60717d", self.window.summary_divider.styleSheet())
        self.assertLessEqual(self.window.target_controls_dock.height(), 102)
        self.assertEqual(self.window.summary_panel.verticalScrollBar().sizeHint().width(), 13)

    def test_tray_controls_follow_language_selector(self) -> None:
        self.window.show()
        self.app.processEvents()
        self.assertLess(self.window.language_combo.geometry().right(),
                        self.window.shortcut_button.geometry().left())
        self.assertLess(self.window.shortcut_button.geometry().right(),
                        self.window.quit_button.geometry().left())
        self.assertEqual(self.window.shortcut_button.text(), "단축키 설정")
        self.assertEqual(self.window.quit_button.text(), "완전 종료")

    def test_global_hotkey_requires_modifier_and_toggles_visibility(self) -> None:
        self.assertIsNone(GlobalHotkeyManager._to_native(QKeySequence("S")))
        self.assertIsNotNone(GlobalHotkeyManager._to_native(QKeySequence("Ctrl+Shift+S")))
        self.window.show()
        self.app.processEvents()
        self.window._toggle_visibility()
        self.assertFalse(self.window.isVisible())
        self.window._toggle_visibility()
        self.assertTrue(self.window.isVisible())

    def test_fit_all_keeps_pan_room(self) -> None:
        self.window.show()
        QTest.qWait(90)
        self.app.processEvents()
        view = self.window.view
        view.fit_graph()
        self.app.processEvents()
        content = view.scene().itemsBoundingRect()
        self.assertGreater(view.sceneRect().width(), content.width())
        self.assertGreater(view.horizontalScrollBar().maximum(), view.horizontalScrollBar().minimum())
        old_center = view.mapToScene(view.viewport().rect().center())
        view.centerOn(old_center.x() + 400, old_center.y())
        self.app.processEvents()
        new_center = view.mapToScene(view.viewport().rect().center())
        self.assertGreater(new_center.x(), old_center.x())

    def test_remaining_generator_names_and_existing_grid_input(self) -> None:
        panel = self.window.target_panel
        panel.item_input.setText("바이오매스 연소기")
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_GeneratorBiomass_Automated_C")
        panel.item_input.setText("원자력 발전소")
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_GeneratorNuclear_C")
        self.assertIn("Desc_NuclearWaste_C", self.window.calculator.summarize_byproducts(self.window.scene.root))
        panel.item_input.setText("지열 발전소")
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_GeneratorGeoThermal_C")
        self.assertEqual(self.window.scene.root.generation_kind, "geothermal")
        panel.item_input.setText("외계 전력 증폭기")
        self.assertFalse(panel.grid_input.isHidden())
        panel.grid_input.setValue(5000)
        panel.rate_input.setValue(1000)
        panel._emit_request()
        self.app.processEvents()
        self.assertEqual(self.window.scene.root.building_id, "Build_AlienPowerBuilding_C")
        self.assertAlmostEqual(self.window.scene.root.generation_mw, 1050)

    def test_single_generator_fit_does_not_enlarge_card(self) -> None:
        panel = self.window.target_panel
        panel.item_input.setText("지열 발전소")
        panel._emit_request()
        self.window.show()
        QTest.qWait(90)
        self.app.processEvents()
        self.window.view.fit_graph()
        self.assertLessEqual(self.window.view.transform().m11(), 1.0)


if __name__ == "__main__":
    unittest.main()
