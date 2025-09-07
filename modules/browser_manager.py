import asyncio
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from modules.logger import logger
from modules.captcha_solver import captcha_solver
from modules.exceptions import BrowserError, ConfigurationError
from config import LOGIN_URL, USERNAME, PASSWORD, RETRY_TIMES


class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.main_page: Page | None = None
        self.is_logged_in = False
        self._login_lock = asyncio.Lock()

    async def start_browser(self):
        """啟動瀏覽器"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # 設為 True 可隱藏瀏覽器視窗
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )

            # 創建持久化 context 保持 session
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            self.main_page = await self.context.new_page()
            logger.info("瀏覽器啟動成功")
            return True

        except PlaywrightError as e:
            logger.error(f"Playwright 啟動失敗: {e}")
            raise BrowserError(f"Playwright 啟動失敗: {e}")
        except Exception as e:
            logger.error(f"瀏覽器啟動發生未預期錯誤: {e}")
            raise BrowserError(f"瀏覽器啟動失敗: {e}")

    async def login(self, max_attempts=RETRY_TIMES):
        """登入校務系統，包含重試邏輯"""
        if self.is_logged_in:
            return True

        if not USERNAME or not PASSWORD:
            raise ConfigurationError("未設定使用者名稱或密碼")
        if not LOGIN_URL:
            raise ConfigurationError("未設定登入 URL")

        for login_attempt in range(max_attempts):
            logger.info(f"登入嘗試 {login_attempt + 1}/{max_attempts}")

            try:
                if await self._single_login_attempt():
                    self.is_logged_in = True
                    logger.success("登入成功！")
                    return True

                if login_attempt < max_attempts - 1:
                    logger.warning(f"第 {login_attempt + 1} 次登入失敗")
            except Exception as e:
                logger.error(f"登入過程發生錯誤: {e}")
                if login_attempt < max_attempts - 1:
                    logger.info("等待 5 秒後重試...")
                    await asyncio.sleep(5)

        logger.error(f"登入失敗，已嘗試 {max_attempts} 次")
        return False

    async def _single_login_attempt(self):
        """單次登入嘗試"""

        async with self._login_lock:
            try:
                # 前往登入頁面
                try:
                    await self.main_page.goto(LOGIN_URL, timeout=30000)
                    await self.main_page.wait_for_load_state('networkidle')
                except PlaywrightTimeoutError:
                    logger.error("登入頁面載入超時")
                    return False
                except ConnectionError:
                    logger.error("無法連接到登入頁面")
                    return False

                # 等待登入表單元素
                try:
                    await self.main_page.wait_for_selector('#pLoginName', timeout=15000)
                    await self.main_page.wait_for_selector('#pLoginPassword', timeout=15000)
                except PlaywrightTimeoutError:
                    logger.error("登入表單元素載入超時")
                    return False

                # 填入帳號密碼
                await self.main_page.fill('#pLoginName', USERNAME)
                await self.main_page.fill('#pLoginPassword', PASSWORD)

                # 處理驗證碼 - 簡化重試邏輯，讓 captcha_solver 處理重試
                try:
                    logger.info("開始解析驗證碼")
                    captcha_text = await captcha_solver.capture_and_solve(self.main_page, '#NumberCaptcha')
                    
                    if not captcha_text:
                        logger.error("驗證碼解析結果為空")
                        return False

                    # 填入驗證碼並提交
                    await self.main_page.fill('#ValidationCode', captcha_text)
                    await self.main_page.click('#LoginSubmitBtn')
                    await self.main_page.wait_for_load_state('networkidle', timeout=10000)
                    
                    if await self.check_login_success():
                        logger.info("登入成功")
                        return True
                    else:
                        logger.warning("登入失敗，可能是驗證碼錯誤")
                        return False
                        
                except Exception as e:
                    logger.error(f"登入過程發生錯誤: {e}")
                    return False

            except Exception as e:
                logger.error(f"登入過程發生致命錯誤: {e}")
                return False

    async def _prepare_retry(self):
        """準備重試登入"""
        try:
            await self.main_page.reload()
            await self.main_page.wait_for_load_state('networkidle')
            await self.main_page.fill('#pLoginName', USERNAME)
            await self.main_page.fill('#pLoginPassword', PASSWORD)
        except Exception as e:
            logger.error(f"準備重試時發生錯誤: {e}")
            # 不拋出異常，讓調用方處理

    async def check_login_success(self):
        """檢查是否登入成功"""
        try:
            # 等待頁面載入
            await self.main_page.wait_for_load_state('networkidle', timeout=10000)

            # 檢查是否有登入後的特徵元素
            current_url = self.main_page.url
            page_content = await self.main_page.content()

            # 檢查 URL 變化或頁面內容
            if '選課' in page_content or 'course' in current_url.lower():
                return True

            # 檢查是否還在登入頁面
            if 'login' in current_url.lower() or '登入' in page_content:
                return False

            return True

        except PlaywrightError as e:
            logger.error(f"檢查登入狀態時 Playwright 錯誤: {e}")
            return False
        except Exception as e:
            logger.error(f"檢查登入狀態失敗: {e}")
            return False

    async def new_page(self):
        """創建新分頁"""
        try:
            if not self.context:
                raise BrowserError("瀏覽器上下文未初始化")
            new_page = await self.context.new_page()
            return new_page
        except PlaywrightError as e:
            logger.error(f"Playwright 創建新分頁失敗: {e}")
            raise BrowserError(f"無法創建新分頁: {e}")
        except Exception as e:
            logger.error(f"創建新分頁發生未預期錯誤: {e}")
            raise BrowserError(f"創建新分頁失敗: {e}")

    async def close(self):
        """關閉瀏覽器"""
        # 關閉 context
        try:
            if self.context:
                await self.context.close()
        except Exception as e:
            msg = str(e)
            if 'Connection closed' in msg or 'Connection reset' in msg:
                logger.info(f"關閉 context 時連線已終止，忽略: {msg}")
            else:
                logger.error(f"關閉 context 失敗: {e}")

        # 關閉 browser
        try:
            if self.browser:
                await self.browser.close()
        except Exception as e:
            msg = str(e)
            if 'Connection closed' in msg or 'Connection reset' in msg:
                logger.info(f"關閉 browser 時連線已終止，忽略: {msg}")
            else:
                logger.error(f"關閉 browser 失敗: {e}")

        # 停止 playwright
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            msg = str(e)
            if 'Connection closed' in msg or 'Connection reset' in msg:
                logger.info(f"停止 playwright 時連線已終止，忽略: {msg}")
            else:
                logger.error(f"停止 playwright 失敗: {e}")

        # 重置狀態
        self.context = None
        self.browser = None
        self.playwright = None

        logger.info("瀏覽器已關閉")


# 全域 browser manager 實例
browser_manager = BrowserManager()
