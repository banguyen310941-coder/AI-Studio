import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "ai_studio"
LOG_DIRECTORY_NAME = "logs"
LOG_FILE_NAME = "ai_studio.log"

MAX_LOG_FILE_SIZE = 2 * 1024 * 1024
BACKUP_LOG_FILE_COUNT = 5


def get_project_root() -> Path:
    """
    Trả về thư mục gốc của AI Studio.

    Cấu trúc dự kiến:

    AI Studio/
        app/
            core/
                logger.py
    """

    return Path(__file__).resolve().parents[2]


def get_log_directory() -> Path:
    """
    Trả về thư mục chứa log và tự động tạo nếu chưa tồn tại.
    """

    log_directory = (
        get_project_root()
        / LOG_DIRECTORY_NAME
    )

    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return log_directory


def get_log_file_path() -> Path:
    """
    Trả về đường dẫn đầy đủ của file log.
    """

    return (
        get_log_directory()
        / LOG_FILE_NAME
    )


def configure_logger() -> logging.Logger:
    """
    Khởi tạo Logger dùng chung cho toàn bộ AI Studio.

    Logger ghi dữ liệu ra:
    - Terminal
    - logs/ai_studio.log

    File log được tự động xoay vòng khi vượt quá 2 MB.
    """

    logger = logging.getLogger(
        LOGGER_NAME
    )

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(
        sys.stdout
    )
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=get_log_file_path(),
        maxBytes=MAX_LOG_FILE_SIZE,
        backupCount=BACKUP_LOG_FILE_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(
        "Logger của AI Studio đã được khởi tạo."
    )

    return logger


def get_logger(
    module_name: str | None = None,
) -> logging.Logger:
    """
    Trả về logger cho một module cụ thể.

    Ví dụ:

        logger = get_logger(__name__)
        logger.info("Ứng dụng đã khởi động")
    """

    configure_logger()

    if not module_name:
        return logging.getLogger(
            LOGGER_NAME
        )

    return logging.getLogger(
        f"{LOGGER_NAME}.{module_name}"
    )


def log_exception(
    logger: logging.Logger,
    message: str,
    error: BaseException,
) -> None:
    """
    Ghi lỗi kèm đầy đủ traceback vào file log.
    """

    logger.exception(
        "%s Chi tiết: %s",
        message,
        error,
    )