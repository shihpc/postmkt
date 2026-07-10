# build_postmkt.py — 盤後分析資料管線
#
# 抓 FinMind 5 個盤後 dataset（全市場、單日），各 tab 預先聚合/排序，
# 輸出單一 data/postmkt.json 給前端（index.html）讀取。
# token 讀環境變數 FINMIND_TOKEN（GitHub Actions 由 secrets 帶入）。
#
# 排行榜每表取前 50 檔；鉅額交易本質稀疏，保留全量。

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
BASE = "https://api.finmindtrade.com/api/v4/data"
TOP_N = 50
MAX_BACK_DAYS = 5


def token() -> str:
    t = os.environ.get("FINMIND_TOKEN", "").strip()
    if not t:
        raise RuntimeError("找不到環境變數 FINMIND_TOKEN")
    return t


def api_get(dataset: str, **params) -> list:
    """通用 /api/v4/data 查詢（同 taiwan-flow-live-v2 的封裝寫法）。"""
    params.update(dataset=dataset, token=token())
    r = requests.get(BASE, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()
    if j.get("status") not in (200, None):
        raise RuntimeError(f"{dataset}: {j.get('msg')}")
    return j.get("data") or []


def fetch_latest(dataset: str, base_date: dt.date) -> tuple[str, list]:
    """從 base_date 起往前回退最多 MAX_BACK_DAYS 天，取第一個有資料的交易日（全市場查詢）。"""
    for back in range(MAX_BACK_DAYS + 1):
        d = (base_date - dt.timedelta(days=back)).isoformat()
        rows = api_get(dataset, start_date=d, end_date=d)
        if rows:
            print(f"  {dataset}: {d} -> {len(rows)} 筆")
            return d, rows
    print(f"  {dataset}: {base_date} 起回退 {MAX_BACK_DAYS} 天皆無資料")
    return "", []


def fetch_daytrading(base_date: dt.date) -> tuple[str, list, list]:
    """當沖需已 settle 的 Volume（約 21:30 後），且要有同日 TaiwanStockPrice 當比重分母。
    兩者任一缺就往前回退（當沖標的清單盤前就有、但 Volume 全空，不能算有資料）。"""
    for back in range(MAX_BACK_DAYS + 1):
        d = (base_date - dt.timedelta(days=back)).isoformat()
        rows = api_get("TaiwanStockDayTrading", start_date=d, end_date=d)
        if not any((r.get("Volume") or 0) > 0 for r in rows):
            continue
        price = api_get("TaiwanStockPrice", start_date=d, end_date=d)
        if not price:
            continue
        print(f"  TaiwanStockDayTrading: {d} -> {len(rows)} 筆；TaiwanStockPrice -> {len(price)} 筆")
        return d, rows, price
    print(f"  TaiwanStockDayTrading: {base_date} 起回退 {MAX_BACK_DAYS} 天皆無已結算資料")
    return "", [], []


def stock_names() -> dict:
    """TaiwanStockInfo 建 code -> 中文名 對照（同一 code 取第一筆）。"""
    rows = api_get("TaiwanStockInfo")
    names = {}
    for r in rows:
        c = r.get("stock_id")
        if c and c not in names:
            names[c] = r.get("stock_name") or ""
    print(f"  TaiwanStockInfo: {len(names)} 檔對照")
    return names


# ---------- 各 tab 聚合 ----------

def build_margin(date: str, rows: list, nm: dict) -> dict:
    """融資：餘額增減排行（今日-昨日，張）＋融資使用率排行（餘額/限額）。"""
    recs = []
    for r in rows:
        bal = r.get("MarginPurchaseTodayBalance") or 0
        prev = r.get("MarginPurchaseYesterdayBalance") or 0
        limit = r.get("MarginPurchaseLimit") or 0
        c = r.get("stock_id", "")
        recs.append({
            "c": c, "n": nm.get(c, ""),
            "bal": bal, "chg": bal - prev, "limit": limit,
            "usage": round(bal / limit * 100, 2) if limit > 0 else None,
        })
    inc = sorted((x for x in recs if x["chg"] > 0), key=lambda x: -x["chg"])[:TOP_N]
    dec = sorted((x for x in recs if x["chg"] < 0), key=lambda x: x["chg"])[:TOP_N]
    usage = sorted((x for x in recs if x["usage"] is not None and x["bal"] > 0),
                   key=lambda x: -x["usage"])[:TOP_N]
    return {"date": date, "increase": inc, "decrease": dec, "usage": usage}


def build_lending(date: str, rows: list, nm: dict) -> dict:
    """借券：逐筆成交明細依股票彙總，當日借券成交量排行。"""
    agg = {}
    for r in rows:
        c = r.get("stock_id", "")
        o = agg.setdefault(c, {"c": c, "n": nm.get(c, ""), "vol": 0, "deals": 0,
                               "close": None, "fee_max": None})
        o["vol"] += r.get("volume") or 0
        o["deals"] += 1
        if r.get("close") is not None:
            o["close"] = r["close"]
        fr = r.get("fee_rate")
        if fr is not None and (o["fee_max"] is None or fr > o["fee_max"]):
            o["fee_max"] = fr
    top = sorted(agg.values(), key=lambda x: -x["vol"])[:TOP_N]
    return {"date": date, "top": top}


def build_short_balance(date: str, rows: list, nm: dict) -> dict:
    """融券餘額增減 + 借券賣出餘額增減 兩張排行（原始單位為股，轉成張）。"""
    ms, sbl = [], []
    for r in rows:
        c = r.get("stock_id", "")
        n = nm.get(c, "")
        m_bal = (r.get("MarginShortSalesCurrentDayBalance") or 0) / 1000
        m_chg = m_bal - (r.get("MarginShortSalesPreviousDayBalance") or 0) / 1000
        s_bal = (r.get("SBLShortSalesCurrentDayBalance") or 0) / 1000
        s_chg = s_bal - (r.get("SBLShortSalesPreviousDayBalance") or 0) / 1000
        if m_chg:
            ms.append({"c": c, "n": n, "bal": round(m_bal), "chg": round(m_chg)})
        if s_chg:
            sbl.append({"c": c, "n": n, "bal": round(s_bal), "chg": round(s_chg)})
    ms.sort(key=lambda x: -abs(x["chg"]))
    sbl.sort(key=lambda x: -abs(x["chg"]))
    return {"date": date, "margin_short": ms[:TOP_N], "sbl": sbl[:TOP_N]}


def build_daytrading(date: str, rows: list, price_rows: list, nm: dict) -> dict:
    """當沖：金額排行＋當沖比重排行（分母 = 同日 TaiwanStockPrice 的 Trading_Volume）。"""
    tv = {r.get("stock_id"): (r.get("Trading_Volume") or 0) for r in price_rows}
    recs = []
    for r in rows:
        vol = r.get("Volume") or 0
        if vol <= 0:
            continue
        c = r.get("stock_id", "")
        amt = ((r.get("BuyAmount") or 0) + (r.get("SellAmount") or 0)) / 2
        total = tv.get(c) or 0
        recs.append({
            "c": c, "n": nm.get(c, ""),
            "vol": vol, "amt": round(amt),
            "ratio": round(vol / total * 100, 2) if total > 0 else None,
        })
    by_amount = sorted(recs, key=lambda x: -x["amt"])[:TOP_N]
    # 比重榜過濾極小量股（總量 < 500 張）避免失真
    by_ratio = sorted((x for x in recs if x["ratio"] is not None and (tv.get(x["c"]) or 0) >= 500_000),
                      key=lambda x: -x["ratio"])[:TOP_N]
    return {"date": date, "by_amount": by_amount, "by_ratio": by_ratio}


def build_blocktrade(date: str, rows: list, nm: dict) -> dict:
    """鉅額交易：當日逐筆列表，依金額排序（全量，本質稀疏）。"""
    out = []
    for r in rows:
        c = r.get("stock_id", "")
        out.append({
            "c": c, "n": nm.get(c, ""),
            "type": r.get("trade_type", ""),
            "price": r.get("price"),
            "vol": r.get("volume") or 0,
            "money": r.get("trading_money") or 0,
        })
    out.sort(key=lambda x: -x["money"])
    return {"date": date, "rows": out}


def main() -> None:
    today = dt.date.today()
    print("抓取 FinMind 盤後資料…")
    nm = stock_names()

    d_margin, r_margin = fetch_latest("TaiwanStockMarginPurchaseShortSale", today)
    d_lend, r_lend = fetch_latest("TaiwanStockSecuritiesLending", today)
    d_short, r_short = fetch_latest("TaiwanDailyShortSaleBalances", today)
    d_dt, r_dt, r_price = fetch_daytrading(today)
    d_block, r_block = fetch_latest("TaiwanStockBlockTrade", today)

    dates = [d for d in (d_margin, d_lend, d_short, d_dt, d_block) if d]
    out = {
        "date": max(dates) if dates else "",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "margin": build_margin(d_margin, r_margin, nm),
        "lending": build_lending(d_lend, r_lend, nm),
        "short_balance": build_short_balance(d_short, r_short, nm),
        "daytrading": build_daytrading(d_dt, r_dt, r_price, nm),
        "blocktrade": build_blocktrade(d_block, r_block, nm),
    }

    dst = ROOT / "data" / "postmkt.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"輸出 {dst}（{dst.stat().st_size:,} bytes）")


if __name__ == "__main__":
    try:
        sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass
    main()
