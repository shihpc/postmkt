# postmkt — 盤後分析

台股盤後資料的靜態儀表板（單一 `index.html`，無 build 工具），
是[股市雷達 Hub](https://shihpc.github.io/) 的子站之一。

## 十四個 Tab（2026-09-09 加「持股異動」後）

| Tab | 資料源 | 內容 |
|---|---|---|
| 摘要分析 | 前端彙整以下各 tab ＋ 即時呼叫 Anthropic Claude API | AI 生成以查找 alpha 標的為目標的洞見（首頁預設 tab） |
| 彙總分析 | 三頁面（本站盤後/即時類股/新聞晨報）context × Sonnet5 各 1 次 ＝ 3 份摘要 → Opus4.8 彙總（自動場走 Message Batches 半價） | 跨份共振精粹 alpha：方向預測＋進出建議；手動一鍵（近2次存瀏覽器）＋自動場（近3日、讀 `data/summary/`） |
| 主動ETF | taiwan-flow-live-v2 `data/aetf/`（跨 repo 唯讀，資料源 FinMind、20+ 檔） | 每日投組快照、主動加減碼**兩欄並列**（主動純額 net_active｜含申贖 raw_change）、進出個股、次產業流向（含ETF名稱）；點 ETF 一律可展開，先看**最新持股組合**（標持股基準日）再看加減碼明細（標資料日，無加減碼顯示「今日無主動加減碼」）；彙整含跨ETF共識與「主動 vs 含申贖」解讀 |
| 融資券借券 | FinMind 融資/融券/借券 + TWSE TWT72U 兩平台借券餘額 | 個股查詢（點開完整明細）＋整合排行（全市場 2200+ 檔、分組雙列表頭、虛擬捲動） |
| 當沖 | FinMind `TaiwanStockDayTrading` + `TaiwanStockPrice` + `TradingDailyReport` | 當沖排行（含漲跌幅/振幅/分點推估） |
| 鉅額交易 | FinMind `TaiwanStockBlockTrade`(+`BlockTradingDailyReport`) | 當日逐筆列表，同股分組、買賣方分點盡力比對 |
| 零股 | TWSE `TWTC7U`（盤中）/`TWT53U`（盤後），公開端點免金鑰 | 盤中/盤後兩子標籤，個股成交股數/筆數/金額 |
| 分點 | FinMind `TaiwanSecuritiesTraderInfo`＋`TradingDailyReport` 專屬 endpoint | 單點（查分點進出個股）/個股（查個股進出分點）/清單（1010 分點模糊查找） |
| 大盤餘額 | FinMind `TaiwanStockTotalMarginPurchaseShortSale`（融資/融券）＋ TWSE `TWT72U`（借券賣出，SLB+NLB整體市場相加）＋ TWSE `TWTA1U`（不限用途借貸，6 selectType加總） | 全市場層級四項餘額合計（融資/融券/借券賣出/不限用途款項借貸），4 pill 切換，近5日逐日＋近3年各月底（年列可展開），與「融借券」tab（個股排行）明確區分定位 |
| 輪動雷達 | taiwan-flow-live-v2 `data/chain_daily/series.json`（跨 repo 唯讀，594KB 懶載，283 交易日 × 47 條產業鏈日頻序列，每交易日夜間增量更新） | 盤後日頻 RRG（B-ew 軸：等權報酬相對大盤等權基準，n=12 z-score／k=10 動能）：47 鏈散點＋成交額 Top10 錨點軌跡尾巴、日期回看、候補清單（改善／領先象限，持續性 N=3 完整列出）、新鮮度提示；描述語氣、附成員重疊揭露與盤中版互連 |
| 選股 | `data/screen/screen.json`（`src/build_screen.py` 盤後管線：TradingView scanner 批次初篩「明年預估 EPS≥20」→ 鉅亨網 marketinfo API 逐檔補 FactSet 多年度預估 EPS 分佈/目標價/券商評等 → 合併 diag.json 籌碼/營收欄） | 分析師預估選股表：現價、FY 今年/明年預估 EPS（錨定資料日日曆年）、forward PER（自算）、EPS 預估家數（明年，表內附預估日與樣本數）、目標價中位與潛在漲幅、營收 YoY/連 N 月、PER-TTM、評等濃縮；門檻鈕（明年 EPS ≥30/50/100）＋全欄排序；固定標注 FactSet/鉅亨網來源與「預估非保證」免責 |
| 日期 | 即時 fetch 八個資料源的 date/generated_at | 全專案資料日期總覽：各源資料日/產出時間(台北,到分)/新鮮度狀態（最新/落後N個交易日，僅排除週末、國定假日不扣），一眼看清哪些資料到今天 |
| 持股異動 | `data/postmkt.json` 的 `market_daily`（全市場逐檔 {代號, 漲跌%, 外資張, 投信張}，走既有 `ensurePm()`，**本 tab 零新增網路請求**；畫面上的隱私承諾一律寫「持股代號不進任何網路請求」，**不可寫「本 tab 不發任何網路請求」**——`ensurePm()` 本身就會抓 `data/postmkt.json`，那句是假的） | 拿本機持股清單（localStorage `pm_holdings`）比對全市場逐檔資料，只列達門檻者（法人 ±100 張或漲跌 ±3%，最多 5 檔）；**六種「說錯話」分開講**（與本檔「前端消費 `market_daily` 的必要條件」六軸、`index.html` 該段註解 ①–⑥ 為同一組）：本表不涵蓋（權證／偽代號，**不可說成「查無此代號」**）／該資料日法人資料未到（`f`／`t` 為 null，非 0）／該資料日完全沒有資料（`chg`／`f`／`t` 三欄全 null，**不是**「未達門檻」）／整表殘缺（`rows` 空或 <2000 列）整段「無法取得異動資料」、**不得逐檔說成「查無此代號」**（2026-09-09 更正：此列原把「查無此代號」列成六項之一、把「整表殘缺」擺到六項之外，與同檔下方「前四軸／另外三軸」的算法互相矛盾）；**第五軸＝主語一律綁 `market_daily.date`、不寫「今天／今日／當日」**（該日期是價格／法人資料日，與頂列的 `pm.date`＝全檔基準日語意不同；2026-09-09 基準日脫鉤前實測系統性差一天，脫鉤後常態相等但**仍不保證**——見下方第五軸），落後 ≥2 個交易日或缺失時另出一段與免責卡同重量的說明（**不新增紅黃綠判級**）；**第六軸＝整表不可用時頂列徽章不得報成「N 檔涵蓋」**（徽章與內文共用 `myChgUnusable()`）。點個股跳「持股診斷」是全站唯一**刻意塞歷史**的 hash 寫出（`location.hash =`，讓 Back 退得回來；其餘 hash 寫出一律 `replaceState`）。門檻為顯示用可調常數、無回測依據，不是買賣訊號。**2026-09-09 由入口站 shihpc.github.io「我的異動」搬遷而來**（該站表格 6 欄、手機只看得到前 2 欄；持股清單本來就是本站寫入的） |
| 持股診斷 | `data/diag/diag.json`（`src/build_diag.py` 夜間管線）＋ v2 `/live` 現價＋ taiwan-stock-news 新聞 | 輸入持股（僅存 localStorage）→ 逐檔五面向（籌碼/價量/題材/基本面/系統）紅黃綠燈號＋事實清單＋組合層檢查＋近3日新聞命中＋可選 AI 解讀 |

原「融資」「融券借券賣出餘額」兩 tab 於 2026-07-11 併入「融資券借券」整合排行（該 tab 為個股層級排行）；
2026-07-19 新增「大盤餘額」tab 補上大盤層級（全市場合計）視角，兩者並存、口徑用途不同。

## 架構

- `src/fmclient.py`：四支 Python 管線共用的 FinMind client（api_get 統一重試：
  402/429 限流等 65 秒、其他錯誤等 3 秒）＋ `token()`／台北時區工具（2026-07-24
  抽出，原本四份實作重試策略互異、build_postmkt 甚至零重試）。
- `src/twseclient.py`：TWSE 公開端點共用 client——全域節流鎖（IP 限流教訓，見「已知教訓」），
  build_postmkt 與 build_mktbal 共用。
- `tests/`＋`.github/workflows/test.yml`：離線單元測試（pytest，免 token/網路），
  覆蓋日期閘門（news_fresh 跨午夜、slot_trading_day 延遲跨日、is_twse_holiday 民國年/
  fail-open——都是實際踩過的坑）、diag 純函式（streak/rev_metrics/_pctile/_roc_date）、
  fmclient 重試語意、零股合計列過濾、lending 瘦身欄位形狀與重建公式對齊。
  本機跑：`python -m pytest tests/ -q`。Python/測試檔變動時 CI 自動跑。
- `build_postmkt.py`：抓 FinMind dataset＋TWSE 公開端點的最新交易日全市場資料，
  各 tab 預先聚合排序，輸出 `data/postmkt.json`（~1.6MB；2026-07-24 瘦身：lending.rows
  只落地基礎量＋px 收盤價，市值/金額衍生欄由前端 `augmentLending()` 與
  `build_summary.py _augment_lending()` 載入後重建，公式三處需一致；當沖 `by_ratio`
  比重榜同時停產——前端從未渲染，停產順帶把分點推估查詢從 ~100 檔減半）。
  TWSE 端點（TWT72U/零股）改走 `src/twseclient.py` 全域節流。
  找不到最新交易日資料時自動往前回退最多 5 天；TWSE 端點失敗重試一次後降級（缺欄警示）。
  **`market_daily` 區塊（2026-09-09 新增，供「持股異動」用）**：全市場逐檔精簡底表，
  形狀比照 taiwan-flows `data/daily/<d>.json` 的 `{date, cols, rows}` 欄式二維陣列，
  `cols` ＝ `["c","chg","f","t"]`（代號／漲跌%／外資買賣超張／投信買賣超張），
  `date` ＝ `lending.date`（與最上層 `date` 語意不同，見 `docs/date-semantics.md`）。
  **宇宙＝當日 `TaiwanStockPrice` ∩ `TaiwanStockInfo`（`nm`）－ 商品類黑名單**，兩者建置時
  都已在手、零額外 API 呼叫；**不能直接用整包 `TaiwanStockPrice`**——它單日全市場就有 4.5 萬列
  （2026-09-09 CI 實測 45,675 列，權證佔絕大多數），照單全收會讓全檔從 ~1.65 MB 變成
  2,719,486 bytes（實測）。**收斂靠的是 `nm`（3,147 檔對照），代號型態只當黑名單、不當白名單**：
  白名單寫法會把真的可以被持有的證券擋掉（2026-09-09 以本站自己的 `data/postmkt.json` 反查，
  誤擋 7 檔＝4 檔 `91xxxx` 存託憑證＋2 檔 `01xxxT` REIT 受益證券＋`2887Z1` 雙字元後綴特別股），
  那些代號會在前端呈現成「查無此代號」而非「資料源不涵蓋」。**黑名單只擋兩類**
  （`RE_MARKET_CODE` 要求數字開頭、`RE_MARKET_EXCLUDE` 擋權證）：**權證**（6 碼 `03`–`09` 開頭／
  `7` 開頭；`nm` 自己就收了 36 檔、全部是 `7` 開頭，實測 `710553` 當日有價，所以 `nm` 單獨當閘門
  擋不住）、**`Index`／`大盤` 偽代號**（`TAIEX`、`Semiconductor`… 共 32 筆）。
  **ETN 已納入**（2026-09-09 使用者裁定）：ETN 是可以被持有的證券（`nm` 內 48 檔，代號一律
  `02` 開頭、不帶 U，例 `020041`／`02001L`），擋掉會讓持有者在前端被告知「查無此代號」。
  取捨方向固定：寧可多放幾檔（幾十列、不到 1KB），不可少放一檔。
  收斂後 **2,757 檔**（**真實建置實測**：2026-09-09 CI run `34321284815`／head_sha `ec50d80`，
  基準日 2026-09-08；個股＋ETF＋ETN＋DR＋REIT＋特別股全保留，含 `00637L`／`00981A` 這類字母後綴），
  區塊約 55KB，全檔 **1,706,347 bytes ＝ 1.706 MB**（本檔 MB 一律 10⁶ 進位）。
  日常區間 **2,730–2,830 檔**／**1.70–1.72 MB**——兩次真實建置（`c44937b` 2,724 檔／1,707,249 B、
  `ec50d80` 2,757 檔／1,706,347 B）體積都落在區間內。**全檔 byte 數只給區間、不做點預測**：
  本檔由十幾個區塊合成，當天 TWSE 零股（`TWT53U`）等區塊取到哪一天的內容也會左右總長度
  ——2026-09-09 那次點預測就因此比實測高了 1,753 B（預測 1,708,100–1,708,240 B、實測 1,706,347 B），見 CHANGELOG 2026-09-09。
  **前端消費本區塊前必讀下方「前端消費 `market_daily` 的必要條件」。**
  漲跌%與當沖 tab 共用 `_chg_pct()`。**查不到法人資料寫 `null` 不寫 0**（刻意與
  `lending.rows` 的 `foreign_vol`/`trust_vol` 不同——後者把「沒資料」寫成 0，兩者無法
  區分），法人資料日 ≠ 基準日時 `f`/`t` 全留 `null`（寧缺勿混；`build_lending` 沒有這道
  守門，兩邊那天會不一致——刻意的，見 CHANGELOG 2026-09-09）。
  **此區塊必須排在 `out` 最後（跨 repo 檔頭契約）**：taiwan-flow-live-v2 的 Worker
  `/status`（`fetchStatusHead`，`bytes = 2048`）與 claude-harness
  `tools/freshness_watchdog.py`（`HEAD_BYTES = 2048`）都對本檔走 Range 只取**檔頭
  2048 bytes**，再 regex 撈**第一個** `"date"`／`"generated_at"`；任何區塊插到那兩個
  key 之前，兩站會**靜默**撈到錯的日期或撈不到。守門測試＝
  `tests/test_postmkt_build.py::test_output_head_contract_date_and_generated_at_first`
  （對 `json.dumps` 後前 2048 bytes 跑與那兩個消費端逐字相同的 regex）。此契約與
  `CLAUDE.md`「不可破壞的約定」第 7 條「外部消費者」屬同一組跨 repo 依賴——第 7 條
  只寫了 Worker 輪詢 raw main 鏈式觸發下游，**沒有**涵蓋這條檔頭 Range 契約。
- `.github/workflows/build.yml`：平日 21:53 台北（13:53 UTC）排程＋手動觸發
  （2026-07-14 起由 21:30 延後：FinMind 當沖量值約 21:30 後才更新，留緩衝＋
  冷門分鐘避開壅塞），跑完自動 commit `data/postmkt.json`。
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
- `src/build_mktbal.py`：大盤層級四項餘額（融資/融券/借券賣出/不限用途借貸）管線，輸出
  `data/market_balance_history.json`（daily 近30交易日＋monthly 近36月底，皆升序陣列）。
  `.github/workflows/mktbal.yml`：平日 22:20 台北排程（排在 build.yml/diag.yml 之後）＋
  push-paths 首推＋workflow_dispatch（可帶 backfill）。`--backfill` 一次性回補 3 年，
  TWSE 抓取全域節流(預設4秒/請求，`TWSE_THROTTLE`可調、舊名`MKTBAL_TWSE_THROTTLE`仍相容；
  節流鎖 2026-07-24 抽到 `src/twseclient.py` 供 build_postmkt 共用)＋指數退避重試(2/5/10/20秒)，
  避免連續打 TWT72U/TWTA1U 觸發 IP 限流（2026-07-19 修：前一版無節流，backfill 連抓
  約6次後被限流回空、近八成月份 sbl/unrestricted 全 null；修完 64 個回補日期全數 0 null）。
- 主動ETF tab 直接讀 taiwan-flow-live-v2 的 raw JSON，不搬遷該站管線。
- **日期欄語意**：五 repo 所有產出檔的日期欄（欄位/語意/時區/粒度）對照表見
  [`docs/date-semantics.md`](docs/date-semantics.md)——跨站資料流除錯或調整 dlabel 對齊時先讀它。

## 快速接手

帶日期的歷次變更紀錄已搬到 [`CHANGELOG.md`](CHANGELOG.md)（2026-07-24 起）；
本節只留接手需要的常青內容（各 tab 口徑、資料流、教訓、維護約定）。

### 前端消費 `market_daily` 的必要條件（2026-09-09 訂，改前端前必讀）

**現行消費端＝本站 `index.html` 的「持股異動」tab**（2026-09-09 上線，grep `function myChgHtml`／`const MYCHG_MIN_ROWS`——裸名 `MYCHG_MIN_ROWS` 在 `index.html` 有 4 處命中，宣告式才唯一）。下列**六軸**（軸1～軸4 接在本段之後；第五／第六軸的錨點用**行首形式** `grep -n '^- \*\*第五軸'`／`'^- \*\*第六軸'`（各在本檔唯一命中，實測；**裸名 `**第五軸：` 不唯一——本句自己就是第二次命中**）——它們**不是本節最後兩則**，而是本節頂層 9 則 bullet 的第 7、8 則，其後還有第 9 則「股名對照」，那則不屬六軸。2026-09-09 兩次更正：先前寫「四軸」是補上第五、第六軸時漏改的計數，寫「本節末尾兩則」則是位置講錯）在該 tab 都有對應的實作與文案，改那段程式前先讀完本節；改本節判準（含 `RE_MARKET_CODE`／`RE_MARKET_EXCLUDE`／`MARKET_DAILY_MIN_ROWS`）要回頭同步該 tab 的 `MYCHG_WARRANT_RE`／`MYCHG_SEC_RE`／`MYCHG_MIN_ROWS`。

**`market_daily.rows` 刻意不是全宇宙**。前端拿使用者的持股代號去查這張表時，
**「代號不在 `rows` 裡」不可一律呈現為「查無此代號（已下市／停牌／代號有誤）」**——
本表刻意不涵蓋權證與非證券偽代號，那類必須說「**本表不涵蓋**」而不是「查無此代號」。
持有權證的使用者若被告知「代號有誤」，那是**說錯話**，不是顯示瑕疵。

| | 類別 | 例 |
|---|---|---|
| **涵蓋** | 上市櫃個股（含單／雙字元後綴特別股） | `2330`／`2887F`／`2887Z1` |
| | ETF（含槓桿／反向／主動式字母後綴） | `0050`／`006201`／`00637L`／`00981A` |
| | **ETN**（2026-09-09 起納入） | `020041`／`02001L` |
| | REIT 受益證券 | `01002T`／`01004T` |
| | 存託憑證 DR | `910322`／`911868` |
| **不涵蓋** | **權證**（上市 6 碼 `03`–`09` 開頭／上櫃 `7` 開頭 6 碼） | `030018`／`710553`／`73107P` |
| | `Index`／`大盤` 偽代號（非數字開頭） | `TAIEX`／`TPEx`／`Semiconductor` |

- **「不涵蓋」這個狀態是永久的、消滅不了的**：權證全市場 4.5 萬檔，納入會讓
  `data/postmkt.json` 從 ~1.71 MB 爆到 2,719,486 bytes（實測），所以權證**必須**留在黑名單。
  管線端**無法**區分「不在底表」與「這檔證券不存在」——這是消費端的責任，不是管線的 bug。
- **判別方式（前端可自行做，不需新資料）**：代號**非數字開頭**＝偽代號／不是證券；
  代號符合 `^0[3-9]\d{3}[0-9A-Z]$` 或 `^7\d{4}[0-9A-Z]$`＝權證。這兩類走「本表不涵蓋」文案；
  其餘查不到才是真的「查無此代號」（已下市／停牌／代號有誤）。判準正本在
  `build_postmkt.py` 的 `RE_MARKET_CODE`／`RE_MARKET_EXCLUDE`（**錨點用宣告式**
  `RE_MARKET_CODE = `／`RE_MARKET_EXCLUDE = `，在該檔各唯一命中；裸名各有 5 處，
  另散見 `index.html` 與 `tests/test_postmkt_build.py`），
  **改那兩條 regex 要回頭改這張表**。
- **由來**：入口站 shihpc.github.io 的「我的異動」明文要求三種狀態（達門檻／未達門檻／
  查無此代號）**必須分得開**，理由是「缺資料卻呈現成正常」會讓使用者無從分辨。
  把「資料源不涵蓋」混進「查無此代號」是同一型的錯誤——只是這次錯在**文案斷言了成因**。

以上是「代號在不在表裡」這一軸。**另外三軸同樣會把「缺資料」呈現成別的東西，一併釘住**：

- **`f`／`t` 為 `null` ≠ 無異動——不得當成 0，也不得說成「無顯著異動」**。
  `build_market_daily()` 在**法人資料日 ≠ 基準日**時會把整欄 `f`／`t` 寫成 `null`
  （寧缺勿混；`build_postmkt.py` grep `法人資料日與本區塊基準日`——**裸名 `法人資料日` 有 2 處命中**，守門測試
  `test_market_daily_inst_date_mismatch_blanks_f_t`），單檔查無法人資料時同樣寫 `null` 而非 0
  （`test_market_daily_missing_inst_is_null_not_zero`）。**前端把 `null` 讀成 0 或「無顯著異動」，
  等於原封不動複製本節開頭引用的那個舊坑**（入口站「我的異動」舊版只讀 `latest.json`，
  當日 911 檔達門檻者有 687 檔被寫成「無顯著異動」）。正確文案是「**當日法人資料未到**」——
  同一列的 `chg`（漲跌%）**只要不是 `null` 就仍然有效**、來源是 `price_rows` 本身，可照常判讀，不必整檔靜音
  ——但**不得無條件宣稱「同列漲跌% 當日仍然有效」**，`chg` 自己也可能是 `null`（見下一軸）。
  注意同一天 `lending.rows` 的 `foreign_vol`／`trust_vol` 仍會顯示數字（`build_lending()`
  **沒有**這道日期守門），**兩邊不一致是刻意的**（新區塊較嚴），不是 `market_daily` 壞了。
- **`chg` 也可能是 `null`；`chg`／`f`／`t` 三欄全 `null` ＝「當日完全沒有資料」，不得說成「未達門檻」**
  （2026-09-09 補；此軸原本漏列，前端因此把「完全沒有資料」誤述成「當日資料查得到，只是變化不到門檻」）。
  `build_market_daily()` 的 `chg` 來自 `price_rows` 的當日漲跌%，**查不到就寫 `null`**（不是 0）：
  停牌／當日無成交／上游該檔沒出價的標的都會這樣。**實測（線上 `44ef7e7` 版，資料日 2026-09-08）：
  2,757 列中 `chg` 為 `null` 者 46 列**；該版恰逢法人資料日 ≠ 基準日、`f`／`t` 整欄留空，
  所以這 46 檔**三個資料欄全空**。
  - **這 46/2757 是 n=1 的單日單次觀測，不是常態分布**（2026-09-09 更正）：`market_daily` 區塊
    2026-09-09 才上線，`data/postmkt.json` 近 20 個 commit 只有 `44ef7e7` 帶這個區塊，
    所以「一天有幾檔全空、是哪些檔」目前只有一天的樣本，**不知道日常區間**，引用時要標明。
  - **成分實查（2026-09-09 把 46 檔全數分類，更正原本的「多為匯率避險型 ETF 與 ETN」）**：
    ETN（`02` 開頭）**7 檔**（`020001`／`020011`／`020012`／`020028`／`020032`／`020035`／`020040`）、
    `00` 開頭 ETF **6 檔**（`00638R`／`00656R`／`00707R` 為 R 尾碼、`00625K`／`00643K` 為 K 尾碼、
    `00682U` 為 U 尾碼）、**其餘 33 檔（72%）是一般證券代號**（31 檔純 4 位數字，如 `2945`／`4154`／
    `5906`／`6210`／`6929`／`8905`／`8921`，另 `1312A` 與 `910322` 各 1）。
    **ETF＋ETN 只佔 13/46（28%）**——原描述「多為匯率避險型 ETF 與 ETN」與實檔不符，
    真實樣貌是「以流動性偏低的一般個股為主，ETF／ETN 只是其中一小部分」。
  - **三欄全 `null` 必須自成一類**：它既不是「查得到但變化不到門檻」（那是**有**資料且判過門檻），
    也不是「查無此代號」（它確實在 `rows` 裡）。前端把它併進「未達門檻」＝**把「沒有資料」說成
    「有資料且正常」**，與本節開頭那個舊坑同型。
  - **部分缺值只講缺的那部分**：只缺 `chg`（法人欄有值）就只說「該資料日沒有漲跌%」，仍照法人欄判讀；
    只缺 `f`／`t`（`chg` 有值）才是上一軸的「該資料日的法人資料未到」。**不得為了簡化而把部分缺講成全缺**，
    也不得無條件加上「同列漲跌% 仍然有效」——那句只有在該列 `chg` 真的有值時才成立。
  - **「單欄 null」在現行管線下不可達，那兩個分支是防禦性的（2026-09-09 查證，不要刪）**：
    `build_market_daily()` 的 `it = inst_by_c.get(c)` 以**同一個** `it` 真假值同時決定 `f` 與 `t`
    （法人資料日 ≠ 基準日時 `inst_by_c` 直接清空），所以 `f`／`t` 只會同時有值或同時 `null`；
    前端 `instMissPx` 的「其中 N 檔」與「整句不加」兩個分支因此在管線可達輸入下觸發不到
    （已在 `myChgHtml()` 該處以註解標明）。第三方或未來的資料形狀可能單欄缺，**保留**。
  - 現行實作：`myChgHtml()` 的 `isBlank`／`blank`／`rated`／`instMiss`／`instMissPx`／`pxMiss`
    （grep `const isBlank`），門檻判定 `myChgSig` 本身不變（三欄全 `null` 與「都沒超過門檻」同樣回 `false`，
    差別在**分類與文案**：前者是無從判起、後者是判過）。
- **`rows` 為空或明顯殘缺 ＝「無法取得異動資料」，不得逐檔說成「查無此代號」**。
  上游 `TaiwanStockPrice`／`TaiwanStockInfo` 整包抓不到時，`build_market_daily()` 仍會照常輸出
  `{"date": …, "cols": …, "rows": []}`（有半份資料比整包不產出好），**但前端若沿用
  「不在 `rows` ＝查無此代號」，會把使用者的每一檔持股都說成「已下市／停牌／代號有誤」**——
  這是上述幾種說錯話裡最嚴重的一種。**前端必須先看整表健康度**：`rows` 為空、或
  `len(rows) < 2000`（同管線端的 `MARKET_DAILY_MIN_ROWS`，**錨點用宣告式**
  `MARKET_DAILY_MIN_ROWS = ` 在 `build_postmkt.py` 唯一命中；裸名 4 處）時，**整段顯示
  「無法取得異動資料」**——這句文案沿用自入口站 `shihpc.github.io/index.html` 舊「我的異動」區塊
  `loadMyChanges()` 的失敗路徑（`body.textContent = "無法取得異動資料"`）。**出處已不存在**：
  該區塊隨本 tab 搬遷而於 2026-09-09 從入口站移除（`shihpc.github.io` commit `a30d5fa`），
  `loadMyChanges()` 現已 grep 不到——**但文案本身仍照舊沿用**（那個字串是對的，只是原始碼沒了），
  不要因為找不到出處就改字。**不得**進入逐檔三分狀態，
  **也不得靜默當成「今天沒有異動」**。管線端在這種情況會印 `⚠ market_daily：…` 警告
  （2026-09-09 放寬：原條件是 `price_rows and nm and len(rows_out) < MIN`，**整包為空反而靜默**，
  現在多一條分支專門示警；守門測試 `test_market_daily_warns_when_upstream_input_is_empty`），
  但那只是 CI log，線上前端拿不到，**這道判斷前端必須自己做**。
- **第五軸：`market_daily.date` 不是「今天」——畫面主語不得用「今天／今日／當日」代稱**
  （2026-09-09 補；獨立驗收實測發現，是本節前四軸的**同型第五次**）。
  `market_daily.date` ＝ `build_market_daily()` 的基準日，**2026-09-09 起＝法人日 `d_inst`**
  （價格／法人資料日；同日修正前綁的是借券 tab 的 `lend_date`，見 CHANGELOG）。它**與
  `data/postmkt.json` 最上層的 `date`（頂列顯示的全檔基準日）語意不同**：該 `date` 實查
  `build_postmkt.py:768-769` 的 `dates = [...]`／`latest = max(dates)`，**只取 margin／lend／
  short／dt／block／inst／hold 七支 FinMind dataset 的日期**，**不含**兩支 TWSE 零股日期
  `d_oddi`／`d_odda`（`build_postmkt.py:765-766`），所以寫成「所有資料源的最大日」是過寬的。
  脫鉤後常態相等，但只要有任何一支資料源比法人更新，兩者就會再度分開，**相等不是保證**。
  脫鉤前的實測是系統性差一天（線上 `44ef7e7`：頂列 `2026-09-09`、本區塊 `2026-09-08`）
  ——那是本軸的成因證據，脫鉤只縮小發生頻率、**沒有消滅這個狀態**，所以本軸的**規範**一字不改。同一畫面同時
  擺出兩個日期、主語卻寫「今天」，等於**宣稱這是今天的狀態**；把 `date` 改成一個多月前，
  舊版畫面照樣說「持股中今日沒有任何一檔達門檻」，真正的資料日只在最底下 0.74rem 灰字裡。
  - **現行實作**：`myChgDateInfo()`／`myChgWhen()`／`myChgAt()`（grep `function myChgDateInfo`）。
    免責卡、段落標題、主句與每一條說明全部寫出實際日期；日期缺失或格式不合時說
    「本區塊資料日（不明）」，**不得退回「今天」**。
  - **落後或不明要看得出來**：資料日落後今日 ≥ `MYCHG_STALE_LAG`（2）個交易日、晚於今日、
    或缺失時，另出一段與免責卡同重量的 `.diag-disc` 說明（不是 0.74rem 灰字）。交易日距離沿用
    `dayDiff()`（只排週末、國定假日不扣，同頂列與日期 tab 的已知近似）。
    **刻意不新增紅黃綠判級**（判級語意未經裁決，CANON 第 8 條），只把「這些數字是哪一天的」講清楚。
  - **兩個資料日並存要明講**：`market_daily.date` ≠ 最上層 `date` 時，說明列會指出頂列那個是全檔
    基準日、本區塊另以自己的資料日為準（比照 CLAUDE.md 個股摘要側欄「每段自帶自己的資料日」）。

- **第六軸：整表不可用時，頂列徽章不得把它報成正常涵蓋**（2026-09-09 補；修完第五軸後主動自查找到）。
  舊版 `renderStats()` 的 `mychg` 分支自己算 `(md.rows||[]).length`，與內文的健康度判斷各寫一份，
  於是**同一個畫面自相矛盾**：`cols` 形狀不符時徽章顯示「資料日 2026-09-08 · **2757 檔涵蓋**」，
  內文卻是「無法取得異動資料」（三種殘缺情境 Playwright 實測皆如此）——**把一份本 tab 根本用不了的
  資料呈現成正常涵蓋**，與前五軸同型。修法：健康度抽成唯一事實來源 `myChgUnusable(md)`
  （grep `function myChgUnusable`），徽章與內文共用；徽章逐字沿用「無法取得異動資料」、成因放
  `title`，**刻意不上色**（不新增判級語意）。**改健康度判準只需要改那一支**。

- **股名對照在本 tab 是刻意不完整的——說明列只講「查不到就顯示代號」，沒講成因**
  （2026-09-09 補；獨立驗收提出，判定為「文案字面成立但資訊不足」。**本批只補文件、不改畫面字串**）。
  `stkName()`（grep `function stkName`）的名稱來源優先序是 `BK_NM` → `state.diag` → `state.screen`
  → `state.aetf`，但**後三者各由自己 tab 的 `ensure*()` 載入，在「持股異動」tab 一律沒載**，
  所以本 tab 實際只剩 `BK_NM` 一條路。`BK_NM`（grep `function buildBkNm`）只從 `state.pm` 的
  `oddlot.intraday`／`oddlot.after`／`lending` 三張表建，**涵蓋不到 `market_daily` 的全部代號**
  ——實查 `1456 怡華`／`1259 安心`／`2330 台積電`／`00637L 元大滬深300正2` 查得到名稱，
  `1293`／`1269`／`020025` 查不到、畫面顯示為代號。
  **這是「零新增網路請求」硬約束的必然代價，不是 bug**：要補齊得多抓一份 `TaiwanStockInfo` 或
  `meta.json`，那會直接違反本 tab 的核心承諾——**不得為了補股名而新增任何網路請求**。
  - **下列比值是量級參考、不是實測涵蓋率**：本機 `data/postmkt.json`（資料日 2026-09-08，
    **該版尚無 `market_daily` 區塊**）建出的 `BK_NM` 有 2,284 個代號；上文那個約 2,757 列的
    `market_daily` 來自線上 `44ef7e7`（資料日 2026-09-08）。**兩者是不同檔案版本**，相除得到的
    約 83% 只能當量級看，**沒有在同一份資料上實測過**，引用時要標明。
  - 若日後要讓文案更誠實，正確做法是**改說明列文字**（例如講明對照表只涵蓋零股／借券出現過的
    代號），屬畫面變更、需另案處理；**不得**改成暗示「查不到＝該檔沒有名稱」。

### 輪動雷達 tab（2026-08-11 上線）

- **口徑（第二階段定案，不得單方更改）**：B-ew＝價格版 RRG × 等權報酬。X 軸 RS-Ratio＝
  鏈等權報酬指數 ÷ 大盤等權報酬指數（RS）再做 12 日窗 z-score（100＋標準差倍數）；
  Y 軸 RS-Momentum＝RS-Ratio 的 10 日 ROC 再做同法 z-score。象限 100/100 分界、不做中位置中，
  右上起順時針＝領先／轉弱／落後／改善。候補清單（改善＝「資金剛輪入」、領先＝「相對強度領先」）
  套持續性 N=3（連續 3 日在該象限才列入），完整列出不設上限。
- **候補清單的排序鍵與標籤（不屬第二階段定案枚舉項）**：taiwan-flow-live-v2
  `backtest/report_chain_overlap.md` §5.4 明列的第二階段定案是「B-ew、K/n=12、L/k=10、N=3、
  只當狀態描述不當買賣訊號」五項，**排序鍵與 UI 標籤不在其中**，故 2026-08-30 的調整不落在
  上一條「不得單方更改」的範圍內。**排序鍵兩份清單不同**：改善＝RS-Momentum 遞減
  （要的就是變化率）；領先＝**RS-Ratio 遞減**（2026-08-30 由 RS-Momentum 改，該清單語意上
  要的是相對強度的水準——這是改動的主要依據），同日 UI 標籤亦由「動能領先」更名為
  「相對強度領先」以與排序一致。回測旁證見同報告 §2.5（§5.3 複述）：RS-Momentum 水準排序
  六種切法 6/6 為負（平均 -0.238%）、RS-Ratio 水準 6/6 為正（平均 +0.156%）；但該節自陳
  「分塊 CI 不跨 0 的格子數：0 / 12」、§5.3 引註自陳「本檔沒有證明『反著做會賺』」，
  屬方向線索而非顯著證據。**且有類比落差**：§2.5 量的是「全 47 條鏈橫斷面排序、取前後 20%」
  的 T+3 多空價差，本清單則是「先過 N=3 持續性、只留領先象限的鏈，再排序」，兩者不是同一個
  構造，該節的 +0.156% 不能直接推到象限內排序。
- **公式正本**：taiwan-flow-live-v2 `backtest/run_rrg_daily_axes.py` 的 `axis_systems`
  （`price_coords` 分支）。前端 `index.html` 的 `RRGD-PURE` 註解區塊逐式重現（含 `cum_index`
  開頭缺值當 0／中間缺值截斷、樣本標準差 ddof=1、SD=0 回 null 等細節），改公式必須兩邊同步
  並重跑對拍（抽 3 日期 × 47 鏈，(x,y) 誤差 <1e-6；2026-08-11 實測最大誤差 5.7e-14）。
- **文案紀律**：該專案回測結論為前瞻超額六種切法 0/12 顯著——資料不支持任何買賣建議，
  全 tab 描述語氣；頁尾固定附回測依據句、成員重疊揭露（一塊錢平均被算進 2.24 條鏈；
  14 條鏈成交額 100% 來自同時屬於其他鏈的成員）與「盤中版 →」互連（兩者軸定義不同）。
- **前端**：插入式改動，命名全用 `rrgd*` 前綴——`TABS`／`SUBS`／`state`（rrgd/rrgdErr/
  rrgdLoading/rrgdIdx）／`render()` 分派／`renderStats()` 各一處；`ensureChainDaily()` 懶載
  （比照 `ensureMktbal()`，594KB 不進首屏），載入後 `rrgdPrep()` 驗格式＋算好座標放模組層
  `RRGD` 快取，格式異常 throw 走 `rrgdErr` 降級文案（fetch 失敗同路徑），不壞其他 tab。
  畫布為純 SVG 字串（`rrgdSvg()`，零外部依賴），880px 單欄圖上清單下。日期選擇：
  `#rrgdSel` 下拉（change 委派）＋ `data-rrgdstep` 前後鍵（click 委派），只列可算出座標的
  日期（`valid_idx` 同式：當日至少半數鏈有座標）。新鮮度：`rrgdLagDays()` 以平日粗略計，
  落後今日 >3 平日顯示「資料未更新」（上游＝v2 baseline 班掛的增量更新，斷了這裡看得出來）。
- **標名碰撞避讓（2026-08-30）**：錨點與加選鏈的標名改走候選位搜尋——每點一圈 8 個候選位、
  撞光再跑外三圈（共 32 個），取第一個「與已放置標籤零重疊」處；32 個全撞則放在**加權重疊
  面積最小**處（不省略標籤，錨點與加選都是使用者主動要看的），32 個全出界才夾回畫布內。
  佔位權重＝當日成交額（正規化 0~100），優先序＝**加選鏈 → 錨點（成交額遞減）**。
  演算法移植自 taiwan-flow-live-v2 `index.html` 的 `ovRrgHtml` 標籤段；因頭點半徑語意
  （本頁固定 r=5、盤中版是可變泡泡半徑）與強制標名族群定義（本頁＝加選＋錨點）不同，
  兩邊**不登記為跨站同步函式**，只在各自程式碼加互相引用註解。
  離線量測（264 個可顯示交易日 × 15 個標籤＝3,960 個，加選固定取當日成交額第 11~15 名）：
  重疊配對 **719 → 0**、有重疊的標籤佔比 **28.2% → 0%**、跑出畫布 **31 → 0**；
  83.6% 的標籤位置與改動前逐位元相同、99.6% 落在第一圈，加權疊放的 fallback 未曾觸發。
- **未解／待觀察**：新鮮度以平日近似、國定假日連假可能誤報 1-2 日（與「日期」tab 的
  `dayDiff` 同一已知近似）。

### 大盤餘額 tab（2026-07-19 上線）

- **口徑**：融資餘額/融券餘額直接取 FinMind 該 dataset 的 TodayBalance；借券賣出餘額＝
  TWSE TWT72U 的 SLB＋NLB「整體市場」合計列相加（兩個獨立借券管道、彼此不重疊）；
  不限用途款項借貸餘額＝TWTA1U 六個 selectType（X/A/F/G/B/I）「證券商不限用途款項
  借貸／今日餘額」欄逐列加總，欄位位置從回傳 `groups` metadata 動態定位（6類別欄位配置
  不同，不可假設固定 index）。
- **抽核紀錄（2026-07-17，獨立於程式碼之外直接打即時 API 核對）**：FinMind
  margin_shares=9,348,875／margin_money=587,962,513,000／short_shares=236,300 全一致；
  TWT72U SLB 16,910,017,000股/2,718,883,468,980元＋NLB 13,331,897,000股/742,675,370,680元
  ＝30,241,914,000股/3,461,558,839,660元，與 sbl_short_shares/sbl_short_value 一致；
  TWTA1U 六類別加總 16,092,652（仟股），與 unrestricted_shares 一致。
- **已知教訓**：backfill 對 TWSE 端點是逐日高頻查詢（每日2+6次子請求 ×64個回補日），
  無節流會在約6次請求後被 TWSE IP 限流（回應變非JSON空內容），且限流後不會自動解除，
  導致近八成資料全 null——务必保留 `twseclient.throttled_get()` 的全域節流鎖與退避重試，
  不要為了「加速」拿掉。
- **前端**：`index.html` 插入式改動——`MKTBAL_PILLS`/`renderMktbal()`/`mktThead`/
  `mktCell`/`mktDiffCell` 等函式與 `renderDates()` 同樣繞過 `renderPM()`，直接掛在
  `render()` 分派（`state.tab==="mktbal"`）。年展開狀態存 `state.mktbalOpen`，
  比照 taiwan-flows 的 `ffOpen`/`ffToggle` 機制（點擊委派在 `document` 的
  `data-mktyr`/`data-mktsel`）。
- **未解／待觀察**：前端月度年列的 YoY 比較只用「該年最後一筆 vs 去年最後一筆」，
  非嚴謹交易日對齊；`mktbal.yml` 上線後首次排程觸發尚未實跑驗證（本次僅驗證
  push-paths 首推），需留意下個交易日 22:20 後產物是否正常更新。

### 持股診斷 tab（2026-07-18 兩子期上線）

- **資料流**：`src/build_diag.py`（`.github/workflows/diag.yml`，平日台北 22:10、排在
  build.yml 21:53 後）→ `data/diag/diag.json`（全市場日均成交值前 1200 檔；2026-09-06
  實測 746KB、gzip 約 165KB，原文件寫「<2.5MB」屬上限估計）＋
  `data/diag/cache.json`（增量快取；2026-07-24 起不進 git、改由 diag.yml 以
  actions/cache 跨 run 保存——快取被淘汰時管線自動全量重建，只是該晚 API 呼叫較多）。
  來源：FinMind 價量/法人/融資/借券/千張大戶/月營收/
  PER/股利公告（token 走 Actions secret；千張大戶與 PER3年百分位/除權息只能單檔查，
  採每晚上限輪替刷新 `HOLD_CAP`/`VAL_CAP`）＋ TWSE/TPEx 處置注意 OpenAPI（免金鑰；
  TPEx 站憑證缺 SKI 需 `verify=False`）＋ v2 raw（classify/morning/us）＋本站 postmkt.json
  （券資比/當沖量 merge）。前端另即時抓 v2 `/live`（現價）與 taiwan-stock-news `news.json`
  （新聞命中，本機過濾）。本地驗證：`python src/build_diag.py --sample`（免 token）。
- **燈號規則位置**：全部集中在 `index.html` 的 `DIAG_RULES` 陣列（資料驅動條件表，
  單一定義處；聚合邏輯在 `diagLights()`）。誠實性約定：`ver`/`tag` 標「已驗證（附回測出處）
  ／描述性／交易所公告」；`addon:true`（土洋同買）為疊加條件，需另有**非系統面**綠燈
  才計入，不單獨亮綠。燈號判定是 14 條布林規則（8 紅 6 綠）的優先序：任一紅燈成立→紅；
  否則有非系統面綠燈→綠；其餘黃——無分數、無權重、無門檻。
- **隱私設計**：持股清單只存 localStorage `pm_holdings`，不進任何網路請求 payload、
  不走 gh_token 雲端。tab 內對外請求全是固定 URL 唯讀 GET（diag.json／live／news.json）。
  AI 解讀按了才呼叫 Claude，送出＝該股事實＋市場＋組合層「彙總指標」，
  **不含持股清單/股數/成本**（UI 有明示）。
- **待觀察／待辦**：TPEx 上櫃「注意股」無公開 OpenAPI 端點（2026-07 swagger 查證），
  `at` 欄僅涵蓋 TWSE，列待辦；千張大戶/估值百分位靠輪替刷新，首週資料逐晚補齊；
  燈號規則未經整體回測（僅個別訊號有站內回測出處），校準後調 `DIAG_RULES` 即可；
  盤中行為（/live 降級、即時損益）未在開盤時段實測。
- **已知限制（選股 tab）**：預估 EPS／目標價的預估日與樣本數（`est[y].date/n`、`tp.date/n`）
  自 2026-09-06 起顯示於表內儲存格第二行（原本 screen.json 已有、表內未顯示）；
  評等分布的來源樣本與 EPS 家數不同源，表內不互相換算。
- **已知限制（前端快取，2026-09-06 批次二）**：`loadJSON()` 不再對每個 URL 掛 `?t=Date.now()`
  繞過快取，改以 `fetch(url,{cache:"no-cache"})` 每次做條件請求（內容未變回 304 只傳 header；
  `index.html` 的 `FETCH_MODE` 改回 `"buster"` 即恢復舊行為）。代價：GitHub Pages 回
  `cache-control: max-age=600`，CDN 端最多可能殘留 10 分鐘舊版——**資料更新→使用者可見的實際
  延遲尚待線上實測**（本機 `python -m http.server` 只能驗 304 路徑）。`data/analyses/`
  的雲端歷史讀回（`cloudLoadHist`）是寫入後立即重讀的路徑，刻意保留 `?t=`。
- **首屏懶載與頂列（2026-09-06 批次二）**：`load()` 不再首屏抓 postmkt.json（1.6MB）／aetf／
  taiwan-flows latest.json，改 `ensurePm()`／`ensureAetf()`／`ensureTf()` 於需要的 tab 或一鍵流程
  才載；預設 tab「摘要分析」與頂列「資料日｜本站更新｜狀態」只靠 `ensurePmHead()` 讀檔頭 4KB
  （`Range: bytes=0-4095`，GitHub Pages 回 206）。狀態四值判準見 `docs/date-semantics.md` §4
  與 `index.html` `pmStatus()`（平日國定假日 22:30 後會誤判「延遲」一次，屬已知近似）。

- 前端表格框架 `tbl(cols, rows, opts)`：表頭排序（`col.sortVal` 供複合欄位給原始值）、
  分組雙列表頭（`col.g`）、加總列（`opts.totals`，sticky 在表頭下）、凍結首二欄
  （`opts.s2`）、>200 列自動虛擬捲動。sticky 相關已知坑全記在 `<style>` 區註解：
  border-collapse/`.tblbox` padding 與 overflow 裁切邊界差（sticky top/left 要設負 padding 值）、
  thead 兩列要 `<tr>` 本身 sticky、rAF 在背景分頁不觸發（量測用 setTimeout、
  虛擬捲動有 300ms 輪詢保險，背景分頁跳過）。
- TWSE 端點的「合計」市場總計列要濾掉（代號欄非 ASCII 英數），TWT72U/TWTC7U/TWT53U 都有。
- 分點查詢聚合：張數保留小數、只在顯示時捨入（先逐列 round 再加總會偏差且讓個股
  買賣超合計出現假非零）。金額顯示單位＝百萬元 1 位小數（`milF/milS`，÷1e6，僅此表用；
  2026-07-16 由原「萬元」改；排序仍用原始 `b_amt/s_amt` 未除）。
- 摘要分析：LLM 洞見機制由使用者決定用「LLM 前端即時」（見 2026-07-11 對話）；
  system prompt 強制「只描述歷史統計傾向、非投資建議、非預測、每個觀察可追溯數據」，
  符合工作區共同原則。本站是四站摘要分析的**範本站**，套用已完成（2026-07-12）：
  即時類股動態（taiwan-flow-live-v2）與新聞晨報（taiwan-stock-news）已各自新增同框架 tab；
  盤後法人動態（taiwan-flows）**不加 tab、該站零改動**，其法人資料改併入本站 insight——
  `TF_BASE` 常數（`raw.githubusercontent.com/shihpc/taiwan-flows/main/data`）、`load()`
  平行抓 `latest.json` 存 `state.tf`（失敗不擋），`insightGatherContext()` 新增
  「三大法人買賣超」段（外資買超前10/賣超前6＋台指期未平倉、投信買超前10/賣超前6，
  dlabel 跨日警告自動生效）。SYS prompt 未改。退版點：git tag `pre-insight-tab`。
- 彙總分析 tab（2026-07-12 新增，第 8 個 tab）：一鍵 3+1 呼叫（3 頁 context×每頁 1 次
  ＋Opus 彙總）。**摘要全走 Sonnet 5、彙總維持 Opus 4.8，成本考量**（2026-07-12 起改
  Sonnet 5，當時為每頁×2 次共 6 份、標籤 Sonnet5-A/B 去重；2026-08-29 起減為每頁 1 次共
  3 份，見下）。彙總 SYS 以「跨份共振優先」（N/3 份提及，`index.html` `SUM_SYS_SYNTH`）
  精粹 alpha、給方向預測與進出建議。單份失敗不中止（≥2 份成功才彙總，
  `build_summary.py` `MIN_OK_FOR_SYNTH=2`／`index.html` 手動場同門檻）。手動近 2 次存 localStorage
  `summary_manual`；自動場由 `build_summary.py`＋`summary.yml`（cron 06:23/22:47 台北觸發——提早＋錯開整點
  避開 GitHub cron 壅塞（UTC 00:00 整點延遲常達 2-3 小時），由資料齊全輪詢閘門等資料
  **2026-08-29 起：每頁 1 份（共 3 份、≥2 份成功才彙總、共振強度 N/3），自動場摘要與彙總改走
  Message Batches（半價；am 期限 25 分／pm 180 分，超時或單筆失敗逐筆同步回退，另受全場時間預算
  折算不撞 workflow timeout）。費用估依官方現行價（Sonnet 5 \$2/\$10、Opus 4.8 \$5/\$25）重算約
  NT$10-12/手動次——原文案 NT$8-10 係以 6+1 次但舊價低估，非成本上升。**
  （2026-07-14 依審計改造：pm 硬等 postmkt/news晚班(>=21:00)/taiwan-flows 三源皆今日、最多 170 分，
  逾時=假日 skip；am 先硬等 morning.json 最多 150 分，通過後軟等 us.json＋news早班(>=06:00)
  最多 60 分、逾時照跑），輸出 `data/summary/YYYYMMDD-{am|pm}.json` 保留近 3 日，前端列表點閱。
  **假日/颱風假**（2026-07-12 補強）：閘門進場先查 TWSE 休市行事曆 API（免金鑰）擋排定
  假日——am 場必須靠這層（晨報管線假日仍會更新 generated_at，資料閘門擋不住）；行事曆
  混有「開始交易日」等交易日標記，過濾規則見 `is_twse_holiday()` 註解；API 失敗
  fail-open 續走資料閘門。颱風假等臨時停市無盤前可查來源：pm 場由 postmkt.json `date`
  回退機制天然防住；am 場會誤跑一次（約 NT$9、每年 2-4 次），屬已評估接受的殘餘風險。
  **維護重點**：三站 gather 邏輯在本 repo 有兩份移植副本（index.html 的 sumCtx* 與
  build_summary.py 的 gather_*），三站前端 insightGatherContext/SYS 改動時需同步兩處
  （SYS 已驗逐字一致）。自動場需 repo Secret `ANTHROPIC_API_KEY`（見部署設定）。
  **2026-07-16 修（pm 晚場永久缺存檔根因）**：pm 閘門的 `news_fresh` 原硬性要求新聞
  `generated_at` 為「同日且台北 ≥21:00」，但新聞晚班常因觸發延遲跨過台北午夜才落地
  （generated_at 滾成隔日 00:1x、hour=0），兩條件同破且跨日後永久失敗 → pm 場天天 skip、
  `data/summary/*-pm.json` 從未產出。修法＝`news_fresh` 加 `next_day_before` 參數，pm 呼叫
  傳 `5`：額外接受「隔日 00:00~05:00 前」的晚班（該時窗無別班次，可安全視為前一交易日晚班）；
  am 場未帶新參數、行為不變。**跨 repo 依賴**：真正讓新聞跨午夜的是 `taiwan-stock-news`
  的備援 schedule（原台北 22:37，被 GitHub cron 延遲到 00:17 覆蓋掉 Worker 22:07 已寫好的
  22:18 好資料）——已同步把該備援前挪到 21:37（`build-news.yml`，2026-07-16），使延遲也不跨
  午夜、不覆蓋。新聞晚班主觸發是 taiwan-flow-live-v2 Worker 每小時 :07 的 workflow_dispatch
  （準點、最後一班台北 22:07），schedule 僅備援。兩處互補：Worker 保正常、閘門放寬當最終防線。
  注意此修只影響未來場次，歷史缺的 pm 場不回填（要補需手動 workflow_dispatch）。
- 個股外連＋雲端儲存（2026-07-12）：三站（本站/taiwan-flow-live-v2/taiwan-stock-news）insight
  渲染＋本站彙總渲染中，個股代號自動變連結外開 Yahoo 技術分析頁。`linkifyStocks(html, knownSet)`
  雙層防誤連：各站 `stockCodeSet()` 收集已知代號＋型態兜底（代號緊跟中文、單位黑名單、
  「元大/元太」例外），tag 切分不破壞 HTML。分析結果自動存本 repo `data/analyses/`
  （`insight-{postmkt|live|news}-YYYYMMDD.json`／`summary-manual-YYYYMMDD.json`，當日陣列、
  單日上限10筆，保留近3日由 build_summary.py 清理段順手刪）。寫入靠 localStorage `gh_token`
  （三站同 origin 共用，未設靜默跳過）；讀取免 token——彙總 tab「雲端歷史（近3日）」列 4 種檔、
  v2/news 各列自站，raw CDN 約 5 分快取。**維護點**：`linkifyStocks`/`ghSaveAnalysis` 三站逐字一致，改動需三站同步。
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
   費用參考：自動雙場 × 約 22 交易日 ≈ NT$350-450/月（摘要用 Sonnet 5、彙總用 Opus 4.8；
   Sonnet 5 介紹價 input $2/output $10 per MTok 至 2026-08-31，之後恢復 $3/$15、月費略升），
   計入該 key 的 Anthropic 帳戶。**此數字為介紹價時期估算**，未反映 2026-08-29 起自動場
   摘要與彙總改走 Message Batches（半價）及每頁 1 份摘要（原 6 份）的變動，待實際用量重估。
2. **GitHub Pages**：Settings → Pages → Source 選 `Deploy from a branch`，
   Branch 選 `main` / `(root)` → Save。
3. （可選）Actions tab 手動跑一次 `build postmkt data` 產生第一份資料。
4. （可選）GitHub Fine-grained PAT：Settings → Developer settings → Fine-grained tokens，
   只勾本 repo、權限 Contents Read/Write，貼進頁面 `gh_token` 欄（三站設一次即可），
   供分析結果雲端儲存；不設不影響其他功能。

## 本機開發

```bash
pip install -r requirements.txt
FINMIND_TOKEN=xxx python build_postmkt.py
python -m http.server 8000   # 開 http://localhost:8000
```
