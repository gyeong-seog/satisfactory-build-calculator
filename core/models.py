"""Domain objects shared by the calculation and presentation layers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    item_id: str
    name_ko: str
    name_en: str
    is_raw_resource: bool = False
    unit: str = "items"


@dataclass(frozen=True)
class Ingredient:
    item_id: str
    amount: float


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    name: str
    output_item_id: str
    output_amount: float
    duration_seconds: float
    building_id: str
    ingredients: tuple[Ingredient, ...]
    is_default: bool = False
    is_alternate: bool = False
    kind: str = "manufacturing"
    name_en: str = ""
    byproducts: tuple[Ingredient, ...] = ()
    generation_min_mw: float = 0.0
    generation_max_mw: float = 0.0
    grid_boost_fraction: float = 0.0
    site_limit: int = 0


@dataclass(frozen=True)
class BuildingSpec:
    name: str
    base_power_mw: float = 0.0
    power_exponent: float = 1.321929
    boost_power_exponent: float = 2.0
    sloop_slots: int = 0
    variable_min_mw: float = 0.0
    variable_max_mw: float = 0.0


@dataclass(frozen=True)
class MachineSettings:
    shards: int = 0
    sloops: int = 0


@dataclass
class ProductionNode:
    """One independently displayed production line in the tree."""

    node_id: str
    item_id: str
    item_name: str
    required_rate: float
    selected_recipe_id: str | None
    recipe_name: str
    building_id: str | None
    building_name: str
    building_count: float | None
    depth: int
    parent_id: str | None
    is_raw_resource: bool
    unit: str
    children: list["ProductionNode"] = field(default_factory=list)
    shards: int = 0
    sloops: int = 0
    sloop_slots: int = 0
    installed_count: int = 0
    power_mw: float = 0.0
    peak_power_mw: float = 0.0
    is_generator: bool = False
    generation_kind: str = ""
    generation_mw: float = 0.0
    generation_min_mw: float = 0.0
    generation_max_mw: float = 0.0
    existing_grid_mw: float = 0.0
    grid_boost_fraction: float = 0.0
    byproducts: list[Ingredient] = field(default_factory=list)
