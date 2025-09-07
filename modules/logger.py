import logging
import os
from datetime import datetime
import aiofiles


class CourseLogger:
    def __init__(self, log_file=None, log_level=None):
        self.log_file = log_file or os.getenv("LOG_FILE") or "course_bot.log"
        
        provided_level = log_level or os.getenv("LOG_LEVEL", "INFO")
        self.log_level = self._validate_log_level(provided_level)
        
        self.setup_logger()

    def _validate_log_level(self, level):
        """驗證並返回有效的日誌級別"""
        if not level:
            return "INFO"
        
        level = level.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        if level in valid_levels:
            return level
        else:
            print(f"[WARNING] 無效的日誌級別 '{level}'，使用預設值 'INFO'")
            return "INFO"

    def setup_logger(self):
        """設置 logger，避免重複新增 handler"""
        try:
            self.logger = logging.getLogger('CourseBot')
            self.logger.setLevel(getattr(logging, self.log_level))
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

            # 僅在沒有 handler 時才新增
            if not self.logger.hasHandlers():
                # 創建文件處理器
                file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                file_handler.setLevel(getattr(logging, self.log_level))
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
        except Exception as e:
            # 如果設置失敗，使用基本配置
            print(f"[WARNING] Logger 設置失敗: {e}，使用基本配置")
            logging.basicConfig(
                level=logging.INFO,
                format='[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.logger = logging.getLogger('CourseBot')

    def info(self, message):
        """記錄 INFO 級別日誌"""
        self.logger.info(message)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] {message}")

    def success(self, message):
        """記錄成功訊息"""
        self.logger.info(f"SUCCESS: {message}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCCESS] {message}")

    def warning(self, message):
        """記錄警告訊息"""
        self.logger.warning(message)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WARNING] {message}")

    def alert(self, message):
        """記錄警告訊息"""
        self.logger.warning(f"ALERT: {message}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ALERT] {message}")

    def error(self, message):
        """記錄錯誤訊息"""
        self.logger.error(message)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] {message}")

    async def async_log(self, level, message):
        """異步寫入日誌"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        async with aiofiles.open(self.log_file, 'a', encoding='utf-8') as f:
            await f.write(log_entry)

# 全域 logger 實例
logger = CourseLogger()