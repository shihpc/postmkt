# CLAUDE.md — postmkt 接手速覽

<!-- CANON:BEGIN v1 -->
<!-- 唯一事實來源＝shihpc/claude-harness 的 CANON.md。以下區塊在五個 repo 的 CLAUDE.md 頂端
     有 byte-identical 逐字副本，由各 repo 的 .github/workflows/canon.yml 守門（比對 sha256）。
     改動流程：先改 claude-harness/CANON.md → 跑 tools/sync_canon.py 同步五份 → 更新守門 hash。
     不要只改單一 repo，CI 會擋下來。 -->

## 通用工作鐵律（五個 repo 逐字相同，勿單獨修改）

1. **機密**：token／金鑰一律走 `.env` 或 Actions secret，絕不寫進任何會 commit 的檔案、log 或
   對話輸出。commit 前用 `git diff --staged` 檢查有無夾帶金鑰樣式字串（`sk-ant-`、`ghp_`、`eyJ` 開頭）。
2. **指揮官不下場**：掃 repo、通讀 >300 行的檔、一次讀 >3 個檔、查網頁研究、批次改檔、
   驗收改過的東西——這六類一律派 subagent，主對話只收結論＋`檔案:行號`。
   雲端 session 的 subagent 派工（含第 3 條驗收）已獲常備授權，需要時直接派，不需逐次詢問。
3. **先寫驗收條件再動手**：動手前先寫下目標專案完整路徑＋怎樣算完成＋怎麼驗。改完派
   fresh-context subagent 驗收——**改東西的 agent（含主對話自己）不得擔任驗收者**。
4. **不確定不亂說**：陳述事實（尤其技術細節、數字、外部服務的限制與行為）要嘛附佐證（官方
   文件、實測、`檔案:行號`），要嘛明說「這點我不確定，需要查證」，不可憑印象當確定講。
   區分「已驗證事實」與「推測」，推測要標明。
5. **一次只做一件事**：只做明確要求的那件事，做完給簡短結果；少主動丟一堆延伸提案。
6. **完成的定義**：驗收條件逐條打勾＋fresh-context subagent 驗過＋產物在使用者拿得到的位置。
   **沒實跑過不算完成**。涉及部署者另需 push＋部署 workflow 成功＋**線上驗證本次變更的具體內容**
   （破快取 raw URL／curl／瀏覽器實查），只寫在本機不算完成。
7. **push 前**：先 `git fetch`；`git log --oneline main..origin/main` 非空必須先看內容（訊息／
   時間戳／diff）。一般 push → rebase 整合，嚴禁直接覆蓋；force push 前若 origin 領先的 commit
   是真實新工作 → 停下來問，授權「這次 force push」不等於授權蓋掉 origin 所有領先 commit。
8. **新指標／訊號先問有沒有回測依據**，沒有就先驗證再上線。市場內容可做情境判讀與多空
   因素分析，可研判市場與大眾情緒對該數值或新聞的可能反應，並可提供具體個股／標的的
   買賣建議與進出點位；以上均須附依據、區分事實與推論，並標明屬 AI 研判而非保證。
9. **語言**：對話與文件用繁體中文；程式碼註解可中文，identifier 用英文。

> 判準細則、派工模板、教訓簿見 `shihpc/claude-harness`（private）。雲端 session 需 add_repo 才讀得到。
<!-- CANON:END v1 -->

台股盤後靜態儀表板：**單一 `index.html`（無 build 工具，這是刻意的專案定位，勿拆檔）**
＋ 4 支 Python 管線 ＋ GitHub Actions 排程產資料進 `data/`，GitHub Pages 從 main root 服務。
詳細架構與各 tab 口徑見 README.md；歷次變更見 CHANGELOG.md；日期欄語意見 docs/date-semantics.md。

## 佈局

- `index.html`：13 個 tab 全部前端（CSS/JS 內嵌）。`render()` 分派各 tab；共用表格框架 `tbl()`
  （排序/分組表頭/凍結欄/虛擬捲動，sticky 的坑記在 `<style>` 註解）。
  - **hash 路由（2026-09-07）**：`#tab=&code=&sub=`，只放非預設值。`parseHash()`／`applyHash()`
    （`:358`／`:371`）於 `load()` 套用，`syncHash()`（`:405`）掛在 `render()` 結尾以
    `history.replaceState` 寫回（**不塞歷史、不觸發 hashchange**），外部改網址走
    `hashchange`（`:410`）。讀入一律白名單＋型別檢查，非法值靜默退回預設。
  - **個股摘要側欄（2026-09-07 批次三 #15 後半）**：`index.html:3634-3872`。代號旁 `▤` 鈕
    （`stkBtn`／`:3658`，掛在共用 `nameCell`／`:473`、選股 tab 代號欄、分點「單點」結果的名稱欄、
    持股診斷卡標題）開側欄；`renderStockDrawer()`（`:3845`）／`stkOpen()`（`:3856`）／
    `stkClose()`（`:3865`），DOM 是 `.wrap` 外的 `#stkMask`／`#stkPanel`（`:338-339`，position:fixed）。
    **硬約束：開側欄不發任何網路請求**——只讀已在記憶體的 `state.pm`／`diag`／`screen`／`aetf`／
    `diagLive`，未載入的資料集整段不出現；`stkOpen()` 刻意只呼叫 `renderStockDrawer()` 而非
    `render()`（後者會替當前 tab 觸發 `ensure*()`）。**每段自帶自己的資料日**（`stkSec()`），
    因為各 dataset 的 date 本來就會不同（見 `date_mismatch`）。跨站一律純導覽 `<a target="_blank"
    rel="noopener">`，**不 fetch → 不需新增 CSP `connect-src`**；深連結只用實查確認支援的格式
    （`stkSecLinks`／`:3821`）：taiwan-stock-news `#tab=track&code=`／`#tab=news&q=` 可用，
    **taiwan-flows 與 taiwan-flow-live-v2 沒有 hash 路由**（2026-09-07 curl 線上 index.html
    grep `location.hash` 零命中），只連首頁並在說明列註明需自行搜尋，不得編造深連結格式。
    hash key 用 **`stock=`**（`parseHash`／`:412`、`applyHash`／`:419`、`currentHash`／`:450`），
    **刻意與 `code=` 分家**——`code=` 已被 lending／broker／diag 三個 tab 各自佔用，側欄跨 tab 都能開；
    兩者可並存。ESC 與點遮罩關閉、走 `history.replaceState` 不塞歷史。持股清單不進 hash（約定 6 不變）。
  - **持股清單匯出／匯入／清除（2026-09-07）**：`holdExportPayload`／`holdParseImport`／
    `holdExport`／`holdImportFile`（`:3025-3070`）。**仍只走 localStorage `pm_holdings`
    與使用者本機檔案，不進任何網路 payload**（約定 6 不變）；匯入走 `holdParseImport`
    的結構與型別檢查，壞檔整包拒收、不半套。
- `build_postmkt.py` → `data/postmkt.json`（主資料，五個盤後 tab）
- `build_summary.py` → `data/summary/`（AI 彙總自動場；含資料齊全輪詢閘門與假日判斷）。
  **2026-08-29 起：每頁 1 份共 3 份摘要（原 6 份）、`MIN_OK_FOR_SYNTH=2` 才彙總、共振強度口徑 N/3；
  自動場摘要與彙總改走 Anthropic Message Batches（半價，am 期限 25 分／pm 180 分，逾時或單筆
  失敗逐筆同步回退）**。`summary.yml` 另有 `workflow_dispatch` 輸入 `no_wait`（跳過資料齊全閘門，
  測試／補跑用）
- `src/build_diag.py` → `data/diag/diag.json`（持股診斷素材庫；cache.json 走 actions/cache 不進 git）
- `src/build_mktbal.py` → `data/market_balance_history.json`（大盤餘額）
- `src/build_screen.py` → `data/screen/screen.json`（選股：TradingView 初篩＋鉅亨 FactSet 預估
  EPS/目標價/評等＋diag 合併；掛在 diag workflow 後段，`continue-on-error` 失敗不擋 diag）
- 共用模組：`src/fmclient.py`（FinMind client＋token/台北時區）、`src/twseclient.py`（TWSE 節流）
- workflows：build/diag/mktbal/summary（各自 cron＋v2 Worker 哨兵 dispatch）＋ test.yml；
  commit/push 與失敗告警在 `.github/actions/` composite

## 不可破壞的約定（踩過坑的）

1. **TWSE 全域節流**：所有 TWSE HTTP 呼叫必須走 `twseclient.throttled_get()`。連發 ~6 次就被
   IP 限流且不自動解除（README「已知教訓」）。不要為了加速拿掉。
2. **三站同步函式**：`callClaude`/`mdToHtml`/`linkifyStocks`/`ghSaveAnalysis` 與 `sumCtx*`（gather）
   在 taiwan-flow-live-v2、taiwan-stock-news 有逐字副本，改動需三站同步；`build_summary.py` 的
   `gather_*` 是 index.html gather 的 Python 移植副本。SYS prompt 唯一事實來源＝index.html
   `SUM_SYS_POSTMKT`，`build_summary.py SYS_POSTMKT` 為移植複本需逐字同步。
   **第五組（2026-08-27 起）**：費用估算 `insightCostText`／`INSIGHT_PRICES`／`USD_TWD`
   （`index.html:2111-2133`）三站亦為逐字副本，改價或改算式需三站同步。
   **另有一組「四站同步但非逐字」的 `loadSiteVer()`＋footer `#siteVer`**（`index.html:260`、
   `:3430`）：postmkt／taiwan-flow-live-v2／taiwan-flows／taiwan-stock-news 四站都有
   （入口站 shihpc.github.io 沒有），刻意不同的三處＝①各站打自己 repo 的 commits 端點
   ②sessionStorage key 各站獨立（`pm_site_ver`／`tf2_site_ver`／`tf_site_ver`／`news_site_ver`）
   ③時間格式 postmkt 走 `fmtGenTaipei`、另三站內嵌 `toLocaleString("sv-SE")`。
   改行為要四站一起改，但**不要**強求逐字。它帶來一個對外依賴
   `api.github.com/repos/shihpc/<repo>/commits/main`（免金鑰、限 60 req/hr/IP，失敗或超限
   一律靜默隱藏版本列）；本站 CSP 的 `connect-src` 早已含 `https://api.github.com`
   （`index.html:10`），無須再加，其餘三站無 CSP meta。
3. **lending 衍生欄重建公式三處一致**：postmkt.json 的 lending.rows 只存基礎量＋px，
   衍生欄由 `index.html augmentLending()` 與 `build_summary.py _augment_lending()` 重建，
   改公式要同步（有 parity 測試守著）。
4. **XSS**：innerHTML 拼字串一律過 `esc()`；CSP meta 的 connect-src 白名單新增資料源時要同步。
5. **日期閘門**：`slot_trading_day`/`news_fresh`/`is_twse_holiday` 的跨午夜與民國年邏輯都是
   修過的生產事故，改動前先看 tests/test_summary_gates.py。
6. **金鑰**：FINMIND_TOKEN/ANTHROPIC_API_KEY 走 Actions secret；前端金鑰只存 localStorage，
   永不進 repo。持股清單只存 localStorage、不進任何網路 payload。
7. **外部消費者**：taiwan-flow-live-v2 的 Cloudflare Worker 會輪詢本 repo raw main 的
   postmkt.json/diag.json 來鏈式觸發下游；資料檔位置/欄位大改前先確認跨 repo 影響。

## 驗證方式

```bash
python -m pytest tests/ -q        # 離線單元測試（免 token/網路）
python src/build_diag.py --sample # diag 管線本地驗證（免 token）
python -m http.server 8000        # 前端本機驗證；慣例＝13 個 tab 逐一點擊 console 零 error
ruff check .                      # lint（設定在 pyproject.toml）
```

改前端後務必實測 13 tab 零 console error（歷次都這樣驗）；改 gather/SYS 後記得跨站同步檢查。
