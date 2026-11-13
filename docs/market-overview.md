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

## 3. 交集表（後端）——2026-11-12 實查後定案

方向：**本批只做偏多（資金流入）側**；偏空側未做，文件與畫面說明列明。
實作 `src/build_overview.py`；常數名見該檔頂端。以下數字為 2026-11-12 以本機 checkout 實查／實跑的結果。

### 3.0 規格初稿（留存：定案前的候選清單）

類股候選 A–E、個股候選 a–f 與「次產業來源須經 (產業, 次產業) 對映上卷，對不上就降級為另列、不得硬湊」的要求，
見本檔 git 歷史 `e85087e`；定案如下。

### 3.1 類股交集（主鍵＝產業鏈「產業」）

**分類體系實查**：
- taiwan-flows `sector_ranges_lite.json` 的 chain 類股（47 個）、taiwan-flow-live-v2 `chain_daily/series.json` 的 `chains`（47 條）、
  `classify.json` 的 `map[].c`（47 個）三者**集合完全相同**（交集 47、差集皆空）→ A／B／E 可直接用產業名當主鍵。
- `classify.json` 的 `map[].p`＝(產業, 次產業) 配對共 512 組，與 taiwan-flows `industry_chain.json` 的配對**完全相同**；
  次產業名 484 個，其中 **19 個同名次產業掛在多個產業下**（例：「生產製程及檢測設備」→ 半導體／印刷電路板／平面顯示器；「伺服器」→ 雲端運算／電腦及週邊設備）。
- `aetf/diff.json` 的 `subs[].name` 128 個、`morning.json` 的 `signals.new_subs` 6 個，全部查得到對映（128/128、6/6）。
- 上卷規則：**只上卷「唯一對到一個產業」的次產業**；對到多個產業或查不到的列在該來源的 `unmapped`、不計入（不硬湊）。
  `classify.json` 讀不到時 C、D 整個降級為 `listed`（另列、不計入交集）。

| 來源 | 定案 | 口徑 | 資料日 |
|------|------|------|--------|
| A 產業鏈資金流 | **納入（基準）** | `windows.r5` chain／`total`，`net_amt_k`>0 依金額遞減（同值依名稱）前 10（`TOP_A`） | `windows.r5.end` |
| B 籌碼雷達 | **納入** | 前端 `radarPoints(r5, r20, "chain", "total")`（含 r20 `n`≥8 的門檻）中 `radarQuad`＝`acc_in`（**加速流入**）者。初稿寫的「轉買」在 `radarQuad` 沒有對應象限（`slow_out`「流出放緩」不保證近 5 日為淨買），故只取加速流入 | 同 A |
| C 主動 ETF 次產業 | **納入（經上卷）** | `subs` 中 `val`>0 依金額遞減（同值依名稱）前 10（`TOP_C`）→ 上卷到產業；輸出保留 `subs`（原始前 10）、`via`（每個產業由哪些次產業上卷）、`unmapped` | `primary_date` |
| D 連湧／新湧次產業 | **納入；晚間建置不計入、隔天早上重跑時計入** | `signals.cont_subs`＋`new_subs` → 上卷。**資料日＝`recap.baseline_date`＝前一交易日**（`taiwan-flow-live-v2/src/build_morning.py` 的 signals 由前一日 baseline 算出；2026-11-12 的檔 `baseline_date`＝2026-11-11），**是否計入取決於建置時點**：晚間建置時 `morning.json` 仍是當天早上那一版（`baseline_date`＝前一交易日）→ 依 §3.3 判 `stale`、另列不計入；隔天早上 `morning.json` 更新後若又有一班建置（排程延遲到清晨、或 push 觸發），`baseline_date` 已等於基準日 → **計入**（線上實證：2026-11-13 08:43 台北 push 觸發的 mktbal run 43339158924，D 資料日 2026-11-12、計入，類股列由 4 變 6） | `recap.baseline_date` |
| E 日級輪動雷達 | **納入** | 前端 `rrgdPrep`→最後一個有效日 t，`rrgdPersistList` 連續 3 日「改善」（依 RS-Momentum）與「領先」（依 RS-Ratio）兩份清單的聯集；`via` 記是哪一個象限。**該雷達的回測 12 格中信賴區間不跨 0 的為 0 格（0/12）**，畫面說明列註明 | `dates[t]` |

**計票群組（2026-11-12 驗收後修正）**：A 與 B 讀同一個檔的同一個 r5 窗，而 `acc_in` 的定義（近 20 日日均 ≥0 且近 5 日日均 ≥ 近 20 日日均）
保證近 5 日淨額不為負——B 的成員只要進 A 前 10 就必然兩者皆中，不是兩個獨立來源。故 A、B 併為同一個計票群組**「法人資金流」（`group:"flow"`）：
同組內命中幾個來源都只算 1 票**；`hits` 與畫面的來源欄仍分別標出 A、B，來源狀態列也照列兩者。機制是通用的（每個來源帶 `group`，預設各自成組）。
類股層的計票群組因此是 4 個：法人資金流（A、B）、C、D、E。修正前「資通訊安全」只靠 A＋B 上榜、「製藥」算 3 票；修正後前者不上榜、後者 2 票。

**D 何時另列、何時計入**（2026-11-13 更正；原寫「恆判 `stale`」是錯的，使用者同日裁定維持現行行為、只改文件）：連湧／新湧的資料日＝`recap.baseline_date`。
晚間建置時它是前一交易日 → `stale`、另列不計入（來源的 `note` 與畫面來源狀態列會寫明原因）；隔天早上 `morning.json` 更新後再建置則資料日等於基準日 → 計入。
程式一字未改，判定仍是 §3.3 的「資料日＝基準日才計入」。

**C 被丟掉的次產業怎麼呈現**：同名掛在多個產業下（或查無對映）的次產業不上卷，列在來源 C 的 `unmapped`；
畫面在來源狀態列 C 那一行以「未上卷（一個次產業名對到多個產業或查無對映）：…」逐一列出，不計入任何產業。

2026-11-12 實跑：A 10 個、B 5 個、C 前 10 個次產業上卷成 5 個產業（2 個 `unmapped`：「生產製程及檢測設備」「記憶體」）、
D 5 個（stale）、E 12 個；交集 **4 列**（併票前 5 列）。

### 3.2 個股交集（主鍵＝股票代號，白名單 `^\d{4}[0-9A-Z]{0,2}$`，不合的丟棄）

| 來源 | 定案 | 口徑 | 資料日／容許窗 |
|------|------|------|----------------|
| a 外資投信同步買超 Top30 | **納入（基準）** | taiwan-flows `latest.json` `pages.sync.sync_buy` 全部（30 檔） | `latest.date` |
| b 主動 ETF 加碼共識 | **納入** | `diff.stocks` 中 `by`（主動純額口徑）為正的 ETF 數 ≥2（同本站 aetf tab `aetfInsight` 的 `nBuyers(s)>=2`；不截前幾名） | `primary_date`，須等於基準日 |
| c 選股二追蹤名單 | **納入** | `data/pick2/track.json` `tracking` 全部（`schema` 須為 1） | `track.date`，須等於基準日 |
| d 月營收 Beat | **納入（月頻）** | `data/revenue/index.json` 的 `latest` 月份檔中 `cls` 為「高預期仍Beat」或「Beat」者 | 營收月份 M：基準日落在 **M+1 月 1 日～M+2 月 15 日**才計入（`REV_VALID_UNTIL_DAY`＝15；下一個月的營收約 11–16 日建置，留到 15 日） |
| e 千張大戶週增前 20 | **納入（週頻）** | 前端 `radarHolders(diag, "all").up`（`hdw`>0 依 `hdw` 遞減、同值依代號，前 20） | 集保資料日 `hdd`（全體最大值）：距基準日 **0–10 個日曆日**內才計入（`HOLDER_MAX_AGE_DAYS`＝10；週資料正常落後 ≤7 日，留假日餘裕） |
| f 彙總分析精華標的 | **不納入** | 2026-11-09～11-12 八場自動彙總的標的標題有**七種不同寫法**（例：`｜方向：偏多`、`｜**偏多**`、`｜偏多`、`｜大型｜共振 2/3 份｜**偏多**`，另有一場沒有 `###` 標題），方向無法以固定規則可靠解析；輸出以 `status:"excluded"` 列出並說明 | — |

**個股層有無同型的重複計票**：逐對查過，沒有「同檔同窗、其一成立即保證另一成立」的來源對，五個來源各自成組。
最接近的是 c 與 e（都出自 `diag.json`）：c 的多空總分 12 項中有 1 項（權重 2）用到 `hdw`，但大戶週增前 20 不保證總分 ≥80，反之亦然，不併組。
b（個股層）與 C（類股層）同出自 `aetf/diff.json`，分屬兩張表、互不計票。

2026-11-12 實跑：a 30、b 14、c 24、d 19（2026-10）、e 20（hdd 2026-11-06）；交集 18 列（併票前後相同）。

### 3.3 共同規則

- 計數（`count`）＝該鍵命中的**有效計票群組**數（同組多個來源只算 1 票；同一來源內重複的鍵只記一次）；
  輸出 `count ≥ 2` 的列，依 count 遞減、同數依鍵遞增。`hits` 仍列出每一個命中的來源，所以 `len(hits)` 可以大於 `count`。
- **來源有效性**：每個來源記自己的資料日；日頻來源的資料日 ≠ 該層基準日（類股層＝A、個股層＝a）即 `stale`、**不計入**；
  月頻 d、週頻 e 依 §3.2 的容許窗。基準來源本身讀不到時，該層其餘來源一律 `stale`（無從比對）、該表不輸出列。
- 來源讀不到／形狀不合＝`status:"fail"`、不計入，其餘照算；有效**計票群組** <2 時該表不輸出列並在 `note` 說明
  （例：類股層只剩 A、B 有效時是 1 個群組，不輸出）。
- **兩層的基準來源都讀不到 → 不寫檔、exit 2**（沒有可用的日期）。頂層 `date`＝個股層基準日，缺則用類股層基準日。
- 輸出 schema 1：
  `{schema, date, generated_at, label, side:"long", sectors:{base_date, sources:[…], rows:[…], note?}, stocks:{…同}}`。
  schema 維持 1（計票群組只新增 `sources[].group`／`group_name` 兩欄、`count` 的算法在首次上線前修正，沒有既有消費者）。
  `sources[]`＝`{id, name, freq, group, group_name?, date, ok, stale, counted, status, n, items:[{key, name?, via?}], subs?, unmapped?, note?}`，
  `status` ∈ `valid`／`stale`／`fail`／`listed`／`excluded`，`counted` 只在 `valid` 為真。
  `rows[]`＝`{key, count, hits:[來源 id…], name?（個股）, via?:{來源 id:[上卷前的次產業或象限…]}}`。
  `label` 逐字為「AI 研判，未經回測，非保證」。
- 快照冪等：同一 `date` 重跑覆寫同一檔；`generated_at` 以外內容不變時**不重寫檔**（`write_if_changed`），不產生 commit。
- 排程：`diag.yml`（pick2 之後）與 `mktbal.yml`（晚場鏈最後一棒）各跑一次，皆 `continue-on-error`、commit 之後才轉紅；
  不新增 Worker cron、不改其他 repo。
- 跨 repo 讀取：CI 走 `raw.githubusercontent.com/shihpc/<repo>/main/…`（逾時 30 秒、重試一次、免 token）；
  本機以 `--src-root /home/user`（或環境變數 `OVERVIEW_SRC_ROOT`）改讀 checkout。本 repo 的檔一律讀磁碟。
- 口徑移植的守門：`tests/test_overview_build.py` 以 node 抽 `index.html` 的 `radarPoints`／`radarHolders`／RRGD 純函式區段／
  `nBuyers`，與 Python 移植逐位比對（座標比 `float.hex()`）。

### 3.4 已知限制（誠實列出）

- **D 是否計入取決於建置時點，同一基準日的快照因此可能前後不同**（見 §3.1）：晚間各班 D 為 `stale`；隔天早上若再有一班（GitHub cron 延遲到清晨有前例、或 push 觸發），D 會計入、類股列數可能變多。
  **`data/overview/daily/<date>.json` 以最後一次寫入為準**（同日覆寫）；事後驗證要比較 D 計入與否時，以檔內 D 來源的 `counted`／`date` 欄判斷該份快照屬哪一種，必要時從 git 歷史取晚間那一版。
- CI 讀的是 raw main，上游當晚尚未落地的來源會被判 `stale`；mktbal 那班是第二次機會，之後不再重跑。
- raw.githubusercontent.com 在 CI 的實際連通與延遲**未實測**（本批只以本機 checkout 實跑）；上線後第一晚須看 workflow log。
- 休市日不特別處理：上游不更新時內容不變、不重寫檔。

## 4. 前端

- `TABS` 新增 `overview`「市場總覽」（位置：第一個；**預設 tab 不變**）。CSS 一律 `.ov-*`；不加新 hash key。
- 交集表用既有 `tbl()`，不改 `tbl()`；出現清單數為中性色，不加燈號；每列列出命中哪些來源（只為**計入**的來源開欄，
  未計入但讀得到的來源在來源狀態列以「另列（不計入交集）」列出其項目）。
- 盤勢第 3 項（外資台指期）定案讀 `../taiwan-flows/data/futures/<YYYYMMDD>.json`（每日約 5KB），日期取 `totals.json` 的最末兩個交易日；
  淨口數＝TX／外資的多方未平倉口數 − 空方未平倉口數（`latest.json` 的 `futures_card` 只有對上月底的增減、沒有前一交易日，故不用）。
- 盤勢第 6 項取 `data/summary/index.json` 最新一場的 `synthesis.text` 中「## 盤勢綜合研判」一節（`ovSynthSection`），經三站同步碼 `mdToHtml` 顯示（只呼叫）。
- 程式位置：`index.html` grep `// ================= 市場總覽 tab`；純函式在 `ov-pure:begin`～`end`；測試 `tests/test_overview_frontend.mjs`。
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

## 6. 資金流出側（2026-11-13 追加）

### 6.0 使用者裁定

- 2026-11-13 使用者指示處理先前列為未做的「資金流出側」。它與流入側同型：依「出現在幾個來源群組」排序的候選排序、**無回測依據**，
  沿用 2026-11-12 的裁定條件——畫面逐字標示「AI 研判，未經回測，非保證」、每日快照留存、列入事後驗證。
- 用語一律「資金流出側」；畫面與文件**不得**寫成放空／賣出建議。

### 6.1 來源（流入側各來源的鏡像；實作者逐一打開實檔核對後把定案寫回本節）

類股（主鍵＝產業鏈「產業」）：
- A′ 產業鏈資金流：r5 chain／三大法人淨額 <0，依淨賣金額取前 10
- B′ 籌碼雷達：流入側所用象限的鏡像（加速流出；以前端 `radarPoints`／`radarQuad` 的實際象限名為準）；**A′、B′ 併為同一計票群組**（同檔同窗）
- C′ 主動 ETF 次產業流向：減碼前 10，上卷規則同 C
- D′ `morning.json` 若有對應的退潮類訊號才納入（資料日規則同 D）；沒有就寫明「無對應來源」
- E′ 日級輪動雷達：流入側所用兩個象限的鏡像（以 `rrgdPersistList` 實際支援的清單名為準；若前端沒有現成的鏡像清單，寫明並說明如何以同一純函式取得，不得另創口徑）

個股（主鍵＝代號）：
- a′ 外資投信同步賣超 Top30（`pages.sync` 的賣方清單）
- b′ 主動 ETF 跨 ETF 減碼共識（≥2 檔同賣，口徑對齊本站 aetf tab 的賣方共識）
- c′ 選股二：**無流出側對應**（追蹤名單只有選入），不納入
- d′ 月營收 Miss／低預期仍 Miss（容許窗同 d）
- e′ 千張大戶週減前 20（`radarHolders` 的減少側）

### 6.2 規則與輸出

- 計票群組、stale、容許窗、count ≥2、排序、降級規則全部沿用 §3.3，**與流入側共用同一份實作**（以方向參數區分，不得複製一份）。
- schema 維持 1、**只增不改**：既有頂層 `side`／`sectors`／`stocks`（流入側）一字不動；新增 `out: {sectors:{…}, stocks:{…}}`，內部形狀與流入側相同。
  `daily/<date>.json` 同步帶 `out`。既有流入側輸出在同一份輸入下必須逐位不變（測試守門）。
- 前端：總覽頁交集區加「資金流入側／資金流出側」切換（預設流入側；狀態不進 hash、不加新 hash key）；流出側同樣顯示來源狀態列、標示句與說明列。
  `out` 缺（舊檔）時流出側顯示一句「尚無資料」，流入側照常。

### 6.3 驗收條件

1. pytest 全過（本批起預期 0 failed）；ruff 通過；三站同步碼、`tbl()`、CSP、CANON 區塊不動。
2. 新測試：流出側各來源的方向與門檻（突變會紅：正負號反轉、取到流入側象限、前 10 改 100、群組失效、count≥2）、與前端口徑對跑、
   **流入側輸出逐位不變**、`out` 缺時前端降級。
3. 真實資料實跑成功；獨立重算（不 import 實作）兩張流出表逐列相符。
4. 前端：20 tab 無頁面錯誤、首屏請求清單不變、375／390／1280 無整頁水平捲軸與逐格零裁切、切換兩側皆逐字顯示標示句、注入不執行、
   畫面無「放空」「賣出建議」等字樣（來源名「同步賣超」「減碼」屬描述，允許）。
5. fresh-context 驗收綁定 commit；CLAUDE.md／CHANGELOG／本文件同步。
