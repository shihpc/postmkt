# 月營收 Beat／Miss（規格與驗收條件）

建立：2026-11-12。目標專案：`shihpc/postmkt`（`/home/claude/postmkt`，雲端 session）。
使用者需求：每月 11 日產出「上月營收 vs 預期」的比較，重點是 beat 與 miss 的公司，參考陸行之的月營收分析框架。

分三階段，**一次只做一階段**（鐵律 5）：

| 階段 | 範圍 | 狀態 |
|---|---|---|
| 一 | 資料管線：`src/build_revenue.py`＋輸入檔＋`revenue.yml`＋離線測試 | **完成（2026-11-12）**，結果見 §4 末 |
| 二 | 前端第 19 個 tab「月營收」 | 進行中；驗收條件見 §5 |
| 三 | 回測（beat／miss 公布後報酬）＋門檻校準 | 未開始 |

## 1. 鐵律 8 狀態（重要）

本分類（Beat／Miss／高預期仍 Beat／低預期仍 Miss）**沒有回測依據**。門檻只用 2026 年 7–10 月四個月試作校準
（對照陸行之公開點名的個案），樣本極小。

- 階段一只產生資料檔、**不在任何畫面顯示**；資料檔自帶 `label: "AI 研判，未經回測，非保證"`。
- **使用者裁定（2026-11-12）：無回測依據、同意標示「未經回測」先上線。** 階段二畫面須逐字標「AI 研判，未經回測，非保證」，
  並列入事後驗證（階段三回測）。
- 階段三回測結論出來前，不得拿掉「未經回測」標示。

## 2. 資料與口徑

- 營收：FinMind `TaiwanStockMonthRevenue`，逐檔查詢（`data_id`＋`start_date`），單位換算為**億元**。
  月份用回傳的 `revenue_year`／`revenue_month`（`date` 欄是公布月、晚一個月，不用）。
  全市場單次查詢（不帶 `data_id`）在 Sponsor 方案是否可行**未實測**，故不依賴。
- 股票池：`data/revenue/universe.json`（人工維護的科技／半導體次產業分類，一檔只屬一個次產業，避免加總重複）。
- 預期基準（優先序 A＝B > C；同檔同季以 `expect.json` 為準）：
  - **A** 公司法說財測（換算季營收中位數）、**B** 媒體引用且出處明確的外資預估（不收來源不明的「市場共識」）→ `data/revenue/expect.json`，人工維護、每筆附來源與日期。
  - **C** 模型：`(去年同季 × 上季年增率)` 與 `(上季 × 過去 4 年同季季增中位數)` 的幾何平均，再限制在上季的 0.75～1.30 倍。
    季增中位數**至少要 2 年有值**才採用；不足時只用趨勢項一項；兩項都算不出來＝無法建立預期，該檔列入 `missing`。
- **彭博共識不進本 repo**（repo 與 Pages 皆公開；使用者 2026-11-12 同意彭博層只走私下流程）。
  `expect.json` 不得填入彭博數值或由其推得的數值。
- 正常進度：過去 4 年同季「季內前 k 個月累計 ÷ 全季」的中位數（**至少 2 年有值，不足時用 `k/3`**），限制在 `k/3 ± 0.06`；季末月為 1。
- 驚喜% ＝ `季累計 ÷ (預期季營收 × 正常進度) − 1`。
  C 層在季內第 2、3 個月改算**當月增量**：修正後季預期＝`0.7 ×（前幾月累計 ÷ 前幾月正常進度）＋0.3 × 季初預期`，
  當月預期＝修正後季預期 ×（本月進度 − 上月進度）。A／B 層一律用季累計。
- 門檻：A／B 層 ±10%；C 層 ±15%；C 層且屬 `lumpy_sectors`（認列不穩）±25%。
- 預期高低：高＝預期年增 ≥50% 或預期季增 ≥15%；低＝預期年增 ≤−10% 或預期季增 ≤−10%；
  兩者同時成立時以預期年增 ≥50% 判高，否則判低。
- 次產業年增率：成分股當月營收加總 ÷ 去年同月加總 − 1；**只計入本月、去年同月、上月、去年上月四個月份都有值的成分股**
  （讓本月與上月的成分一致）；與上月年增率相差 ≥10 個百分點標「加速」、≤−10 標「減速」。
- 已知限制（階段二前端讀 `index.json` 前要處理）：目錄內沒有任何月檔時 `index.json` 會是 `{"months":[],"latest":null}`。
- 已知限制：C 層的「預期高低」是模型推估，不等於分析師實際預期；新產品放量、併購、認列時點不固定的公司容易失準。

## 3. 產出

- `data/revenue/<YYYY-MM>.json`（該營收月份一檔）與 `data/revenue/index.json`（`months` 升序＋`latest`）。
- `generated_at` 只在內容有變時更新（內容相同不重寫檔，避免只有時間戳的 commit）。
- 排程：每月 11–16 日 07:30 台北各跑一次（`30 23 10-15 * *` UTC）。申報期限是每月 10 日、遇假日順延，
  連跑數日可涵蓋順延與晚報；未公布的公司列在 `missing`。
- 防呆：可分析家數（`reported_n`＝已公布且能建立預期的檔數）未達股票池五成不寫該月檔（月初因 push 觸發時不產出殘缺月檔）；抓取失敗超過一成立即中止、不寫檔；
  `missing[].why` 區分「抓取失敗」「當月營收未公布或無資料」「歷史不足，無法建立預期」。

## 4. 階段一驗收條件

1. `python -m pytest tests/ -q` 全綠（含新增 `tests/test_revenue.py`，離線、免 token）。
2. `ruff check .` 無新增違規。
3. 以同一份營收資料重跑 2026-08／09／10，`cls`／`sur`／`exp_q` 與試作腳本（session 內 `analyze.py`）逐檔一致；
   **已知且刻意的差異**僅限 `expect.json` 未收的四筆（2330、5269、6515 未查證；2308 來源不明，皆改走 C 層）。
4. `expect.json` 每筆都有可查證來源（附網址）；不含彭博數值，**也不收來源不明的「市場共識」數字**
   （2026-11-12 驗收後移除 2308 一筆：媒體轉引外資報告中的市場共識，無法確認是否出自資料商）。
5. 新 workflow 沿用 `commit-data`／`notify-failure`、`permissions` 含 `issues: write`、actions 版本與既有 workflow 相同。
6. 不動 `index.html`、不動既有四支管線與既有測試。
7. push 後 `revenue` workflow 實際跑成功，`data/revenue/2026-10.json` 出現在 main，
   且 GitHub Pages 上 `data/revenue/index.json` 讀得到（線上驗證，鐵律 6）。

### 階段一結果（2026-11-12）

- 獨立驗收兩輪（fresh-context）：`be4c146` 首驗、`17c6c0c` 重驗修正範圍，皆通過；之後 `515849f` 只改文件文字。
- push 後 `revenue` workflow 實跑成功（run 43124936325 產出 2026-10；run 43125189070 回補 2026-08／09），三個月皆 149/150、
  `fetch_failed` 為空、`missing` 只有 7769。CI 產出與本機以同一份快取重建的內容完全相同（builder 回報「內容相同未重寫」）。
- **線上讀取未由本 session 直接驗證**：雲端 session 的網路白名單連不到 `shihpc.github.io`；只確認 `pages build and deployment`
  對含資料的 commit `6eed01a` 成功。依鐵律 6，這不等於已在實際服務位置驗證，待使用者開網址確認。

## 5. 階段二驗收條件（前端「月營收」tab）

目標：`/home/claude/postmkt/index.html` 新增第 19 個 tab `revenue`（標籤「月營收」），排在 `sentiment` 之後、`dates` 之前。

1. **只在切到本 tab 時才抓資料**，首屏請求清單不變：先抓 `data/revenue/index.json`，再抓選定月份的 `data/revenue/<YYYY-MM>.json`
   （同源相對路徑、CSP 不改）。in-flight 去重；失敗記錯不重試、畫面一句話說明、不拋錯。`months` 為空或 `latest` 為 null 顯示「尚無資料」。
2. **標示**：頁內顯眼處逐字顯示「AI 研判，未經回測，非保證」（取資料檔 `label`，缺值時用同一句常數）；另一行說明口徑（預期三層、門檻取資料檔 `thresholds`）。
3. **自帶資料日**：顯示營收月份、`generated_at`（先過格式檢查）、已分析 `reported_n`／`universe_n`；`missing` 逐檔列出代號、名稱與原因。
   頂列 stats 比照籌碼雷達清空。
4. **內容三區**：(a) 四類摘要，「高預期仍Beat」「低預期仍Miss」置前，各列檔數與個股（代號、名稱、驚喜%）；
   (b) 次產業表（年增%、上月年增%、變化、加速／減速），並列台積電當月年增 `tsmc_yoy` 作基準；
   (c) 個股表，沿用共用 `tbl()`，欄位＝分類、代號、名稱、次產業、當月營收（億）、月增%、年增%、預期季營收、預期季增%、預期年增%、
   達成率%、正常進度%、驚喜%、基準層、來源；可依分類與次產業篩選，預設排序＝資料檔順序。
5. **月份切換**：下拉選單列 `index.months`（新到舊）；hash 新 key `rm`（`^\d{4}-\d{2}$` 且須在 `months` 內）只在 `tab=revenue` 讀寫，
   預設（最新月）不寫入 hash；非法值靜默退回最新月。
6. **顏色**：分類以文字標籤呈現、中性色，不新增紅綠燈號；漲跌著色只用在月增%／年增%／驚喜%（沿用 `sgn()`）。
7. **安全**：外來字串插值一律 `esc()`；數值先做 typeof number＋isFinite 檢查，否則顯示「—」；來源欄的網址**不轉成連結**。
8. **不動**三站／四站同步碼（`callClaude`／`mdToHtml`／`linkifyStocks`／`ghSaveAnalysis`／`sumCtx*`／費用估算／`loadSiteVer`）、不動 CSP、
   不動既有 tab 行為；CSS 一律 `.rev-*` 前綴；純函式集中在 `rev-pure:begin`～`end` 區段。
9. **測試**：新增 `tests/test_revenue_frontend.mjs`（由 `tests/test_revenue_frontend.py` 代跑）涵蓋純函式（月份白名單、篩選、數值格式、
   generated_at 檢查）與讀碼檢查（lazy 載入、標示句、`esc()`）；既有測試全綠（含會讀 `index.html` 的測試）；`ruff check .` 無違規。
10. **實測**：本機 http.server 以 Playwright 逐一點 19 個 tab，console 零 error；375／390／1280 三寬度下整頁
    `document.documentElement.scrollWidth == window.innerWidth`，個股表在 `.tblbox` 內橫捲、逐格無裁切（CLAUDE.md「手機驗收條件」）。
11. **文件**：README（tab 數與本 tab 說明）、CLAUDE.md 佈局（18→19、hash key `rm`）、CHANGELOG 同步；CANON 區塊不動。
12. **部署**：push 後 pages 部署成功；因本 session 連不到 `shihpc.github.io`，線上頁面由使用者開啟確認。
