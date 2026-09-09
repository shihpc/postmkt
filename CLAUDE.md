# CLAUDE.md — postmkt 接手速覽

<!-- CANON:BEGIN v1 -->
<!-- 唯一事實來源＝shihpc/claude-harness 的 CANON.md。以下區塊在家族各 repo 的 CLAUDE.md 頂端
     有 byte-identical 逐字副本，由各 repo 的 .github/workflows/canon.yml 守門（比對 sha256）。
     改動流程：先改 claude-harness/CANON.md → 跑 tools/sync_canon.py 同步全部副本 → 更新守門 hash。
     **repo 名單以 tools/sync_canon.py 的 TARGET_REPOS 為準，此處刻意不寫死數量**——
     數量已改過兩次（五→六→七），每改一次就得動全部 repo 的 CLAUDE.md 與守門 hash。
     不要只改單一 repo，CI 會擋下來。 -->

## 通用工作鐵律（家族各 repo 逐字相同，勿單獨修改）

1. **機密**：token／金鑰只存在不受版控的本機設定或受控 secrets（`.env`／Actions secret／
   `wrangler secret`），絕不寫進會 commit 的檔案、log 或對話輸出。commit 前掃 staged 內容，
   **只回報檔名／行號／類型、不把可疑字串原文印出來**；`sk-ant-`／`ghp_`／`eyJ` 是線索不是全集。
2. **指揮官不下場**：掃 repo、通讀 >300 行的檔、一次讀 >3 個檔、查網頁研究、批次改檔、
   驗收改過的東西——這六類一律派 subagent，主對話只收結論＋`檔案:行號`；但 subagent 回報
   **不等於事實**，主對話為核對結論可直接查原始證據。雲端 session 的 subagent 派工（含第 3 條
   驗收）已獲常備授權，需要時直接派，不需逐次詢問。
3. **先寫驗收條件再動手**：動手前先寫下目標專案完整路徑＋怎樣算完成＋怎麼驗。修改者先自測，
   再派 fresh-context subagent 驗收——**改東西的 agent（含主對話自己）不得擔任驗收者**。
   驗收要綁**確切 commit／產物版本**；驗收後又改動，受影響部分要重驗。
4. **不確定不亂說**：陳述事實（尤其技術細節、數字、外部服務的限制與行為）要嘛附佐證（官方
   文件、實測、`檔案:行號`），要嘛明說「這點我不確定，需要查證」，不可憑印象當確定講。區分
   「已驗證事實」與「推測」，推測要標明；**`檔案:行號` 只證明程式這樣寫，不證明線上這樣跑**。
5. **一次只做一件事**：聚焦一個明確目標，完成該目標必要的修改、測試與整合；不擅自加入無關
   重構或延伸功能。範圍外問題簡短記錄、不自行擴張任務。
6. **完成的定義**：驗收條件逐條打勾＋fresh-context subagent 驗過＋產物在使用者拿得到的位置，
   並明示已完成與未完成；**可執行的東西沒實跑過不算完成**（純文件交付以內容與結構檢查為準）。
   涉及部署者另需 push＋部署 workflow 成功＋在**實際服務的位置**驗證本次變更（線上頁面／API／
   資料時戳）——**raw URL 只證明原始碼進了 repo，不證明線上跑的是該版本**，200 也不等於功能正確。
7. **push 前**：先確認目前分支與推送目標，`git fetch` 後檢查遠端是否領先，非空必須先看內容
   （訊息／時間戳／diff）。一般 push → rebase 整合（本專案既定政策），嚴禁直接覆蓋；force push
   前若遠端領先的 commit 是真實新工作 → 停下來問，且一律用 `--force-with-lease=<ref>:<預期 SHA>`；
   授權「這次 force push」不等於授權蓋掉遠端所有領先 commit。
8. **新指標／訊號若會影響投資方向、候選排序、進出場或風險判定，先問有沒有回測依據**，沒有就
   先驗證再上線；純描述性顯示（欄位、日期、圖示）只需驗算式正確。市場內容可做情境判讀與多空
   因素分析，可研判市場與大眾情緒對該數值或新聞的可能反應，並可提供具體個股／標的的買賣建議
   與進出點位；以上均須附依據、區分事實與推論，並標明屬 AI 研判而非保證。
9. **語言**：對話與文件用繁體中文；程式碼註解可中文，identifier 用英文；外部原文、API 名稱、
   指令與錯誤訊息保留原樣。

> 判準細則、派工模板、教訓簿見 `shihpc/claude-harness`（private）。雲端 session 需 add_repo 才讀得到。
<!-- CANON:END v1 -->

台股盤後靜態儀表板：**單一 `index.html`（無 build 工具，這是刻意的專案定位，勿拆檔）**
＋ 4 支 Python 管線 ＋ GitHub Actions 排程產資料進 `data/`，GitHub Pages 從 main root 服務。
詳細架構與各 tab 口徑見 README.md；歷次變更見 CHANGELOG.md；日期欄語意見 docs/date-semantics.md。

## 佈局

- `index.html`：14 個 tab 全部前端（CSS/JS 內嵌）。`render()` 分派各 tab；共用表格框架 `tbl()`
  （排序/分組表頭/凍結欄/虛擬捲動，sticky 的坑記在 `<style>` 註解）。
  - **hash 路由（2026-09-07）**：`#tab=&code=&sub=`，只放非預設值。`parseHash()`／`applyHash()`
    （grep `function parseHash`／`function applyHash`）於 `load()` 套用，`syncHash()`
    （grep `function syncHash`）掛在 `render()` 結尾以 `history.replaceState` 寫回
    （**不塞歷史、不觸發 hashchange**），外部改網址走 `hashchange`
    （grep `addEventListener("hashchange"`）。讀入一律白名單＋型別檢查，非法值靜默退回預設。
    **唯一刻意例外（2026-09-09）**：「持股異動」列點個股跳「持股診斷」走 `location.hash = …`
    ——**全站唯一的「賦值」是它**。位置＝`renderMyChg()` **之後**那個 document 級委派 listener
    ——錨點 grep `closest(".clk[data-mychg]")`，在 `index.html` **2 處**：hash 路由那段的說明
    註解 1 處＋實作 1 處。**它不在 `myChgHtml()` 內**（`myChgHtml()` 只吐出帶 `data-mychg`
    屬性的字串，2026-09-09 更正原本寫錯的位置）。但
    `grep 'location.hash = '` 在 `index.html` 有 **3 處命中**（兩行註解＋這一處賦值）：
    **「唯一賦值」為真、「唯一命中」為假**，兩者不可混講。同理 `grep data-mychg` 在
    `index.html` 有 **5 處**（不是 4）：註解 3 行（其中一行就是 `index.html` 自己那句
    「則有 4 處」的宣稱——**宣稱句本身也算一次命中**，那正是上一版少算的那一次）
    ＋`myChgHtml()` 表格欄的屬性＋handler 的 `closest(".clk[data-mychg]")`。
    **`index.html` 那兩行註解仍寫舊數字，屬程式檔註解、本批不動**（見 CHANGELOG 待辦）。
    此處**會塞一筆歷史**——那是使用者主動的下鑽導覽、不是 `render()`
    的狀態寫回，Back 要能退回持股異動。除此之外全站 hash 寫出一律 `replaceState`。
  - **個股摘要側欄（2026-09-07 批次三 #15 後半）**：`index.html` grep `// ---------- 個股摘要側欄`
    起，至該節末尾兩個 document 級 listener（`[data-stk]` 委派點擊與 grep `Escape" && state.stkOpen`
    的 ESC 關閉）止。代號旁 `▤` 鈕（grep `const stkBtn`，掛在共用 `nameCell`（grep `const nameCell`）、
    選股 tab 代號欄、分點「單點」結果的名稱欄、持股診斷卡標題）開側欄；`renderStockDrawer()`／
    `stkOpen()`／`stkClose()`（grep `function renderStockDrawer`／`function stkOpen`／
    `function stkClose`），DOM 是 `.wrap` 外的 `#stkMask`／`#stkPanel`
    （grep `id="stkMask"`／`id="stkPanel"`，position:fixed）。
    **硬約束：開側欄不發任何網路請求**——只讀已在記憶體的 `state.pm`／`diag`／`screen`／`aetf`／
    `diagLive`，未載入的資料集整段不出現；`stkOpen()` 刻意只呼叫 `renderStockDrawer()` 而非
    `render()`（後者會替當前 tab 觸發 `ensure*()`）。**每段自帶自己的資料日**（`stkSec()`），
    因為各 dataset 的 date 本來就會不同（見 `date_mismatch`）。跨站一律純導覽 `<a target="_blank"
    rel="noopener">`，**不 fetch → 不需新增 CSP `connect-src`**；深連結只用實查確認支援的格式
    （grep `function stkSecLinks`）：taiwan-stock-news `#tab=track&code=`／`#tab=news&q=` 可用，
    **taiwan-flows 與 taiwan-flow-live-v2 沒有 hash 路由**（2026-09-07 curl 線上 index.html
    grep `location.hash` 零命中），只連首頁並在說明列註明需自行搜尋，不得編造深連結格式。
    hash key 用 **`stock=`**（處理該 key 的三行 grep `q.get("stock")`／`state.stkOpen = h.stock`／
    `p.push("stock="`，分別位於 `parseHash`／`applyHash`／`currentHash` 內），
    **刻意與 `code=` 分家**——`code=` 已被 lending／broker／diag 三個 tab 各自佔用，側欄跨 tab 都能開；
    兩者可並存。ESC 與點遮罩關閉、走 `history.replaceState` 不塞歷史。持股清單不進 hash（約定 6 不變）。
  - **持股異動 tab（2026-09-09）**：`index.html` grep `function myChgHtml`／`function renderMyChg`／
    `const MYCHG_MIN_ROWS`（**裸名 `MYCHG_MIN_ROWS` 有 4 處命中，宣告式才唯一**）／
    `function myChgDateInfo`。資料源＝`state.pm.market_daily`（走既有 `ensurePm()`，
    **零新增網路請求**，持股代號不進任何 URL／header／body——畫面承諾只能寫「持股代號不進任何網路
    請求」，**不可寫「本 tab 不發任何網路請求」**，`ensurePm()` 自己就會抓 `data/postmkt.json`）。
    **六種「說錯話」不可混講**（正本＝README「前端消費 `market_daily` 的必要條件」的六軸，
    與 `index.html` 該段註解的 ①–⑥ 是**同一組六項**：三方的**集合**必須一致，
    **序號則尚未對齊**——`index.html` 的 ③④ 與 README 的軸3／軸4 順序互換，
    屬敘述性差異、不影響判準，列在 CHANGELOG「待下批同步」，統一時以 README 的軸序為準）：
    本表不涵蓋（權證／偽代號，**不可說成「查無此代號」**）／該資料日法人資料未到（`f`／`t` 為
    `null`，不得讀成 0；**同列 `chg` 只有在它自己不是 `null` 時才仍然有效**——`chg` 也可能是
    `null`，**不得無條件宣稱「同列漲跌% 仍然有效」**）／該資料日完全沒有資料（`chg`／`f`／`t`
    三欄全 `null`，**不是**「未達門檻」）／**整表殘缺**（`rows` 空或 <2000 列）整段顯示
    「無法取得異動資料」、**不得逐檔說成「查無此代號」**、也不得靜默當成沒有異動／
    **資料日不是「今天」**（第五軸）／**整表不可用時頂列徽章不得報成「N 檔涵蓋」**
    （第六軸；徽章與內文共用 `myChgUnusable()`）。
    **「查無此代號」不另計為一軸**：它是第一軸與整表殘缺軸的**對照項**（代號在涵蓋範圍內、
    確實不在 `rows` 裡才是它），三方都把它寫成「不可說錯成這個」而不是獨立一軸——
    `index.html` 的 ①③④ 與 README 的軸1／軸4 皆然。
    （**2026-09-09 二次更正**：`26e3a73` 那版把「查無此代號」提成六項之一、又把「整表殘缺」
    踢出六軸另立一層，與 `index.html` ③ 和 README「前四軸／另外三軸」直接相反，
    把原本三方一致的清單改成互相矛盾，本批已改回。教訓見 CHANGELOG。）
    資料日徽章取 **`market_daily.date`，不是 `pm.date`**（前者＝價格／借券資料日，後者＝全檔基準日，
    線上實測系統性差一天）。**第五軸（2026-09-09）**：畫面主語一律寫出實際日期，
    **不得用「今天／今日／當日」代稱**；落後 ≥`MYCHG_STALE_LAG`（2）個交易日、晚於今日或缺失時
    另出一段與免責卡同重量的說明，且**不新增紅黃綠判級**。比照個股摘要側欄「每段自帶自己的資料日」。
    **股名在本 tab 刻意不完整**：`stkName()` 的 `diag`／`screen`／`aetf` 三個來源在本 tab 都沒載，
    只剩 `BK_NM`（只由 `oddlot`／`lending` 三張表建），查不到就顯示代號——那是「零新增網路請求」的
    代價，**不得為了補股名而新增請求**；細節與量級見 README 同節。
  - **持股清單匯出／匯入／清除（2026-09-07）**：`holdExportPayload`／`holdParseImport`／
    `holdExport`／`holdImportFile`（grep `const HOLD_SCHEMA` 起至 `async function holdImportFile`
    該函式結尾止）。**仍只走 localStorage `pm_holdings` 與使用者本機檔案，不進任何網路 payload**
    （約定 6 不變）；匯入走 `holdParseImport`
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
   （`index.html` grep `// ---- 本次費用估算` 起至 `function insightCostText` 該函式結尾止）三站亦為
   逐字副本，改價或改算式需三站同步。
   **另有一組「四站同步但非逐字」的 `loadSiteVer()`＋footer `#siteVer`**（`index.html` grep
   `async function loadSiteVer`／`id="siteVer"`）：postmkt／taiwan-flow-live-v2／taiwan-flows／
   taiwan-stock-news 四站都有
   （入口站 shihpc.github.io 沒有），刻意不同的三處＝①各站打自己 repo 的 commits 端點
   ②sessionStorage key 各站獨立（`pm_site_ver`／`tf2_site_ver`／`tf_site_ver`／`news_site_ver`）
   ③時間格式 postmkt 走 `fmtGenTaipei`、另三站內嵌 `toLocaleString("sv-SE")`。
   改行為要四站一起改，但**不要**強求逐字。它帶來一個對外依賴
   `api.github.com/repos/shihpc/<repo>/commits/main`（免金鑰、限 60 req/hr/IP，失敗或超限
   一律靜默隱藏版本列）；本站 CSP 的 `connect-src` 早已含 `https://api.github.com`
   （`index.html` grep `Content-Security-Policy`），無須再加，其餘三站無 CSP meta。
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
python -m http.server 8000        # 前端本機驗證；慣例＝14 個 tab 逐一點擊 console 零 error
ruff check .                      # lint（設定在 pyproject.toml）
```

改前端後務必實測 14 tab 零 console error（歷次都這樣驗）；改 gather/SYS 後記得跨站同步檢查。

**手機驗收條件（2026-09-09 更正，舊寫法已被實測推翻）**：375／390／1280 三寬度下
①**整頁 `document.documentElement.scrollWidth == window.innerWidth`**（無**頁面級**水平捲軸）、
②表格各欄**全部可見、無文字裁切（逐格 `scrollWidth - clientWidth == 0`）、無換行**。
**不得宣稱 `.tblbox` 的 `scrollWidth == clientWidth`**——`.mtable` 是 `width:100%`＋`nowrap`，
壓到 min-content 之後由 `.tblbox` 的 `overflow:auto` 吸收，「持股異動」在 **375px ＋ 6 位數張數**
時實測會溢出數 px（依股名長度而動，本批量到 6px）。那不影響可見性：`.tblbox` 的裁切邊界是
**padding box**，溢出量落在其 **12px 右內距**內，不捲動也完整看得到。
數據、量法與「刻意不修」的決定見 CHANGELOG「（同日修正之五）手機驗收條件更正」節。
