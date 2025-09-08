import os
from dotenv import load_dotenv
from modules.logger import logger

# 讀取 .env 檔
load_dotenv()


def validate_config():
    """驗證所有必要的配置設定"""
    import sys
    errors: list[str] = []
    warnings: list[str] = []

    # 讀取環境變數
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    login_url = os.getenv("LOGIN_URL")
    selection_url = os.getenv("SELECTION_URL")
    query_url = os.getenv("QUERY_URL")
    target_courses_raw = os.getenv("TARGET_COURSES")
    log_file = os.getenv("LOG_FILE", "course_bot.log")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    # 必要變數檢查
    if not username:
        errors.append("USERNAME 未設定")
    if not password:
        errors.append("PASSWORD 未設定")
    if not login_url:
        errors.append("LOGIN_URL 未設定")
    if not selection_url:
        errors.append("SELECTION_URL 未設定")
    if not query_url:
        errors.append("QUERY_URL 未設定")
    if not target_courses_raw:
        errors.append("TARGET_COURSES 未設定")

    # 數值型配置檢查
    def _read_int(name: str, default: int):
        # 檢查是否存在此環境變數
        raw = os.getenv(name)
        if raw is None:
            warnings.append(f"{name} 未設定，已設置為 {default}")
            return
        # 驗證為有效且大於 0 的整數
        try:
            val = int(raw)
            if val <= 0:
                warnings.append(f"{name} 必須大於 0，已設置為 {default}")
        except ValueError:
            warnings.append(f"{name} 必須是有效的整數，已設置為 {default}")

    _read_int("MONITOR_INTERVAL", 5)
    _read_int("RETRY_TIMES", 3)
    _read_int("SESSION_CHECK_INTERVAL", 300)

    if warnings:
        for warn in warnings:
            logger.alert(warn)

    if errors:
        for err in errors:
            logger.error(err)
        sys.exit(1)


# 載入配置（如果驗證失敗則使用默認值）
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

TARGET_COURSES = [c.strip() for c in os.getenv(
    "TARGET_COURSES", "").split(",") if c.strip()]

MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 5))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", 3))
SESSION_CHECK_INTERVAL = int(os.getenv("SESSION_CHECK_INTERVAL", 300))

LOGIN_URL = os.getenv("LOGIN_URL")
SELECTION_URL = os.getenv("SELECTION_URL")
QUERY_URL = os.getenv("QUERY_URL")

LOG_FILE = os.getenv("LOG_FILE")
LOG_LEVEL = os.getenv("LOG_LEVEL")
