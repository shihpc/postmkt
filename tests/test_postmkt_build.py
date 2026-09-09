# build_postmkt 聚合函式（離線 fixture）：零股合計列過濾、lending 瘦身後欄位形狀、
# 當沖 by_ratio 停產。date 傳空字串可跳過所有網路呼叫（TWSE/分點推估）。
import build_postmkt as bp


# ---------- build_oddlot：TWSE 合計列過濾（TWTC7U/TWT53U 已知坑） ----------

def test_oddlot_filters_total_rows_keeps_etf():
    rows = [
        ["2330", "台積電", "1,000", "10", "500,000"],
        ["00679B", "元大美債20年", "2,000", "5", "60,000"],   # ETF 代號帶字母要保留
        ["合計", "", "999,999", "999", "9,999,999"],           # 中文合計列要濾掉
        ["", "小計", "888", "8", "88,888"],                    # 空代號列要濾掉
        ["2317", "鴻海", "0", "0", "0"],                       # 成交股數 0 要濾掉
    ]
    out = bp.build_oddlot("2026-07-24", rows, "", [])
    codes = [r["c"] for r in out["intraday"]["rows"]]
    assert codes == ["2330", "00679B"]  # 依金額排序
    assert out["intraday"]["rows"][0]["sh"] == 1000
    assert out["after"]["rows"] == []


# ---------- build_lending：瘦身後的欄位形狀（date="" 跳過 TWSE 網路呼叫） ----------

def _lending_fixture():
    margin_rows = [{"stock_id": "2330", "MarginPurchaseTodayBalance": 1000,
                    "MarginPurchaseYesterdayBalance": 900, "MarginPurchaseBuy": 50,
                    "MarginPurchaseLimit": 2000, "OffsetLoanAndShort": 3}]
    short_rows = [{"stock_id": "2330",
                   "SBLShortSalesCurrentDayBalance": 500_000,      # 股 → 500 張
                   "SBLShortSalesPreviousDayBalance": 400_000,
                   "MarginShortSalesCurrentDayBalance": 200_000,
                   "MarginShortSalesPreviousDayBalance": 250_000,
                   "MarginShortSalesQuota": 1_000_000,
                   "SBLShortSalesShortSales": 10_000, "SBLShortSalesReturns": 5_000}]
    inst_rows = [{"stock_id": "2330", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 1_000_000},
                 {"stock_id": "2330", "name": "Investment_Trust", "buy": 100_000, "sell": 400_000}]
    price_rows = [{"stock_id": "2330", "close": 1000.0}]
    return bp.build_lending("", [], margin_rows, short_rows, [], "", price_rows,
                            inst_rows, [], {"2330": "台積電"})


def test_lending_slim_no_derived_fields():
    row = _lending_fixture()["rows"][0]
    # 衍生欄 2026-07-24 起不落地（由前端 augmentLending / build_summary._augment_lending 重建）
    for k in ("plat_total", "plat_total_chg", "plat_total_mv", "sys_mv_chg", "otc_mv_chg",
              "sbl_short_mv", "sbl_short_mv_chg", "margin_short_mv", "margin_short_mv_chg",
              "short_total", "short_total_chg", "short_total_mv", "short_total_mv_chg",
              "margin_mv", "margin_mv_chg", "foreign_net", "trust_net", "dealer_net",
              "foreign_shares_mv"):
        assert k not in row, f"{k} 應已從落地欄位移除"


def test_lending_slim_base_fields_and_px():
    row = _lending_fixture()["rows"][0]
    assert row["px"] == 1000.0
    assert row["sbl_short_bal"] == 500 and row["sbl_short_chg"] == 100
    assert row["margin_short_bal"] == 200 and row["margin_short_chg"] == -50
    assert row["margin_bal"] == 1000 and row["margin_chg"] == 100
    assert row["foreign_vol"] == 2000 and row["trust_vol"] == -300
    assert row["credit_ratio"] == 20.0   # 200/1000
    assert row["short_usage"] == 20.0    # 200/1000 張配額
    assert row["margin_usage"] == 50.0


def test_lending_augment_parity_with_old_backend_formula():
    """前端/摘要端重建公式應與舊後端公式等值（同一 fixture 手算對照）。"""
    import build_summary as bs
    row = dict(_lending_fixture()["rows"][0])
    out = bs._augment_lending([row])[0]
    px = 1000.0
    assert out["foreign_net"] == round(2_000_000 * px / 1000)  # 舊後端：股數差×px÷1000
    assert out["trust_net"] == round(-300_000 * px / 1000)
    assert out["plat_total"] == row["sys_bal"] + row["otc_bal"]


# ---------- build_daytrading：by_ratio 停產、聚合正確 ----------

def test_daytrading_no_by_ratio_and_metrics():
    rows = [{"stock_id": "2330", "Volume": 1_000_000, "BuyAmount": 2_000_000, "SellAmount": 4_000_000}]
    price_rows = [{"stock_id": "2330", "close": 102.0, "spread": 2.0, "max": 103.0, "min": 99.0,
                   "Trading_Volume": 2_000_000}]
    out = bp.build_daytrading("", rows, price_rows, {"2330": "台積電"})
    assert "by_ratio" not in out
    r = out["by_amount"][0]
    assert r["amt"] == 3_000_000          # (買+賣)/2
    assert r["ratio"] == 50.0             # 100萬/200萬股
    assert r["chg_pct"] == 2.0            # spread 2 / 前收 100
    assert r["amp_pct"] == 4.0            # (103-99)/100
    assert "traders" not in r             # date="" 跳過分點推估


# ---------- twseclient.resolve_cols：fields metadata 欄位定位＋固定索引後備 ----------

def test_resolve_cols_by_field_names():
    from twseclient import resolve_cols
    j = {"fields": ["股票代號", "股票名稱", "前日餘額", "本日借券", "本日還券", "本日餘額", "收盤價", "本日餘額市值", "備註"]}
    cols = resolve_cols(j, {
        "prev": (99, ("前日", "餘額"), ("市值",)),
        "bal":  (99, ("餘額",), ("前日", "市值")),
        "mv":   (99, ("市值",), ()),
    })
    assert cols == {"prev": 2, "bal": 5, "mv": 7}


def test_resolve_cols_reordered_fields_still_found():
    from twseclient import resolve_cols
    # TWSE 若調整欄位順序，仍應對到正確欄而非靜默錯值
    j = {"fields": ["股票代號", "股票名稱", "本日餘額市值", "本日餘額", "前日餘額"]}
    cols = resolve_cols(j, {"bal": (5, ("餘額",), ("前日", "市值")), "mv": (7, ("市值",), ())})
    assert cols == {"bal": 3, "mv": 2}


def test_resolve_cols_missing_fields_fallback():
    from twseclient import resolve_cols
    cols = resolve_cols({}, {"bal": (5, ("餘額",), ()), "mv": (7, ("市值",), ())})
    assert cols == {"bal": 5, "mv": 7}


# ---------- fetch_twse_lending：重試序列對齊 twseclient.RETRY_BACKOFFS（2026-09-06） ----------

def test_fetch_twse_lending_retries_follow_backoffs(monkeypatch):
    """暫時性錯誤時依 RETRY_BACKOFFS 等待、共 len+1 次嘗試，全失敗回空 dict（不拋、不中斷管線）。"""
    calls, waits = [], []

    def boom(url, params, timeout=30):
        calls.append(params["selectType"])
        raise RuntimeError("simulated TWSE outage")

    monkeypatch.setattr(bp, "throttled_get", boom)
    monkeypatch.setattr(bp.time, "sleep", lambda s: waits.append(s))
    assert bp.fetch_twse_lending("2026-09-04", "SLB") == {}
    assert len(calls) == len(bp.RETRY_BACKOFFS) + 1
    assert waits == list(bp.RETRY_BACKOFFS)


def test_fetch_twse_lending_success_after_transient_failure(monkeypatch):
    """第 1 次失敗、第 2 次成功：只等一次 RETRY_BACKOFFS[0]、回傳解析結果。"""
    n = {"i": 0}
    waits = []

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"stat": "OK", "fields": [], "data": []}

    def flaky(url, params, timeout=30):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("first hit fails")
        return Resp()

    monkeypatch.setattr(bp, "throttled_get", flaky)
    monkeypatch.setattr(bp.time, "sleep", lambda s: waits.append(s))
    out = bp.fetch_twse_lending("2026-09-04", "NLB")
    assert isinstance(out, dict)
    assert n["i"] == 2 and waits == [bp.RETRY_BACKOFFS[0]]


# ---------- build_market_daily：全市場逐檔精簡表（持股異動 tab 用，2026-09-09） ----------

def _md_price_rows():
    """close/spread 的各種組合，含缺值與 spread=0 的邊界。"""
    return [
        {"stock_id": "2330", "close": 102.0, "spread": 2.0},
        {"stock_id": "2317", "close": 200.0, "spread": -10.0},
        {"stock_id": "1101", "close": 30.0, "spread": 0.0},      # 平盤 → 0.0，不是 None
        {"stock_id": "00637L", "close": 25.5, "spread": None},   # spread 缺 → chg=None
        {"stock_id": "9999", "close": None, "spread": 1.0},      # close 缺 → chg=None
        {"stock_id": "8888", "close": 5.0, "spread": 5.0},       # 前收=0 → 除以零防護 → None
    ]


def _md_inst_rows():
    return [
        {"stock_id": "2330", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 1_000_000},
        {"stock_id": "2330", "name": "Foreign_Dealer_Self", "buy": 0, "sell": 500_000},
        {"stock_id": "2330", "name": "Investment_Trust", "buy": 100_000, "sell": 400_000},
        {"stock_id": "2317", "name": "Dealer_self", "buy": 900_000, "sell": 0},  # 只有自營 → f/t 為 0
    ]


def test_market_daily_shape_and_full_coverage():
    out = bp.build_market_daily("2026-09-07", _md_price_rows(), _md_inst_rows(), "2026-09-07")
    assert out["date"] == "2026-09-07"
    assert out["cols"] == ["c", "chg", "f", "t"]
    # 宇宙＝當日 TaiwanStockPrice 全市場，逐檔都在（不是排行、不截斷），依代號排序
    codes = [r[0] for r in out["rows"]]
    assert codes == sorted(r["stock_id"] for r in _md_price_rows())
    assert all(len(r) == len(out["cols"]) for r in out["rows"])


def test_market_daily_chg_pct_matches_build_daytrading():
    """漲跌%必須與 build_daytrading 同一算式（兩邊共用 _chg_pct，這裡以輸出實測對照）。"""
    price = _md_price_rows()
    dt_rows = [{"stock_id": p["stock_id"], "Volume": 1_000, "BuyAmount": 0, "SellAmount": 0}
               for p in price]
    dt_out = bp.build_daytrading("", dt_rows, price, {})
    dt_chg = {r["c"]: r["chg_pct"] for r in dt_out["by_amount"]}
    md = bp.build_market_daily("2026-09-07", price, [], "2026-09-07")
    md_chg = {r[0]: r[1] for r in md["rows"]}
    assert dt_chg == md_chg
    # 同時釘住實際數值，避免兩邊一起改錯還互相對得上
    assert md_chg == {"2330": 2.0,        # 2 / 前收 100
                      "2317": -4.76,      # -10 / 前收 210
                      "1101": 0.0,        # 平盤是 0.0，不是 None
                      "00637L": None, "9999": None, "8888": None}


def test_market_daily_missing_inst_is_null_not_zero():
    """刻意與 build_lending 不同：查不到法人資料寫 null，不寫 0（缺資料≠沒異動）。"""
    out = bp.build_market_daily("2026-09-07", _md_price_rows(), _md_inst_rows(), "2026-09-07")
    by_c = {r[0]: r for r in out["rows"]}
    # 有法人資料：外資 = (300萬-100萬) + (0-50萬) = 150萬股 → 1500 張；投信 -300 張
    assert by_c["2330"][2] == 1500 and by_c["2330"][3] == -300
    # 有法人資料但只有自營 → 真的是 0，不是 None
    assert by_c["2317"][2] == 0 and by_c["2317"][3] == 0
    # 完全查不到法人資料 → None
    for c in ("1101", "00637L", "9999", "8888"):
        assert by_c[c][2] is None and by_c[c][3] is None, f"{c} 缺法人資料應為 None"
    # 對照組：build_lending 現行做法會寫 0（既有缺陷，本區塊刻意不沿用）
    lend = bp.build_lending("", [], [{"stock_id": "1101"}], [], [], "", [], [], [], {})
    assert lend["rows"][0]["foreign_vol"] == 0


def test_market_daily_inst_date_mismatch_blanks_f_t():
    """法人資料日 ≠ 基準日 → f/t 一律留 None（寧缺勿混，同 build_lending 的 dt_* 處理）。"""
    out = bp.build_market_daily("2026-09-07", _md_price_rows(), _md_inst_rows(), "2026-09-04")
    assert all(r[2] is None and r[3] is None for r in out["rows"])
    # chg 不受影響（它來自 price_rows 本身）
    assert {r[0]: r[1] for r in out["rows"]}["2330"] == 2.0


def test_market_daily_does_not_touch_lending():
    """新區塊不得改到 lending：同一份輸入，先後呼叫 build_market_daily 前後 lending 逐位相同。"""
    before = _lending_fixture()
    bp.build_market_daily("2026-09-07", _md_price_rows(), _md_inst_rows(), "2026-09-07")
    after = _lending_fixture()
    assert before == after
    # lending 的欄位形狀維持現狀（rows 是 dict 陣列、不是 market_daily 的二維陣列）
    assert isinstance(before["rows"][0], dict) and "cols" not in before
