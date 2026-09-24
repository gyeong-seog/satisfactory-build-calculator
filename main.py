"""Satisfactory Build Calculator entry point."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Satisfactory Build Calculator")
    app.setApplicationVersion("0.2.0")
    app.setQuitOnLastWindowClosed(False)

    # PyInstaller one-file builds unpack bundled resources into _MEIPASS.
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    data_dir = bundle_dir / "data"
    window = MainWindow(data_dir)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
