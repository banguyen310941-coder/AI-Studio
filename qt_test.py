import sys
import platform
import PySide6

from PySide6.QtWidgets import QApplication, QLabel

print("Python architecture:", platform.machine())
print("PySide6 version:", PySide6.__version__)

app = QApplication(sys.argv)

label = QLabel("Kiểm tra PySide6")
label.resize(400, 200)
label.show()

sys.exit(app.exec())
