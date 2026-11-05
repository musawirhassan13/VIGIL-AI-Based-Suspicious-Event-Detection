"""VIGIL desktop app entry point."""
import sys

from PySide6.QtWidgets import QApplication

from vigil import theme
from vigil.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("VIGIL")
    theme.apply(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
