"""Persistence and manual-progress tests for self-quest projects."""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.calculator import ProductionCalculator
from core.data_loader import load_production_data
from core.projects import ProjectManager


class ProjectManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_production_data(PROJECT_ROOT / "data")
        cls.root = ProductionCalculator(cls.data).calculate(
            next(item.item_id for item in cls.data.items.values()
                 if item.name_en == "Supercomputer"),
            10.0,
            {},
        )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "projects.json"
        self.manager = ProjectManager(self.data, self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_snapshot_preserves_recipe_inputs_and_machine_plan(self) -> None:
        task = self.manager.add_snapshot(self.root.item_id, 10.0, self.root)
        self.assertEqual(task.item_id, self.root.item_id)
        self.assertEqual(task.recipe_id, self.root.selected_recipe_id)
        self.assertEqual(task.required_buildings, 6)
        self.assertGreater(len(task.ingredients), 0)
        self.assertEqual(task.completion_type, "MANUAL")
        self.assertTrue(self.path.exists())

    def test_manual_progress_completion_and_reload(self) -> None:
        task = self.manager.add_snapshot(self.root.item_id, 10.0, self.root)
        self.manager.adjust_installed(task.task_id, 1)
        self.assertEqual(task.installed_buildings, 1)
        self.assertEqual(task.status, "in_progress")

        self.manager.toggle_complete(task.task_id)
        self.assertEqual(task.status, "complete")
        self.assertTrue(task.manual_locked)
        self.manager.adjust_installed(task.task_id, 1)
        self.assertEqual(task.installed_buildings, 1)

        restored = ProjectManager(self.data, self.path)
        restored_task = restored.active_project.tasks[0]
        self.assertEqual(restored_task.status, "complete")
        self.assertTrue(restored_task.manual_locked)
        self.assertEqual(restored_task.installed_buildings, 1)

        restored.toggle_complete(restored_task.task_id)
        self.assertEqual(restored_task.status, "in_progress")
        self.assertFalse(restored_task.manual_locked)

    def test_same_card_is_not_duplicated(self) -> None:
        first = self.manager.add_snapshot(self.root.item_id, 10.0, self.root)
        second = self.manager.add_snapshot(self.root.item_id, 10.0, self.root)
        self.assertEqual(first.task_id, second.task_id)
        self.assertEqual(len(self.manager.active_project.tasks), 1)

    def test_selected_subtree_is_captured_in_preorder(self) -> None:
        expected = []

        def visit(node, depth):
            expected.append((node.node_id, depth))
            for child in node.children:
                visit(child, depth + 1)

        selected = self.root.children[0]
        visit(selected, 0)
        tasks = self.manager.add_subtree_snapshot(self.root.item_id, 10.0, selected)
        self.assertEqual([task.source_key.split("|", 1)[0] for task in tasks],
                         [node_id for node_id, _ in expected])
        self.assertEqual([task.tree_depth for task in tasks],
                         [depth for _, depth in expected])

    def test_clear_active_project_removes_goals_from_storage(self) -> None:
        self.manager.add_subtree_snapshot(self.root.item_id, 10.0, self.root.children[0])
        self.manager.clear_active_project()
        self.assertEqual(self.manager.projects, [])
        self.assertEqual(self.manager.active_project_id, "")
        restored = ProjectManager(self.data, self.path)
        self.assertEqual(restored.projects, [])


if __name__ == "__main__":
    unittest.main()
