"""Scene assembly, visibility, highlighting, and graph navigation."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsView

from core.data_loader import ProductionData
from core.models import ProductionNode
from ui.i18n import tr
from .connection_item import ConnectionItem
from .layout_engine import TreeLayoutEngine
from .production_node import ProductionNodeItem


NODE_WIDTH = TreeLayoutEngine.NODE_WIDTH


class ProductionScene(QGraphicsScene):
    recipe_selection_changed = Signal(str, str)
    completion_changed = Signal(str)
    settings_changed = Signal(str, str, int)
    selection_summary_changed = Signal(str)

    def __init__(self, data: ProductionData, parent=None):
        super().__init__(parent)
        self.data = data
        self.root: ProductionNode | None = None
        self.completed: set[str] = set()
        self.node_items: dict[str, ProductionNodeItem] = {}
        self.connection_items: list[tuple[str, str, ConnectionItem]] = []
        self.layout_engine = TreeLayoutEngine()
        self.manual_positions: dict[str, tuple[float, float]] = {}
        self.layout_locked = False
        self.language = "ko"
        self.selectionChanged.connect(self._update_highlighting)

    def set_tree(self, root: ProductionNode, completed: set[str] | None = None) -> None:
        # Scene.clear() can emit selectionChanged while Qt is deleting old cards.
        # Clear our references first and suppress that transient selection update.
        self.blockSignals(True)
        self.node_items.clear()
        self.connection_items.clear()
        self.clear()
        self.root = root
        self.completed = completed or set()
        positions = self.layout_engine.layout(root, self.completed)
        positions.update({key: value for key, value in self.manual_positions.items() if key in positions})

        def add_nodes(node: ProductionNode) -> None:
            item = ProductionNodeItem(
                node, self.data, node is root, node.node_id in self.completed,
                self.recipe_selection_changed.emit, self.completion_changed.emit,
                self.settings_changed.emit, self._node_moved,
                self.language, not self.layout_locked,
            )
            item.setPos(*positions[node.node_id])
            self.addItem(item)
            self.node_items[node.node_id] = item
            if node.node_id in self.completed:
                return
            for child in node.children:
                add_nodes(child)

        def add_connections(node: ProductionNode) -> None:
            if node.node_id in self.completed:
                return
            parent_item = self.node_items[node.node_id]
            for child in node.children:
                child_item = self.node_items[child.node_id]
                source, target = self._endpoints(parent_item, child_item)
                connection = ConnectionItem(source, target)
                self.addItem(connection)
                self.connection_items.append((node.node_id, child.node_id, connection))
                add_connections(child)

        try:
            add_nodes(root)
            add_connections(root)
            self.setSceneRect(self.itemsBoundingRect().adjusted(-80, -80, 80, 80))
        finally:
            self.blockSignals(False)
        self.selection_summary_changed.emit("")

    @staticmethod
    def _endpoints(parent_item: ProductionNodeItem, child_item: ProductionNodeItem):
        source = parent_item.pos() + parent_item.boundingRect().center()
        target = child_item.pos() + child_item.boundingRect().center()
        if source.x() <= target.x():
            source.setX(parent_item.pos().x() + NODE_WIDTH)
            target.setX(child_item.pos().x())
        else:
            source.setX(parent_item.pos().x())
            target.setX(child_item.pos().x() + NODE_WIDTH)
        return source, target

    def _node_moved(self, node_id: str) -> None:
        item = self.node_items.get(node_id)
        if item is None:
            return
        self.manual_positions[node_id] = (item.pos().x(), item.pos().y())
        for parent_id, child_id, connection in self.connection_items:
            if node_id in (parent_id, child_id):
                source, target = self._endpoints(self.node_items[parent_id], self.node_items[child_id])
                connection.update_endpoints(source, target)
        self.setSceneRect(self.itemsBoundingRect().adjusted(-80, -80, 80, 80))
        for view in self.views():
            if isinstance(view, ProductionGraphicsView):
                view.update_pan_bounds()

    def reset_layout(self) -> None:
        self.manual_positions.clear()
        if self.root is not None:
            self.set_tree(self.root, self.completed)

    def set_layout_locked(self, locked: bool) -> None:
        self.layout_locked = locked
        for item in self.node_items.values():
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    def _update_highlighting(self) -> None:
        selected = self.selectedItems()
        if not selected:
            for item in self.node_items.values():
                item.set_dimmed(False)
                item.set_related_match(False)
            for _, _, connection in self.connection_items:
                connection.set_dimmed(False)
            self.selection_summary_changed.emit("")
            return

        selected_item = next((item for item in selected if isinstance(item, ProductionNodeItem)), None)
        if not selected_item:
            return
        active = self._descendant_ids(selected_item.node.node_id)
        same_product = {
            node_id
            for node_id, item in self.node_items.items()
            if item.node.item_id == selected_item.node.item_id
        }
        visible = active | same_product
        for node_id, item in self.node_items.items():
            item.set_related_match(node_id in same_product and node_id != selected_item.node.node_id)
            item.set_dimmed(node_id not in visible)
        for parent_id, child_id, connection in self.connection_items:
            connection.set_dimmed(parent_id not in active or child_id not in active)
        self.selection_summary_changed.emit(
            tr(self.language, "same_product", name=selected_item.node.item_name, count=len(same_product))
        )

    def _descendant_ids(self, root_id: str) -> set[str]:
        result = {root_id}
        waiting = [root_id]
        while waiting:
            parent_id = waiting.pop()
            for candidate_id, item in self.node_items.items():
                if item.node.parent_id == parent_id:
                    result.add(candidate_id)
                    waiting.append(candidate_id)
        return result


class ProductionGraphicsView(QGraphicsView):
    def __init__(self, scene: ProductionScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#0b151b"))

    def drawBackground(self, painter: QPainter, rect) -> None:
        """Add a restrained construction grid behind the diagram."""

        super().drawBackground(painter, rect)
        step = 80
        left = int(rect.left() // step) * step
        top = int(rect.top() // step) * step
        painter.setPen(QPen(QColor("#1b2932"), 1))
        x = left
        while x <= rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += step
        y = top
        while y <= rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += step

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self.update_pan_bounds()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_pan_bounds()

    def fit_graph(self) -> None:
        if self.scene().items():
            content = self.scene().itemsBoundingRect().adjusted(-80, -80, 80, 80)
            self.resetTransform()
            scale = min(
                1.0,
                max(1, self.viewport().width() - 16) / max(content.width(), 1),
                max(1, self.viewport().height() - 16) / max(content.height(), 1),
            )
            self.scale(scale, scale)
            self.update_pan_bounds()
            self.centerOn(content.center())

    def update_pan_bounds(self) -> None:
        """Keep an extra viewport of scrollable space around the graph at any zoom."""
        if not self.scene().items():
            return
        content = self.scene().itemsBoundingRect().adjusted(-80, -80, 80, 80)
        scale = max(self.transform().m11(), 0.001)
        horizontal = max(self.viewport().width() / scale, 400)
        vertical = max(self.viewport().height() / scale, 400)
        self.setSceneRect(content.adjusted(-horizontal, -vertical, horizontal, vertical))
