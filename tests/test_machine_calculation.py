"""Power shard, Somersloop, and factory power regression checks."""

import unittest
from pathlib import Path

from core.calculator import ProductionCalculator
from core.data_loader import load_production_data
from core.models import MachineSettings


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class MachineCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.calculator = ProductionCalculator(load_production_data(DATA_DIR))

    def test_shards_change_machine_count_and_power_not_material(self) -> None:
        base = self.calculator.calculate("Desc_IronIngot_C", 60, {})
        boosted = self.calculator.calculate(
            "Desc_IronIngot_C", 60, {}, {"root": MachineSettings(shards=3)}
        )
        self.assertEqual(base.children[0].required_rate, boosted.children[0].required_rate)
        self.assertEqual((base.installed_count, boosted.installed_count), (2, 1))
        self.assertAlmostEqual(base.power_mw, 8)
        self.assertGreater(boosted.power_mw, base.power_mw)

    def test_sloops_double_output_without_extra_material(self) -> None:
        base = self.calculator.calculate("Desc_IronIngot_C", 60, {})
        boosted = self.calculator.calculate(
            "Desc_IronIngot_C", 60, {}, {"root": MachineSettings(sloops=1)}
        )
        self.assertEqual(boosted.sloop_slots, 1)
        self.assertAlmostEqual(boosted.children[0].required_rate, base.children[0].required_rate / 2)
        self.assertEqual(boosted.installed_count, 1)
        self.assertAlmostEqual(boosted.power_mw, 16)
        self.assertEqual(self.calculator.summarize_power(boosted)[2:], (0, 1))

    def test_variable_power_building_has_nonzero_power_range(self) -> None:
        root = self.calculator.calculate("Desc_SpaceElevatorPart_9_C", 1, {})
        self.assertGreater(root.power_mw, 0)
        self.assertGreater(root.peak_power_mw, root.power_mw)

    def test_default_shards_apply_to_descendants(self) -> None:
        root = self.calculator.calculate("Desc_IronPlate_C", 20, {}, default_shards=2)
        self.assertEqual(root.shards, 2)
        self.assertEqual(root.children[0].shards, 2)


if __name__ == "__main__":
    unittest.main()
