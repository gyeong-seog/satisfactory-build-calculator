"""Orthogonal production relationship connection."""

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem


class ConnectionItem(QGraphicsPathItem):
    def __init__(self, source: QPointF, target: QPointF):
        super().__init__()
        self.update_endpoints(source, target)
        self.setPen(QPen(QColor("#7f8e98"), 2))
        self.setZValue(-1)

    def update_endpoints(self, source: QPointF, target: QPointF) -> None:
        midpoint_x = (source.x() + target.x()) / 2
        path = QPainterPath(source)
        path.lineTo(midpoint_x, source.y())
        path.lineTo(midpoint_x, target.y())
        path.lineTo(target)
        self.setPath(path)

    def set_dimmed(self, dimmed: bool) -> None:
        self.setOpacity(0.16 if dimmed else 1.0)
