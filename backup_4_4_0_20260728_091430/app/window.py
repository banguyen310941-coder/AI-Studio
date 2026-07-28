from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.project_manager import ProjectManager
from app.project_page import ProjectPage
from app.settings_page import SettingsPage
from app.version import APP_VERSION, WINDOW_TITLE


class AIStudio(QMainWindow):
    """Cửa sổ chính AI Studio 4.3 với dashboard mới và lazy loading an toàn."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)

        self.project_manager = ProjectManager()
        self.menu_buttons: dict[str, QPushButton] = {}
        self._lazy_pages: dict[str, QWidget] = {}

        self.build_ui()

    def build_ui(self) -> None:
        central_widget = QWidget(self)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self.create_sidebar()
        self.pages = QStackedWidget(self)

        self.dashboard_page = self.create_dashboard()
        self.project_page = ProjectPage(self.project_manager)
        self.project_page.back_requested.connect(self.show_dashboard)

        self.settings_page = SettingsPage()
        self.settings_page.settings_saved.connect(self.handle_settings_saved)

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.project_page)
        self.pages.addWidget(self.settings_page)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)

        self.setCentralWidget(central_widget)
        self.show_dashboard()
        self.statusBar().showMessage(f"AI Studio {APP_VERSION} đã sẵn sàng")

    def create_sidebar(self) -> QFrame:
        sidebar = QFrame(self)
        sidebar.setFixedWidth(230)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 25, 20, 25)
        layout.setSpacing(12)

        logo = QLabel("AI STUDIO", sidebar)
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addSpacing(20)

        menu_items = [
            ("dashboard", "🏠  Tổng quan"),
            ("create_video", "🎬  Tạo video"),
            ("script", "📝  Viết kịch bản"),
            ("film_studio", "🎥  AI Film Studio"),
            ("image_to_video", "🖼  Ảnh thành video"),
            ("video_editor", "🎞  AI Video Editor"),
            ("library", "📂  Thư viện video"),
            ("export", "📤  Xuất video"),
            ("settings", "⚙️  Cài đặt"),
        ]

        for menu_key, text in menu_items:
            button = QPushButton(text, sidebar)
            button.setObjectName("menuButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, key=menu_key: self.change_page(key)
            )
            self.menu_buttons[menu_key] = button
            layout.addWidget(button)

        layout.addStretch()

        version = QLabel(f"Phiên bản {APP_VERSION}", sidebar)
        version.setObjectName("version")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        return sidebar

    def create_dashboard(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("dashboardScroll")

        content = QWidget(scroll)
        content.setObjectName("content")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(38, 32, 38, 38)
        layout.setSpacing(20)

        top_row = QHBoxLayout()
        title_box = QVBoxLayout()

        self.page_title = QLabel("Tổng quan", content)
        self.page_title.setObjectName("pageTitle")

        description = QLabel(
            f"AI Studio {APP_VERSION} — quản lý dự án và sản xuất video AI.",
            content,
        )
        description.setObjectName("description")

        title_box.addWidget(self.page_title)
        title_box.addWidget(description)
        top_row.addLayout(title_box)
        top_row.addStretch()

        action_button = QPushButton("＋ Tạo dự án mới", content)
        action_button.setObjectName("primaryButton")
        action_button.clicked.connect(self.create_project)
        top_row.addWidget(action_button)

        layout.addLayout(top_row)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(14)
        stats_grid.setVerticalSpacing(14)

        self.project_count_value = QLabel("0")
        self.file_count_value = QLabel("0")
        self.storage_value = QLabel("0 B")

        stats_grid.addWidget(
            self._create_stat_card("Dự án", self.project_count_value, "Đang quản lý"),
            0,
            0,
        )
        stats_grid.addWidget(
            self._create_stat_card("Tệp nội dung", self.file_count_value, "Trong mọi dự án"),
            0,
            1,
        )
        stats_grid.addWidget(
            self._create_stat_card("Dung lượng", self.storage_value, "Dữ liệu dự án"),
            0,
            2,
        )
        layout.addLayout(stats_grid)

        quick_title = QLabel("Bắt đầu nhanh", content)
        quick_title.setObjectName("sectionTitle")
        layout.addWidget(quick_title)

        quick_grid = QGridLayout()
        quick_grid.setHorizontalSpacing(14)
        quick_grid.setVerticalSpacing(14)
        quick_grid.addWidget(
            self._create_action_card(
                "🎥",
                "AI Film Studio",
                "Tạo kế hoạch phim, chia cảnh và dựng video.",
                self._show_film_studio,
            ),
            0,
            0,
        )
        quick_grid.addWidget(
            self._create_action_card(
                "🖼",
                "Ảnh thành video",
                "Biến ảnh tĩnh thành video có chuyển động.",
                self._show_image_to_video,
            ),
            0,
            1,
        )
        quick_grid.addWidget(
            self._create_action_card(
                "🎞",
                "AI Video Editor",
                "Ghép, cắt và xuất video từ các tư liệu.",
                self._show_video_editor,
            ),
            0,
            2,
        )
        layout.addLayout(quick_grid)

        projects_header = QHBoxLayout()
        projects_title = QLabel("Dự án gần đây", content)
        projects_title.setObjectName("sectionTitle")
        projects_header.addWidget(projects_title)
        projects_header.addStretch()

        refresh_button = QPushButton("↻ Làm mới", content)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_projects)
        projects_header.addWidget(refresh_button)
        layout.addLayout(projects_header)

        self.projects_container = QFrame(content)
        self.projects_container.setObjectName("card")
        self.projects_layout = QVBoxLayout(self.projects_container)
        self.projects_layout.setContentsMargins(18, 18, 18, 18)
        self.projects_layout.setSpacing(10)
        layout.addWidget(self.projects_container)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    def _create_stat_card(self, title: str, value_label: QLabel, note: str) -> QFrame:
        card = QFrame(self)
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(5)

        label = QLabel(title, card)
        label.setObjectName("statLabel")
        value_label.setParent(card)
        value_label.setObjectName("statValue")
        hint = QLabel(note, card)
        hint.setObjectName("statHint")

        layout.addWidget(label)
        layout.addWidget(value_label)
        layout.addWidget(hint)
        return card

    def _create_action_card(
        self,
        icon: str,
        title: str,
        description: str,
        callback: Callable[[], None],
    ) -> QFrame:
        card = QFrame(self)
        card.setObjectName("actionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        icon_label = QLabel(icon, card)
        icon_label.setObjectName("actionIcon")
        title_label = QLabel(title, card)
        title_label.setObjectName("actionTitle")
        description_label = QLabel(description, card)
        description_label.setObjectName("cardText")
        description_label.setWordWrap(True)

        button = QPushButton("Mở công cụ", card)
        button.setObjectName("secondaryButton")
        button.clicked.connect(callback)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()
        layout.addWidget(button)
        return card

    @staticmethod
    def _format_total_size(size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size_bytes} B"

    def _get_or_create_page(
        self,
        key: str,
        factory: Callable[[], QWidget],
    ) -> QWidget:
        page = self._lazy_pages.get(key)
        if page is not None:
            return page

        page = factory()
        self._lazy_pages[key] = page
        self.pages.addWidget(page)
        return page

    def _show_image_to_video(self) -> None:
        from app.image_to_video_page import ImageToVideoPage

        page = self._get_or_create_page("image_to_video", ImageToVideoPage)
        self.pages.setCurrentWidget(page)
        self.set_active_menu("image_to_video")
        self.statusBar().showMessage("Ảnh thành video đã sẵn sàng", 3000)

    def _show_video_editor(self) -> None:
        from app.video_editor_page import VideoEditorPage

        page = self._get_or_create_page("video_editor", VideoEditorPage)
        self.pages.setCurrentWidget(page)
        self.set_active_menu("video_editor")
        self.statusBar().showMessage("AI Video Editor đã sẵn sàng", 3000)

    def _show_film_studio(self) -> None:
        from app.film_studio_page import FilmStudioPage

        page = self._get_or_create_page("film_studio", FilmStudioPage)
        self.pages.setCurrentWidget(page)
        self.set_active_menu("film_studio")
        self.statusBar().showMessage("AI Film Studio đã sẵn sàng", 3000)

    def change_page(self, page_key: str) -> None:
        if page_key == "dashboard":
            self.show_dashboard()
        elif page_key == "settings":
            self.show_settings()
        elif page_key == "film_studio":
            self._show_film_studio()
        elif page_key == "image_to_video":
            self._show_image_to_video()
        elif page_key == "video_editor":
            self._show_video_editor()
        elif page_key == "create_video":
            self.show_dashboard()
            self.statusBar().showMessage(
                "Hãy tạo dự án mới hoặc mở dự án có sẵn.",
                4000,
            )
        else:
            page_names = {
                "script": "Viết kịch bản",
                "library": "Thư viện video",
                "export": "Xuất video",
            }
            page_name = page_names.get(page_key, page_key)
            self.statusBar().showMessage(
                f"Chức năng {page_name} sẽ được xây ở bản tiếp theo.",
                4000,
            )

    def set_active_menu(self, active_key: str) -> None:
        for menu_key, button in self.menu_buttons.items():
            is_active = menu_key == active_key
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def refresh_projects(self) -> None:
        while self.projects_layout.count():
            item = self.projects_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        projects = self.project_manager.get_projects()
        total_files = sum(project.file_count for project in projects)
        total_size = sum(project.size_bytes for project in projects)

        self.project_count_value.setText(str(len(projects)))
        self.file_count_value.setText(str(total_files))
        self.storage_value.setText(self._format_total_size(total_size))

        if not projects:
            empty_label = QLabel(
                "Chưa có dự án. Nhấn “Tạo dự án mới” để bắt đầu.",
                self.projects_container,
            )
            empty_label.setObjectName("description")
            self.projects_layout.addWidget(empty_label)
            return

        for project in projects[:8]:
            row = QFrame(self.projects_container)
            row.setObjectName("projectRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)

            info_layout = QVBoxLayout()
            name = QLabel(f"📁  {project.name}", row)
            name.setObjectName("projectName")
            meta = QLabel(
                f"{project.file_count} tệp · {project.size_text} · "
                f"Cập nhật {project.modified_at.strftime('%d/%m/%Y %H:%M')}",
                row,
            )
            meta.setObjectName("projectMeta")
            info_layout.addWidget(name)
            info_layout.addWidget(meta)

            open_button = QPushButton("Mở", row)
            open_button.setObjectName("secondaryButton")
            open_button.clicked.connect(
                lambda checked=False, project_name=project.name: self.open_project(
                    project_name
                )
            )

            row_layout.addLayout(info_layout)
            row_layout.addStretch()
            row_layout.addWidget(open_button)
            self.projects_layout.addWidget(row)

    def open_project(self, project_name: str) -> None:
        self.project_page.load_project(project_name)
        self.pages.setCurrentWidget(self.project_page)
        self.set_active_menu("create_video")
        self.statusBar().showMessage(f"Đang mở dự án: {project_name}", 5000)

    def show_dashboard(self) -> None:
        self.refresh_projects()
        self.pages.setCurrentWidget(self.dashboard_page)
        self.page_title.setText("Tổng quan")
        self.set_active_menu("dashboard")
        self.statusBar().showMessage("Đã mở trang Tổng quan", 3000)

    def show_settings(self) -> None:
        self.settings_page.load_settings()
        self.pages.setCurrentWidget(self.settings_page)
        self.set_active_menu("settings")
        self.statusBar().showMessage("Đã mở trang Cài đặt", 3000)

    def handle_settings_saved(self) -> None:
        self.statusBar().showMessage("Cài đặt đã được lưu", 5000)

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
            QMessageBox.warning(self, "Thiếu tên dự án", "Bạn chưa nhập tên dự án.")
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

        if not self.project_manager.create_project(safe_name):
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
        self.statusBar().showMessage(f"Đã tạo dự án: {safe_name}", 5000)
