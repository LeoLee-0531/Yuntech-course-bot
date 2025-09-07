import asyncio
import re
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from modules.logger import logger
from modules.browser_manager import browser_manager
from modules.course_enroller import course_enroller
from modules.exceptions import PageLoadError, CourseNotFoundError, BrowserError
from config import QUERY_URL, TARGET_COURSES, MONITOR_INTERVAL


class CourseMonitor:
    def __init__(self):
        self.target_courses = TARGET_COURSES
        self.monitor_interval = MONITOR_INTERVAL
        self.monitoring = False
        # 狀態追蹤
        self.last_available: dict[str, bool] = {}
        self.in_flight: set[str] = set()
        self.successed_courses: set[str] = set()
        # 追蹤所有由 create_task 建立的背景任務
        self.tasks: set[asyncio.Task] = set()

    async def _handle_enroll(self, course_info: dict):
        """啟動一次選課任務，並在完成後更新狀態。"""
        course_id = course_info.get('course_id')
        try:
            # 進行選課
            result = await course_enroller.enroll_course(course_info)
            if result:
                self.successed_courses.add(course_id)
                logger.info(f"課程 {course_id} 選課成功")
            else:
                logger.info(f"課程 {course_id} 選課未成功")
        except Exception as e:
            logger.error(f"處理選課任務失敗 {course_id}: {e}")
        finally:
            # 無論成功與否，這一波機會的任務結束，清除 in_flight
            if course_id in self.in_flight:
                self.in_flight.remove(course_id)

    async def parse_course_table(self, html_content):
        """解析課程表格"""
        try:
            courses_info: dict = {}
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find(
                'table', {'id': 'ctl00_MainContent_Course_GridView'})

            if not table:
                logger.debug("查無課程表格元素，可能是頁面結構變動或查無結果")
                return {}

            rows = table.find_all('tr')[1:]  # 跳過表頭

            for row in rows:
                if 'PageBar' in str(row):  # 跳過分頁列
                    continue

                cells = row.find_all('td')
                if len(cells) < 11:
                    continue

                try:
                    # 提取課程資訊
                    course_id_elem = cells[0].find('a')
                    if not course_id_elem:
                        continue

                    course_id = course_id_elem.text.strip()

                    # 只處理目標課程
                    if course_id not in self.target_courses:
                        continue

                    # 提取課程名稱
                    course_name_elem = cells[2].find('a')
                    course_name = course_name_elem.text.strip() if course_name_elem else "未知課程"

                    # 提取修課人數
                    sel_no_elem = cells[9].find('span')
                    sel_no = int(sel_no_elem.text.strip(
                    )) if sel_no_elem and sel_no_elem.text.strip().isdigit() else 0

                    # 提取人數限制
                    limit_elem = cells[10].find('span')
                    limit_text = limit_elem.text.strip() if limit_elem else ""

                    # 解析人數限制
                    limit_match = re.search(r'(\d+)', limit_text)
                    course_limit = int(limit_match.group(1)
                                       ) if limit_match else 0
                    # 構建課程資訊並直接回傳（找到就返回）
                    return {
                        'course_id': course_id,
                        'name': course_name,
                        'current': sel_no,
                        'limit': course_limit,
                        'available': course_limit - sel_no if course_limit > sel_no else 0
                    }

                except Exception as e:
                    logger.error(f"解析課程資料失敗: {e}")
                    continue

            return {}

        except Exception as e:
            logger.error(f"解析課程表格失敗: {e}")
            return {}

    async def query_courses(self, course_id):
        """查詢課程狀態"""
        try:
            # 創建新分頁查詢課程
            try:
                query_page = await browser_manager.new_page()
            except BrowserError as e:
                logger.error(f"無法創建查詢頁面: {e}")
                return {}

            # 前往課程查詢頁面
            try:
                await query_page.goto(QUERY_URL, timeout=30000)
                await query_page.wait_for_load_state('networkidle')
            except PlaywrightTimeoutError:
                logger.warning(f"課程查詢頁面載入超時: {course_id}")
                await query_page.close()
                return {}
            except ConnectionError:
                logger.warning(f"無法連接到課程查詢頁面: {course_id}")
                await query_page.close()
                return {}

            # 搜尋目標課程
            try:
                # 清空搜尋框並輸入課程代碼
                search_input = query_page.locator(
                    '#ctl00_MainContent_CurrentSubj').first
                if await search_input.count() > 0:
                    await search_input.clear()
                    await search_input.fill(course_id)

                    # 點擊搜尋按鈕
                    search_btn = query_page.locator(
                        '#ctl00_MainContent_Submit').first
                    if await search_btn.count() > 0:
                        await search_btn.click()
                        await query_page.wait_for_load_state('networkidle')
            except PlaywrightError as e:
                logger.warning(f"搜尋課程 {course_id} 時 Playwright 錯誤: {e}")
                # 不直接失敗，繼續解析頁面

            # 獲取頁面內容並解析
            try:
                html_content = await query_page.content()
                courses_info = await self.parse_course_table(html_content)
            except PlaywrightError as e:
                logger.warning(f"無法獲取頁面內容: {e}")
                courses_info = {}
            except Exception as e:
                logger.warning(f"解析課程資訊失敗: {e}")
                courses_info = {}

            # 關閉查詢頁面
            try:
                await query_page.close()
            except Exception as e:
                logger.warning(f"關閉查詢頁面時發生錯誤: {e}")

            return courses_info

        except PlaywrightError as e:
            logger.error(f"查詢課程 {course_id} 時 Playwright 錯誤: {e}")
            return {}
        except Exception as e:
            logger.error(f"查詢課程 {course_id} 發生未預期錯誤: {e}")
            return {}

    async def start_monitoring(self):
        """開始監聽課程"""
        self.monitoring = True
        logger.info(f"開始監聽課程")

        while self.monitoring:
            for course_id in self.target_courses:
                try:
                    # 已成功選到則跳過，避免重複查詢
                    if course_id in self.successed_courses:
                        continue
                    
                    # 查詢課程狀態
                    courses_info = await self.query_courses(course_id)

                    if courses_info:
                        # 檢查是否有空位
                        available = courses_info.get('available', 0)
                        available_count = courses_info.get(
                            'limit', 0) - courses_info.get('current', 0)

                        # 邊緣觸發：僅在無→有的瞬間觸發一次
                        previously_available = self.last_available.get(
                            course_id, False)
                        if available > 0:
                            if not previously_available:
                                logger.info(
                                    f"課程 {course_id} 有空位！剩餘 {available_count} 個名額")
                                # 去重：避免同課程同時多個任務
                                if course_id not in self.in_flight:
                                    self.in_flight.add(course_id)
                                    # 啟動一次選課任務（不阻塞監聽迴圈），並追蹤 task 與例外
                                    task = asyncio.create_task(
                                        self._handle_enroll(courses_info))
                                    self.tasks.add(task)

                                    def _on_done(t: asyncio.Task, cid=course_id):
                                        # 移除追蹤並處理例外
                                        self.tasks.discard(t)
                                        if t.cancelled():
                                            logger.info(
                                                f"enroll task for {cid} was cancelled")
                                            return
                                        exc = t.exception()
                                        if exc:
                                            logger.error(
                                                f"enroll task for {cid} raised: {exc}")
                                    task.add_done_callback(_on_done)
                            # 標記目前為有名額狀態
                            self.last_available[course_id] = True
                        else:
                            # 回到無名額，重置邊緣觸發狀態
                            self.last_available[course_id] = False

                    else:
                        logger.error("無法獲取課程資訊")

                except Exception as e:
                    logger.error(f"監聽過程發生錯誤: {e}")
                    await asyncio.sleep(self.monitor_interval)

            # 等待下次監聽
            await asyncio.sleep(self.monitor_interval)

    async def stop_monitoring(self):
        """停止監聽"""
        self.monitoring = False
        logger.info("停止課程監聽，正在取消尚在執行的 enroll 任務…")
        tasks = list(self.tasks)
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()


# 全域 course monitor 實例
course_monitor = CourseMonitor()
