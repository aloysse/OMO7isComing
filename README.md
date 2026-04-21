# Hotel Vacancy Monitor + Telegram 通知

此專案會每天自動檢查飯店 API 的空房資料，並將指定日期的結果發送到 Telegram。

## 功能

- 每日固定時間（台灣時間 09:00）執行。
- 查詢目標日期：
  - 2026-02-15
  - 2026-02-28
- 若目標日期都沒空房：通知「目前沒空房」。
- 若有空房：通知空房數與價格（JPY），並換算成 TWD。

## 專案檔案

- `monitor.py`：主程式，負責呼叫 API、匯率換算、發送 Telegram。
- `.github/workflows/daily-vacancy-check.yml`：GitHub Actions 排程工作。

## GitHub Secrets 設定

請到 GitHub Repository 的 **Settings → Secrets and variables → Actions**，建立以下三個 secrets：

- `API_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## API 查詢邏輯

程式會使用以下固定參數呼叫 `API_URL`：

- `hotelId=0000000201`
- `adult=2`
- `underTwelve=0`
- `underFour=0`
- `stayLength=5`
- `lang=CH`
- `monthlyDate=YYYY/MM/01`（依目標日期的月份自動帶入）

並從回傳的 `vacancyList` 中找到目標日期，判斷 `vacancy` 是否大於 0。

## 匯率換算

程式使用 Frankfurter 匯率 API 取得 `JPY -> TWD` 最新匯率，再將 `unitCharge` 換算為台幣。

## 本機執行

```bash
export API_URL="https://hoshinoresorts.com/api/rooms/vacancies/monthly"
export TELEGRAM_BOT_TOKEN="<your_bot_token>"
export TELEGRAM_CHAT_ID="<your_chat_id>"
# 可選，預設為 2026-02-15,2026-02-28
export TARGET_DATES="2026-02-15,2026-02-28"

python monitor.py
```

## GitHub Actions 排程

- 檔案：`.github/workflows/daily-vacancy-check.yml`
- `cron: "0 1 * * *"` 代表每天 UTC 01:00（即台灣時間 09:00）執行。
- Workflow 已設定 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`，可提前避免 Node.js 20 deprecation 問題。
- 也可從 Actions 頁面手動執行（`workflow_dispatch`）。
