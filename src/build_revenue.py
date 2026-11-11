# src/build_revenue.py — 月營收 Beat／Miss 資料管線
#
# 產出 data/revenue/<YYYY-MM>.json（該「營收月份」一檔）與 data/revenue/index.json。
# 規格、口徑、門檻與鐵律 8 狀態的正本＝docs/revenue-beatmiss.md；本檔常數須與該文件 §2 一致。
#
# ⚠ 本分類沒有回測依據（門檻只用 2026 年 7–10 月試作校準）。資料檔自帶 LABEL；
#   要在畫面顯示前須先取得使用者依鐵律 8 的裁定（見規格 §1）。
#
# 資料源：FinMind TaiwanStockMonthRevenue，逐檔查詢。月份用 revenue_year／revenue_month
#   （date 欄是公布月、晚一個月）。全市場單次查詢（不帶 data_id）未實測，故不依賴。
# 預期基準：A／B＝data/revenue/expect.json（人工維護、附來源）；C＝模型。彭博數值不得進本 repo。
#
# 用法：
#   FINMIND_TOKEN=... python src/build_revenue.py                  # 目標月＝台北今日的上個月
#   python src/build_revenue.py --month 2026-10                    # 指定營收月份（可重複）
#   python src/build_revenue.py --month 2026-10 --cache-dir /tmp/c # 本機開發：逐檔原始回應讀寫快取
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from fmclient import api_get, taipei_now, taipei_today  # noqa: E402

OUT_DIR = ROOT / "data" / "revenue"
SCHEMA = 1
LABEL = "AI 研判，未經回測，非保證"
START_DATE = "2021-01-01"      # 取 4 年以上歷史供季節性計算
REQ_SLEEP = 0.2                # 逐檔查詢間隔（秒）

# ---- 口徑常數（改動＝改 docs/revenue-beatmiss.md §2＋CHANGELOG）----
HIST_YEARS = 4                 # 季節性回看年數
MIN_HIST = 2                   # 季節性至少要幾年有值才採用
EQ_CLAMP = (0.75, 1.30)        # C 層預期季營收相對上季的上下限
SHARE_BAND = 0.06              # 正常進度相對 k/3 的容許偏離
RUNRATE_W = 0.7                # C 層季內修正：跑速權重（其餘為季初預期）
TH_AB = 10.0                   # A／B 層 beat/miss 門檻（%）
TH_C = 15.0                    # C 層門檻
TH_C_LUMPY = 25.0              # C 層且認列不穩次產業
HI_YOY, HI_QOQ, LO = 50.0, 15.0, -10.0
SECTOR_DELTA = 10.0            # 次產業年增率加減速門檻（百分點）

CLS_HI_BEAT, CLS_LO_MISS, CLS_BEAT, CLS_MISS, CLS_INLINE = "高預期仍Beat", "低預期仍Miss", "Beat", "Miss", "符合"


# ================= 純函式（離線可測）=================
def parse_series(rows: list) -> dict:
    """FinMind 列 → {(年, 月): 營收億元}。缺欄或非數值的列略過。"""
    out = {}
    for x in rows or []:
        try:
            y, m, v = int(x["revenue_year"]), int(x["revenue_month"]), float(x["revenue"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= m <= 12 and v == v:
            out[(y, m)] = v / 1e8
    return out


def q_of(y: int, m: int) -> tuple:
    return y, (m - 1) // 3 + 1


def qmonths(y: int, q: int) -> list:
    return [(y, 3 * (q - 1) + k) for k in (1, 2, 3)]


def prev_q(y: int, q: int) -> tuple:
    return (y, q - 1) if q > 1 else (y - 1, 4)


def prev_m(y: int, m: int) -> tuple:
    return (y, m - 1) if m > 1 else (y - 1, 12)


def qsum(r: dict, y: int, q: int):
    v = [r.get(k) for k in qmonths(y, q)]
    return sum(v) if all(x is not None for x in v) else None


def pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def hist_share(r: dict, y: int, q: int, k: int):
    """過去 HIST_YEARS 年同季「前 k 個月累計 ÷ 全季」中位數，限制在 k/3±SHARE_BAND；歷史不足回 k/3。"""
    if k >= 3:
        return 1.0
    sh = []
    for d in range(1, HIST_YEARS + 1):
        t = qsum(r, y - d, q)
        if t:
            sh.append(sum(r[x] for x in qmonths(y - d, q)[:k]) / t)
    s = statistics.median(sh) if len(sh) >= MIN_HIST else k / 3
    return min(max(s, k / 3 - SHARE_BAND), k / 3 + SHARE_BAND)


def model_eq(r: dict, y: int, q: int):
    """C 層預期季營收；資料不足回 None。"""
    py, pq = prev_q(y, q)
    pqv, lyq, lypq = qsum(r, py, pq), qsum(r, y - 1, q), qsum(r, py - 1, pq)
    cands = []
    if lyq and pqv and lypq:
        cands.append(lyq * pqv / lypq)                       # 趨勢延續
    hq = []
    for d in range(1, HIST_YEARS + 1):
        a, b = qsum(r, y - d, q), qsum(r, *prev_q(y - d, q))
        if a and b:
            hq.append(a / b)
    if pqv and len(hq) >= MIN_HIST:
        cands.append(pqv * statistics.median(hq))            # 季節性
    if not cands:
        return None
    p = 1.0
    for c in cands:
        p *= c
    eq = p ** (1 / len(cands))
    if pqv:
        eq = min(max(eq, pqv * EQ_CLAMP[0]), pqv * EQ_CLAMP[1])
    return eq


def analyze(r: dict, y: int, m: int, override=None):
    """單檔單月分析。override＝(預期季營收億元, 層級, 來源) 或 None。當月無營收或無法建立預期回 None。"""
    a = r.get((y, m))
    if a is None:
        return None
    yy, q = q_of(y, m)
    k = m - 3 * (q - 1)
    months = qmonths(yy, q)[:k]
    if any(r.get(x) is None for x in months):
        return None
    qtd = sum(r[x] for x in months)
    py, pq = prev_q(yy, q)
    pqv, lyq = qsum(r, py, pq), qsum(r, yy - 1, q)
    layer, src = "C", "模型"
    eq = model_eq(r, yy, q)
    if override:
        eq, layer, src = override
    if not eq:
        return None
    share = hist_share(r, yy, q, k)
    sur = qtd / (eq * share) - 1
    if layer == "C" and k > 1:
        s0 = hist_share(r, yy, q, k - 1)
        eq_rev = RUNRATE_W * ((qtd - a) / s0) + (1 - RUNRATE_W) * eq
        exp_m = eq_rev * (share - s0)
        if exp_m > 0:
            sur = a / exp_m - 1
    pm = prev_m(y, m)
    return {
        "rev": a, "mom": pct(a, r.get(pm)), "yoy": pct(a, r.get((y - 1, m))),
        "prev_yoy": pct(r.get(pm), r.get((pm[0] - 1, pm[1]))),
        "exp_q": eq, "exp_qoq": pct(eq, pqv), "exp_yoy": pct(eq, lyq),
        "ach": qtd / eq * 100, "norm": share * 100, "sur": sur * 100,
        "layer": layer, "src": src, "k": k,
    }


def classify(x: dict, lumpy: bool) -> str:
    th = TH_AB if x["layer"] != "C" else (TH_C_LUMPY if lumpy else TH_C)
    ey, eqq = x["exp_yoy"], x["exp_qoq"]
    hi = (ey is not None and ey >= HI_YOY) or (eqq is not None and eqq >= HI_QOQ)
    lo = (ey is not None and ey <= LO) or (eqq is not None and eqq <= LO)
    if hi and lo:
        hi = ey is not None and ey >= HI_YOY
        lo = not hi
    if x["sur"] >= th:
        return CLS_HI_BEAT if hi else CLS_BEAT
    if x["sur"] <= -th:
        return CLS_LO_MISS if lo else CLS_MISS
    return CLS_INLINE


def sector_table(series: dict, sector_of: dict, y: int, m: int) -> list:
    """次產業年增率（成分股加總）；四個月份都有值的成分股才計入。依加速幅度遞減。"""
    pm = prev_m(y, m)
    keys = [(y, m), (y - 1, m), pm, (pm[0] - 1, pm[1])]
    agg = {}
    for code, r in series.items():
        if all(k in r for k in keys):
            a = agg.setdefault(sector_of[code], [0.0, 0.0, 0.0, 0.0, 0])
            for j, k in enumerate(keys):
                a[j] += r[k]
            a[4] += 1
    out = []
    for s, a in agg.items():
        if not a[1] or not a[3]:
            continue
        yoy, pyoy = (a[0] / a[1] - 1) * 100, (a[2] / a[3] - 1) * 100
        d = yoy - pyoy
        out.append({"name": s, "n": a[4], "yoy": _r(yoy, 1), "prev_yoy": _r(pyoy, 1), "delta": _r(d, 1),
                    "signal": "加速" if d >= SECTOR_DELTA else ("減速" if d <= -SECTOR_DELTA else "")})
    return sorted(out, key=lambda t: (-t["delta"], t["name"]))


def _r(v, nd):
    return None if v is None else round(v, nd)


def load_overrides(expect: dict) -> dict:
    """expect.json → {(code, 'YYYYQn'): (億元, 層級, 來源)}；只收 A／B 層且數值為正的列。"""
    out = {}
    for e in (expect or {}).get("entries", []):
        try:
            v = float(e["exp_rev_100m"])
            if e["layer"] in ("A", "B") and v > 0:
                out[(str(e["code"]), str(e["quarter"]))] = (v, e["layer"], str(e.get("source", "")))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def build_month(series: dict, universe: dict, overrides: dict, y: int, m: int, failed=()) -> dict:
    """組出單月 payload（不含 generated_at）。failed＝本次抓取失敗的代號（與「未公布」分開標示）。"""
    lumpy = set(universe.get("lumpy_sectors", []))
    meta = {s["code"]: (s["name"], sec) for sec, lst in universe["sectors"].items() for s in lst}
    yy, q = q_of(y, m)
    qkey = f"{yy}Q{q}"
    rows, missing = [], []
    for code, (name, sec) in meta.items():
        r = series.get(code) or {}
        x = analyze(r, y, m, overrides.get((code, qkey)))
        if x is None:
            why = ("抓取失敗" if code in failed else
                   "當月營收未公布或無資料" if (y, m) not in r else "歷史不足，無法建立預期")
            missing.append({"code": code, "name": name, "why": why})
            continue
        cls = classify(x, sec in lumpy)
        rows.append({
            "code": code, "name": name, "sector": sec, "cls": cls,
            "rev": _r(x["rev"], 2), "mom": _r(x["mom"], 1), "yoy": _r(x["yoy"], 1), "prev_yoy": _r(x["prev_yoy"], 1),
            "exp_q": _r(x["exp_q"], 2), "exp_qoq": _r(x["exp_qoq"], 1), "exp_yoy": _r(x["exp_yoy"], 1),
            "ach": _r(x["ach"], 1), "norm": _r(x["norm"], 1), "sur": _r(x["sur"], 1),
            "layer": x["layer"], "src": x["src"],
        })
    order = {CLS_HI_BEAT: 0, CLS_LO_MISS: 1, CLS_BEAT: 2, CLS_MISS: 3, CLS_INLINE: 4}
    rows.sort(key=lambda t: (order[t["cls"]], -abs(t["sur"]), t["code"]))
    counts = {c: sum(1 for t in rows if t["cls"] == c) for c in order}
    tsmc = series.get("2330") or {}
    sector_of = {c: v[1] for c, v in meta.items()}
    return {
        "schema": SCHEMA, "label": LABEL, "month": f"{y}-{m:02d}", "quarter": qkey, "k": m - 3 * (q - 1),
        "universe_n": len(meta), "reported_n": len(rows), "counts": counts,
        "tsmc_yoy": _r(pct(tsmc.get((y, m)), tsmc.get((y - 1, m))), 1),
        "thresholds": {"ab": TH_AB, "c": TH_C, "c_lumpy": TH_C_LUMPY, "hi_yoy": HI_YOY, "hi_qoq": HI_QOQ, "lo": LO,
                       "sector_delta": SECTOR_DELTA},
        "sectors": sector_table({c: r for c, r in series.items() if c in sector_of}, sector_of, y, m),
        "rows": rows, "missing": missing, "fetch_failed": sorted(failed),
    }


def default_month(today) -> tuple:
    """目標營收月份＝台北今日的上個月。"""
    return prev_m(today.year, today.month)


# ================= I/O =================
def fetch_series(codes: list, cache_dir: Path | None = None) -> dict:
    series, failed = {}, []
    for i, code in enumerate(codes, 1):
        raw = None
        cf = cache_dir / f"{code}.json" if cache_dir else None
        if cf and cf.exists():
            raw = json.loads(cf.read_text(encoding="utf-8"))
        else:
            try:
                raw = api_get("TaiwanStockMonthRevenue", data_id=code, start_date=START_DATE)
            except RuntimeError as e:
                failed.append(code)
                print(f"  ! {code} 抓取失敗：{e}", flush=True)
            if raw is not None and cf:
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(json.dumps(raw), encoding="utf-8")
            time.sleep(REQ_SLEEP)
        if raw is not None:
            series[code] = parse_series(raw)
        if i % 50 == 0:
            print(f"  已抓 {i}/{len(codes)}", flush=True)
    return series, failed


def write_if_changed(path: Path, payload: dict) -> bool:
    """內容（不含 generated_at）與現有檔相同就不重寫，避免只有時間戳的 commit。"""
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            old.pop("generated_at", None)
            if old == payload:
                return False
        except (ValueError, OSError):
            pass
    out = dict(payload, generated_at=taipei_now().isoformat(timespec="seconds"))
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return True


def write_index() -> None:
    months = sorted(p.stem for p in OUT_DIR.glob("????-??.json"))
    payload = {"schema": SCHEMA, "months": months, "latest": months[-1] if months else None}
    write_if_changed(OUT_DIR / "index.json", payload)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", action="append", help="營收月份 YYYY-MM，可重複；省略＝台北今日的上個月")
    ap.add_argument("--cache-dir", help="本機開發用：逐檔原始回應快取目錄")
    a = ap.parse_args(argv)
    if a.month:
        targets = []
        for s in a.month:
            y, m = s.split("-")
            targets.append((int(y), int(m)))
    else:
        targets = [default_month(taipei_today())]
    universe = json.loads((OUT_DIR / "universe.json").read_text(encoding="utf-8"))
    overrides = load_overrides(json.loads((OUT_DIR / "expect.json").read_text(encoding="utf-8")))
    codes = [s["code"] for lst in universe["sectors"].values() for s in lst]
    if len(set(codes)) != len(codes):
        raise RuntimeError("universe.json 有重複代號（一檔只能屬一個次產業）")
    series, failed = fetch_series(codes, Path(a.cache_dir) if a.cache_dir else None)
    # 抓取失敗超過一成＝資料源異常，中止不寫檔（避免把大量公司誤列為「未公布」）
    if len(failed) > len(codes) * 0.1:
        raise RuntimeError(f"抓取失敗 {len(failed)}/{len(codes)} 檔，超過一成，中止")
    for y, m in targets:
        payload = build_month(series, universe, overrides, y, m, failed)
        if payload["reported_n"] == 0:
            print(f"{y}-{m:02d}：尚無任何公司公布，略過不寫檔")
            continue
        changed = write_if_changed(OUT_DIR / f"{y}-{m:02d}.json", payload)
        c = payload["counts"]
        print(f"{y}-{m:02d} 已公布 {payload['reported_n']}/{payload['universe_n']}｜"
              f"高預期Beat {c[CLS_HI_BEAT]}｜低預期Miss {c[CLS_LO_MISS]}｜Beat {c[CLS_BEAT]}｜Miss {c[CLS_MISS]}｜"
              f"{'已寫檔' if changed else '內容相同未重寫'}")
    write_index()
    return 0


if __name__ == "__main__":
    sys.exit(main())
