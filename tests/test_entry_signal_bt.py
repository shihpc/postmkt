"""research/entry_signal_bt.py 純函式離線測試（規則見 docs/entry-signal-backtest.md）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))

import entry_signal_bt as bt  # noqa: E402


def _ind(**kw):
    base = {"ma20": 100.0, "ma60": 95.0, "atr14": 2.0, "r5": 0.0, "slope60": 1.0}
    base.update(kw)
    return base


def test_classify_order_and_thresholds():
    # 下降季線之下 → 暫不進場（優先於延伸判斷）
    assert bt.classify(90.0, _ind(ma60=95.0, slope60=-0.1, r5=0.2)) == "暫不進場"
    # 季線之下但季線上揚 → 不算暫不進場
    assert bt.classify(90.0, _ind(ma60=95.0, slope60=0.1)) == "現在可買"
    # ext 恰 1.0 → 現在可買；>1.0 → 等3%；恰 2.0 → 等3%；>2.0 → 等5-8%
    assert bt.classify(102.0, _ind()) == "現在可買"
    assert bt.classify(102.1, _ind()) == "等3%"
    assert bt.classify(104.0, _ind()) == "等3%"
    assert bt.classify(104.1, _ind()) == "等5-8%"
    # r5 > 8% 單獨即可觸發
    assert bt.classify(100.0, _ind(r5=0.081)) == "等5-8%"
    assert bt.classify(100.0, _ind(r5=0.08)) == "現在可買"


def _flat(n, c=100.0):
    return [{"date": f"2022-01-{i:03d}", "o": c, "h": c, "l": c, "c": c} for i in range(n)]


def test_simulate_fill_gap_and_chase():
    bars = _flat(bt.H + bt.W + 5)
    bars[bt.H]["c"] = 110.0  # 出場價（t=0）
    # 第 3 天低點觸及 97 → 以 97 成交
    bars[3]["l"] = 96.0
    ch, mi, f = bt.simulate(bars, 0, 0.03)
    assert f and abs(ch - (110 / 97 - 1)) < 1e-12 and ch == mi
    # 跳空開低 95 → 以開盤價成交
    bars[3]["o"] = 95.0
    ch, _, _ = bt.simulate(bars, 0, 0.03)
    assert abs(ch - (110 / 95 - 1)) < 1e-12
    # 不成交 → chase 以 C_{t+W}、miss 記 0
    bars2 = _flat(bt.H + bt.W + 5)
    bars2[bt.H]["c"] = 110.0
    bars2[bt.W]["c"] = 105.0
    ch, mi, f = bt.simulate(bars2, 0, 0.05)
    assert not f and abs(ch - (110 / 105 - 1)) < 1e-12 and mi == 0.0


def test_fill_after_window_is_ignored():
    bars = _flat(bt.H + bt.W + 5)
    bars[bt.W + 1]["l"] = 50.0  # 超出等待窗
    _, _, f = bt.simulate(bars, 0, 0.03)
    assert not f


def test_fix_splits_10_for_1():
    bars = [{"date": f"d{i}", "o": 1000.0, "h": 1000.0, "l": 1000.0, "c": 1000.0} for i in range(3)]
    bars += [{"date": f"e{i}", "o": 101.0, "h": 101.0, "l": 101.0, "c": 101.0} for i in range(3)]
    fixed = bt.fix_splits(bars)
    assert all(abs(b["c"] - 100.0) < 1e-9 for b in fixed[:3])
    assert fixed[3]["c"] == 101.0
    # 單純大跌 50%（非整數倍附近）不調整
    crash = [{"date": "a", "o": 100.0, "h": 100.0, "l": 100.0, "c": 100.0},
             {"date": "b", "o": 40.0, "h": 40.0, "l": 40.0, "c": 40.0}]
    assert bt.fix_splits(crash)[0]["c"] == 100.0


def test_us_adj_close_scales_ohlc():
    rows = [{"date": "2024-01-02", "Open": 10, "High": 12, "Low": 9, "Close": 10, "Adj_Close": 5}]
    b = bt.bars_from_us(rows)[0]
    assert (b["o"], b["h"], b["l"], b["c"]) == (5.0, 6.0, 4.5, 5.0)


def test_indicators_warmup_and_values():
    bars = [{"date": f"2022-{i:04d}", "o": 100.0 + i, "h": 101.0 + i, "l": 99.0 + i, "c": 100.0 + i}
            for i in range(80)]
    ind = bt.indicators(bars)
    assert ind[63] is None and ind[64] is not None
    i = 70
    assert abs(ind[i]["ma20"] - sum(100.0 + j for j in range(i - 19, i + 1)) / 20) < 1e-9
    assert abs(ind[i]["atr14"] - 2.0) < 1e-9  # TR = max(2, |101+i-(99+i)|...) = 2
    assert abs(ind[i]["r5"] - ((100 + i) / (95 + i) - 1)) < 1e-12
    assert abs(ind[i]["slope60"] - 5.0) < 1e-9


def _rec(label, buy, w3, w5, dd=-0.05, mkt="us", year="2023"):
    r = {"label": label, "buy": buy, "w3": w3, "w5": w5, "w8": w5, "dd": dd, "mkt": mkt, "year": year}
    for p in (3, 5, 8):
        r[f"w{p}m"] = r[f"w{p}"]
        r[f"f{p}"] = True
    return r


def test_evaluate_requires_both_markets_and_years():
    recs = []
    for mkt in ("us", "tw"):
        for y in ("2022", "2023", "2024"):
            recs += [_rec("現在可買", 0.10, 0.08, 0.07, mkt=mkt, year=y) for _ in range(30)]
            recs += [_rec("等3%", 0.05, 0.06, 0.04, mkt=mkt, year=y) for _ in range(30)]
            recs += [_rec("等5-8%", 0.02, 0.03, 0.04, mkt=mkt, year=y) for _ in range(30)]
            recs += [_rec("暫不進場", -0.02, 0.0, 0.0, dd=-0.2, mkt=mkt, year=y) for _ in range(30)]
    ev = bt.evaluate(recs)
    assert all(ev[c]["pass"] for c in ("C1", "C2", "C3", "C4"))
    # 美股 C2 翻向 → 整條不通過
    for r in recs:
        if r["mkt"] == "us" and r["label"] == "等3%":
            r["w3"] = 0.0
    assert not bt.evaluate(recs)["C2"]["pass"]
