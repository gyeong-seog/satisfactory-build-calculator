"""A deterministic left-to-right tree layout."""

from core.models import ProductionNode


class TreeLayoutEngine:
    NODE_WIDTH = 230
    NODE_HEIGHT = 258
    HORIZONTAL_GAP = 80
    VERTICAL_GAP = 28

    def layout(
        self,
        root: ProductionNode,
        completed: set[str] | None = None,
    ) -> dict[str, tuple[float, float]]:
        """Place every parent at the top edge of its first child branch."""

        completed = completed or set()
        positions: dict[str, tuple[float, float]] = {}
        subtree_heights: dict[str, float] = {}

        def measure(node: ProductionNode) -> float:
            visible_children = [] if node.node_id in completed else node.children
            if not visible_children:
                height = self.NODE_HEIGHT
            else:
                children_height = sum(measure(child) for child in visible_children)
                gaps_height = self.VERTICAL_GAP * (len(visible_children) - 1)
                height = max(self.NODE_HEIGHT, children_height + gaps_height)
            subtree_heights[node.node_id] = height
            return height

        def place(node: ProductionNode, top: float) -> None:
            x = node.depth * (self.NODE_WIDTH + self.HORIZONTAL_GAP)
            positions[node.node_id] = (x, top)

            visible_children = [] if node.node_id in completed else node.children
            child_top = top
            for child in visible_children:
                place(child, child_top)
                child_top += subtree_heights[child.node_id] + self.VERTICAL_GAP

        measure(root)
        place(root, 0.0)
        return positions
