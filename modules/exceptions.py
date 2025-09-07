"""
自定義異常類 - 課程選課機器人專用異常
"""

class CourseEnrollmentError(Exception):
    """選課相關異常的基底類"""
    pass


class CaptchaError(CourseEnrollmentError):
    """驗證碼處理異常"""
    pass


class PageLoadError(CourseEnrollmentError):
    """頁面載入異常"""
    pass


class LoginError(CourseEnrollmentError):
    """登入異常"""
    pass


class CourseNotFoundError(CourseEnrollmentError):
    """課程找不到異常"""
    pass


class EnrollmentFailedError(CourseEnrollmentError):
    """選課失敗異常"""
    pass


class BrowserError(CourseEnrollmentError):
    """瀏覽器相關異常"""
    pass


class ConfigurationError(CourseEnrollmentError):
    """配置錯誤異常"""
    pass