# src/build_pick2.py — 選股二「追蹤名單」每日建置（2026-10-19 使用者裁定）
#
# 讀：data/diag/diag.json、data/screen/screen.json、taiwan-backtest raw main aisc/universe.json、data/pick2/user.json
# 寫：data/pick2/daily/<date>.json（候選池台股全部的收盤／多空總分／有值項數快照）＋ data/pick2/track.json（追蹤名單）
# 介面契約（taiwan-flow-live-v2 Worker 讀 track.json 推 LINE，欄位名不得自行更改）見 docs/pick2-score.md §7。
#
# 裁定（使用者 2026-10-19）：
#   - 自動選入＝台股、單日多空總分 ≥ 80 且有值項 ≥ 9（不加易經）；**無自動移出**，追蹤到使用者刪除。
#   - 使用者在前端「刪除／加入追蹤」以 GitHub Contents API 追加寫 data/pick2/user.json（append-only，同代號以最後一筆為準）。
#     被刪除（最後一筆 del）的股不再自動選回；手動加入（最後一筆 add）可解除刪除，since＝加入後第一次建置日。
#   - 無回測依據、先上線：畫面標「AI 研判，未經回測，非保證」、列入事後驗證（追蹤紀錄 vs 候選池等權）。
#
# 多空總分＝index.html `pk2Score`（pick2-pure 區段，規格 PK2_SCORE_SPEC／docs/pick2-score.md）的 Python 移植，
# 逐項同口徑、逐位相同（tests/test_pick2_build.py 以 node 抽 index.html 對跑）。四捨五入一律 js_round（JS Math.round
# 的 half-up 語意），**不可用 Python round()**（banker's rounding）。
#
# 失敗處理：universe 讀不到／形狀不對、diag／screen 讀不到、user.json 壞檔、track.json 日期晚於本次 → 不寫檔、exit 非 0。
# 冪等：同 date 重跑結果相同（new_today 只列 since＝本 date 者；since 早於本 date 的追蹤列沿用前次 track.json）。
#
# 用法：
#   python src/build_pick2.py                                  # 正式（universe 走 raw main）
#   python src/build_pick2.py --universe /path/universe.json   # 本機檔注入（離線測試／補跑）；或環境變數 PICK2_UNIVERSE
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
UNIVERSE_URL = "https://raw.githubusercontent.com/shihpc/taiwan-backtest/main/aisc/universe.json"
SPEC = "pick2-score-v1"
MIN_SCORE = 80
MIN_ITEMS = 9
TAIPEI = dt.timezone(dt.timedelta(hours=8))
TW_RE = re.compile(r"^\d{4}[0-9A-Z]{0,2}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 與 index.html PK2_SCORE_SPEC 逐項同序同權重（tests/test_pick2_build.py 比對 k／w 與順序）
SCORE_SPEC = [
    ("ma20", 1), ("ma60", 1), ("r20", 1), ("rs", 1),
    ("f5", 2), ("t5", 2), ("bb", 2), ("mg5", 2), ("hdw", 2),
    ("yoy", 1), ("up", 2), ("buyr", 1),
]


# ---------- JS 語意輔助 ----------

def js_round(x: float) -> float:
    """JS Math.round：最接近的整數，.5 往 +∞（half-up）。x − floor(x) 對 double 是精確的。"""
    f = math.floor(x)
    return float(f + 1) if x - f >= 0.5 else float(f)


def fin(v) -> bool:
    """JS `typeof v === "number" && isFinite(v)`（bool 在 JS 是 boolean，不算 number）"""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def num(v):
    return v if fin(v) else None


def sign(v) -> int:
    return 1 if v > 0 else -1 if v < 0 else 0


def is_one(v) -> bool:   # JS v === 1
    return fin(v) and v == 1


def is_zero(v) -> bool:  # JS v === 0
    return fin(v) and v == 0


# ---------- pk2Score 移植 ----------

def buy_ratio(rt):
    if not isinstance(rt, dict):
        return None
    ks = ["buy", "overweight", "hold", "underweight", "sell"]
    if not any(fin(rt.get(k)) for k in ks):
        return None

    def g(k):
        return rt[k] if fin(rt.get(k)) else 0
    tot = 0
    for k in ks:
        tot = tot + g(k)
    return (g("buy") + g("overweight")) / tot if tot > 0 else None


def score_item(k: str, r: dict):
    v = r.get(k)
    if k in ("ma20", "r20", "rs", "f5", "t5", "hdw", "yoy"):
        return sign(v) if fin(v) else None
    if k == "ma60":
        if fin(v):
            return sign(v)
        a = r.get("a60")
        return 1 if a is True else -1 if a is False else None
    if k == "bb":
        return 1 if is_one(v) else 0 if is_zero(v) else None
    if k == "mg5":
        return (-1 if v > 5 else 0) if fin(v) else None
    if k == "up":
        if not fin(v):
            return None
        u = js_round(v * 1e6) / 1e6
        return 1 if u >= 20 else 0.5 if u >= 10 else 0 if u >= 0 else -1
    if k == "buyr":
        return (1 if v >= 0.7 else 0) if fin(v) else None
    return None


def pk2_score(r: dict) -> tuple[float | None, int]:
    """回 (score, n)；美股一律 (None, 0)。"""
    if r.get("m") == "US":
        return None, 0
    sw = 0
    sws = 0
    n = 0
    for k, w in SCORE_SPEC:
        s = score_item(k, r)
        if s is None:
            continue
        n += 1
        sw += w
        sws += w * s
    if sw <= 0:
        return None, n
    return js_round((50 + 50 * sws / sw) * 10) / 10, n


def tw_row(code: str, d, sc) -> dict:
    """pk2Rows() 中與分數有關的欄位（台股）。d＝diag.stocks[code]、sc＝screen.rows 該檔。
    diag 不涵蓋的台股：前端會退用 aisc 每日表的 r20／above60（本後端不讀該表 → 那兩項缺值，見 docs §7 已知差異）。"""
    d = d if isinstance(d, dict) else None
    sc = sc if isinstance(sc, dict) else None
    r = {"m": "TW", "code": code}
    if d:
        for k in ("c", "r20", "ma20", "ma60", "rs", "f5", "t5", "mg5", "yoy"):
            r[k] = num(d.get(k))
        r["a60"] = None
        r["bb"] = d.get("bb")
        hd = d.get("hd") if isinstance(d.get("hd"), list) else None
        if num(d.get("hdw")) is not None:
            hdw = d["hdw"]
        elif hd and len(hd) >= 2 and num(hd[0]) is not None and num(hd[1]) is not None:
            hdw = hd[0] - hd[1]
        else:
            hdw = None
        r["hdw"] = num(hdw)
    else:
        for k in ("c", "r20", "ma20", "ma60", "rs", "f5", "t5", "mg5", "yoy", "bb", "hdw", "a60"):
            r[k] = None
    px = num(sc.get("px")) if sc else None
    tp = num(sc["tp"].get("median")) if sc and isinstance(sc.get("tp"), dict) else None
    r["up"] = (tp / px - 1) * 100 if (px is not None and px > 0 and tp is not None) else None
    r["buyr"] = buy_ratio(sc.get("rating")) if sc else None
    return r


# ---------- 輸入 ----------

def load_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def fetch_universe(src: str | None):
    """本機檔（--universe／PICK2_UNIVERSE）或 raw main。失敗重試一次（比照 build_diag.get_raw），仍失敗回 None。"""
    if src:
        try:
            return load_json(Path(src))
        except Exception as e:  # noqa: BLE001
            print(f"::error::universe 本機檔讀取失敗：{e}")
            return None
    import requests
    for attempt in (1, 2):
        try:
            r = requests.get(UNIVERSE_URL, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            print(f"  ! universe 讀取失敗（{e}）" + ("，重試一次" if attempt == 1 else ""))
            if attempt == 1:
                time.sleep(3)
    return None


def universe_tw(j) -> list[tuple[str, str]] | None:
    if not isinstance(j, dict) or not isinstance(j.get("TW"), list):
        return None
    out, seen = [], set()
    for x in j["TW"]:
        if not isinstance(x, dict) or not isinstance(x.get("code"), str):
            continue
        c = x["code"].strip().upper()
        if not TW_RE.match(c) or c in seen:
            continue
        seen.add(c)
        out.append((c, x["name"] if isinstance(x.get("name"), str) else ""))
    return out or None


def parse_user(j) -> dict[str, str]:
    """user.json → {code: 最後一筆 act}。形狀不對 raise ValueError（壞檔不可當空，否則已刪除的股會被自動選回）。
    log 依陣列順序（append-only）；個別不合格的筆略過。"""
    if not isinstance(j, dict) or j.get("schema") != 1 or isinstance(j.get("schema"), bool) or not isinstance(j.get("log"), list):
        raise ValueError("user.json 形狀不合（需 {schema:1, log:[...]}）")
    st: dict[str, str] = {}
    for e in j["log"]:
        if not isinstance(e, dict) or e.get("act") not in ("add", "del") or not isinstance(e.get("code"), str):
            continue
        c = e["code"].strip().upper()
        if not TW_RE.match(c):
            continue
        st[c] = e["act"]
    return st


# ---------- 計算 ----------

def r6(x):
    return None if x is None else js_round(x * 1e6) / 1e6


def snap_get(snap: dict, code: str):
    if not snap:
        return None
    return (snap.get("rows") or {}).get(code) or (snap.get("extra") or {}).get(code)


def metrics(code: str, since: str, date: str, snaps: dict[str, dict]) -> dict:
    """entry／last／ret／pool_ret／mdd／days。snaps＝{date: daily 快照}（含本 date）。"""
    dates = sorted(d for d in snaps if since <= d <= date)
    e = snap_get(snaps.get(since), code) or {}
    last = snap_get(snaps.get(date), code) or {}
    ec, lc = num(e.get("c")), num(last.get("c"))
    ret = (lc / ec - 1) if (ec is not None and ec > 0 and lc is not None) else None
    # 候選池等權：since 與 date 兩日快照 rows（候選池，不含 extra）皆有 c 者
    pr = None
    a = (snaps.get(since) or {}).get("rows") or {}
    b = (snaps.get(date) or {}).get("rows") or {}
    rs = []
    for c in sorted(set(a) & set(b)):
        x, y = num(a[c].get("c")), num(b[c].get("c"))
        if x is not None and x > 0 and y is not None:
            rs.append(y / x - 1)
    if rs:
        tot = 0.0
        for v in rs:
            tot += v
        pr = tot / len(rs)
    # 最大回撤：since 以來各快照收盤相對前高（≤ 0）
    mdd, peak = None, None
    for d in dates:
        c = num((snap_get(snaps[d], code) or {}).get("c"))
        if c is None or c <= 0:
            continue
        peak = c if peak is None or c > peak else peak
        dd = c / peak - 1
        mdd = dd if mdd is None or dd < mdd else mdd
    return {"entry_close": ec, "entry_score": num(e.get("score")), "last_close": lc, "last_score": num(last.get("score")),
            "ret": r6(ret), "pool_ret": r6(pr), "mdd": r6(mdd), "days": max(len(dates) - 1, 0)}


def build(date: str, uni: list[tuple[str, str]], diag: dict, screen: dict, user: dict[str, str],
          prev: dict | None, snaps: dict[str, dict], generated_at: str) -> tuple[dict, dict]:
    """回 (daily 快照, track)。snaps＝既有 daily 快照（不含本 date 亦可；本 date 會被覆寫）。"""
    stocks = diag.get("stocks") if isinstance(diag.get("stocks"), dict) else {}
    sc_map = {r["code"]: r for r in (screen.get("rows") or []) if isinstance(r, dict) and isinstance(r.get("code"), str)}

    def one(code, name):
        d = stocks.get(code)
        row = tw_row(code, d, sc_map.get(code))
        s, n = pk2_score(row)
        if not name and isinstance(d, dict) and isinstance(d.get("n"), str):
            name = d["n"]
        return {"name": name, "c": row["c"], "score": s, "n": n}

    rows = {c: one(c, nm) for c, nm in uni}
    deleted = sorted(c for c, a in user.items() if a == "del")
    del_set = set(deleted)

    # 前次追蹤（同 date 重跑時只沿用 since 早於本 date 的列）
    base = {}
    if prev:
        for t in prev.get("tracking") or []:
            if isinstance(t, dict) and isinstance(t.get("code"), str) and isinstance(t.get("since"), str) and t["since"] < date:
                base[t["code"]] = {"code": t["code"], "src": t.get("src") if t.get("src") in ("auto", "manual") else "auto",
                                   "since": t["since"], "name": t.get("name") or ""}
    track = {c: v for c, v in base.items() if c not in del_set}
    for c, a in sorted(user.items()):
        if a == "add" and c not in track:
            track[c] = {"code": c, "src": "manual", "since": date, "name": ""}
    for c, _ in uni:
        r = rows[c]
        if c in track or c in del_set:
            continue
        if r["score"] is not None and r["score"] >= MIN_SCORE and r["n"] >= MIN_ITEMS:
            track[c] = {"code": c, "src": "auto", "since": date, "name": ""}

    extra = {c: one(c, "") for c in sorted(track) if c not in rows}
    daily = {"schema": 1, "date": date, "spec": SPEC, "rows": rows}
    if extra:
        daily["extra"] = extra   # 追蹤中但不在當日候選池的股（換池移出／手動加入池外股）；pool_ret 不計它們
    snaps = dict(snaps)
    snaps[date] = daily

    tracking = []
    for c in sorted(track, key=lambda x: (track[x]["since"], x)):
        t = track[c]
        cur = snap_get(daily, c) or {}
        m = metrics(c, t["since"], date, snaps)
        tracking.append({"code": c, "name": cur.get("name") or t["name"] or c, "src": t["src"], "since": t["since"], **m})
    new_today = [{"code": t["code"], "name": t["name"], "src": t["src"], "score": t["last_score"]}
                 for t in tracking if t["since"] == date]
    tr = {"schema": 1, "date": date, "generated_at": generated_at, "rule": {"min_score": MIN_SCORE, "min_items": MIN_ITEMS},
          "spec": SPEC, "tracking": tracking, "new_today": new_today, "deleted": deleted}
    return daily, tr


def load_snaps(ddir: Path) -> dict[str, dict]:
    out = {}
    if ddir.is_dir():
        for p in sorted(ddir.glob("*.json")):
            if DATE_RE.match(p.stem):
                try:
                    j = load_json(p)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(j, dict) and j.get("date") == p.stem:
                    out[p.stem] = j
    return out


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="選股二追蹤名單每日建置")
    ap.add_argument("--root", default=str(ROOT), help="repo 根目錄（測試用）")
    ap.add_argument("--universe", default=os.environ.get("PICK2_UNIVERSE") or None, help="universe.json 本機檔（預設走 raw main）")
    a = ap.parse_args(argv)
    root = Path(a.root)
    try:
        diag = load_json(root / "data/diag/diag.json")
        screen = load_json(root / "data/screen/screen.json")
    except Exception as e:  # noqa: BLE001
        print(f"::error::diag／screen 讀取失敗：{e}")
        return 2
    date = diag.get("date") if isinstance(diag, dict) else None
    if not isinstance(date, str) or not DATE_RE.match(date) or not isinstance(screen, dict):
        print("::error::diag.date 不合或 screen 形狀不合")
        return 2
    uni = universe_tw(fetch_universe(a.universe))
    if not uni:
        print("::error::universe 讀取失敗或無台股名單，不寫檔")
        return 2
    up = root / "data/pick2/user.json"
    try:
        user = parse_user(load_json(up)) if up.exists() else {}
    except Exception as e:  # noqa: BLE001
        print(f"::error::user.json 壞檔（{e}），不寫檔")
        return 2
    tp = root / "data/pick2/track.json"
    prev = None
    if tp.exists():
        try:
            prev = load_json(tp)
        except Exception as e:  # noqa: BLE001
            print(f"::error::track.json 壞檔（{e}），不寫檔")
            return 2
        if isinstance(prev, dict) and isinstance(prev.get("date"), str) and prev["date"] > date:
            print(f"::error::track.json 日期 {prev['date']} 晚於本次 {date}，不寫檔")
            return 2
    ddir = root / "data/pick2/daily"
    snaps = load_snaps(ddir)
    gen = dt.datetime.now(TAIPEI).isoformat(timespec="seconds")
    daily, tr = build(date, uni, diag, screen, user, prev if isinstance(prev, dict) else None, snaps, gen)
    write_json(ddir / f"{date}.json", daily)
    write_json(tp, tr)
    print(f"pick2 {date}: 候選池台股 {len(daily['rows'])} 檔、追蹤 {len(tr['tracking'])} 檔、"
          f"本日新選入 {len(tr['new_today'])} 檔、已刪除 {len(tr['deleted'])} 檔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
