"""Composite input controls with arrow buttons outside the text field."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


ARROW_STYLE = (
    "QToolButton { background: #17232c; color: #dce3e6; "
    "border: 1px solid #53626d; border-radius: 3px; padding: 0; }"
    "QToolButton:hover { background: #263640; border-color: #d89a45; }"
    "QToolButton:pressed { background: #d99b43; color: #10161a; }"
)


class ExternalSpinControl(QWidget):
    """A spin editor followed by a separate vertical step-button rail."""

    def __init__(self, editor: QAbstractSpinBox, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(editor, 1)

        rail = QWidget(self)
        rail.setStyleSheet("background: transparent;")
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(2)
        self.up_button = self._arrow_button(Qt.ArrowType.UpArrow)
        self.down_button = self._arrow_button(Qt.ArrowType.DownArrow)
        self.up_button.clicked.connect(editor.stepUp)
        self.down_button.clicked.connect(editor.stepDown)
        rail_layout.addWidget(self.up_button)
        rail_layout.addWidget(self.down_button)
        layout.addWidget(rail)

    @staticmethod
    def _arrow_button(arrow: Qt.ArrowType) -> QToolButton:
        button = QToolButton()
        button.setArrowType(arrow)
        button.setAutoRepeat(True)
        button.setFixedWidth(24)
        button.setStyleSheet(ARROW_STYLE)
        return button


class ExternalComboControl(QWidget):
    """A combo editor followed by a separate popup button."""

    def __init__(self, combo: QComboBox, parent=None):
        super().__init__(parent)
        self.combo = combo
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        combo.setStyleSheet(
            combo.styleSheet()
            + " QComboBox::drop-down { width: 0; border: none; }"
            + " QComboBox::down-arrow { image: none; width: 0; height: 0; }"
        )
        layout.addWidget(combo, 1)
        self.drop_button = QToolButton(self)
        self.drop_button.setArrowType(Qt.ArrowType.DownArrow)
        self.drop_button.setFixedWidth(26)
        self.drop_button.setStyleSheet(ARROW_STYLE)
        self.drop_button.clicked.connect(combo.showPopup)
        layout.addWidget(self.drop_button)
