import sys

from PySide6.QtWidgets import QApplication

from app.settings_page import SettingsPage


def main() -> None:
    app = QApplication(sys.argv)

    page = SettingsPage()
    page.setWindowTitle("Kiểm tra trang Cài đặt")
    page.resize(900, 760)
    page.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
