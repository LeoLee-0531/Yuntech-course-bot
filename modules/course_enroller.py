import asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from modules.logger import logger
from modules.browser_manager import browser_manager
from modules.captcha_solver import captcha_solver
from modules.exceptions import EnrollmentFailedError, CourseNotFoundError, PageLoadError, CaptchaError, BrowserError
from config import MAX_CONCURRENT_ENROLLS, RETRY_TIMES, SELECTION_URL


class CourseEnroller:
    def __init__(self):
        # TODO: 最多只能有一個選課頁面，所以要把平行取消
        self.max_concurrent = MAX_CONCURRENT_ENROLLS
        self.enrolling_courses = set()
        self.enroll_semaphore = asyncio.Semaphore(self.max_concurrent)

    async def find_enroll_page(self, page, course_id):
        """尋找並進入選課頁面"""
        try:
            # 等待頁面載入
            try:
                await page.wait_for_load_state('networkidle', timeout=15000)
            except PlaywrightTimeoutError:
                pass

            # 搜尋課程加選
            try:
                search_input = page.locator(
                    '#ContentPlaceHolder1_CurrentSubjTextBox').first
                if await search_input.count() > 0:
                    await search_input.fill(course_id)
                    # 點擊加選按鈕
                    await page.click("#ContentPlaceHolder1_CurrentSubjRegisterButton")
                    await page.click("#ContentPlaceHolder1_NextStepButton")
                    await page.wait_for_load_state('networkidle')
                    return True
                else:
                    raise CourseNotFoundError(f"找不到課程搜尋輸入框")
            except PlaywrightError as e:
                logger.error(f"搜尋課程時發生錯誤 {course_id}: {e}")
                raise CourseNotFoundError(f"無法搜尋課程 {course_id}: {e}")

        except CourseNotFoundError:
            # 重新拋出已知異常
            raise
        except PlaywrightError as e:
            logger.error(f"Playwright 錯誤: {e}")
            raise PageLoadError(f"頁面操作失敗: {e}")
        except Exception as e:
            logger.error(f"尋找選課頁面發生未預期錯誤: {e}")
            raise PageLoadError(f"尋找選課頁面失敗: {e}")

    async def submit_enrollment(self, page):
        """提交選課申請"""
        await page.wait_for_load_state('networkidle')

        try:
            for attempt in range(RETRY_TIMES):
                # 點擊課程
                await page.click('#ContentPlaceHolder1_CourseCheckListGridView_SelectCheckBox_0')

                # 處理驗證碼
                try:
                    captcha_text = await captcha_solver.capture_and_solve(page, '#ContentPlaceHolder1_Captcha')                    
                    await page.fill('#ContentPlaceHolder1_CaptchaTextBox', captcha_text)

                except Exception as e:
                    logger.error(f"驗證碼處理失敗 (第 {attempt + 1} 次): {e}")
                    continue

                # 提交選課申請
                try:
                    await page.click('#ContentPlaceHolder1_SaveButton')
                    await page.wait_for_load_state('networkidle')
                    await asyncio.sleep(5)  # 等待頁面反應

                    # 先檢查是否有選課成功的結果元素
                    success_result = page.locator('#ContentPlaceHolder1_ResultGridView_ProcessMsg_0')
                    if await success_result.count() > 0:
                        # 讀取成功訊息內容確認
                        message = await success_result.text_content()
                        cleaned_message = message.replace('\n', '').replace('\r', '').strip() if message else ""
                        logger.info(f"選課成功: {cleaned_message}")
                        return True
                    
                    # 如果沒有成功訊息，檢查是否有錯誤訊息需要關閉
                    try:
                        # 等待 CloseButton 出現，但時間較短
                        await page.wait_for_selector('#CloseButton', timeout=2000)
                        
                        close_button = page.locator('#CloseButton')
                        if await close_button.count() > 0:
                            await close_button.click()
                            continue
                    except PlaywrightTimeoutError:
                        # 沒有 CloseButton 是正常的，繼續下一次嘗試
                        logger.error("沒有找到 CloseButton，繼續下一次嘗試")
                        continue
                    except Exception as e:
                        logger.error(f"點擊 CloseButton 失敗: {e}")
                        continue

                except PlaywrightError:
                    raise EnrollmentFailedError("找不到提交按鈕")

                except Exception as e:
                    logger.error(f"提交選課申請時發生錯誤: {e}")
                    raise EnrollmentFailedError(f"提交選課申請失敗: {e}")
                
            return False
                
        except (CaptchaError, EnrollmentFailedError):
            # 重新拋出已知異常
            raise
        except Exception as e:
            logger.error(f"提交選課申請過程發生致命錯誤: {e}")
            raise EnrollmentFailedError(f"提交選課申請失敗: {e}")

    async def enroll_course(self, course_info):
        """執行單一課程選課"""
        # 驗證輸入參數
        if not course_info or not isinstance(course_info, dict):
            raise ValueError("課程資訊格式錯誤")

        try:
            course_id = course_info['course_id']
            course_name = course_info['name']
        except KeyError as e:
            logger.error(f"課程資訊缺少必要欄位: {e}")
            raise ValueError(f"課程資訊缺少必要欄位: {e}")

        async with self.enroll_semaphore:
            if course_id in self.enrolling_courses:
                return False

            self.enrolling_courses.add(course_id)
            enroll_page = None

            try:
                logger.info(f"開始搶課: {course_id} ({course_name})")

                # 創建新分頁進行選課
                try:
                    enroll_page = await browser_manager.new_page()
                except BrowserError as e:
                    logger.error(f"無法為課程 {course_id} 創建選課頁面: {e}")
                    raise EnrollmentFailedError(f"無法創建選課頁面: {e}")

                # 前往選課系統
                try:
                    await enroll_page.goto(SELECTION_URL, timeout=30000)
                    await enroll_page.wait_for_load_state('networkidle')
                except PlaywrightTimeoutError:
                    raise PageLoadError("選課頁面載入超時")
                except ConnectionError:
                    raise PageLoadError("網路連線問題")

                # 尋找並選擇課程
                try:
                    found = await self.find_enroll_page(enroll_page, course_id)
                    if not found:
                        raise CourseNotFoundError(f"找不到課程 {course_id} 的選課入口")
                except (CourseNotFoundError, PageLoadError) as e:
                    raise EnrollmentFailedError(f"無法進入選課頁面: {e}")

                # 提交選課申請
                try:
                    success = await self.submit_enrollment(enroll_page)
                    if success:
                        # 選課成功後立即關閉分頁
                        try:
                            if not enroll_page.is_closed():
                                await enroll_page.close()
                                enroll_page = None  # 設為 None 避免 finally 重複關閉
                        except Exception as e:
                            logger.error(f"關閉成功選課頁面時發生錯誤: {e}")
                        return True
                    else:
                        return False
                except (CaptchaError, EnrollmentFailedError) as e:
                    logger.error(f"課程 {course_id} ({course_name}) 選課失敗: {e}")
                    return False

            except ValueError:
                # 重新拋出參數錯誤
                raise
            except (PageLoadError, EnrollmentFailedError, CourseNotFoundError, CaptchaError):
                # 重新拋出已知異常
                return False
            except PlaywrightError as e:
                logger.error(f"課程 {course_id} Playwright 錯誤: {e}")
                return False
            except Exception as e:
                logger.error(f"課程 {course_id} 選課過程發生未預期錯誤: {e}")
                return False
            finally:
                # 確保頁面被關閉
                if enroll_page:
                    try:
                        if not enroll_page.is_closed():
                            await enroll_page.close()
                    except Exception as e:
                        logger.error(f"關閉選課頁面時發生錯誤: {e}")

                # 移除選課狀態
                self.enrolling_courses.discard(course_id)


# 全域 course enroller 實例
course_enroller = CourseEnroller()
