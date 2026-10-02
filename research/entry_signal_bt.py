"""進場狀態欄回測（規則 v1）。規格與通過條件見 docs/entry-signal-backtest.md，改規則先改該檔。

用法：
    FINMIND_TOKEN=... python research/entry_signal_bt.py --out out/
離線測試只用純函式（classify／simulate／evaluate），不打網路。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

RULE_VERSION = 1
H = 60          # 持有交易日（出場日＝t+H）
W = 10          # 等待限價成交的交易日窗
KS = (0.03, 0.05, 0.08)
DD_LIMIT = 0.15
START = "2021-01-01"
LABELS = ("現在可買", "等3%", "等5-8%", "暫不進場")

TOP10_US = ["MU", "CRDO", "VRT", "AVGO", "NVDA", "COHR", "ANET"]
TOP10_TW = ["6669", "2368", "2345"]
EXTRA_US = ["AMD", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "MRVL", "QCOM", "INTC",
            "TXN", "ADI", "ON", "MPWR", "SMCI", "DELL", "HPE", "ALAB"]


# ---------------- 價格整理 ----------------
def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def bars_from_tw(rows: list) -> list[dict]:
    out = []
    for r in rows:
        o, h, lo, c = _f(r.get("open")), _f(r.get("max")), _f(r.get("min")), _f(r.get("close"))
        if None in (o, h, lo, c):
            continue
        out.append({"date": str(r["date"])[:10], "o": o, "h": h, "l": lo, "c": c})
    return sorted(out, key=lambda b: b["date"])


def bars_from_us(rows: list) -> list[dict]:
    out = []
    has_adj = any(_f(r.get("Adj_Close")) for r in rows)
    for r in rows:
        o, h, lo, c = _f(r.get("Open")), _f(r.get("High")), _f(r.get("Low")), _f(r.get("Close"))
        if None in (o, h, lo, c):
            continue
        fac = 1.0
        if has_adj:
            a = _f(r.get("Adj_Close"))
            if a is None:
                continue
            fac = a / c
        out.append({"date": str(r["date"])[:10], "o": o * fac, "h": h * fac, "l": lo * fac, "c": c * fac})
    out.sort(key=lambda b: b["date"])
    if not has_adj:
        out = fix_splits(out)
    return out


def fix_splits(bars: list[dict]) -> list[dict]:
    """無還原價時偵測分割：單日收盤跌幅 >45% 且前後比接近整數 n≥2（誤差 10% 內）→ 之前的價格除以 n。"""
    bars = [dict(b) for b in bars]
    for i in range(len(bars) - 1, 0, -1):
        ratio = bars[i - 1]["c"] / bars[i]["c"]
        if ratio < 1 / 0.55:
            continue
        n = round(ratio)
        if n >= 2 and abs(ratio - n) / n <= 0.10:
            for b in bars[:i]:
                for k in ("o", "h", "l", "c"):
                    b[k] /= n
    return bars


# ---------------- 指標與分類 ----------------
def indicators(bars: list[dict]) -> list[dict | None]:
    """每日回傳 {ma20, ma60, atr14, r5, slope60}；暖身不足為 None。"""
    n = len(bars)
    c = [b["c"] for b in bars]
    tr = [None] * n
    for i in range(1, n):
        h, lo, pc = bars[i]["h"], bars[i]["l"], c[i - 1]
        tr[i] = max(h - lo, abs(h - pc), abs(lo - pc))
    out: list[dict | None] = [None] * n
    for i in range(n):
        if i < 64:  # MA60 需 60 日、slope60 再往前 5 日
            continue
        ma20 = sum(c[i - 19:i + 1]) / 20
        ma60 = sum(c[i - 59:i + 1]) / 60
        ma60_5 = sum(c[i - 64:i - 4]) / 60
        atr = sum(tr[i - 13:i + 1]) / 14
        out[i] = {"ma20": ma20, "ma60": ma60, "atr14": atr,
                  "r5": c[i] / c[i - 5] - 1, "slope60": ma60 - ma60_5}
    return out


def classify(close: float, ind: dict) -> str:
    if close < ind["ma60"] and ind["slope60"] < 0:
        return "暫不進場"
    ext = (close - ind["ma20"]) / ind["atr14"] if ind["atr14"] > 0 else 0.0
    if ext > 2.0 or ind["r5"] > 0.08:
        return "等5-8%"
    if ext > 1.0:
        return "等3%"
    return "現在可買"


# ---------------- 模擬 ----------------
def simulate(bars: list[dict], t: int, k: float) -> tuple[float, float, bool]:
    """回傳 (chase 報酬, miss 報酬, 是否成交)；出場價 C_{t+H}。呼叫端保證 t+H 存在。"""
    exit_px = bars[t + H]["c"]
    lim = bars[t]["c"] * (1 - k)
    for j in range(t + 1, t + W + 1):
        if bars[j]["l"] <= lim:
            px = min(bars[j]["o"], lim)
            r = exit_px / px - 1
            return r, r, True
    return exit_px / bars[t + W]["c"] - 1, 0.0, False


def records_for(code: str, mkt: str, bars: list[dict]) -> list[dict]:
    ind = indicators(bars)
    recs = []
    for t in range(len(bars) - H):
        if ind[t] is None or bars[t]["date"] < START:
            continue
        c = bars[t]["c"]
        exit_px = bars[t + H]["c"]
        low = min(b["l"] for b in bars[t + 1:t + H + 1])
        rec = {"code": code, "mkt": mkt, "date": bars[t]["date"], "year": bars[t]["date"][:4],
               "label": classify(c, ind[t]), "buy": exit_px / c - 1, "dd": low / c - 1}
        for k in KS:
            ch, mi, filled = simulate(bars, t, k)
            p = int(round(k * 100))
            rec[f"w{p}"], rec[f"w{p}m"], rec[f"f{p}"] = ch, mi, filled
        recs.append(rec)
    return recs


# ---------------- 評估 ----------------
def _mean(xs):
    return sum(xs) / len(xs) if xs else None


CLAIMS = {
    "C1": ("現在可買", lambda r: r["buy"] - r["w3"], ">="),
    "C2": ("等3%", lambda r: r["w3"] - r["buy"], ">"),
    "C3": ("等5-8%", lambda r: r["w5"] - r["buy"], ">"),
}


def _claim_ok(recs: list[dict], cid: str) -> tuple[bool | None, float | None, int]:
    if cid == "C4":
        a = [r for r in recs if r["label"] == "暫不進場"]
        b = [r for r in recs if r["label"] == "現在可買"]
        if not a or not b:
            return None, None, min(len(a), len(b))
        ma, mb = _mean([r["buy"] for r in a]), _mean([r["buy"] for r in b])
        pa = _mean([1.0 if r["dd"] < -DD_LIMIT else 0.0 for r in a])
        pb = _mean([1.0 if r["dd"] < -DD_LIMIT else 0.0 for r in b])
        return (ma < mb and pa > pb), ma - mb, min(len(a), len(b))
    label, fn, op = CLAIMS[cid]
    xs = [fn(r) for r in recs if r["label"] == label]
    if not xs:
        return None, None, 0
    m = _mean(xs)
    return (m >= 0 if op == ">=" else m > 0), m, len(xs)


def evaluate(recs: list[dict]) -> dict:
    res = {}
    for cid in ("C1", "C2", "C3", "C4"):
        groups = {"全體": recs,
                  "台股": [r for r in recs if r["mkt"] == "tw"],
                  "美股": [r for r in recs if r["mkt"] == "us"]}
        g = {name: _claim_ok(rs, cid) for name, rs in groups.items()}
        years = {}
        for y in sorted({r["year"] for r in recs}):
            ok, m, n = _claim_ok([r for r in recs if r["year"] == y], cid)
            if n >= 50 and ok is not None:
                years[y] = (ok, m, n)
        yr_pass = (sum(1 for v in years.values() if v[0]) * 3 >= 2 * len(years)) if years else False
        passed = all(v[0] is True for v in g.values()) and yr_pass
        res[cid] = {"groups": g, "years": years, "years_pass": yr_pass, "pass": passed}
    return res


def label_table(recs: list[dict]) -> list[dict]:
    rows = []
    for lab in LABELS:
        rs = [r for r in recs if r["label"] == lab]
        if not rs:
            rows.append({"label": lab, "n": 0})
            continue
        row = {"label": lab, "n": len(rs),
               "buy_mean": _mean([r["buy"] for r in rs]),
               "buy_median": statistics.median(r["buy"] for r in rs),
               "buy_win": _mean([1.0 if r["buy"] > 0 else 0.0 for r in rs]),
               "dd15": _mean([1.0 if r["dd"] < -DD_LIMIT else 0.0 for r in rs])}
        for p in (3, 5, 8):
            row[f"w{p}_mean"] = _mean([r[f"w{p}"] for r in rs])
            row[f"w{p}m_mean"] = _mean([r[f"w{p}m"] for r in rs])
            row[f"fill{p}"] = _mean([1.0 if r[f"f{p}"] else 0.0 for r in rs])
        rows.append(row)
    return rows


def _pct(x):
    return "—" if x is None else f"{x * 100:+.2f}%"


def report(recs: list[dict], fetched: dict) -> str:
    L = [f"# 進場狀態欄回測結果（規則 v{RULE_VERSION}）", ""]
    L.append(f"樣本：{len(recs)} 個訊號日，{len({r['code'] for r in recs})} 檔；"
             f"期間 {min(r['date'] for r in recs)} ~ {max(r['date'] for r in recs)}（訊號日）。H={H}、W={W}。")
    miss = [c for c, v in fetched.items() if not v]
    if miss:
        L.append(f"抓不到或資料不足而略過：{', '.join(miss)}")
    L += ["", "## 各標籤後續表現（報酬均為至 t+60 交易日）", "",
          "| 標籤 | N | 直接買 平均 | 直接買 中位 | 勝率 | 回撤>15% | 等3% chase | 等5% chase | 等8% chase | 3%成交率 | 5%成交率 | 8%成交率 |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in label_table(recs):
        if not r["n"]:
            L.append(f"| {r['label']} | 0 |" + " — |" * 10)
            continue
        L.append(f"| {r['label']} | {r['n']} | {_pct(r['buy_mean'])} | {_pct(r['buy_median'])} | "
                 f"{r['buy_win'] * 100:.1f}% | {r['dd15'] * 100:.1f}% | {_pct(r['w3_mean'])} | "
                 f"{_pct(r['w5_mean'])} | {_pct(r['w8_mean'])} | {r['fill3'] * 100:.1f}% | "
                 f"{r['fill5'] * 100:.1f}% | {r['fill8'] * 100:.1f}% |")
    L += ["", "## 主張判定", ""]
    ev = evaluate(recs)
    desc = {"C1": "現在可買：直接買 − 等3%", "C2": "等3%：等3% − 直接買",
            "C3": "等5-8%：等5% − 直接買", "C4": "暫不進場：直接買平均 − 現在可買日直接買平均"}
    for cid, v in ev.items():
        L.append(f"### {cid} {desc[cid]} → **{'通過' if v['pass'] else '不通過'}**")
        for g, (ok, m, n) in v["groups"].items():
            L.append(f"- {g}：{_pct(m)}（N={n}）{'✓' if ok else '✗'}")
        ys = "、".join(f"{y} {_pct(m)}{'✓' if ok else '✗'}" for y, (ok, m, n) in v["years"].items())
        L.append(f"- 分年（N≥50）：{ys or '無'} → {'≥2/3 成立' if v['years_pass'] else '未達 2/3'}")
        L.append("")
    return "\n".join(L)


# ---------------- 抓資料 ----------------
def fetch_all(tw_codes: list[str], us_codes: list[str]) -> tuple[dict, dict]:
    from fmclient import api_get
    data, ok = {}, {}
    for code in tw_codes:
        rows = []
        for ds in ("TaiwanStockPriceAdj", "TaiwanStockPrice"):
            try:
                rows = api_get(ds, data_id=code, start_date="2020-09-01")
            except Exception as e:  # noqa: BLE001 — 單檔失敗略過
                print(f"  ! {code} {ds}: {e}", flush=True)
                rows = []
            if rows:
                break
        bars = bars_from_tw(rows)
        ok[code] = len(bars) > H + 70
        if ok[code]:
            data[code] = ("tw", bars)
        print(f"  {code}: {len(bars)} bars", flush=True)
    for code in us_codes:
        try:
            rows = api_get("USStockPrice", data_id=code, start_date="2020-09-01")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {code} USStockPrice: {e}", flush=True)
            rows = []
        bars = bars_from_us(rows)
        ok[code] = len(bars) > H + 70
        if ok[code]:
            data[code] = ("us", bars)
        print(f"  {code}: {len(bars)} bars adj={'Adj_Close' if any(_f(r.get('Adj_Close')) for r in rows) else 'split-detect'}",
              flush=True)
    return data, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--screen", default=str(ROOT / "data/screen/screen.json"))
    a = ap.parse_args(argv)
    screen = [r["code"] for r in json.loads(Path(a.screen).read_text(encoding="utf-8"))["rows"]]
    tw = list(dict.fromkeys(TOP10_TW + screen))
    us = list(dict.fromkeys(TOP10_US + EXTRA_US))
    data, ok = fetch_all(tw, us)
    recs = []
    for code, (mkt, bars) in data.items():
        recs += records_for(code, mkt, bars)
    if not recs:
        print("無任何樣本", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "records.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    rep = report(recs, ok)
    (out / "report.md").write_text(rep, encoding="utf-8")
    (out / "evaluate.json").write_text(json.dumps(evaluate(recs), ensure_ascii=False, indent=1), encoding="utf-8")
    print(rep)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as fh:
            fh.write(rep + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
