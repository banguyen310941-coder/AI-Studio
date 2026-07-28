from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.music_service import MusicService, MusicTrack


class MusicStudioPage(QWidget):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.projects_root = Path(__file__).resolve().parent.parent / "projects"
        self.service = MusicService()
        self.current_project_dir: Path | None = None
        self.tracks: list[MusicTrack] = []
        self._build_ui()
        self.refresh_projects()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("🎵 Music & Sound FX", self)
        title.setObjectName("pageTitle")
        description = QLabel(
            "Quản lý nhạc nền, hiệu ứng âm thanh, âm lượng, thời điểm và fade.",
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

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._create_project_panel())
        splitter.addWidget(self._create_tracks_panel())
        splitter.setSizes([240, 1000])
        root.addWidget(splitter, 1)

    def _create_project_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)

        label = QLabel("Dự án", panel)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)

        self.project_list = QListWidget(panel)
        self.project_list.itemDoubleClicked.connect(self.open_project)
        layout.addWidget(self.project_list, 1)

        refresh_button = QPushButton("↻ Làm mới", panel)
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_projects)
        layout.addWidget(refresh_button)

        open_button = QPushButton("Mở dự án", panel)
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(self.open_project)
        layout.addWidget(open_button)
        return panel

    def _create_tracks_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()

        self.project_label = QLabel("Chưa mở dự án", panel)
        self.project_label.setObjectName("sectionTitle")
        toolbar.addWidget(self.project_label)
        toolbar.addStretch()

        add_music = QPushButton("＋ Nhạc nền", panel)
        add_music.setObjectName("secondaryButton")
        add_music.clicked.connect(lambda: self.add_track("Nhạc nền"))
        toolbar.addWidget(add_music)

        add_sfx = QPushButton("＋ Sound FX", panel)
        add_sfx.setObjectName("secondaryButton")
        add_sfx.clicked.connect(lambda: self.add_track("Sound FX"))
        toolbar.addWidget(add_sfx)

        remove_button = QPushButton("− Xóa", panel)
        remove_button.setObjectName("secondaryButton")
        remove_button.clicked.connect(self.remove_selected)
        toolbar.addWidget(remove_button)

        save_button = QPushButton("💾 Lưu kế hoạch âm thanh", panel)
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_plan)
        toolbar.addWidget(save_button)

        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 10, panel)
        self.table.setHorizontalHeaderLabels(
            [
                "Bật",
                "Tên",
                "Loại",
                "Bắt đầu",
                "Thời lượng",
                "Âm lượng",
                "Fade In",
                "Fade Out",
                "Loop",
                "Tệp nguồn",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 180)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 55)
        self.table.setColumnWidth(9, 360)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()

        manifest_button = QPushButton("🎚 Tạo Mix Manifest", panel)
        manifest_button.setObjectName("secondaryButton")
        manifest_button.clicked.connect(self.create_manifest)
        footer.addWidget(manifest_button)

        footer.addStretch()

        self.summary_label = QLabel("0 track · 00:00", panel)
        self.summary_label.setObjectName("description")
        footer.addWidget(self.summary_label)

        layout.addLayout(footer)
        return panel

    def refresh_projects(self) -> None:
        self.project_list.clear()
        self.projects_root.mkdir(parents=True, exist_ok=True)

        projects = sorted(
            [path for path in self.projects_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for project_dir in projects:
            item = QListWidgetItem(project_dir.name)
            item.setData(Qt.ItemDataRole.UserRole, str(project_dir))
            self.project_list.addItem(item)

    def open_project(self, item=None) -> None:
        if item is None:
            item = self.project_list.currentItem()
        if item is None:
            QMessageBox.warning(self, "Chưa chọn dự án", "Hãy chọn một dự án.")
            return

        self.current_project_dir = Path(item.data(Qt.ItemDataRole.UserRole))
        self.tracks = self.service.load_plan(self.current_project_dir)
        self.project_label.setText(f"Dự án: {self.current_project_dir.name}")
        self.render_tracks()

    def add_track(self, kind: str) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp âm thanh",
            "",
            "Audio (*.mp3 *.wav *.aiff *.m4a *.aac *.flac);;All files (*)",
        )
        if not path:
            return

        source_path = Path(path)
        copied_path = self.service.copy_into_project(
            self.current_project_dir,
            source_path,
            kind,
        )
        self.tracks.append(
            MusicTrack(
                name=source_path.stem,
                kind=kind,
                source_path=str(copied_path),
                start_seconds=0,
                duration_seconds=30 if kind == "Nhạc nền" else 5,
                volume=65 if kind == "Nhạc nền" else 85,
                fade_in_seconds=2 if kind == "Nhạc nền" else 0,
                fade_out_seconds=2 if kind == "Nhạc nền" else 0,
                loop=kind == "Nhạc nền",
                enabled=True,
            )
        )
        self.render_tracks()

    def render_tracks(self) -> None:
        self.table.setRowCount(0)

        for track in self.tracks:
            row = self.table.rowCount()
            self.table.insertRow(row)

            enabled = QCheckBox(self.table)
            enabled.setChecked(track.enabled)
            enabled.stateChanged.connect(self.update_summary)
            self.table.setCellWidget(row, 0, enabled)

            self.table.setItem(row, 1, QTableWidgetItem(track.name))

            kind = QComboBox(self.table)
            kind.addItems(["Nhạc nền", "Sound FX"])
            kind.setCurrentText(track.kind)
            self.table.setCellWidget(row, 2, kind)

            start = QSpinBox(self.table)
            start.setRange(0, 86400)
            start.setValue(track.start_seconds)
            start.setSuffix(" s")
            start.valueChanged.connect(self.update_summary)
            self.table.setCellWidget(row, 3, start)

            duration = QSpinBox(self.table)
            duration.setRange(1, 86400)
            duration.setValue(track.duration_seconds)
            duration.setSuffix(" s")
            duration.valueChanged.connect(self.update_summary)
            self.table.setCellWidget(row, 4, duration)

            volume_box = QWidget(self.table)
            volume_layout = QHBoxLayout(volume_box)
            volume_layout.setContentsMargins(0, 0, 0, 0)
            volume = QSlider(Qt.Orientation.Horizontal, volume_box)
            volume.setRange(0, 100)
            volume.setValue(track.volume)
            volume_value = QLabel(f"{track.volume}%", volume_box)
            volume.valueChanged.connect(
                lambda value, label=volume_value: label.setText(f"{value}%")
            )
            volume_layout.addWidget(volume)
            volume_layout.addWidget(volume_value)
            self.table.setCellWidget(row, 5, volume_box)

            fade_in = QSpinBox(self.table)
            fade_in.setRange(0, 60)
            fade_in.setValue(track.fade_in_seconds)
            fade_in.setSuffix(" s")
            self.table.setCellWidget(row, 6, fade_in)

            fade_out = QSpinBox(self.table)
            fade_out.setRange(0, 60)
            fade_out.setValue(track.fade_out_seconds)
            fade_out.setSuffix(" s")
            self.table.setCellWidget(row, 7, fade_out)

            loop = QCheckBox(self.table)
            loop.setChecked(track.loop)
            self.table.setCellWidget(row, 8, loop)

            self.table.setItem(row, 9, QTableWidgetItem(track.source_path))
            self.table.setRowHeight(row, 44)

        self.update_summary()

    def collect_tracks(self) -> list[MusicTrack]:
        tracks: list[MusicTrack] = []

        for row in range(self.table.rowCount()):
            enabled = self.table.cellWidget(row, 0)
            kind = self.table.cellWidget(row, 2)
            start = self.table.cellWidget(row, 3)
            duration = self.table.cellWidget(row, 4)
            volume_box = self.table.cellWidget(row, 5)
            fade_in = self.table.cellWidget(row, 6)
            fade_out = self.table.cellWidget(row, 7)
            loop = self.table.cellWidget(row, 8)

            volume_slider = (
                volume_box.findChild(QSlider)
                if isinstance(volume_box, QWidget)
                else None
            )

            tracks.append(
                MusicTrack(
                    name=self._text_cell(row, 1),
                    kind=kind.currentText() if isinstance(kind, QComboBox) else "Nhạc nền",
                    source_path=self._text_cell(row, 9),
                    start_seconds=start.value() if isinstance(start, QSpinBox) else 0,
                    duration_seconds=duration.value()
                    if isinstance(duration, QSpinBox)
                    else 30,
                    volume=volume_slider.value()
                    if isinstance(volume_slider, QSlider)
                    else 70,
                    fade_in_seconds=fade_in.value()
                    if isinstance(fade_in, QSpinBox)
                    else 0,
                    fade_out_seconds=fade_out.value()
                    if isinstance(fade_out, QSpinBox)
                    else 0,
                    loop=loop.isChecked() if isinstance(loop, QCheckBox) else False,
                    enabled=enabled.isChecked()
                    if isinstance(enabled, QCheckBox)
                    else True,
                )
            )

        return tracks

    def _text_cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self.update_summary()

    def save_plan(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.tracks = self.collect_tracks()
        path = self.service.save_plan(self.current_project_dir, self.tracks)
        self.summary_label.setText(f"Đã lưu {path.name}")

    def create_manifest(self) -> None:
        if self.current_project_dir is None:
            QMessageBox.warning(self, "Chưa mở dự án", "Hãy mở một dự án trước.")
            return

        self.tracks = self.collect_tracks()
        self.service.save_plan(self.current_project_dir, self.tracks)
        path = self.service.create_mix_manifest(
            self.current_project_dir,
            self.tracks,
        )
        QMessageBox.information(
            self,
            "Đã tạo Mix Manifest",
            f"Đã lưu:\n{path}",
        )

    def update_summary(self) -> None:
        tracks = self.collect_tracks()
        enabled = [track for track in tracks if track.enabled]
        total = max(
            (track.start_seconds + track.duration_seconds for track in enabled),
            default=0,
        )
        minutes, seconds = divmod(total, 60)
        self.summary_label.setText(
            f"{len(enabled)} track đang bật · {minutes:02d}:{seconds:02d}"
        )
