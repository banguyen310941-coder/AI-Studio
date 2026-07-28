from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.project_manager import ProjectManager
from app.project_page import ProjectPage


class AIStudio(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("AI Studio")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self.project_manager = ProjectManager()

        self.build_ui()

    def build_ui(self) -> None:
        central_widget = QWidget()

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self.create_sidebar()

        self.pages = QStackedWidget()

        self.dashboard_page = self.create_content()

        self.project_page = ProjectPage(self.project_manager)
        self.project_page.back_requested.connect(self.show_dashboard)

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.project_page)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)

        self.setCentralWidget(central_widget)
        self.statusBar().showMessage("AI Studio đã sẵn sàng")

    def create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 25, 20, 25)
        layout.setSpacing(12)

        logo = QLabel("AI STUDIO")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(logo)
        layout.addSpacing(20)

        menu_items = [
            "🏠  Tổng quan",
            "🎬  Tạo video",
            "📝  Viết kịch bản",
            "📂  Thư viện video",
            "📤  Xuất video",
            "⚙️  Cài đặt",
        ]

        for index, text in enumerate(menu_items):
            button = QPushButton(text)
            button.setObjectName("menuButton")

            if index == 0:
                button.setProperty("active", True)

            button.clicked.connect(
                lambda checked=False, name=text: self.change_page(name)
            )

            layout.addWidget(button)

        layout.addStretch()

        version = QLabel("Phiên bản 2.0")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(version)

        return sidebar

    def create_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("content")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 35, 40, 35)
        layout.setSpacing(20)

        self.page_title = QLabel("Tổng quan")
        self.page_title.setObjectName("pageTitle")

        description = QLabel(
            "Chào mừng bạn đến với AI Studio.\n"
            "Đây là trung tâm tạo kịch bản, quản lý footage và dựng video AI."
        )
        description.setObjectName("description")
        description.setWordWrap(True)

        action_button = QPushButton("＋ Tạo dự án video mới")
        action_button.setObjectName("primaryButton")
        action_button.setFixedWidth(230)
        action_button.clicked.connect(self.create_project)

        progress_card = QFrame()
        progress_card.setObjectName("card")

        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(25, 25, 25, 25)
        progress_layout.setSpacing(10)

        progress_title = QLabel("Tiến độ dự án")
        progress_title.setObjectName("cardTitle")

        progress_text = QLabel(
            "✓ Cài đặt môi trường\n"
            "✓ Chạy ứng dụng desktop\n"
            "✓ Tách giao diện khỏi main.py\n"
            "✓ Quản lý danh sách dự án\n"
            "● Đang xây trang chi tiết dự án\n"
            "○ Kết nối AI viết kịch bản\n"
            "○ Dựng video bằng FFmpeg"
        )
        progress_text.setObjectName("cardText")

        progress_layout.addWidget(progress_title)
        progress_layout.addWidget(progress_text)

        projects_title = QLabel("Dự án của bạn")
        projects_title.setObjectName("cardTitle")

        self.projects_container = QFrame()
        self.projects_container.setObjectName("card")

        self.projects_layout = QVBoxLayout(self.projects_container)
        self.projects_layout.setContentsMargins(20, 20, 20, 20)
        self.projects_layout.setSpacing(10)

        layout.addWidget(self.page_title)
        layout.addWidget(description)
        layout.addWidget(action_button)
        layout.addWidget(progress_card)
        layout.addWidget(projects_title)
        layout.addWidget(self.projects_container)
        layout.addStretch()

        self.refresh_projects()

        return content

    def change_page(self, page_name: str) -> None:
        clean_name = page_name.split("  ", 1)[-1]

        if clean_name == "Tổng quan":
            self.show_dashboard()
            return

        self.statusBar().showMessage(
            f"Chức năng {clean_name} sẽ được xây ở bước tiếp theo.",
            4000,
        )

    def refresh_projects(self) -> None:
        while self.projects_layout.count():
            item = self.projects_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        projects = self.project_manager.get_projects()

        if not projects:
            empty_label = QLabel("Chưa có dự án nào.")
            empty_label.setObjectName("description")
            self.projects_layout.addWidget(empty_label)
            return

        for project in projects:
            project_button = QPushButton(f"📁  {project.name}")
            project_button.setObjectName("projectButton")

            project_button.clicked.connect(
                lambda checked=False, name=project.name: self.open_project(name)
            )

            self.projects_layout.addWidget(project_button)

    def open_project(self, project_name: str) -> None:
        self.project_page.load_project(project_name)
        self.pages.setCurrentWidget(self.project_page)

        self.statusBar().showMessage(
            f"Đang mở dự án: {project_name}",
            5000,
        )

    def show_dashboard(self) -> None:
        self.refresh_projects()
        self.pages.setCurrentWidget(self.dashboard_page)
        self.page_title.setText("Tổng quan")

        self.statusBar().showMessage(
            "Đã quay lại Tổng quan",
            3000,
        )

    def create_project(self) -> None:
        project_name, accepted = QInputDialog.getText(
            self,
            "Tạo dự án mới",
            "Nhập tên dự án video:",
        )

        if not accepted:
            return

        project_name = project_name.strip()

        if not project_name:
            QMessageBox.warning(
                self,
                "Thiếu tên dự án",
                "Bạn chưa nhập tên dự án.",
            )
            return

        safe_name = "".join(
            character
            for character in project_name
            if character.isalnum() or character in (" ", "-", "_")
        ).strip()

        if not safe_name:
            QMessageBox.warning(
                self,
                "Tên không hợp lệ",
                "Tên dự án phải có chữ hoặc số.",
            )
            return

        created = self.project_manager.create_project(safe_name)

        if not created:
            QMessageBox.warning(
                self,
                "Dự án đã tồn tại",
                f"Dự án “{safe_name}” đã có.",
            )
            return

        self.refresh_projects()

        QMessageBox.information(
            self,
            "Tạo dự án thành công",
            f"Đã tạo dự án:\n{safe_name}",
        )

        self.statusBar().showMessage(
            f"Đã tạo dự án: {safe_name}",
            5000,
        )