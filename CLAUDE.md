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

- `index.html`：17 個 tab 全部前端（CSS/JS 內嵌；2026-09-28 由 14 加到 16，見下方「籌碼雷達／社群聲量」；2026-09-29 加第 17 個「市場情緒」，見下方同名節）。`render()` 分派各 tab；共用表格框架 `tbl()`
  （排序/分組表頭/凍結欄/虛擬捲動，sticky 的坑記在 `<style>` 註解）。
  - **hash 路由（2026-09-07）**：`#tab=&code=&sub=`（2026-09-28 另加 `rcls`／`rinv`／`sd`，僅限各自 tab，見下方籌碼雷達／社群聲量），只放非預設值。`parseHash()`／`applyHash()`
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
    `index.html` 有 **5 處**（不是 4）：註解 3 行（`:477` 「入口站改連」那句／`:490` 計數說明本身
    ——現行措辭是「`grep -o` … `wc -l` ＝ 5 處（舊版寫 4）」，**宣稱句自己也算一次命中**，
    那正是上一版少算的那一次／`:491` 拆解裡的 handler 錨點）＋`myChgHtml()` 表格欄的屬性（`:1455`）
    ＋handler 本體（`:1499`）。**引用時只寫現行措辭**——舊版那句「則有 4 處」已隨本批改寫、
    現在 grep 不到了。
    **`index.html` 那段註解的舊數字已於 2026-09-13 改正並結案**（原寫「唯一命中」與「4 處」，
    現已改成上述的 3 處／5 處，並把「怎麼數的」寫進註解；CHANGELOG 對應待辦條目同批結案）。
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
    **taiwan-flows 與 taiwan-flow-live-v2 只連首頁**，並在說明列註明需自行搜尋，不得編造深連結格式。
    **理由 2026-09-13 更正**：原寫「兩站都沒有 hash 路由（09-07 curl grep `location.hash` 零命中）」
    ——**對 taiwan-flows 是錯的**，實查 `origin/main` 得 `location.hash` **3 處**、`function parseHash`
    **1 處**（live-v2 才是兩者皆 0）。flows 的 hash 路由**就是 09-07 當天**（批次三 #15）加的，
    量測當下為真、同日即過期。真正的理由是 **flows 的 hash key 沒有逐檔代號**
    （`#tab=&mode=&d1=&d2=&side=&rank=&etype=&inv=&sec=&sub=`，`sec`／`sub` 是類股／次產業），
    所以仍給不出個股深連結。**結論不變、依據換掉**；畫面文案寫「沒有個股網址參數」本來就正確。
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
    與 `index.html` 該段註解的 ①–⑥ 是**同一組六項**：三方的**集合**與**序號**現已一致
    ——2026-09-13 以 README 的軸序為準，把 `index.html` 原本互換的 ③④ 對調回來
    （③＝三欄全 `null`、④＝整表殘缺；**六軸的規範內容一字未改，只動序號與敘述順序**），
    CHANGELOG「待下批同步」該條同批結案）：
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
    踢出六軸另立一層，與 `index.html` 的「整表殘缺」那一軸（**當時編號 ③，2026-09-13 重編號後為 ④**）
    和 README「前四軸／另外三軸」直接相反，
    把原本三方一致的清單改成互相矛盾，本批已改回。教訓見 CHANGELOG。）
    資料日徽章取 **`market_daily.date`，不是 `pm.date`**（前者＝**價格／法人資料日**，後者＝全檔基準日
    ＝`build_postmkt.py` grep `dates = [d for d in (d_margin` 那行——**七支 FinMind dataset**
    （margin／lend／short／dt／block／inst／hold）**的日期取 max，不含兩支 TWSE 零股日**
    `d_oddi`／`d_odda`；原寫「各段 date 取 max」是過寬的，2026-09-13 更正）。
    **頂列與本區塊是兩個不同的軸，刻意不統一**（2026-09-13 使用者裁決：`pmStatus` 維持用
    `pm.date`、不改程式）：頂列答的是「**這份檔整體走到哪一天**」，本區塊答的是「**這張表是哪一天**」。
    要頂列跟隨單一區塊就得挑一個區塊當代表，而本檔有 17 個 tab、各自吃不同的 dataset，
    綁 `market_daily.date` 會讓其餘 16 個 tab 的頂列變得不準（例：借券 tab 走 `lend_date`，
    法人日領先短賣日那天頂列就會比借券 tab 自己的資料日新）。所以正解是**每段自帶自己的資料日**
    （同個股摘要側欄的立場），並在兩者不同時明講，而不是把頂列改成某一段的日期。**2026-09-09 起本區塊基準日改綁法人日 `d_inst`、與借券 tab 的 `lend_date`
    脫鉤**（`build_postmkt.py` grep `md_date = d_inst or lend_date`）：原本共用 `lend_date`
    ＝`d_short or latest`，而短賣餘額是全批最慢的一支，晚場那班常落後一天，於是
    `build_market_daily()` 的「法人資料日 ≠ 基準日」守門必然觸發、**f/t 整欄變 null**
    （線上實證：generated_at `2026-09-09T20:55:42+08:00` 那版 `date_mismatch` 四項全 `2026-09-09`、
    `market_daily.date` 停在 `2026-09-08`、2,757 檔的 `f`／`t` 非 null 各 0 檔）。脫鉤後常態下
    本區塊資料日與 `pm.date` 應相同，**但仍不保證**——法人日落後、或 `d_inst` 為空退回 `lend_date`
    時兩者會不同，所以「兩個資料日並存要明講」那條不變（**脫鉤後尚無線上樣本，此段為程式碼依據**）。**第五軸（2026-09-09）**：畫面主語一律寫出實際日期，
    **不得用「今天／今日／當日」代稱**；落後 ≥`MYCHG_STALE_LAG`（2）個交易日、晚於今日或缺失時
    另出一段與免責卡同重量的說明，且**不新增紅黃綠判級**。比照個股摘要側欄「每段自帶自己的資料日」。
    **股名在本 tab 刻意不完整**：`stkName()` 的 `diag`／`screen`／`aetf` 三個來源在本 tab 都沒載，
    只剩 `BK_NM`（只由 `oddlot`／`lending` 三張表建），查不到就顯示代號——那是「零新增網路請求」的
    代價，**不得為了補股名而新增請求**；細節與量級見 README 同節。
  - **籌碼雷達 `chipradar`／社群聲量 `social`（2026-09-28 由 taiwan-flows `radar`、taiwan-stock-news `social` 搬來，
    原站已移除；驗收條件 `docs/move-radar-social.md`）**：`index.html` grep `// ================= 籌碼雷達 tab`
    與 `// ==== 社群聲量` 兩段（接在「日期 tab」之前）。**搬家不改口徑**——規格正本仍是
    `taiwan-flows/docs/radar-tab.md` 與 `taiwan-stock-news/docs/social-display.md`（含 §1b，紅綠／排行／雙確認建議／
    參考價位是使用者 2026-09-28 裁決、**未經回測**，畫面標「AI 研判，未經回測，非保證」）；純函式
    （`radarQuad`／`radarPoints`／`radarHolders`／`radarSvg` 與 `social-pure:begin`～`end` 區段）與原站逐字相同。
    **資料不搬、改讀同源相對路徑**（CSP `connect-src 'self'` 已涵蓋、未改）：`../taiwan-flows/data/sector_ranges_lite.json`
    （`CR_SECT_URL`）、`../taiwan-stock-news/data/social/`（`SOCIAL_BASE`）；大戶／價位讀本站 `data/diag/diag.json`
    ——**沿用既有 `ensureDiag()`／`state.diag`**（與持股診斷共用一份，`ensureDiag` 載完後在 diag／chipradar／social
    三個 tab 都會重繪）。副作用：先開過這兩個 tab 後，`stkName()` 的 diag 來源會變成可用（同「先開過持股診斷」）。
    **兩個 tab 的資料都只在切到該 tab 時才抓，首屏請求清單不變**。本站變成**另兩個 repo 資料檔的前端消費者**：
    taiwan-flows `sector_ranges_lite.json` 的 `windows.r5/r20.classifications`、taiwan-stock-news `data/social/*.json`
    的 schema 改名或改語意＝跨站變更。**hash 新 key**：`rcls`（`exchange`｜`chain`）／`rinv`（`total`｜`foreign`｜
    `trust`｜`dealer`）只在 `tab=chipradar` 讀寫（產業下拉不進 hash），`sd`（YYYY-MM-DD，須在非 fixture 日期清單內）
    只在 `tab=social` 讀寫；白名單在 `HASH_CR`／`HASH_SD_RE`，非法值靜默丟棄。搬來時為避撞名改的東西：`tbl()` 多了
    選填 opts `sortI`／`sortD`／`tie`（不帶時行為逐字不變）、CSS 一律 `.cr-*`／`.soc-*` 前綴、原站 `.row/.lbl/.chip/.meta/.tblwrap`
    → `.soc-row/.soc-lbl/.soc-chip/.soc-meta/.soc-tblwrap`。大戶兩表在本站版心（880px）改上下疊放（原站並排）。手機窄寬（≤480px）為滿足下方手機驗收條件②改藏次要欄、關鍵欄全留：大戶表藏產業／外資5日張／投信5日張（外資／投信改成名稱下方兩行小字 `.cr-nw`），社群表藏推／噓／作者態度分布（點代號展開的依據段仍列出）、股名併入代號欄第二行（`.soc-nm2`）；量測見 docs/move-radar-social.md §3。
    測試：`tests/test_chipradar.mjs`（17 項，pytest 由 `tests/test_frontend_moved.py` 代跑，上半用
    `tests/fixtures/chipradar_sector_ranges_r5r20.json` 快照）、`tests/test_social_display.py`（13 案）、
    `tests/test_frontend_moved.py`（hash 白名單＋首屏）。本機驗證 http.server 要起在三個 repo 的**上一層**
    （例 `/home/user`），以 `/postmkt/` 開頁，`../taiwan-flows/`、`../taiwan-stock-news/` 才可達。
  - **市場情緒 `sentiment`（2026-09-29 新增，第 17 個 tab，排在 `social` 之後、`dates` 之前；規格正本
    `taiwan-flows/docs/sentiment-tab.md` §3，硬約束 M4–M7）**：`index.html` grep `// ================= 市場情緒 tab`
    （接在社群聲量之後、「日期 tab」之前）。資料＝`const SENT_URL = "../taiwan-flows/data/sentiment.json"`（**同源相對路徑、
    CSP 未改**），**只在切到本 tab 時才抓**（`sentRender()` 內呼叫 `sentEnsure()`：in-flight 以 `SENT.loading` 去重、失敗記
    `SENT.err` 不重試，比照 `crEnsureSr`），首屏請求清單不變。三張卡：臺指 VIX／Put-Call（未平倉比為主含折線、成交量比為輔）／
    小台散戶多空比（另列最新一列的法人多／空、散戶淨部位、全市場未平倉「全部契約」與「僅月契約」兩種口徑，標「口徑比對中」）。
    每卡＝最新值＋**自帶資料日**（該欄最後一個非 null 的列；最新列該欄缺值時明講）、與前一筆有值的差、近 N 筆有值資料第 P 百分位
    （N＝min(60, 實有筆數)，不足 60 註明；P＝窗內 ≤ 最新值的筆數 ÷ N，四捨五入）、均值、全部歷史 inline SVG 折線＋
    60 筆有值資料均線（不足 60 筆不畫）——**窗是「筆」不是「日」**：序列跳過 null 的日子，含缺值時跨度多於 N 個交易日，
    畫面措辭因此一律寫「近 N 筆有值資料」（2026-09-29 更正，演算法未改）。免責句前半「情緒指標為現況描述，非買賣訊號；無回測依據。」逐字固定（`SENT_DISCLAIMER`），後半「VIX 歷史自 YYYY-MM-DD 起。」**不寫死**——由 `sentDisclaimer(rows)` 取資料中第一個有 `vix` 值的列日期（先過 `SENT_DATE_RE`），無值時整個後半句省略（2026-09-30；原寫死 2026-03-02，實際資料自 2026-03-11 起）。`generated_at` 徽章先過 `sentGenOk()`
    （`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}` 開頭才顯示，否則「產出 —」；它是產出時刻、不代表資料新鮮度）、一行口徑說明。**純描述（M6）**：畫面除免責句外不得出現偏多／偏空／建議／訊號等字樣，
    線條與字色一律中性（`var(--txt)`／`var(--muted)`，不用紅綠）。**M7**：日期白名單 `SENT_DATE_RE`（`^\d{4}-\d{2}-\d{2}$`，
    不合的列整列丟棄）、數值 `sentNum()`（typeof number＋isFinite，字串數字一律當 null）後 `toFixed`、外來字串插值一律 `esc()`。
    降級：某欄全 null／缺欄 → 該卡灰字「目前無資料」、其餘卡照常；整檔 404／壞 JSON／`rows` 非陣列或空 → 整段一句
    「資料尚未產生或讀取失敗」（不報錯）。**不接休市行事曆、不做「今天」判斷**。CSS 一律 `.sent-*` 前綴；**不加新 hash key**
    （`#tab=sentiment` 由 `HASH_TABS`＝`TABS` 自動白名單）；頂列 stats 列比照籌碼雷達清空（頁內自帶資料日）。
    **本站因此也是 taiwan-flows `data/sentiment.json` 的前端消費者**：`rows[].date`／`vix`／`pc_oi`／`pc_vol`／`put_oi`／`call_oi`／
    `put_vol`／`call_vol`／`inst_long`／`inst_short`／`retail_net`／`retail_ratio`／`mtx_oi`／`mtx_oi_monthly_only` 與頂層
    `generated_at` 改名或改語意＝跨站變更（日期語意見 `docs/date-semantics.md`）。**P/C 卡與小台卡的口徑說明另註「未平倉不含當日到期契約」**（2026-09-30，對應 taiwan-flows 規格 §0b；後端每列附加 `cv`（計算版本，2＝排除當日到期契約），前端不讀、形狀相容，演算法未改）。純函式集中在 `sent-pure:begin`～`end` 區段；
    測試 `tests/test_sentiment_frontend.mjs`（pytest 由 `tests/test_sentiment_frontend.py` 代跑；樣本
    `tests/fixtures/sentiment_sample.json`＝80 列，最末列 2026-09-24 的 VIX／P/C／法人口數取規格 §0 實測，其餘與 `mtx_oi` 為合成值），
    另含 M6 字樣／色票、M4/M5 lazy、M7 插值 `esc()` 的讀碼檢查與整段內嵌 script 可編譯檢查。本機驗證同籌碼雷達（http.server 起在上一層）。
  - **休市行事曆（2026-09-29 家族批次二，規格正本 `taiwan-flow-live-v2/docs/holiday-calendar.md` §5b）**：
    `index.html` grep `// ---------- 家族休市行事曆` 起（`HOL_URL`／`holParse`／`holClosed`／`isTradingDay`／
    `prevTradingDay`／`holLoad`）。`load()` 末尾 `holLoad()` 以**同源相對路徑** `../taiwan-flow-live-v2/data/twse_holidays.json`
    非阻塞讀取（CSP `connect-src 'self'` 已涵蓋、未改 CSP；首屏多這一支小檔）；載入成功才重繪頂列＋`dates`／`mychg`／`rrgd`
    三個 tab 一次。**休市日比照週末**：`pmStatus`（休市日＝「休市定格」、上一交易日跳過休市日）、`dayDiff`（日期 tab
    `dateStatus` 與持股異動第五軸 `myChgDateInfo` 的交易日差）、`rrgdLagDays`。資料日≠今日且 `lag`＝0（今日為休市日或週末）時第五軸文案寫
    「今日 X（假日名休市／非交易日），此為最近交易日」而非「即今日」（**週末同型的舊錯誤同批於 `7e244f4` 一併修正**；
    代價：無行事曆時的週末文案與改動前不再逐字相同）。
    **fail-open**：讀不到／非 2xx／壞檔／`schema` 不是整數 1（`true` 不收）／`years` 無合法年度 → `HOL=null`
    ＝只排週末＝改動前行為（Playwright 以行事曆 404 對跑 origin/main，16 tab `#topbar`＋`#main` 逐字相同）；某年不在
    `years`＝該年未知、只排週末。**不新增判級／門檻、不改資料欄位**；`MYCHG_STALE_LAG` 仍為 2。颱風臨時停市仍會誤報。
    刻意不改：`twDayList`（雲端歷史近 3 個**日曆日**，休市日檔案本來就 404 靜默略過）、`diagNewsFor`（用 news.json 自帶
    `trading_days`）、大盤餘額「異動」（跟陣列前一筆比，不做日期推算）。同規則在 taiwan-flows／taiwan-backtest 前端與
    Worker `parseHolidayCal` 各一份（前端無共用模組）。測試 `tests/test_holidays_frontend.mjs`（pytest 由
    `tests/test_holidays_frontend.py` 代跑；fixture `tests/fixtures/twse_holidays_2026.json` 為 2026-09-29 快照）。
  - **持股清單匯出／匯入／清除（2026-09-07）**：`holdExportPayload`／`holdParseImport`／
    `holdExport`／`holdImportFile`（grep `const HOLD_SCHEMA` 起至 `async function holdImportFile`
    該函式結尾止）。**仍只走 localStorage `pm_holdings` 與使用者本機檔案，不進任何網路 payload**
    （約定 6 不變）；匯入走 `holdParseImport`
    的結構與型別檢查，壞檔整包拒收、不半套。
- `build_postmkt.py` → `data/postmkt.json`（主資料，五個盤後 tab）
- `build_summary.py` → `data/summary/`（AI 彙總自動場；含資料齊全輪詢閘門與假日判斷）。
  **2026-08-29 起：每頁 1 份共 3 份摘要（原 6 份）、`MIN_OK_FOR_SYNTH=2` 才彙總、共振強度口徑 N/3；
  自動場摘要與彙總改走 Anthropic Message Batches（半價，逾時或單筆失敗逐筆同步回退）**。
  **pm 期限 2026-09-10 改走牌鐘截止點**（`build_summary.py` grep `PM_BATCH_CUTOFF_HM`＝台北 23:00；
  am 維持固定 25 分、**刻意不掛牌鐘**）：`batch_deadline(slot, t_start, now=None)` 取
  min(場次期限, 全場剩餘預算−同步保留, 距截止點剩餘)，已過截止＝回 0＝整包跳過 batch 直接同步。
  `BATCH_DEADLINE_SEC["pm"]` 為 **180 分，但那只是上界**，實際綁住 pm 的是牌鐘。
  **同日第一版「砍成固定 30 分」已作廢**：那版的理由寫「那包 batch 本來就沒成功過，所以沒有代價」，
  **被當晚 run 34481046459 推翻**——摘要那包實跑約 **104 分鐘**後 `via` 全 batch 成功、產物台北 22:58
  落地（早於健檢），30 分會把它 cancel 掉、白付原價。**五天**實際分布＝**三失敗兩成功**
  （09-07／08／09 逾 180 分未 ended 全 sync 回退；09-10 約 104 分成功；09-11 整場僅
  **7 分 32 秒**、摘要 batch 上界約 5 分）。**2026-09-13 補 09-11，原寫「四天三失敗一成功」已過期。**
  完成時間橫跨約 5 分 ~ 104 分 ~ >180 分，**分布極寬**——任何固定分鐘數都是在賭它。
  **23:00 是餘裕的選擇、不是量出來的最適值**（截止後最壞還要摘要同步回退 4 分 17 秒＋彙總，
  留 50 分給 23:50 健檢；沒有足夠天數的完成時間分布可算最適值，**不可寫成實測結論**）。
  逐行 log 證據寫在 `build_summary.py` 的 `BATCH_DEADLINE_SEC` 上方；**要調整之前，先看幾天
  `-pm.json` 的 `via` 欄**（`sync`＝那包 batch 又沒趕上牌鐘）。**場次期限與牌鐘都是 per-slot、
  摘要與彙總共用**，改它會同時改到彙總那包的上限。`summary.yml` 另有 `workflow_dispatch` 輸入 `no_wait`（跳過資料齊全閘門，
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
6. **金鑰**：FINMIND_TOKEN/ANTHROPIC_API_KEY 走 Actions secret。**前端金鑰 2026-10-01 起改存瀏覽器密碼管理器，
   不再存 localStorage**（使用者裁定 D1–D8，方案文件見當日 session scratchpad `token-pwmgr-plan.md`）：
   - 四站（postmkt／taiwan-flow-live-v2／taiwan-stock-news／taiwan-flows）同一套寫法，`index.html` grep
     `// ---------- 前端憑證` 起至 `// ---------- 前端憑證結束` 止；**刻意不要求逐字**（`CRED`／`CRED_SPEC`／
     `credRerender` 與 escape 函式名各站不同），但行為改一站要四站一起改。
   - 每種憑證一個 `<form data-cred="<kind>">`：`type="text"` **readonly** 且預填固定帳號名的 username 欄
     （`autocomplete="username"`；不用 `type=hidden`——Firefox 不認）＋`autocomplete="current-password"` 密碼欄
     （**不可 readonly**——Chrome／Firefox 不填唯讀欄）＋submit。submit handler `preventDefault()` 後才讀 `.value`
     （Chrome 自動填入值在使用者手勢前 JS 讀不到），先打一次**免費唯讀**驗證、通過才收進記憶體物件 `CRED` 並重繪
     （表單消失＝密碼管理器判定已送出），失敗當場顯示錯誤、不採用。
   - 驗證（D5）只打各站 CSP `connect-src` 既有 origin、token 一律放 header：Anthropic `GET /v1/models?limit=1`
     （列模型、不產生 token 用量；CORS 預檢 2026-10-01 curl 實測允許 `x-api-key`／`anthropic-version`／
     `anthropic-dangerous-direct-browser-access`）；GitHub `GET /repos/shihpc/postmkt`（flows 為 `/repos/shihpc/taiwan-flows`）。
     **FinMind 不驗證**：本站只以 query 帶 token，header 版的 CORS 預檢本沙箱連不到 FinMind 無法實測，token 又不得進 URL
     ——存入時不打請求，第一次查詢失敗才會知道 token 有誤。
   - 家族統一 username（**改名＝使用者要在密碼管理器重存**）：`anthropic-api-key`（三站共用一筆）、
     `github-pat-postmkt-analyses`（三站共用）、`finmind-token`（本站）、`github-pat-flows-dispatch`（taiwan-flows）、
     入口站密碼門 `hub`。
   - 「只在本分頁記住」（D2，預設不勾）：勾了才寫 sessionStorage `cred_tab_<kind>`（重新整理仍在、關分頁即清）。
     **任何路徑都不得再把金鑰 `setItem` 進 localStorage**；值不進 DOM 屬性、URL、hash。
   - `anthKey()`／`ghToken()`／`fmToken()` 保留原名、改讀 `CRED`，所以逐字同步碼 `ghSaveAnalysis`／`callClaude`
     **位元組不變**（`check_sync.py` PASS）。`saveAnalysisCloud`（不在 check_sync 範圍，三站同步改）在 PAT 未載入時
     記 `cloud="nokey"`，畫面顯示「GitHub PAT 本分頁未載入，未存雲端」。
   - 搬移（D7）：舊 localStorage key `anthropic_key`／`gh_token`／`fm_token`／`tf_gh_token`（四站每站都處理全部四把）
     **新版不讀作金鑰**，只用來顯示提示卡（`#credMigrate`，按「刪除本機舊副本」才刪）；`CRED_MIGRATE_UNTIL`
     ＝`"2026-10-15"`（台北日期）之後載入頁面即無條件刪除。期滿後的下一批可拿掉提示卡、只留刪除。
     `tflive2_usw_sync`（美股自選同步碼）**不搬**（D6）。
   - **未經實機驗證**：密碼管理器的儲存提示、自動填入、同 origin 多筆不互蓋、Android 底部選單是否依 username 過濾、
     長 token 是否被截斷——Playwright 無法模擬瀏覽器內建密碼管理器，需使用者手機實測後回寫本節（區分已驗證與推論）。
   持股清單只存 localStorage、不進任何網路 payload。
7. **外部消費者**：taiwan-flow-live-v2 的 Cloudflare Worker 會輪詢本 repo raw main 的
   postmkt.json/diag.json 來鏈式觸發下游；資料檔位置/欄位大改前先確認跨 repo 影響。

## 驗證方式

```bash
python -m pytest tests/ -q        # 離線單元測試（免 token/網路）
python src/build_diag.py --sample # diag 管線本地驗證（免 token）
python -m http.server 8000        # 前端本機驗證；慣例＝17 個 tab 逐一點擊 console 零 error
ruff check .                      # lint（設定在 pyproject.toml）
```

改前端後務必實測 17 tab 零 console error（歷次都這樣驗）；改 gather/SYS 後記得跨站同步檢查。

**手機驗收條件（2026-09-09 更正，舊寫法已被實測推翻）**：375／390／1280 三寬度下
①**整頁 `document.documentElement.scrollWidth == window.innerWidth`**（無**頁面級**水平捲軸）、
②表格各欄**全部可見、無文字裁切（逐格 `scrollWidth - clientWidth == 0`）、無換行**。
**不得宣稱 `.tblbox` 的 `scrollWidth == clientWidth`**——`.mtable` 是 `width:100%`＋`nowrap`，
壓到 min-content 之後由 `.tblbox` 的 `overflow:auto` 吸收，「持股異動」在 **375px ＋ 6 位數張數**
時實測會溢出數 px（依股名長度而動，本批量到 6px）。那不影響可見性：`.tblbox` 的裁切邊界是
**padding box**，溢出量落在其 **12px 右內距**內，不捲動也完整看得到。
數據、量法與「刻意不修」的決定見 CHANGELOG「（同日修正之五）手機驗收條件更正」節。
