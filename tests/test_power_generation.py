"""Generator fuel demand and electricity target regression tests."""

import unittest
from pathlib import Path

from core.calculator import CalculationError, ProductionCalculator
from core.data_loader import load_production_data


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class PowerGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_production_data(DATA_DIR)
        cls.calculator = ProductionCalculator(cls.data)

    def test_coal_generator_consumes_coal_and_water(self) -> None:
        root = self.calculator.calculate("Electricity_MW", 75, {})
        self.assertTrue(root.is_generator)
        self.assertEqual(root.unit, "mw")
        self.assertEqual(root.building_id, "Build_GeneratorCoal_C")
        self.assertEqual(root.installed_count, 1)
        demand = {child.item_id: child.required_rate for child in root.children}
        self.assertAlmostEqual(demand["Desc_Coal_C"], 15)
        self.assertAlmostEqual(demand["Desc_Water_C"], 45)
        self.assertEqual(self.data.items["Desc_Coal_C"].unit, "items")
        self.assertEqual(self.data.items["Desc_Water_C"].unit, "m3")
        self.assertAlmostEqual(self.calculator.summarize_power(root)[0], 0)

    def test_fuel_generator_uses_fluid_and_upstream_electricity(self) -> None:
        recipe_id = "Power_Build_GeneratorFuel_C_Desc_LiquidFuel_C"
        root = self.calculator.calculate("Electricity_MW", 250, {"root": recipe_id})
        self.assertEqual(root.installed_count, 1)
        self.assertEqual(root.children[0].item_id, "Desc_LiquidFuel_C")
        self.assertAlmostEqual(root.children[0].required_rate, 20)
        self.assertEqual(root.children[0].unit, "m3")
        self.assertGreater(self.calculator.summarize_power(root)[0], 0)

    def test_alternate_fuels_and_generator_count(self) -> None:
        recipes = self.data.recipes_for("Electricity_MW")
        self.assertEqual(len(recipes), 22)
        self.assertEqual(len(self.data.generator_building_ids()), 6)
        compacted = self.calculator.calculate(
            "Electricity_MW", 150,
            {"root": "Power_Build_GeneratorCoal_C_Desc_CompactedCoal_C"},
        )
        self.assertEqual(compacted.installed_count, 2)
        self.assertAlmostEqual(compacted.children[0].required_rate, 150 * 60 / 630)
        self.assertAlmostEqual(compacted.children[1].required_rate, 90)

    def test_biomass_burner_fuel_scales_with_requested_power(self) -> None:
        recipe = "Power_Build_GeneratorBiomass_Automated_C_Desc_Biofuel_C"
        root = self.calculator.calculate("Electricity_MW", 45, {"root": recipe})
        self.assertEqual(root.installed_count, 2)
        self.assertAlmostEqual(root.children[0].required_rate, 6)
        self.assertEqual(root.generation_mw, 45)

    def test_nuclear_rod_water_and_waste_variants(self) -> None:
        expected = (
            ("Desc_NuclearFuelRod_C", 0.2, "Desc_NuclearWaste_C", 10),
            ("Desc_PlutoniumFuelRod_C", 0.1, "Desc_PlutoniumWaste_C", 1),
            ("Desc_FicsoniumFuelRod_C", 1.0, None, 0),
        )
        for fuel_id, fuel_rate, waste_id, waste_rate in expected:
            with self.subTest(fuel_id=fuel_id):
                recipe = f"Power_Build_GeneratorNuclear_C_{fuel_id}"
                root = self.calculator.calculate("Electricity_MW", 2500, {"root": recipe})
                demand = {child.item_id: child.required_rate for child in root.children}
                self.assertAlmostEqual(demand[fuel_id], fuel_rate)
                self.assertAlmostEqual(demand["Desc_Water_C"], 240)
                self.assertEqual(self.calculator.summarize_byproducts(root).get(waste_id, 0), waste_rate)

    def test_geothermal_purity_range_and_site_limit(self) -> None:
        recipe = "Power_Build_GeneratorGeoThermal_C_Normal"
        root = self.calculator.calculate("Electricity_MW", 250, {"root": recipe})
        self.assertEqual(root.installed_count, 2)
        self.assertEqual(root.generation_mw, 400)
        self.assertEqual(root.generation_min_mw, 200)
        self.assertEqual(root.generation_max_mw, 600)
        self.assertFalse(root.children)
        with self.assertRaises(CalculationError):
            self.calculator.calculate("Electricity_MW", 2800, {"root": recipe})

    def test_alien_augmenter_uses_existing_grid_and_matrix(self) -> None:
        base = self.calculator.calculate(
            "Electricity_MW", 1000,
            {"root": "Power_Build_AlienPowerBuilding_C_Base"},
            existing_grid_mw=5000,
        )
        self.assertEqual(base.installed_count, 1)
        self.assertAlmostEqual(base.generation_mw, 1050)
        fueled = self.calculator.calculate(
            "Electricity_MW", 2000,
            {"root": "Power_Build_AlienPowerBuilding_C_Matrix"},
            existing_grid_mw=5000,
        )
        self.assertEqual(fueled.installed_count, 1)
        self.assertAlmostEqual(fueled.generation_mw, 2150)
        self.assertAlmostEqual(fueled.children[0].required_rate, 5)


if __name__ == "__main__":
    unittest.main()
