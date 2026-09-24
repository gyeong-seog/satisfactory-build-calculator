"""Persistent manual projects built from production-calculation snapshots."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QStandardPaths, Signal

from core.data_loader import ProductionData
from core.models import ProductionNode


@dataclass
class ProjectIngredient:
    item_id: str
    name_ko: str
    name_en: str
    rate: float
    unit: str


@dataclass
class ProjectTask:
    task_id: str
    source_key: str
    item_id: str
    name_ko: str
    name_en: str
    target_rate: float
    unit: str
    recipe_id: str
    recipe_name_ko: str
    recipe_name_en: str
    is_alternate: bool
    building_id: str
    building_name_ko: str
    building_name_en: str
    calculated_buildings: float
    required_buildings: int
    installed_buildings: int
    ingredients: list[ProjectIngredient] = field(default_factory=list)
    shards: int = 0
    sloops: int = 0
    power_mw: float = 0.0
    status: str = "pending"
    completion_type: str = "MANUAL"
    manual_locked: bool = False
    created_at: str = ""
    tree_depth: int = 0

    @classmethod
    def from_dict(cls, value: dict) -> "ProjectTask":
        payload = dict(value)
        payload["ingredients"] = [ProjectIngredient(**item) for item in value.get("ingredients", [])]
        payload.setdefault("tree_depth", 0)
        return cls(**payload)


@dataclass
class Project:
    project_id: str
    source_target_id: str
    source_target_rate: float
    name_ko: str
    name_en: str
    tasks: list[ProjectTask] = field(default_factory=list)
    created_at: str = ""

    @classmethod
    def from_dict(cls, value: dict) -> "Project":
        payload = dict(value)
        payload["tasks"] = [ProjectTask.from_dict(item) for item in value.get("tasks", [])]
        return cls(**payload)


class ProjectManager(QObject):
    """Own projects independently of whether progress comes from UI or a future adapter."""

    changed = Signal()
    active_project_changed = Signal(str)

    def __init__(self, data: ProductionData, storage_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.data = data
        self.storage_path = storage_path or self.default_storage_path()
        self.projects: list[Project] = []
        self.active_project_id = ""
        self.load()

    @staticmethod
    def default_storage_path() -> Path:
        base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        return base / "projects.json"

    @property
    def active_project(self) -> Project | None:
        return next((project for project in self.projects
                     if project.project_id == self.active_project_id), None)

    def add_snapshot(self, target_id: str, target_rate: float, node: ProductionNode,
                     tree_depth: int = 0, commit: bool = True) -> ProjectTask:
        project = self._project_for(target_id, target_rate)
        source_key = f"{node.node_id}|{node.item_id}|{node.selected_recipe_id or ''}"
        existing = next((task for task in project.tasks if task.source_key == source_key), None)
        if existing is not None:
            self.set_active_project(project.project_id)
            return existing

        item = self.data.items[node.item_id]
        recipe = self.data.recipes.get(node.selected_recipe_id or "")
        ingredients: dict[str, ProjectIngredient] = {}
        for child in node.children:
            child_item = self.data.items[child.item_id]
            current = ingredients.get(child.item_id)
            if current is None:
                ingredients[child.item_id] = ProjectIngredient(
                    child.item_id, child_item.name_ko, child_item.name_en,
                    child.required_rate, child.unit,
                )
            else:
                current.rate += child.required_rate

        building_id = node.building_id or ""
        task = ProjectTask(
            task_id=uuid4().hex,
            source_key=source_key,
            item_id=node.item_id,
            name_ko=item.name_ko,
            name_en=item.name_en,
            target_rate=node.required_rate,
            unit=node.unit,
            recipe_id=node.selected_recipe_id or "",
            recipe_name_ko=recipe.name if recipe else node.recipe_name,
            recipe_name_en=(recipe.name_en or recipe.name) if recipe else node.recipe_name,
            is_alternate=bool(recipe and recipe.is_alternate),
            building_id=building_id,
            building_name_ko=self.data.buildings.get(building_id, node.building_name),
            building_name_en=self.data.building_names_en.get(building_id, node.building_name),
            calculated_buildings=float(node.building_count or 0),
            required_buildings=max(0, math.ceil(node.building_count or 0)),
            # Calculator "installed_count" is the rounded planning count, not
            # evidence of buildings already placed in the game. Manual quests
            # therefore always begin at zero.
            installed_buildings=0,
            ingredients=list(ingredients.values()),
            shards=node.shards,
            sloops=node.sloops,
            power_mw=node.power_mw,
            created_at=datetime.now(timezone.utc).isoformat(),
            tree_depth=tree_depth,
        )
        project.tasks.append(task)
        self.active_project_id = project.project_id
        if commit:
            self.save()
            self.changed.emit()
            self.active_project_changed.emit(project.project_id)
        return task

    def add_subtree_snapshot(self, target_id: str, target_rate: float,
                             node: ProductionNode) -> list[ProjectTask]:
        """Capture the selected card and every production card below it."""

        tasks: list[ProjectTask] = []

        def visit(current: ProductionNode, depth: int) -> None:
            tasks.append(self.add_snapshot(
                target_id, target_rate, current, tree_depth=depth, commit=False,
            ))
            for child in current.children:
                visit(child, depth + 1)

        visit(node, 0)
        self.save()
        self.changed.emit()
        if self.active_project_id:
            self.active_project_changed.emit(self.active_project_id)
        return tasks

    def _project_for(self, target_id: str, target_rate: float) -> Project:
        project = next((value for value in self.projects
                        if value.source_target_id == target_id
                        and abs(value.source_target_rate - target_rate) < 0.000001), None)
        if project is not None:
            return project
        item = self.data.items[target_id]
        if item.unit == "mw":
            suffix_ko = suffix_en = " MW"
        elif item.unit == "m3":
            suffix_ko = suffix_en = " m³/min"
        else:
            suffix_ko = suffix_en = "/min"
        project = Project(
            project_id=uuid4().hex,
            source_target_id=target_id,
            source_target_rate=target_rate,
            name_ko=f"{item.name_ko} {target_rate:g}{suffix_ko}",
            name_en=f"{item.name_en} {target_rate:g}{suffix_en}",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.projects.append(project)
        return project

    def set_active_project(self, project_id: str) -> None:
        if project_id == self.active_project_id:
            return
        if not any(project.project_id == project_id for project in self.projects):
            return
        self.active_project_id = project_id
        self.save()
        self.active_project_changed.emit(project_id)
        self.changed.emit()

    def adjust_installed(self, task_id: str, delta: int) -> None:
        task = self._task(task_id)
        if task is None or task.manual_locked:
            return
        task.installed_buildings = max(0, task.installed_buildings + delta)
        if task.required_buildings and task.installed_buildings >= task.required_buildings:
            task.status = "complete"
        elif task.installed_buildings > 0:
            task.status = "in_progress"
        else:
            task.status = "pending"
        task.completion_type = "MANUAL"
        self._commit()

    def toggle_complete(self, task_id: str) -> None:
        task = self._task(task_id)
        if task is None:
            return
        completed = task.status != "complete"
        task.status = "complete" if completed else (
            "in_progress" if task.installed_buildings else "pending"
        )
        task.completion_type = "MANUAL"
        task.manual_locked = completed
        self._commit()

    def remove_task(self, task_id: str) -> None:
        project = self.active_project
        if project is None:
            return
        project.tasks = [task for task in project.tasks if task.task_id != task_id]
        if not project.tasks:
            self.projects = [value for value in self.projects if value.project_id != project.project_id]
            self.active_project_id = self.projects[-1].project_id if self.projects else ""
        self._commit()

    def clear_active_project(self) -> None:
        """Remove the currently displayed goal set and select the next one."""

        project = self.active_project
        if project is None:
            return
        self.projects = [value for value in self.projects if value.project_id != project.project_id]
        self.active_project_id = self.projects[-1].project_id if self.projects else ""
        self.save()
        self.changed.emit()
        self.active_project_changed.emit(self.active_project_id)

    def _task(self, task_id: str) -> ProjectTask | None:
        return next((task for project in self.projects for task in project.tasks
                     if task.task_id == task_id), None)

    def _commit(self) -> None:
        self.save()
        self.changed.emit()

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "active_project_id": self.active_project_id,
            "projects": [asdict(project) for project in self.projects],
        }
        temporary = self.storage_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.storage_path)

    def load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
            self.projects = [Project.from_dict(value) for value in payload.get("projects", [])]
            requested = str(payload.get("active_project_id", ""))
            self.active_project_id = requested if any(
                project.project_id == requested for project in self.projects
            ) else (self.projects[0].project_id if self.projects else "")
        except (OSError, ValueError, TypeError, KeyError):
            # A damaged optional project file must never prevent the calculator
            # itself from starting. The original file is left untouched.
            self.projects = []
            self.active_project_id = ""
