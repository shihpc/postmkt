# 盤後分析頁面 — FinMind dataset 研究與驗證

- 研究日期：2026-07-10
- 驗證用交易日：2026-07-09（週四，正常交易日）
- 驗證用股票：2330（台積電，個股查詢），另用不帶 `data_id` 的全市場查詢確認涵蓋檔數
- 呼叫方式：`GET https://api.finmindtrade.com/api/v4/data`，帶 `dataset` / `data_id`(可選) / `start_date` / `end_date` / `token`
- Token 讀取：`taiwan-flow-live-v2/.env` 的 `FINMIND_TOKEN`（付費 Sponsor 方案）。**本文件不含任何 token 明碼。**
- 驗證腳本：`C:\Users\施伯承\AppData\Local\Temp\claude\...\scratchpad\verify_postmarket.py`（暫存目錄，內含 token 讀取邏輯但不含明碼字串，執行後輸出見同目錄 `output.txt`）
- 資料來源：FinMind 官方文件全文 `C:\Users\施伯承\Desktop\Claude\FinMind\llms-full.txt`

---

## 1. 融資 → `TaiwanStockMarginPurchaseShortSale`（個股融資融劵表）

- **結論：找到，實測 OK。**
- Tier：Free（帶 data_id）／Backer/Sponsor（全市場，不帶 data_id）
- Data range：2001-01-01 ~ now，Mon-Fri 21:00 更新
- 主要欄位：`date, stock_id, MarginPurchaseBuy, MarginPurchaseCashRepayment, MarginPurchaseLimit, MarginPurchaseSell, MarginPurchaseTodayBalance, MarginPurchaseYesterdayBalance, Note, OffsetLoanAndShort, ShortSaleBuy, ShortSaleCashRepayment, ShortSaleLimit, ShortSaleSell, ShortSaleTodayBalance, ShortSaleYesterdayBalance`
  - 融資：`MarginPurchase*` 欄位（買進/賣出/現金償還/限額/今日餘額/昨日餘額）
  - 融券：`ShortSale*` 欄位同構
  - 融資使用率可自行計算：`MarginPurchaseTodayBalance / MarginPurchaseLimit`
- 測試方法：`data_id=2330, start_date=2026-07-09, end_date=2026-07-09`（1 筆）；再用 `start_date=2026-07-09` 不帶 data_id 取全市場（**2194 筆**，涵蓋全市場個股，資料量合理）
- 真實回應片段（2330，2026-07-09）：
```json
{
  "date": "2026-07-09",
  "stock_id": "2330",
  "MarginPurchaseBuy": 1064,
  "MarginPurchaseCashRepayment": 14,
  "MarginPurchaseLimit": 6483092,
  "MarginPurchaseSell": 272,
  "MarginPurchaseTodayBalance": 33061,
  "MarginPurchaseYesterdayBalance": 32283,
  "Note": " ",
  "OffsetLoanAndShort": 0,
  "ShortSaleBuy": 14,
  "ShortSaleCashRepayment": 0,
  "ShortSaleLimit": 6483092,
  "ShortSaleSell": 0,
  "ShortSaleTodayBalance": 71,
  "ShortSaleYesterdayBalance": 85
}
```

---

## 2. 借券 → `TaiwanStockSecuritiesLending`（借券成交明細）

- **結論：找到，實測 OK（注意：這是「成交明細」，非「餘額」表；每檔股票當日可能有多筆逐筆借券成交record，不是單一彙總列）。**
- Tier：Free（帶 data_id）／Backer/Sponsor（全市場）
- Data range：2001-05-01 ~ now，Mon-Fri 15:00 更新
- 主要欄位：`date, stock_id, transaction_type（議借/競價）, volume, fee_rate, close, original_return_date, original_lending_period`
- 測試方法：`data_id=2330, start_date=2026-07-09, end_date=2026-07-09`（5 筆逐筆成交）；`start_date=2026-07-09` 不帶 data_id 全市場（**1094 筆**，橫跨多檔股票的逐筆借券成交，資料量合理，非稀疏）
- 真實回應片段（2330，2026-07-09，前3筆逐筆成交）：
```json
[
  {
    "date": "2026-07-09",
    "stock_id": "2330",
    "transaction_type": "議借",
    "volume": 124,
    "fee_rate": 0.22,
    "close": 2415.0,
    "original_return_date": "2027-01-08",
    "original_lending_period": 183
  },
  {
    "date": "2026-07-09",
    "stock_id": "2330",
    "transaction_type": "議借",
    "volume": 190,
    "fee_rate": 1.0,
    "close": 2415.0,
    "original_return_date": "2027-01-08",
    "original_lending_period": 183
  }
]
```
- 若需「借券餘額」（存量）而非「成交明細」（增量），請見第 3 項的 `SBLShortSales*` 欄位。

---

## 3. 融券餘額 + 借券賣出餘額 → `TaiwanDailyShortSaleBalances`（信用額度總量管制餘額表）

- **結論：找到，實測 OK。台灣證交所「融資融券餘額」報表中的融券部分 + 獨立的「借券賣出餘額」報表，FinMind 把兩者合併在同一個 dataset 裡，用欄位前綴區分。**
- Tier：Free（帶 data_id）／Backer/Sponsor（全市場）
- Data range：2005-07-01 ~ now，Mon-Fri 21:00 更新
- 主要欄位（每檔股票一列）：
  - 融券（信用交易融券）：`MarginShortSalesPreviousDayBalance, MarginShortSalesShortSales, MarginShortSalesShortCovering, MarginShortSalesStockRedemption, MarginShortSalesCurrentDayBalance, MarginShortSalesQuota`
  - 借券賣出（SBL 借券系統）：`SBLShortSalesPreviousDayBalance, SBLShortSalesShortSales, SBLShortSalesReturns, SBLShortSalesAdjustments, SBLShortSalesCurrentDayBalance, SBLShortSalesQuota, SBLShortSalesShortCovering`
  - 共同：`stock_id, date`
- 測試方法：`data_id=2330, start_date=2026-07-09, end_date=2026-07-09`（1 筆彙總）；`start_date=2026-07-09` 不帶 data_id 全市場（**2215 筆**，涵蓋全市場，資料量合理）
- 真實回應片段（2330，2026-07-09）：
```json
{
  "stock_id": "2330",
  "MarginShortSalesPreviousDayBalance": 85000,
  "MarginShortSalesShortSales": 0,
  "MarginShortSalesShortCovering": 14000,
  "MarginShortSalesStockRedemption": 0,
  "MarginShortSalesCurrentDayBalance": 71000,
  "MarginShortSalesQuota": 6483092516,
  "SBLShortSalesPreviousDayBalance": 11347514,
  "SBLShortSalesShortSales": 11000,
  "SBLShortSalesReturns": 0,
  "SBLShortSalesAdjustments": 0,
  "SBLShortSalesCurrentDayBalance": 11358514,
  "SBLShortSalesQuota": 12738328,
  "SBLShortSalesShortCovering": 0,
  "date": "2026-07-09"
}
```
- 補充：另有 `TaiwanStockMarginPurchaseShortSale`（第1項）也含 `ShortSaleTodayBalance` 等融券餘額欄位，但**沒有借券（SBL）部分**；若頁面同時要呈現融券餘額與借券賣出餘額，建議統一用本 dataset（`TaiwanDailyShortSaleBalances`），兩塊資料同源、同結構、一次查詢即可。

---

## 4. 當沖 → `TaiwanStockDayTrading`（當日沖銷交易標的及成交量值）

- **結論：找到，實測 OK。**
- Tier：Free（帶 data_id）／Backer/Sponsor（全市場）
- Data range：2014-01-01 ~ now；標的清單與 BuyAfterSale 標記盤前可得，Volume/BuyAmount/SellAmount 約 21:30 後更新
- 主要欄位：`stock_id, date, BuyAfterSale（＊=禁先賣後買 / Y或空白=可雙向）, Volume, BuyAmount, SellAmount`
  - 當沖比重可自行計算：以 `Volume` 對比當日總成交量（需搭配 `TaiwanStockPrice` 等成交量資料）
- 測試方法：`data_id=2330, start_date=2026-07-09, end_date=2026-07-09`（1 筆）；`start_date=2026-07-09` 不帶 data_id 全市場（**2040 筆**，涵蓋全市場，資料量合理）
- 真實回應片段（2330，2026-07-09）：
```json
{
  "stock_id": "2330",
  "date": "2026-07-09",
  "BuyAfterSale": "",
  "Volume": 5382000,
  "BuyAmount": 13112155000,
  "SellAmount": 13122820000
}
```

---

## 5. 鉅額交易 → `TaiwanStockBlockTrade`（鉅額交易日成交資訊）＋ `TaiwanStockBlockTradingDailyReport`（鉅額交易買賣日報表，逐筆券商對手盤）

- **結論：找到，實測 OK。有兩個互補 dataset，依需求擇一或並用。**

### 5a. `TaiwanStockBlockTrade`（鉅額交易日成交資訊，逐筆）
- Tier：Sponsor
- Data range：2005-04-04 ~ now
- 主要欄位：`date, stock_id, trade_type（配對交易/逐筆交易等）, price, volume, trading_money`
- 測試方法：`data_id=2330, start_date=2026-06-01, end_date=2026-07-09`（**212 筆**逐筆鉅額交易，屬本質上稀疏／逐筆的資料，屬正常，非空值）；全市場單日 `start_date=2026-07-09, end_date=2026-07-09`（**51 筆**，橫跨多檔股票，也屬合理逐筆稀疏量）
- 真實回應片段（2330，2026-06-01）：
```json
{
  "date": "2026-06-01",
  "stock_id": "2330",
  "trade_type": "配對交易",
  "price": 2403.79,
  "volume": 10000,
  "trading_money": 24037900
}
```

### 5b. `TaiwanStockBlockTradingDailyReport`（鉅額交易買賣日報表，含券商別）
- Tier：Sponsor
- Data range：**2026-04-28 ~ now**（歷史很短，只能看近期）
- 主要欄位：`securities_trader, price, buy, sell, trade_type, securities_trader_id, stock_id, date`
- 測試方法：`start_date=2026-07-09`（全市場，不支援 data_id 篩選單股於此測試中，直接抓全市場）（**119 筆**，屬合理逐筆券商成交量）
- 真實回應片段（2026-07-09）：
```json
{
  "securities_trader": "元大總公司",
  "price": 27.91,
  "buy": 0,
  "sell": 21500000,
  "trade_type": "配對",
  "securities_trader_id": "9887",
  "stock_id": "00687B",
  "date": "2026-07-09"
}
```
- 若頁面只需「單筆巨額買賣申報」層級（價格/量/金額），用 `TaiwanStockBlockTrade` 即可（歷史長，2005年起）；若要進一步看是哪家券商配對成交，用 `TaiwanStockBlockTradingDailyReport`（但歷史只到 2026-04-28）。

---

## 總結表

| Tab | Dataset | Tier | 狀態 |
|---|---|---|---|
| 融資 | `TaiwanStockMarginPurchaseShortSale` | Free/Sponsor | OK |
| 借券 | `TaiwanStockSecuritiesLending` | Free/Sponsor | OK（逐筆成交明細） |
| 融券＋借券賣出餘額 | `TaiwanDailyShortSaleBalances` | Free/Sponsor | OK（`MarginShortSales*` + `SBLShortSales*`） |
| 當沖 | `TaiwanStockDayTrading` | Free/Sponsor | OK |
| 鉅額交易 | `TaiwanStockBlockTrade`（主）／`TaiwanStockBlockTradingDailyReport`（券商別，補充） | Sponsor | OK |

所有 5 項皆在既有 Sponsor 方案下用全市場查詢（不帶 `data_id`，帶 `start_date`）驗證成功，回傳筆數從數十筆（鉅額交易，本質逐筆稀疏）到兩千餘筆（融資/融券/當沖，涵蓋全市場個股）不等，符合預期。
