# 選股二「多空總分」規格（pick2 score）

> 正本。`index.html` 的 `PK2_SCORE_SPEC`（grep `const PK2_SCORE_SPEC`）與本文件下表逐列一致，
> `tests/test_pick2.mjs` 會逐列比對 label／規則字串／權重，改一邊沒改另一邊測試會紅。

## 1. 使用者裁定（2026-10-18）

- 「選股二」tab 要有排序分數。依家族鐵律 8：**此分數沒有任何回測依據**。
- 使用者明確裁定**可先上線**，條件：
  1. 畫面標示「**AI 研判，未經回測，非保證**」（`PK2_SCORE_NOTE`，逐字固定）；
  2. 裁定登錄於 repo 文件（即本文件、`CLAUDE.md`「選股二」節、CHANGELOG）；
  3. **列入事後驗證**（§5；本批不實作驗證）。
- 另並列「股市易經」三期間總分（`bs`）**供參考**，**不是**本分數的一部分（§6）。
- 本分數只是把現有表格欄位依固定規則加總，**不是買賣訊號**，不據此下單。
- **同日追加裁定：美股不計多空總分**（資料項不足）。`pk2Score` 對 `m==="US"` 一律回 `score:null`，畫面「—」、tooltip
  「美股不計總分（資料項不足）」、預設排序排在最後（台股在前、美股在後依代號）。

## 2. 規格表（12 項）

每項得分 s∈{+1, 0, −1}（目標價空間另有 +0.5），權重 w。欄位來源同表格現有欄（diag.json／screen.json／aisc 每日表）。
「鍵」＝`pk2Rows()` 列物件欄位名。

| 類 | 鍵 | 項目 | 規則 | w |
|---|---|---|---|---|
| 趨勢 | `ma20` | MA20 | 收盤在 MA20 之上 +1、之下 −1、相等 0（diag 收盤距 MA20%：>0／<0／=0） | 1 |
| 趨勢 | `ma60` | MA60 | 收盤在 MA60 之上 +1、之下 −1、相等 0（diag 收盤距 MA60%；diag 不涵蓋的台股用 aisc above60：True +1／False −1） | 1 |
| 趨勢 | `r20` | 20日漲幅 | 20日漲幅 >0 +1、<0 −1、=0 0 | 1 |
| 趨勢 | `rs` | RS | RS >0 +1、<0 −1、=0 0 | 1 |
| 籌碼 | `f5` | 外資5日 | 外資 5 日買賣超 >0 +1、<0 −1、=0 0 | 2 |
| 籌碼 | `t5` | 投信5日 | 投信 5 日買賣超 >0 +1、<0 −1、=0 0 | 2 |
| 籌碼 | `bb` | 土洋同買 | 土洋同買＝1 +1、＝0 0 | 2 |
| 籌碼 | `mg5` | 融資5日% | 融資 5 日增減 >5% −1、否則 0 | 2 |
| 籌碼 | `hdw` | 大戶週變化 | 千張大戶持股週變化 >0 +1、<0 −1、=0 0（同表格「大戶週變化(pp)」欄） | 2 |
| 基本面 | `yoy` | 營收年增 | 月營收年增 >0 +1、<0 −1、=0 0 | 1 |
| 基本面 | `up` | 目標價空間 | 目標價中位÷現價−1：≥20% +1、10%≤x<20% +0.5、0≤x<10% 0、<0 −1 | 2 |
| 基本面 | `buyr` | 買進＋加碼佔比 | 分析師（買進＋加碼）÷五類總家數 ≥0.7 +1、否則 0；總家數 0 視為缺值 | 1 |

口徑補充（照現有欄位，不另算）：
- `ma20`／`ma60` 是 diag.json 的「現價距 MA%」（`src/build_diag.py` 以 `r2` 四捨五入到 2 位小數），所以「收盤 > MA」等價於距離 > 0；
  距離小於 0.005% 會被捨入成 0、得 0 分。
- `hdw`＝diag `hdw`，缺時退 `hd[0]−hd[1]`（與表格「大戶週變化(pp)」欄同一個值）。
- `up`＝screen `tp.median ÷ px − 1`（%，`px>0` 才有），同表格「目標價空間%」欄。
- `buyr`＝screen `rating` 五鍵（buy／overweight／hold／underweight／sell）；缺鍵記 0（同表格「分析師評等」欄），五鍵皆缺或總家數 0＝缺值。

## 3. 公式與缺值

- 缺值（`null`／非有限數）＝該項**不計分且不計入分母**；值存在但得 0 分＝**計入分母**。
- `score = 50 + 50 × Σ(w·s) ÷ Σw`（只對有值項），四捨五入到 1 位小數（`Math.round(x×10)/10`）；範圍 0～100，50＝中性。
- 全部缺值 → `null`，畫面顯示「—」。
- 純函式 `pk2Score(row)` 回 `{score, n, items:[{k,label,s,w}]}`：`items` 只列有值項、`n＝items.length`。
  畫面總分格的 tooltip 由 `pk2ScoreTip()` 產生，例「MA20 +1×1｜外資5日 −1×2｜…（12 項中 10 項有值）」。

手算例（`tests/test_pick2.mjs` 有斷言）：12 項全有值，趨勢 +1−1+1+0、籌碼 +2−2+2−2+2、基本面 +1＋(0.5×2)＋1
→ Σws＝6、Σw＝18 → 50＋50×6/18＝66.67 → **66.7**。

## 4. 市場差異

- **美股不計總分**（2026-10-18 使用者裁定）：美股只有 aisc 每日表（收盤／r5／r20／above60／ext／slope60），沒有 diag／screen，
  12 項中實際只有 `ma60`（above60）與 `r20` 兩項有值，若照算分數只能是 0／50／100 且會排到台股前面，故一律 `score:null`
  （`items` 空、`n＝0`），顯示「—」、排在最後。規格表 `ma60` 列的「美股用 above60」字樣保留，只適用 diag 不涵蓋的台股退用 aisc 表的情形。
- 台股不在 diag 素材庫者：趨勢類退用 aisc 表（`r20`、`above60`），其餘缺值。

## 5. 事後驗證計畫（本批不實作）

- 分數輸入全部可由 git 歷史重建：postmkt `data/diag/diag.json`、`data/screen/screen.json` 的每日版本，
  與 taiwan-backtest `output/aisc/daily/` 的每日表；以同一支 `pk2Score`（自 `index.html` `pick2-pure` 區段抽出）重算每日分數。
- 對照之後 N 日（建議 5／20／60 交易日）報酬，看分數高低組的報酬差與 rank IC；樣本期、名單（換池前後）與市場分開報告。
- 驗證前**不得改門檻或權重來「修」結果**；要改＝改本文件與 `PK2_SCORE_SPEC` 並在 CHANGELOG 記版本，舊分數不回頭重寫。
- 驗證結論出來前，畫面標示「AI 研判，未經回測，非保證」不得拿掉。

## 6. 股市易經欄（參考，不屬本分數）

- 來源：同源相對路徑 `../taiwan-stock-iching/data/web/latest.json`（`PK2_ICH_URL`，約 1.4MB，**只在切到本 tab 才抓**，CSP 未改），
  取 `stocks[code].short|swing|mid.bs` 與頂層 `date`（頁頂「股市易經 資料日」）。美股與易經站不涵蓋者「—」。
- 畫面固定附註（`PK2_ICH_NOTE`，逐字）：「股市易經總分僅供參考：易經站公布之驗證結果——短線驗證段 IC 為負、未通過門檻；
  波段驗證段證據不足、訓練段 IC 為負；中期證據不足。總分高不代表後續報酬較高；上市與上櫃混排的可比性未經驗證。」
  （依據：taiwan-stock-iching `docs/P4-PREVIEW.md` §12 裁定 #74 的逐期間驗證結果。）
- 易經三欄**不進**多空總分，也不是預設排序鍵；點表頭可依它們排序。

## 7. 追蹤名單（2026-10-19 使用者裁定）

### 7.1 裁定
- **自動選入**＝台股、單日多空總分 **≥ 80** 且有值項 **≥ 9**（`n`，即 §3 `items` 的筆數；**不加易經**）。
- **無自動移出**：選入後追蹤到使用者刪除為止（分數掉下門檻、月度換池移出候選池都照樣追蹤）。
- 使用者可在「選股二」tab **手動加入**（表格台股代號下「加入追蹤」鈕）與**停止追蹤**（追蹤表「停止追蹤」鈕，須 confirm；2026-10-23 由「刪除」改名，避免與名單的「刪除勾選」混淆，行為不變）；
  寫回 repo（GitHub PAT，密碼管理器帳號名 `github-pat-postmkt-analyses`，見 CLAUDE.md 約定 6），**下次每日建置生效**。
- **被刪除的股不再自動選回**；手動加入可解除刪除，`since`＝加入後第一次建置日。只追蹤台股。
- **無回測依據、先上線**（家族鐵律 8）：畫面（追蹤區塊與「加入追蹤」鈕）標「AI 研判，未經回測，非保證」、本節登錄、列入事後驗證（§7.4）。
- LINE 推播由 taiwan-flow-live-v2 Worker 讀 `track.json` 發（該 repo 另案實作），本 repo 不推播。

### 7.2 實作
- 後端 `src/build_pick2.py`（掛在 `diag.yml` 的 `Build screen.json` 之後，`continue-on-error`、不擋 diag；commit 帶 `data/pick2/`）：
  讀 `data/diag/diag.json`、`data/screen/screen.json`、taiwan-backtest raw main `aisc/universe.json`（逾時 30 秒、失敗重試一次；
  本機檔可用 `--universe` 或環境變數 `PICK2_UNIVERSE` 注入）、`data/pick2/user.json`；資料日＝`diag.json` 的 `date`。
  分數＝`pk2Score` 的 Python 移植（`SCORE_SPEC` 與 `PK2_SCORE_SPEC` 逐項同序同權重；四捨五入 `js_round`＝JS `Math.round`
  half-up，**不可用 Python `round()`**；目標價空間先捨 1e-6；缺值不計分母；美股 null）。`tests/test_pick2_build.py` 以 node
  抽 `index.html` 的 `pick2-pure`＋`pk2Rows()` 對跑 fixture（20 檔真實資料＋人造邊界例）與現行 `data/diag`／`data/screen` 全部代號，逐位相同。
- **失敗會亮紅燈**：`diag.yml` 的 `Build pick2 track`（`id: pick2`）設 `continue-on-error`，diag／screen 照常 commit；
  commit 之後的 `Fail if pick2 failed`（`if: steps.pick2.outcome == 'failure'`）再 `exit 1`，job 轉紅並觸發既有 notify-failure（延後紅燈）。
- **失敗不寫檔、exit 非 0**：universe 讀不到／無台股名單、diag／screen 讀不到、`user.json` 壞檔（不可當空，否則已刪除的股會被自動選回）、
  `track.json` 壞檔或日期晚於本次。
- **冪等**：同 date 重跑結果相同（`generated_at` 除外）——沿用前次 `track.json` 中 `since` **早於**本 date 的列，`since`＝本 date 的列
  一律重算；`new_today` 只列 `since`＝本 date 者。第一次執行（無歷史）＝當日符合門檻者全部選入、`since`＝該日。
- 前端（`index.html` grep `// ---- 追蹤名單`、`function pk2TrackHtml`、`async function pk2UserWrite`）：切到本 tab 才以同源讀
  `data/pick2/track.json` 與 `data/pick2/user.json`（404＝尚無紀錄），首屏請求不變、CSP 未改（寫入走既有 `connect-src` 的 `api.github.com`）。
  按鈕以記憶體 `CRED.gh`（`ghToken()`）對 Contents API `GET`→驗形狀→追加一筆→`PUT` 帶 `sha`，409／422 重讀再試（共 3 次）；
  repo 上 `user.json` 形狀不合時拒寫。PAT 只進 `Authorization` header，不進 localStorage／DOM／URL；未載入時區塊內提供載入表單。
  寫入成功先在記憶體標「待加入／待刪除（下次建置生效）」；重新整理後以 `track.json`＋`user.json` 判斷：`user.json` 中 `at` 晚於
  `track.generated_at` 的動作＝尚未生效。**三站逐字同步碼 `ghSaveAnalysis`／`callClaude` 未改。**

### 7.3 介面契約（taiwan-flow-live-v2 Worker 同時讀，欄位名不得自行更改）
- `data/pick2/user.json`（前端寫、後端讀）：`{"schema":1,"log":[{"act":"add"|"del","code":"2330","at":"<ISO>"}]}`（append-only，同代號以最後一筆為準）。
- `data/pick2/daily/<YYYY-MM-DD>.json`（後端每日）：`{"schema":1,"date","spec":"pick2-score-v1","rows":{"<code>":{"name","c","score","n"}}}`
  （`rows`＝候選池台股全部）。**附加鍵 `extra`**（同形狀）只在有「追蹤中但不在當日候選池」的股時出現（換池移出／手動加入池外股），
  用來算這些股的報酬與回撤；`pool_ret` 只看 `rows`、不看 `extra`。
- `data/pick2/track.json`（後端每日）：`{"schema":1,"date","generated_at","rule":{"min_score":80,"min_items":9},"spec":"pick2-score-v1",
  "tracking":[{"code","name","src":"auto"|"manual","since","entry_close","entry_score","last_close","last_score","ret","pool_ret","mdd","days"}],
  "new_today":[{"code","name","src","score"}],"deleted":["<code>",...]}`。
  - `entry_*`＝`since` 那天快照的收盤／分數，`last_*`＝本 date；`ret＝last_close/entry_close−1`；`pool_ret`＝候選池台股等權平均報酬
    （`since` 與 `date` 兩日快照 `rows` 皆有 `c` 者）；`mdd`＝`since` 以來各快照收盤相對前高的最大跌幅（**≤ 0**，例 −0.25）；
    `days`＝`since` **之後**的快照數（列入當天為 0）。百分比一律存小數、`js_round` 到 6 位；算不出為 `null`。
  - `deleted`＝`user.json` 最後一筆為 `del` 的代號（排序）。
- 已知差異：diag 不涵蓋的台股，前端會退用 aisc 每日表的 20日漲幅／above60，後端不讀該表（那兩項缺值、分數可能與畫面不同）；
  2026-10-19 現行候選池 93 檔台股全在 diag 內，實際無差異。

### 7.3a 已知限制（2026-10-19 驗收記錄，現況接受）
- **待生效判斷以 `generated_at` 為準、不是 checkout 時點**：建置讀的是 workflow checkout 當下的 `user.json`，而前端拿 `at` 與
  `track.generated_at`（建置結束時刻）比。checkout 之後、建置寫完之前寫入的動作，`at` 早於 `generated_at` 會被當成「已生效」，
  實際卻要到下一次建置才生效——這段誤差窗內畫面少標一次「待生效」。
- **Pages 延遲期間重新整理，按鈕會回彈**：寫入成功後同源 `data/pick2/user.json` 要等 Pages 重新部署才更新；期間重新整理只剩記憶體以外的狀態，
  「待生效」標示消失、「加入追蹤／停止追蹤」鈕重新出現。再按一次只會在 log 追加一筆同動作的重複紀錄，因同代號以最後一筆為準，**無害**。
- **某日建置失敗會少一個 daily 快照**：`days`（以快照計）少算一天、`mdd` 少看那天收盤；之後的建置不會回補缺的那天。
- **diag 與 screen 的資料日未互檢**：screen 步驟失敗時 `screen.json` 停在舊日，分數的目標價空間／評等兩項用的是舊資料，建置不擋也不標示
  （同前端畫面的行為，前端頁頂各資料源自帶資料日）。

### 7.4 事後驗證
- 追蹤紀錄可完全由 git 歷史重建（`data/pick2/daily/*.json`＋`track.json`＋`user.json`）。對照組＝同期候選池台股等權（`pool_ret`）。
- 驗證時分 `src`（自動／手動）報告：自動選入組 `ret − pool_ret` 的分布、勝率、`mdd`；樣本累積前不下結論。
- 驗證結論出來前不得改門檻（80／9）來「修」結果；要改＝改本節、`build_pick2.py` 常數與 `spec` 版本並記 CHANGELOG，舊紀錄不回頭重寫。
