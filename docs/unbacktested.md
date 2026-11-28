# 未經回測而上線的功能：事後驗證到期日登錄

依鐵律第 8 條：沒有回測依據、經使用者裁定先上線的功能，須訂事後驗證到期日；到期未驗須提請使用者裁定延期或下架。
本表是到期日的唯一登錄處；裁定內容與驗證方法以各規格文件為準。

**到期日一律 2027-01-23**（2026-11-28 補訂，自當日起算預設 8 週；這些功能上線時鐵律尚無到期日規定）。

| 功能（tab） | 裁定日 | 裁定與驗證方法登錄處 | 驗證用資料 | 狀態 | 到期日 |
|---|---|---|---|---|---|
| 選股二多空總分（`pick2`） | 2026-10-18 | `docs/pick2-score.md` §5 | `data/pick2/daily/` 每日快照 | 未驗 | 2027-01-23 |
| 選股二追蹤名單（`pick2`） | 2026-10-19 | `docs/pick2-score.md` §7.4 | `data/pick2/daily/`、`track.json` | 未驗 | 2027-01-23 |
| 市場總覽交集排序，流入側（`overview`） | 2026-11-12 | `docs/market-overview.md` | `data/overview/daily/` 每日快照 | 未驗 | 2027-01-23 |
| 市場總覽資金流出側與我的持股對照（`overview`） | 2026-11-13 | `docs/market-overview.md` §6、§7 | 同上（`out`） | 未驗 | 2027-01-23 |
| 社群聲量紅綠、排行、雙確認建議、參考價位（`social`） | 2026-09-28 | `taiwan-stock-news/docs/social-display.md` §1b | `taiwan-stock-news/data/social/` 每日檔 | 未驗；驗證方法尚未訂 | 2027-01-23 |
| 月營收 Beat／Miss 分類（`revenue`） | 2026-11-12 | `docs/revenue-beatmiss.md` §7、`docs/revenue-backtest.md` | `data/revenue/backtest/` | **已回測**（2026-11-13）：只有 20 日的 Beat 類合計對 Miss 類合計達顯著；使用者同日裁定標示維持不動 | 不適用 |

到期前要做的事：對「未驗」各列提出驗證結果，或提請使用者裁定延期／下架。社群聲量一列須先訂驗證方法。
