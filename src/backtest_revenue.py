# src/backtest_revenue.py — 月營收 Beat／Miss 回測（階段三）
#
# 規格、預先登錄判準與驗收條件的正本＝docs/revenue-beatmiss.md §7；本檔的設計不得偏離 §7.1，
# verdict 只能照 §7.2 的文字機械計算。產出 data/revenue/backtest/summary.json＋events.csv。
#
# 分類一律呼叫 build_revenue 的純函式（parse_series／analyze／classify），不複製口徑；
# 只回測 C 層（模型）：analyze() 不帶 override、expect.json 完全不讀。
# 門檻格點以「暫時覆寫 build_revenue 的模組常數、finally 還原」實作（th_override），
# 仍由 classify() 本身分類——不另寫第二份分類規則。
#
# 資料源（FinMind，逐檔查詢）：
#   TaiwanStockMonthRevenue（start_date=2018-01-01）
#   TaiwanStockPriceAdj（還原）；以 2330 探測一次，取不到整批退回 TaiwanStockPrice（price_adjusted=false）
#   TaiwanStockTotalReturnIndex（data_id=TAIEX）；取不到只標示缺、不中止
# ⚠ 價格與報酬指數的欄位名是假設（date／open／close；date／price），未以 token 實測；
#   欄位不符時該檔零筆可用價格 → 列入 fetch_failed.price，超過一成即中止。
#
# 用法：
#   FINMIND_TOKEN=... python src/backtest_revenue.py
#   python src/backtest_revenue.py --cache-dir /tmp/c --out-dir /tmp/o            # 本機：原始回應讀寫快取
#   python src/backtest_revenue.py --cache-dir /tmp/c --out-dir /tmp/o --offline  # 只讀快取、不連網
# 快取目錄結構：<cache-dir>/<資料集名>/<代號>.json（原始 data 陣列）
from __future__ import annotations

import argparse
import bisect
import contextlib
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import build_revenue as br  # noqa: E402
from fmclient import api_get, taipei_now  # noqa: E402

OUT_DIR = ROOT / "data" / "revenue" / "backtest"
SCHEMA = 1
REV_START = "2018-01-01"       # §7.1：營收自 2018-01 起抓
PRICE_START = "2019-01-01"     # 涵蓋最早可評估月份（2019-04 營收 → 2019-05 進場）即可
DS_REV = "TaiwanStockMonthRevenue"
DS_ADJ, DS_RAW = "TaiwanStockPriceAdj", "TaiwanStockPrice"
DS_TRI, TRI_ID = "TaiwanStockTotalReturnIndex", "TAIEX"
CAL_CODE = "2330"              # 交易日曆與價格資料集探測都用它
REQ_SLEEP = 0.2
FAIL_ABORT = br.FAIL_ABORT     # 抓取失敗超過一成中止（比照 build_revenue）

HORIZONS = (5, 10, 20)         # 持有交易日數（含進場日）
MAIN_H = 20                    # §7.2 主口徑
GRID = (10.0, 15.0, 20.0, 25.0, 30.0)   # TH_C 格點；TH_C_LUMPY＝TH_C＋10
LUMPY_ADD = 10.0
T_MIN = 2.0                    # §7.2：月群聚 t 值門檻
ND = 4                         # 報酬／超額（%）的小數位；統計一律由四捨五入後的事件值計算，events.csv 可重算

CLS_NONE = "未分類"            # 有報酬但無法建立預期：只當等權基準成員，不算事件
GRP_BEAT, GRP_MISS = "Beat類合計", "Miss類合計"
GROUPS = {
    br.CLS_HI_BEAT: (br.CLS_HI_BEAT,), br.CLS_LO_MISS: (br.CLS_LO_MISS,), br.CLS_BEAT: (br.CLS_BEAT,),
    br.CLS_MISS: (br.CLS_MISS,), br.CLS_INLINE: (br.CLS_INLINE,),
    GRP_BEAT: (br.CLS_HI_BEAT, br.CLS_BEAT), GRP_MISS: (br.CLS_LO_MISS, br.CLS_MISS),
}
V_YES, V_PART, V_NO = "有回測支持", "部分支持", "無回測支持"


# ================= 純函式（離線可測）=================
def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def parse_prices(rows: list) -> dict:
    """FinMind 日線列 → {'YYYY-MM-DD': (開盤, 收盤)}。缺欄、非數值或 ≤0（無成交日）的列略過。"""
    out = {}
    for x in rows or []:
        if not isinstance(x, dict):
            continue
        d, o, c = x.get("date"), _num(x.get("open")), _num(x.get("close"))
        if isinstance(d, str) and len(d) >= 10 and o and c and o > 0 and c > 0:
            out[d[:10]] = (o, c)
    return out


def parse_index(rows: list) -> dict:
    """報酬指數列 → {'YYYY-MM-DD': 指數}。值欄位依序試 price／close。"""
    out = {}
    for x in rows or []:
        if not isinstance(x, dict):
            continue
        d = x.get("date")
        v = _num(x.get("price"))
        if v is None:
            v = _num(x.get("close"))
        if isinstance(d, str) and len(d) >= 10 and v and v > 0:
            out[d[:10]] = v
    return out


def next_m(y: int, m: int) -> tuple:
    return (y, m + 1) if m < 12 else (y + 1, 1)


def ym(y: int, m: int) -> str:
    return f"{y}-{m:02d}"


def event_dates(cal: list, y: int, m: int, horizons=HORIZONS):
    """營收月份 (y, m) 的事件日。cal＝升序交易日（ISO 字串）。
    期限日＝公布月（次月）10 日起第一個交易日；t0＝期限日的下一個交易日；
    持有 N 日的出場日＝第 t0+N−1 個交易日（日曆不夠長＝None）。
    日曆未涵蓋到公布月 10 日（太早或太晚）或沒有 t0 → 回 None。"""
    py, pm = next_m(y, m)
    target = f"{py}-{pm:02d}-10"
    if not cal or cal[0] > target:
        return None
    i = bisect.bisect_left(cal, target)
    if i + 1 >= len(cal):
        return None
    return {"deadline": cal[i], "t0": cal[i + 1],
            "exits": {n: (cal[i + n] if i + n < len(cal) else None) for n in horizons}}


def hold_return(px: dict, t0: str, exit_d):
    """t0 開盤進、exit_d 收盤出的報酬%；任一日無價（停牌／未上市／缺資料）回 None，不以鄰近日代替。"""
    a, b = px.get(t0), px.get(exit_d) if exit_d else None
    return (b[1] / a[0] - 1) * 100 if a and b else None


def index_return(idx: dict, deadline: str, exit_d):
    """報酬指數只有收盤值：以期限日收盤 → 出場日收盤近似「t0 開盤 → 出場日收盤」。缺值回 None。"""
    a, b = idx.get(deadline), idx.get(exit_d) if exit_d else None
    return (b / a - 1) * 100 if a and b else None


@contextlib.contextmanager
def th_override(th_c: float):
    """暫時把 build_revenue 的 C 層門檻改成 th_c／th_c+10，離開時（含例外）還原。"""
    old = br.TH_C, br.TH_C_LUMPY
    br.TH_C, br.TH_C_LUMPY = float(th_c), float(th_c) + LUMPY_ADD
    try:
        yield
    finally:
        br.TH_C, br.TH_C_LUMPY = old


def universe_meta(universe: dict) -> tuple:
    """→ ({code: (名稱, 次產業)}, lumpy 次產業集合)；lumpy 判斷與 build_month() 相同。"""
    meta = {s["code"]: (s["name"], sec) for sec, lst in universe["sectors"].items() for s in lst}
    return meta, set(universe.get("lumpy_sectors", []))


def month_range(a: tuple, b: tuple) -> list:
    out, cur = [], a
    while cur <= b:
        out.append(cur)
        cur = next_m(*cur)
    return out


def analyze_all(series: dict, meta: dict) -> dict:
    """{(y, m): {code: analyze 結果}}；只收能建立預期者。一律不帶 override（只回測 C 層）。"""
    keys = [k for r in series.values() for k in r]
    if not keys:
        return {}
    out = {}
    for y, m in month_range(min(keys), max(keys)):
        d = {}
        for code in meta:
            x = br.analyze(series.get(code) or {}, y, m)
            if x is not None:
                d[code] = x
        if d:
            out[(y, m)] = d
    return out


def eval_months(analyzed: dict, cal: list) -> list:
    """評估月份：模型能建立預期的最早月份起，至最長持有期出場日已存在的最近月份止（中間月份全收）。"""
    ok = [k for k in sorted(analyzed)
          if (e := event_dates(cal, *k)) and e["exits"][max(HORIZONS)]]
    return month_range(ok[0], ok[-1]) if ok else []


def build_events(analyzed: dict, meta: dict, lumpy: set, prices: dict, cal: list, index: dict, months: list) -> list:
    """每個評估月份 × 股票池每檔一列（含「未分類」）。至少一個持有期算得出報酬、或有分類才留列。
    等權基準＝同月同持有期、股票池內所有算得出報酬的個股（不論有無分類）之平均。"""
    rows = []
    for y, m in months:
        ev = event_dates(cal, y, m)
        if not ev:
            continue
        xs = analyzed.get((y, m), {})
        mrows = []
        for code, (name, sec) in meta.items():
            x = xs.get(code)
            px = prices.get(code) or {}
            r = {"month": ym(y, m), "code": code, "name": name, "sector": sec,
                 "cls": br.classify(x, sec in lumpy) if x else CLS_NONE,
                 "sur": _r(x["sur"], 2) if x else None, "exp_qoq": _r(x["exp_qoq"], 2) if x else None,
                 "exp_yoy": _r(x["exp_yoy"], 2) if x else None, "k": x["k"] if x else None,
                 "deadline": ev["deadline"], "t0": ev["t0"], "_x": x, "_lumpy": sec in lumpy}
            for n in HORIZONS:
                ex = ev["exits"][n]
                r[f"exit_{n}"] = ex
                r[f"ret_{n}"] = _r(hold_return(px, ev["t0"], ex), ND)
                r[f"taiex_ret_{n}"] = _r(index_return(index or {}, ev["deadline"], ex), ND)
            if x or any(r[f"ret_{n}"] is not None for n in HORIZONS):
                mrows.append(r)
        for n in HORIZONS:
            v = [r[f"ret_{n}"] for r in mrows if r[f"ret_{n}"] is not None]
            bench = _r(sum(v) / len(v), ND) if v else None
            for r in mrows:
                ret, tx = r[f"ret_{n}"], r[f"taiex_ret_{n}"]
                r[f"bench_{n}"] = bench if ret is not None else None
                r[f"bench_n_{n}"] = len(v) if ret is not None else None
                r[f"excess_{n}"] = _r(ret - bench, ND) if ret is not None else None
                r[f"excess_taiex_{n}"] = _r(ret - tx, ND) if ret is not None and tx is not None else None
        rows.extend(mrows)
    return rows


def reclassify(events: list, th_c: float) -> list:
    """以指定 TH_C（lumpy＝+10）重新分類，回傳與 events 等長的分類清單。仍由 br.classify() 判定。"""
    with th_override(th_c):
        return [br.classify(e["_x"], e["_lumpy"]) if e["_x"] else CLS_NONE for e in events]


def _r(v, nd):
    return None if v is None else round(v, nd)


def t_stat(vals: list) -> dict:
    """n／平均／樣本標準差（n−1）／t＝平均 ÷（標準差 ÷ √n）。n<2 或標準差為 0 時 sd／t 為 None。"""
    n = len(vals)
    if not n:
        return {"n": 0, "mean": None, "sd": None, "t": None}
    mean = sum(vals) / n
    sd = statistics.stdev(vals) if n >= 2 else None
    t = mean / (sd / math.sqrt(n)) if sd else None
    return {"n": n, "mean": _r(mean, 4), "sd": _r(sd, 4), "t": _r(t, 3)}


def group_stats(events: list, classes: tuple, n: int, cls_list=None, key="excess") -> dict:
    """某類（或合計類）× 持有期：事件層級統計＋月群聚統計。"""
    by_m, vals = {}, []
    for i, e in enumerate(events):
        c = cls_list[i] if cls_list is not None else e["cls"]
        v = e[f"{key}_{n}"]
        if c in classes and v is not None:
            vals.append(v)
            by_m.setdefault(e["month"], []).append(v)
    ev = t_stat(vals)
    mm = t_stat([sum(v) / len(v) for _, v in sorted(by_m.items())])
    return {"n_events": ev["n"], "mean": ev["mean"], "median": _r(statistics.median(vals), 4) if vals else None,
            "win_rate": _r(sum(1 for v in vals if v > 0) / len(vals) * 100, 2) if vals else None,
            "t_event": ev["t"],                                   # 僅供參考：同月事件高度相關
            "n_months": mm["n"], "monthly_mean": mm["mean"], "monthly_sd": mm["sd"], "t_monthly": mm["t"]}


def spread_series(events: list, n: int, cls_list=None) -> tuple:
    """Beat 類合計 − Miss 類合計 的每月價差（各月：兩邊事件超額的平均相減）。
    → ([(月份, 價差, Beat 事件數, Miss 事件數)], 被略過的月份清單)；某月任一邊沒有事件＝略過。
    註：同月同持有期的基準相同，價差與用哪個基準（等權或 TAIEX）無關。"""
    by_m = {}
    for i, e in enumerate(events):
        c = cls_list[i] if cls_list is not None else e["cls"]
        v = e[f"excess_{n}"]
        d = by_m.setdefault(e["month"], ([], []))
        if v is None:
            continue
        if c in GROUPS[GRP_BEAT]:
            d[0].append(v)
        elif c in GROUPS[GRP_MISS]:
            d[1].append(v)
    out, skipped = [], []
    for mth, (b, s) in sorted(by_m.items()):
        if b and s:
            out.append((mth, round(sum(b) / len(b) - sum(s) / len(s), ND), len(b), len(s)))
        else:
            skipped.append(mth)
    return out, skipped


def spread_stats(series: list, skipped=(), months=None) -> dict:
    """價差序列的月群聚統計；months 給定時只取該集合內的月份。"""
    sel = [x for x in series if months is None or x[0] in months]
    sk = [x for x in skipped if months is None or x in months]
    st = t_stat([x[1] for x in sel])
    return {"n_months": st["n"], "skipped_months": len(sk), "mean": st["mean"], "sd": st["sd"], "t": st["t"],
            "pos_rate": _r(sum(1 for x in sel if x[1] > 0) / len(sel) * 100, 2) if sel else None}


def split_halves(months: list) -> tuple:
    """依時間對半切：前半＝前 len//2 個評估月份，後半＝其餘（奇數時後半多一個月）。"""
    h = len(months) // 2
    return months[:h], months[h:]


def period_stats(events: list, months=None) -> dict:
    """某段期間（months＝'YYYY-MM' 集合；None＝全期）的主口徑：各類 × 各持有期＋價差。"""
    sel = [e for e in events if months is None or e["month"] in months]
    out = {"by_class": {}, "spread": {}}
    for g, classes in GROUPS.items():
        out["by_class"][g] = {str(n): group_stats(sel, classes, n) for n in HORIZONS}
    for n in HORIZONS:
        out["spread"][str(n)] = spread_stats(*spread_series(sel, n))
    return out


def grid_table(events: list, first: set, second: set) -> list:
    """門檻格點：每個 TH_C 重新分類後，全期／前半（樣本內）／後半（樣本外）的 Beat−Miss 價差。"""
    out = []
    for th in GRID:
        cl = reclassify(events, th)
        row = {"th_c": th, "th_c_lumpy": th + LUMPY_ADD,
               "n_beat": sum(1 for c in cl if c in GROUPS[GRP_BEAT]),
               "n_miss": sum(1 for c in cl if c in GROUPS[GRP_MISS]), "horizons": {}}
        for n in HORIZONS:
            s, sk = spread_series(events, n, cl)
            row["horizons"][str(n)] = {"full": spread_stats(s, sk), "in_sample": spread_stats(s, sk, first),
                                       "out_of_sample": spread_stats(s, sk, second)}
        out.append(row)
    return out


def grid_pick(grid: list, n: int = MAIN_H) -> dict:
    """以前半期（樣本內）主口徑持有期的月群聚 t 值選最佳門檻（同值取較小門檻；t 全為 None 則不選），
    並列出該門檻的樣本外數字。另附「以樣本內平均價差選」的結果供對照。"""
    def best(key):
        c = [(g["horizons"][str(n)]["in_sample"][key], -g["th_c"], g) for g in grid
             if g["horizons"][str(n)]["in_sample"][key] is not None]
        return max(c, key=lambda t: t[:2])[2] if c else None

    out = {"criterion": "前半期月群聚 t 值最大（同值取較小門檻）", "horizon": n, "default_th_c": br.TH_C}
    for name, key in (("by_t", "t"), ("by_mean", "mean")):
        g = best(key)
        out[name] = None if g is None else {
            "th_c": g["th_c"], "in_sample": g["horizons"][str(n)]["in_sample"],
            "out_of_sample": g["horizons"][str(n)]["out_of_sample"]}
    return out


def verdict(full: dict, first: dict, second: dict) -> dict:
    """§7.2 機械判定。輸入＝全期／前半／後半的 spread（{'5': {...}, '10': ..., '20': ...}）。
    每個持有期兩項條件：①月群聚 t ≥ 2；②前半、後半平均同為正。
    有回測支持＝主口徑（20 日）兩項皆成立；部分支持＝主口徑只成立一項，或主口徑兩項皆不成立但
    5 日或 10 日兩項皆成立；其餘＝無回測支持。缺值（月數不足）一律視為不成立。"""
    checks = {}
    for n in HORIZONS:
        k = str(n)
        t, a, b = full[k]["t"], first[k]["mean"], second[k]["mean"]
        ct = t is not None and t >= T_MIN
        ch = a is not None and b is not None and a > 0 and b > 0
        checks[k] = {"t": t, "t_ok": ct, "first_mean": a, "second_mean": b, "halves_ok": ch, "both": ct and ch}
    main = checks[str(MAIN_H)]
    if main["both"]:
        res = V_YES
    elif main["t_ok"] or main["halves_ok"] or any(checks[str(n)]["both"] for n in HORIZONS if n != MAIN_H):
        res = V_PART
    else:
        res = V_NO
    return {"result": res, "main_horizon": MAIN_H, "t_min": T_MIN, "checks": checks,
            "note": "依 docs/revenue-beatmiss.md §7.2 機械判定；高預期仍Beat／低預期仍Miss 兩子類不納入判準"}


CSV_HEAD = (["month", "code", "name", "sector", "cls", "sur", "exp_qoq", "exp_yoy", "k", "deadline", "t0"]
            + [f"{p}_{n}" for n in HORIZONS
               for p in ("exit", "ret", "bench", "bench_n", "excess", "taiex_ret", "excess_taiex")])


def build_summary(events: list, months: list, info: dict) -> dict:
    """組 summary（不含 generated_at）。months＝評估月份 [(y, m)]；info＝資料來源與失敗清單等中繼資料。"""
    mstr = [ym(*k) for k in months]
    fa, fb = split_halves(mstr)
    first, second = set(fa), set(fb)
    full = period_stats(events)
    p1, p2 = period_stats(events, first), period_stats(events, second)
    years = sorted({s[:4] for s in mstr})
    grid = grid_table(events, first, second)
    series = {n: spread_series(events, n) for n in HORIZONS}
    by_m = {}
    for n in HORIZONS:
        for mth, v, nb, ns in series[n][0]:
            by_m.setdefault(mth, {})[n] = (v, nb, ns)
    t0_of = {e["month"]: e["t0"] for e in events}
    monthly = []
    for mth in mstr:
        row = {"month": mth, "t0": t0_of.get(mth), "half": 1 if mth in first else 2}
        for n in HORIZONS:
            v = by_m.get(mth, {}).get(n)
            row[f"spread_{n}"], row[f"n_beat_{n}"], row[f"n_miss_{n}"] = v if v else (None, 0, 0)
        monthly.append(row)
    tx = {g: {str(n): group_stats(events, c, n, key="excess_taiex") for n in HORIZONS} for g, c in GROUPS.items()}
    return {
        "schema": SCHEMA, "spec": "docs/revenue-beatmiss.md §7",
        "eval_from": mstr[0] if mstr else None, "eval_to": mstr[-1] if mstr else None, "n_months": len(mstr),
        "n_events": sum(1 for e in events if e["cls"] != CLS_NONE),
        "n_events_with_return": {str(n): sum(1 for e in events if e["cls"] != CLS_NONE and e[f"ret_{n}"] is not None)
                                 for n in HORIZONS},
        "n_benchmark_only_rows": sum(1 for e in events if e["cls"] == CLS_NONE),
        **info,
        "horizons": list(HORIZONS), "main_horizon": MAIN_H,
        "thresholds": {"c": br.TH_C, "c_lumpy": br.TH_C_LUMPY, "hi_yoy": br.HI_YOY, "hi_qoq": br.HI_QOQ, "lo": br.LO},
        "units": "報酬／超額／價差皆為 %；t＝月均值平均 ÷（月均值樣本標準差 ÷ √月數）",
        "by_class": full["by_class"], "by_class_vs_taiex": tx if info.get("taiex_available") else None,
        "spread": full["spread"],
        "halves": {"first": {"from": fa[0] if fa else None, "to": fa[-1] if fa else None, "n_months": len(fa), **p1},
                   "second": {"from": fb[0] if fb else None, "to": fb[-1] if fb else None, "n_months": len(fb), **p2}},
        "yearly": {y: period_stats(events, {s for s in mstr if s[:4] == y}) for y in years},
        "grid": grid, "grid_pick": grid_pick(grid),
        "verdict": verdict(full["spread"], p1["spread"], p2["spread"]),
        "monthly_spread": monthly,
    }


# ================= I/O =================
def fetch_raw(dataset: str, data_id: str, start: str, cache_dir: Path | None, offline: bool = False):
    """→ 原始 data 陣列；抓不到回 None（不 raise）。快取命中不連網、不 sleep。"""
    cf = cache_dir / dataset / f"{data_id}.json" if cache_dir else None
    if cf and cf.exists():
        try:
            return json.loads(cf.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    if offline:
        return None
    try:
        raw = api_get(dataset, data_id=data_id, start_date=start)
    except RuntimeError as e:
        print(f"  ! {dataset} {data_id} 抓取失敗：{e}", flush=True)
        raw = None
    time.sleep(REQ_SLEEP)
    if raw is not None and cf:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(raw), encoding="utf-8")
    return raw


def pick_price_dataset(cache_dir, offline) -> tuple:
    """以 2330 探測一次：還原價取得且解析得出價格就整批用它，否則整批退回未還原。→ (資料集名, 2330 價格 dict)"""
    for ds in (DS_ADJ, DS_RAW):
        px = parse_prices(fetch_raw(ds, CAL_CODE, PRICE_START, cache_dir, offline))
        if px:
            return ds, px
        print(f"  ! {ds} 以 {CAL_CODE} 探測取不到可用價格", flush=True)
    raise RuntimeError(f"{CAL_CODE} 兩個價格資料集都取不到可用價格（需要 date／open／close 欄），無法建立交易日曆，中止")


def fetch_all(codes: list, cache_dir, offline) -> dict:
    ds, cal_px = pick_price_dataset(cache_dir, offline)
    print(f"價格資料集：{ds}", flush=True)
    series, prices, f_rev, f_px = {}, {CAL_CODE: cal_px}, [], []
    limit = len(codes) * FAIL_ABORT
    for i, code in enumerate(codes, 1):
        raw = fetch_raw(DS_REV, code, REV_START, cache_dir, offline)
        s = br.parse_series(raw) if raw is not None else {}
        if s:
            series[code] = s
        else:
            f_rev.append(code)
        if code != CAL_CODE:
            px = parse_prices(fetch_raw(ds, code, PRICE_START, cache_dir, offline))
            if px:
                prices[code] = px
            else:
                f_px.append(code)
        bad = len(set(f_rev) | set(f_px))
        if bad > limit:      # 提早中止：限流時每次要等 65 秒，別拖到 timeout
            raise RuntimeError(f"抓取失敗已達 {bad}/{len(codes)} 檔，超過一成，中止")
        if i % 25 == 0:
            print(f"  已抓 {i}/{len(codes)}", flush=True)
    index = parse_index(fetch_raw(DS_TRI, TRI_ID, PRICE_START, cache_dir, offline))
    if not index:
        print(f"  ! {DS_TRI}（{TRI_ID}）取不到，TAIEX 超額標示為缺", flush=True)
    return {"series": series, "prices": prices, "index": index, "price_dataset": ds,
            "failed_rev": f_rev, "failed_px": f_px}


def write_outputs(out_dir: Path, summary: dict, events: list) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(summary, generated_at=taipei_now().isoformat(timespec="seconds"))
    (out_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out_dir / "events.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_HEAD)
        for e in events:
            w.writerow(["" if e[k] is None else e[k] for k in CSV_HEAD])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", help="原始回應快取目錄（<目錄>/<資料集>/<代號>.json）")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="產出目錄（預設 data/revenue/backtest）")
    ap.add_argument("--offline", action="store_true", help="只讀快取、不連網（快取沒有＝該檔抓取失敗）")
    a = ap.parse_args(argv)
    universe = json.loads((br.OUT_DIR / "universe.json").read_text(encoding="utf-8"))
    meta, lumpy = universe_meta(universe)
    codes = list(meta)
    if CAL_CODE not in meta:
        raise RuntimeError(f"universe.json 沒有 {CAL_CODE}，無法建立交易日曆")
    d = fetch_all(codes, Path(a.cache_dir) if a.cache_dir else None, a.offline)
    cal = sorted(d["prices"][CAL_CODE])
    analyzed = analyze_all(d["series"], meta)
    months = eval_months(analyzed, cal)
    if not months:
        raise RuntimeError("沒有任何可評估月份（營收歷史或價格日曆不足）")
    events = build_events(analyzed, meta, lumpy, d["prices"], cal, d["index"], months)
    info = {
        "universe_n": len(codes), "revenue_start": REV_START, "price_start": PRICE_START,
        "calendar": {"code": CAL_CODE, "from": cal[0], "to": cal[-1], "n_days": len(cal)},
        "price_dataset": d["price_dataset"], "price_adjusted": d["price_dataset"] == DS_ADJ,
        "taiex_available": bool(d["index"]), "taiex_dataset": f"{DS_TRI}:{TRI_ID}",
        "fetch_failed": {"revenue": sorted(d["failed_rev"]), "price": sorted(d["failed_px"])},
    }
    summary = build_summary(events, months, info)
    write_outputs(Path(a.out_dir), summary, events)
    sp, v = summary["spread"][str(MAIN_H)], summary["verdict"]
    print(f"評估 {summary['eval_from']}～{summary['eval_to']}（{summary['n_months']} 個月）｜事件 {summary['n_events']}｜"
          f"{d['price_dataset']}｜TAIEX {'有' if d['index'] else '缺'}｜"
          f"抓取失敗 營收 {len(d['failed_rev'])}／價格 {len(d['failed_px'])}")
    print(f"主口徑（{MAIN_H} 日）Beat−Miss 每月價差：平均 {sp['mean']}%、t={sp['t']}、{sp['n_months']} 個月"
          f"（略過 {sp['skipped_months']}）｜判定：{v['result']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
