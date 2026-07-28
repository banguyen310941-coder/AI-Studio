import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


class ConfigService:
    """
    Quản lý cấu hình chung của AI Studio.

    Cấu hình được lưu trong file config.json
    tại thư mục gốc của dự án.
    """

    DEFAULT_CONFIG: dict[str, Any] = {
        "openai": {
            "api_key": "",
            "image_model": "gpt-image-1",
            "voice_model": "gpt-4o-mini-tts",
            "voice": "alloy",
        },
        "image": {
            "size": "1536x1024",
            "quality": "medium",
        },
        "video": {
            "width": 1280,
            "height": 720,
            "fps": 30,
        },
        "subtitle": {
            "enabled": True,
            "font_name": "Arial",
            "font_size": 22,
            "margin_bottom": 42,
            "max_words_per_caption": 8,
        },
        "project": {
            "directory": "projects",
        },
    }

    def __init__(
        self,
        config_path: Path | str | None = None,
    ) -> None:
        if config_path is None:
            self.config_path = (
                Path.cwd() / "config.json"
            )
        else:
            self.config_path = Path(
                config_path
            )

        self.config: dict[str, Any] = {}

        self.load()

    def load(self) -> dict[str, Any]:
        """
        Đọc cấu hình từ config.json.

        Nếu file chưa tồn tại, hệ thống sẽ tạo file mới
        bằng cấu hình mặc định.
        """

        if not self.config_path.exists():
            self.config = deepcopy(
                self.DEFAULT_CONFIG
            )

            self.apply_environment_api_key()
            self.save()

            return deepcopy(self.config)

        try:
            file_content = (
                self.config_path.read_text(
                    encoding="utf-8"
                )
            )

            loaded_config = json.loads(
                file_content
            )

            if not isinstance(
                loaded_config,
                dict,
            ):
                raise ValueError(
                    "Nội dung config.json phải là object."
                )

            self.config = self.merge_dicts(
                deepcopy(self.DEFAULT_CONFIG),
                loaded_config,
            )

            self.apply_environment_api_key()

            return deepcopy(self.config)

        except json.JSONDecodeError as error:
            raise RuntimeError(
                "File config.json không đúng định dạng JSON.\n\n"
                f"Chi tiết: {error}"
            ) from error

        except OSError as error:
            raise RuntimeError(
                "Không thể đọc file config.json.\n\n"
                f"Chi tiết: {error}"
            ) from error

    def save(self) -> None:
        """
        Lưu cấu hình hiện tại vào config.json.
        """

        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            content = json.dumps(
                self.config,
                ensure_ascii=False,
                indent=4,
            )

            self.config_path.write_text(
                content + "\n",
                encoding="utf-8",
            )

        except OSError as error:
            raise RuntimeError(
                "Không thể lưu file config.json.\n\n"
                f"Chi tiết: {error}"
            ) from error

    def get(
        self,
        key_path: str,
        default: Any = None,
    ) -> Any:
        """
        Lấy một giá trị bằng đường dẫn dạng:

        openai.api_key
        video.width
        subtitle.font_size
        """

        if not key_path:
            return default

        keys = key_path.split(".")
        current_value: Any = self.config

        for key in keys:
            if not isinstance(
                current_value,
                dict,
            ):
                return default

            if key not in current_value:
                return default

            current_value = current_value[key]

        return current_value

    def set(
        self,
        key_path: str,
        value: Any,
        save_immediately: bool = True,
    ) -> None:
        """
        Gán một giá trị bằng đường dẫn dạng:

        config.set("openai.voice", "nova")
        config.set("video.fps", 30)
        """

        if not key_path:
            raise ValueError(
                "Tên cấu hình không được để trống."
            )

        keys = key_path.split(".")
        current_value = self.config

        for key in keys[:-1]:
            existing_value = current_value.get(
                key
            )

            if not isinstance(
                existing_value,
                dict,
            ):
                current_value[key] = {}

            current_value = current_value[key]

        current_value[keys[-1]] = value

        if save_immediately:
            self.save()

    def update_many(
        self,
        values: dict[str, Any],
    ) -> None:
        """
        Cập nhật nhiều giá trị rồi chỉ lưu file một lần.

        Ví dụ:

        config.update_many({
            "openai.voice": "nova",
            "video.width": 1920,
            "video.height": 1080,
        })
        """

        for key_path, value in values.items():
            self.set(
                key_path=key_path,
                value=value,
                save_immediately=False,
            )

        self.save()

    def reset(self) -> None:
        """
        Khôi phục toàn bộ cấu hình mặc định.
        """

        self.config = deepcopy(
            self.DEFAULT_CONFIG
        )

        self.apply_environment_api_key()
        self.save()

    def get_all(self) -> dict[str, Any]:
        """
        Trả về bản sao toàn bộ cấu hình.
        """

        return deepcopy(
            self.config
        )

    def get_api_key(self) -> str:
        """
        Trả về API Key đã được làm sạch.
        """

        return str(
            self.get(
                "openai.api_key",
                "",
            )
        ).strip()

    def set_api_key(
        self,
        api_key: str,
    ) -> None:
        """
        Lưu API Key vào config.json.
        """

        cleaned_api_key = api_key.strip()

        self.set(
            "openai.api_key",
            cleaned_api_key,
        )

    def get_project_directory(self) -> Path:
        """
        Trả về đường dẫn tuyệt đối đến thư mục dự án.
        """

        configured_path = str(
            self.get(
                "project.directory",
                "projects",
            )
        ).strip()

        if not configured_path:
            configured_path = "projects"

        project_path = Path(
            configured_path
        ).expanduser()

        if not project_path.is_absolute():
            project_path = (
                Path.cwd()
                / project_path
            )

        return project_path.resolve()

    def ensure_project_directory(
        self,
    ) -> Path:
        """
        Tạo thư mục dự án nếu chưa tồn tại.
        """

        project_path = (
            self.get_project_directory()
        )

        project_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return project_path

    def apply_environment_api_key(
        self,
    ) -> None:
        """
        Nếu config.json chưa có API Key nhưng biến môi trường
        OPENAI_API_KEY đã tồn tại thì sử dụng biến môi trường.

        API Key trong config.json sẽ được ưu tiên nếu đã có.
        """

        configured_api_key = str(
            self.config
            .get("openai", {})
            .get("api_key", "")
        ).strip()

        environment_api_key = (
            os.getenv(
                "OPENAI_API_KEY",
                "",
            ).strip()
        )

        if (
            not configured_api_key
            and environment_api_key
        ):
            self.config.setdefault(
                "openai",
                {},
            )

            self.config["openai"][
                "api_key"
            ] = environment_api_key

    def merge_dicts(
        self,
        default_values: dict[str, Any],
        custom_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Gộp cấu hình cũ với cấu hình mặc định.

        Khi phiên bản mới có thêm tùy chọn, các tùy chọn mới
        sẽ tự xuất hiện mà không làm mất cấu hình cũ.
        """

        result = deepcopy(
            default_values
        )

        for key, value in custom_values.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_dicts(
                    result[key],
                    value,
                )
            else:
                result[key] = deepcopy(
                    value
                )

        return result