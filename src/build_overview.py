# src/build_overview.py — 「市場總覽」tab 的兩張交集表（2026-11-12 使用者裁定：標示後先上線）
#
# 規格與驗收條件正本：docs/market-overview.md（§3 為本檔的定案內容）。
# 寫：data/overview/latest.json ＋ data/overview/daily/<date>.json（每日快照，事後驗證用）。
# 前端（index.html「市場總覽」tab）只渲染、不重算——交集口徑只有這一份實作。
#
# 鐵律 8：交集表依「出現在幾個來源清單」排序，屬新的候選排序、**無回測依據**；使用者 2026-11-12 裁定
# 標示「AI 研判，未經回測，非保證」後上線，列入事後驗證。本批只做偏多（資金流入）側。
#
# 來源（各自獨立 try；讀不到／形狀不合＝status "fail"、不計入，其餘照算）：
#   類股（主鍵＝產業鏈「產業」，47 條；flows chain／classify.c／chain_daily 三者同一套命名，2026-11-12 實查）
#     A 產業鏈資金流：taiwan-flows sector_ranges_lite.json windows.r5 chain/total 淨買金額 >0 前 10（基準日＝r5.end）
#     B 籌碼雷達：同檔 r5 對 r20，index.html radarPoints(…,"chain","total") 的 acc_in（加速流入）象限
#     C 主動 ETF 次產業加碼前 10：taiwan-flow-live-v2 aetf/diff.json subs（val>0），經 classify.json 的
#       (產業, 次產業) 配對上卷；一個次產業名對到多個產業時不上卷（列入 unmapped）
#     D 連湧／新湧次產業：taiwan-flow-live-v2 morning.json signals.cont_subs＋new_subs，同法上卷；
#       資料日＝recap.baseline_date（前一交易日的資料）→ 晚間建置時通常 stale、不計入
#     E 日級輪動雷達：chain_daily/series.json，index.html rrgdPersistList 的「改善」「領先」（連續 3 日）
#   個股（主鍵＝代號）
#     a 外資投信同步買超 Top30：taiwan-flows latest.json pages.sync.sync_buy（基準日＝latest.date）
#     b 主動 ETF 跨 ETF 加碼共識：aetf/diff.json stocks，by 中 >0 的 ETF 數 ≥2（同 index.html aetfInsight 的 nBuyers）
#     c 選股二追蹤名單：data/pick2/track.json tracking
#     d 月營收 Beat／高預期仍Beat：data/revenue/<latest>.json（月頻，容許窗見 revenue_valid）
#     e 千張大戶週增前 20：data/diag/diag.json，index.html radarHolders(diag,"all").up（週頻，容許窗 HOLDER_MAX_AGE_DAYS）
#     f 彙總分析精華標的：**不納入**（標題格式逐場不同，方向無法可靠解析；見 docs/market-overview.md §3.2）
#
# B／E／e／b 為前端口徑的 Python 移植，tests/test_overview_build.py 以 node 抽 index.html 對跑、逐位比對。
#
# 冪等：generated_at 以外內容相同時不重寫檔（不產生 commit 噪音）。
# 失敗處理：類股與個股兩層的基準來源（A、a）都讀不到 → 不寫檔、exit 2。
#
# 用法：
#   python src/build_overview.py                       # 正式：跨 repo 檔走 raw main，本 repo 檔讀磁碟
#   python src/build_overview.py --src-root /home/user # 跨 repo 檔改讀本機 checkout（或環境變數 OVERVIEW_SRC_ROOT）
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/shihpc/{repo}/main/{path}"
TAIPEI = dt.timezone(dt.timedelta(hours=8))
LABEL = "AI 研判，未經回測，非保證"
SCHEMA = 1
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
CODE_RE = re.compile(r"^\d{4}[0-9A-Z]{0,2}$")

TOP_A = 10                 # A：淨買金額前 10
TOP_C = 10                 # C：次產業加碼前 10
RADAR_MIN_N = 8            # ＝index.html RADAR_MIN_N
RRGD_N, RRGD_K, RRGD_PERSIST = 12, 10, 3   # ＝index.html RRGD_N／RRGD_K／RRGD_PERSIST
HOLDER_TOP = 20            # ＝index.html radarHolders 的 slice(0,20)
HOLDER_MAX_AGE_DAYS = 10   # e（週頻）：集保資料日距基準日 0–10 個日曆日內才計入
REV_CLS = ("高預期仍Beat", "Beat")
REV_VALID_UNTIL_DAY = 15   # d（月頻）：營收月份 M 自 M+1 月 1 日起、至 M+2 月 15 日止計入
MIN_VALID = 2              # 有效來源少於 2 個時該表不輸出列
FETCH_TIMEOUT = 30

SRC_FILES = {
    "sr": ("taiwan-flows", "data/sector_ranges_lite.json"),
    "tf": ("taiwan-flows", "data/latest.json"),
    "diff": ("taiwan-flow-live-v2", "data/aetf/diff.json"),
    "morning": ("taiwan-flow-live-v2", "data/morning.json"),
    "series": ("taiwan-flow-live-v2", "data/chain_daily/series.json"),
    "classify": ("taiwan-flow-live-v2", "data/classify.json"),
}


# ---------- JS 語意輔助 ----------

def fin(v) -> bool:
    """JS `typeof v === "number" && isFinite(v)`"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def norm_date(v):
    """'2026/11/12'／'2026-11-12…' → '2026-11-12'；不合回 None"""
    if not isinstance(v, str):
        return None
    s = v[:10].replace("/", "-")
    return s if DATE_RE.match(s) else None


def _s(v) -> str:
    return v if isinstance(v, str) else ""


# ---------- 口徑移植：籌碼雷達（index.html radarQuad／radarPoints） ----------

def radar_quad(x: float, y: float) -> str:
    if x >= 0:
        return "acc_in" if y >= 0 else "slow_in"
    return "acc_out" if y < 0 else "slow_out"


def radar_points(r5, r20, classify: str, inv: str) -> list[dict]:
    def pick(w):
        try:
            v = w["classifications"][classify]["investors"][inv]
        except (KeyError, TypeError):
            return []
        return v if isinstance(v, list) else []

    def td(w):
        if not isinstance(w, dict):
            return 0
        return w.get("trading_days") or (len(w["dates"]) if isinstance(w.get("dates"), list) else 0) or 0

    d5, d20 = td(r5), td(r20)
    if not d5 or not d20:
        return []
    m5 = {r["sector"]: r for r in pick(r5) if isinstance(r, dict) and isinstance(r.get("sector"), str)}
    out = []
    for b in pick(r20):
        if not isinstance(b, dict) or not isinstance(b.get("sector"), str):
            continue
        a = m5.get(b["sector"])
        if a is None or not (fin(b.get("n")) and b["n"] >= RADAR_MIN_N):
            continue
        if not fin(b.get("net_amt_k")) or not fin(a.get("net_amt_k")):
            continue   # 前端此時會得到 NaN；後端直接不列（實檔無此情形）
        v20, v5 = b["net_amt_k"] / 1e5, a["net_amt_k"] / 1e5
        x = v20 / d20
        y = v5 / d5 - x
        out.append({"sector": b["sector"], "n": b["n"], "v20": v20, "v5": v5, "x": x, "y": y, "q": radar_quad(x, y)})
    out.sort(key=lambda p: (-p["v20"], p["sector"]))
    return out


# ---------- 口徑移植：千張大戶（index.html radarHolders，ind="all" 的 up 清單） ----------

def radar_holders_up(diag) -> dict:
    st = diag.get("stocks") if isinstance(diag, dict) else None
    st = st if isinstance(st, dict) else {}
    al = []
    for code, s in st.items():
        if not isinstance(s, dict) or not fin(s.get("hdw")):
            continue
        n = s.get("n")
        al.append({"code": code, "name": "" if n is None else str(n), "hdw": s["hdw"],
                   "hdd": s["hdd"] if isinstance(s.get("hdd"), str) else None})
    hdd = None
    for r in al:
        if r["hdd"] and (hdd is None or r["hdd"] > hdd):
            hdd = r["hdd"]
    up = sorted((r for r in al if r["hdw"] > 0), key=lambda r: (-r["hdw"], r["code"]))[:HOLDER_TOP]
    return {"up": up, "cover": len(al), "hdd": hdd}


# ---------- 口徑移植：日級輪動雷達（index.html RRGD-PURE 區段） ----------

def rrgd_cum_index(rets, base=100):
    out, v, broken, started = [], base, False, False
    for r in rets:
        if broken:
            out.append(None)
            continue
        out.append(v)
        if r is None:
            if started:
                broken = True
            continue
        started = True
        v *= (1 + r)
    return out


def rrgd_roll_mean_sd(xs, n):
    mu, sd = [None] * len(xs), [None] * len(xs)
    for t in range(n - 1, len(xs)):
        w = xs[t - n + 1:t + 1]
        if any(v is None for v in w):
            continue
        m = 0.0
        for v in w:
            m += v
        m /= n
        mu[t] = m
        s = 0.0
        for v in w:
            s += (v - m) * (v - m)
        sd[t] = math.sqrt(s / (n - 1)) if n > 1 else 0
    return mu, sd


def rrgd_zscore100(xs, n):
    mu, sd = rrgd_roll_mean_sd(xs, n)
    out = [None] * len(xs)
    for t in range(len(xs)):
        if xs[t] is None or mu[t] is None or not sd[t]:
            continue
        out[t] = 100 + (xs[t] - mu[t]) / sd[t]
    return out


def rrgd_price_coords(chain_rets: dict, bench_ret, n, k) -> dict:
    bi = rrgd_cum_index(bench_ret)
    out = {}
    for name, rets in chain_rets.items():
        ci = rrgd_cum_index(rets)
        rs = [None if (v is None or not bi[t]) else 100 * v / bi[t] for t, v in enumerate(ci)]
        rat = rrgd_zscore100(rs, n)
        roc = [None if (t < k or v is None or not rat[t - k]) else 100 * (v / rat[t - k] - 1) for t, v in enumerate(rat)]
        mom = rrgd_zscore100(roc, n)
        out[name] = [None if (v is None or mom[t] is None) else (v, mom[t]) for t, v in enumerate(rat)]
    return out


def rrgd_quad(r, m) -> str:
    if r >= 100:
        return "領先" if m >= 100 else "轉弱"
    return "改善" if m >= 100 else "落後"


def rrgd_persist_list(coords: dict, t: int, q: str, n: int, sort_key: int = 1) -> list[str]:
    out = []
    for name, arr in coords.items():
        ok = True
        for j in range(n):
            i = t - j
            if i < 0 or not arr[i] or rrgd_quad(arr[i][0], arr[i][1]) != q:
                ok = False
                break
        if ok:
            out.append(name)
    out.sort(key=lambda nm: (-coords[nm][t][sort_key], nm))
    return out


def rrgd_prep(j) -> dict:
    """＝index.html rrgdPrep；格式異常 raise ValueError"""
    if (not isinstance(j, dict) or not isinstance(j.get("dates"), list) or not j["dates"]
            or not isinstance(j.get("chains"), dict) or not isinstance(j.get("market"), dict)
            or not isinstance(j["market"].get("ret_ew"), list)):
        raise ValueError("series.json 格式異常")
    T, rets = len(j["dates"]), {}
    for name, c in j["chains"].items():
        if not isinstance(c, dict) or not isinstance(c.get("ret_ew"), list) or len(c["ret_ew"]) != T:
            raise ValueError(f"series.json 格式異常（{name}）")
        rets[name] = c["ret_ew"]
    coords = rrgd_price_coords(rets, j["market"]["ret_ew"], RRGD_N, RRGD_K)
    names = list(coords.keys())
    need = max(2, len(names) // 2)
    valid = [t for t in range(T) if sum(1 for nm in names if coords[nm][t]) >= need]
    if not valid:
        raise ValueError("series.json 資料不足")
    return {"coords": coords, "valid": valid, "names": names}


# ---------- 口徑移植：主動 ETF 跨 ETF 加碼共識（index.html aetfInsight 的 nBuyers(s)>=2） ----------

def aetf_n_buyers(s) -> int:
    by = s.get("by") if isinstance(s, dict) else None
    if not isinstance(by, dict):
        return 0
    return sum(1 for v in by.values() if fin(v) and v > 0)


def aetf_co_buy(diff) -> list[dict]:
    st = diff.get("stocks") if isinstance(diff, dict) else None
    return [s for s in (st if isinstance(st, list) else []) if aetf_n_buyers(s) >= 2]


# ---------- 次產業 → 產業 上卷 ----------

def sub_parents(classify) -> dict[str, list[str]] | None:
    """classify.json map[code].p＝[[產業, 次產業], …] → {次產業: [產業…]}；形狀不合回 None"""
    mp = classify.get("map") if isinstance(classify, dict) else None
    if not isinstance(mp, dict) or not mp:
        return None
    out: dict[str, set] = {}
    for v in mp.values():
        for p in (v.get("p") if isinstance(v, dict) and isinstance(v.get("p"), list) else []):
            if isinstance(p, list) and len(p) == 2 and isinstance(p[0], str) and isinstance(p[1], str):
                out.setdefault(p[1], set()).add(p[0])
    return {k: sorted(v) for k, v in out.items()} or None


def roll_up(subs: list[str], parents: dict[str, list[str]]):
    """回 (items=[{key, via:[次產業…]}], unmapped=[次產業…])。只收**唯一**對到一個產業的次產業。"""
    via: dict[str, list[str]] = {}
    unmapped = []
    for s in subs:
        ps = parents.get(s) or []
        if len(ps) == 1:
            via.setdefault(ps[0], []).append(s)
        else:
            unmapped.append(s)
    return [{"key": k, "via": v} for k, v in sorted(via.items())], unmapped


# ---------- 容許窗 ----------

def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def revenue_valid(month: str, base: str) -> bool:
    """營收月份 M（YYYY-MM）：基準日落在 [M+1 月 1 日, M+2 月 REV_VALID_UNTIL_DAY 日] 才計入"""
    y, m = int(month[:4]), int(month[5:7])
    y1, m1 = (y + 1, 1) if m == 12 else (y, m + 1)
    y2, m2 = (y1 + 1, 1) if m1 == 12 else (y1, m1 + 1)
    return dt.date(y1, m1, 1) <= _d(base) <= dt.date(y2, m2, REV_VALID_UNTIL_DAY)


def holder_valid(hdd: str, base: str) -> bool:
    return 0 <= (_d(base) - _d(hdd)).days <= HOLDER_MAX_AGE_DAYS


# ---------- 來源抽取（每個回 {id,name,freq,date,items,note?}；失敗 raise） ----------

def src_A(sr):
    r5 = sr["windows"]["r5"]
    rows = r5["classifications"]["chain"]["investors"]["total"]
    date = norm_date(r5.get("end")) or norm_date(sr.get("date"))
    if not date or not isinstance(rows, list):
        raise ValueError("形狀不合")
    pos = [r for r in rows if isinstance(r, dict) and isinstance(r.get("sector"), str)
           and fin(r.get("net_amt_k")) and r["net_amt_k"] > 0]
    pos.sort(key=lambda r: (-r["net_amt_k"], r["sector"]))
    return {"date": date, "items": [{"key": r["sector"]} for r in pos[:TOP_A]]}


def src_B(sr):
    w = sr["windows"]
    date = norm_date(w["r5"].get("end")) or norm_date(sr.get("date"))
    if not date:
        raise ValueError("形狀不合")
    pts = radar_points(w["r5"], w["r20"], "chain", "total")
    if not pts:
        raise ValueError("r5／r20 無可比類股")
    return {"date": date, "items": [{"key": p["sector"]} for p in sorted(pts, key=lambda p: p["sector"]) if p["q"] == "acc_in"]}


def src_C(diff, parents):
    date = norm_date(diff.get("primary_date"))
    subs = diff.get("subs")
    if not date or not isinstance(subs, list):
        raise ValueError("形狀不合")
    pos = [s for s in subs if isinstance(s, dict) and isinstance(s.get("name"), str) and fin(s.get("val")) and s["val"] > 0]
    pos.sort(key=lambda s: (-s["val"], s["name"]))
    names = [s["name"] for s in pos[:TOP_C]]
    if parents is None:
        return {"date": date, "items": [], "subs": names, "listed": True,
                "note": "次產業對映檔（classify.json）讀不到，無法上卷到產業：另列、不計入交集"}
    items, unmapped = roll_up(names, parents)
    return {"date": date, "items": items, "subs": names, "unmapped": unmapped}


def src_D(morning, parents):
    sig = morning.get("signals")
    date = norm_date((morning.get("recap") or {}).get("baseline_date"))
    if not isinstance(sig, dict) or not date:
        raise ValueError("形狀不合")
    names = []
    for k in ("cont_subs", "new_subs"):
        for s in (sig.get(k) if isinstance(sig.get(k), list) else []):
            if isinstance(s, str) and s not in names:
                names.append(s)
    if parents is None:
        return {"date": date, "items": [], "subs": names, "listed": True,
                "note": "次產業對映檔（classify.json）讀不到，無法上卷到產業：另列、不計入交集"}
    items, unmapped = roll_up(names, parents)
    return {"date": date, "items": items, "subs": names, "unmapped": unmapped}


def src_E(series):
    p = rrgd_prep(series)
    t = p["valid"][-1]
    date = norm_date(series["dates"][t])
    if not date:
        raise ValueError("日期不合")
    imp = rrgd_persist_list(p["coords"], t, "改善", RRGD_PERSIST, 1)
    lead = rrgd_persist_list(p["coords"], t, "領先", RRGD_PERSIST, 0)
    items = [{"key": k, "via": ["改善"]} for k in imp] + [{"key": k, "via": ["領先"]} for k in lead]
    return {"date": date, "items": sorted(items, key=lambda x: x["key"])}


def _stock_item(code, name):
    if not isinstance(code, str) or not CODE_RE.match(code):
        return None
    return {"key": code, "name": _s(name)}


def src_a(tf):
    date = norm_date(tf.get("date"))
    rows = tf["pages"]["sync"]["sync_buy"]
    if not date or not isinstance(rows, list):
        raise ValueError("形狀不合")
    items = [x for x in (_stock_item(r.get("code"), r.get("name")) for r in rows if isinstance(r, dict)) if x]
    return {"date": date, "items": items}


def src_b(diff):
    date = norm_date(diff.get("primary_date"))
    if not date or not isinstance(diff.get("stocks"), list):
        raise ValueError("形狀不合")
    items = [x for x in (_stock_item(s.get("c"), s.get("n")) for s in aetf_co_buy(diff)) if x]
    return {"date": date, "items": items}


def src_c(track):
    date = norm_date(track.get("date"))
    rows = track.get("tracking")
    if track.get("schema") != 1 or not date or not isinstance(rows, list):
        raise ValueError("形狀不合")
    items = [x for x in (_stock_item(r.get("code"), r.get("name")) for r in rows if isinstance(r, dict)) if x]
    return {"date": date, "items": items}


def src_d(rev):
    month = rev.get("month")
    rows = rev.get("rows")
    if not isinstance(month, str) or not MONTH_RE.match(month) or not isinstance(rows, list):
        raise ValueError("形狀不合")
    items = [x for x in (_stock_item(r.get("code"), r.get("name")) for r in rows
                         if isinstance(r, dict) and r.get("cls") in REV_CLS) if x]
    return {"date": month, "items": items}


def src_e(diag):
    h = radar_holders_up(diag)
    if not h["cover"] or not h["hdd"] or not DATE_RE.match(h["hdd"]):
        raise ValueError("無大戶資料或集保資料日不合")
    items = [x for x in (_stock_item(r["code"], r["name"]) for r in h["up"]) if x]
    return {"date": h["hdd"], "items": items}


# ---------- 交集 ----------

SECTOR_DEFS = [
    ("A", "產業鏈資金流：近 5 日三大法人淨買前 10", "daily"),
    ("B", "籌碼雷達：近 5 日對近 20 日「加速流入」象限", "daily"),
    ("C", "主動 ETF 次產業加碼前 10（上卷到產業）", "daily"),
    ("D", "連湧／新湧次產業（上卷到產業）", "daily"),
    ("E", "日級輪動雷達：連續 3 日「改善」或「領先」", "daily"),
]
STOCK_DEFS = [
    ("a", "外資投信同步買超 Top30", "daily"),
    ("b", "主動 ETF 跨 ETF 加碼共識（≥2 檔同買）", "daily"),
    ("c", "選股二追蹤名單", "daily"),
    ("d", "月營收 Beat／高預期仍Beat", "monthly"),
    ("e", "千張大戶週增前 20", "weekly"),
]
EXCLUDED_F = {"id": "f", "name": "彙總分析精華標的", "freq": "daily", "date": None, "ok": False, "stale": False,
              "counted": False, "status": "excluded", "n": 0, "items": [],
              "note": "不納入：彙總分析為 AI 自由文字，標題格式逐場不同，方向無法可靠解析"}


def judge(defs, got: dict, base_id: str, valid_fn) -> tuple[str | None, list[dict]]:
    """got[id]＝抽取結果 dict 或 Exception。回 (base_date, sources)"""
    b = got.get(base_id)
    base = b["date"] if isinstance(b, dict) else None
    out = []
    for sid, name, freq in defs:
        g = got.get(sid)
        s = {"id": sid, "name": name, "freq": freq, "date": None, "ok": False, "stale": False,
             "counted": False, "status": "fail", "n": 0, "items": []}
        if not isinstance(g, dict):
            s["note"] = "讀取失敗或形狀不合" + (f"（{type(g).__name__}）" if isinstance(g, Exception) else "")
            out.append(s)
            continue
        s.update({"date": g["date"], "ok": True, "n": len(g["items"]), "items": g["items"]})
        for k in ("subs", "unmapped", "note"):
            if g.get(k):
                s[k] = g[k]
        if g.get("listed"):
            s["status"] = "listed"
        elif base is None:
            s["status"] = "stale"
            s["stale"] = True
            s["note"] = "基準來源讀不到，無從比對資料日，不計入"
        elif valid_fn(sid, g["date"], base):
            s["status"] = "valid"
            s["counted"] = True
        else:
            s["status"] = "stale"
            s["stale"] = True
        out.append(s)
    return base, out


def sector_valid(sid, date, base) -> bool:
    return date == base


def stock_valid(sid, date, base) -> bool:
    if sid == "d":
        return revenue_valid(date, base)
    if sid == "e":
        return holder_valid(date, base)
    return date == base


def intersect(sources: list[dict], with_name: bool) -> tuple[list[dict], str | None]:
    counted = [s for s in sources if s["counted"]]
    if len(counted) < MIN_VALID:
        return [], f"有效來源只有 {len(counted)} 個（少於 {MIN_VALID} 個），不輸出交集"
    hits: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    via: dict[str, dict] = {}
    for s in counted:
        seen = set()
        for it in s["items"]:
            k = it["key"]
            if k not in seen:
                seen.add(k)
                hits.setdefault(k, []).append(s["id"])
            if with_name and it.get("name") and k not in names:
                names[k] = it["name"]
            if it.get("via"):
                via.setdefault(k, {}).setdefault(s["id"], [])
                via[k][s["id"]] += [v for v in it["via"] if v not in via[k][s["id"]]]
    rows = []
    for k in sorted(hits, key=lambda k: (-len(hits[k]), k)):
        if len(hits[k]) < 2:
            continue
        r = {"key": k, "count": len(hits[k]), "hits": hits[k]}
        if with_name:
            r["name"] = names.get(k, "")
        if k in via:
            r["via"] = via[k]
        rows.append(r)
    return rows, None


def build(inp: dict, gen: str) -> dict | None:
    """inp＝{sr, tf, diff, morning, series, classify, track, rev, diag}，值為已解析 JSON 或 Exception／None。"""
    def run(fn, *keys):
        args = [inp.get(k) for k in keys]
        if any(not isinstance(a, dict) for a in args):
            bad = next(a for a in args if not isinstance(a, dict))
            return bad if isinstance(bad, Exception) else ValueError("缺檔")
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            return e

    cl = inp.get("classify")
    parents = sub_parents(cl) if isinstance(cl, dict) else None

    def with_parents(fn, key):
        a = inp.get(key)
        if not isinstance(a, dict):
            return a if isinstance(a, Exception) else ValueError("缺檔")
        try:
            return fn(a, parents)
        except Exception as e:  # noqa: BLE001
            return e

    sg = {"A": run(src_A, "sr"), "B": run(src_B, "sr"), "C": with_parents(src_C, "diff"),
          "D": with_parents(src_D, "morning"), "E": run(src_E, "series")}
    tg = {"a": run(src_a, "tf"), "b": run(src_b, "diff"), "c": run(src_c, "track"),
          "d": run(src_d, "rev"), "e": run(src_e, "diag")}
    sbase, ssrc = judge(SECTOR_DEFS, sg, "A", sector_valid)
    tbase, tsrc = judge(STOCK_DEFS, tg, "a", stock_valid)
    date = tbase or sbase
    if not date:
        return None
    srows, snote = intersect(ssrc, False)
    trows, tnote = intersect(tsrc, True)
    sectors = {"base_date": sbase, "sources": ssrc, "rows": srows}
    stocks = {"base_date": tbase, "sources": tsrc + [dict(EXCLUDED_F)], "rows": trows}
    if snote:
        sectors["note"] = snote
    if tnote:
        stocks["note"] = tnote
    return {"schema": SCHEMA, "date": date, "generated_at": gen, "label": LABEL, "side": "long",
            "sectors": sectors, "stocks": stocks}


# ---------- 輸入／輸出 ----------

def load_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fetch_remote(repo: str, path: str, src_root: str | None):
    """跨 repo 檔：本機 checkout（--src-root）或 raw main（逾時 30 秒、失敗重試一次）。失敗回 Exception。"""
    if src_root:
        try:
            return load_json(Path(src_root) / repo / path)
        except Exception as e:  # noqa: BLE001
            return e
    import requests
    err: Exception = ValueError("unknown")
    for attempt in (1, 2):
        try:
            r = requests.get(RAW.format(repo=repo, path=path), timeout=FETCH_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            err = e
            print(f"  ! {repo}/{path} 讀取失敗（{type(e).__name__}）" + ("，重試一次" if attempt == 1 else ""))
            if attempt == 1:
                time.sleep(3)
    return err


def load_local(root: Path) -> dict:
    out = {}

    def tryload(key, fn):
        try:
            out[key] = fn()
        except Exception as e:  # noqa: BLE001
            out[key] = e

    tryload("track", lambda: load_json(root / "data/pick2/track.json"))
    tryload("diag", lambda: load_json(root / "data/diag/diag.json"))

    def rev():
        idx = load_json(root / "data/revenue/index.json")
        m = idx.get("latest")
        if not isinstance(m, str) or not MONTH_RE.match(m):
            raise ValueError("index.latest 不合")
        return load_json(root / f"data/revenue/{m}.json")
    tryload("rev", rev)
    return out


def strip_gen(o):
    return {k: v for k, v in o.items() if k != "generated_at"} if isinstance(o, dict) else o


def write_if_changed(p: Path, obj: dict) -> bool:
    """generated_at 以外內容相同就不重寫（不產生 commit 噪音）。回是否寫了檔。"""
    if p.exists():
        try:
            if strip_gen(load_json(p)) == strip_gen(obj):
                return False
        except Exception:  # noqa: BLE001
            pass
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(p)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="市場總覽交集表每日建置")
    ap.add_argument("--root", default=str(ROOT), help="repo 根目錄（測試用）")
    ap.add_argument("--src-root", default=os.environ.get("OVERVIEW_SRC_ROOT") or None,
                    help="姊妹 repo 本機 checkout 的上一層目錄（預設走 raw main）")
    a = ap.parse_args(argv)
    root = Path(a.root)
    inp = load_local(root)
    for key, (repo, path) in SRC_FILES.items():
        inp[key] = fetch_remote(repo, path, a.src_root)
    gen = dt.datetime.now(TAIPEI).isoformat(timespec="seconds")
    out = build(inp, gen)
    if out is None:
        print("::error::類股與個股兩層的基準來源（A 產業鏈資金流、a 同步買超）都讀不到，不寫檔")
        return 2
    for layer in ("sectors", "stocks"):
        for s in out[layer]["sources"]:
            if s["status"] in ("fail", "stale", "listed"):
                print(f"::warning::overview 來源 {s['id']}（{s['name']}）{s['status']}：資料日 {s['date']}／基準日 {out[layer]['base_date']}")
    w1 = write_if_changed(root / "data/overview/latest.json", out)
    w2 = write_if_changed(root / f"data/overview/daily/{out['date']}.json", out)
    print(f"overview {out['date']}: 類股交集 {len(out['sectors']['rows'])} 列、個股交集 {len(out['stocks']['rows'])} 列；"
          f"latest {'已寫' if w1 else '內容相同未寫'}、daily {'已寫' if w2 else '內容相同未寫'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
