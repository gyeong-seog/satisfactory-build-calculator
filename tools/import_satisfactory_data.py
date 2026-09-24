"""Convert localized Satisfactory Docs files into the application's data format."""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ITEM_PATTERN = re.compile(
    r'ItemClass="[^"]*\.([A-Za-z0-9_]+)\'",Amount=([0-9.eE+\-]+)'
)
BUILDING_PATTERN = re.compile(r'\.([A-Za-z0-9_]+)"')
FLUID_FORMS = {"RF_LIQUID", "RF_GAS"}


def load_docs(path: Path) -> list[dict]:
    """Load a UTF-16 localized Docs JSON file."""

    return json.loads(path.read_bytes().decode("utf-16"))


def classes_by_id(groups: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for group in groups:
        for value in group.get("Classes", []):
            class_name = value.get("ClassName")
            if class_name:
                result[class_name] = value
    return result


def classes_for_native(groups: list[dict], native_fragment: str) -> list[dict]:
    for group in groups:
        if native_fragment in group.get("NativeClass", ""):
            return group.get("Classes", [])
    return []


def parse_item_amounts(value: str) -> list[tuple[str, float]]:
    return [(item_id, float(amount)) for item_id, amount in ITEM_PATTERN.findall(value)]


def normalized_amount(item: dict, amount: float) -> float:
    if item.get("mForm") in FLUID_FORMS:
        return amount / 1000.0
    return amount


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("data/source"))
    parser.add_argument("--output", type=Path, default=Path("data"))
    args = parser.parse_args()

    english_path = args.source / "en-US.json"
    korean_path = args.source / "ko.json"
    english_groups = load_docs(english_path)
    korean_groups = load_docs(korean_path)
    english = classes_by_id(english_groups)
    korean = classes_by_id(korean_groups)

    raw_ids = {
        value["ClassName"]
        for value in classes_for_native(english_groups, "FactoryGame.FGResourceDescriptor")
    }

    building_values: dict[str, dict] = {}
    for group in english_groups:
        native = group.get("NativeClass", "")
        if "FGBuildableManufacturer" not in native:
            continue
        for value in group.get("Classes", []):
            building_values[value["ClassName"]] = value
    supported_buildings = set(building_values)

    source_recipes = classes_for_native(english_groups, "FactoryGame.FGRecipe")
    converted_recipes: list[dict] = []
    referenced_item_ids: set[str] = set()

    for source_recipe in source_recipes:
        if source_recipe.get("mRelevantEvents"):
            continue

        produced_in = BUILDING_PATTERN.findall(source_recipe.get("mProducedIn", ""))
        building_id = next((value for value in produced_in if value in supported_buildings), None)
        if building_id is None:
            continue

        products = parse_item_amounts(source_recipe.get("mProduct", ""))
        ingredients = parse_item_amounts(source_recipe.get("mIngredients", ""))
        if not products:
            continue

        output_item_id, output_amount = products[0]
        if output_item_id not in english:
            raise ValueError(f"Unknown output item: {output_item_id}")

        converted_ingredients = []
        for item_id, amount in ingredients:
            item = english.get(item_id)
            if item is None:
                raise ValueError(f"Unknown ingredient item: {item_id}")
            converted_ingredients.append(
                {
                    "item_id": item_id,
                    "amount": normalized_amount(item, amount),
                }
            )
            referenced_item_ids.add(item_id)

        recipe_id = source_recipe["ClassName"]
        english_name = source_recipe.get("mDisplayName", recipe_id)
        korean_name = korean.get(recipe_id, {}).get("mDisplayName", english_name)
        is_alternate = recipe_id.startswith("Recipe_Alternate_") or english_name.startswith("Alternate:")

        converted_recipes.append(
            {
                "id": recipe_id,
                "name": korean_name,
                "name_en": english_name,
                "output_item_id": output_item_id,
                "output_amount": normalized_amount(english[output_item_id], output_amount),
                "duration_seconds": float(source_recipe["mManufactoringDuration"]),
                "building_id": building_id,
                "ingredients": converted_ingredients,
                "is_default": False,
                "is_alternate": is_alternate,
                "menu_priority": float(source_recipe.get("mManufacturingMenuPriority", 0)),
            }
        )
        referenced_item_ids.add(output_item_id)

    recipes_by_output: dict[str, list[dict]] = defaultdict(list)
    for recipe in converted_recipes:
        recipes_by_output[recipe["output_item_id"]].append(recipe)

    for output_id, recipes in recipes_by_output.items():
        output_name = english[output_id].get("mDisplayName", "")
        recipes.sort(
            key=lambda recipe: (
                recipe["name_en"] != output_name,
                recipe["building_id"] == "Build_Packager_C",
                recipe["is_alternate"],
                recipe["menu_priority"],
                recipe["id"],
            )
        )
        recipes[0]["is_default"] = True

    converted_recipes.sort(key=lambda recipe: (recipe["output_item_id"], not recipe["is_default"], recipe["id"]))
    for recipe in converted_recipes:
        recipe.pop("menu_priority")

    produced_item_ids = set(recipes_by_output)
    items = []
    for item_id in sorted(referenced_item_ids):
        english_item = english[item_id]
        korean_item = korean.get(item_id, {})
        form = english_item.get("mForm", "RF_SOLID")
        items.append(
            {
                "id": item_id,
                "name_ko": korean_item.get("mDisplayName", english_item.get("mDisplayName", item_id)),
                "name_en": english_item.get("mDisplayName", item_id),
                # Collectibles, reactor waste, and other non-manufactured inputs
                # are terminal nodes even when they are not mineral resources.
                "is_raw_resource": item_id in raw_ids or item_id not in produced_item_ids,
                "unit": "m3" if form in FLUID_FORMS else "items",
            }
        )

    buildings = []
    for building_id in sorted(supported_buildings):
        value = building_values[building_id]
        can_boost = value.get("mCanChangeProductionBoost") == "True"
        boost_step = float(value.get("mProductionShardBoostMultiplier", 0) or 0)
        buildings.append(
            {
                "id": building_id,
                "name_ko": korean.get(building_id, {}).get("mDisplayName", value.get("mDisplayName", building_id)),
                "name_en": value.get("mDisplayName", building_id),
                "base_power_mw": float(value.get("mPowerConsumption", 0) or 0),
                "power_exponent": float(value.get("mPowerConsumptionExponent", 1.321929) or 1.321929),
                "boost_power_exponent": float(value.get("mProductionBoostPowerConsumptionExponent", 2) or 2),
                "sloop_slots": round(1 / boost_step) if can_boost and boost_step else 0,
                "variable_min_mw": float(value.get("mEstimatedMininumPowerConsumption", 0) or 0),
                "variable_max_mw": float(value.get("mEstimatedMaximumPowerConsumption", 0) or 0),
            }
        )

    # A generator's output is power (MW), not a manufactured item per minute.
    # Fuel energy is MJ per solid item, or MJ per mL for liquids/gases in Docs.
    electricity_id = "Electricity_MW"
    items.append({
        "id": electricity_id, "name_ko": "전기", "name_en": "Electricity",
        "is_raw_resource": False, "unit": "mw",
    })
    generator_ids = (
        "Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C",
        "Build_GeneratorFuel_C", "Build_GeneratorNuclear_C",
    )
    for generator_id in generator_ids:
        generator = english[generator_id]
        generator_name = korean.get(generator_id, {}).get("mDisplayName", generator.get("mDisplayName", generator_id))
        generator_mw = float(generator["mPowerProduction"])
        buildings.append({
            "id": generator_id, "name_ko": generator_name,
            "name_en": generator.get("mDisplayName", generator_id),
            "base_power_mw": 0, "sloop_slots": 0,
        })
        for fuel_index, fuel_entry in enumerate(generator["mFuel"]):
            fuel_id = fuel_entry["mFuelClass"]
            fuel = english[fuel_id]
            fuel_energy = float(fuel["mEnergyValue"])
            if fuel_energy <= 0:
                raise ValueError(f"No fuel energy value for {fuel_id}")
            fuel_per_min = generator_mw * 60 / fuel_energy
            if fuel.get("mForm") in FLUID_FORMS:
                fuel_per_min /= 1000
            ingredients = [{"item_id": fuel_id, "amount": fuel_per_min}]
            if generator_id == "Build_GeneratorCoal_C":
                # Coal generators need 45 m³/min water at 75 MW, regardless of fuel.
                ingredients.append({"item_id": "Desc_Water_C", "amount": 45.0})
            if generator_id == "Build_GeneratorNuclear_C":
                ingredients.append({"item_id": "Desc_Water_C", "amount": 240.0})
            byproducts = []
            waste_id = fuel_entry.get("mByproduct", "")
            if waste_id:
                byproducts.append({
                    "item_id": waste_id,
                    "amount": fuel_per_min * float(fuel_entry["mByproductAmount"]),
                })
                referenced_item_ids.add(waste_id)
            fuel_name = korean.get(fuel_id, {}).get("mDisplayName", fuel.get("mDisplayName", fuel_id))
            converted_recipes.append({
                "id": f"Power_{generator_id}_{fuel_id}",
                "name": f"{generator_name} · {fuel_name}",
                "name_en": f"{generator.get('mDisplayName', generator_id)} · {fuel.get('mDisplayName', fuel_id)}",
                "output_item_id": electricity_id,
                "output_amount": generator_mw,
                "duration_seconds": 60.0,
                "building_id": generator_id,
                "ingredients": ingredients,
                "byproducts": byproducts,
                "is_default": generator_id == "Build_GeneratorCoal_C" and fuel_index == 0,
                "is_alternate": False,
                "kind": "generator",
            })
            referenced_item_ids.add(fuel_id)
            if generator_id in ("Build_GeneratorCoal_C", "Build_GeneratorNuclear_C"):
                referenced_item_ids.add("Desc_Water_C")

    geothermal_id = "Build_GeneratorGeoThermal_C"
    geothermal = english[geothermal_id]
    geothermal_name = korean.get(geothermal_id, {}).get("mDisplayName", geothermal.get("mDisplayName", geothermal_id))
    buildings.append({
        "id": geothermal_id, "name_ko": geothermal_name,
        "name_en": geothermal.get("mDisplayName", geothermal_id),
        "base_power_mw": 0, "sloop_slots": 0,
    })
    # Purity-dependent ranges are not present in Docs; use the game's geyser
    # purity multipliers and the generator's 200 MW normal-purity average.
    geothermal_average = float(geothermal["mVariablePowerProductionFactor"])
    for purity, korean_purity, multiplier, site_limit in (
        ("Impure", "저순도", 0.5, 9),
        ("Normal", "보통", 1.0, 13),
        ("Pure", "고순도", 2.0, 9),
    ):
        average = geothermal_average * multiplier
        converted_recipes.append({
            "id": f"Power_{geothermal_id}_{purity}",
            "name": f"{geothermal_name} · {korean_purity}",
            "name_en": f"{geothermal.get('mDisplayName', geothermal_id)} · {purity}",
            "output_item_id": electricity_id,
            "output_amount": average,
            "duration_seconds": 60.0,
            "building_id": geothermal_id,
            "ingredients": [],
            "is_default": False,
            "kind": "geothermal",
            "generation_min_mw": average / 2,
            "generation_max_mw": average * 1.5,
            "site_limit": site_limit,
        })

    augmenter_id = "Build_AlienPowerBuilding_C"
    augmenter = english[augmenter_id]
    augmenter_name = korean.get(augmenter_id, {}).get("mDisplayName", augmenter.get("mDisplayName", augmenter_id))
    buildings.append({
        "id": augmenter_id, "name_ko": augmenter_name,
        "name_en": augmenter.get("mDisplayName", augmenter_id),
        "base_power_mw": 0, "sloop_slots": 0,
    })
    matrix_id = "Desc_AlienPowerFuel_C"
    matrix = english[matrix_id]
    matrix_rate = 60 / float(matrix["mBoostDuration"])
    base_boost = float(augmenter["mBaseBoostPercentage"])
    for fueled in (False, True):
        suffix = "Matrix" if fueled else "Base"
        converted_recipes.append({
            "id": f"Power_{augmenter_id}_{suffix}",
            "name": f"{augmenter_name} · {'전력 매트릭스' if fueled else '기본'}",
            "name_en": f"{augmenter.get('mDisplayName', augmenter_id)} · {'Power Matrix' if fueled else 'Base'}",
            "output_item_id": electricity_id,
            "output_amount": float(augmenter["mBasePowerProduction"]),
            "duration_seconds": 60.0,
            "building_id": augmenter_id,
            "ingredients": [{"item_id": matrix_id, "amount": matrix_rate}] if fueled else [],
            "is_default": False,
            "kind": "augmenter",
            "grid_boost_fraction": base_boost + (float(matrix["mBoostPercentage"]) if fueled else 0),
            "site_limit": 10,
        })
    referenced_item_ids.add(matrix_id)

    known_items = {item["id"] for item in items}
    for item_id in sorted(referenced_item_ids - known_items):
        english_item = english[item_id]
        form = english_item.get("mForm", "RF_SOLID")
        items.append({
            "id": item_id,
            "name_ko": korean.get(item_id, {}).get("mDisplayName", english_item.get("mDisplayName", item_id)),
            "name_en": english_item.get("mDisplayName", item_id),
            "is_raw_resource": item_id in raw_ids or item_id not in produced_item_ids,
            "unit": "m3" if form in FLUID_FORMS else "items",
        })

    metadata = {
        "source": "Satisfactory CommunityResources/Docs localized files",
        "en-US_sha256": hashlib.sha256(english_path.read_bytes()).hexdigest(),
        "ko_sha256": hashlib.sha256(korean_path.read_bytes()).hexdigest(),
        "item_count": len(items),
        "recipe_count": len(converted_recipes),
        "building_count": len(buildings),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "items.json", items)
    write_json(args.output / "recipes.json", converted_recipes)
    write_json(args.output / "buildings.json", buildings)
    write_json(args.output / "import_metadata.json", metadata)

    print(
        f"Imported {len(items)} items, {len(converted_recipes)} recipes, "
        f"and {len(buildings)} buildings."
    )
    return 0


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
