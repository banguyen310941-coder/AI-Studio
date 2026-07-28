from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.controllers.pipeline_controller import PipelineController
from app.controllers.project_controller import ProjectController
from app.controllers.scene_controller import SceneController
from app.controllers.script_controller import ScriptController
from app.core.event_bus import get_event_bus
from app.models.project_model import ProjectModel
from app.project_manager import ProjectManager
from app.services.history_service import HistoryService
from app.widgets.scene_card import SceneCard
from app.widgets.scene_editor_toolbar import SceneEditorToolbar


class ProjectPage(QWidget):
    """
    Trang chỉnh sửa và xử lý một dự án video.

    ProjectModel là nguồn dữ liệu chính.

    SceneCard chỉ hiển thị dữ liệu và phát tín hiệu khi người dùng
    chỉnh sửa nội dung.

    HistoryService quản lý snapshot để thực hiện Undo và Redo.
    """

    back_requested = Signal()

    HISTORY_DELAY_MS = 700

    FIELD_LABELS = {
        "title": "tiêu đề",
        "visual": "hình ảnh",
        "narration": "lời đọc",
        "screen_text": "chữ trên màn hình",
        "image_prompt": "prompt ảnh",
    }

    def __init__(
        self,
        project_manager: ProjectManager,
    ) -> None:
        super().__init__()

        self.project_manager = project_manager
        self.scene_cards: list[SceneCard] = []

        self._restoring_history = False
        self._pipeline_running = False
        self._pending_history_description = ""
        self._last_project_save_error = ""

        self.project_model = ProjectModel(
            parent=self
        )

        self.history = HistoryService(
            parent=self
        )

        self.project_controller = ProjectController(
            project_manager=project_manager,
            project_model=self.project_model,
            history_service=self.history,
            parent=self,
        )

        self.event_bus = get_event_bus()

        self.pipeline_controller = PipelineController(
            parent=self,
            event_bus=self.event_bus,
        )

        self.scene_controller = SceneController(
            project_path_provider=self.get_project_path,
            parent=self,
            event_bus=self.event_bus,
            project_model=self.project_model,
            history_service=self.history,
        )

        self.script_controller = ScriptController(
            project_model=self.project_model,
            history_service=self.history,
            parent=self,
        )

        self.history_timer = QTimer(
            self
        )
        self.history_timer.setSingleShot(
            True
        )
        self.history_timer.setInterval(
            self.HISTORY_DELAY_MS
        )
        self.history_timer.timeout.connect(
            self.commit_pending_history
        )

        self.build_ui()
        self.create_shortcuts()

        self.connect_event_bus()
        self.connect_project_model()
        self.connect_history_service()
        self.connect_project_controller()
        self.connect_scene_editor()
        self.connect_scene_controller()
        self.connect_script_controller()

    def connect_event_bus(self) -> None:
        """
        Kết nối ProjectPage với EventBus.
        """

        self.event_bus.pipeline_progress.connect(
            self.update_pipeline_progress
        )

        self.event_bus.pipeline_scene_completed.connect(
            self.handle_scene_completed
        )

        self.event_bus.pipeline_completed.connect(
            self.handle_pipeline_completed
        )

        self.event_bus.pipeline_failed.connect(
            self.handle_pipeline_failed
        )

        self.event_bus.pipeline_running_changed.connect(
            self.set_pipeline_controls
        )

        self.event_bus.pipeline_finished.connect(
            self.handle_pipeline_finished
        )

        self.event_bus.scene_warning.connect(
            self.show_scene_warning
        )

        self.event_bus.scene_error.connect(
            self.show_scene_error
        )

    def connect_project_model(self) -> None:
        """
        Kết nối dữ liệu trung tâm với giao diện.
        """

        self.project_model.scenes_changed.connect(
            self.display_scenes
        )

        self.project_model.dirty_changed.connect(
            self.on_dirty_changed
        )

    def connect_history_service(self) -> None:
        """
        Kết nối HistoryService với giao diện.
        """

        self.history.history_changed.connect(
            self.update_history_controls
        )

        self.history.state_restored.connect(
            self.restore_history_state
        )

        self.history.error_occurred.connect(
            self.show_scene_error
        )

    def connect_project_controller(self) -> None:
        """
        Kết nối ProjectController với giao diện.
        """

        self.project_controller.project_loaded.connect(
            self.handle_project_loaded
        )

        self.project_controller.project_load_failed.connect(
            self.handle_project_load_failed
        )

        self.project_controller.project_saved.connect(
            self.handle_project_saved
        )

        self.project_controller.project_save_failed.connect(
            self.handle_project_save_failed
        )

    def connect_scene_editor(self) -> None:
        """
        Kết nối SceneEditorToolbar với SceneController và lịch sử.
        """

        self.scene_toolbar.add_scene_requested.connect(
            self.request_add_scene
        )

        self.scene_toolbar.duplicate_scene_requested.connect(
            self.request_duplicate_scene
        )

        self.scene_toolbar.delete_scene_requested.connect(
            self.request_delete_scene
        )

        self.scene_toolbar.move_scene_up_requested.connect(
            self.request_move_scene_up
        )

        self.scene_toolbar.move_scene_down_requested.connect(
            self.request_move_scene_down
        )

        self.scene_toolbar.scene_selected.connect(
            self.scene_controller.select_scene
        )

        self.scene_toolbar.undo_requested.connect(
            self.undo
        )

        self.scene_toolbar.redo_requested.connect(
            self.redo
        )

    def connect_scene_controller(self) -> None:
        """
        Kết nối các yêu cầu điều hướng của SceneController với giao diện.
        """

        self.scene_controller.scene_focus_requested.connect(
            self.focus_scene
        )

        self.scene_controller.warning_requested.connect(
            self.show_scene_warning
        )

        self.scene_controller.error_occurred.connect(
            self.show_scene_error
        )

    def connect_script_controller(self) -> None:
        """
        Kết nối ScriptController với giao diện.
        """

        self.script_controller.generation_started.connect(
            self.handle_script_generation_started
        )

        self.script_controller.generation_finished.connect(
            self.handle_script_generation_finished
        )

        self.script_controller.generation_failed.connect(
            self.handle_script_generation_failed
        )

        self.script_controller.warning_requested.connect(
            self.show_scene_warning
        )

    def create_shortcuts(self) -> None:
        """
        Tạo phím tắt Undo và Redo.

        macOS:
            Cmd + Z
            Cmd + Shift + Z

        Windows/Linux:
            Ctrl + Z
            Ctrl + Shift + Z
        """

        self.undo_shortcut = QShortcut(
            QKeySequence(
                QKeySequence.StandardKey.Undo
            ),
            self,
        )
        self.undo_shortcut.activated.connect(
            self.undo
        )

        self.redo_shortcut = QShortcut(
            QKeySequence(
                QKeySequence.StandardKey.Redo
            ),
            self,
        )
        self.redo_shortcut.activated.connect(
            self.redo
        )

    def show_scene_warning(
        self,
        title: str,
        message: str,
    ) -> None:
        QMessageBox.warning(
            self,
            title,
            message,
        )

    def show_scene_error(
        self,
        title: str,
        message: str,
    ) -> None:
        QMessageBox.critical(
            self,
            title,
            message,
        )

    def build_ui(self) -> None:
        main_layout = QVBoxLayout(
            self
        )
        main_layout.setContentsMargins(
            40,
            30,
            40,
            30,
        )
        main_layout.setSpacing(16)

        top_layout = QHBoxLayout()

        back_button = QPushButton(
            "← Quay lại"
        )
        back_button.setObjectName(
            "secondaryButton"
        )
        back_button.clicked.connect(
            self.back_requested.emit
        )

        self.project_title = QLabel(
            "Chi tiết dự án"
        )
        self.project_title.setObjectName(
            "pageTitle"
        )

        top_layout.addWidget(
            back_button
        )
        top_layout.addSpacing(15)
        top_layout.addWidget(
            self.project_title
        )
        top_layout.addStretch()

        description = QLabel(
            "AI viết kịch bản, chia cảnh, tạo ảnh, "
            "giọng đọc và xuất video MP4."
        )
        description.setObjectName(
            "description"
        )
        description.setWordWrap(
            True
        )

        topic_card = QFrame()
        topic_card.setObjectName(
            "card"
        )

        topic_layout = QVBoxLayout(
            topic_card
        )
        topic_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )
        topic_layout.setSpacing(12)

        topic_title = QLabel(
            "Chủ đề video"
        )
        topic_title.setObjectName(
            "cardTitle"
        )

        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText(
            "Ví dụ: Video quảng cáo resort "
            "Oceanami Long Hải..."
        )
        self.topic_input.setFixedHeight(
            75
        )

        action_layout = QHBoxLayout()

        self.generate_button = QPushButton(
            "✨ AI tạo kịch bản và chia cảnh"
        )
        self.generate_button.setObjectName(
            "primaryButton"
        )
        self.generate_button.clicked.connect(
            self.generate_scenes
        )

        self.save_button = QPushButton(
            "💾 Lưu dự án"
        )
        self.save_button.setObjectName(
            "secondaryButton"
        )
        self.save_button.clicked.connect(
            self.save_project
        )

        self.auto_video_button = QPushButton(
            "🚀 Tạo toàn bộ video"
        )
        self.auto_video_button.setObjectName(
            "primaryButton"
        )
        self.auto_video_button.clicked.connect(
            self.start_full_video_pipeline
        )

        self.stop_button = QPushButton(
            "⏹ Dừng"
        )
        self.stop_button.setObjectName(
            "secondaryButton"
        )
        self.stop_button.setEnabled(
            False
        )
        self.stop_button.clicked.connect(
            self.stop_full_video_pipeline
        )

        self.open_video_button = QPushButton(
            "▶ Mở video"
        )
        self.open_video_button.setObjectName(
            "secondaryButton"
        )
        self.open_video_button.setEnabled(
            False
        )
        self.open_video_button.clicked.connect(
            self.open_final_video
        )

        action_layout.addWidget(
            self.generate_button
        )
        action_layout.addWidget(
            self.save_button
        )
        action_layout.addWidget(
            self.auto_video_button
        )
        action_layout.addWidget(
            self.stop_button
        )
        action_layout.addWidget(
            self.open_video_button
        )
        action_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(
            0,
            100,
        )
        self.progress_bar.setValue(
            0
        )
        self.progress_bar.setTextVisible(
            True
        )

        self.status_label = QLabel(
            "Kịch bản: Chưa có"
        )
        self.status_label.setObjectName(
            "description"
        )

        topic_layout.addWidget(
            topic_title
        )
        topic_layout.addWidget(
            self.topic_input
        )
        topic_layout.addLayout(
            action_layout
        )
        topic_layout.addWidget(
            self.progress_bar
        )
        topic_layout.addWidget(
            self.status_label
        )

        scenes_title = QLabel(
            "Danh sách cảnh"
        )
        scenes_title.setObjectName(
            "cardTitle"
        )

        self.scene_toolbar = SceneEditorToolbar(
            parent=self
        )

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(
            True
        )
        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.scenes_widget = QWidget()

        self.scenes_layout = QVBoxLayout(
            self.scenes_widget
        )
        self.scenes_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self.scenes_layout.setSpacing(
            15
        )
        self.scenes_layout.addStretch()

        self.scroll_area.setWidget(
            self.scenes_widget
        )

        main_layout.addLayout(
            top_layout
        )
        main_layout.addWidget(
            description
        )
        main_layout.addWidget(
            topic_card
        )
        main_layout.addWidget(
            scenes_title
        )
        main_layout.addWidget(
            self.scene_toolbar
        )
        main_layout.addWidget(
            self.scroll_area,
            1,
        )

    def load_project(
        self,
        project_name: str,
    ) -> None:
        """
        Yêu cầu ProjectController mở dự án.
        """

        self.history_timer.stop()
        self._pending_history_description = ""

        self.topic_input.clear()
        self.progress_bar.setValue(
            0
        )
        self.open_video_button.setEnabled(
            False
        )

        self.project_controller.open_project(
            project_name
        )

    def handle_project_loaded(
        self,
        project_name: str,
        scene_count: int,
    ) -> None:
        """
        Cập nhật giao diện sau khi mở dự án thành công.
        """

        self.topic_input.setPlainText(
            self.project_model.get_topic()
        )

        self.on_dirty_changed(
            False
        )

        self.open_video_button.setEnabled(
            self.get_final_video_path().exists()
        )

        if scene_count > 0:
            self.status_label.setText(
                (
                    f"Kịch bản: Đã tải "
                    f"{scene_count} cảnh"
                )
            )
        else:
            self.status_label.setText(
                "Kịch bản: Chưa có"
            )

    def handle_project_load_failed(
        self,
        message: str,
    ) -> None:
        QMessageBox.critical(
            self,
            "Lỗi mở dự án",
            message,
        )

    def handle_project_saved(
        self,
        scene_count: int,
    ) -> None:
        """
        Cập nhật giao diện sau khi lưu thành công.
        """

        self.on_dirty_changed(
            False
        )

        self.status_label.setText(
            f"Đã lưu {scene_count} cảnh"
        )

    def handle_project_save_failed(
        self,
        message: str,
    ) -> None:
        """
        Signal này chủ yếu phục vụ thao tác lưu không hiện hộp thoại.
        Hàm save_project sẽ tự quyết định có hiển thị lỗi hay không.
        """

        self._last_project_save_error = message

    def generate_scenes(self) -> None:
        """
        Yêu cầu ScriptController tạo kịch bản AI.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()

        topic = (
            self.topic_input
            .toPlainText()
        )

        self.script_controller.generate(
            topic
        )

    def handle_script_generation_started(
        self,
    ) -> None:
        """
        Cập nhật giao diện khi AI bắt đầu tạo kịch bản.
        """

        self.generate_button.setEnabled(
            False
        )
        self.generate_button.setText(
            "⏳ AI đang tạo các cảnh..."
        )
        self.status_label.setText(
            "AI đang tạo kịch bản..."
        )

    def handle_script_generation_finished(
        self,
        scene_count: int,
    ) -> None:
        """
        Cập nhật giao diện khi AI tạo kịch bản thành công.
        """

        self.generate_button.setEnabled(
            not self._pipeline_running
        )
        self.generate_button.setText(
            "✨ AI tạo kịch bản và chia cảnh"
        )
        self.status_label.setText(
            (
                f"AI đã tạo {scene_count} "
                "cảnh, chưa lưu"
            )
        )

    def handle_script_generation_failed(
        self,
        message: str,
    ) -> None:
        """
        Khôi phục giao diện và hiển thị lỗi tạo kịch bản.
        """

        self.generate_button.setEnabled(
            not self._pipeline_running
        )
        self.generate_button.setText(
            "✨ AI tạo kịch bản và chia cảnh"
        )
        self.status_label.setText(
            "Tạo kịch bản thất bại"
        )

        self.show_scene_error(
            "Lỗi tạo kịch bản",
            message,
        )

    def display_scenes(
        self,
        scenes: list[dict],
    ) -> None:
        """
        Dựng danh sách SceneCard từ ProjectModel.

        Hàm này được gọi khi:
        - Mở dự án.
        - AI tạo kịch bản.
        - Undo/Redo khôi phục snapshot.
        """

        selected_scene = (
            self.scene_toolbar
            .get_selected_scene_number()
        )

        self.clear_scenes()

        for index, scene in enumerate(
            scenes,
            start=1,
        ):
            card = SceneCard(
                scene_number=index,
                title=str(
                    scene.get(
                        "title",
                        "",
                    )
                ),
                visual=str(
                    scene.get(
                        "visual",
                        "",
                    )
                ),
                narration=str(
                    scene.get(
                        "narration",
                        "",
                    )
                ),
                screen_text=str(
                    scene.get(
                        "screen_text",
                        "",
                    )
                ),
                image_prompt=str(
                    scene.get(
                        "image_prompt",
                        "",
                    )
                ),
            )

            card.field_changed.connect(
                self.handle_scene_field_changed
            )

            self.scene_cards.append(
                card
            )

            self.scene_controller.register_card(
                card
            )

            self.scenes_layout.insertWidget(
                self.scenes_layout.count() - 1,
                card,
            )

        scene_count = len(scenes)

        self.scene_toolbar.set_scene_count(
            scene_count
        )

        if scene_count > 0:
            target_scene = min(
                max(selected_scene, 1),
                scene_count,
            )

            self.scene_toolbar.set_selected_scene(
                target_scene
            )

    def clear_scenes(self) -> None:
        """
        Xóa toàn bộ SceneCard khỏi giao diện.
        """

        self.scene_controller.unregister_all_cards()

        for card in self.scene_cards:
            self.scenes_layout.removeWidget(
                card
            )
            card.deleteLater()

        self.scene_cards.clear()

    def handle_scene_field_changed(
        self,
        scene_number: int,
        field_name: str,
        value: str,
    ) -> None:
        """
        Nhận thay đổi từ SceneCard và cập nhật ProjectModel.

        Lịch sử không được tạo cho từng ký tự. QTimer sẽ gom các
        lần gõ liên tiếp thành một thao tác Undo duy nhất.
        """

        if self._restoring_history:
            return

        try:
            changed = (
                self.project_model
                .update_scene_field(
                    scene_number=scene_number,
                    field_name=field_name,
                    value=value,
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Lỗi cập nhật cảnh",
                str(error),
            )
            return

        if not changed:
            return

        field_label = self.FIELD_LABELS.get(
            field_name,
            field_name,
        )

        self.queue_history_snapshot(
            (
                f"Sửa {field_label} "
                f"Cảnh {scene_number}"
            )
        )

    def queue_history_snapshot(
        self,
        description: str,
    ) -> None:
        """
        Hẹn lưu snapshot sau khi người dùng ngừng nhập.
        """

        if self._restoring_history:
            return

        self._pending_history_description = (
            description.strip()
            or "Chỉnh sửa dự án"
        )

        self.history_timer.start()

    def commit_pending_history(self) -> bool:
        """
        Lưu thay đổi đang chờ vào HistoryService.

        Trả về True nếu có snapshot mới được lưu.
        """

        self.history_timer.stop()

        description = (
            self._pending_history_description
            .strip()
        )

        self._pending_history_description = ""

        if not description:
            return False

        if not (
            self.project_model
            .get_project_name()
        ):
            return False

        return self.history.push(
            state=(
                self.project_model
                .create_snapshot()
            ),
            description=description,
        )

    def undo(self) -> None:
        """
        Hoàn tác thay đổi gần nhất.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()

        if not self.history.can_undo():
            return

        self.history.undo()

    def redo(self) -> None:
        """
        Làm lại thay đổi vừa hoàn tác.
        """

        if self._pipeline_running:
            return

        if not self.history.can_redo():
            return

        self.history.redo()

    def restore_history_state(
        self,
        snapshot: dict,
    ) -> None:
        """
        Áp dụng snapshot do HistoryService trả về.
        """

        self.history_timer.stop()
        self._pending_history_description = ""

        self._restoring_history = True

        try:
            should_be_dirty = not (
                self.snapshot_matches_saved(
                    snapshot
                )
            )

            self.project_model.restore_snapshot(
                snapshot=snapshot,
                mark_dirty=should_be_dirty,
            )

            topic = str(
                snapshot.get(
                    "topic",
                    "",
                )
            )

            self.topic_input.setPlainText(
                topic
            )

            self.on_dirty_changed(
                should_be_dirty
            )

            if should_be_dirty:
                self.status_label.setText(
                    "Đã khôi phục thay đổi, chưa lưu."
                )
            else:
                self.status_label.setText(
                    "Đã khôi phục trạng thái đã lưu."
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Lỗi khôi phục lịch sử",
                str(error),
            )

        finally:
            self._restoring_history = False

    def snapshot_matches_saved(
        self,
        snapshot: dict[str, Any],
    ) -> bool:
        """
        Ủy quyền việc so sánh trạng thái đã lưu cho ProjectController.
        """

        return (
            self.project_controller
            .snapshot_matches_saved(
                snapshot
            )
        )

    def update_history_controls(
        self,
        can_undo: bool,
        can_redo: bool,
    ) -> None:
        """
        Bật hoặc tắt nút Undo/Redo.
        """

        controls_available = not (
            self._pipeline_running
        )

        self.scene_toolbar.set_history_state(
            can_undo=(
                can_undo
                and controls_available
            ),
            can_redo=(
                can_redo
                and controls_available
            ),
            undo_description=(
                self.history
                .get_undo_description()
            ),
            redo_description=(
                self.history
                .get_redo_description()
            ),
        )

    def request_add_scene(self) -> None:
        """
        Thêm một cảnh mới sau khi lưu thay đổi văn bản đang chờ.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()
        self.scene_controller.add_scene()

    def request_duplicate_scene(
        self,
        scene_number: int,
    ) -> None:
        """
        Nhân đôi cảnh đang chọn.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()
        self.scene_controller.duplicate_scene(
            scene_number
        )

    def request_delete_scene(
        self,
        scene_number: int,
    ) -> None:
        """
        Hỏi xác nhận trước khi xóa cảnh.
        """

        if self._pipeline_running:
            return

        scene = self.project_model.get_scene(
            scene_number
        )

        if scene is None:
            return

        title = str(
            scene.get(
                "title",
                "",
            )
        ).strip()

        scene_label = (
            f"Cảnh {scene_number}: {title}"
            if title
            else f"Cảnh {scene_number}"
        )

        reply = QMessageBox.question(
            self,
            "Xóa cảnh",
            (
                f"Bạn có chắc muốn xóa {scene_label}?\n\n"
                "Thao tác này có thể hoàn tác bằng Undo."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.commit_pending_history()
        self.scene_controller.delete_scene(
            scene_number
        )

    def request_move_scene_up(
        self,
        scene_number: int,
    ) -> None:
        """
        Di chuyển cảnh lên một vị trí.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()
        self.scene_controller.move_scene_up(
            scene_number
        )

    def request_move_scene_down(
        self,
        scene_number: int,
    ) -> None:
        """
        Di chuyển cảnh xuống một vị trí.
        """

        if self._pipeline_running:
            return

        self.commit_pending_history()
        self.scene_controller.move_scene_down(
            scene_number
        )

    def focus_scene(
        self,
        scene_number: int,
    ) -> None:
        """
        Chọn cảnh trên toolbar và cuộn SceneCard vào vùng nhìn thấy.
        """

        self.scene_toolbar.set_selected_scene(
            scene_number
        )

        card = self.find_scene_card(
            scene_number
        )

        if card is None:
            return

        self.scroll_area.ensureWidgetVisible(
            card,
            0,
            20,
        )

        card.setFocus()

    def find_scene_card(
        self,
        scene_number: int,
    ) -> SceneCard | None:
        for card in self.scene_cards:
            if (
                card.scene_number
                == scene_number
            ):
                return card

        return None

    def get_project_path(self) -> Path:
        return (
            self.project_controller
            .get_project_path()
        )

    def get_final_video_path(self) -> Path:
        return (
            self.project_controller
            .get_final_video_path()
        )

    def start_full_video_pipeline(
        self,
    ) -> None:
        """
        Lưu dữ liệu hiện tại và bắt đầu tạo toàn bộ video.
        """

        if (
            self.pipeline_controller
            .is_running()
        ):
            QMessageBox.information(
                self,
                "Đang xử lý",
                "AI Studio đang tạo video.",
            )
            return

        self.commit_pending_history()

        scenes = (
            self.project_model
            .get_scenes()
        )

        if not scenes:
            QMessageBox.warning(
                self,
                "Chưa có cảnh",
                "Bạn cần tạo kịch bản trước.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Tạo toàn bộ video",
            (
                f"AI Studio sẽ xử lý "
                f"{len(scenes)} cảnh.\n\n"
                "Quá trình này có thể "
                "phát sinh chi phí API.\n"
                "Bạn có muốn tiếp tục?"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            reply
            != QMessageBox.StandardButton.Yes
        ):
            return

        project_saved = self.save_project(
            show_message=False
        )

        if not project_saved:
            QMessageBox.critical(
                self,
                "Không thể bắt đầu",
                "Không thể lưu dữ liệu dự án.",
            )
            return

        scenes = (
            self.project_model
            .get_scenes()
        )

        self.progress_bar.setValue(
            0
        )
        self.open_video_button.setEnabled(
            False
        )

        try:
            started = (
                self.pipeline_controller
                .start(
                    project_path=(
                        self.get_project_path()
                    ),
                    scenes=scenes,
                )
            )

            if not started:
                QMessageBox.information(
                    self,
                    "Đang xử lý",
                    "AI Studio đang tạo video.",
                )

        except Exception as error:
            self.set_pipeline_controls(
                False
            )

            QMessageBox.critical(
                self,
                "Không thể tạo video",
                str(error),
            )

    def stop_full_video_pipeline(
        self,
    ) -> None:
        if not (
            self.pipeline_controller
            .is_running()
        ):
            return

        self.stop_button.setEnabled(
            False
        )

        self.status_label.setText(
            "Đang yêu cầu dừng..."
        )

        cancelled = (
            self.pipeline_controller
            .cancel()
        )

        if not cancelled:
            self.status_label.setText(
                "Không có tiến trình đang chạy."
            )

    def update_pipeline_progress(
        self,
        progress: int,
        message: str,
    ) -> None:
        self.progress_bar.setValue(
            progress
        )

        self.status_label.setText(
            message
        )

    def handle_scene_completed(
        self,
        scene_number: int,
        video_path_text: str,
    ) -> None:
        self.scene_controller.refresh_scene(
            scene_number=scene_number,
            video_path=video_path_text,
        )

    def handle_pipeline_completed(
        self,
        final_path_text: str,
    ) -> None:
        final_path = Path(
            final_path_text
        )

        self.progress_bar.setValue(
            100
        )

        self.status_label.setText(
            "Video hoàn chỉnh đã được tạo."
        )

        self.open_video_button.setEnabled(
            True
        )

        QMessageBox.information(
            self,
            "Tạo video thành công",
            (
                "Video đã được lưu tại:\n"
                f"{final_path}"
            ),
        )

        subprocess.run(
            [
                "open",
                str(final_path),
            ],
            check=False,
        )

    def handle_pipeline_failed(
        self,
        error_message: str,
    ) -> None:
        self.status_label.setText(
            "Quá trình tạo video không hoàn thành."
        )

        QMessageBox.critical(
            self,
            "Lỗi tạo video",
            error_message,
        )

    def handle_pipeline_finished(
        self,
    ) -> None:
        """
        Được gọi sau khi Worker đã dừng hoàn toàn.
        """

        if (
            self.progress_bar.value()
            < 100
            and self.status_label.text()
            == "Đang yêu cầu dừng..."
        ):
            self.status_label.setText(
                "Quá trình tạo video đã được dừng."
            )

    def set_pipeline_controls(
        self,
        running: bool,
    ) -> None:
        """
        Bật hoặc tắt các nút trong khi Pipeline hoạt động.
        """

        self._pipeline_running = running

        self.generate_button.setEnabled(
            not running
        )

        self.save_button.setEnabled(
            not running
        )

        self.auto_video_button.setEnabled(
            not running
        )

        self.stop_button.setEnabled(
            running
        )

        self.scene_toolbar.set_editing_enabled(
            not running
        )

        self.scene_controller.set_editing_enabled(
            not running
        )

        self.update_history_controls(
            self.history.can_undo(),
            self.history.can_redo(),
        )

    def open_final_video(self) -> None:
        final_path = (
            self.get_final_video_path()
        )

        if not final_path.exists():
            QMessageBox.warning(
                self,
                "Không tìm thấy video",
                "Dự án chưa có final_video.mp4.",
            )
            return

        subprocess.run(
            [
                "open",
                str(final_path),
            ],
            check=False,
        )

    def save_project(
        self,
        show_message: bool = True,
    ) -> bool:
        """
        Yêu cầu ProjectController lưu ProjectModel hiện tại.
        """

        self.commit_pending_history()

        if not self.project_model.get_scenes():
            if show_message:
                QMessageBox.warning(
                    self,
                    "Chưa có cảnh",
                    "Không có dữ liệu để lưu.",
                )
            return False

        self._last_project_save_error = ""

        saved = (
            self.project_controller
            .save_current_project()
        )

        if not saved:
            if show_message:
                QMessageBox.critical(
                    self,
                    "Lỗi lưu dự án",
                    (
                        self._last_project_save_error
                        or "Không thể lưu dữ liệu dự án."
                    ),
                )
            return False

        if show_message:
            scene_count = len(
                self.project_model.get_scenes()
            )

            QMessageBox.information(
                self,
                "Lưu thành công",
                f"Đã lưu {scene_count} cảnh.",
            )

        return True

    def on_dirty_changed(
        self,
        dirty: bool,
    ) -> None:
        """
        Hiển thị dấu * nếu dự án có thay đổi chưa lưu.
        """

        project_name = (
            self.project_model
            .get_project_name()
        )

        if not project_name:
            self.project_title.setText(
                "Chi tiết dự án"
            )
            return

        if dirty:
            self.project_title.setText(
                f"📁 {project_name} *"
            )
        else:
            self.project_title.setText(
                f"📁 {project_name}"
            )