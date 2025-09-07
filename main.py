import asyncio
import signal
import sys
from modules.logger import logger
from modules.browser_manager import browser_manager
from modules.course_monitor import course_monitor
from config import TARGET_COURSES, SESSION_CHECK_INTERVAL, validate_config


class CourseBot:
    def __init__(self):
        self.running = False
        self.tasks = []

    async def session_keeper(self):
        """維持登入狀態"""
        while self.running:
            try:
                await asyncio.sleep(SESSION_CHECK_INTERVAL)

                if not browser_manager.is_logged_in:
                    logger.info("檢測到登入狀態異常，嘗試重新登入...")
                    try:
                        success = await browser_manager.login()
                        if not success:
                            logger.warning("重新登入失敗，將在下次檢查時重試")
                        else:
                            logger.success("重新登入成功！")
                    except Exception as e:
                        logger.error(f"重新登入過程發生錯誤: {e}")
                else:
                    logger.info("登入狀態正常")

            except Exception as e:
                logger.error(f"Session 維持器發生錯誤: {e}")
                await asyncio.sleep(60)

    async def start(self):
        """啟動搶課機器人"""
        try:
            self.running = True
            logger.info("=== 雲科大搶課機器人啟動 ===")
            logger.info(f"目標課程: {TARGET_COURSES}")
            logger.info("=" * 30)

            # 啟動瀏覽器
            logger.info("正在啟動瀏覽器...")
            if not await browser_manager.start_browser():
                logger.error("瀏覽器啟動失敗")
                return False

            # 登入系統
            logger.info("正在登入校務系統...")
            if not await browser_manager.login():
                logger.error("登入失敗")
                await browser_manager.close()
                return False

            # 創建並啟動異步任務
            logger.info("正在啟動監聽與搶課服務...")

            # 任務1: 課程監聽
            monitor_task = asyncio.create_task(
                course_monitor.start_monitoring())
            self.tasks.append(monitor_task)

            # 任務2: （移除）原 queue 型選課處理，改為 monitor 邊緣觸發直接建立任務

            # 任務3: Session 維持
            session_task = asyncio.create_task(self.session_keeper())
            self.tasks.append(session_task)

            logger.success("搶課機器人已成功啟動！")

            # 等待所有任務完成
            await asyncio.gather(*self.tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"搶課機器人啟動失敗: {e}")
            return False

    async def stop(self):
        """停止搶課機器人"""
        logger.info("正在停止搶課機器人...")
        self.running = False
        # 停止課程監聽
        await course_monitor.stop_monitoring()

        # 取消所有任務
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # 等待任務結束
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # 關閉瀏覽器
        await browser_manager.close()

        logger.info("搶課機器人已停止")


async def main():
    """主函數"""
    bot = CourseBot()

    # 設置信號處理器，確保能 await 停止流程
    stop_event = asyncio.Event()

    async def handle_stop():
        logger.info("收到停止信號，正在關閉程式...")
        await bot.stop()
        stop_event.set()

    def signal_handler(signum, frame):
        # signum 和 frame 參數被 signal 模組要求，即使未使用也必須保留
        asyncio.create_task(handle_stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 啟動 bot.start() 作為背景任務，便於在收到停止信號時立即取消
    start_task = asyncio.create_task(bot.start())
    try:
        # 等待停止事件被觸發（由 signal handler 執行 stop 並 set）
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("使用者中斷程式")
        await bot.stop()
    except Exception as e:
        logger.error(f"程式執行發生錯誤: {e}")
        await bot.stop()
    finally:
        # 確保 start_task 已結束，否則取消並等待
        if not start_task.done():
            start_task.cancel()
            await asyncio.gather(start_task, return_exceptions=True)
        logger.info("程式已結束")

if __name__ == "__main__":
    # 檢查與列印完整配置摘要（若有缺漏會一次列出並退出）
    validate_config()

    # 運行程式
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程式已被使用者中斷")
    except Exception as e:
        logger.error(f"程式執行失敗: {e}")
        sys.exit(1)
