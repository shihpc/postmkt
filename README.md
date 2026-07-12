# postmkt — 盤後分析

台股盤後資料的靜態儀表板（單一 `index.html`，無 build 工具），
是[股市雷達 Hub](https://shihpc.github.io/) 的子站之一。

## 八個 Tab（2026-07-12 改版後）

| Tab | 資料源 | 內容 |
|---|---|---|
| 摘要分析 | 前端彙整以下各 tab ＋ 即時呼叫 Anthropic Claude API | AI 生成以查找 alpha 標的為目標的洞見（首頁預設 tab） |
| 彙總分析 | 三頁面（本站盤後/即時類股/新聞晨報）context × Opus4.8/Sonnet5 ＝ 6 份摘要 → Opus4.8 彙總 | 跨份共振精粹 alpha：方向預測＋進出建議；手動一鍵（近2次存瀏覽器）＋自動場（近3日、讀 `data/summary/`） |
| 主動ETF | taiwan-flow-live-v2 `data/aetf/`（跨 repo 唯讀） | 每日投組快照、主動加減碼、進出個股、次產業流向 |
| 融資券借券 | FinMind 融資/融券/借券 + TWSE TWT72U 兩平台借券餘額 | 個股查詢（點開完整明細）＋整合排行（全市場 2200+ 檔、分組雙列表頭、虛擬捲動） |
| 當沖 | FinMind `TaiwanStockDayTrading` + `TaiwanStockPrice` + `TradingDailyReport` | 當沖排行（含漲跌幅/振幅/分點推估） |
| 鉅額交易 | FinMind `TaiwanStockBlockTrade`(+`BlockTradingDailyReport`) | 當日逐筆列表，同股分組、買賣方分點盡力比對 |
| 零股 | TWSE `TWTC7U`（盤中）/`TWT53U`（盤後），公開端點免金鑰 | 盤中/盤後兩子標籤，個股成交股數/筆數/金額 |
| 分點 | FinMind `TaiwanSecuritiesTraderInfo`＋`TradingDailyReport` 專屬 endpoint | 單點（查分點進出個股）/個股（查個股進出分點）/清單（1010 分點模糊查找） |

原「融資」「融券借券賣出餘額」兩 tab 於 2026-07-11 併入「融資券借券」整合排行。

## 架構

- `build_postmkt.py`：抓 FinMind dataset＋TWSE 公開端點的最新交易日全市場資料，
  各 tab 預先聚合排序，輸出 `data/postmkt.json`（~2.4MB）。
  找不到最新交易日資料時自動往前回退最多 5 天；TWSE 端點失敗重試一次後降級（缺欄警示）。
- `.github/workflows/build.yml`：平日 21:30 台北（13:30 UTC）排程＋手動觸發，
  跑完自動 commit `data/postmkt.json`。
- 預產資料的 tab 前端不直連 FinMind（token 走 Actions secret）。
- **例外：分點 tab 的「單點/個股」是互動查詢**（無法預產 1010 分點×2215 檔組合），
  前端直呼 FinMind `/api/v4/taiwan_stock_trading_daily_report`（CORS 開放）。
  token 由使用者在頁面輸入一次、只存瀏覽器 localStorage，不進 repo。
- **例外：摘要分析 tab 前端即時呼叫 Anthropic Claude API**（`insightHtml`/`runInsight`
  /`callClaude`）。`insightGatherContext()` 把主動ETF/融借券/當沖/鉅額/零股盤中彙整成
  ~2.4K token 精簡文字，`insightFetchBrokers()` 即時抓 4 個指定分點（9268/9800/9600/9A00），
  組成 prompt 送 Claude（`anthropic-dangerous-direct-browser-access:true` header 開瀏覽器
  CORS，已實測）。Anthropic token 存 localStorage `anthropic_key`，只送 Anthropic，不進 repo。
  模型 `state.insightModel`（預設 `claude-opus-4-8`）。輸出走 `mdToHtml()` 極簡 markdown 渲染。
- 主動ETF tab 直接讀 taiwan-flow-live-v2 的 raw JSON，不搬遷該站管線。

## 快速接手（2026-07-12）

- 前端表格框架 `tbl(cols, rows, opts)`：表頭排序（`col.sortVal` 供複合欄位給原始值）、
  分組雙列表頭（`col.g`）、加總列（`opts.totals`，sticky 在表頭下）、凍結首二欄
  （`opts.s2`）、>200 列自動虛擬捲動。sticky 相關已知坑全記在 `<style>` 區註解：
  border-collapse/`.tblbox` padding 與 overflow 裁切邊界差（sticky top/left 要設負 padding 值）、
  thead 兩列要 `<tr>` 本身 sticky、rAF 在背景分頁不觸發（量測用 setTimeout、
  虛擬捲動有 200ms 輪詢保險）。
- TWSE 端點的「合計」市場總計列要濾掉（代號欄非 ASCII 英數），TWT72U/TWTC7U/TWT53U 都有。
- 分點查詢聚合：張數保留小數、只在顯示時捨入（先逐列 round 再加總會偏差且讓個股
  買賣超合計出現假非零）。
- 摘要分析：LLM 洞見機制由使用者決定用「LLM 前端即時」（見 2026-07-11 對話）；
  system prompt 強制「只描述歷史統計傾向、非投資建議、非預測、每個觀察可追溯數據」，
  符合工作區共同原則。本站是四站摘要分析的**範本站**，套用已完成（2026-07-12）：
  即時類股動態（taiwan-flow-live-v2）與新聞晨報（taiwan-stock-news）已各自新增同框架 tab；
  盤後法人動態（taiwan-flows）**不加 tab、該站零改動**，其法人資料改併入本站 insight——
  `TF_BASE` 常數（`raw.githubusercontent.com/shihpc/taiwan-flows/main/data`）、`load()`
  平行抓 `latest.json` 存 `state.tf`（失敗不擋），`insightGatherContext()` 新增
  「三大法人買賣超」段（外資買超前10/賣超前6＋台指期未平倉、投信買超前10/賣超前6，
  dlabel 跨日警告自動生效）。SYS prompt 未改。退版點：git tag `pre-insight-tab`。
- 彙總分析 tab（2026-07-12 新增，第 8 個 tab）：一鍵 6+1 呼叫（3 頁 context×兩模型
  ＋Opus 彙總，約 NT$12-15/次），彙總 SYS 以「跨份共振優先」（N/6 份提及）精粹 alpha、
  給方向預測與進出建議。單份失敗不中止（≥3 份成功才彙總）。手動近 2 次存 localStorage
  `summary_manual`；自動場由 `build_summary.py`＋`summary.yml`（cron 08:00/22:00 台北
  觸發＋資料齊全輪詢閘門：am 等晨報最多 90 分、pm 等盤後+新聞最多 120 分，逾時=假日
  skip），輸出 `data/summary/YYYYMMDD-{am|pm}.json` 保留近 3 日，前端列表點閱。
  **假日/颱風假**（2026-07-12 補強）：閘門進場先查 TWSE 休市行事曆 API（免金鑰）擋排定
  假日——am 場必須靠這層（晨報管線假日仍會更新 generated_at，資料閘門擋不住）；行事曆
  混有「開始交易日」等交易日標記，過濾規則見 `is_twse_holiday()` 註解；API 失敗
  fail-open 續走資料閘門。颱風假等臨時停市無盤前可查來源：pm 場由 postmkt.json `date`
  回退機制天然防住；am 場會誤跑一次（約 NT$13、每年 2-4 次），屬已評估接受的殘餘風險。
  **維護重點**：三站 gather 邏輯在本 repo 有兩份移植副本（index.html 的 sumCtx* 與
  build_summary.py 的 gather_*），三站前端 insightGatherContext/SYS 改動時需同步兩處
  （SYS 已驗逐字一致）。自動場需 repo Secret `ANTHROPIC_API_KEY`（見部署設定）。
- 待辦（暫緩）：回測模組（nightly pipeline 累積歷史→前向報酬勝率餵 prompt），
  使用者 2026-07-11 決定暫緩，規格未定義。
- 未解：分點互動查詢在無 token 環境只能看到輸入提示；FinMind 個股層級維持率、
  投信/自營商持股水位等官方未公開，明細面板已註明不提供。
- 未解：摘要分析在無 Anthropic token 環境只能看到輸入提示（無法自動化驗證真實 200 回應，
  已用 dummy key 驗證 CORS/請求格式/錯誤處理/回應解析路徑）。

## 部署設定（需手動做一次）

1. **Secret**：repo Settings → Secrets and variables → Actions →
   New repository secret，名稱 `FINMIND_TOKEN`，值填 FinMind API token（Sponsor 方案）。
   另加 `ANTHROPIC_API_KEY`（Anthropic API key）供彙總分析自動場（`summary.yml`）使用；
   未設時自動場會失敗、前端顯示「尚無自動產出」，手動一鍵不受影響。
   費用參考：自動雙場 × 約 22 交易日 ≈ NT$500-700/月，計入該 key 的 Anthropic 帳戶。
2. **GitHub Pages**：Settings → Pages → Source 選 `Deploy from a branch`，
   Branch 選 `main` / `(root)` → Save。
3. （可選）Actions tab 手動跑一次 `build postmkt data` 產生第一份資料。

## 本機開發

```bash
pip install -r requirements.txt
FINMIND_TOKEN=xxx python build_postmkt.py
python -m http.server 8000   # 開 http://localhost:8000
```
