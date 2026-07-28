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
from app.image_to_video_page import ImageToVideoPage
from app.video_editor_page import VideoEditorPage
from app.film_studio_page import FilmStudioPage
from app.project_page import ProjectPage
from app.settings_page import SettingsPage


class AIStudio(QMainWindow):
    """
    Cửa sổ chính của AI Studio.

    Các trang chính:
    - Tổng quan.
    - Trang dự án.
    - Trang cài đặt.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("AI Studio")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self.project_manager = ProjectManager()

        self.menu_buttons: dict[str, QPushButton] = {}

        self.build_ui()

    def build_ui(self) -> None:
        central_widget = QWidget()

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self.create_sidebar()

        self.pages = QStackedWidget()

        self.dashboard_page = self.create_content()

        self.project_page = ProjectPage(
            self.project_manager
        )
        self.project_page.back_requested.connect(
            self.show_dashboard
        )

        self.image_to_video_page = ImageToVideoPage()
        self.video_editor_page = VideoEditorPage()
        self.film_studio_page = FilmStudioPage()

        self.settings_page = SettingsPage()
        self.settings_page.settings_saved.connect(
            self.handle_settings_saved
        )

        self.pages.addWidget(
            self.dashboard_page
        )
        self.pages.addWidget(
            self.project_page
        )
        self.pages.addWidget(self.image_to_video_page)
        self.pages.addWidget(self.video_editor_page)
        self.pages.addWidget(self.film_studio_page)
        self.pages.addWidget(
            self.settings_page
        )

        root_layout.addWidget(sidebar)
        root_layout.addWidget(
            self.pages,
            1,
        )

        self.setCentralWidget(
            central_widget
        )

        self.show_dashboard()

        self.statusBar().showMessage(
            "AI Studio đã sẵn sàng"
        )

    def create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(
            20,
            25,
            20,
            25,
        )
        layout.setSpacing(12)

        logo = QLabel("AI STUDIO")
        logo.setObjectName("logo")
        logo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(logo)
        layout.addSpacing(20)

        menu_items = [
            (
                "dashboard",
                "🏠  Tổng quan",
            ),
            (
                "create_video",
                "🎬  Tạo video",
            ),
            (
                "script",
                "📝  Viết kịch bản",
            ),
            (
                "film_studio",
                "🎥  AI Film Studio",
            ),
            (
                "image_to_video",
                "🖼  Ảnh thành video",
            ),
            (
                "video_editor",
                "🎞  AI Video Editor",
            ),
            (
                "library",
                "📂  Thư viện video",
            ),
            (
                "export",
                "📤  Xuất video",
            ),
            (
                "settings",
                "⚙️  Cài đặt",
            ),
        ]

        for menu_key, text in menu_items:
            button = QPushButton(text)
            button.setObjectName(
                "menuButton"
            )
            button.setCheckable(True)

            button.clicked.connect(
                lambda checked=False,
                key=menu_key: self.change_page(
                    key
                )
            )

            self.menu_buttons[
                menu_key
            ] = button

            layout.addWidget(button)

        layout.addStretch()

        version = QLabel("Phiên bản 4.0")
        version.setObjectName("version")
        version.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(version)

        return sidebar

    def create_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("content")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            40,
            35,
            40,
            35,
        )
        layout.setSpacing(20)

        self.page_title = QLabel(
            "Tổng quan"
        )
        self.page_title.setObjectName(
            "pageTitle"
        )

        description = QLabel(
            "Chào mừng bạn đến với AI Studio.\n"
            "Đây là trung tâm tạo kịch bản, "
            "quản lý hình ảnh, giọng đọc "
            "và dựng video AI."
        )
        description.setObjectName(
            "description"
        )
        description.setWordWrap(True)

        action_button = QPushButton(
            "＋ Tạo dự án video mới"
        )
        action_button.setObjectName(
            "primaryButton"
        )
        action_button.setFixedWidth(230)
        action_button.clicked.connect(
            self.create_project
        )

        progress_card = QFrame()
        progress_card.setObjectName("card")

        progress_layout = QVBoxLayout(
            progress_card
        )
        progress_layout.setContentsMargins(
            25,
            25,
            25,
            25,
        )
        progress_layout.setSpacing(10)

        progress_title = QLabel(
            "Tiến độ AI Studio"
        )
        progress_title.setObjectName(
            "cardTitle"
        )

        progress_text = QLabel(
            "✓ Cài đặt môi trường\n"
            "✓ Quản lý danh sách dự án\n"
            "✓ AI viết và chia kịch bản\n"
            "✓ Tạo ảnh AI\n"
            "✓ Tạo giọng đọc AI\n"
            "✓ Dựng video bằng FFmpeg\n"
            "✓ Hiệu ứng chuyển động Ken Burns\n"
            "✓ Tạo và chèn phụ đề tự động\n"
            "✓ Hệ thống config.json\n"
            "✓ Trang Cài đặt"
        )
        progress_text.setObjectName(
            "cardText"
        )

        progress_layout.addWidget(
            progress_title
        )
        progress_layout.addWidget(
            progress_text
        )

        projects_title = QLabel(
            "Dự án của bạn"
        )
        projects_title.setObjectName(
            "cardTitle"
        )

        self.projects_container = QFrame()
        self.projects_container.setObjectName(
            "card"
        )

        self.projects_layout = QVBoxLayout(
            self.projects_container
        )
        self.projects_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )
        self.projects_layout.setSpacing(10)

        layout.addWidget(
            self.page_title
        )
        layout.addWidget(description)
        layout.addWidget(action_button)
        layout.addWidget(progress_card)
        layout.addWidget(projects_title)
        layout.addWidget(
            self.projects_container
        )
        layout.addStretch()

        self.refresh_projects()

        return content

    def change_page(
        self,
        page_key: str,
    ) -> None:
        """
        Chuyển trang khi người dùng bấm menu bên trái.
        """

        if page_key == "dashboard":
            self.show_dashboard()
            return

        if page_key == "settings":
            self.show_settings()
            return

        if page_key == "film_studio":
            self.pages.setCurrentWidget(self.film_studio_page)
            self.set_active_menu("film_studio")
            self.statusBar().showMessage("AI Film Studio đã sẵn sàng", 3000)
            return

        if page_key == "image_to_video":
            self.pages.setCurrentWidget(self.image_to_video_page)
            self.set_active_menu("image_to_video")
            self.statusBar().showMessage("Ảnh thành video đã sẵn sàng", 3000)
            return

        if page_key == "video_editor":
            self.pages.setCurrentWidget(self.video_editor_page)
            self.set_active_menu("video_editor")
            self.statusBar().showMessage("AI Video Editor đã sẵn sàng", 3000)
            return

        if page_key == "create_video":
            self.show_dashboard()

            self.statusBar().showMessage(
                (
                    "Hãy tạo một dự án mới "
                    "hoặc mở dự án có sẵn."
                ),
                4000,
            )
            return

        page_names = {
            "script": "Viết kịch bản",
            "library": "Thư viện video",
            "export": "Xuất video",
        }

        page_name = page_names.get(
            page_key,
            page_key,
        )

        self.statusBar().showMessage(
            (
                f"Chức năng {page_name} "
                "sẽ được xây ở bước tiếp theo."
            ),
            4000,
        )

    def set_active_menu(
        self,
        active_key: str,
    ) -> None:
        """
        Đánh dấu nút menu đang được chọn.
        """

        for menu_key, button in (
            self.menu_buttons.items()
        ):
            is_active = (
                menu_key == active_key
            )

            button.setChecked(is_active)
            button.setProperty(
                "active",
                is_active,
            )

            button.style().unpolish(
                button
            )
            button.style().polish(
                button
            )
            button.update()

    def refresh_projects(self) -> None:
        """
        Làm mới danh sách dự án trên trang Tổng quan.
        """

        while self.projects_layout.count():
            item = (
                self.projects_layout.takeAt(
                    0
                )
            )
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        projects = (
            self.project_manager
            .get_projects()
        )

        if not projects:
            empty_label = QLabel(
                "Chưa có dự án nào."
            )
            empty_label.setObjectName(
                "description"
            )

            self.projects_layout.addWidget(
                empty_label
            )
            return

        for project in projects:
            project_button = QPushButton(
                f"📁  {project.name}"
            )
            project_button.setObjectName(
                "projectButton"
            )

            project_button.clicked.connect(
                lambda checked=False,
                name=project.name: (
                    self.open_project(name)
                )
            )

            self.projects_layout.addWidget(
                project_button
            )

    def open_project(
        self,
        project_name: str,
    ) -> None:
        """
        Mở trang chi tiết của một dự án.
        """

        self.project_page.load_project(
            project_name
        )

        self.pages.setCurrentWidget(
            self.project_page
        )

        self.set_active_menu(
            "create_video"
        )

        self.statusBar().showMessage(
            f"Đang mở dự án: {project_name}",
            5000,
        )

    def show_dashboard(self) -> None:
        """
        Quay lại trang Tổng quan.
        """

        self.refresh_projects()

        self.pages.setCurrentWidget(
            self.dashboard_page
        )

        self.page_title.setText(
            "Tổng quan"
        )

        self.set_active_menu(
            "dashboard"
        )

        self.statusBar().showMessage(
            "Đã mở trang Tổng quan",
            3000,
        )

    def show_settings(self) -> None:
        """
        Mở trang Cài đặt.
        """

        self.settings_page.load_settings()

        self.pages.setCurrentWidget(
            self.settings_page
        )

        self.set_active_menu(
            "settings"
        )

        self.statusBar().showMessage(
            "Đã mở trang Cài đặt",
            3000,
        )

    def handle_settings_saved(self) -> None:
        """
        Xử lý sau khi người dùng lưu cài đặt.
        """

        self.statusBar().showMessage(
            "Cài đặt đã được lưu",
            5000,
        )

    def create_project(self) -> None:
        """
        Tạo một dự án video mới.
        """

        project_name, accepted = (
            QInputDialog.getText(
                self,
                "Tạo dự án mới",
                "Nhập tên dự án video:",
            )
        )

        if not accepted:
            return

        project_name = (
            project_name.strip()
        )

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
            if (
                character.isalnum()
                or character
                in (
                    " ",
                    "-",
                    "_",
                )
            )
        ).strip()

        if not safe_name:
            QMessageBox.warning(
                self,
                "Tên không hợp lệ",
                (
                    "Tên dự án phải "
                    "có chữ hoặc số."
                ),
            )
            return

        created = (
            self.project_manager
            .create_project(
                safe_name
            )
        )

        if not created:
            QMessageBox.warning(
                self,
                "Dự án đã tồn tại",
                (
                    f"Dự án “{safe_name}” "
                    "đã có."
                ),
            )
            return

        self.refresh_projects()

        QMessageBox.information(
            self,
            "Tạo dự án thành công",
            (
                "Đã tạo dự án:\n"
                f"{safe_name}"
            ),
        )

        self.statusBar().showMessage(
            f"Đã tạo dự án: {safe_name}",
            5000,
        )