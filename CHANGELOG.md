# Changelog

帶日期的變更紀錄從 README「快速接手」搬出集中於此（2026-07-24 起）；
更早的逐日歷史見 git log。常青的架構／口徑／教訓說明仍在 README。

## 2026-09-09（合併前最終驗收回修）文件計數與錨點唯一性：純文件批

獨立驗收在 `26e3a73` 之後找到 4 項必修，**全部是文件的計數／唯一性宣稱錯誤**。
本批**只動 `.md`**：`index.html` 與 `build_postmkt.py` 位元組層零變更（md5 前後相同）。

1. **`CLAUDE.md` 的「六種說錯話」被 `26e3a73` 改成與 `index.html`／README 相反（必修，最嚴重）**。
   `26e3a73` 之前，三方的六項完全一致＝{本表不涵蓋／`f`／`t` 為 `null`／三欄全 `null`／
   整表殘缺／資料日不是今天／徽章報成正常涵蓋}（實查 `git show 26e3a73^:CLAUDE.md` 與
   `index.html` 的 ①–⑥、README 的「下列N軸／另外三軸／前四軸／第五軸／第六軸」）。
   `26e3a73` 把「查無此代號」提成六項之一、又寫下「整表殘缺……**不進**上述逐檔分類」，
   於是 `index.html` 把整表殘缺列為 ③、README 把它算進「前四軸」、`CLAUDE.md` 卻說它不算——
   **三方直接相反**。本批把 `CLAUDE.md` 改回原本那六項，「查無此代號」改寫成**不影響計數**的
   對照項說明（它本來就是第一軸與整表殘缺軸「不可說錯成這個」的那一端）。
   **教訓**：上一批是「照著驗收指示改、沒有自己驗證那個指示」——驗收說「漏了查無此代號」，
   改的人沒去比對另外兩方就照做，結果把原本一致的三份文件改成互相矛盾。
   **收到修改指示時，指示裡的事實主張同樣要自己驗一次。**
2. **`data-mychg` 宣稱 4 處、實際 5 處**。少算的正是**宣稱句自身**那一次
   （`grep 'data-mychg' index.html` ＝註解 3 行＋表格欄屬性＋handler 的 `closest()`）。
   `CLAUDE.md` 已改（並寫明「宣稱句本身也算一次命中」）。
3. **`README.md` 三處「grep 唯一命中」不成立**：`RE_MARKET_CODE`／`RE_MARKET_EXCLUDE` 在
   `build_postmkt.py` 各 **5 行**、`MARKET_DAILY_MIN_ROWS` **4 行**（三者另各出現於
   `index.html` 與 `tests/test_postmkt_build.py`）。改成**宣告式錨點**
   （`RE_MARKET_CODE = ` 等，實測各唯一）並附上裸名的真實處數。
4. **`'location.hash = '`「全站唯一命中」實為 3 處**（兩行註解＋一處真賦值）。
   「全站唯一的**賦值**」為真、「唯一命中」為假，`CLAUDE.md` 已分開講。

**同批順手（同類、都實測過）**：
- `MYCHG_MIN_ROWS` 錨點改 `const MYCHG_MIN_ROWS`（裸名在 `index.html` 4 處命中，宣告式唯一）。
- `README.md:117` 原寫「下列**四軸**」，該節實際有六軸（第五、第六軸補上時漏改計數）→ 改「六軸」。
- `README.md:22` 摘要列原本也把「查無此代號」列成六項之一、把「整表殘缺」擺在六項之外，
  **與同檔下方「前四軸／另外三軸」自相矛盾**（此列不在 `26e3a73` 的 diff 裡，是更早就存在的）
  → 一併對齊。

### 待下批同步（本批刻意不動：那些是程式檔註解，改了會動到 `index.html` 位元組）

- `index.html` 的 `grep 'location.hash = '` 註解仍寫「全站唯一命中」（應為「唯一的賦值」）。
- `index.html` 的 `grep data-mychg` 註解仍寫「則有 4 處」（應為 5 處）。
- `index.html` 的 `myChgHtml()` 內註解稱「三欄全 `null`」為**第四軸**，但 README 把它列為**軸3**、
  整表殘缺列為**軸4**；`index.html` 的 ③④ 與 README 的軸3／軸4 **順序互換**。
  六項的**集合**三方一致（本批已確保），只有**序號**對不上，屬敘述性差異、不影響判準。
  下批統一時以 README 的軸序為準。

### 範圍外、只記錄不處理（本批不動，CANON 第 5 條）

- **`CLAUDE.md` 側欄那段寫「taiwan-flows 與 taiwan-flow-live-v2 沒有 hash 路由」，對
  taiwan-flows 已經過期**：本機 `taiwan-flows/index.html` `grep -c location.hash` ＝ **3**，
  且該 repo 自己的 `CLAUDE.md` 記載 hash 路由於 2026-09-07（批次三 #15）上線
  （`#tab=&mode=&d1=&d2=&side=&rank=&etype=&inv=&sec=&sub=`）。`taiwan-flow-live-v2` 本機
  `grep -c location.hash` ＝ **0**，那半句仍成立。**線上狀態本批未驗**（沙箱未實打該站），
  且改這句連帶要決定 `stkSecLinks()` 要不要吐 taiwan-flows 深連結＝**動 `index.html`**，
  超出「純文件」範圍，故只記錄。下批處理時：先實打線上 `index.html` 確認格式，
  再一起改程式與文件，**不得只憑本機 repo 就編造深連結格式**。

### 貫穿本 session 的教訓：自我指涉的計數，與「沒跑過的數字」

**「宣稱 grep X 唯一命中」這句話本身會讓 X 多一次命中**——文件寫下錨點的同時就改變了被計數的
母體，是典型的自我指涉計數錯誤（本批第 2 項就是它：少算的那一次正是宣稱句自己）。

本 session 在「宣稱數量」與「宣稱唯一性」這兩類上反覆出錯：`120 筆` cron 延遲樣本／
`>10h 為 0 筆`／「三種缺資料狀態」／「六種說錯話」／「13 個 tab」／「22 支測試」／「347 行」／
多處「grep 唯一命中」。**共通點是它們全都能用一行指令驗證，卻沒有人去跑。**

往後的規矩：
1. 文件裡的錨點一律用**宣告式**（`const X`／`function X`／`X = `），不要用裸名——裸名會命中
   註解、測試與文件自身。
2. 寫下任何「唯一／N 處／N 筆／N 支／N 行」之前**實跑一次**（`grep -o … | wc -l` 數的是
   **出現次數**、`grep -c` 數的是**行數**，兩者不同，講清楚是哪一種）。
3. 錨點寫進文件後**再跑一次**——因為這句話本身可能就改變了計數。
4. 收到別人（含驗收）給的事實主張，先驗證再照做。

## 2026-09-09（持股異動獨立驗收回修）第五軸「資料日不是今天」＋兩處畫面／文件不實敘述

獨立驗收（fresh-context）在上一批「持股異動」tab 找到 2 項必修＋3 處不精確敘述，本批全數修掉。
**管線 `build_postmkt.py` 一行未動，其餘 13 個 tab 未動。**

1. **第五軸：資料日被講成「今天」（必修，同型錯誤第五次）**。`market_daily.date` ＝管線的
   `lending.date`（價格／借券資料日），與頂列 `pmStatus` 取的 `pm.date`（全檔基準日）**是兩個
   不同的日期**——線上 `44ef7e7` 實測頂列 `2026-09-09`、本區塊 `2026-09-08`，**系統性差一天**。
   舊版把 `date` 改成一個多月前，畫面照樣說「持股中**今日**沒有任何一檔達門檻」，真正的資料日
   只在最底下 0.74rem 灰字裡——**又一次把不明時點的資料呈現成今天的正常狀態**。
   - 新增 `myChgDateInfo()`／`myChgWhen()`／`myChgAt()`（`MYCHG_STALE_LAG` = 2）。免責卡、段落
     標題、主句與每一條說明**一律寫出實際日期**，`grep 今日/當日` 在該區塊的畫面字串上零命中；
     日期缺失時說「本區塊資料日（不明）」，**不退回「今天」**。
   - 資料日落後今日 ≥2 個交易日、晚於今日、或缺失時，另出一段與免責卡同重量的 `.diag-disc`
     說明（不是 0.74rem 灰字）。交易日距離沿用既有 `dayDiff()`（只排週末的已知近似）。
     **刻意不新增紅黃綠判級**（判級語意未經裁決，CANON 第 8 條），只敘述「這些數字是哪一天的」。
   - `market_daily.date` ≠ `pm.date` 時多一條說明，指出頂列那個是全檔基準日、本區塊另有自己的
     資料日（比照 CLAUDE.md 個股摘要側欄「每段自帶自己的資料日」）。
2. **畫面上的假話：「本 tab 也不發任何網路請求」（必修）**。直接開 `#tab=mychg` 時 `ensurePm()`
   就會抓 `data/postmkt.json`。改成真正成立的保證——「**持股代號不進任何網路請求**（本 tab
   不新增網路請求，資料取自各盤後 tab 共用、已載入的 `data/postmkt.json`）」，隱私承諾不弱化。
   `SUBS.mychg`、README、CLAUDE.md 同批改，並在三處註明「不可再寫『不發任何網路請求』」。
3. **「多為匯率避險型 ETF 與 ETN」與實檔不符（必修）**。把 `44ef7e7` 版 46 檔 `chg=null` 全數
   分類：ETN（`02` 開頭）**7 檔**、`00` 開頭 ETF **6 檔**（R／K／U 尾碼 3／2／1）、
   **其餘 33 檔（72%）是一般證券代號**（31 檔純 4 位數字，另 `1312A`、`910322` 各 1）
   ——**ETF＋ETN 只佔 13/46（28%）**。README 與 `index.html` 註解兩處都改成與實檔相符的描述。
4. **`46/2757` 標明是 n=1 的單日單次觀測**：`market_daily` 2026-09-09 才上線，
   `data/postmkt.json` 近 20 個 commit 只有 `44ef7e7` 帶這個區塊，日常分布未知。
5. **「grep `data-mychg` 唯一命中」不實**（實際 4 處：兩段註解＋表格欄屬性＋handler 選擇器）。
   改成可驗證的說法：`grep 'location.hash = '`（帶等號的賦值）才是全站唯一命中。
   `index.html` 與 `CLAUDE.md` 同步改。
6. **第六軸（本輪主動自查找到並一併修掉）：整表不可用時頂列徽章仍報「N 檔涵蓋」**。
   `renderStats()` 的 `mychg` 分支自己算 `(md.rows||[]).length`，與內文的健康度判斷各寫一份，於是
   `cols` 形狀不符時徽章顯示「資料日 2026-09-08 · **2757 檔涵蓋**」、內文卻是「無法取得異動資料」
   （三種殘缺情境實測皆如此）。健康度抽成唯一事實來源 `myChgUnusable(md)`，徽章與內文共用，
   徽章逐字沿用「無法取得異動資料」、成因放 `title`，**刻意不上色**。
7. **標明兩個不可達分支**：`instMissPx` 的「其中 N 檔」與「整句不加」在現行管線下觸發不到
   ——`build_market_daily()` 的 `it = inst_by_c.get(c)` 以同一個 `it` 真假值同時決定 `f` 與 `t`，
   單欄 `null` 不可能發生；而 `rated` 已排除三欄全 `null`。**兩個分支是防禦性的、不刪**
   （第三方或未來的資料形狀可能單欄缺），改在程式與 README 註明其不可達性。

## 2026-09-09 新增第 14 個 tab「持股異動」（由入口站「我的異動」搬遷，第一階段：只做 postmkt 前端）

**入口站 `shihpc.github.io` 這階段零改動**（移除是下一階段）。搬家的兩個理由：①持股清單
（localStorage `pm_holdings`）本來就由本站寫入，本站才是擁有者；②入口站那張表 6 欄，
手機上只看得到前 2 欄，外資／投信／漲跌三個關鍵數字全在畫面外。

- **版面**：改用共用 `tbl()` 框架的 **4 欄**（`nameCell` 代號＋名稱兩行合成一格／外資(張)／
  投信(張)／漲跌%），資料日不佔欄位、改走 `renderStats()` 徽章——**取 `market_daily.date`
  而不是 `pm.date`**（兩者語意不同、值常常不同，例 `44ef7e7` 是 09-09 vs 09-08）。
- **資料源**：`data/postmkt.json` 的 `market_daily`，走既有 `ensurePm()`，**本 tab 零新增網路
  請求**；持股代號絕不進任何請求的 URL／header／body（CANON 第 1 條＋CLAUDE.md 約定 6），
  比對全在瀏覽器端。Playwright 逐請求稽核（URL＋body＋headers）零命中。
- **三種「缺資料」分開講**（實作 README「前端消費 `market_daily` 的必要條件」）：
  ①代號不在 `rows` 且屬權證（`MYCHG_WARRANT_RE`）或偽代號（非數字開頭，`MYCHG_SEC_RE`）
  → 「本表不涵蓋」，不說「查無此代號」；②`f`／`t` 為 `null` → 「當日法人資料未到（不是 0、
  也不是無顯著異動）」，**同列 `chg` 照常判讀、不整檔靜音**；③`rows` 為空或 `< MYCHG_MIN_ROWS`
  (2000，同管線 `MARKET_DAILY_MIN_ROWS`) → 整段「無法取得異動資料」，不逐檔說成查無此代號。
- **誠實原則（CANON 第 8 條）逐字保留**：「門檻：法人淨買賣 ±100 張或漲跌 ±3%，為顯示用可調
  常數、無回測依據，不是買賣訊號，只是相對變化提醒」。
- **動到的地方**：`TABS`／`SUBS`／`render()` 分派（**else 鏈末端是 fallback 到 `renderPM()`，
  沒加分支會掉進去**）／`renderStats()`／新區塊 `function myChgHtml`＋`function renderMyChg`
  ＋`.clk[data-mychg]` 委派（點個股走內部 hash `#tab=diag&code=`，同站切 tab 不開新分頁）。
  `HASH_TABS` 由 `TABS` 自動生成，未手改。
- **驗收（Playwright，本機 `http.server`）**：14 tab 逐一點擊 console error 0／pageerror 0；
  三種狀態各自實測（正常有值／`f`,`t` 全 null＝線上 `44ef7e7` 天然狀態／`rows: []`＋1500 列殘缺
  ＋`cols` 形狀不符＋整包 500）；權證 `030018` 走「本表不涵蓋」、`9999` 走「查無此代號」、
  `TAIEX` 走「不是證券代號」；375／390／1280 三寬度 `scrollWidth == innerWidth` 不溢出；
  代號與股名含 `<img onerror>` 未執行（`window.__xss` 為 null、`#main` 內 `img` 0 個、以字面文字顯示）。

## 2026-09-09（同日修正之四）真實建置數字回填文件＋「必要條件」補兩種「缺資料被說成別的東西」

**全部是文件與告警條件，宇宙判準（`RE_MARKET_CODE`／`RE_MARKET_EXCLUDE`）與 `build_market_daily()`
的既有輸出行為一行未動**（唯一的程式改動是告警條件，見下第 3 點）。

1. **用真實建置數字取代已被證偽的點預測**（詳見「同日修正之三」的「體積與宇宙」段，已就地改寫）：
   `ec50d80` 的 CI run [`34321284815`](https://github.com/shihpc/postmkt/actions/runs/34321284815)
   實測 **宇宙 2,757 檔**（點預測分毫不差）、**全檔 1,706,347 bytes**（**點預測
   1,708,100–1,708,240 B 被證偽，實測低 1,753 B／−0.10%**）。成因是 TWSE 盤後零股 `TWT53U`
   兩個 run 取到不同日（錨點 `2026-09-08`、本 run `2026-09-09`），差在 `oddlot` 區塊、
   **與宇宙規則無關**。日常區間 2,730–2,830 檔／1.70–1.72 MB 仍成立，且現在有兩次真實建置背書。
   `README.md` 對應段落同步改為實測值，並改寫成「全檔只給區間、不做點預測」。
2. **`README.md`「前端消費 `market_daily` 的必要條件」補兩條**（原本只寫了「涵蓋／不涵蓋」，
   漏了另外兩種同型的「缺資料被呈現成別的東西」）：
   - **`f`／`t` 為 `null` ≠ 無異動**：法人資料日 ≠ 基準日時整欄寫 `null` 是刻意設計、有測試守著，
     前端把它當 0 或「無顯著異動」就是**完全複製**該節自己引用的入口站舊坑
     （911 檔達門檻者有 687 檔被寫成「無顯著異動」）。正確文案＝「當日法人資料未到」；
     `chg` 那天仍有效、不必整檔靜音。
   - **`rows` 為空／殘缺 ＝「無法取得異動資料」**：不得逐檔說成「查無此代號（已下市／停牌／
     代號有誤）」。判準給到 `len(rows) < 2000`（同 `MARKET_DAILY_MIN_ROWS`），文案逐字沿用
     入口站 `shihpc.github.io/index.html` `loadMyChanges()` 既有的失敗路徑
     （`body.textContent = "無法取得異動資料"`）。
3. **管線端告警放寬（唯一的程式行為改動）**：原條件
   `if price_rows and nm and len(rows_out) < MARKET_DAILY_MIN_ROWS`——**`price_rows`（或 `nm`）
   為空時前兩個條件就短路，最該示警的情況反而連警告都不印**，區塊照樣以 `rows: []` 靜默輸出。
   改成兩條分支：整包為空 → `⚠ market_daily：上游輸入為空（…），前端須整段顯示
   「無法取得異動資料」而非逐檔「查無此代號」`；有輸入但列數不足 → 沿用原訊息逐字不變。
   **只加一條 print，不改任何回傳值**。守門測試
   `test_market_daily_warns_when_upstream_input_is_empty`（三種空輸入都要示警＋對照組不得誤報成
   「上游輸入為空」）。
4. **`CHANGELOG.md`「同日修正之二」ETN 分類計數就地更正**：原寫「『ETN』20＋『指數投資證券(ETN)』28」，
   **兩個數字對調**（本次重新匿名拉 `TaiwanStockInfo` 全表逐項計數：`ETN` **28**、
   `指數投資證券(ETN)` **20**）；總數 48 無誤，同檔「同日修正之三」與 `build_postmkt.py:50`
   的註解本來就是對的。

**`lending` 一個 byte 都沒動**：本次 `build_postmkt.py` 的 diff 只有三個 hunk
（`MARKET_DAILY_MIN_ROWS` 上方註解、`build_market_daily()` docstring、告警的兩條分支），
`build_lending()`／`stock_names()`／`_agg_*` 一行未動；另以同一份 fixture 跑 `ec50d80` 與本次，
`PYTHONHASHSEED` 取 0／1／2 各一次，離線輸入（`date=""`）**672 bytes**、真實輸入
（`date="2026-09-08"`，實打 TWSE SLB/NLB）**1,227,628 bytes**，兩種都逐位相同。

**突變測試（自測，六種全紅照舊＋新守門一種）**：①`market_daily` 移到 `out` 第一個 key → 2 紅；
②`rows_out[:TOP_N]` → 7 紅；③拿掉宇宙過濾 → 5 紅；④拿掉基準日過濾 → 1 紅；
⑤`RE_MARKET_CODE` 退回舊白名單 → 7 紅；⑥`RE_MARKET_EXCLUDE` 退回擋 ETN → 5 紅；
⑦**告警條件退回 `price_rows and nm and …`** → 1 紅（本次新增的守門）。

## 2026-09-09（同日修正之三）`market_daily` 宇宙**納入 ETN**，黑名單只剩權證

**裁定與理由**：上一節把 ETN 排除，同時自承「ETN 是**可以被持有的證券**，排除後前端會呈現成
『查無此代號（已下市/停牌/代號有誤）』——與事實不符」。使用者裁定**納入 ETN**（48 檔、
體積代價 ~1.3KB 量級）。

**規則變更**（`build_postmkt.py`，grep `RE_MARKET_EXCLUDE`）：

| | 舊（`8dc1f0b`） | 新 |
|---|---|---|
| `RE_MARKET_CODE` | `^\d[0-9A-Z]{2,7}$` | **不變** |
| `RE_MARKET_EXCLUDE` | `^(?:0[2-9]\d{3}[0-9A-Z]｜7\d{4}[0-9A-Z]｜\d{6}U)$` | `^(?:0[3-9]\d{3}[0-9A-Z]｜7\d{4}[0-9A-Z])$` |

＝`0[2-9]` → `0[3-9]`（放行 `02` 開頭的 ETN）＋拿掉 `\d{6}U`。**上一節留下的兩句話要對起來**：
它同時寫了「退回方式＝把 `0[2-9]` 改成 `0[3-9]`、拿掉 `\d{6}U`」與「FinMind 實際的 ETN 代號是
`020041`／`02001L` 這種**不帶 U** 的寫法」。本次覆驗的結論是**兩句都對、但份量不同**：
真正放行那 48 檔 ETN 的是 `0[2-9]`→`0[3-9]`；**拿掉 `\d{6}U` 對真實資料是零影響**
（`TaiwanStockInfo` 全表沒有任何 `\d{6}U` 形狀的代號），一起改只是讓「黑名單裡不再有任何一條
是為了擋 ETN 而存在」在規則上也成立。改完黑名單**只剩權證**。

**驗證母體＝FinMind `TaiwanStockInfo` 全表**（2026-09-09 **匿名**取得，本沙箱可直接打
`api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo`，免 token；**全市場單日
`TaiwanStockPrice` 匿名會回 400「Your level is free」，逐檔 `data_id=` 則可**）。
**刻意不用 taiwan-flows 的 daily 檔當母體**（與規則同源，循環論證）。原始列 4,319、
去重後 **3,147 檔**——與 CI log 的 `TaiwanStockInfo: 3147 檔對照` 相符。以**程式裡的
regex 本體**（`import build_postmkt` 後直接呼叫 `bp.RE_MARKET_CODE`／`bp.RE_MARKET_EXCLUDE`）
逐檔對跑：

| 類別（`industry_category`） | 檔數 | 新規則 | 點名實例 |
|---|---|---|---|
| ETN（「ETN」28＋「指數投資證券(ETN)」20） | 48 | **全部放行** ✅ | `020000`／`020041`／`02001L`／`02003L` |
| 權證（「所有證券」） | 36 | **全部被擋** ✅ | `710553`／`73107P`／`708785`／`711145` |
| 產業別／指數偽代號（`Index` 30＋`大盤` 2） | 32 | **全部被擋** ✅ | `TAIEX`／`TPEx`／`Semiconductor` |
| 其餘（個股／ETF／DR／REIT／特別股…） | 3,031 | 全部放行 | `0050`／`00637L`／`00981A`／`910322`／`01002T`／`2887Z1`／`2887F` |

- **通過 3,079、被擋 68**，被擋的**恰為權證 36＋偽代號 32、沒有第三類**。
- **相對 `8dc1f0b` 逐檔對跑：新增放行 48 檔（恰為全部 ETN），新增被擋 0 檔**（零回歸）。
- **`TaiwanStockInfo` 收的 36 檔權證全部是 `7` 開頭**（`708785`–`711145`／`73107P`／`73193P`），
  `03`–`09` 開頭的上市權證**一檔都不在該表內** → 黑名單第一條分支對現況是**防禦性**的
  （真的漏進 `nm` 才用得到）；測試 fixture 仍把 `030018`／`715001` 放進 `nm` 守著它。

**體積與宇宙：預測 → 真實建置實測（2026-09-09 補記，實測值已取代點預測）**

**單位口徑：本節 MB 一律 10⁶ 進位**（`1 MB = 1,000,000 bytes`）。錨點 `1,707,249 bytes`
＝ **1.707 MB(10⁶)** ＝ 1.628 MiB(2²⁰)；上一節同時出現 MB／MiB 兩種讀法，本節起統一為前者。

- **錨點（本次直接讀 CI log 覆驗，非轉述）**：run [`34317606227`](https://github.com/shihpc/postmkt/actions/runs/34317606227)
  （`c44937b`）的 build 步驟 log 逐字為 `TaiwanStockInfo: 3147 檔對照`、
  `TaiwanStockDayTrading: 2026-09-08 -> 2079 筆；TaiwanStockPrice -> 45675 筆`、
  `market_daily：宇宙 2724 檔`、`輸出 …/data/postmkt.json（1,707,249 bytes）`。**基準日 2026-09-08**。
  （該 run 整體 conclusion 是 failure，但失敗的是最後的 `Commit & push`（分支落後遠端），
  build 步驟本身 success——結論可用。）
- **✅ 真實建置實測（本節規則實際跑出來的結果，2026-09-09 補記）**：run
  [`34321284815`](https://github.com/shihpc/postmkt/actions/runs/34321284815)（head_sha `ec50d80`，
  2026-09-09T06:55Z 起跑）的 build 步驟 log 逐字兩行——
  `market_daily：宇宙 2757 檔（TaiwanStockPrice 45675 列、TaiwanStockInfo 3147 檔對照）`、
  `輸出 /home/runner/work/postmkt/postmkt/data/postmkt.json（1,706,347 bytes）`。
  **基準日 2026-09-08**（同 run `TaiwanStockDayTrading: 2026-09-08 -> 2079 筆`）。該 run 整體
  conclusion 同樣是 failure，失敗的一樣是最後的 `Commit & push`（feature branch 落後遠端），
  **build 步驟本身 success**，數字可用。
- **宇宙 2,757 檔：點預測分毫不差** ✅。預測式＝2,724 ＋ 12（DR／REIT／`2887Z1`，`8dc1f0b`
  放行的）＋ **21（ETN）**；兩組加項都是**逐檔實打
  `TaiwanStockPrice&data_id=…&start_date=end_date=2026-09-08`** 得到的（不是沿用上一節的數字）：
  34 檔中 12 檔當日有列（`01001T`／`01002T`／`01004T`／`01007T`／`01009T`／`2887Z1`／`910322`／
  `910861`／`911608`／`911622`／`911868`／`912000`，與上一節逐檔相符）；48 檔 ETN 中 **21 檔**
  當日有列（`020000`／`020001`／`020011`／`020012`／`02001L`／`020020`／`020025`／`020028`–`020041`）。
- **❌ 全檔的「點預測」被證偽（原寫 1,708,100–1,708,240 bytes ≒ 1.708 MB）**：那個區間是把新增
  33 列以 `json.dumps(separators=(",",":"))` 逐列實算（858 B 全 null ～ 990 B）加在錨點上得到的。
  **實測 1,706,347 bytes，比預測下界還低 1,753 bytes（−0.10%）**。
  **成因不在 `market_daily`、也不在宇宙規則，在 `oddlot` 區塊**：兩個 run 的 FinMind 輸入逐項相同
  （`TaiwanStockInfo 3147`／`TaiwanStockPrice 45675`／`TaiwanStockDayTrading 2079`／
  `InstitutionalInvestorsBuySell 108338`／`Shareholding 2371`／`MarginPurchaseShortSale 2217`／
  `SecuritiesLending 884`／`ShortSaleBalances 2232`／`BlockTrade 30`，兩份 log 逐行比對），
  **唯一不同的是 TWSE 盤後零股 `TWT53U`：錨點 run 取到 `2026-09-08`、本 run 取到 `2026-09-09`**
  （兩者都是 1368 筆，但是不同一天的內容，代號與金額都不同 → 序列化長度不同）。`TWT53U` 餵的是
  `build_oddlot()` 的盤後零股段（`build_postmkt.py` grep `TWT53U`），與 `market_daily` 無關。
- **教訓：全檔 byte 數不可做點預測**。`postmkt.json` 是十幾個區塊合成的單一檔案，**任一區塊
  當天的內容都會左右全檔長度**，所以「同一天同一份輸入」這個前提對全檔並不成立
  （TWSE 端點各自回自己最新的一天，甚至同一天跑兩次也可能不同）。點對點的 byte 預測只在
  **區塊層**做得到；全檔一律只給區間。
- **日常區間（仍成立，且現在有兩次真實建置背書）**：宇宙 **2,730–2,830 檔**、全檔
  **1.70–1.72 MB**。`c44937b` 的 2,724 檔／1,707,249 B 與 `ec50d80` 的 **2,757 檔／1,706,347 B**
  體積都落在區間內（前者檔數低於下界 6 檔——那一版還沒納入 ETN，屬預期內）。ETN／DR／REIT
  每天有無成交不同，其餘區塊本來就有逐日變動。真實建置落在 2.7 MB 或 1.65 MB 附近都代表改動沒生效。

**⚠ 前端階段的必要條件（已寫進 `README.md`，這是本次的重點之一）**：**權證必須留在黑名單**
（4.5 萬檔，納入會讓檔案再爆到 2,719,486 bytes），所以**「本表不涵蓋這個代號」這個狀態必然存在**，
不是這次或下次能消滅的。因此前端消費 `market_daily` 時，**「代號不在 `rows` 裡」不可一律呈現成
「查無此代號（已下市／停牌／代號有誤）」**——那對持有權證的使用者是**說錯話**。
涵蓋／不涵蓋的完整清單與判別方式見 `README.md`「**前端消費 `market_daily` 的必要條件**」節。
（由來：入口站 shihpc.github.io「我的異動」明文要求三種狀態「必須分得開」，把「資料源不涵蓋」
混進「查無此代號」正是同型的錯誤。）

**`2887Y` 殘留錯誤敘述的更正**：全 repo 掃描（`README.md`／`CHANGELOG.md`／`build_postmkt.py`
註解與 docstring）**已無任何一處拿 `2887Y` 當實例**——`8dc1f0b` 已就地改成 `2887F`。僅剩的兩處
在 `CHANGELOG.md` 的兩段更正註記裡，且原文仍寫「`2887Y` 是**特別股**不是存託憑證」——這句
**本身也錯**（該代號在 `TaiwanStockInfo` 3,147 檔中零命中，本次以全表再次覆驗），故兩處一併改為
「`2887Y` 這個代號根本不存在，正確的單字母後綴特別股實例是 `2887F`」。

**測試**：
- 新增／改寫 `test_market_daily_universe_includes_etn_excludes_warrants`（取代原
  `..._excludes_warrants_and_etn`）：ETN 三種寫法必須**在**宇宙內、權證四例必須**不在**，
  並直接對 `bp.RE_MARKET_EXCLUDE` 釘住「`02` 開頭不得命中、`03`–`09`／`7` 開頭必須命中」。
- fixture 調整：新增 `_MD_ETN`（`020041`／`02001L`／`020019U`）並併入 `_md_universe()`；
  `030018`／`715001` 補進 `_md_nm()`（原本不在 `nm`，等於是被 `nm` 閘門擋掉的假陽性，
  現在擋它們的確定是黑名單）。`020019U` 保留為**形狀層守門**——FinMind 沒有這種寫法
  （全表零命中），它守的是「`\d{6}U` 那條分支確實已拿掉」。
- `..._no_false_reject_on_real_postmkt_corpus`（母體＝repo 內 `data/postmkt.json` 各區塊代號
  聯集 2,284 檔）同步改為「被擋的只能是 `03`–`09`／`7` 開頭的權證型態」，並新增反向斷言
  「自家資料裡若出現 `02` 開頭的 ETN 必須通過」。

**`lending` 一個 byte 都沒動**：`git diff 8dc1f0b -- build_postmkt.py` 的三個 hunk 全部落在
模組層 regex 註解／定義與 `build_market_daily()` 內（`build_lending`／`stock_names`／`_agg_*`
一行未動）。另以同一份 fixture 跑 `8dc1f0b` 與本次，`PYTHONHASHSEED` 取 0／1／2 各一次，兩種輸入
都逐位相同：離線輸入（`date=""`）**672 bytes**、真實輸入（`date="2026-09-08"`，會實打 TWSE
SLB/NLB 全市場借券餘額）**1,227,628 bytes**。

**突變測試（自測，六種全紅）**：①`market_daily` 移到 `out` 第一個 key → 2 紅；
②`rows_out[:TOP_N]` → 7 紅；③拿掉宇宙過濾 → 5 紅；④拿掉基準日過濾 → 1 紅；
⑤`RE_MARKET_CODE` 退回舊白名單 → 7 紅；⑥**`RE_MARKET_EXCLUDE` 退回擋 ETN**
（`0[2-9]`＋`\d{6}U`）→ 5 紅（本次新增的守門確實守得住回退）。

## 2026-09-09（同日修正之二）`market_daily` 宇宙：代號型態由白名單改成**黑名單**，`nm` 升為主閘門

**症狀（獨立驗收抓到，屬相對 `e96c5d8`（全收）的覆蓋率退步）**：上一節把代號型態當白名單
（`^(?:[1-9]\d{3}[A-Z]?|00\d{2,4}[A-Z]?)$`），會把**真的可以被持有的證券**擋在底表之外。
被擋掉的代號在前端會被呈現成「**查無此代號（已下市/停牌/代號有誤）**」，而不是「資料源不涵蓋」
——正是這個區塊當初要消滅的坑。

**證據（刻意不用 taiwan-flows 的 2,650 檔當測試集）**：那份母體是用幾乎同一把尺
（`build_meta.py` 的 `RE_STOCK`／`RE_ETF`）篩出來的，拿它驗本 regex 是**循環論證**，必然回報
0 誤擋。改用 **postmkt 自己 `data/postmkt.json` 各區塊（`lending.rows`／`oddlot`／`daytrading`／
`blocktrade`／`margin`／`short_balance`）代號的聯集共 2,284 檔**當回歸母體，舊規則誤擋 **7 檔**：

| 代號 | 名稱 | 類別 | 佐證 |
|---|---|---|---|
| `910322`／`910861`／`911868`／`912000` | 康師傅-DR／神州-DR／同方友友-DR／晨訊科-DR | 存託憑證 | 都在 `lending.rows` 且 `n` 非空（`n` ＝ `nm.get(c,"")`，非空即證明在 `nm` 內）、`px` 來自餵給 `build_market_daily` 的同一份 `price_rows` |
| `01002T`／`01004T` | 土銀國泰R1／土銀富邦R2 | REIT 受益證券 | 在 `oddlot`；另 2026-09-09 直打 FinMind `TaiwanStockPrice&data_id=` 2026-09-08 確認**有價**（13.02／10.04），且在 `TaiwanStockInfo` 內（`industry_category` ＝「受益證券」） |
| `2887Z1` | 台新新光己特 | 雙字元後綴特別股 | 在 `oddlot`；同上實打有價（22.2）、在 `TaiwanStockInfo` 內。同一檔金控的 `2887F` 卻通過白名單——**規則本身的破口** |

**修法**：`nm`（`TaiwanStockInfo`）升為**主閘門**，代號型態只當**黑名單**。

- **體積本來就是 `nm` 解決的**：45,675 → ≤3,147 這一刀是它砍的，代號型態不需要、也不應該
  當白名單。
- **黑名單仍然必要（`nm` 單獨當閘門不夠）**：2026-09-09 拉 `TaiwanStockInfo` 全表實測，
  3,147 檔裡混了 `industry_category` 為「所有證券」的**權證 36 檔**、**ETN 48 檔**
  （`industry_category` ＝「ETN」**28**＋「指數投資證券(ETN)」**20**；**2026-09-09 就地更正：
  原文寫成「20＋28」，兩個數字對調了，總數 48 無誤——本次重新匿名拉 `TaiwanStockInfo` 全表
  逐項計數覆驗，且同檔「同日修正之三」那段本來就是對的**）、以及 `Index`／`大盤` 的
  **產業別／指數偽代號 32 筆**
  （`TAIEX`／`TPEx`／`Semiconductor`…）。其中權證 `710553` 實打 2026-09-08 在
  `TaiwanStockPrice` **有價**（0.46）→ 真的會漏進來。
- **新規則**（`build_postmkt.py`，grep `RE_MARKET_EXCLUDE`）：
  - `RE_MARKET_CODE = ^\d[0-9A-Z]{2,7}$`（數字開頭的英數＝擋掉 `TAIEX` 那類偽代號）
  - `RE_MARKET_EXCLUDE = ^(?:0[2-9]\d{3}[0-9A-Z]|7\d{4}[0-9A-Z]|\d{6}U)$`
    （6 碼且首兩碼 `02`–`09` ＝ ETN 與上市權證；`7` 開頭 6 碼 ＝ 上櫃權證，含 `73107P`；
    `\d{6}U` ＝ 帶 U 的 ETN 寫法。**刻意不含 `00`（ETF：`0050`／`006201`／`00637L`）與
    `01`（REIT：`01002T`）**）
  - 條件順序改成 `c not in nm or not RE_MARKET_CODE.match(c) or RE_MARKET_EXCLUDE.match(c)`
- **取捨方向固定**：寧可多放幾檔（多幾十列、不到 1KB），不可少放一檔（少放＝使用者的持股
  從底表消失，並被誤述為「查無此代號」）。
- **新舊規則對 `TaiwanStockInfo` 全表逐檔對跑**：新規則多放行 **34 檔**＝存託憑證 25＋
  受益證券 8＋`2887Z1` 1，**沒有任何一檔由通過變成被擋**（零回歸）。

**⚠ 已知代價，需前端配合（管線端不打算解決）**：**ETN 是可以被持有的證券**（`nm` 內 48 檔，
FinMind 實際代號是 `020041`／`02001L` 這種**不帶 U** 的寫法——2026-09-09 逐檔實打
`TaiwanStockPrice` 確認，上一節寫的「ETN ＝ 6 碼＋U」只對其中一種來源的寫法）。本次依既有
決策把 ETN 排除，於是持有 ETN 的使用者在前端會看到「查無此代號」，而該文案語意是
「已下市／停牌／代號有誤」——**與事實不符**。管線端無法區分「不在底表」與「不存在」，
**前端必須另備「資料源不涵蓋」的說法**（前端階段處理；本次未動 `index.html`）。
若日後裁定 ETN 應納入底表，只要把 `RE_MARKET_EXCLUDE` 的 `0[2-9]` 改成 `0[3-9]`、拿掉
`\d{6}U` 即可（權證仍擋），代價約 +48 列／+1.3KB。

**體積與宇宙重新估算（取代上一節的 2,600–2,950 檔／1.70–1.76MB）**：以 CI run
`34317606227`（`c44937b`，build 步驟 success）的**真實建置**為基準——宇宙 2,724 檔、
全檔 **1,707,249 bytes**。新規則多放行的 34 檔中，逐檔實打 `TaiwanStockPrice`
（2026-09-08）確認**有 12 檔當日有列**（`01001T`／`01002T`／`01004T`／`01007T`／`01009T`／
`2887Z1`／`910322`／`910861`／`911608`／`911622`／`911868`／`912000`），其餘 22 檔當日無成交。
故**同一天同一份輸入下的預測**：宇宙 **2,736 檔**、全檔約 **1,707,600 bytes**
（12 列 × 約 25–30 B，`json.dumps(separators=(",",":"))`）。日常區間：宇宙 **2,700–2,800 檔**、
全檔 **1.70–1.72 MB**（10^6 進位；DR／REIT 有無成交每天不同，其餘區塊本來就有逐日變動）。

**必修 2：文件與程式不符（本次一併修）**：`README.md` 與 `CHANGELOG.md` 上一節原寫
「唯一放寬處是……單一字母後綴（特別股／**存託憑證**，例如 `2887Y`）」——**`2887Y` 這個代號
根本不存在**（2026-09-09 實查 `TaiwanStockInfo` 3,147 檔零命中，同一檔金控現存的是
`2887F`／`2887Z1`；2026-09-09「同日修正之三」再次以全表覆驗，結論相同）——它既不是特別股的例子、
更不是存託憑證的例子，正確的單字母後綴特別股實例是 `2887F`；
真正的存託憑證 `91xxxx` 在該版規則下**全部被擋**；`README.md` 的「個股＋ETF 全保留」也不成立
（DR／REIT／雙字元後綴特別股當時全被擋）。兩處已改寫，錯誤敘述在上一節留有就地註記。

**測試**：
- `test_market_daily_universe_keeps_dr_reit_and_preferred_shares`：7 檔誤擋案例＋`2887F` 對照組
  逐檔釘住必須在宇宙內。
- `test_market_daily_universe_excludes_warrants_and_etn`：`030018`／`715001`／`710553`／`73107P`
  （權證）、`020019U`／`020041`／`02001L`（ETN 兩種寫法）、`TAIEX`（偽代號）必須被擋——
  **fixture 把它們全部放進 `nm`**（因為真實 `TaiwanStockInfo` 就是這樣），所以擋下它們的
  必然是黑名單而不是 `nm` 閘門。
- `test_market_daily_universe_gate_is_stock_info_then_blacklist`：證明 `nm` 是主閘門
  （`7654` 加進 `nm` 就會收），以及「不在黑名單的新型態一律放行」（`1234X9`）。
- `test_market_daily_universe_no_false_reject_on_real_postmkt_corpus`：以 repo 內
  `data/postmkt.json` 各區塊代號聯集（2,284 檔）當回歸母體，斷言**形狀閘門一檔都不擋**，
  被擋的只能是黑名單命中的商品類。

**`lending` 逐位未受影響**：`git diff` 顯示本次改動全部落在模組層 regex 定義與
`build_market_daily()` 內（`build_lending()`／`stock_names()` 一行未動）；另以同一份 fixture 跑
改前（`c44937b`）／改後，`PYTHONHASHSEED` 取 0／1／2 各一次，`lending` 輸出（列序以代號排序後）
**逐位相同（751 bytes）**。

**突變測試（自測，五種都會紅）**：①`market_daily` 移到 `out` 第一個 key → 2 紅；
②`rows_out[:TOP_N]` → 7 紅；③拿掉宇宙過濾 → 5 紅；④拿掉基準日過濾 → 1 紅；
⑤`RE_MARKET_CODE` 退回舊白名單 → 6 紅（新增的宇宙守門確實守得住回退）。

## 2026-09-09（同日修正）`market_daily` 宇宙收斂：`TaiwanStockPrice` 單日就含 4.5 萬列權證

**症狀**：帶真實 `FINMIND_TOKEN` 的第一次真實建置（CI run `34315933248`，ref 為本分支，
build 步驟 success）輸出 `data/postmkt.json` **2,719,486 bytes**，而 main 上同期檔案約
1,652,000 bytes ——實際增量 **+1,067,000 bytes（+65%）**，與下一節估算的 +56KB／+3.4% 差 19 倍。

**成因（已判定：非重複列，而是宇宙本身就含非個股商品）**：

- 同一份 log 印出 `TaiwanStockPrice -> 45675 筆`（`fetch_daytrading()` 的 print）。台股權證／ETN
  數以萬計，**FinMind `TaiwanStockPrice` 單日全市場切片本來就包含它們**；同 log 的
  `TaiwanStockInfo: 3147 檔對照` 則只有 3,147 檔 —— 兩者差的 4 萬多列就是權證等非個股商品。
- **不是「抓了多天」造成的重複**：`r_price_lend` 只會是 `fetch_daytrading()` 內
  `api_get("TaiwanStockPrice", start_date=d, end_date=d)` 的結果，或 `main()` 內同樣
  `start_date=end_date=lend_date` 的單日查詢（`build_postmkt.py` 該兩處），而 `src/fmclient.py`
  的 `api_get()` 是單次請求、沒有分頁也沒有日期迴圈。算術也對不上：`45675 / 2650 ≈ 17.2`，
  而回退上限只有 5 天。**每列約 23.4 bytes ×45,675 ≒ 1.07MB**，與實測增量相符 →
  45,675 列**全部**進了 `market_daily.rows`。
- 上一節的體積估算方法本身沒錯（拿 taiwan-flows 2,650 檔重建同形狀區塊），**錯在程式的宇宙
  從來就不是那個母體**——估算與實作用了不同的宇宙，才會差 19 倍。

**修法（沿用家族既有機制，不自創）**：`build_market_daily()` 的宇宙改成
**當日 `TaiwanStockPrice` ∩ `TaiwanStockInfo`（本管線既有的 `nm`，3,147 檔對照）
∩ `RE_MARKET_CODE`**。`RE_MARKET_CODE` 沿用 taiwan-flows `src/build_meta.py` 的母體定義
（`RE_STOCK`／`RE_ETF`）＋`pipeline.build_rows()` 的「只收母體，排除權證等」，唯一放寬處是
一般股 4 位數後允許單一字母後綴（特別股，例如 `2887F`）。另加「只留基準日那列＋依代號去重」
（列有 `date` 才比對），防日後改成多日切片時把不同天的同一檔重複寫進來。

> **⚠ 本節這段修法在同日被下一節推翻（見「同日修正之二」）**：把代號型態當**白名單**會誤擋
> 存託憑證／REIT／雙字元後綴特別股。上面原文寫的「單一字母後綴（特別股／**存託憑證**，例如
> `2887Y`）」有兩個錯：①**`2887Y` 這個代號根本不存在**（2026-09-09 實查 `TaiwanStockInfo`
> 3,147 檔零命中，同一檔金控現存的是 `2887F`／`2887Z1`）——所以它既不是特別股的例子、
> 更不是存託憑證的例子，正確的單字母後綴特別股實例是 `2887F`；②真正的存託憑證是
> `91xxxx` 六碼，在該版規則下**全部被擋**。原文已就地改為 `2887F`，錯誤敘述保留在此註記中。

- **ETF 完整保留**（這個區塊存在的唯一理由就是全市場覆蓋，不是為了縮小體積）：`00` 開頭含字母
  後綴（`00637L`／`00981A`）全在母體內，測試逐檔釘住。權證／ETN 排除。
- **健全性觀測**：建置時印 `market_daily：宇宙 N 檔（TaiwanStockPrice M 列、TaiwanStockInfo K 檔對照）`，
  低於 `MARKET_DAILY_MIN_ROWS`（2000）另印警告但不中斷（有資料比沒資料好，但要看得見）。
- **體積重估（估算，非真實建置產出）**：以 taiwan-flows `data/daily/20260907.json` 的 2,650 檔
  重建同形狀區塊 → 區塊 raw **53,511 B**（每列 20.19 B）／gzip 16,891 B；併進現行
  `data/postmkt.json`（1,652,453 B）後 raw **1,705,980 B（+3.24%）**、gzip 269,942 → 287,509 B。
  宇宙若到 2,950 檔則區塊約 59.6KB。**對真實建置的預測**：`market_daily` 約 **2,600–2,950 檔**、
  區塊 **53–62KB**，全檔約 **1.70–1.76MB**（其餘區塊本來就有逐日變動，故給區間）。
  真實建置落在 2.7MB 或 1.65MB 附近都代表修法沒生效。

**同批補上獨立驗收指出的 5 項必修**：

1. **檔頭契約守門測試**（原本 104 支測試對「把 `market_daily` 移到 `out` 第一個 key」**全數通過**）：
   新增 `test_output_head_contract_date_and_generated_at_first`，以離線 fixture 跑真正的 `main()`，
   斷言 `list(out)[:2] == ["date","generated_at"]`，並對 `json.dumps` 後的**前 2048 bytes** 跑與兩個
   消費端**逐字相同**的 regex（taiwan-flow-live-v2 `worker/src/index.js` 的 `extractHeadFields`＋
   `fetchStatusHead(bytes = 2048)`、claude-harness `tools/freshness_watchdog.py` 的
   `HEAD_BYTES = 2048`），比對結果須等於 `out["date"]`／`out["generated_at"]`。
2. **「不截斷、全市場」守門測試**（原本 fixture 只有 6 檔，遠低於 `TOP_N = 50`，
   「改成 `rows_out[:TOP_N]`」的突變**全數通過**）：fixture 補到 **67 檔（> TOP_N）**，
   `test_market_daily_is_not_a_ranking_no_truncation` 斷言 `len(rows) == 宇宙檔數`（不是 `> 0`），
   並另有一支跑完整 `main()` 的版本。
3. **`docs/date-semantics.md` 補 `market_daily.date`**（該檔是跨五站唯一對照表）：其值＝
   `lending.date`（`lend_date`），**與最上層 `date`（各段取 max）語意不同、值可能不同**，
   消費端一律讀區塊自己的 `date`。
4. **`README.md` 的「（見「外部消費者」）」指向不存在的章節**：改成明寫該契約本身（兩個消費端、
   Range 檔頭 2048 bytes、regex 撈第一個 `date`／`generated_at`、守門測試名稱），並指出它與
   `CLAUDE.md`「不可破壞的約定」第 7 條屬同一組跨 repo 依賴——**第 7 條只寫了 Worker 輪詢
   raw main 鏈式觸發下游，沒有涵蓋這條檔頭契約**。
5. **`lending.foreign_vol` 與 `market_daily.f` 的刻意不一致（本節即為書面紀錄）**：
   `build_lending()` 對法人資料**沒有**日期守門（無條件用 `inst_by_c`），`build_market_daily()`
   有（法人資料日 ≠ 基準日 → `f`／`t` 整欄 `null`）。**所以法人資料落後的那一天，融借券 tab 會
   顯示某檔外資 +N 張，持股異動同一檔顯示「—」。這是刻意的（新區塊較嚴、寧缺勿混），不是 bug。**
   `build_lending` 的舊行為不改：它的欄位受「三處一致」約定與 parity 測試綁死，改它是另一件事。
   程式端 `build_market_daily()` docstring 亦有原地註解。

**`lending` 逐位未受影響**（本次未動它一行）：以同一份 fixture 跑改前（`e96c5d8`）／改後，
`PYTHONHASHSEED` 取 0／1／2 各跑一次，輸出（列序以代號排序後）逐位相同（2,447 bytes）。

**突變測試（自測，四種都會紅）**：①`market_daily` 移到 `out` 第一個 key → 2 紅；
②`rows_out[:TOP_N]` → 6 紅；③拿掉宇宙過濾（權證全收）→ 5 紅；④拿掉基準日過濾 → 1 紅。

## 2026-09-09 `postmkt.json` 新增 `market_daily` 全市場逐檔精簡區塊（管線階段）

入口站 `shihpc.github.io` 的「我的異動」要搬進本站成為新 tab，它需要**任一持股**的三個數字：
漲跌%／外資買賣超(張)／投信買賣超(張)。站內既有資料不夠：`diag.json` 只有 1200 檔（45.3%）
且無單日法人張數（只有 5 日合計 `f5`／`t5` 與連買天數）；`postmkt.json` 的 `lending.rows`
雖有 2232 檔法人張數，但**完全沒有漲跌%**，且宇宙是「有借券／融資融券活動」的聯集
（`codes = set(sys_bal) | set(otc_bal) | ...`），純現股會缺席。

**做法：讓 `postmkt.json` 自給自足，不新增對 taiwan-flows 的跨 repo 依賴。**

- **不擴大 `lending.rows`**：那是依借券餘額排序的排行，擴大宇宙會污染「融借券」tab，
  也會動到 `augmentLending()`／`_augment_lending()` 三處一致的約定與既有 parity 測試。
  改為新增**獨立區塊** `market_daily`（`build_postmkt.build_market_daily`）。
- **區塊名 `market_daily` 的理由**：它不是排行（其餘區塊都是），而是「全市場×單日」的
  逐檔底表；形狀與命名比照 taiwan-flows `data/daily/<d>.json` 的 `{date, cols, rows}`
  欄式二維陣列，跨站對應一眼看得出來。`cols` ＝ `["c","chg","f","t"]`。
- **零額外 API 呼叫**：漲跌%取自建置時已在手的全市場 `TaiwanStockPrice`
  （`r_price_lend`，與 lending 同基準日 `lend_date`），法人張數取自已抓的 `r_inst`。
  漲跌%算式與當沖 tab **共用同一個 `_chg_pct()`**（由 `build_daytrading` 原地抽出，
  行為不變），不各寫一份。
- **缺資料寫 `null`、不寫 0**（刻意與 `build_lending` 不同）：`build_lending` 的
  `inst_by_c.get(c, {"foreign": 0, ...})` 把「查不到這檔的法人資料」與「法人真的沒買賣」
  寫成同一個 0。這個 tab 要判讀的正是「有沒有異動」，**缺資料被呈現成無異動**就是入口站
  舊版踩過的坑（舊版只讀 `latest.json` 各榜前 30，911 檔達門檻者有 687 檔被寫成「無顯著異動」），
  故一律 `null`。法人資料日 ≠ 基準日時 `f`／`t` 全留 `null`（寧缺勿混，同 `dt_*` 的處理）。
- **`market_daily` 放在 `out` 的最後**：taiwan-flow-live-v2 的 Worker `/status` 對本檔走
  Range 只取檔頭（`fetchStatusHead`，預設 2048 bytes）再 regex 撈**第一個** `"date"` 與
  `"generated_at"`，新區塊插到那兩個 key 之前會讓它撈到錯的日期。程式該處有原地註解。
- **體積**（以 taiwan-flows 2026-09-07 全市場 2650 檔重建同形狀區塊估算，非真實建置產出）：
  區塊 raw 56,315 B／gzip 17,263 B；全檔 raw 1,651,880 → 1,708,211（+3.41%）、
  gzip 270,522 → 288,384（+6.60%）。
- **`lending` 逐位未受影響**：同一份 fixture 跑改前／改後（固定 `PYTHONHASHSEED`）逐位相同。
  順帶記下一個**既有、非本次造成**的觀察：`build_lending` 的 `codes` 是 `set`，
  借券餘額同值（例如都為 0）時列序會隨 `PYTHONHASHSEED` 變動——舊版自己跑兩次不同 seed
  也會不同。不在本次範圍，未動。

**本階段只做 Python 管線＋離線測試，未碰 `index.html`**；「持股異動」tab 另案。
新增測試 5 支於 `tests/test_postmkt_build.py`（形狀／漲跌%與當沖同算式／缺法人為 null 不為 0／
資料日不一致留空／不影響 lending）。

## 2026-09-07 個股摘要側欄 v1（批次三 #15 後半）

批次三 #15 的完成判準是「URL 狀態（hash 路由）→ 個股摘要側欄 v1（摘要＋跨站深連結，**不重抓**）」，
hash 路由那半已於同日先行（commit 9812437），本次補上側欄。

**入口**：個股列表的代號旁多一個 `▤` 小鈕（`stkBtn`，掛在共用 `nameCell` 與選股／分點／持股診斷三處），
**不奪走任何既有互動**——融借券點列本體照樣展開明細、選股 tab 的 Yahoo 連結照樣可點、持股診斷卡標題照樣開合
（兩個外層 `.clk` 處理器加了「點到 `[data-stk]` 就讓路」的守衛）。分點「單點」結果的鈕掛在名稱欄而非代號欄，
因為代號欄是 `.mtable-s2` 的 62px 凍結欄（`nowrap`+`overflow:hidden`），塞進去會被裁掉。

**內容**：只讀**已在記憶體**的資料集，**開側欄不發任何網路請求**（Playwright 監看 `page.on('request')`
實測新增請求數＝0）。段落＝報價／診斷素材庫（價量・籌碼・基本面）／融借券整合／當沖排行／融資排行／
短部位排行／鉅額／零股盤中盤後／主動ETF 加減碼與持有／分析師預估，**每段自帶自己的資料日**
（各 dataset 的 date 本來就會不同，見 `date_mismatch`）。未載入的資料集整段不出現、不為此補抓；
`stkOpen()` 刻意只重繪側欄而非呼叫 `render()`（`render()` 會替當前 tab 觸發 `ensure*()`）。

**跨站深連結**（純導覽 `<a target="_blank" rel="noopener">`，不 fetch，**故不需新增 CSP `connect-src`**）：
只用 2026-09-07 curl 線上 index.html 實查確認支援的格式——taiwan-stock-news 有 hash 路由，
`#tab=track&code=`／`#tab=news&q=` 可用；**taiwan-flows 與 taiwan-flow-live-v2 全檔 grep
`location.hash` 零命中＝沒有 hash 路由**，故只連首頁並在說明列註明「需自行搜尋該檔」，
不編造不存在的深連結格式。另附 Yahoo 技術分析與三條本站 hash 深連結（融借券／持股診斷／分點）。

**URL 狀態**：新 hash key `stock=`，**刻意與既有 `code=` 分家**——`code=` 的語意已被 lending（展開列）／
broker（查詢 id）／diag（聚焦持股卡）三個 tab 各自佔用，而側欄跨 tab 都能開，混用會讓同一把 key 有兩種意思；
兩者可並存（例 `#tab=lending&code=2330&stock=2454`）。讀入同樣白名單＋型別檢查（4–6 位大寫英數），
寫出走 `history.replaceState`（實測開關側欄 `history.length` 不變）。ESC 與點遮罩可關閉；
本站深連結不帶 `stock=`，`applyHash` 因此順帶關閉側欄。持股清單絕不進 hash 或任何請求（約定 6 不變）。

驗收（Playwright 本機 `http.server`）：13 tab 逐一點擊 console error 0／pageerror 0；開側欄新增請求 0；
375px 六個 tab `scrollWidth <= innerWidth`；股名／產業名注入 `<img src=x onerror>` 後 `window.__xss`
未定義、側欄 `<img>` 數 0、以字面文字顯示。

## 2026-09-07 持股清單匯出／匯入／清除（批次三 #2）

持股診斷 tab「我的持股」區塊新增三個按鈕（`index.html` 的 `diagInputHtml`），**全部在本機瀏覽器完成、
不送往任何網路端點**（CLAUDE.md 約定 6；Playwright 監看全部 request 的 URL／body 無持股代號）：

| 按鈕 | 做法 | 程式 |
|------|------|------|
| ⬇ 匯出 | `Blob`→`<a download>`，檔名 `pm_holdings_YYYYMMDD.json`，內容 `{schema:"pm_holdings/1", exported_at:ISO, holdings:[{c,sh,cost}]}` | `holdExportPayload`／`holdExport` |
| ⬆ 匯入 | `<input type=file>` 讀本機檔 → `holdParseImport` 純函式嚴格驗證（頂層物件、`schema` 必等於 `pm_holdings/1`、`holdings` 為陣列、每筆 `c` 4–6 位英數、`sh`／`cost` 為 null 或 ≥0 有限數、代號不重複）；任一不合即整檔拒絕、顯示原因、**既有清單不覆蓋**；成功則取代清單並立即重繪 | `holdParseImport`／`holdImportFile` |
| ✕ 清除 | `confirm()` 後清空 `pm_holdings`（取消不動） | click handler `[data-hold-clear]` |

順手修：持股表 5 欄在 375px 超寬（既有問題，拿掉新按鈕列仍溢出），包一層 `overflow-x:auto`。
Playwright 驗過：假持股→匯出（攔 download 讀內容）→清除→匯入同檔恢復且 diag 卡片重繪；六種壞檔
（schema 錯／代號含 `<`／非 JSON／股數型別錯／頂層陣列／代號重複）皆顯示錯誤且原持股不變；pageerror 零。

## 2026-09-07 URL 狀態（hash 路由，批次三 #1）

原本無任何 hash／pushState 路由，重新整理一律回「摘要分析」。現在 `location.hash`＝
`#tab=<13 tab 之一>&code=<代號>&sub=<子分頁>`，只放非預設值（預設 insight 時 hash 為空）。
程式在 `index.html` 的 `// ---------- URL 狀態（hash 路由` 區塊：`parseHash`（白名單／型別檢查：
tab 必在 `TABS`、sub 必在該 tab 允許值、code 為 4–6 位大寫英數，非法值靜默退回預設）→
`applyHash`（載入與 `hashchange` 時套進 state）→ `currentHash`／`syncHash`（每次 `render()` 末尾
以 `history.replaceState` 寫回，不塞歷史堆疊、不觸發 hashchange）。

| tab | 子狀態 | 行為 |
|-----|--------|------|
| oddlot | `sub=intraday\|after` | 盤中／盤後子分頁 |
| broker | `sub=branch\|stock\|list`＋`code=` | 有 code 無 sub 視為股票走「個股」；查詢框預填 `state.bkPending`，`state.pm` 就緒且有 FinMind token 才自動送出一次（無 token 只預填、不 alert） |
| lending | `code=` | 展開該檔明細（`state.openLend`） |
| diag | `code=` | 在持股→展開該卡並捲到位（入口站「我的異動」連 `#tab=diag&code=<代號>`）；不在持股→提示＋預填新增欄，不炸。持股清單本身絕不進 hash |

與批次二懶載相容（切到需要資料的 tab 仍由 `render()` 觸發 `ensurePm()` 等）。Playwright 驗過：
`#tab=lending` 直落借券且表格有資料、`#tab=broker&code=2330` 帶入並送出（FinMind mock）、
`#tab=diag&code=2330` 聚焦／不在持股提示、切 tab 與子分頁 hash 更新且 reload 保留、`hashchange`＋
goBack、非法值退回預設、13 tab pageerror 零、375px 不溢出。

## 2026-08-30 自動彙總場補寫 `synthesis.model`（費用估算最後一塊缺口）

上一則記錄的「未補的一項」——`data/summary/*.json` 的 `synthesis` 只有 `{text, usage, via}`、
缺 `model`，導致前端 `sumResultHtml` 在自動場刻意不顯示彙總本身的費用估算——本次補齊。
**只動 `build_summary.py`，`index.html` 零改動**（前端本來就讀 `sy.model`，缺席才回空字串）。

**做法是把「這次實際呼叫用的 model」沿著兩條路徑帶回來，而不是在落地時寫 `SYNTH_MODEL`
字面量**——彙總有 batch 主路徑與同步回退兩條路，硬套常數等於再一次「從程式碼推論」：

| 位置 | 改動 |
|------|------|
| `call_claude_retry` | 成功與 `ok:false` 佔位一律回傳 `model`＝這次送出的模型 |
| `call_claude_batch` | 每筆成功結果附 `model`＝`reqs[cid]` 該筆送出時用的模型（逐筆各自記） |
| `main()` 彙總段 | `write_output` 的 payload 加 `"model": synth.get("model")`，取自 synth 本身 |

`six[]` 原本就有 `model`（前端 `s.model` 早已可用），本次兩路回傳的 `model` 展開後為
**同值覆蓋**（`reqs[f"s{i}"]` 與 `jobs[i]` 是同一個 `model` 變數），既有欄位值不變。
`synthesis` 也只新增 `model`，`text`／`usage`／`via` 原樣。

寫進去的字串是**送出請求時用的模型別名**（`claude-opus-4-8`／`claude-sonnet-5`），
不是 API 回應裡可能被解析成帶日期版本的 `message.model`——因為前端 `INSIGHT_PRICES`
以別名為鍵，寫回帶日期的 id 會讓 `insightCostText` 靜靜回空字串。新增測試
`tests/test_summary_model_field.py` 有一條就在守這件事（比對 `SYNTH_MODEL`／
`SUMMARY_MODELS` 是否都在 `index.html` 的 `INSIGHT_PRICES` 鍵集合內）。

未觸及 `gather_*`（index.html gather 的 Python 移植副本）與 `SYS_*`（唯一事實來源＝
index.html），三站同步約定不受影響。

## 2026-08-30 「本次 API 費用估算」補到摘要分析其餘場次（三站）

2026-08-27 首次上線的費用估算只掛在**單發**摘要分析（postmkt `691226a`／
taiwan-flow-live-v2 `737d9b2`／taiwan-stock-news `04c4d78`，當時明記「其餘場次未加」）。
本次補齊，**全部重用既有的三站同步函式 `insightCostText`，未產生任何變體**：

| 場次 | 位置 | 本次 |
|------|------|------|
| 單發摘要分析 | 三站 `insightHtml`／`renderInsight` | 08-27 已有 |
| 雲端歷史（單發存檔） | 三站 `cloudHistSectionHtml` | **補上**（`entry.model`＋`entry.usage` 皆在） |
| 彙總場 3 份原始分析 | postmkt `sumResultHtml` 的 `six[]` | **補上**（`s.model` 在 JSON 內） |
| 彙總場的彙總本身 | postmkt `sumResultHtml` 的 `synthesis` | **手動場補上**；自動場見下 |
| 持股診斷 AI 解讀 | postmkt `diagCardHtml` | **補上**（`ai.model`＋`ai.usage` 皆在） |

**未補的一項，照實記錄**：`data/summary/*.json`（GitHub Actions 自動彙總場）的
`synthesis` 只有 `{text, usage, via}`、**沒有 model 欄**。彙總模型雖在程式碼裡固定是
Opus 4.8，但那是「從程式碼推論」而非資料本身，硬套等於顯示一個猜的數字，故
`sumResultHtml` 在 `synthesis.model` 缺席時讓 `insightCostText` 回空字串、**寧可不顯示**。
要補齊需 `build_summary.py` 的 `write_output` 一併寫入彙總模型（本次未動 Python）。
手動彙總場已改成落地時寫入 `synthesis.model`（新增常數 `SUM_SYNTH_MODEL`，同時是
`runSummary` 呼叫點的事實來源，取代原本寫死的字面量），故手動場即刻可見。

**`insightCostText` 本體唯一的改動＝batch 半價**：自動彙總場走 Message Batches，其 `usage`
帶 `service_tier:"batch"`，而 Batch API 是標準價的 50%（claude-api skill 定價表）。不處理的話
自動場的每一份原始分析都會**高估一倍**。故加 `const disc = usage.service_tier === "batch" ? 0.5 : 1`
一行；瀏覽器單發的 `service_tier` 是 `"standard"`，走 `disc=1`，**既有單發場數字逐位元不變**
（實測 Sonnet 5／輸入 10,000／輸出 2,000＝`US$0.0400（≈ NT$1.3）`，改動前後相同）。
三站該區塊改後 sha256 仍全等（`5139f23e…`），新增的雲端歷史片段
`${insightCostText(u, cur.entry.model)}` 三站亦逐字相同。

`INSIGHT_PRICES`／`USD_TWD` 本次未動（08-30 剛對齊）。經清點，各場次用到的 model id 只有
`claude-sonnet-5`（`SUM_MODELS`、單發下拉）與 `claude-opus-4-8`（彙總、單發下拉），
**都在價目表內**，無「表中沒有的 model」情形；表外 model 的現行行為（回空字串、靜默）未改。

## 2026-08-30 輪動雷達日頻 RRG 錨點標名碰撞避讓

`rrgdSvg` 的錨點與加選鏈標名原本一律固定偏移（x+7、y−6），零碰撞偵測——點密集日會互相重疊，
只能靠 hover 兜底（README 原「未解／待觀察」條）。本次改為候選位搜尋：每個頭點一圈 8 個候選位
（第一個候選位在 gap=3 時恰為舊版的 (x+7, y−6)，故不擁擠時外觀不變），撞光再跑 gap 12/22/32
外三圈共 32 個，取第一個零重疊處；全撞則放在**加權重疊面積最小**處（`ovlp()` 算的是重疊面積
而非布林，就是為了讓 fallback 能挑最小者），全出界才夾回畫布內。**不省略任何標籤**——錨點與
加選鏈都是使用者主動要看的，靜默消失比疊放更糟。佔位權重＝當日成交額（`j.chains[nm].amt[t]`，
正規化 0~100），擁擠時優先蓋掉小鏈而非龍頭；優先序＝**加選鏈 → 錨點（成交額遞減）**，
加選是使用者主動點的故優先保障。標籤改為統一畫在所有頭點之上並加 `pointer-events="none"`，
不再遮住頭點的 hover `<title>`。

演算法移植自 taiwan-flow-live-v2 `index.html` 的 `ovRrgHtml` 標籤段。移植時重新對應三處語意：
①本頁頭點固定 r=5（盤中版是可變泡泡半徑）②權重改用成交額（盤中版用成交佔比）③強制標名族群＝
加選＋錨點（盤中版是錨點／改善象限／位移異常）。差異夠大，**兩邊刻意不登記為「改一邊要同步
另一邊」的跨站同步函式**，只在各自程式碼加互相引用的註解。

**量測**（臨時 Node 腳本抽 `index.html` 的 `rrgd*` 視覺層離線跑，未入 repo；序列取
taiwan-flow-live-v2 `data/chain_daily/series.json`，264 個可顯示交易日 × 15 個標籤＝3,960 個，
加選情境固定取當日成交額第 11~15 名）：

| 指標 | 改動前 | 改動後 |
|------|-------|-------|
| 標籤矩形兩兩重疊配對數 | 719 | **0** |
| 有重疊的標籤佔比 | 28.2%（1,117／3,960） | **0%** |
| 跑出畫布的標籤數 | 31 | **0** |

位置擾動：83.6% 的標籤與改動前逐位元相同，99.6% 落在第一圈（離頭點 ≤18px），只有 17 個
（0.4%）走到外圈，最遠一次位移 38px；加權疊放 fallback 全期間未觸發。優先序不變式亦逐日
驗過：314 組「舊版會相撞的 加選×錨點」配對中，沒有任何一組是錨點佔住位置而把加選擠開
（5 組表面例外經逐筆歸因，均為加選被**更前序的加選**擋住，非錨點所致）。

改動全部落在 `rrgdSvg` 的標籤輸出段，`RRGD-PURE-BEGIN … RRGD-PURE-END` 區塊逐位元未動
（raw 與去註解後 sha256 前後相同），故不觸發與 `taiwan-flow-live-v2/backtest/
run_rrg_daily_axes.py` 的前後端座標對拍不變式，無須重跑對拍。

## 2026-08-30 輪動雷達「動能領先」更名為「相對強度領先」＋三站 INSIGHT_PRICES 對齊

**UI 更名**：承接同日排序鍵改動（見下一則），領先象限候補清單的排序已由 RS-Momentum 改為
RS-Ratio，「動能領先」四個字與排序不符（momentum vs level），故標籤改為
**「相對強度領先（領先象限）」**。改動點只有 `renderRrgd` 的 `sec(...)` 一處（`index.html:1762`）
＋同段程式碼註解；「資金剛輪入（改善象限）」的名稱與排序（RS-Momentum）維持不變。
README 輪動雷達段的口徑敘述同步更新。

**INSIGHT_PRICES 三站對齊**：`claude-sonnet-5` 的價目在 postmkt 已由 `[3,15]` 更正為
`[2,10]`，但 taiwan-stock-news 與 taiwan-flow-live-v2 仍是 `[3,15]`（費用估算高估約 50%），
本次補齊。三站該常數逐字一致（sha256 比對），`insightCostText` 本體未動。同批把該區塊註解
「Sonnet 5 於 2026-08-31 前有 intro 價 $2/$10，此處採標準價 $3/$15」除鏽——該敘述與現值
`[2,10]` 自相矛盾且次日到期，改為敘明 claude-api skill 定價表（快取日 2026-06-24）所列現行價
Opus 4.8 $5/$25、Sonnet 5 $2/$10。`claude-opus-4-8`（`[5,25]`）與 `USD_TWD`（31.5）
三站原本即一致，無其他欄位差異。

## 2026-08-30 輪動雷達「動能領先」排序改用 RS-Ratio

「動能領先（領先象限）」候補清單原依 RS-Momentum 遞減排序，改為依 RS-Ratio 遞減。
理由有二：(1) 語意——該清單要表達的是相對強度的**水準**，RS-Momentum 是水準的變化率；
(2) 回測旁證——taiwan-flow-live-v2 `backtest/report_chain_overlap.md` **§2.5**（§5.3 複述）記載，
同一套橫斷面排序下 RS-Momentum 水準六種切法 6/6 為負（平均 -0.238%）、RS-Ratio 水準 6/6 為正
（平均 +0.156%）；純動能（過去 L 日超額報酬）18/18 點估計為正、4/18 分塊 CI 顯著則是 **§2.4**
（§5.3 一併複述）。**該報告自陳 CI 全跨 0（§2.5 表下方「分塊 CI 不跨 0 的格子數：0 / 12」）、
只是方向線索不是可上線結論**；且 §2.5 量的是「全 47 條鏈橫斷面排序、取前後 20%」的 T+3 多空
價差，與本清單「先過 N=3 持續性、只留領先象限的鏈，再排序」不是同一個構造，該節數字不能直接
推到象限內排序——故主要依據是 (1) 的語意，(2) 僅為方向旁證。本次只調整排序鍵，不改軸定義、
不改象限判定、不加任何買賣建議語氣。

實作：`rrgdPersistList` 新增 `sortKey` 參數（`RRGD_SORT_RATIO`／`RRGD_SORT_MOM`），
「資金剛輪入（改善象限）」維持 RS-Momentum；清單說明列的排序文字改為逐清單標示。
postmkt 無 RRG 後端實作（座標公式正本在 taiwan-flow-live-v2 `backtest/run_rrg_daily_axes.py`，
該處無此清單排序），故本次為單邊改動。UI 標籤「動能領先」暫未更名。

## 2026-08-29 彙總分析 6→3 份＋自動場改走 Message Batches（＋三項小改）

commit `3617f69`／`ef9c2d4`／`09ac097`（摘要與彙總）、`9f49344`（no_wait）、
`9a161ee`（頁尾版本）、`f2a7d65`（主動ETF）。

| 改動 | 內容 |
|------|------|
| 摘要 6→3 份 | 每頁由 2 次獨立分析（Sonnet5-A/B）減為 1 次，共 3 份；`MIN_OK_FOR_SYNTH` 3→2；彙總 SYS 的共振強度口徑 N/6→**N/3**（`index.html` `SUM_SYS_SYNTH` 與 `build_summary.py SYS_SYNTH` 同步）。手動場執行鈕文案一併由「6+1 次呼叫」改「3+1 次」 |
| 自動場改 Message Batches | `build_summary.py` 新增 `call_claude_batch`：摘要與彙總都以 batch 送出（**半價**），am 期限 25 分／pm 180 分；逾時或單筆失敗**逐筆同步回退**至 `call_claude_retry`。另加全場時間預算折算，避免撞上 `summary.yml` 的 240 分 timeout |
| `summary.yml` 加 `no_wait` | `workflow_dispatch` 新增布林輸入 `no_wait`（→ `--no-wait`），跳過資料齊全輪詢閘門，供測試與補跑；**週末假日也會照跑**，正常排程不受影響 |
| 頁尾顯示站台版本 | footer 加 `#siteVer`＋`loadSiteVer()`：打 `api.github.com/repos/shihpc/postmkt/commits/main` 取 main 最新 commit 短碼與時間，存 sessionStorage `pm_site_ver`；任何失敗一律靜默隱藏。四站（本站／live-v2／flows／news）同步但**非逐字**，差異見 CLAUDE.md 約定第 2 條 |
| 主動ETF比較 4→6 | 同時勾選上限由 4 檔放寬為 6 檔 |

同批曾試「產出檔加 `code_version` 版本戳」（`5be7561`）後**整條 revert**（`bd88a1f`），
`data/summary/*.json` 無該欄——費用估算缺的 `synthesis.model` 改由 08-30 那則補齊。

## 2026-08-27 摘要分析顯示本次 API 費用估算（三站）

commit `691226a`（本站）／live-v2 `737d9b2`／news `04c4d78`。依回應 `usage` 與 model
估算單次費用，新增三站逐字同步的 `insightCostText`／`INSIGHT_PRICES`／`USD_TWD`
（**第五組三站同步函式**，見 CLAUDE.md 約定第 2 條）。當時只掛在單發摘要分析，
其餘場次由 08-30 那則補齊。

## 2026-08-12 新增第 13 個 tab「選股」（分析師預估 EPS 篩選）

動機＝富邦投顧「明年 EPS>50 找萬元股」報告的自動化重現。新管線 `src/build_screen.py` →
`data/screen/screen.json`：TradingView scanner 批次初篩（`earnings_per_share_forecast_next_fy>=20`，
server 端 filter，實篩 91 檔）→ 鉅亨網 `marketinfo.api.cnyes.com` 逐檔補 FactSet 共識
（多年度預估 EPS 高/低/均/中位＋分析師家數、目標價、券商評等；上市上櫃一律 `TWS:` 前綴，
節流 1.2s/檔，連續 10 檔全失敗才 abort 且 abort 不覆蓋舊檔）→ 合併 diag.json 的
pe/yoy/mom/rvs 欄。掛在 diag workflow 的 build_diag 之後（`continue-on-error: true`，
失敗不擋 diag 主產物；commit composite 加 `add_all` 容錯不存在路徑）。

前端 tab：`tbl()` 全欄排序、門檻鈕（明年 EPS ≥30/50/100，預設 50）、forward PER＝現價÷預估
EPS 自算、目標價中位與潛在漲幅。**年度欄錨定日曆年**（基準年＝資料日年份，今年/明年欄
分別取 est[Y]/est[Y+1]，缺該年度顯「—」）——初版曾用「逐列取最小年度＋欄頭取眾數」，
同一欄會混到不同年度（欄頭 FY25、2330 那格卻是 2026 值），驗收抓到後改錨定制。
門檻過濾口徑＝est[Y+1].mean 缺值 fallback TradingView feps。固定標注「FactSet（經鉅亨網）／
TradingView，預估值為券商共識非保證」。資料源皆非官方端點、無 SLA（Yahoo 2023 加 crumb
為前例），管線失敗時前端顯示舊檔或空狀態降級。離線測試 `tests/test_screen.py` 14 支
（fixture 免網路）；13 tab Playwright 零 console error、門檻筆數/PER/漲幅與 JSON 獨立重算零差異。

## 2026-08-11 新增第 12 個 tab「輪動雷達」（盤後日頻 RRG）

規格＝taiwan-flow-live-v2 `docs/rrg-daily-spec-20260811.md` §4 第三階段。軸與參數為該專案
第二階段定案：**B-ew**（價格版 RRG × 等權報酬）、z-score 窗 n=12、動能回看 k=10、候補清單
持續性 N=3；公式正本＝該站 `backtest/run_rrg_daily_axes.py` 的 `axis_systems`，前端
`RRGD-PURE` 區塊逐式重現並以 Node 對拍（抽 2026-08-11／2025-11-28／2026-04-13 三日 ×
47 鏈，最大絕對誤差 5.7e-14 < 1e-6）。資料源 `data/chain_daily/series.json`（594KB）走
`ensureChainDaily()` 懶載不進首屏。畫布純 SVG：47 鏈散點、成交額 Top10 錨點標名＋軌跡尾巴、
其餘淡化 hover 可見；日期可回看；候補清單「資金剛輪入」（改善）／「動能領先」（領先）
完整列出。文案全程描述語氣（該專案回測：前瞻超額六種切法 0/12 顯著，資料不支持任何
買賣建議），頁尾附回測依據、成員重疊揭露（一塊錢平均被算進 2.24 條鏈）與「盤中版 →」互連。
新鮮度：最後資料日落後今日 >3 平日顯示「資料未更新」；fetch 失敗／格式異常皆降級不壞整頁。

## 2026-07-28 彙總分析：`max_tokens` 8000 → 16000

前一批的空回應守門只讓「thinking 吃光額度」變成明確失敗＋retry，不降低發生率。實測 5 個時段
共 30 份子分析：**盤後分析 10 份裡有 6 份撞到 8000 上限**（4 份 text 全空、2 份文字被截短），
新聞晨報 1/10，即時類股動態 0/10（最多只用到 2,247 thinking token）——集中在 context 最大的
盤後分析（實測 `input_tokens` 7,774–7,923，新聞晨報 4,344–4,487、即時類股 1,803–3,267）。

Sonnet 5 已移除 `budget_tokens`（送出即 400），**無法單獨限制 thinking**，thinking 與回覆文字
共用同一份 `max_tokens`，所以只剩「拉高上限」或「降 effort」兩條路。選前者：`max_tokens` 是
上限而非預留額度、只按實際生成計費，而一份空白目前是燒 8000 token 換 0 字、加上 retry 等於
16000 換 0 字——**拉高上限比維持現狀更省**。降 effort 則是反方向（官方指引：推理不足應調高
而非調低），且會犧牲最複雜那頁的品質。16000 也是非串流請求的建議上限，不必改成串流架構。

三頁同調（即時類股動態用不到，調高對它零成本）；`effort` 維持 `medium`。三站 `callClaude`
逐字同步。`tests/test_summary_call.py` 新增斷言釘住 16000 與 `thinking.type=adaptive`。
`stop_reason` 已落進 `six[]`，之後若仍見 `max_tokens` 代表 16000 也不夠，屆時再考慮縮 context。

## 2026-07-27 彙總分析：空回應攔截 + 三條 SYS 規則放寬

- **修 bug：AI 空回應未攔截**。adaptive thinking 吃滿 `max_tokens:8000` 時回應只有 thinking block、
  沒有 text block，`callClaude`／`call_claude` 都把它當成功回傳空字串，以 `ok:true` 進彙總
  （2026-07-27 pm 場：6 份中 3 份 `output_tokens=8000`／`thinking≈8000`、`text` 為空，
  `ok_n=6` 通過 `MIN_OK_FOR_SYNTH=3` 檢查，彙總層只好自行宣告「本日 6 份中…為空白」）。
  現在空白（含全空白字元）視為失敗丟出：自動場交給既有 retry，仍空則落 `ok:false` 佔位；
  前端無重試故直接落 `ok:false`。回傳值一併保留 `stop_reason` 並寫進 `six[]` 供事後判讀。
  三站 `callClaude` 逐字同步（postmkt／taiwan-flow-live-v2／taiwan-stock-news）。
- **SYS 規則放寬三條**（原本模型在缺料時自行放寬、與 prompt 明文相牴觸，改為寫成明確規則）：
  `SYS_LIVE (7)` 個股成交量只出現在「個股盤中資金集中 前15」段的「量X張」、該段無資料時整段略過，
  故不硬性套用 1,000 張門檻，查不到量能者可入選但須標注「量能未知」；
  `SYS_NEWS (7)` 美股／晨報資料日與主資料日不同時，由「嚴禁跨日串連」改為可串連但須標注資料日
  （**USER prompt 需一併改**：原 `sumUserNews = sumUserPostmkt` 別名共用同一條「僅可單獨解讀，勿跨日
  比較」，會與放寬後的 SYS 打架；已拆成獨立模板，三份副本措辭一致）；
  `SYS_SYNTH (5)(6)` 彙總層同步鬆綁量能門檻與跨日禁令（新聞晨報資料日不受跨日限制）。
  `SYS_POSTMKT (7)(9)` **不動**——盤後分析頁本身有成交量資料，門檻與日期對齊維持原樣。
- 新增 `tests/test_summary_call.py`（10 支）：空回應／retry 行為，外加 SYS prompt 在
  `index.html` ↔ `build_summary.py` 兩份副本的逐字一致性守門（此路徑原本零測試覆蓋）。

## 2026-07-24 專案優化批次（三輪）

- cache.json（~3MB 增量快取）移出 git 改走 actions/cache；diag/mktbal 資料改懶載（首屏傳輸減半）；
  四 workflow 補 timeout＋失敗告警（開 issue）；日期 tab 落後計算改交易日（排除週末）；`.gitignore` 補齊。
- 抽共用 `src/fmclient.py`（FinMind api_get 統一重試，postmkt 從零重試變有重試）；
  SYS prompt 953 字三份複本去重（唯一事實來源＝`SUM_SYS_POSTMKT`）；requirements 鎖版本。
- postmkt.json 瘦身 2.42MB→1.57MB（lending 衍生欄改由消費端以 px 重建、當沖 by_ratio 停產）；
  抽共用 `src/twseclient.py`（全域節流，postmkt 的 TWSE 端點也納入）；pytest 測試上線（60+ 離線測試）；
  TWT72U 欄位改 fields metadata 動態定位；diag 回補窗常數集中（full/--sample 共用）；
  分點推估 3 併發；`_next_exdiv` 同日現金+股票合併改寫為順序無關；CSP meta 上線；
  commit/push 與失敗告警抽 composite action；日期 tab 快取可刷新；多項顯示小修
  （+0 不上色、stat 列各 tab 用自身資料日、新聞連結 scheme 過濾、診斷 AI 可中斷）。

## 2026-07-21 盤後批次改進四項（依 b-group-investigation 調查結果）

- **項5 ETF 持股加市值欄**：`renderAETF` 持股組合表新增「市值(億)」欄＝`stocks[code][3]/1e8`，
  section 註記「市值依 FinMind 揭露日、非即時」；缺值顯「—」。資料源 build_aetf.py 已補逐股 mv
  （v2 `src/build_aetf.py` `grab_holding()`），但 postmkt 讀 v2 raw latest.json，故要等 v2 排程
  重跑 build_aetf push 後該欄才有實值（在此之前一律「—」，屬預期）。
- **項8 大盤餘額只留金額**：`MKTBAL_PILLS` 由 4 pill（融資/融券/借券賣出/不限用途）縮為 2 pill：
  融資餘額（只 `margin_money` 金額(億)、拿掉張數）＋借券賣出餘額（只 `sbl_short_value` 金額(元)＋
  `mktNum` 千位點、拿掉股數）。融券/不限用途 TWSE/FinMind 官方無金額欄故不顯示；資料檔
  `market_balance_history.json` 欄位不動、僅前端不消費那兩項。
- **項9 融借券整合排行拆 TSE/券商兩區塊**：`index.html` 整合排行表把單一「借券餘額」欄組拆成
  「TSE餘額」「券商餘額」兩區塊各 餘額(張)/異動(張)/市值(億)/市值異動(億)，刪掉合計三欄
  （`plat_total*` 資料保留、摘要仍用不動）。後端 `build_postmkt.py build_lending()` 新增
  `sys_mv_chg`/`otc_mv_chg`（=異動張數×收盤價，同 sbl_short_mv_chg 近似法）寫入 row。
  （註：2026-07-24 瘦身後這批 `*_mv_chg`/`plat_total*` 改由前端 `augmentLending()` 重建，不再落地。）
- **項10 日期 tab 移最右＋文案**：TABS 陣列 `["dates","日期"]` 移到 `["diag","持股診斷"]` 之後；
  「自動產出」section 文案由「早場08:00／晚場22:00」更正為實際 cron「早場06:23／晚場22:47 台北」。
- **驗證**：本機跑 build_postmkt（3481 群創 sys_mv_chg=-376891/otc_mv_chg=109469 千元）＋瀏覽器 11 tab
  零 console error；大盤2pill、融借券兩區塊八欄無合計、ETF市值欄、借券賣出金額帶千位點、日期 tab 在最右皆實測。

## 2026-07-20 主動ETF tab 三項UI改進（純前端，`renderAETF` 內）

- **修「部分ETF點不進去」的bug**：根因是舊版 ETF 總覽表只在 `diff.etfs[code]` 有
  buy/sell（`n_buy`/`n_sell` 非0）時才把 ETF 名稱掛可點（`data-etf`），00981A 等
  當日無主動加減碼的 ETF（`n_buy=n_sell=0`）因此點不進去。改法：`ov` 每列一律
  可點，不再看 `hasDiff`；`state.openEtf` 展開區塊改成先看 `latest.etfs[code]`
  是否存在（持股一定有，只要 latest 載入成功），不再依賴 `diff.etfs[code]` 是否有值。
- **展開區塊重排**：「最新持股組合」（讀 `latest.json etfs[code].stocks`，dict
  `code→[股數,名稱,權重%]`，實測結構）移到「加減碼明細」**上方**，各自標資料日
  （持股＝`src_date`；加減碼＝`de.d0→d1`，該 ETF 若無 diff 條目則退回
  `diff.primary_date`）。無加減碼時顯示「今日無主動加減碼」而非空白兩欄。
- **次產業流向明細補 ETF 名稱**：`so.detail[].etf` 原本只有代號，改用
  `latest.etfs[code].name`（備援 `diff.etfs[code].name`）補上，呈現同
  `code`+`nm` span 樣式（跟個股欄一致）。
- 三項均已本機起 `python -m http.server` 跑 `index.html` 實測（00981A/00403A 兩種
  case＋次產業展開），全 11 個 tab 逐一點擊 console 零 error；未動
  `callClaude`/`mdToHtml`/`linkifyStocks` 等三站同步函式本體。
