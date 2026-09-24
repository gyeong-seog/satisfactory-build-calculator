"""Dark industrial interface palette inspired by the game's menu language."""

APP_STYLESHEET = """
QMainWindow, QDockWidget, QToolBar, QScrollArea, QWidget {
    background-color: #0f191f;
    color: #e7ecee;
    font-family: "Pretendard", "Segoe UI";
    font-size: 10pt;
}
QDockWidget {
    border: 1px solid #34434d;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #17232c;
    border-bottom: 1px solid #34434d;
    color: #f4f1e9;
    padding: 10px 14px;
    text-align: left;
    font-size: 11pt;
    font-weight: 600;
}
QToolBar {
    background-color: #141f27;
    border-bottom: 1px solid #34434d;
    spacing: 6px;
    padding: 3px 7px;
}
QToolBar QLabel, QToolBar QCheckBox { background-color: transparent; color: #aeb9c0; }
#targetControls { background-color: #101a21; }
#targetControls QLabel { background-color: transparent; }
#summaryPanel, #summaryContent { background-color: #101a21; border: none; }
#summaryRow, #summaryRow QLabel { background-color: transparent; }
QToolBar QToolButton, QPushButton, QToolButton {
    background-color: #1d2932;
    color: #eef1f2;
    border: 1px solid #475762;
    border-radius: 5px;
    padding: 5px 10px;
    font-weight: 600;
}
QToolBar QToolButton:hover, QPushButton:hover, QToolButton:hover {
    background-color: #273640;
    border-color: #d89a45;
}
QToolBar QToolButton:pressed, QPushButton:pressed, QToolButton:pressed {
    background-color: #d99b43;
    color: #10161a;
}
QToolBar QToolButton:checked, QPushButton:checked {
    background-color: #e1a44c;
    border-color: #efb65f;
    color: #10161a;
}
QPushButton#primaryButton {
    background-color: #e1a44c;
    border-color: #efb65f;
    color: #10161a;
    font-weight: 700;
    padding: 8px 10px;
}
QPushButton#primaryButton:hover { background-color: #efb65f; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #0a141a;
    color: #f4f1e9;
    border: 1px solid #475762;
    border-radius: 5px;
    padding: 4px 7px;
    selection-background-color: #d99b43;
    selection-color: #15191c;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #e1a44c;
}
QComboBox::drop-down { border-left: 1px solid #34434d; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #17232c;
    color: #f4f1e9;
    border: 1px solid #475762;
    selection-background-color: #d99b43;
    selection-color: #10161a;
}
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QScrollBar:vertical {
    background: #111c23; width: 13px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #52616c; min-height: 28px; border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #111c23; height: 13px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #52616c; min-width: 28px; border-radius: 5px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle { background: #34434d; width: 2px; }
"""
