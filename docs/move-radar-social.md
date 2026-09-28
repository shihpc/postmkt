# 籌碼雷達、社群聲量搬到盤後分析 — 驗收條件

**寫於** 2026-09-28，動手前定稿。**使用者裁決（2026-09-28，主對話直接選定）**：
「籌碼雷達」（原 taiwan-flows `radar` tab）與「社群聲量」（原 taiwan-stock-news `social` tab）**搬到 postmkt**；
**原站兩個 tab 直接移除，不留搬遷提示**。「市場情緒」tab 也改放 postmkt，另批處理（見 `docs/sentiment-tab.md`，本批不做）。

**涉及 repo（皆在分支 `claude/investment-site-optimization-nac77h`）**：
- `/home/user/postmkt`：新增兩個 tab（本批主體）。
- `/home/user/taiwan-flows`：移除 `radar` tab。
- `/home/user/taiwan-stock-news`：移除 `social` tab。**管線不動**：`build_social.py`、Hetzner cron、`data/social/**` 照舊產在該 repo。

## 0. 搬遷原則
- **邏輯逐字沿用、不改口徑**：兩個 tab 在原站都已通過 fresh-context 驗收並上線，規格正本仍是
  `taiwan-flows/docs/radar-tab.md` 與 `taiwan-stock-news/docs/social-display.md`（含 §1b 紅綠／排行／雙確認建議／參考價位，
  **這些是使用者本人在主對話直接選定的規格，已在線上運作**）。本批是搬家，不是改功能。
- **資料不搬，改讀路徑**（全部同源 `shihpc.github.io`，postmkt CSP `connect-src 'self'` 已涵蓋，**CSP 不改**）：
  | 用途 | 原路徑 | postmkt 內的新路徑 |
  |---|---|---|
  | 類股 r5／r20 | taiwan-flows 同源 `data/sector_ranges_lite.json` | `../taiwan-flows/data/sector_ranges_lite.json` |
  | 大戶持股／參考價位 | `../postmkt/data/diag/diag.json` | 本 repo 同源 `data/diag/diag.json` |
  | 社群產物 | taiwan-stock-news 同源 `data/social/` | `../taiwan-stock-news/data/social/` |
- 本機驗證：http.server 起在 `/home/user`，以 `/postmkt/` 開頁，三個 repo 的相對路徑才都可達。

## 1. 硬約束
| # | 約束 | 驗法 |
|---|---|---|
| P1 | postmkt 只改 `index.html`＋`docs/`＋`CLAUDE.md`／`README.md`＋新增測試；後端、workflow、`data/**` 零改動 | `git diff --stat` |
| P2 | 既有 14 個 tab 行為不變；hash 既有 key（`tab`／`code`／`sub`／`stock`）語意不變；`#tab=mychg` 深連結仍有效 | Playwright |
| P3 | 新 tab id：`chipradar`「籌碼雷達」、`social`「社群聲量」，加在 `TABS` 末尾「日期」之前；新 hash key 只有 `rcls`／`rinv`（僅 tab=chipradar）與 `sd`（僅 tab=social），白名單＋非法值靜默退回 | 測試＋Playwright |
| P4 | 首屏不多載：兩個 tab 的資料只在切到該 tab 時載入（沿用各自原本的 lazy 行為） | 首屏請求清單與改動前相同 |
| P5 | 注入面：外來字串（類股名、股名、產業、標題、作者、URL、日期）一律 `esc()`；文章連結只接受 `https://www.ptt.cc/` 開頭 | 注入測試 |
| P6 | 讀不到跨站資料時各自降級（籌碼雷達上半讀不到 taiwan-flows、社群讀不到 news、建議讀不到 diag），不影響其他 tab、pageerror 零 | `page.route` 回 404 |
| P7 | 原站移除乾淨：taiwan-flows 回到 9→8 個 tab、taiwan-stock-news 6→5 個 tab；`python tests/parity.py --n 1 5 10 20 65` 零差異；news `python -m pytest tests/ -q` 全綠（移除 `test_social_display.py` 或改為測 postmkt 版） | 實跑 |
| P8 | 文件同步：三個 repo 的 CLAUDE.md（tab 數、hash、跨站依賴）與 README；**postmkt CLAUDE.md 的「14 個 tab」相關敘述全部更新為 16**；「persist 14 tab 零 console error」等驗證慣例同步 | grep |

## 2. 驗收清單（fresh-context 驗收者逐條，綁三個 repo 的 commit）
- [ ] Q1 P1–P8 逐條
- [ ] Q2 postmkt `python -m pytest tests/ -q` 全綠；純函式測試搬進 postmkt（`tests/` 下，node 或 python 皆可，沿用原測試案例：籌碼雷達 17 項、社群聲量 13 案），並補 hash 新 key 白名單測試
- [ ] Q3 以真實資料獨立重算：籌碼雷達前 10 列與大戶兩表、社群聲量的標籤／建議／參考價位（用樣本社群檔＋真實 diag.json），與畫面逐格一致
- [ ] Q4 Playwright：postmkt 16 個 tab 逐一點擊 pageerror 零；375／390／1280 三寬度頁面級 `scrollWidth == innerWidth`（postmkt CLAUDE.md 手機驗收條件）
- [ ] Q5 taiwan-flows 8 tab、taiwan-stock-news 5 tab 逐一點擊 pageerror 零；舊網址 `#tab=radar`、`#tab=social` 靜默退回預設
- [ ] **線上（合併後）**：三站各自打開確認；postmkt 兩個新 tab 讀得到跨站資料
