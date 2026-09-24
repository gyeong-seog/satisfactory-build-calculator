"""Recursive production-tree calculation independent from Qt."""

from collections import defaultdict
from math import ceil

from .data_loader import ProductionData
from .models import Ingredient, MachineSettings, ProductionNode, Recipe


class CalculationError(ValueError):
    """A recoverable request or data problem shown to the user."""


class ProductionCalculator:
    def __init__(self, data: ProductionData):
        self.data = data

    def calculate(self, target_item_id: str, target_rate: float, selected_recipes: dict[str, str],
                  machine_settings: dict[str, MachineSettings] | None = None,
                  default_shards: int = 0, language: str = "ko",
                  existing_grid_mw: float = 0.0) -> ProductionNode:
        if target_item_id not in self.data.items:
            raise CalculationError("Unknown item." if language == "en" else "존재하지 않는 아이템입니다.")
        if target_rate <= 0:
            raise CalculationError("Target must be greater than zero." if language == "en" else "목표 생산량은 0보다 커야 합니다.")
        if default_shards not in range(4):
            raise CalculationError("Power Shards must be 0–3." if language == "en" else "동력핵은 0~3개여야 합니다.")
        if existing_grid_mw < 0:
            raise CalculationError("Existing grid power cannot be negative." if language == "en"
                                   else "기존 전력망 발전량은 0 이상이어야 합니다.")
        return self._build_node(target_item_id, target_rate, "root", 0, None, selected_recipes, set(),
                                machine_settings or {}, default_shards, language, existing_grid_mw)

    def summarize(self, root: ProductionNode) -> tuple[dict[str, float], dict[str, float]]:
        totals: dict[str, float] = defaultdict(float)
        raw_totals: dict[str, float] = defaultdict(float)

        def visit(node: ProductionNode) -> None:
            totals[node.item_id] += node.generation_mw if node.is_generator else node.required_rate
            if node.is_raw_resource:
                raw_totals[node.item_id] += node.required_rate
            for child in node.children:
                visit(child)

        visit(root)
        return dict(totals), dict(raw_totals)

    def summarize_byproducts(self, root: ProductionNode) -> dict[str, float]:
        byproducts: dict[str, float] = defaultdict(float)
        def visit(node: ProductionNode) -> None:
            for byproduct in node.byproducts:
                byproducts[byproduct.item_id] += byproduct.amount
            for child in node.children:
                visit(child)
        visit(root)
        return dict(byproducts)

    def summarize_power(self, root: ProductionNode) -> tuple[float, float, int, int]:
        """Return active/peak MW and installed shard/sloop totals, including collapsed lines."""
        active = peak = 0.0
        shards = sloops = 0
        def visit(node: ProductionNode) -> None:
            nonlocal active, peak, shards, sloops
            active += node.power_mw
            peak += node.peak_power_mw
            shards += node.shards * node.installed_count
            sloops += node.sloops * node.installed_count
            for child in node.children:
                visit(child)
        visit(root)
        return active, peak, shards, sloops

    def _build_node(self, item_id: str, rate: float, node_id: str, depth: int, parent_id: str | None,
                    selected_recipes: dict[str, str], ancestry: set[str],
                    machine_settings: dict[str, MachineSettings], default_shards: int,
                    language: str, existing_grid_mw: float) -> ProductionNode:
        item = self.data.items[item_id]
        if item_id in ancestry:
            name = self.data.item_name(item_id, language)
            raise CalculationError(f"Cyclic recipe: {name}" if language == "en" else f"순환 레시피를 감지했습니다: {name}")
        if item.is_raw_resource:
            return ProductionNode(
                node_id=node_id,
                item_id=item_id,
                item_name=self.data.item_name(item_id, language),
                required_rate=rate,
                selected_recipe_id=None,
                recipe_name="Raw resource" if language == "en" else "원자재",
                building_id=None,
                building_name="-",
                building_count=None,
                depth=depth,
                parent_id=parent_id,
                is_raw_resource=True,
                unit=item.unit,
            )

        recipe = self._selected_recipe(item_id, node_id, selected_recipes, language)
        spec = self.data.building_specs[recipe.building_id]
        settings = machine_settings.get(node_id, MachineSettings(default_shards, 0))
        is_generator = recipe.kind in ("generator", "geothermal", "augmenter")
        shards = 0 if is_generator else min(max(settings.shards, 0), 3)
        sloops = 0 if is_generator else min(max(settings.sloops, 0), spec.sloop_slots)
        clock = 1 + 0.5 * shards
        boost = 1 + sloops / spec.sloop_slots if spec.sloop_slots else 1.0
        per_machine_rate = recipe.output_amount * 60 / recipe.duration_seconds
        building_count = rate / (per_machine_rate * clock * boost)
        installed_count = ceil(building_count - 1e-10)
        generation_mw = generation_min_mw = generation_max_mw = 0.0
        if recipe.kind == "geothermal":
            if recipe.site_limit and installed_count > recipe.site_limit:
                raise CalculationError(
                    f"Only {recipe.site_limit} geysers of this purity are available."
                    if language == "en" else f"이 순도의 간헐천은 최대 {recipe.site_limit}곳입니다."
                )
            generation_mw = installed_count * per_machine_rate
            generation_min_mw = installed_count * recipe.generation_min_mw
            generation_max_mw = installed_count * recipe.generation_max_mw
        elif recipe.kind == "augmenter":
            installed_count = next((count for count in range(1, recipe.site_limit + 1)
                                    if (existing_grid_mw + count * per_machine_rate) *
                                    (1 + count * recipe.grid_boost_fraction) - existing_grid_mw >= rate), 0)
            if not installed_count:
                raise CalculationError(
                    "This target exceeds the available Power Augmenters."
                    if language == "en" else "사용 가능한 외계 전력 증폭기 수로는 이 목표를 달성할 수 없습니다."
                )
            building_count = float(installed_count)
            generation_mw = ((existing_grid_mw + installed_count * per_machine_rate) *
                             (1 + installed_count * recipe.grid_boost_fraction) - existing_grid_mw)
            generation_min_mw = generation_max_mw = generation_mw
        elif recipe.kind == "generator":
            generation_mw = generation_min_mw = generation_max_mw = rate
        power_mw = peak_power_mw = 0.0
        # Full machines run at the chosen clock. The last machine is underclocked
        # to meet the target rate; this avoids charging for unused capacity.
        for machine_index in range(installed_count if not is_generator else 0):
            fractional_load = min(1.0, max(0.0, building_count - machine_index))
            machine_clock = max(0.01, clock * fractional_load)
            boost_power = boost ** spec.boost_power_exponent
            if spec.variable_max_mw:
                average_base = (spec.variable_min_mw + spec.variable_max_mw) / 2
                peak_base = spec.variable_max_mw
            else:
                average_base = peak_base = spec.base_power_mw
            multiplier = machine_clock ** spec.power_exponent * boost_power
            power_mw += average_base * multiplier
            peak_power_mw += peak_base * multiplier
        node = ProductionNode(
            node_id=node_id,
            item_id=item_id,
            item_name=self.data.item_name(item_id, language),
            required_rate=rate,
            selected_recipe_id=recipe.recipe_id,
            recipe_name=self.data.recipe_name(recipe, language),
            building_id=recipe.building_id,
            building_name=self.data.building_name(recipe.building_id, language),
            building_count=building_count,
            depth=depth,
            parent_id=parent_id,
            is_raw_resource=False,
            unit=item.unit,
            shards=shards,
            sloops=sloops,
            sloop_slots=spec.sloop_slots,
            installed_count=installed_count,
            power_mw=power_mw,
            peak_power_mw=peak_power_mw,
            is_generator=is_generator,
            generation_kind=recipe.kind if is_generator else "",
            generation_mw=generation_mw,
            generation_min_mw=generation_min_mw,
            generation_max_mw=generation_max_mw,
            existing_grid_mw=existing_grid_mw if recipe.kind == "augmenter" else 0.0,
            grid_boost_fraction=recipe.grid_boost_fraction,
            byproducts=[Ingredient(byproduct.item_id,
                                   byproduct.amount * rate / recipe.output_amount)
                        for byproduct in recipe.byproducts],
        )
        next_ancestry = ancestry | {item_id}
        for index, ingredient in enumerate(recipe.ingredients):
            if recipe.kind == "augmenter":
                required_rate = installed_count * ingredient.amount
            else:
                required_rate = rate * ingredient.amount / (recipe.output_amount * boost)
            child_id = f"{node_id}/{index}:{ingredient.item_id}"
            node.children.append(self._build_node(
                ingredient.item_id, required_rate, child_id, depth + 1, node_id, selected_recipes, next_ancestry,
                machine_settings, default_shards, language, existing_grid_mw,
            ))
        return node

    def _selected_recipe(self, item_id: str, node_id: str, selected_recipes: dict[str, str],
                         language: str) -> Recipe:
        desired_id = selected_recipes.get(node_id)
        if desired_id:
            recipe = self.data.recipes.get(desired_id)
            if recipe and recipe.output_item_id == item_id:
                return recipe
        recipe = self.data.default_recipe_for(item_id)
        if recipe is None:
            name = self.data.item_name(item_id, language)
            raise CalculationError(f"No recipe for {name}." if language == "en" else f"{name}의 레시피가 없습니다.")
        return recipe
