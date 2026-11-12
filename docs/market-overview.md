# 市場總覽 tab（`overview`）——規格與驗收條件

目標專案：`/home/user/postmkt`（shihpc/postmkt）。跨站只讀、不改其他 repo。

## 0. 使用者裁定（鐵律 8）

- 2026-11-12 使用者裁定：「標示『AI 研判，未經回測，非保證』後上線。」
- 範圍：市場中心的每日一頁，三段＝盤勢七項（描述）、類股交集表、個股交集表。
  交集表依「出現在幾個來源清單」排序，屬**新的候選排序、無回測依據**，依裁定先上線。
- 畫面三種狀態（正常／部分來源缺／讀取失敗）都逐字顯示「AI 研判，未經回測，非保證」。
- 列入事後驗證：後端每日把交集表存快照進 git（`data/overview/daily/<date>.json`），
  累積後另提驗證方法；驗證結論出來前不得拿掉標示。
- 部位中心（持股）版本不在本批（使用者：「下次再做」）。

## 1. 架構（為何這樣分）

- **盤勢七項＝前端直接顯示既有資料**：純描述，沒有可漂移的計算；各項自帶資料日。
- **兩張交集表＝後端單一實作** `src/build_overview.py` → `data/overview/latest.json`
  ＋`data/overview/daily/<date>.json`；前端只渲染、不重算（避免同一口徑兩份實作）。
- 首屏請求清單不變：一切只在切到本 tab 時才抓；全部同源相對路徑，CSP 不改。

## 2. 盤勢七項（描述性；每項自帶資料日；缺哪項只灰掉那項）

| # | 項目 | 來源（同源相對路徑） |
|---|------|------|
| 1 | 當日總結：指數、漲跌家數、次產業拉抬／拖累 | `../taiwan-flow-live-v2/data/daysummary/latest.json` |
| 2 | 三大法人買賣淨額（上市＋上櫃）、外資佔比 | `../taiwan-flows/data/totals.json` |
| 3 | 外資台指期未平倉口數與前一交易日增減 | taiwan-flows 既有產物（實作者挑最小且可靠的檔，文件記下） |
| 4 | 市場情緒：VIX／Put-Call／小台散戶多空比的最新值與百分位 | `../taiwan-flows/data/sentiment.json`（沿用 `sent-pure`） |
| 5 | 大盤餘額：融資、借券賣出餘額與異動 | `data/market_balance_history.json` |
| 6 | 盤勢綜合研判（AI 文字，標 AI 研判） | `data/summary/` 最新一場的 synthesis |
| 7 | 晨報今日三件事＋開盤前定位（AI 文字，標 AI 研判） | `../taiwan-stock-news/daily-brief-card.json` |

硬約束：1–5 不得出現偏多／偏空／建議等判斷字樣（來源檔自帶的文字如「氣氛」原樣顯示並標來源）；
漲跌著色只用在漲跌與買賣超正負（沿用 `sgn()`）；外來字串一律 `esc()`；數值先過 number＋isFinite。

## 3. 交集表（後端）

方向：**本批只做偏多（資金流入）側**；偏空側未做，文件與畫面說明列明。

### 3.1 類股交集（主鍵＝產業鏈「產業」）

候選來源（實作者須逐一打開實檔核對鍵名與分類體系後定案，定案寫回本節）：
- A 產業鏈資金流：`sector_ranges_lite.json` `windows.r5` chain／三大法人，淨買金額 >0 的前 10
- B 籌碼雷達：r5 對 r20 的「轉買／加速買」象限（口徑同前端 `radarQuad`，移植時以測試對前端逐位比對）
- C 主動 ETF 次產業流向：`aetf/diff.json` 次產業加碼前 10
- D 連湧／新湧次產業：`morning.json`
- E 日級輪動雷達「改善」「領先」清單（註明：回測 0/12 顯著）

次產業來源（C、D）須經 (產業, 次產業) 對映上卷到產業才計入；**名稱對不上或無可靠對映檔時，
該來源降級為「另列、不計入交集」並在畫面與本文件明講，不得硬湊**。

### 3.2 個股交集（主鍵＝股票代號）

- a 外資投信同步買超 Top30（`taiwan-flows/data/latest.json` `pages.sync`）
- b 主動 ETF 跨 ETF 加碼共識（≥2 檔同買；口徑同本站 aetf tab）
- c 選股二追蹤名單（`data/pick2/track.json` `tracking`）
- d 月營收 Beat／高預期仍 Beat（`data/revenue/` 最新月；月頻，輸出註明營收月份）
- e 千張大戶週增前 20（`data/diag/diag.json`；口徑同前端 `radarHolders`）
- f 彙總分析精華標的：只有在方向可由文字**可靠**解析為偏多時才計入，否則不納入並說明

### 3.3 共同規則

- 計數＝該鍵出現在幾個**有效**來源；輸出 `count ≥ 2` 的列，依 count 遞減、同數依鍵遞增。
- **來源有效性**：每個來源記自己的資料日；資料日 ≠ 本次 overview 基準日（個股層取 a 的資料日、
  類股層取 A 的資料日）的日頻來源標 `stale` 且**不計入 count**（月頻 d、週頻 e 另訂容許窗並寫明）。
- 來源讀不到／形狀不合＝該來源 `ok:false`、不計入，其餘照算；有效來源 <2 時該表不輸出列並說明。
- 輸出 schema 1：`{schema, date, generated_at, label, sectors:{sources:[…], rows:[…]},
  stocks:{sources:[…], rows:[…]}}`；`label` 逐字為「AI 研判，未經回測，非保證」。
- 快照冪等：同一 `date` 重跑覆寫；`generated_at` 以外內容不變時不產生 commit 噪音（沿用本 repo 既有做法）。
- 排程：掛在既有晚間 workflow 的後段（`continue-on-error`，失敗不擋原管線）；不新增 Worker cron、不改其他 repo。
- 無 token、無新外部網域；跨 repo 讀 raw main 公開檔。

## 4. 前端

- `TABS` 新增 `overview`「市場總覽」（位置：第一個；**預設 tab 不變**）。CSS 一律 `.ov-*`；不加新 hash key。
- 交集表用既有 `tbl()`，不改 `tbl()`；出現清單數為中性色，不加燈號；每列列出命中哪些來源。
- 頁頂列出每個來源的資料日與狀態（有效／過期不計／讀取失敗）。
- `data/overview/latest.json` 讀不到＝交集兩段顯示一句話、盤勢七項照常。

## 5. 驗收條件

1. `python -m pytest tests/ -q` 全過（含新測試）；`ruff check .` 無新增問題；三站同步碼位元組不變。
2. 新測試涵蓋：計數與排序、stale 不計入、來源缺失降級、次產業上卷（或降級）行為、label 逐字、冪等、B／e／b 與前端口徑一致。
3. `python src/build_overview.py` 以真實資料實跑成功，產出檔通過 schema 檢查；隨機抽 3 列人工回查來源檔相符。
4. 前端（http.server 起在 `/home/user`，以 `/postmkt/` 開頁；外部請求以 route mock）：20 個 tab 逐一點擊 console 零 error；
   首屏請求清單與 origin/main 相同；375／390／1280 整頁無水平捲軸、表格逐格零裁切。
5. 三種畫面狀態都看得到逐字標示；注入 `<img onerror>` 字串到來源檔的名稱欄不執行。
6. fresh-context subagent 依本文件逐條驗收並綁定 commit。
7. CLAUDE.md（tab 數 19→20、新節）、CHANGELOG、本文件同步。
8. 上線＝合併到 main 後 Pages 實際頁面看得到本 tab 且當晚 workflow 產出 `data/overview/latest.json`（本條需使用者合併後才能驗）。
