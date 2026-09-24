"""JSON loading with validation and convenient recipe lookup."""

import json
from pathlib import Path

from .models import BuildingSpec, Ingredient, Item, Recipe


GENERATOR_KO_NAMES = {
    "Build_GeneratorBiomass_Automated_C": "바이오매스 발전기",
    "Build_GeneratorCoal_C": "석탄 발전기",
    "Build_GeneratorFuel_C": "연료 발전기",
    "Build_GeneratorNuclear_C": "원자력 발전기",
    "Build_GeneratorGeoThermal_C": "지열 발전기",
}


class DataError(ValueError):
    """Raised when the prototype data cannot be read safely."""


class ProductionData:
    def __init__(self, items: dict[str, Item], recipes: dict[str, Recipe], buildings: dict[str, str],
                 building_specs: dict[str, BuildingSpec] | None = None,
                 building_names_en: dict[str, str] | None = None):
        self.items = items
        self.recipes = recipes
        self.buildings = buildings
        self.building_specs = building_specs or {key: BuildingSpec(name) for key, name in buildings.items()}
        self.building_names_en = building_names_en or buildings
        self.recipes_by_output: dict[str, list[Recipe]] = {}

        for recipe in recipes.values():
            self.recipes_by_output.setdefault(recipe.output_item_id, []).append(recipe)

    def recipes_for(self, item_id: str) -> list[Recipe]:
        return self.recipes_by_output.get(item_id, [])

    def default_recipe_for(self, item_id: str) -> Recipe | None:
        recipes = self.recipes_for(item_id)
        return next((recipe for recipe in recipes if recipe.is_default), recipes[0] if recipes else None)

    def search_items(self, query: str) -> list[Item]:
        normalized = query.strip().casefold()
        if not normalized:
            return list(self.items.values())
        return [
            item for item in self.items.values()
            if normalized in item.name_ko.casefold() or normalized in item.name_en.casefold()
        ]

    def item_name(self, item_id: str, language: str) -> str:
        item = self.items[item_id]
        return item.name_en if language == "en" else item.name_ko

    def recipe_name(self, recipe: Recipe, language: str) -> str:
        return (recipe.name_en or recipe.name) if language == "en" else recipe.name.replace("발전소", "발전기")

    def building_name(self, building_id: str, language: str) -> str:
        return self.building_names_en.get(building_id, self.buildings[building_id]) if language == "en" else self.buildings[building_id]

    def generator_building_ids(self) -> list[str]:
        return list(dict.fromkeys(recipe.building_id for recipe in self.recipes_for("Electricity_MW")
                                  if recipe.kind in ("generator", "geothermal", "augmenter")))


def load_production_data(data_dir: Path) -> ProductionData:
    try:
        items_raw = _read_json(data_dir / "items.json")
        recipes_raw = _read_json(data_dir / "recipes.json")
        buildings_raw = _read_json(data_dir / "buildings.json")
    except OSError as error:
        raise DataError(f"데이터 파일을 읽을 수 없습니다: {error}") from error

    try:
        items = {
            value["id"]: Item(
                item_id=value["id"],
                name_ko=value["name_ko"],
                name_en=value["name_en"],
                is_raw_resource=value.get("is_raw_resource", False),
                unit=value.get("unit", "items"),
            )
            for value in items_raw
        }
        buildings = {value["id"]: value["name_ko"] for value in buildings_raw}
        buildings.update({key: value for key, value in GENERATOR_KO_NAMES.items() if key in buildings})
        building_names_en = {value["id"]: value.get("name_en", value["name_ko"]) for value in buildings_raw}
        building_specs = {
            value["id"]: BuildingSpec(
                name=value["name_ko"],
                base_power_mw=float(value.get("base_power_mw", 0)),
                power_exponent=float(value.get("power_exponent", 1.321929)),
                boost_power_exponent=float(value.get("boost_power_exponent", 2)),
                sloop_slots=int(value.get("sloop_slots", 0)),
                variable_min_mw=float(value.get("variable_min_mw", 0)),
                variable_max_mw=float(value.get("variable_max_mw", 0)),
            ) for value in buildings_raw
        }
        recipes = {
            value["id"]: Recipe(
                recipe_id=value["id"],
                name=value["name"],
                output_item_id=value["output_item_id"],
                output_amount=float(value["output_amount"]),
                duration_seconds=float(value["duration_seconds"]),
                building_id=value["building_id"],
                ingredients=tuple(Ingredient(item_id=i["item_id"], amount=float(i["amount"])) for i in value["ingredients"]),
                is_default=value.get("is_default", False),
                is_alternate=value.get("is_alternate", False),
                kind=value.get("kind", "manufacturing"),
                name_en=value.get("name_en", value["name"]),
                byproducts=tuple(Ingredient(item_id=i["item_id"], amount=float(i["amount"]))
                                 for i in value.get("byproducts", [])),
                generation_min_mw=float(value.get("generation_min_mw", 0)),
                generation_max_mw=float(value.get("generation_max_mw", 0)),
                grid_boost_fraction=float(value.get("grid_boost_fraction", 0)),
                site_limit=int(value.get("site_limit", 0)),
            )
            for value in recipes_raw
        }
    except (KeyError, TypeError, ValueError) as error:
        raise DataError(f"데이터 형식이 올바르지 않습니다: {error}") from error

    for recipe in recipes.values():
        if recipe.output_item_id not in items or recipe.building_id not in buildings:
            raise DataError(f"레시피 참조를 찾을 수 없습니다: {recipe.recipe_id}")
        if recipe.output_amount <= 0 or recipe.duration_seconds <= 0:
            raise DataError(f"레시피 생산량 또는 시간이 0 이하입니다: {recipe.recipe_id}")
        for ingredient in recipe.ingredients:
            if ingredient.item_id not in items or ingredient.amount <= 0:
                raise DataError(f"레시피 재료가 올바르지 않습니다: {recipe.recipe_id}")
        for byproduct in recipe.byproducts:
            if byproduct.item_id not in items or byproduct.amount <= 0:
                raise DataError(f"발전 부산물이 올바르지 않습니다: {recipe.recipe_id}")
        if recipe.kind in ("generator", "geothermal", "augmenter") and items[recipe.output_item_id].unit != "mw":
            raise DataError(f"발전 레시피 출력 단위가 올바르지 않습니다: {recipe.recipe_id}")

    return ProductionData(items, recipes, buildings, building_specs, building_names_en)


def _read_json(path: Path) -> list[dict]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError as error:
        raise DataError(f"잘못된 JSON 파일입니다 ({path.name}): {error.msg}") from error
    if not isinstance(value, list):
        raise DataError(f"{path.name}의 최상위 값은 목록이어야 합니다.")
    return value
