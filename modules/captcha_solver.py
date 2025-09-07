import cv2
import numpy as np
import easyocr
from PIL import Image
import io
import base64
from modules.logger import logger

class CaptchaSolver:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=False)
    
    def preprocess_image(self, image_data):
        """
        預處理驗證碼圖片
        """
        try:
            # 將 base64 或 bytes 轉換為 PIL Image
            if isinstance(image_data, str):
                # base64 格式
                image_data = base64.b64decode(image_data)
            
            # 轉換為 PIL Image
            pil_image = Image.open(io.BytesIO(image_data))
            
            # 轉換為 numpy array
            img_array = np.array(pil_image)
            
            # 轉換為灰階
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # 高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # 二值化處理
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形態學操作去除小噪點
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 反轉顏色 (黑字白底 -> 白字黑底)
            inverted = cv2.bitwise_not(cleaned)
            
            return inverted
            
        except Exception as e:
            logger.error(f"圖片預處理失敗: {e}")
            return None
    
    def solve_captcha(self, image_data):
        """
        使用 EasyOCR 解析驗證碼
        """
        try:
            # 預處理圖片
            processed_img = self.preprocess_image(image_data)
            if processed_img is None:
                return None
            
            # 使用 EasyOCR 進行 OCR
            results = self.reader.readtext(processed_img)
            
            if not results:
                logger.error("EasyOCR 未檢測到任何文字")
                return None
            
            # 提取所有檢測到的文字並合併
            text = ''.join([result[1] for result in results])
            
            # 清理結果，只保留字母和數字
            text = ''.join(c for c in text.upper() if c.isalnum())

            if len(text) == 4:
                logger.info(f"CAPTCHA 解析結果: {text}")
                return text
            else:
                logger.error(f"CAPTCHA 解析結果太短: {text}")
                return None

        except Exception as e:
            logger.error(f"CAPTCHA 解析失敗: {e}")
            return None
    
    async def capture_and_solve(self, page, captcha_selector):
        """
        從頁面擷取驗證碼並解析
        """
        try:
            # 等待驗證碼元素載入
            await page.wait_for_selector(captcha_selector, timeout=10000)
            
            # 擷取驗證碼圖片
            captcha_element = page.locator(captcha_selector)
            screenshot = await captcha_element.screenshot()
            
            # 解析驗證碼
            result = self.solve_captcha(screenshot)
            
            if result:
                logger.info(f"成功解析驗證碼: {result}")
                return result
            else:
                logger.error("驗證碼解析失敗")
                return None
                
        except Exception as e:
            logger.error(f"擷取驗證碼失敗: {e}")
            return None

# 全域 captcha solver 實例
captcha_solver = CaptchaSolver()