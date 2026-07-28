import sys

from PySide6.QtWidgets import QApplication

from app.settings_page import SettingsPage


def main():
    app = QApplication(sys.argv)

    window = SettingsPage()
    window.resize(900, 700)
    window.setWindowTitle("Settings Test")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()