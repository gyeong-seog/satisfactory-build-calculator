"""Shared production-card colors and visual constants."""


BUILDING_COLORS = {
    "Build_ConstructorMk1_C": "#22B5A5",
    "Build_AssemblerMk1_C": "#4A8FE7",
    "Build_ManufacturerMk1_C": "#8067D8",
    "Build_SmelterMk1_C": "#E46A47",
    "Build_FoundryMk1_C": "#C94D68",
    "Build_OilRefinery_C": "#E7A23B",
    "Build_Packager_C": "#7D91A5",
    "Build_Blender_C": "#3387C8",
    "Build_HadronCollider_C": "#B550B8",
    "Build_Converter_C": "#5968D8",
    "Build_QuantumEncoder_C": "#A34FE3",
    "Build_GeneratorCoal_C": "#98A3AD",
    "Build_GeneratorFuel_C": "#C0CF42",
    "Build_GeneratorBiomass_Automated_C": "#4DBD65",
    "Build_GeneratorNuclear_C": "#EC5EAC",
    "Build_GeneratorGeoThermal_C": "#45C9DD",
    "Build_AlienPowerBuilding_C": "#E06AD4",
}

RAW_RESOURCE_COLOR = "#3C9360"
COMPLETED_COLOR = "#38A17A"
UNKNOWN_BUILDING_COLOR = "#62717C"
TARGET_BORDER_COLOR = "#E9B550"


def color_for_building(building_id: str | None) -> str:
    return BUILDING_COLORS.get(building_id, UNKNOWN_BUILDING_COLOR)
