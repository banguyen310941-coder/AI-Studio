from pathlib import Path

from app.workers.video_pipeline_worker import VideoPipelineWorker


class VideoAgent:
    """
    AI Agent điều khiển toàn bộ quy trình tạo video.

    Hiện tại Agent chỉ đóng vai trò khởi chạy
    VideoPipelineWorker.

    Sau này Agent sẽ chịu trách nhiệm:

    - Viết kịch bản
    - Chia cảnh
    - Tạo prompt
    - Tạo ảnh
    - Tạo giọng đọc
    - Tạo phụ đề
    - Dựng video
    - Xuất video
    """

    def __init__(
        self,
        project_path: Path,
        scenes: list[dict],
    ) -> None:

        self.project_path = Path(project_path)
        self.scenes = scenes

    def create_worker(
        self,
    ) -> VideoPipelineWorker:

        return VideoPipelineWorker(
            project_path=self.project_path,
            scenes=self.scenes,
        )