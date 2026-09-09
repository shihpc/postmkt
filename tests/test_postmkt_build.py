# build_postmkt 聚合函式（離線 fixture）：零股合計列過濾、lending 瘦身後欄位形狀、
# 當沖 by_ratio 停產。date 傳空字串可跳過所有網路呼叫（TWSE/分點推估）。
import datetime as dt
import json
import pathlib
import re

import pytest

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

def _md_edge_price_rows():
    """close/spread 的各種組合，含缺值與 spread=0 的邊界（代號全部落在母體內）。"""
    return [
        {"stock_id": "2330", "close": 102.0, "spread": 2.0},
        {"stock_id": "2317", "close": 200.0, "spread": -10.0},
        {"stock_id": "1101", "close": 30.0, "spread": 0.0},      # 平盤 → 0.0，不是 None
        {"stock_id": "00637L", "close": 25.5, "spread": None},   # spread 缺 → chg=None
        {"stock_id": "00981A", "close": 15.0, "spread": 0.3},    # 主動式 ETF（字母後綴）
        {"stock_id": "9999", "close": None, "spread": 1.0},      # close 缺 → chg=None
        {"stock_id": "8888", "close": 5.0, "spread": 5.0},       # 前收=0 → 除以零防護 → None
    ]


# 一般股填充列：**必須 > TOP_N**，否則「把輸出改成 rows_out[:TOP_N]」（誤當排行）的
# 突變測試會全綠——2026-09-09 獨立驗收實測過，舊 fixture 只有 6 檔時 104 支測試全過。
_MD_BULK_N = 60


def _md_bulk_price_rows():
    return [{"stock_id": str(1200 + i), "close": 100.0 + i, "spread": 1.0} for i in range(_MD_BULK_N)]


# 真實可持有、但 2026-09-09 舊版「代號型態白名單」誤擋的證券（獨立驗收以 postmkt 自己的
# data/postmkt.json 反查出來的 7 檔，全部逐一實打過 FinMind 確認存在）：
#   91xxxx DR：在 lending.rows 且 n 非空（＝在 nm 內）、px 來自同一份 price_rows
#   01xxxT REIT／2887Z1 雙字元後綴特別股：實打 TaiwanStockPrice data_id 2026-09-08 皆有價
_MD_FALSE_REJECTS = [
    ("910322", "康師傅-DR"), ("910861", "神州-DR"),
    ("911868", "同方友友-DR"), ("912000", "晨訊科-DR"),
    ("01002T", "土銀國泰R1"), ("01004T", "土銀富邦R2"),
    ("2887Z1", "台新新光己特"),
    # 同一檔金控的單字元後綴特別股，舊版通過、新版也要通過（白名單破口的對照組）
    ("2887F", "台新新光戊特二"),
]


def _md_holdable_price_rows():
    return [{"stock_id": c, "close": 20.0, "spread": 0.2} for c, _ in _MD_FALSE_REJECTS]


# ETN（2026-09-09「同日修正之三」納入宇宙）：**是可以被持有的證券**，擋掉會讓持有者在前端
# 看到「查無此代號（已下市/停牌/代號有誤）」。FinMind `TaiwanStockInfo` 全表（2026-09-09 匿名
# 實查 3,147 檔）裡 ETN 共 48 檔、**代號一律 `02` 開頭且不帶 U**（`020000`–`020041`／`02001L`
# 這類字母後綴）。`020019U` 那種 6 碼＋U 的寫法**全表零命中**，這裡仍放一筆，是為了守住
# 「`\d{6}U` 那條黑名單分支確實已拿掉」（形狀層守門，不是宣稱 FinMind 有這種寫法）。
_MD_ETN = [
    ("020041", "兆豐半導體氣候N"),   # FinMind 實際寫法（2026-09-08 實打有價 20.87）
    ("02001L", "富邦蘋果正二N"),     # 字母後綴（同上，138.8）
    ("020019U", "某ETN(U 寫法)"),    # 6 碼＋U：FinMind 沒有這種寫法，守 `\d{6}U` 已移除
]


def _md_noise_price_rows():
    """TaiwanStockPrice 單日全市場實測 45,675 列（2026-09-09 CI），絕大多數是這類非證券商品。"""
    return [
        {"stock_id": "030018", "close": 1.2, "spread": 0.1},     # 認購權證（6 碼，03 開頭）
        {"stock_id": "715001", "close": 0.8, "spread": -0.05},   # 認售權證（7 開頭 6 碼）
        {"stock_id": "710553", "close": 0.46, "spread": -0.05},  # 上櫃權證，**實測在 nm 裡**（見下）
        {"stock_id": "73107P", "close": 0.3, "spread": 0.0},     # 上櫃權證（5 碼＋字母）
        {"stock_id": "TAIEX", "close": 25000.0, "spread": 1.0},  # 大盤偽代號（nm 裡真的有）
        {"stock_id": "009800", "close": 3.3, "spread": 0.1},     # 代號型態像 ETF、但不在 TaiwanStockInfo
        {"stock_id": "7654", "close": 50.0, "spread": 1.0},      # 代號型態合法、但不在 TaiwanStockInfo
    ]


def _md_etn_price_rows():
    return [{"stock_id": c, "close": 20.0, "spread": 0.2} for c, _ in _MD_ETN]


def _md_price_rows():
    return (_md_edge_price_rows() + _md_bulk_price_rows()
            + _md_holdable_price_rows() + _md_etn_price_rows() + _md_noise_price_rows())


def _md_nm():
    """TaiwanStockInfo 對照（本管線既有的 nm）。

    **它不是乾淨的白名單**：2026-09-09 匿名實查全表 3,147 檔，混了 industry_category 為
    「所有證券」的權證 36 檔（例 `710553`／`73107P`）、`Index`／`大盤` 偽代號 32 筆
    （`TAIEX`…）、以及 ETN 48 檔（ETN 已改為納入宇宙）。fixture 照這個事實把它們放進 nm，
    才測得出黑名單／形狀閘門真的有作用（而不是被 nm 順手擋掉的假陽性）。

    **`030018`／`715001` 是實查該表沒有的形狀**（36 檔權證全部 `7` 開頭、皆為 6 碼），
    這裡仍放進 nm，是為了讓 `RE_MARKET_EXCLUDE` 的 `0[3-9]…` 防禦性分支有測試守著。
    """
    codes = [r["stock_id"] for r in _md_edge_price_rows() + _md_bulk_price_rows()]
    nm = {c: f"名{c}" for c in codes}
    nm.update(dict(_MD_FALSE_REJECTS))
    nm.update(dict(_MD_ETN))
    nm.update({"030018": "某認購權證", "715001": "某認售權證",
               "710553": "穩懋統一9B購03", "73107P": "原相國票9B售02",
               "TAIEX": "TAIEX"})
    return nm


def _md_universe():
    """預期宇宙＝price_rows ∩ nm − 黑名單（權證／指數偽代號；**ETN 在宇宙內**）。
    **刻意不寫成 sorted(_md_nm())**：nm 本身就含權證與偽代號（見 _md_nm docstring）。"""
    codes = [r["stock_id"] for r in _md_edge_price_rows() + _md_bulk_price_rows()]
    return sorted(codes + [c for c, _ in _MD_FALSE_REJECTS] + [c for c, _ in _MD_ETN])


def _md_inst_rows():
    return [
        {"stock_id": "2330", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 1_000_000},
        {"stock_id": "2330", "name": "Foreign_Dealer_Self", "buy": 0, "sell": 500_000},
        {"stock_id": "2330", "name": "Investment_Trust", "buy": 100_000, "sell": 400_000},
        {"stock_id": "2317", "name": "Dealer_self", "buy": 900_000, "sell": 0},  # 只有自營 → f/t 為 0
    ]


def _md_build(date="2026-09-07", price=None, inst=None, inst_date="2026-09-07", nm=None):
    return bp.build_market_daily(date,
                                 _md_price_rows() if price is None else price,
                                 _md_inst_rows() if inst is None else inst,
                                 inst_date,
                                 _md_nm() if nm is None else nm)


def test_market_daily_shape_and_full_coverage():
    out = _md_build()
    assert out["date"] == "2026-09-07"
    assert out["cols"] == ["c", "chg", "f", "t"]
    # 宇宙＝當日 TaiwanStockPrice ∩ TaiwanStockInfo ∩ 母體代號型態，逐檔都在、依代號排序
    codes = [r[0] for r in out["rows"]]
    assert codes == _md_universe()
    assert all(len(r) == len(out["cols"]) for r in out["rows"])


def test_market_daily_is_not_a_ranking_no_truncation():
    """全市場底表，不是排行：列數＝宇宙檔數（**不是** > 0，也不是 TOP_N）。
    fixture 刻意 > TOP_N，才擋得住「rows_out[:TOP_N]」這種把它改成排行的突變。"""
    rows = _md_build()["rows"]
    assert len(_md_universe()) > bp.TOP_N, "fixture 必須 > TOP_N，否則截斷突變測不出來"
    assert len(rows) == len(_md_universe())
    assert len(rows) > bp.TOP_N


def test_market_daily_universe_includes_etn_excludes_warrants():
    """**ETN 在宇宙內、權證不在**（2026-09-09「同日修正之三」，使用者裁定）。

    - **ETN 是可以被持有的證券**（`TaiwanStockInfo` 全表 48 檔），擋掉它會讓持有者在前端
      看到「查無此代號（已下市/停牌/代號有誤）」——與事實不符，故納入。
    - **權證仍必須擋**：全市場 4.5 萬檔，納入會讓 `data/postmkt.json` 再爆到 2.7MB（實測）。

    **權證與偽代號全部同時被放進 fixture 的 nm**（`TaiwanStockInfo` 真的收了 36 檔權證與
    32 筆指數/產業別偽代號；`030018`／`715001` 是實查沒有的形狀，放進來是為了守住黑名單的
    `0[3-9]…` 防禦性分支），所以擋下它們的必然是黑名單／形狀閘門，不是 nm 閘門。
    """
    codes = {r[0] for r in _md_build()["rows"]}
    # ETN：三種寫法都必須在宇宙內
    for c, n in _MD_ETN:
        assert c in codes, f"{c}（{n}）是 ETN＝可持有的證券，必須在宇宙內"
    # 權證：一檔都不能進
    for c in ("030018", "715001", "710553", "73107P"):
        assert c not in codes, f"{c} 是權證，不該進母體"
    assert "TAIEX" not in codes, "TAIEX 是大盤偽代號，不是證券"
    # ETF（含字母後綴）一檔都不能少——這是這個區塊存在的理由
    for c in ("00637L", "00981A"):
        assert c in codes, f"{c} 是 ETF，必須保留"
    # regex 層直接釘住：02 開頭（ETN）不得命中黑名單，03–09／7 開頭（權證）必須命中
    for c in ("020041", "02001L", "020000", "020019U"):
        assert not bp.RE_MARKET_EXCLUDE.match(c), f"{c} 是 ETN，黑名單不得命中"
    for c in ("030018", "090001", "715001", "710553", "73107P"):
        assert bp.RE_MARKET_EXCLUDE.match(c), f"{c} 是權證，黑名單必須命中"


def test_market_daily_universe_keeps_dr_reit_and_preferred_shares():
    """**必修 1（2026-09-09 獨立驗收）**：舊版把代號型態當白名單，誤擋 DR／REIT／雙字元後綴
    特別股——它們是真的可以被持有的證券，被擋掉會在前端呈現成「查無此代號」（＝已下市/停牌/
    代號有誤），而不是「資料源不涵蓋」。這是相對 e96c5d8（全收）的覆蓋率退步。"""
    codes = {r[0] for r in _md_build()["rows"]}
    for c, n in _MD_FALSE_REJECTS:
        assert c in codes, f"{c}（{n}）是可持有的證券，不得被宇宙過濾誤擋"
    # 型態相鄰的反向對照：6 碼 00/01/02 開頭（ETF／REIT／ETN）要留，03–09 開頭（權證）要擋
    assert bp.RE_MARKET_EXCLUDE.match("030018") and not bp.RE_MARKET_EXCLUDE.match("006201")
    assert not bp.RE_MARKET_EXCLUDE.match("00637L") and not bp.RE_MARKET_EXCLUDE.match("01004T")
    assert not bp.RE_MARKET_EXCLUDE.match("020041")


def test_market_daily_universe_gate_is_stock_info_then_blacklist():
    """兩道過濾的分工（2026-09-09 反轉）：**nm 是主閘門**（45,675 → ≤3,147，體積由它解決），
    代號型態只當黑名單（擋 nm 自己混進來的權證／ETN／偽代號）。"""
    codes = {r[0] for r in _md_build()["rows"]}
    assert "7654" not in codes and "009800" not in codes   # 型態合法但不在 Info → nm 閘門擋下
    # 反向：代號型態合法但 Info 沒有 → 加進 Info 就會收（證明擋它的是 nm、不是型態）
    nm3 = dict(_md_nm(), **{"7654": "某股"})
    assert "7654" in {r[0] for r in _md_build(nm=nm3)["rows"]}
    # 反向：把新商品塞進 Info，只要不在黑名單就一律放行（寧可多放、不可少放）
    nm4 = dict(_md_nm(), **{"1234X9": "某新型態證券"})
    price = _md_price_rows() + [{"stock_id": "1234X9", "close": 10.0, "spread": 0.1}]
    assert "1234X9" in {r[0] for r in _md_build(price=price, nm=nm4)["rows"]}


def test_market_daily_universe_no_false_reject_on_real_postmkt_corpus():
    """**回歸母體＝postmkt 自己 data/postmkt.json 各區塊代號的聯集**（2026-09-09 實測 2,284 檔）。

    刻意**不用** taiwan-flows 的 2,650 檔當母體：那份母體是用幾乎同一把尺
    （`build_meta.py` 的 `RE_STOCK`／`RE_ETF`）篩出來的，拿它驗本 regex 是循環論證，
    必然回報 0 誤擋。用本站自己的資料才有鑑別力——舊規則在這份母體上誤擋 7 檔。

    斷言分兩層：①**形狀閘門 `RE_MARKET_CODE` 不得擋掉任何一檔**（它只負責「數字開頭」）；
    ②被擋下的只能是黑名單命中的商品類（權證／ETN），且要把清單印出來，日後真的出現時
    是「看得見的取捨」而不是靜默消失。
    """
    path = pathlib.Path(__file__).resolve().parents[1] / "data" / "postmkt.json"
    if not path.exists():
        pytest.skip("data/postmkt.json 不在（本測試用它當真實回歸母體）")
    doc = json.loads(path.read_text(encoding="utf-8"))
    corpus: set = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("c", "code", "stock_id") and isinstance(v, str):
                    corpus.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for blk in ("margin", "lending", "short_balance", "daytrading", "blocktrade", "oddlot"):
        walk(doc.get(blk))
    assert len(corpus) > 1500, f"母體只有 {len(corpus)} 檔，data/postmkt.json 疑似殘缺"

    shape_rejects = sorted(c for c in corpus if not bp.RE_MARKET_CODE.match(c))
    assert shape_rejects == [], f"形狀閘門誤擋了自家資料裡的代號：{shape_rejects}"
    blacklisted = sorted(c for c in corpus if bp.RE_MARKET_EXCLUDE.match(c))
    # 2026-09-09 實測為空；黑名單納入 ETN 後只剩權證，故被擋的只能是 03–09／7 開頭的權證型態
    assert all(re.match(r"^(?:0[3-9]|7)", c) for c in blacklisted), \
        f"黑名單擋到了非權證型態的代號：{blacklisted}"
    # 反向：自家資料裡的 ETN（若有）必須通過——ETN 是可持有的證券
    etn_in_corpus = sorted(c for c in corpus if re.match(r"^02\d{3}[0-9A-Z]$", c))
    assert all(not bp.RE_MARKET_EXCLUDE.match(c) for c in etn_in_corpus), \
        f"ETN 被黑名單擋下：{etn_in_corpus}"


def test_market_daily_dedupes_and_keeps_basis_date_only():
    """單日查詢（start=end）本來就不會有跨日列；這道是防「哪天改成多日切片」時
    同一代號重複寫入／別天的資料被錯配。"""
    price = [
        {"date": "2026-09-07", "stock_id": "2330", "close": 102.0, "spread": 2.0},
        {"date": "2026-09-05", "stock_id": "2330", "close": 90.0, "spread": -1.0},   # 前一交易日 → 丟棄
        {"date": "2026-09-05", "stock_id": "1101", "close": 30.0, "spread": 1.0},    # 只有別天的 → 整檔不出現
        {"stock_id": "2317", "close": 200.0, "spread": -10.0},                        # 沒有 date 欄 → 當同日
    ]
    out = bp.build_market_daily("2026-09-07", price, [], "2026-09-07", _md_nm())
    by_c = {r[0]: r for r in out["rows"]}
    assert sorted(by_c) == ["2317", "2330"]
    assert by_c["2330"][1] == 2.0   # 留的是基準日那筆（前收 100），不是 09-05 那筆


def test_market_daily_chg_pct_matches_build_daytrading():
    """漲跌%必須與 build_daytrading 同一算式（兩邊共用 _chg_pct，這裡以輸出實測對照）。"""
    price = _md_edge_price_rows()
    dt_rows = [{"stock_id": p["stock_id"], "Volume": 1_000, "BuyAmount": 0, "SellAmount": 0}
               for p in price]
    dt_out = bp.build_daytrading("", dt_rows, price, {})
    dt_chg = {r["c"]: r["chg_pct"] for r in dt_out["by_amount"]}
    md = bp.build_market_daily("2026-09-07", price, [], "2026-09-07", _md_nm())
    md_chg = {r[0]: r[1] for r in md["rows"]}
    assert dt_chg == md_chg
    # 同時釘住實際數值，避免兩邊一起改錯還互相對得上
    assert md_chg == {"2330": 2.0,        # 2 / 前收 100
                      "2317": -4.76,      # -10 / 前收 210
                      "1101": 0.0,        # 平盤是 0.0，不是 None
                      "00981A": 2.04,     # 0.3 / 前收 14.7
                      "00637L": None, "9999": None, "8888": None}


def test_market_daily_missing_inst_is_null_not_zero():
    """刻意與 build_lending 不同：查不到法人資料寫 null，不寫 0（缺資料≠沒異動）。"""
    by_c = {r[0]: r for r in _md_build()["rows"]}
    # 有法人資料：外資 = (300萬-100萬) + (0-50萬) = 150萬股 → 1500 張；投信 -300 張
    assert by_c["2330"][2] == 1500 and by_c["2330"][3] == -300
    # 有法人資料但只有自營 → 真的是 0，不是 None
    assert by_c["2317"][2] == 0 and by_c["2317"][3] == 0
    # 完全查不到法人資料 → None
    for c in ("1101", "00637L", "9999", "8888"):
        assert by_c[c][2] is None and by_c[c][3] is None, f"{c} 缺法人資料應為 None"
    # 對照組：build_lending 現行做法會寫 0（既有缺陷，本區塊刻意不沿用；差異記在 CHANGELOG 2026-09-09）
    lend = bp.build_lending("", [], [{"stock_id": "1101"}], [], [], "", [], [], [], {})
    assert lend["rows"][0]["foreign_vol"] == 0


def test_market_daily_inst_date_mismatch_blanks_f_t():
    """法人資料日 ≠ 基準日 → f/t 一律留 None（寧缺勿混，同 build_lending 的 dt_* 處理）。"""
    out = _md_build(inst_date="2026-09-04")
    assert all(r[2] is None and r[3] is None for r in out["rows"])
    # chg 不受影響（它來自 price_rows 本身）
    assert {r[0]: r[1] for r in out["rows"]}["2330"] == 2.0


def test_market_daily_warns_when_upstream_input_is_empty(capsys):
    """**上游整包為空時必須示警**（2026-09-09 補的守門）。

    原告警條件是 `if price_rows and nm and len(rows_out) < MIN`——`price_rows`（或 `nm`）為空時
    前兩個條件就短路，**最該示警的情況反而靜默**，區塊照樣以 `rows: []` 輸出。前端若沿用
    「不在 `rows` ＝查無此代號」，會把使用者**每一檔**持股都說成「已下市/停牌/代號有誤」
    （README「前端消費 `market_daily` 的必要條件」）。故三種空輸入都必須印出 `⚠ market_daily`。
    """
    for label, kwargs in (
        ("price_rows 為空", {"price": []}),
        ("nm 為空", {"nm": {}}),
        ("兩者皆空", {"price": [], "nm": {}}),
    ):
        out = _md_build(**kwargs)
        err = capsys.readouterr().out
        assert out["rows"] == [], f"{label}：宇宙應為空"
        assert out["cols"] == ["c", "chg", "f", "t"] and "date" in out, f"{label}：區塊形狀不變"
        assert "⚠ market_daily" in err, f"{label}：必須示警，不可靜默輸出 rows: []"
        assert "無法取得異動資料" in err, f"{label}：訊息要指出前端該顯示的文案"

    # 對照組：輸入非空時走的是另一條分支（fixture 只有數十檔，會命中列數不足那條），
    # 不得誤報成「上游輸入為空」——兩種故障的處置不同，訊息必須分得開。
    _md_build()
    err = capsys.readouterr().out
    assert "上游輸入為空" not in err
    assert f"低於 {bp.MARKET_DAILY_MIN_ROWS}" in err


def test_market_daily_does_not_touch_lending():
    """新區塊不得改到 lending：同一份輸入，先後呼叫 build_market_daily 前後 lending 逐位相同。"""
    before = _lending_fixture()
    _md_build()
    after = _lending_fixture()
    assert before == after
    # lending 的欄位形狀維持現狀（rows 是 dict 陣列、不是 market_daily 的二維陣列）
    assert isinstance(before["rows"][0], dict) and "cols" not in before


# ---------- postmkt.json 檔頭契約：date／generated_at 必須是前兩個 key（跨站，2026-09-09） ----------
#
# taiwan-flow-live-v2 Worker 的 `fetchStatusHead`（bytes = 2048）＋`extractHeadFields`，
# 與 claude-harness `tools/freshness_watchdog.py`（HEAD_BYTES = 2048）都只抓本檔的
# Range 檔頭再 regex 撈**第一個** "date"／"generated_at"。任何區塊插到那兩個 key 之前
# 都會讓它們撈到錯的日期或撈不到，而且是**靜默壞掉**（那兩站只會顯示錯的資料日）。
# 下面兩個 regex 與那兩個消費端逐字相同（worker/src/index.js extractHeadFields；
# freshness_watchdog.py head_fields）。
HEAD_BYTES = 2048
HEAD_DATE_RE = re.compile(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"')
HEAD_GEN_RE = re.compile(r'"generated_at"\s*:\s*"([^"]+)"')


def _run_main_offline(monkeypatch, tmp_path):
    """跑真正的 main()，但所有對外呼叫都換成離線 fixture（不碰網路、不寫進 repo 的 data/）。"""
    day = dt.date.today().isoformat()
    price = [dict(r, date=day) for r in _md_price_rows()]
    info = [{"stock_id": c, "stock_name": n} for c, n in _md_nm().items()]

    def fake_api_get(dataset, **kw):
        same_day = kw.get("start_date") == day
        if dataset == "TaiwanStockInfo":
            return info
        if dataset == "TaiwanStockPrice":
            return price if same_day else []
        if dataset == "TaiwanStockDayTrading":
            return [{"stock_id": "2330", "Volume": 1_000, "BuyAmount": 200, "SellAmount": 100}] if same_day else []
        if dataset == "TaiwanStockInstitutionalInvestorsBuySell":
            return _md_inst_rows() if same_day else []
        return []

    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token-for-offline-test")
    monkeypatch.setattr(bp, "api_get", fake_api_get)
    monkeypatch.setattr(bp, "fetch_twse_lending", lambda date, select_type: {})
    monkeypatch.setattr(bp, "fetch_twse_oddlot", lambda base_date, report: ("", []))
    monkeypatch.setattr(bp, "ROOT", tmp_path)
    bp.main()
    return json.loads((tmp_path / "data" / "postmkt.json").read_text(encoding="utf-8"))


def test_output_head_contract_date_and_generated_at_first(monkeypatch, tmp_path):
    out = _run_main_offline(monkeypatch, tmp_path)
    assert list(out)[:2] == ["date", "generated_at"], "檔頭前兩個 key 是跨站契約，不可被新區塊擠掉"
    # 更嚴：對 json.dumps 後的前 2048 bytes 跑與兩個消費端相同的 regex
    head = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")[:HEAD_BYTES].decode("utf-8", "ignore")
    m_date, m_gen = HEAD_DATE_RE.search(head), HEAD_GEN_RE.search(head)
    assert m_date and m_date.group(1) == out["date"]
    assert m_gen and m_gen.group(1) == out["generated_at"]


def test_output_market_daily_is_full_market_and_last(monkeypatch, tmp_path):
    """整條 main() 跑完後，market_daily 仍是全市場底表（不截斷）且排在最後。"""
    out = _run_main_offline(monkeypatch, tmp_path)
    md = out["market_daily"]
    assert list(out)[-1] == "market_daily"
    assert [r[0] for r in md["rows"]] == _md_universe()
    assert len(md["rows"]) > bp.TOP_N
    assert md["date"] == out["lending"]["date"]   # 與 lending 同基準日（lend_date）
