# postmkt — 盤後分析

台股盤後資料的靜態儀表板（單一 `index.html`，無 build 工具），
是[股市雷達 Hub](https://shihpc.github.io/) 的子站之一。

## 六個 Tab

| Tab | 資料源 | 內容 |
|---|---|---|
| 主動ETF | taiwan-flow-live-v2 `data/aetf/`（跨 repo 唯讀） | 每日投組快照、主動加減碼、進出個股、次產業流向 |
| 融資 | FinMind `TaiwanStockMarginPurchaseShortSale` | 融資餘額增減排行、融資使用率排行 |
| 借券 | FinMind `TaiwanStockSecuritiesLending` | 借券成交量排行（逐筆彙總） |
| 融券借券賣出餘額 | FinMind `TaiwanDailyShortSaleBalances` | 融券餘額增減、借券賣出（SBL）餘額增減 |
| 當沖 | FinMind `TaiwanStockDayTrading` + `TaiwanStockPrice` | 當沖金額排行、當沖比重排行 |
| 鉅額交易 | FinMind `TaiwanStockBlockTrade` | 當日逐筆列表，依金額排序 |

## 架構

- `build_postmkt.py`：抓 FinMind 5 個 dataset 的最新交易日全市場資料，
  各 tab 預先聚合排序（排行榜前 50 檔、鉅額全量），輸出 `data/postmkt.json`。
  找不到最新交易日資料時自動往前回退最多 5 天。
- `.github/workflows/build.yml`：平日 21:30 台北（13:30 UTC）排程＋手動觸發，
  跑完自動 commit `data/postmkt.json`。
- 前端不直連 FinMind（避免曝露 token），只讀靜態 JSON。
- 主動ETF tab 直接讀 taiwan-flow-live-v2 的 raw JSON，不搬遷該站管線。

## 部署設定（需手動做一次）

1. **Secret**：repo Settings → Secrets and variables → Actions →
   New repository secret，名稱 `FINMIND_TOKEN`，值填 FinMind API token（Sponsor 方案）。
2. **GitHub Pages**：Settings → Pages → Source 選 `Deploy from a branch`，
   Branch 選 `main` / `(root)` → Save。
3. （可選）Actions tab 手動跑一次 `build postmkt data` 產生第一份資料。

## 本機開發

```bash
pip install -r requirements.txt
FINMIND_TOKEN=xxx python build_postmkt.py
python -m http.server 8000   # 開 http://localhost:8000
```
