# backtest_revenue 純函式與端到端：離線、免 token（規格 docs/revenue-beatmiss.md §7.4 第 2 條）。
import csv
import datetime as dt
import fnmatch
import glob
import json
import random
from pathlib import Path

import pytest

import backtest_revenue as bt
import build_revenue as br

ROOT = Path(__file__).resolve().parent.parent


def weekdays(start, end, holidays=()):
    """start～end（含）的平日 ISO 字串，扣掉 holidays。"""
    d, out = dt.date.fromisoformat(start), []
    while d <= dt.date.fromisoformat(end):
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def flat(years, base=100.0, growth=1.2, start=2018):
    return {(start + i, m): base * growth ** i for i in range(years) for m in range(1, 13)}


# ---------- 解析 ----------
def test_parse_prices_defensive():
    rows = [{"date": "2024-05-10", "open": 100, "close": "101.5"},
            {"date": "2024-05-13", "open": 0, "close": 0},            # 無成交日
            {"date": "2024-05-14", "open": "x", "close": 5},
            {"date": "2024-05-15", "close": 5},                       # 缺 open
            {"open": 1, "close": 1}, "junk", None]
    assert bt.parse_prices(rows) == {"2024-05-10": (100.0, 101.5)}
    assert bt.parse_prices(None) == {} and bt.parse_prices([{"Date": "2024-05-10", "Open": 1, "Close": 1}]) == {}


def test_parse_index_price_then_close():
    assert bt.parse_index([{"date": "2024-05-10", "price": 40000.5}, {"date": "2024-05-13", "close": 3},
                           {"date": "2024-05-14", "price": None}]) == {"2024-05-10": 40000.5, "2024-05-13": 3.0}


# ---------- 事件日與進出場日 ----------
def test_event_dates_10th_is_trading_day():
    # 2024-04 營收 → 公布月 2024-05；5/10 是週五
    cal = weekdays("2024-04-01", "2024-07-31")
    e = bt.event_dates(cal, 2024, 4)
    assert e["deadline"] == "2024-05-10" and e["t0"] == "2024-05-13"
    assert e["exits"][5] == "2024-05-17"          # 5/13–5/17 共 5 個交易日
    assert e["exits"][10] == "2024-05-24" and e["exits"][20] == "2024-06-07"
    i = cal.index(e["t0"])
    assert all(e["exits"][n] == cal[i + n - 1] for n in bt.HORIZONS)


def test_event_dates_10th_on_weekend():
    # 2024-07 營收 → 2024-08-10 是週六 → 期限日 8/12（一）、t0＝8/13
    e = bt.event_dates(weekdays("2024-07-01", "2024-10-31"), 2024, 7)
    assert (e["deadline"], e["t0"], e["exits"][5]) == ("2024-08-12", "2024-08-13", "2024-08-19")


def test_event_dates_long_holiday():
    # 2024-01 營收 → 2024-02-10 落在春節連假（2/8–2/14 休市）→ 期限日 2/15、t0＝2/16
    hol = {"2024-02-08", "2024-02-09", "2024-02-12", "2024-02-13", "2024-02-14"}
    e = bt.event_dates(weekdays("2024-01-01", "2024-04-30", hol), 2024, 1)
    assert (e["deadline"], e["t0"]) == ("2024-02-15", "2024-02-16")
    assert e["exits"][5] == "2024-02-22"


def test_event_dates_december_rolls_to_january_and_calendar_edges():
    cal = weekdays("2024-01-02", "2024-01-31")
    e = bt.event_dates(cal, 2023, 12)
    assert (e["deadline"], e["t0"]) == ("2024-01-10", "2024-01-11")
    assert e["exits"][5] == "2024-01-17" and e["exits"][20] is None      # 日曆不夠長
    assert bt.event_dates(cal, 2023, 11) is None      # 日曆起點晚於 2023-12-10：無法確認期限日
    assert bt.event_dates(cal, 2024, 1) is None       # 2024-02-10 之後沒有交易日
    assert bt.event_dates([], 2024, 1) is None


def test_eval_months_needs_longest_horizon():
    cal = weekdays("2024-01-02", "2024-06-28")
    analyzed = {(2023, 11): {"a": 1}, (2024, 1): {"a": 1}, (2024, 3): {"a": 1}, (2024, 5): {"a": 1}}
    # 2023-11：日曆未涵蓋 12/10；2024-05：6/11 起不足 20 個交易日 → 起訖＝2024-01～2024-03，中間月份全收
    assert bt.eval_months(analyzed, cal) == [(2024, 1), (2024, 2), (2024, 3)]


# ---------- 報酬 ----------
def test_hold_return_open_to_close_and_missing():
    px = {"2024-05-13": (100.0, 90.0), "2024-05-17": (120.0, 110.0)}
    assert bt.hold_return(px, "2024-05-13", "2024-05-17") == pytest.approx(10.0)   # 110/100−1
    assert bt.hold_return(px, "2024-05-13", "2024-05-16") is None                  # 出場日無價
    assert bt.hold_return(px, "2024-05-14", "2024-05-17") is None                  # 進場日無價
    assert bt.hold_return(px, "2024-05-13", None) is None
    assert bt.index_return({"2024-05-10": 200.0, "2024-05-17": 210.0}, "2024-05-10", "2024-05-17") == pytest.approx(5.0)
    assert bt.index_return({}, "2024-05-10", "2024-05-17") is None


# ---------- 統計（手算）----------
def test_t_stat_hand_example():
    # 1,2,3,4 → 平均 2.5、樣本標準差 sqrt(5/3)=1.2910、t＝2.5÷(1.2910÷2)=3.873
    assert bt.t_stat([1, 2, 3, 4]) == {"n": 4, "mean": 2.5, "sd": 1.291, "t": 3.873}
    assert bt.t_stat([]) == {"n": 0, "mean": None, "sd": None, "t": None}
    assert bt.t_stat([3.0])["t"] is None and bt.t_stat([2.0, 2.0])["t"] is None


def ev(month, cls, **excess):
    e = {"month": month, "cls": cls, "_x": None, "_lumpy": False}
    for n in bt.HORIZONS:
        e[f"excess_{n}"] = excess.get(f"e{n}", excess.get("e"))
    return e


def test_group_stats_monthly_cluster_hand_example():
    # Beat：一月 [1, 3]（月均 2）、二月 [5]（月均 5）、三月 [−1, −3, 2]（月均 −2/3）
    evs = [ev("2024-01", "Beat", e=1), ev("2024-01", "Beat", e=3), ev("2024-02", "Beat", e=5),
           ev("2024-03", "Beat", e=-1), ev("2024-03", "Beat", e=-3), ev("2024-03", "Beat", e=2),
           ev("2024-03", "Miss", e=9), ev("2024-02", "Beat", e=None)]
    s = bt.group_stats(evs, ("Beat",), 20)
    assert s["n_events"] == 6 and s["mean"] == pytest.approx(7 / 6, abs=1e-4) and s["median"] == 1.5
    assert s["win_rate"] == pytest.approx(66.67)
    mm = [2.0, 5.0, -2 / 3]
    mean = sum(mm) / 3
    sd = (sum((v - mean) ** 2 for v in mm) / 2) ** 0.5
    assert s["n_months"] == 3 and s["monthly_mean"] == pytest.approx(mean, abs=1e-4)
    assert s["t_monthly"] == pytest.approx(mean / (sd / 3 ** 0.5), abs=1e-3)
    assert s["t_monthly"] != s["t_event"]


def test_spread_series_groups_and_skips():
    evs = [ev("2024-01", br.CLS_HI_BEAT, e=4), ev("2024-01", br.CLS_BEAT, e=2), ev("2024-01", br.CLS_MISS, e=-1),
           ev("2024-01", br.CLS_LO_MISS, e=-3), ev("2024-01", br.CLS_INLINE, e=50), ev("2024-01", bt.CLS_NONE, e=-50),
           ev("2024-02", br.CLS_BEAT, e=1),                                   # 沒有 Miss → 略過
           ev("2024-03", br.CLS_MISS, e=1), ev("2024-03", br.CLS_BEAT, e=None),   # Beat 無報酬 → 略過
           ev("2024-04", br.CLS_BEAT, e=1), ev("2024-04", br.CLS_MISS, e=3)]
    s, sk = bt.spread_series(evs, 20)
    assert s == [("2024-01", 5.0, 2, 2), ("2024-04", -2.0, 1, 1)]      # (4+2)/2 − (−1−3)/2＝5；1−3＝−2
    assert sk == ["2024-02", "2024-03"]
    st = bt.spread_stats(s, sk)
    assert (st["n_months"], st["skipped_months"], st["mean"], st["pos_rate"]) == (2, 2, 1.5, 50.0)
    assert st["t"] == pytest.approx(1.5 / (((3.5 ** 2) * 2) ** 0.5 / 2 ** 0.5), abs=1e-3)
    sub = bt.spread_stats(s, sk, {"2024-01", "2024-02"})
    assert (sub["n_months"], sub["skipped_months"], sub["mean"], sub["t"]) == (1, 1, 5.0, None)


def test_split_halves():
    m = [f"2024-{i:02d}" for i in range(1, 8)]
    assert bt.split_halves(m) == (m[:3], m[3:])
    assert bt.split_halves(m[:6]) == (m[:3], m[3:6]) and bt.split_halves([]) == ([], [])


def test_period_stats_respects_month_subset():
    evs = [ev("2024-01", br.CLS_BEAT, e=2), ev("2024-01", br.CLS_MISS, e=-2),
           ev("2024-02", br.CLS_BEAT, e=-1), ev("2024-02", br.CLS_MISS, e=3)]
    assert bt.period_stats(evs)["spread"]["20"]["mean"] == 0.0            # (4 + −4)/2
    p = bt.period_stats(evs, {"2024-02"})
    assert p["spread"]["20"]["mean"] == -4.0 and p["by_class"][bt.GRP_BEAT]["20"]["n_events"] == 1


# ---------- 判準（§7.2）----------
def sp(t20, a20, b20, t5=None, a5=None, b5=None, t10=None, a10=None, b10=None):
    f = {"5": {"t": t5}, "10": {"t": t10}, "20": {"t": t20}}
    h1 = {"5": {"mean": a5}, "10": {"mean": a10}, "20": {"mean": a20}}
    h2 = {"5": {"mean": b5}, "10": {"mean": b10}, "20": {"mean": b20}}
    return f, h1, h2


def test_verdict_mechanical():
    assert bt.verdict(*sp(2.0, 0.1, 0.2))["result"] == bt.V_YES                 # t 剛好 2 算成立
    assert bt.verdict(*sp(2.5, 0.1, -0.2))["result"] == bt.V_PART               # 只有 t
    assert bt.verdict(*sp(1.99, 0.1, 0.2))["result"] == bt.V_PART               # 只有前後半同正
    assert bt.verdict(*sp(1.0, 0.1, -0.2))["result"] == bt.V_NO
    assert bt.verdict(*sp(1.0, 0.1, 0.0))["result"] == bt.V_NO                  # 0 不算正
    assert bt.verdict(*sp(None, None, 0.2))["result"] == bt.V_NO                # 缺值視為不成立
    assert bt.verdict(*sp(1.0, -0.1, 0.2, t5=3.0, a5=1.0, b5=1.0))["result"] == bt.V_PART     # 只有 5 日成立
    assert bt.verdict(*sp(1.0, -0.1, 0.2, t10=3.0, a10=1.0, b10=1.0))["result"] == bt.V_PART  # 只有 10 日成立
    assert bt.verdict(*sp(1.0, -0.1, 0.2, t5=3.0, a5=1.0, b5=-1.0))["result"] == bt.V_NO      # 5 日只成立一項不算
    v = bt.verdict(*sp(2.5, 0.1, -0.2))
    assert v["checks"]["20"] == {"t": 2.5, "t_ok": True, "first_mean": 0.1, "second_mean": -0.2,
                                 "halves_ok": False, "both": False}


# ---------- 門檻格點 ----------
def xs(sur, exp_yoy=10.0, exp_qoq=5.0):
    return {"sur": sur, "exp_yoy": exp_yoy, "exp_qoq": exp_qoq, "layer": "C"}


def test_th_override_restores_even_on_error():
    old = (br.TH_C, br.TH_C_LUMPY)
    with bt.th_override(30):
        assert (br.TH_C, br.TH_C_LUMPY) == (30.0, 40.0)
    assert (br.TH_C, br.TH_C_LUMPY) == old
    with pytest.raises(ZeroDivisionError), bt.th_override(10):
        1 / 0
    assert (br.TH_C, br.TH_C_LUMPY) == old == (15.0, 25.0)


def test_reclassify_default_threshold_identical_and_grid_moves():
    rnd = random.Random(7)
    evs = [{"_x": xs(rnd.uniform(-60, 60), rnd.uniform(-40, 90), rnd.uniform(-30, 40)), "_lumpy": rnd.random() < 0.3}
           for _ in range(400)] + [{"_x": None, "_lumpy": False}]
    direct = [br.classify(e["_x"], e["_lumpy"]) if e["_x"] else bt.CLS_NONE for e in evs]
    assert bt.reclassify(evs, br.TH_C) == direct                       # 預設門檻下逐筆相同
    assert len(set(direct)) == 6
    n_in = [sum(1 for c in bt.reclassify(evs, th) if c == br.CLS_INLINE) for th in bt.GRID]
    assert n_in == sorted(n_in) and n_in[0] < n_in[-1]                 # 門檻越高「符合」越多
    # 邊界：sur 20、非 lumpy → TH 20 是 Beat、TH 25 是符合；lumpy 在 TH 10（lumpy 20）才是 Beat
    a, b = {"_x": xs(20.0), "_lumpy": False}, {"_x": xs(20.0), "_lumpy": True}
    assert [bt.reclassify([a, b], th) for th in (10, 15, 20, 25)] == [
        ["Beat", "Beat"], ["Beat", "符合"], ["Beat", "符合"], ["符合", "符合"]]


def test_grid_table_in_and_out_of_sample():
    def e(month, sur, ex):
        return {"month": month, "cls": None, "_x": xs(sur), "_lumpy": False, **{f"excess_{n}": ex for n in bt.HORIZONS}}
    # 大驚喜（±35）前半有效、後半反向；小驚喜（±12）兩段都小幅有效
    evs = []
    for mth, big in (("2024-01", 4.0), ("2024-02", 6.0), ("2024-03", -5.0), ("2024-04", -3.0)):
        evs += [e(mth, 35, big), e(mth, -35, -big), e(mth, 12, 1.0), e(mth, -12, -1.0)]
    first, second = {"2024-01", "2024-02"}, {"2024-03", "2024-04"}
    g = {r["th_c"]: r for r in bt.grid_table(evs, first, second)}
    assert [r["th_c_lumpy"] for r in g.values()] == [20.0, 25.0, 30.0, 35.0, 40.0]
    assert (g[10.0]["n_beat"], g[10.0]["n_miss"], g[15.0]["n_beat"], g[30.0]["n_beat"]) == (8, 8, 4, 4)
    h10, h30 = g[10.0]["horizons"]["20"], g[30.0]["horizons"]["20"]
    assert h10["in_sample"]["mean"] == 6.0 and h10["out_of_sample"]["mean"] == -3.0   # ((4+1)−(−4−1))/2…
    assert h30["in_sample"]["mean"] == 10.0 and h30["out_of_sample"]["mean"] == -8.0
    assert h30["full"]["mean"] == 1.0 and h30["full"]["n_months"] == 4
    pick = bt.grid_pick(list(g.values()))
    assert pick["by_mean"]["th_c"] == 15.0 and pick["by_mean"]["out_of_sample"]["mean"] == -8.0   # 同值取較小門檻
    assert pick["by_t"]["th_c"] == 10.0 and pick["by_t"]["out_of_sample"]["mean"] == -3.0
    assert (br.TH_C, br.TH_C_LUMPY) == (15.0, 25.0)


def test_grid_pick_none_when_no_t():
    g = [{"th_c": th, "horizons": {"20": {"in_sample": {"t": None, "mean": None}, "out_of_sample": {}}}} for th in bt.GRID]
    p = bt.grid_pick(g)
    assert p["by_t"] is None and p["by_mean"] is None


# ---------- 防偷看 ----------
def rand_series(seed, start=2018, end=(2025, 12)):
    rnd = random.Random(seed)
    v, out = rnd.uniform(5, 500), {}
    for y, m in bt.month_range((start, 1), end):
        v *= rnd.uniform(0.7, 1.45)
        if rnd.random() > 0.02:                    # 偶爾缺月
            out[(y, m)] = v
    return out


def assert_no_lookahead(r, lumpy):
    n = 0
    for y, m in bt.month_range(min(r), max(r)):
        full = br.analyze(r, y, m)
        cut = br.analyze({k: v for k, v in r.items() if k <= (y, m)}, y, m)
        assert full == cut, (y, m)                 # 含 sur 在內所有欄位完全相同（不是近似）
        if full is not None:
            n += 1
            assert full["layer"] == "C"
            assert br.classify(full, lumpy) == br.classify(cut, lumpy)
    return n


def test_no_lookahead_synthetic():
    n = sum(assert_no_lookahead(rand_series(s), lumpy=s % 2 == 0) for s in range(12))
    assert n > 500


def test_no_lookahead_future_values_do_not_change_past_class():
    # 把評估月份之後的營收全部乘 10：過去月份的分類與 sur 不得改變
    r = rand_series(99)
    cutoff = (2023, 6)
    r2 = {k: (v * 10 if k > cutoff else v) for k, v in r.items()}
    meta = {"X": ("x", "s")}
    a1, a2 = bt.analyze_all({"X": r}, meta), bt.analyze_all({"X": r2}, meta)
    past = [k for k in a1 if k <= cutoff]
    assert len(past) > 30 and all(a1[k] == a2[k] for k in past)


def test_no_lookahead_real_cache():
    files = sorted(glob.glob("/tmp/revcache/*.json"))
    if not files:
        pytest.skip("沒有 /tmp/revcache 真實營收快取")
    n = 0
    for f in files:
        r = br.parse_series(json.loads(Path(f).read_text(encoding="utf-8")))
        if r:
            n += assert_no_lookahead(r, lumpy=False)
    assert n > 0


# ---------- 規格守門（§7.4 第 3、4 條）----------
def test_script_does_not_copy_rules_or_read_expect():
    src = (ROOT / "src" / "backtest_revenue.py").read_text(encoding="utf-8")
    code = "\n".join(ln.split("#")[0] for ln in src.splitlines())
    assert "load_overrides" not in code and "expect.json" not in code and "override=" not in code
    assert "br.analyze(" in code and "br.classify(" in code and "br.parse_series(" in code
    for name in ("HI_YOY", "HI_QOQ", "EQ_CLAMP", "SHARE_BAND", "RUNRATE_W"):
        assert f"{name} =" not in code                 # 不在回測腳本另定口徑常數
    assert bt.FAIL_ABORT == br.FAIL_ABORT and bt.GRID == (10.0, 15.0, 20.0, 25.0, 30.0)


def test_write_index_glob_ignores_backtest_dir():
    assert not fnmatch.fnmatch("backtest", "????-??.json") and not fnmatch.fnmatch("summary.json", "????-??.json")
    assert bt.OUT_DIR == br.OUT_DIR / "backtest"


def test_workflow_is_dispatch_only():
    y = (ROOT / ".github" / "workflows" / "revenue-backtest.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in y and "schedule:" not in y and "push:" not in y
    assert "paths: data/revenue/backtest" in y and "pipeline: revenue-backtest" in y
    assert "src/backtest_revenue.py" in y and "build_revenue.py" not in y


# ---------- 事件表與端到端 ----------
def synth(tmp_path, adj=True, taiex=True, n_stocks=6):
    """合成快取：6 檔 × 2018–2025 營收、2019–2026/02 價格。回傳 (cache_dir, universe)。"""
    cal = weekdays("2019-01-02", "2026-02-27")
    codes = ["2330"] + [str(9000 + i) for i in range(1, n_stocks)]
    uni = {"lumpy_sectors": ["乙"], "sectors": {"甲": [{"code": c, "name": f"股{c}"} for c in codes[:3]],
                                                "乙": [{"code": c, "name": f"股{c}"} for c in codes[3:]]}}
    ds = bt.DS_ADJ if adj else bt.DS_RAW
    for j, c in enumerate(codes):
        r = rand_series(j + 1)
        rev = [{"date": "x", "revenue_year": y, "revenue_month": m, "revenue": v * 1e8} for (y, m), v in r.items()]
        rnd, p, px = random.Random(100 + j), 100.0, []
        for d in cal:
            o = p * rnd.uniform(0.98, 1.02)
            p = o * rnd.uniform(0.97, 1.035)
            if c == "9005" and "2022-03-01" <= d <= "2022-06-30":
                continue                                           # 停牌一段
            px.append({"date": d, "stock_id": c, "open": round(o, 2), "close": round(p, 2)})
        for name, rows in ((bt.DS_REV, rev), (ds, px)):
            f = tmp_path / "cache" / name / f"{c}.json"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(rows), encoding="utf-8")
    if taiex:
        f = tmp_path / "cache" / bt.DS_TRI / "TAIEX.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps([{"date": d, "stock_id": "TAIEX", "price": 20000 + i} for i, d in enumerate(cal)]))
    return tmp_path / "cache", uni


def run_main(tmp_path, monkeypatch, uni, extra=()):
    rev_dir = tmp_path / "rev"
    rev_dir.mkdir(exist_ok=True)
    (rev_dir / "universe.json").write_text(json.dumps(uni), encoding="utf-8")
    monkeypatch.setattr(br, "OUT_DIR", rev_dir)
    calls = []

    def no_net(dataset, **kw):
        calls.append((dataset, kw.get("data_id")))
        raise RuntimeError("offline")
    monkeypatch.setattr(bt, "api_get", no_net)
    monkeypatch.setattr(bt, "REQ_SLEEP", 0)
    out = tmp_path / "out"
    assert bt.main(["--cache-dir", str(tmp_path / "cache"), "--out-dir", str(out), *extra]) == 0
    s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    with (out / "events.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return s, rows, calls


def fnum(v):
    return float(v) if v != "" else None


def test_end_to_end_adjusted(tmp_path, monkeypatch):
    _, uni = synth(tmp_path)
    s, rows, calls = run_main(tmp_path, monkeypatch, uni)
    assert calls == []                                             # 全部命中快取，未連網
    assert s["price_dataset"] == bt.DS_ADJ and s["price_adjusted"] is True and s["taiex_available"] is True
    assert s["fetch_failed"] == {"revenue": [], "price": []}
    assert s["eval_from"] == "2019-04" and s["eval_to"] == "2025-12" and s["n_months"] == 81
    assert s["verdict"]["result"] in (bt.V_YES, bt.V_PART, bt.V_NO)
    assert list(rows[0].keys()) == bt.CSV_HEAD
    assert s["n_events"] == sum(1 for r in rows if r["cls"] != bt.CLS_NONE) > 300
    assert s["n_benchmark_only_rows"] == sum(1 for r in rows if r["cls"] == bt.CLS_NONE)

    # 等權基準與超額：以 events.csv 自行重算
    for n in bt.HORIZONS:
        by_m = {}
        for r in rows:
            if r[f"ret_{n}"] != "":
                by_m.setdefault(r["month"], []).append(float(r[f"ret_{n}"]))
        for r in rows:
            if r[f"ret_{n}"] == "":
                assert r[f"excess_{n}"] == "" and r[f"bench_{n}"] == ""
                continue
            v = by_m[r["month"]]
            assert float(r[f"bench_{n}"]) == pytest.approx(sum(v) / len(v), abs=1e-4)
            assert int(r[f"bench_n_{n}"]) == len(v)
            assert float(r[f"excess_{n}"]) == pytest.approx(float(r[f"ret_{n}"]) - float(r[f"bench_{n}"]), abs=1.01e-4)
            assert float(r[f"excess_taiex_{n}"]) == pytest.approx(
                float(r[f"ret_{n}"]) - float(r[f"taiex_ret_{n}"]), abs=1.01e-4)
    # 停牌：9005 在 2022-02 營收（t0＝2022-03-11）沒有報酬，但仍有分類
    r9 = next(r for r in rows if r["code"] == "9005" and r["month"] == "2022-02")
    assert r9["t0"] == "2022-03-11" and r9["ret_20"] == "" and r9["cls"] != ""
    # 進出場與報酬對原始價格
    r1 = next(r for r in rows if r["code"] == "9001" and r["month"] == "2024-04")
    px = bt.parse_prices(json.loads((tmp_path / "cache" / bt.DS_ADJ / "9001.json").read_text()))
    assert (r1["deadline"], r1["t0"], r1["exit_5"]) == ("2024-05-10", "2024-05-13", "2024-05-17")
    assert float(r1["ret_5"]) == pytest.approx((px["2024-05-17"][1] / px["2024-05-13"][0] - 1) * 100, abs=1e-4)

    # 主口徑每月價差、平均與 t：由 events.csv 重算須與 summary 一致
    beat, miss = bt.GROUPS[bt.GRP_BEAT], bt.GROUPS[bt.GRP_MISS]
    for n in bt.HORIZONS:
        mm = {}
        for r in rows:
            v = fnum(r[f"excess_{n}"])
            if v is not None and r["cls"] in beat + miss:
                mm.setdefault(r["month"], ([], []))[0 if r["cls"] in beat else 1].append(v)
        series = {m: sum(b) / len(b) - sum(x) / len(x) for m, (b, x) in mm.items() if b and x}
        got = {x["month"]: x[f"spread_{n}"] for x in s["monthly_spread"] if x[f"spread_{n}"] is not None}
        assert got.keys() == series.keys()
        assert all(got[m] == pytest.approx(series[m], abs=1e-4) for m in got)
        st = bt.t_stat(list(got.values()))
        assert (s["spread"][str(n)]["mean"], s["spread"][str(n)]["t"], s["spread"][str(n)]["n_months"]) == (
            st["mean"], st["t"], st["n"])
    # 對半切與逐年
    h = s["halves"]
    assert (h["first"]["from"], h["first"]["to"], h["first"]["n_months"]) == ("2019-04", "2022-07", 40)
    assert (h["second"]["from"], h["second"]["to"], h["second"]["n_months"]) == ("2022-08", "2025-12", 41)
    assert h["first"]["spread"]["20"]["n_months"] + h["second"]["spread"]["20"]["n_months"] == s["spread"]["20"]["n_months"]
    assert sorted(s["yearly"]) == [str(y) for y in range(2019, 2026)]
    assert sum(v["spread"]["20"]["n_months"] for v in s["yearly"].values()) == s["spread"]["20"]["n_months"]
    # 門檻格點：預設門檻那一列＝主結果；樣本內外＝對半切
    g15 = next(g for g in s["grid"] if g["th_c"] == 15.0)["horizons"]["20"]
    assert g15["full"] == s["spread"]["20"]
    assert g15["in_sample"] == h["first"]["spread"]["20"] and g15["out_of_sample"] == h["second"]["spread"]["20"]
    assert [g["th_c"] for g in s["grid"]] == list(bt.GRID) and s["grid_pick"]["horizon"] == 20
    assert s["thresholds"]["c"] == 15.0 and (br.TH_C, br.TH_C_LUMPY) == (15.0, 25.0)


def test_end_to_end_falls_back_to_unadjusted_and_missing_taiex(tmp_path, monkeypatch):
    _, uni = synth(tmp_path, adj=False, taiex=False)
    s, rows, calls = run_main(tmp_path, monkeypatch, uni)
    assert calls == [(bt.DS_ADJ, "2330"), (bt.DS_TRI, "TAIEX")]    # 只探測一次，其餘不逐檔混用
    assert s["price_dataset"] == bt.DS_RAW and s["price_adjusted"] is False
    assert s["taiex_available"] is False and s["by_class_vs_taiex"] is None
    assert all(r["excess_taiex_20"] == "" for r in rows) and any(r["excess_20"] != "" for r in rows)


def test_abort_when_too_many_failures(tmp_path, monkeypatch):
    cache, uni = synth(tmp_path, n_stocks=11)
    (cache / bt.DS_ADJ / "9001.json").write_text(json.dumps([{"date": "2024-01-02", "Open": 1, "Close": 1}]))
    s, _, _ = run_main(tmp_path, monkeypatch, uni, extra=["--offline"])      # 1/11 ≤ 一成：列入失敗清單、照跑
    assert s["fetch_failed"]["price"] == ["9001"]
    (cache / bt.DS_REV / "9002.json").unlink()                               # 2/11 > 一成：中止
    with pytest.raises(RuntimeError, match="超過一成"):
        run_main(tmp_path, monkeypatch, uni, extra=["--offline"])


def test_abort_when_calendar_stock_has_no_price(tmp_path, monkeypatch):
    cache, uni = synth(tmp_path)
    (cache / bt.DS_ADJ / "2330.json").write_text("[]")
    with pytest.raises(RuntimeError, match="交易日曆"):
        run_main(tmp_path, monkeypatch, uni)
