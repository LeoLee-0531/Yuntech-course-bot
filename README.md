# 雲科大搶課機器人

> 雲科這什麼鬼選課系統，我都選不到課，逼我出大絕是吧

## 功能特色

✅ **多課程並行監聽** - 同時監控多門課程的名額狀態  
✅ **自動 OCR 驗證碼** - 使用 Tesseract 自動識別驗證碼  
✅ **並行搶課** - 發現多門課程有空位時同時進行搶課  
✅ **Session 維持** - 自動維持登入狀態，避免重複登入  
✅ **詳細日誌** - 重要事件記錄到終端和日誌檔案  
✅ **容錯機制** - 自動重試和錯誤處理

## 安裝需求

### 1. Python 環境

- Python 3.8 或以上版本

### 2. 安裝 uv (Python 套件管理器)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip 安裝
pip install uv
```

### 3. 建立虛擬環境並安裝依賴

```bash
# 建立虛擬環境
uv venv

# 安裝專案依賴
uv sync

# 安裝 Playwright 瀏覽器
uv run playwright install chromium
```

### 4. 安裝 Tesseract OCR

#### Windows:

1. 下載並安裝 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. 將 Tesseract 安裝路徑加入系統 PATH

#### macOS:

```bash
brew install tesseract
```

#### Ubuntu/Debian:

```bash
sudo apt-get install tesseract-ocr
```

## 設定

### 1. 修改 config.py

```python
# 使用者設定
USERNAME = "your_username"  # 你的學號
PASSWORD = "your_password"  # 你的密碼
TARGET_COURSES = ["1255", "1258", "1259"]  # 目標課程代碼

# 系統設定
MONITOR_INTERVAL = 5  # 監聽間隔 (秒)
MAX_CONCURRENT_ENROLLS = 3  # 最大同時搶課數量
```

### 2. 課程代碼查詢

1. 前往 [課程查詢系統](https://webapp.yuntech.edu.tw/WebNewCAS/Course/QueryCour.aspx)
2. 搜尋你要的課程
3. 記下課程的「學期課號」(例如: 1255, 1258)
4. 將課程代碼加入 `TARGET_COURSES` 清單

## 使用方法

### 1. 啟動程式

```bash
# 使用 uv 執行
uv run python main.py

# 或先啟動虛擬環境再執行
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows
python main.py
```

### 2. 程式運行流程

1. 自動啟動瀏覽器
2. 登入校務系統 (自動處理驗證碼)
3. 開始監聽目標課程
4. 發現有空位時自動搶課
5. 記錄所有重要事件到日誌

### 3. 停止程式

按 `Ctrl+C` 即可安全停止程式

## 開發相關

### 新增套件

```bash
# 新增運行時依賴
uv add requests

# 新增開發依賴
uv add --dev pytest
```

### 移除套件

```bash
uv remove package_name
```

### 更新套件

```bash
uv sync --upgrade
```

## 日誌說明

程式會在終端顯示即時狀態，同時將日誌寫入 `course_bot.log` 檔案。

### 日誌範例:

```
[2024-09-05 14:30:15] [INFO] 開始登入校務系統...
[2024-09-05 14:30:18] [SUCCESS] 登入成功
[2024-09-05 14:30:20] [INFO] 開始監聽課程: ['1255', '1258', '1259']
[2024-09-05 14:30:25] [INFO] 課程 1255 (電機工程概論): 120/135 人 (剩餘 15 個名額)
[2024-09-05 14:30:25] [ALERT] 課程 1258 有空位！剩餘 30 個名額
[2024-09-05 14:30:28] [SUCCESS] 課程 1258 選課成功！
```

## 檔案結構

```
course_bot/
├── main.py                 # 主程式
├── config.py              # 設定檔
├── pyproject.toml         # uv 專案設定檔
├── uv.lock               # 依賴鎖定檔案 (自動生成)
├── README.md             # 說明文件
├── course_bot.log        # 日誌檔案 (執行後產生)
├── .venv/                # 虛擬環境 (uv venv 後產生)
└── modules/              # 程式模組
    ├── __init__.py
    ├── browser_manager.py  # 瀏覽器管理
    ├── captcha_solver.py   # 驗證碼解析
    ├── course_monitor.py   # 課程監聽
    ├── course_enroller.py  # 搶課執行
    └── logger.py          # 日誌管理
```

## 注意事項

⚠️ **重要提醒:**

1. 請遵守學校的選課規定和使用條款
2. 不要設定過短的監聽間隔，避免對伺服器造成過大負擔
3. 建議在選課開放時間使用，避免在非選課時段運行
4. 請確保網路連線穩定

⚠️ **技術限制:**

1. 驗證碼識別率約 75-90%，複雜驗證碼可能需要多次重試
2. 網頁結構變更可能影響程式運行
3. 伺服器繁忙時可能出現連線逾時

## 疑難排解

### 1. 驗證碼識別失敗

- 檢查 Tesseract 是否正確安裝
- 嘗試調整 `RETRY_TIMES` 增加重試次數

### 2. 登入失敗

- 確認帳號密碼正確
- 檢查網路連線
- 確認校務系統是否正常運作

### 3. 找不到課程

- 確認課程代碼正確
- 檢查課程是否在當前學期開設
- 確認課程查詢頁面結構是否變更

### 4. uv 相關問題

```bash
# 重新建立虛擬環境
rm -rf .venv
uv venv
uv sync

# 重新安裝 Playwright 瀏覽器
uv run playwright install chromium --force
```

## 免責聲明

本工具僅供學習和研究使用。使用者應遵守學校相關規定，作者不承擔任何因使用本工具而產生的責任。

## 授權

MIT License
