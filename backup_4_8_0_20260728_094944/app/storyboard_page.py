from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.storyboard_service import StoryboardService, StoryboardShot


class StoryboardPage(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.service = StoryboardService()
        self.project_root = Path(__file__).resolve().parent.parent / "projects"
        self.current_project_dir: Path | None = None
        self.shots: list[StoryboardShot] = []
        self._build_ui()
        self.refresh_projects()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("🧩 Storyboard & Timeline", self)
        title.setObjectName("pageTitle")
        description = QLabel(
            "Quản lý shot, thời lượng, trạng thái, asset và thứ tự dựng phim.",
            self,
        )
        description.setObjectName("description")

        title_box.addWidget(title)
        title_box.addWidget(description)
        header.addLayout(title_box)
        header.addStretch()

        back_button = QPushButton("← Tổng quan", self)
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(back_button)
        root.addLayout(header)

        body = QSplitter(Qt.Orientation.Horizontal, self)
        body.addWidget(self._create_project_panel())
        body.addWidget(self._create_storyboard_panel())
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([240, 920])
        root.addWidget(body, 1)

    def _create_project_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)

        title = QLabel("Dự án", panel)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.project_list = QListWidget(panel)
        self.project_list.itemDoubleClicked.connect(self.open_selected_project)
        layout.addWidget(self.project_list, 1)

        refresh_button = QPushButton("↻ Làm mới", panel)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_projects)
        layout.addWidget(refresh_button)

        open_button = QPushButton("Mở dự án", panel)
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(self.open_selected_project)
        layout.addWidget(open_button)
        return panel

    def _create_storyboard_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()

        self.project_label = QLabel("Chưa mở dự án", panel)
        self.project_label.setObjectName("sectionTitle")
        toolbar.addWidget(self.project_label)
        toolbar.addStretch()

        add_button = QPushButton("＋ Thêm shot", panel)
        add_button.setObjectName("secondaryButton")
        add_button.clicked.connect(self.add_shot)
        toolbar.addWidget(add_button)

        remove_button = QPushButton("− Xóa shot", panel)
        remove_button.setObjectName("secondaryButton")
        remove_button.clicked.connect(self.remove_selected_shot)
        toolbar.addWidget(remove_button)

        up_button = QPushButton("↑", panel)
        up_button.setObjectName("secondaryButton")
        up_button.clicked.connect(lambda: self.move_selected(-1))
        toolbar.addWidget(up_button)

        down_button = QPushButton("↓", panel)
        down_button.setObjectName("secondaryButton")
        down_button.clicked.connect(lambda: self.move_selected(1))
        toolbar.addWidget(down_button)

        save_button = QPushButton("💾 Lưu storyboard", panel)
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_storyboard)
        toolbar.addWidget(save_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 8, panel)
        self.table.setHorizontalHeaderLabels(
            [
                "Shot",
                "Cảnh",
                "Tên",
                "Mô tả hình ảnh",
                "Camera",
                "Thời lượng",
                "Trạng thái",
                "Asset",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 55)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 320)
        self.table.setColumnWidth(4, 240)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 220)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()

        self.timeline_label = QLabel("Timeline: 0 giây", panel)
        self.timeline_label.setObjectName("description")
        footer.addWidget(self.timeline_label)

        footer.addStretch()

        attach_button = QPushButton("📎 Gắn asset", panel)
        attach_button.setObjectName("secondaryButton")
        attach_button.clicked.connect(self.attach_asset)
        footer.addWidget(attach_button)

        export_button = QPushButton("📄 Xuất timeline JSON", panel)
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self.export_timeline)
        footer.addWidget(export_button)

        layout.addLayout(footer)
        return panel

    def refresh_projects(self) -> None:
        self.project_list.clear()
        self.project_root.mkdir(parents=True, exist_ok=True)

        projects = sorted(
            [path for path in self.project_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for project_dir in projects:
            item = QListWidgetItem(project_dir.name)
            item.setData(Qt.ItemDataRole.UserRole, str(project_dir))
            self.project_list.addItem(item)

    def open_selected_project(self, item=None) -> None:
        if item is None:
            item = self.project_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "Chưa chọn dự án", "Hãy chọn một dự án.")
            return

        self.current_project_dir = Path(item.data(Qt.ItemDataRole.UserRole))
        self.shots = self.service.load_from_project(self.current_project_dir)
        self.project_label.setText(f"Dự án: {self.current_project_dir.name}")
        self.render_table()

    def render_table(self) -> None:
        self.table.setRowCount(0)

        for shot in self.shots:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(str(shot.shot_number)))
            self.table.setItem(row, 1, QTableWidgetItem(str(shot.scene_number)))
            self.table.setItem(row, 2, QTableWidgetItem(shot.title))
            self.table.setItem(row, 3, QTableWidgetItem(shot.visual_description))
            self.table.setItem(row, 4, QTableWidgetItem(shot.camera))

            duration = QSpinBox(self.table)
            duration.setRange(1, 60)
            duration.setValue(shot.duration_seconds)
            duration.valueChanged.connect(self.update_timeline_label)
            self.table.setCellWidget(row, 5, duration)

            status = QComboBox(self.table)
            status.addItems(
                ["Chưa dựng", "Đang chuẩn bị", "Đang render", "Đã render", "Lỗi"]
            )
            current_index = status.findText(shot.status)
            status.setCurrentIndex(max(0, current_index))
            self.table.setCellWidget(row, 6, status)

            self.table.setItem(row, 7, QTableWidgetItem(shot.asset_path))

        self.update_timeline_label()

    def collect_rows(self) -> list[StoryboardShot]:
        shots: list[StoryboardShot] = []

        for row in range(self.table.rowCount()):
            duration_widget = self.table.cellWidget(row, 5)
            status_widget = self.table.cellWidget(row, 6)

            shots.append(
                StoryboardShot(
                    shot_number=row + 1,
                    scene_number=self._int_cell(row, 1, 1),
                    title=self._text_cell(row, 2),
                    visual_description=self._text_cell(row, 3),
                    camera=self._text_cell(row, 4),
                    duration_seconds=duration_widget.value()
                    if isinstance(duration_widget, QSpinBox)
                    else 8,
                    veo_prompt=self._existing_prompt(row),
                    status=status_widget.currentText()
                    if isinstance(status_widget, QComboBox)
                    else "Chưa dựng",
                    asset_path=self._text_cell(row, 7),
                )
            )

        return shots

    def _existing_prompt(self, row: int) -> str:
        if 0 <= row < len(self.shots):
            return self.shots[row].veo_prompt
        return ""

    def _text_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _int_cell(self, row: int, column: int, default: int) -> int:
        try:
            return int(self._text_cell(row, column))
        except ValueError:
            return default

    def add_shot(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QTableWidgetItem("1"))
        self.table.setItem(row, 2, QTableWidgetItem(f"Shot {row + 1}"))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        self.table.setItem(row, 4, QTableWidgetItem("wide cinematic shot"))

        duration = QSpinBox(self.table)
        duration.setRange(1, 60)
        duration.setValue(8)
        duration.valueChanged.connect(self.update_timeline_label)
        self.table.setCellWidget(row, 5, duration)

        status = QComboBox(self.table)
        status.addItems(
            ["Chưa dựng", "Đang chuẩn bị", "Đang render", "Đã render", "Lỗi"]
        )
        self.table.setCellWidget(row, 6, status)
        self.table.setItem(row, 7, QTableWidgetItem(""))
        self.update_timeline_label()

    def remove_selected_shot(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self._renumber_rows()
        self.update_timeline_label()

    def move_selected(self, direction: int) -> None:
        row = self.table.currentRow()
        target = row + direction

        if row < 0 or target < 0 or target >= self.table.rowCount():
            return

        shots = self.collect_rows()
        shots[row], shots[target] = shots[target], shots[row]
        self.shots = shots
        self.render_table()
        self.table.selectRow(target)

    def _renumber_rows(self) -> None:
        for row in range(self.table.rowCount()):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def attach_asset(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Chưa chọn shot", "Hãy chọn một shot.")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh hoặc video",
            "",
            "Media (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv);;All files (*)",
        )
        if path:
            self.table.setItem(row, 7, QTableWidgetItem(path))

    def save_storyboard(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.shots = self.collect_rows()
        path = self.service.save(self.current_project_dir, self.shots)
        QMessageBox.information(
            self,
            "Đã lưu",
            f"Storyboard đã lưu tại:\n{path}",
        )

    def export_timeline(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        shots = self.collect_rows()
        source_path = self.service.save_timeline(self.current_project_dir, shots)

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất timeline",
            f"{self.current_project_dir.name}_timeline.json",
            "JSON files (*.json)",
        )
        if not destination:
            return

        Path(destination).write_text(
            source_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        QMessageBox.information(
            self,
            "Đã xuất",
            f"Timeline đã xuất tại:\n{destination}",
        )

    def update_timeline_label(self) -> None:
        total = 0
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 5)
            if isinstance(widget, QSpinBox):
                total += widget.value()
        minutes, seconds = divmod(total, 60)
        self.timeline_label.setText(
            f"Timeline: {minutes:02d}:{seconds:02d} · {self.table.rowCount()} shot"
        )
