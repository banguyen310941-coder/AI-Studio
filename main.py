import sys

from PySide6.QtWidgets import QApplication

from app.styles import apply_styles
from app.window import AIStudio


def main() -> None:
    app = QApplication(sys.argv)
    apply_styles(app)

    window = AIStudio()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()