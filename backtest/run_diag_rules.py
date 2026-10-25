#!/usr/bin/env python3
"""持股診斷燈號回測（規格正本：docs/diag-backtest-spec.md r5 定稿）。

本檔只實作規格 §3.4 Stage 1 之前與 Stage 1 本身，以及不需要報酬值的部分：

  versions  依 §2.1 選版規則重選版本，與附錄 A 逐日比對（附錄 A 為準，不一致只報告）。
  counts    回放附錄 A 的 diag.json 版本 → §2.6 過濾 → node 執行 index.html 燈號原碼
            → 只數筆數與「價格端點是否存在」，與 §2.4／§2.6／§3.4／§3.5／§3.6／§5.4 的
            事前數字比對。**不讀取任何價格值、不算任何報酬。**
  stage1    §3.4 Stage 1：組需求端點集合 → 依決策樹取還原價（TaiwanStockPriceAdj →
            TaiwanStockDividendResult 自行還原 → 皆 <99.0% 才退未還原）→ 寫
            backtest/diag_rules_price_source.json（由 workflow commit 留痕）。

Stage 2（任何報酬計算）刻意**不在本檔**：規格要求它必須等 Stage 1 的決定檔 commit 之後才開工。

資料一律從 git 讀（逐版 `git show <sha>:<path>`，一次只載入一版）：
  --repo        postmkt（diag.json 歷史；需完整歷史，partial clone `--filter=blob:none` 即可）
  --v2-repo     taiwan-flow-live-v2（classify.json 歷史、twse_holidays.json）
  --flows-repo  taiwan-flows（data/meta.json 的 calendar、data/daily/*.json）

FinMind token 只從環境變數 FINMIND_TOKEN 讀，以 `Authorization: Bearer` header 送出（不進 URL）；
所有 log／例外訊息／決定檔字串仍一律先過 mask_secret()（作法同 taiwan-flows src/finmind.py）。
錯誤分類：只有 API 明確回應「無權限／dataset 不可用」才算決策樹的「取不到」；認證失敗、
網路、5xx、個別代號重試後仍失敗一律讓 job 失敗、不寫決定檔（見 classify_api_error）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
PRICE_SOURCE_PATH = HERE / "diag_rules_price_source.json"
DATA_DIR = HERE / "data"          # 還原價原始資料（gzip，commit 進 repo；2026-10-25 使用者裁定 (a)）
EVAL_MJS = HERE / "diag_rules_eval.mjs"
DIAG_PATH = "data/diag/diag.json"
TAIPEI = dt.timezone(dt.timedelta(hours=8))
SPEC = "docs/diag-backtest-spec.md r5"

# ---------------------------------------------------------------- 寫死的規格常數
H_MAIN, H_AUX = 10, 3            # §3.1 期距（交易日）
T0_OFFSETS = (0, 1)              # §3.1 t0=D（主）、t0=D+1（穩健性）
COVERAGE_MIN = 0.99              # §3.4 覆蓋率門檻 99.0%
MIN_TRIG, MIN_DAYS, MIN_NONOVL, MIN_CODES = 300, 20, 3, 30   # §5.4
DAY_MIN = 5                      # §5.1 當日觸發 ≥5 且對照 ≥5
DEFAULT_CALENDAR_END = "2026-10-22"   # §3.6「以 taiwan-flows 到 2026-10-22 為止」

# 附錄 A：選定版本（每個資料日一版，寫死；實作以此為準，不得重新挑）
APPENDIX_A = [
    ("2026-07-17", "4ad0d3b"), ("2026-07-20", "264fa41"), ("2026-07-21", "9c983ac"), ("2026-07-22", "3e7da47"),
    ("2026-07-23", "a3f85bb"), ("2026-07-24", "a8100ee"), ("2026-07-27", "02b151a"), ("2026-07-28", "5a43360"),
    ("2026-07-29", "ae346b4"), ("2026-07-30", "96c7581"), ("2026-07-31", "b34fc5c"), ("2026-08-03", "9f70198"),
    ("2026-08-04", "c4460d5"), ("2026-08-05", "eac05fd"), ("2026-08-06", "07cb551"), ("2026-08-07", "38b77b0"),
    ("2026-08-10", "1184968"), ("2026-08-11", "c30fce4"), ("2026-08-12", "f0bfb55"), ("2026-08-13", "4de7d1d"),
    ("2026-08-14", "4c44610"), ("2026-08-17", "8497211"), ("2026-08-18", "1a6b496"), ("2026-08-19", "f2eb7e5"),
    ("2026-08-20", "94fa5f5"), ("2026-08-21", "50f73bc"), ("2026-08-24", "d0444c6"), ("2026-08-25", "72f5b93"),
    ("2026-08-26", "563b7eb"), ("2026-08-27", "c1139c3"), ("2026-08-28", "e310b97"), ("2026-08-31", "ebbd4c3"),
    ("2026-09-01", "00af1f4"), ("2026-09-02", "0e30e4e"), ("2026-09-03", "1104c29"), ("2026-09-04", "005d641"),
    ("2026-09-07", "fdaaa9b"), ("2026-09-08", "05f126c"), ("2026-09-09", "29b339c"), ("2026-09-10", "952495a"),
    ("2026-09-11", "e965375"), ("2026-09-14", "ff63d03"), ("2026-09-15", "e5da690"), ("2026-09-16", "b8cbcf2"),
    ("2026-09-17", "479ea58"), ("2026-09-18", "1ec7d77"), ("2026-09-21", "7190929"), ("2026-09-22", "a9235d1"),
    ("2026-09-23", "12453fc"), ("2026-09-24", "1649d3d"), ("2026-09-29", "2aab5aa"), ("2026-09-30", "1db7c5d"),
    ("2026-10-01", "7cfacf5"), ("2026-10-02", "ea18b41"), ("2026-10-05", "c090cf7"), ("2026-10-06", "146b5a2"),
    ("2026-10-07", "e7bcd54"), ("2026-10-08", "6152a30"), ("2026-10-12", "aab2281"), ("2026-10-13", "6bb4d0c"),
    ("2026-10-14", "b4afb0c"), ("2026-10-15", "e30e93e"), ("2026-10-16", "4d4310d"), ("2026-10-19", "458e900"),
    ("2026-10-20", "10901b6"), ("2026-10-21", "af38182"), ("2026-10-22", "5ff32ea"),
]

# §2.6 第 2 點：v2 data/classify.json 歷史版本（SHA、commit 時刻 UTC；git log 實查）
CLASSIFY_VERSIONS = [
    ("47cd70e65a38a9a366912fc8749f61c793966de9", "2026-07-01T16:44:09Z"),
    ("9dab5e93db59c18b50fdf7e3eb2c9fdb645f0f89", "2026-07-18T10:48:57Z"),
    ("4ddc69962c4d16439bf207553ccc8840c6833323", "2026-08-01T02:36:04Z"),
    ("790150675187eb58fe030fbee6456865ad786db5", "2026-09-05T02:57:45Z"),
    ("bc2dbe27beb4557836852db67bc90644326d4372", "2026-10-03T03:48:46Z"),
]

# 規格記載的事前數字（只數筆數；用來比對，不一致只報告、不改規格）
SPEC_EXPECTED = {
    "raw_obs": 80400, "excl_non4": 4404, "excl_etf0": 388, "excl_emerging": 8885, "filtered_obs": 66723,
    "total": {"green": 38916, "red": 16737, "yellow": 11070},
    "realizable_days_t10": 57, "realizable_days_t3": 64,
    "main_t10_obs": 56352, "missing_t0h_t10": 99,
    "missing_t0h_t10_by_total": {"red": 32, "green": 46, "yellow": 21},
    "exd_ret_marked_t10": 1713, "exd_ret_marked_by_total": {"red": 378, "green": 1037, "yellow": 298},
    "exd_nonnull_pct": 5.2, "f3_sole_green": 20773, "f3_sole_green_pct": 53.4,
    # id: (觸發, 有觸發日數, null%, T+10 可實現, 代號數, 日數≥5/≥5, 不重疊點(偏移0, min, max；r2 只看觸發≥5), 唯一理由)
    "rules": {
        "P1": (7671, 67, 0.0, 6378, 1052, 57, (6, 5, 6), 5959),
        "P2": (934, 67, 0.0, 769, 523, 49, (5, 4, 6), 567),
        "C1": (319, 65, 0.0, 276, 132, 28, (4, 1, 4), 184),
        "C2": (3384, 66, 11.2, 2971, 668, 57, (6, 5, 6), 2437),
        "S1": (169, 4, 4.1, 169, 128, 4, (1, 0, 1), 49),
        "C3": (1240, 67, 0.0, 1001, 293, 57, (6, 5, 6), None),
        "T1": (334, 29, 4.1, 311, 179, 17, (2, 0, 4), 33),
        "C4": (7076, 67, 0.0, 5615, 889, 57, (6, 5, 6), 224),
        "P3": (19821, 67, 0.0, 15984, 1035, 57, (6, 5, 6), 3320),
        "S2": (42791, 42, 0.0, 38641, 1166, 0, (4, 3, 5), None),
        "F1": (947, 67, 0.0, 809, 97, 57, (6, 5, 6), 798),
        "F2": (0, 0, 1.6, 0, 0, 0, (0, 0, 0), None),
        "F3": (41514, 67, 0.0, 34861, 815, 57, (6, 5, 6), 20773),
        "F4": (5587, 67, 0.0, 4674, 168, 57, (6, 5, 6), 4640),
    },
    # §5.4 事前預期
    "gate": {"insufficient": ["C1", "S1", "T1", "F2"], "na": ["S2"],
             "family": ["P1", "P2", "C2", "C3", "C4", "P3", "F1", "F3", "F4"]},
}
MARKET_LEVEL_RULES = ("S2",)   # §5.1 市場層級、不做橫斷面檢定


# ---------------------------------------------------------------- token 遮罩（鐵律 1）
def mask_secret(msg, token: str | None = None) -> str:
    """把字串裡的 FinMind token 遮掉（同 taiwan-flows src/finmind.py 的兩道作法）。

    ①token 字面量替換（長度 ≥ 8 才做，避免空字串 replace）
    ②`token=` 後綴一律遮到下一個 `&`／空白為止（token 被百分比編碼或未載入時仍成立）。
    """
    s = str(msg)
    tok = (token if token is not None else os.environ.get("FINMIND_TOKEN", "")).strip()
    if len(tok) >= 8:
        s = s.replace(tok, "***")
    return re.sub(r"(token=)[^&\s]+", r"\1***", s)


def mask_obj(obj, token: str | None = None):
    """逐字串遮罩（不可對序列化後的 JSON 文字做 regex：`token=` 規則會吃掉結尾引號）。"""
    if isinstance(obj, str):
        return mask_secret(obj, token)
    if isinstance(obj, dict):
        return {mask_secret(k, token): mask_obj(v, token) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mask_obj(v, token) for v in obj]
    return obj


def log(msg) -> None:
    print(mask_secret(msg), flush=True)


# ---------------------------------------------------------------- git 讀取
class GitRepo:
    def __init__(self, path: str | Path):
        self.path = str(path)

    def _run(self, *args: str) -> bytes:
        r = subprocess.run(["git", "-C", self.path, *args], capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 失敗：{r.stderr.decode(errors='replace').strip()}")
        return r.stdout

    def show(self, ref: str, path: str) -> bytes:
        return self._run("show", f"{ref}:{path}")

    def json(self, ref: str, path: str):
        return json.loads(self.show(ref, path))

    def log_path(self, ref: str, path: str) -> list[tuple[str, str]]:
        out = self._run("log", "--format=%H %cI", ref, "--", path).decode()
        return [tuple(ln.split(" ", 1)) for ln in out.splitlines() if ln.strip()]

    def rev_parse(self, ref: str) -> str:
        return self._run("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()

    def is_shallow(self) -> bool:
        return self._run("rev-parse", "--is-shallow-repository").decode().strip() == "true"


def to_utc(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


# ---------------------------------------------------------------- 交易日曆
def next_trading_day(d: str, calendar: list[str], closed: set[str]) -> str:
    """calendar 內的下一個交易日；d 為日曆末日時，往後找第一個非週末、非休市日。"""
    later = [x for x in calendar if x > d]
    if later:
        return later[0]
    x = dt.date.fromisoformat(d)
    while True:
        x += dt.timedelta(days=1)
        s = x.isoformat()
        if x.weekday() < 5 and s not in closed:
            return s


def select_versions(versions: list[tuple[str, str, str]], calendar: list[str], closed: set[str]) -> dict[str, str]:
    """§2.1 選版規則：對每個資料日 D，取 commit 時間早於「下一個交易日台北 09:00」的最後一版。

    versions：[(sha, commit_iso, data_date)]。回傳 {D: sha}。
    """
    by_day: dict[str, list[tuple[dt.datetime, int, str]]] = {}
    for i, (sha, ciso, d) in enumerate(versions):
        by_day.setdefault(d, []).append((to_utc(ciso), i, sha))
    out = {}
    for d, vs in sorted(by_day.items()):
        nxt = next_trading_day(d, calendar, closed)
        cutoff = dt.datetime.fromisoformat(nxt + "T09:00:00+08:00").astimezone(dt.timezone.utc)
        ok = [v for v in vs if v[0] < cutoff]
        if not ok:
            continue
        # 同一 commit 時刻以 git log 順序（較新者在前、索引較小）為較晚
        ok.sort(key=lambda v: (v[0], -v[1]))
        out[d] = ok[-1][2]
    return out


def compare_appendix(selected: dict[str, str], appendix=APPENDIX_A) -> list[str]:
    """回傳差異說明（空＝與附錄 A 一致）。selected 的 sha 可為完整 SHA。"""
    diffs = []
    app = dict(appendix)
    for d, short in appendix:
        got = selected.get(d)
        if got is None:
            diffs.append(f"{d}: 規則選不到版本（附錄 A＝{short}）")
        elif not got.startswith(short):
            diffs.append(f"{d}: 規則選 {got[:7]}，附錄 A＝{short}")
    for d in sorted(set(selected) - set(app)):
        diffs.append(f"{d}: 規則另選出 {selected[d][:7]}（不在附錄 A；依規格不採用）")
    return diffs


def appendix_hash(appendix=APPENDIX_A) -> str:
    """附錄 A 清單 hash（§7.2 首段用）：sha256("<資料日> <短 SHA>\\n"…)。"""
    return hashlib.sha256("".join(f"{d} {s}\n" for d, s in appendix).encode()).hexdigest()


# ---------------------------------------------------------------- §2.6 過濾
def classify_sha_for(commit_iso: str, versions=CLASSIFY_VERSIONS) -> str:
    """該 diag 版本 commit 時刻之前最後一次 commit 的 classify.json 版本。"""
    t = to_utc(commit_iso)
    cand = [(to_utc(c), s) for s, c in versions if to_utc(c) < t]
    if not cand:
        raise ValueError(f"{commit_iso} 之前沒有 classify 版本")
    return max(cand)[1]


def filter_reason(code: str, cls_map: dict) -> str | None:
    """None＝進樣本；否則回排除原因：non4／etf0／emerging（含不在 classify 或 t 非 twse/tpex）。

    §2.6 第 1 點：4 碼純數字、且不以 0 開頭；第 2 點：classify `t ∈ {twse, tpex}`。
    """
    if not (len(code) == 4 and code.isdigit()):
        return "non4"
    if code.startswith("0"):
        return "etf0"
    ent = cls_map.get(code)
    if not ent:
        return "not_in_classify"
    if ent.get("t") not in ("twse", "tpex"):
        return "emerging"
    return None


def cal_index(calendar: list[str]) -> dict[str, int]:
    return {d: i for i, d in enumerate(calendar)}


def endpoints_for(d: str, cal: list[str], idx: dict[str, int], h: int, off: int):
    """(t0, t0+h)；超出日曆（不可實現）回 None。"""
    i = idx[d] + off
    j = i + h
    if j >= len(cal):
        return None
    return cal[i], cal[j]


def demand_endpoints(codes_by_day: dict[str, list[str]], calendar: list[str],
                     horizons=(H_MAIN, H_AUX), offsets=T0_OFFSETS) -> set[tuple[str, str]]:
    """§3.4 第 2 點需求集合：主樣本（T+10 與 T+3、t0=D 與 t0=D+1）全部觀測所需
    (code, 日期) 價格端點的聯集。只含 t0+h 落在日曆內（可實現）的觀測。"""
    idx = cal_index(calendar)
    need: set[tuple[str, str]] = set()
    for d, codes in codes_by_day.items():
        for h in horizons:
            for off in offsets:
                ep = endpoints_for(d, calendar, idx, h, off)
                if ep is None:
                    continue
                for c in codes:
                    need.add((c, ep[0]))
                    need.add((c, ep[1]))
    return need


def code_ranges(need: set[tuple[str, str]]) -> dict[str, tuple[str, str]]:
    r: dict[str, list[str]] = {}
    for c, d in need:
        lo_hi = r.setdefault(c, [d, d])
        if d < lo_hi[0]:
            lo_hi[0] = d
        if d > lo_hi[1]:
            lo_hi[1] = d
    return {c: (v[0], v[1]) for c, v in r.items()}


# ---------------------------------------------------------------- §3.4 覆蓋率與決策樹
def _pos(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v > 0


def coverage_priceadj(need: set[tuple[str, str]], adj_rows: dict[str, list[dict]]) -> tuple[int, int]:
    """TaiwanStockPriceAdj：端點有還原價＝該代號回應中有該日期且 close 為正數。
    adj_rows：{code: rows}；查詢失敗的代號不在 dict 內（其端點皆無還原價）。"""
    have = set()
    for c, rows in adj_rows.items():
        for r in rows or []:
            if _pos(r.get("close")):
                have.add((c, str(r.get("date", ""))[:10]))
    return len(need & have), len(need)


def dividend_code_adjustable(records: list[dict], lo: str, hi: str) -> bool:
    """§3.4〔r4〕：需求區間 [lo, hi] 內任一筆除權息紀錄缺參考價、或參考價／前收盤
    無法算調整因子（缺值、非正數）→ 該代號不可還原。無紀錄＝可（以未還原價為還原價）。"""
    for r in records or []:
        d = str(r.get("date", ""))[:10]
        if not (lo <= d <= hi):
            continue
        if not (_pos(r.get("reference_price")) and _pos(r.get("before_price"))):
            return False
    return True


def coverage_dividend(need: set[tuple[str, str]], div: dict[str, list[dict]],
                      unadj_close: set[tuple[str, str]]) -> tuple[int, int]:
    """TaiwanStockDividendResult 自行還原（§3.4〔r3〕〔r4〕定義）：端點有還原價須
    ①該端點有未還原 close ②該代號查詢成功（div 內有鍵，含空清單）且查詢區間涵蓋需求區間
    （本實作一律以 [需求首日, 需求末日] 查詢）③該代號區間內紀錄皆可算調整因子。"""
    ranges = code_ranges(need)
    ok_codes = {c for c, (lo, hi) in ranges.items() if c in div and dividend_code_adjustable(div[c], lo, hi)}
    hit = sum(1 for c, d in need if c in ok_codes and (c, d) in unadj_close)
    return hit, len(need)


def decide(adj: dict, divr: dict | None) -> str:
    """§3.4 決策樹。adj／divr：{"obtained": bool, "covered": int, "total": int}。"""
    def passes(x):
        return bool(x and x.get("obtained") and x["total"] and x["covered"] / x["total"] >= COVERAGE_MIN)
    if passes(adj):
        return "TaiwanStockPriceAdj"
    if passes(divr):
        return "TaiwanStockDividendResult"
    return "unadjusted_close"


# ---------------------------------------------------------------- FinMind（Stage 1 專用）
FM_BASE = "https://api.finmindtrade.com/api/v4/data"
PREFLIGHT_DATASET, PREFLIGHT_ID = "TaiwanStockPrice", "2330"   # 認證預檢：本站管線天天在用、方案必含的 dataset

# 錯誤分類（2026-10-25 驗收必修 1；規格 §3.4〔r5〕，使用者 2026-10-25 裁定）：只有 API **明確**表示「無權限／該 dataset 不可用」才算「取不到」，
# 其餘（認證失敗、網路、5xx、無法辨識的回應、個別代號重試後仍失敗）一律讓 job 失敗、不寫決定檔——
# 決定檔 commit 後不可改，誤判成「取不到」會把「未還原」永久寫進去。
# FinMind 錯誤訊息的確切字樣**未實查**（本沙箱無 token）；以下樣式刻意保守：認證樣式先判
# （命中＝job 失敗，安全方向），無權限樣式只認明確字眼，其餘一律歸「暫時／未知」。
_AUTH_RE = re.compile(r"token|unauthori[sz]ed|login|log in|登入|認證|驗證失敗", re.I)
# 只認 FinMind 會員等級類字樣（"Your level is …"／"user level"）；sponsor／upgrade／permission 等寬字刻意不認。
# 也刻意**不**認「dataset 名稱錯誤」類訊息：那更可能是我方程式寫錯，誤判成「取不到」會永久寫死「未還原」。
# 另在 fetch_all 判「取不到」前會以第二檔代號再確認一次（2026-10-25 r5 驗收）。
_UNAVAIL_RE = re.compile(r"your level|user level", re.I)


class FetchError(RuntimeError):
    """暫時性或無法辨識的失敗：重試後仍失敗 → job 失敗、不寫決定檔。"""


class AuthError(FetchError):
    """認證失敗（HTTP 401／403 或訊息指向 token）：不重試、job 失敗。"""


class DatasetUnavailable(FetchError):
    """API 明確回應無權限或該 dataset 不可用＝決策樹的「取不到」。"""


def classify_api_error(http_status: int | None, msg: str) -> type[FetchError]:
    if http_status in (401, 403) or _AUTH_RE.search(msg or ""):
        return AuthError
    if _UNAVAIL_RE.search(msg or ""):
        return DatasetUnavailable
    return FetchError


class FinMind:
    """最小 FinMind client。token 走 `Authorization: Bearer` header（FinMind 官方 SDK
    FinMind/FinMind `FinMind/data/finmind_api.py` 即此寫法，commit 68a1452 實查），不進 URL；
    訊息仍一律 mask_secret（第二道）。"""

    # 限流退避（2026-10-25 r5 驗收 ⑤）：同一請求第 1 次限流等 rate_wait（65 秒，涵蓋每分鐘突發）；
    # 第 2 次起視為每小時額度用完，等到下一個整點＋RATE_HOUR_BUFFER 秒。整個 run 的限流總等待超過
    # rate_budget（預設 75 分；workflow timeout 180 分）就 raise、job 失敗並在訊息中寫明原因。
    # FinMind 每小時額度是滾動窗或整點重置，官方未明寫【未知】；等到整點＋緩衝在兩種情況下都不會短於需要的時間太多。
    RATE_HOUR_BUFFER = 120

    def __init__(self, token: str, session=None, retries: int = 3, rate_wait: float = 65, sleep=time.sleep,
                 rate_budget: float = 75 * 60, now=time.time):
        if not token:
            raise AuthError("找不到環境變數 FINMIND_TOKEN")
        self.token = token
        if session is None:
            import requests
            session = requests.Session()
        self.session, self.retries, self.rate_wait, self.sleep = session, retries, rate_wait, sleep
        self.rate_budget, self.rate_spent, self.now = rate_budget, 0.0, now

    def _rate_backoff(self, n: int, what: str) -> None:
        if n == 1:
            wait = self.rate_wait
        else:
            t = self.now()
            wait = 3600 - (t % 3600) + self.RATE_HOUR_BUFFER
        if self.rate_spent + wait > self.rate_budget:
            raise FetchError(f"{what}：FinMind 限流，累計等待 {self.rate_spent:.0f} 秒＋本次 {wait:.0f} 秒將超過上限 "
                             f"{self.rate_budget:.0f} 秒（疑似每小時額度用完），停止並讓 job 失敗")
        log(f"  ! {what}：FinMind 限流（第 {n} 次），等待 {wait:.0f} 秒"
            + ("（疑似每小時額度用完，等到下一個整點後）" if n > 1 else ""))
        self.rate_spent += wait
        self.sleep(wait)

    def get(self, dataset: str, data_id: str, start: str, end: str) -> list[dict]:
        q = {"dataset": dataset, "data_id": data_id, "start_date": start, "end_date": end}
        hdr = {"Authorization": f"Bearer {self.token}"}
        last = None
        attempt, n_rate = 0, 0
        while attempt < self.retries:
            attempt += 1
            try:
                r = self.session.get(FM_BASE, params=q, headers=hdr, timeout=60)
            except Exception as e:  # noqa: BLE001 — 連線層錯誤＝暫時性，重試
                last = mask_secret(f"{type(e).__name__}: {e}", self.token)
                if attempt < self.retries:
                    self.sleep(3)
                continue
            code = getattr(r, "status_code", 200)
            try:
                j = r.json()
            except Exception:  # noqa: BLE001
                j = None
            msg = mask_secret((j or {}).get("msg") or (j or {}).get("detail") or "", self.token) \
                if isinstance(j, dict) else ""
            status = j.get("status") if isinstance(j, dict) else None
            if code in (402, 429) or status in (402, 429):
                n_rate += 1
                self._rate_backoff(n_rate, f"{dataset} {data_id}")
                attempt -= 1          # 限流不消耗一般重試次數；由限流總等待上限收斂
                continue
            if code >= 500 or j is None or not isinstance(j, dict):
                last = f"HTTP {code}（回應非 JSON 或伺服器錯誤）"
                if attempt < self.retries:
                    self.sleep(3)
                continue
            if code == 200 and status in (200, None) and isinstance(j.get("data", []), list):
                return j.get("data") or []
            kind = classify_api_error(code, msg)
            err = f"{dataset} {data_id}: HTTP {code} status {status}: {msg}"
            if kind is not FetchError:
                raise kind(err)       # 認證／明確無權限：重試無意義
            last = err
            if attempt < self.retries:
                self.sleep(3)
        raise FetchError(f"{dataset} {data_id}: 重試 {self.retries} 次仍失敗：{last}")

    def preflight(self, date: str) -> None:
        """認證預檢：以方案必含的 dataset 打一次；任何失敗或回空都讓 job 失敗。"""
        rows = self.get(PREFLIGHT_DATASET, PREFLIGHT_ID, date, date)
        if not rows:
            raise FetchError(f"認證預檢 {PREFLIGHT_DATASET} {PREFLIGHT_ID} {date} 回空，無法確認 token 與連線正常")


def _confirm_unavailable(fm: FinMind, dataset: str, ranges: dict, first: str, err: Exception) -> dict:
    """第一檔回「無權限」後，用第二檔代號再確認一次；兩檔都回同類才判「取不到」。
    第二檔成功＝矛盾、其他錯誤照拋；只有一檔可查時無法確認＝拋錯（job 失敗）。"""
    others = [c for c in sorted(ranges) if c != first]
    if not others:
        raise FetchError(f"{dataset}：只有 1 檔可查，無法二次確認「不可用」：{err}")
    c2 = others[0]
    lo, hi = ranges[c2]
    try:
        fm.get(dataset, c2, lo, hi)
    except DatasetUnavailable as e2:
        return {"obtained": False, "queried": 2,
                "reason": f"API 明確回應不可用（{first}、{c2} 兩檔皆同）：{mask_secret(e2, fm.token)}"}
    raise FetchError(f"{dataset}：{first} 回「不可用」但 {c2} 查詢成功，前後矛盾：{err}")


def fetch_all(fm: FinMind, dataset: str, ranges: dict[str, tuple[str, str]], cache_dir: Path | None
              ) -> tuple[dict[str, list[dict]], dict]:
    """逐代號查詢，回傳 ({code: rows}, info)。

    - 第一個實際送出的請求回 DatasetUnavailable → 「取不到」（obtained=False），結束。
    - 已有代號成功後才出現 DatasetUnavailable → 前後矛盾，raise（job 失敗）。
    - AuthError／FetchError（含個別代號重試後仍失敗）→ 直接往外拋（job 失敗、不寫決定檔）。
      重跑時已成功的代號由 cache_dir 接續（同一個 runner 內有效）。
    """
    out: dict[str, list[dict]] = {}
    codes = sorted(ranges)
    sent = 0
    for n, c in enumerate(codes, 1):
        lo, hi = ranges[c]
        cf = cache_dir / f"{c}_{lo}_{hi}.json" if cache_dir else None
        if cf and cf.exists():
            out[c] = json.loads(cf.read_text())
            continue
        try:
            rows = fm.get(dataset, c, lo, hi)
        except DatasetUnavailable as e:
            if sent == 0 and not out:
                return {}, _confirm_unavailable(fm, dataset, ranges, c, e)
            raise FetchError(f"{dataset}：已有 {len(out)} 檔成功後才回「不可用」，前後矛盾：{e}") from None
        sent += 1
        out[c] = rows
        if cf:
            cf.parent.mkdir(parents=True, exist_ok=True)
            cf.write_text(json.dumps(rows, ensure_ascii=False))
        if n % 100 == 0:
            log(f"  {dataset}: {n}/{len(codes)}")
    info = {"obtained": True, "queried": len(codes), "codes_nonempty": sum(1 for v in out.values() if v)}
    if out and not info["codes_nonempty"]:
        info["note"] = "全部代號皆回空清單"
    return out, info


# ---------------------------------------------------------------- 樣本組裝（逐版處理）
class Sources:
    def __init__(self, repo: str, ref: str, v2_repo: str, v2_ref: str, flows_repo: str, flows_ref: str,
                 calendar_end: str):
        self.pm, self.pm_ref = GitRepo(repo), ref
        self.v2, self.v2_ref = GitRepo(v2_repo), v2_ref
        self.fl, self.fl_ref = GitRepo(flows_repo), flows_ref
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", calendar_end or ""):
            raise ValueError(f"--calendar-end 格式須為 YYYY-MM-DD：{calendar_end!r}")
        meta = self.fl.json(flows_ref, "data/meta.json")
        self.meta_stocks = meta.get("stocks") or {}
        self.calendar_full = list(meta["calendar"])
        self.calendar = [d for d in self.calendar_full if d <= calendar_end]
        self.calendar_end = calendar_end
        try:
            self.closed = set(self.v2.json(v2_ref, "data/twse_holidays.json").get("closed") or [])
        except Exception:  # noqa: BLE001 — 行事曆只用於日曆末日之後的「下一交易日」
            self.closed = set()
        self._cls: dict[str, dict] = {}
        self._commit_time: dict[str, str] = {}

    def classify_map(self, sha: str) -> dict:
        if sha not in self._cls:
            self._cls[sha] = self.v2.json(sha, "data/classify.json").get("map") or {}
        return self._cls[sha]

    def commit_time(self, sha: str) -> str:
        if sha not in self._commit_time:
            self._commit_time[sha] = self.pm._run("show", "-s", "--format=%cI", sha).decode().strip()
        return self._commit_time[sha]

    def diag(self, sha: str) -> dict:
        return self.pm.json(sha, DIAG_PATH)

    def appendix_full(self) -> list[tuple[str, str]]:
        return [(d, self.pm.rev_parse(s)) for d, s in APPENDIX_A]


def iter_versions(src: Sources):
    """逐版產出 (D, sha, diag dict, classify map)；一次只持有一版。"""
    for d, short in APPENDIX_A:
        sha = src.pm.rev_parse(short)
        j = src.diag(sha)
        if j.get("date") != d:
            raise RuntimeError(f"附錄 A {d} {short} 的 diag.date＝{j.get('date')}，不符")
        cls = src.classify_map(classify_sha_for(src.commit_time(sha)))
        yield d, sha, j, cls


def sample_codes(src: Sources, extra: dict | None = None) -> tuple[dict[str, list[str]], dict]:
    """回 (主樣本代號 by 資料日, 排除計數)。extra 給 dict 時另收集：
    extra["emerging"][D]＝該日 diag 宇宙中的興櫃代號（§2.6 另列子樣本）、
    extra["cls"][D]＝該日對應的 classify map（全市場基準 §3.3 第 3 條用）。"""
    codes_by_day, excl = {}, {"raw": 0, "non4": 0, "etf0": 0, "emerging": 0, "not_in_classify": 0}
    for d, _sha, j, cls in iter_versions(src):
        keep, emg = [], []
        for c in j.get("stocks") or {}:
            excl["raw"] += 1
            why = filter_reason(c, cls)
            if why:
                excl[why] += 1
                if why == "emerging":
                    emg.append(c)
            else:
                keep.append(c)
        codes_by_day[d] = keep
        if extra is not None:
            extra.setdefault("emerging", {})[d] = emg
            extra.setdefault("cls", {})[d] = cls
    return codes_by_day, excl


def benchmark_codes(daily_codes, meta_stocks: dict, cls_map: dict) -> list[str]:
    """§3.3 全市場等權基準成分（價格端點條件留給計算時）：當日 taiwan-flows daily 中，
    代號符合 §2.6 第 1 點、`meta.stocks[code].is_etf == false`、classify t ∈ {twse, tpex}。"""
    out = []
    for c in daily_codes:
        if filter_reason(c, cls_map) is not None:
            continue
        if (meta_stocks.get(c) or {}).get("is_etf") is not False:
            continue
        out.append(c)
    return out


def load_unadjusted(src: Sources, dates: set[str], codes: set[str]) -> dict[str, dict[str, tuple]]:
    """{date: {code: (close, vol)}}——只記需要的代號；用於端點存在性與自行還原條件①。"""
    out = {}
    for d in sorted(dates):
        try:
            j = src.fl.json(src.fl_ref, f"data/daily/{d.replace('-', '')}.json")
        except RuntimeError:
            out[d] = None   # 該日 daily 檔不存在
            continue
        cols = j["cols"]
        ic, iclose, ivol = cols.index("code"), cols.index("close"), cols.index("vol")
        out[d] = {r[ic]: (r[iclose], r[ivol]) for r in j["rows"] if r[ic] in codes}
    return out


def has_close(unadj: dict, code: str, d: str) -> bool:
    """該端點有未還原收盤價＝taiwan-flows 當日有列且 close 為正數。
    close＝0 視同無價格：規格 §3.5 的「t0+10 無列 99 筆」實為 無列 95＋close=0 的 4 筆
    （2026-10-25 重算拆解），close=0 不能當價格用。"""
    day = unadj.get(d)
    return bool(day) and code in day and _pos(day[code][0])


# ---------------------------------------------------------------- 燈號（node 執行 index.html 原碼）
class LightEngine:
    def __init__(self, index_html: Path = ROOT / "index.html"):
        self.p = subprocess.Popen(["node", str(EVAL_MJS), str(index_html)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.rules = json.loads(self.p.stdout.readline())["rules"]

    def run(self, market: dict, stocks: dict) -> dict:
        self.p.stdin.write(json.dumps({"id": 0, "market": market, "stocks": stocks}, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())["res"]

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=30)


def rule_state(rules: list[dict], rec: list, k: int):
    """第 k 條規則的分組：1 觸發／0 對照／None 資料不足。C3 用閘後值（§5.1）。"""
    raw = rec[1 + k]
    if raw is None:
        return None
    if rules[k]["addon"]:
        return 1 if rec[-1] == 1 else 0
    return raw


def recount(obs: list[dict], rules: list[dict], days: list[str], calendar: list[str], h: int = H_MAIN) -> dict:
    """§2.4／§5.4 的「只數筆數」統計。obs 每筆：{d, code, rec, price_ok(可選)}。
    回傳每條規則的各欄位，以及總燈分布等。不讀任何價格值。"""
    idx = cal_index(calendar)
    realizable = [d for d in days if endpoints_for(d, calendar, idx, h, 0) is not None]
    rset = set(realizable)
    pos = {d: i for i, d in enumerate(realizable)}
    n = len(obs)
    res = {"n": n, "realizable_days": len(realizable), "rules": {}}
    tot = {"red": 0, "green": 0, "yellow": 0}
    for o in obs:
        tot[o["rec"][0]] += 1
    res["total"] = tot
    for k, r in enumerate(rules):
        trig = nul = 0
        trig_days = set()
        real_trig = 0
        codes = set()
        per_day = {}     # realizable 日 → [觸發, 對照]
        per_day_px = {}  # 同上，但只計 price_ok 者（§5.4 用）
        codes_px = set()
        trig_px = 0
        sole = 0
        for o in obs:
            st = rule_state(rules, o["rec"], k)
            if st is None:
                nul += 1
                continue
            if st == 1:
                trig += 1
                trig_days.add(o["d"])
            if o["d"] in rset:
                c = per_day.setdefault(o["d"], [0, 0])
                c[0 if st == 1 else 1] += 1
                if st == 1:
                    real_trig += 1
                    codes.add(o["code"])
                if o.get("price_ok", True):
                    cp = per_day_px.setdefault(o["d"], [0, 0])
                    cp[0 if st == 1 else 1] += 1
                    if st == 1:
                        trig_px += 1
                        codes_px.add(o["code"])
            if st == 1:
                sole += _is_sole(rules, o["rec"], k)

        def ok_day(c):
            return c[0] >= DAY_MIN and c[1] >= DAY_MIN

        def nonovl(pd_, need_ctrl):
            vals = []
            for off in range(h):
                ds = realizable[off::h]
                vals.append(sum(1 for d in ds if (pd_.get(d, [0, 0])[0] >= DAY_MIN and
                                                  (not need_ctrl or pd_.get(d, [0, 0])[1] >= DAY_MIN))))
            return (vals[0], min(vals), max(vals)) if vals else (0, 0, 0)

        res["rules"][r["id"]] = {
            "trig": trig, "pct": round(100 * trig / n, 2) if n else 0.0, "trig_days": len(trig_days),
            "null_pct": round(100 * nul / n, 1) if n else 0.0, "real_trig": real_trig, "codes": len(codes),
            "days55": sum(1 for c in per_day.values() if ok_day(c)),
            "nonovl_r2": nonovl(per_day, False), "nonovl_r3": nonovl(per_day, True),
            "sole": None if (r["col"] == "green" and (r["addon"] or r["dim"] == "系統")) else sole,
            # §5.4（扣除 §3.5 剔除後；此處剔除依未還原價端點是否存在）
            "gate": {"trig": trig_px, "days": sum(1 for c in per_day_px.values() if ok_day(c)),
                     "nonovl0": nonovl(per_day_px, True)[0], "codes": len(codes_px)},
        }
        _ = pos
    return res


def _is_sole(rules, rec, k) -> int:
    """該規則是總燈紅（或綠）的唯一理由。紅：總燈紅且唯一亮的紅燈規則；
    綠：總燈綠且唯一亮的非系統面綠燈規則（C3 依閘後值、計入集合）。"""
    r = rules[k]
    on = [rule_state(rules, rec, i) == 1 for i in range(len(rules))]
    if r["col"] == "red":
        return int(rec[0] == "red" and sum(1 for i, x in enumerate(rules) if on[i] and x["col"] == "red") == 1)
    if r["dim"] == "系統" or r["addon"]:
        return 0
    return int(rec[0] == "green" and
               sum(1 for i, x in enumerate(rules) if on[i] and x["col"] == "green" and x["dim"] != "系統") == 1)


def gate_verdict(g: dict, rid: str) -> str:
    if rid in MARKET_LEVEL_RULES:
        return "na"
    ok = g["trig"] >= MIN_TRIG and g["days"] >= MIN_DAYS and g["nonovl0"] >= MIN_NONOVL and g["codes"] >= MIN_CODES
    return "family" if ok else "insufficient"


def cmd_counts(args) -> int:
    src = make_sources(args)
    eng = LightEngine(Path(args.index))
    obs, excl = [], {"raw": 0, "non4": 0, "etf0": 0, "emerging": 0, "not_in_classify": 0}
    exd_nonnull = 0
    exd_by = {}   # (d, code) -> exd
    morning_lag = []
    days = [d for d, _ in APPENDIX_A]
    try:
        for d, sha, j, cls in iter_versions(src):
            keep = {}
            for c, s in (j.get("stocks") or {}).items():
                excl["raw"] += 1
                why = filter_reason(c, cls)
                if why:
                    excl[why] += 1
                else:
                    keep[c] = s
            m = j.get("market") or {}
            if m.get("morning_date") != d:
                morning_lag.append((d, m.get("morning_date")))
            res = eng.run(m, keep)
            for c, s in keep.items():
                obs.append({"d": d, "code": c, "rec": res[c]})
                if s.get("exd") is not None:
                    exd_nonnull += 1
                    exd_by[(d, c)] = s["exd"]
            log(f"  {d} {sha[:7]}：保留 {len(keep)}")
            del j
    finally:
        eng.close()
    cal, idx = src.calendar, cal_index(src.calendar)
    # 價格端點存在性（只看有無、不讀值）
    codes = {o["code"] for o in obs}
    need_dates = set()
    for d in days:
        for h in (H_MAIN, H_AUX):
            for off in T0_OFFSETS:
                ep = endpoints_for(d, cal, idx, h, off)
                if ep:
                    need_dates.update(ep)
    unadj = load_unadjusted(src, need_dates, codes)
    miss_by = {"red": 0, "green": 0, "yellow": 0}
    miss_kind = {"row_absent": 0, "close_null": 0, "close_nonpos": 0, "vol0_with_close": 0, "t0_no_price": 0}
    exd_marked = {"red": 0, "green": 0, "yellow": 0}
    main_n = 0
    for o in obs:
        ep = endpoints_for(o["d"], cal, idx, H_MAIN, 0)
        if ep is None:
            o["price_ok"] = False
            continue
        main_n += 1
        t0, t1 = ep
        ok0, ok1 = has_close(unadj, o["code"], t0), has_close(unadj, o["code"], t1)
        o["price_ok"] = ok0 and ok1
        day1 = unadj.get(t1) or {}
        if not ok1:
            miss_by[o["rec"][0]] += 1
        if o["code"] not in day1:
            miss_kind["row_absent"] += 1
        elif day1[o["code"]][0] is None:
            miss_kind["close_null"] += 1
        elif not _pos(day1[o["code"]][0]):
            miss_kind["close_nonpos"] += 1
        elif day1[o["code"]][1] == 0:
            miss_kind["vol0_with_close"] += 1
        if not ok0:
            miss_kind["t0_no_price"] += 1
        exd = exd_by.get((o["d"], o["code"]))
        if exd and t0 < exd <= t1:
            exd_marked[o["rec"][0]] += 1
    rules = eng.rules
    rc = recount(obs, rules, days, cal, H_MAIN)
    t3_days = sum(1 for d in days if endpoints_for(d, cal, idx, H_AUX, 0) is not None)
    report = {
        "excl": excl, "filtered": len(obs), "total": rc["total"], "realizable_days_t10": rc["realizable_days"],
        "realizable_days_t3": t3_days, "main_t10_obs": main_n, "missing_t0h": miss_kind, "missing_by_total": miss_by,
        "exd_nonnull_pct": round(100 * exd_nonnull / len(obs), 1) if obs else 0.0, "exd_ret_marked": exd_marked,
        "morning_date_mismatch": morning_lag, "rules": rc["rules"],
    }
    f3 = rc["rules"]["F3"]["sole"]
    report["f3_sole_green"] = f3
    report["f3_sole_green_pct"] = round(100 * f3 / rc["total"]["green"], 1) if rc["total"]["green"] else 0.0
    diffs = compare_counts(report)
    out = Path(args.out) if args.out else CACHE / "counts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"report": report, "diffs": diffs}, ensure_ascii=False, indent=1))
    log(f"寫入 {out}")
    log("與規格事前數字比對：" + ("全部一致" if not diffs else f"{len(diffs)} 項不同"))
    for x in diffs:
        log("  ≠ " + x)
    return 0


def compare_counts(rep: dict, exp=SPEC_EXPECTED) -> list[str]:
    diffs = []

    def chk(name, got, want):
        if got != want:
            diffs.append(f"{name}: 實算 {got}，規格 {want}")
    e = rep["excl"]
    chk("原始筆數", e["raw"], exp["raw_obs"])
    chk("排除 非4碼", e["non4"], exp["excl_non4"])
    chk("排除 0開頭", e["etf0"], exp["excl_etf0"])
    chk("排除 興櫃(含不在classify)", e["emerging"] + e["not_in_classify"], exp["excl_emerging"])
    chk("過濾後筆數", rep["filtered"], exp["filtered_obs"])
    chk("總燈分布", rep["total"], exp["total"])
    chk("T+10 可實現日數", rep["realizable_days_t10"], exp["realizable_days_t10"])
    chk("T+3 可實現日數", rep["realizable_days_t3"], exp["realizable_days_t3"])
    chk("T+10 主樣本筆數", rep["main_t10_obs"], exp["main_t10_obs"])
    mk = rep["missing_t0h"]
    chk("t0+10 無價格筆數（無列＋close 非正）", mk["row_absent"] + mk["close_null"] + mk["close_nonpos"],
        exp["missing_t0h_t10"])
    chk("t0+10 無列 依總燈", rep["missing_by_total"], exp["missing_t0h_t10_by_total"])
    chk("報酬側 exd 標記", sum(rep["exd_ret_marked"].values()), exp["exd_ret_marked_t10"])
    chk("報酬側 exd 標記 依總燈", rep["exd_ret_marked"], exp["exd_ret_marked_by_total"])
    chk("exd 非 null%", rep["exd_nonnull_pct"], exp["exd_nonnull_pct"])
    chk("F3 唯一綠燈理由", rep["f3_sole_green"], exp["f3_sole_green"])
    chk("F3 唯一綠燈理由%", rep["f3_sole_green_pct"], exp["f3_sole_green_pct"])
    for rid, w in exp["rules"].items():
        g = rep["rules"][rid]
        got = (g["trig"], g["trig_days"], g["null_pct"], g["real_trig"], g["codes"], g["days55"],
               tuple(g["nonovl_r2"]), g["sole"])
        names = ("觸發", "有觸發日數", "null%", "T+10可實現", "代號數", "日數≥5/≥5", "不重疊點(r2)", "唯一理由")
        for nm, a, b in zip(names, got, w):
            if b is None and nm == "唯一理由":
                continue   # 規格表記「—」（C3／S2 結構上不可能、F2 零觸發）
            if a != b:
                diffs.append(f"{rid} {nm}: 實算 {a}，規格 {b}")
    for kind, ids in exp["gate"].items():
        for rid in ids:
            v = gate_verdict(rep["rules"][rid]["gate"], rid)
            if v != kind:
                diffs.append(f"§5.4 預期 {rid}: 實算 {v}，規格 {kind}（{rep['rules'][rid]['gate']}）")
    return diffs


# ---------------------------------------------------------------- 子命令
def make_sources(args) -> Sources:
    return Sources(args.repo, args.ref, args.v2_repo, args.v2_ref, args.flows_repo, args.flows_ref, args.calendar_end)


def cmd_versions(args) -> int:
    src = make_sources(args)
    if src.pm.is_shallow():
        log("::warning::postmkt checkout 是 shallow，版本清單可能不完整")
    vers = []
    for sha, ciso in src.pm.log_path(args.ref, DIAG_PATH):
        head = src.pm.show(sha, DIAG_PATH)[:400].decode(errors="replace")
        m = re.search(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', head)
        vers.append((sha, ciso, m.group(1) if m else ""))
    sel = select_versions(vers, src.calendar_full, src.closed)
    diffs = compare_appendix(sel)
    log(f"diag.json 版本 {len(vers)} 個、資料日 {len({v[2] for v in vers})} 個；規則選出 {len(sel)} 日")
    log("附錄 A 比對：" + ("一致" if not diffs else f"{len(diffs)} 項差異"))
    for x in diffs:
        log("  ≠ " + x)
    log(f"附錄 A hash＝{appendix_hash()}")
    return 0 if not [x for x in diffs if "不在附錄 A" not in x] else 1


# 結構預留（等使用者裁定，2026-10-25）：
#  (a) 還原價原始資料的保存方式：目前只有 "artifact"（寫到 backtest/cache/stage1/，由 workflow 上傳成
#      90 天 artifact）。若裁定「壓縮後 commit 進 repo」，在 persist_raw() 加一個模式即可，決定檔格式不變。
#  (b) 是否同批抓全市場等權基準（約 1,817 檔）與興櫃代號的還原價（不計入覆蓋率）：目前只有 "none"。
#      extra_ranges() 回傳額外代號的查詢區間；有值時用「採用的那個來源」另抓、另存，不進 need／覆蓋率。
# 2026-10-25 使用者裁定：(a) 預設 "commit"＝gzip 後寫 backtest/data/ 並由 workflow commit（artifact 另保留）；
# (b) 預設 "benchmark_emerging"＝同批抓全市場等權基準（§3.3）與興櫃代號（§2.6 子樣本）的還原價，
#     用採用的那個來源、另存，**不計入需求集合與覆蓋率**。
PERSIST_MODES = ("commit", "artifact")
EXTRA_UNIVERSE_MODES = ("benchmark_emerging", "none")


def persist_raw(name: str, obj, mode: str = "commit") -> dict:
    if mode == "artifact":
        return _dump(CACHE / "stage1" / f"{name}.json", obj)
    if mode == "commit":
        return _dump_gz(DATA_DIR / f"diag_rules_{name}.json.gz", obj)
    raise ValueError(f"未知保存方式 {mode}")


def _dump_gz(p: Path, obj) -> dict:
    """可重現的 gzip（mtime=0、排序鍵）：同內容 → 同位元組 → 同 sha256。"""
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    gz = gzip.compress(raw, compresslevel=9, mtime=0)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gz)
    try:
        name = str(p.relative_to(ROOT))
    except ValueError:
        name = str(p)
    return {"file": name, "sha256": hashlib.sha256(gz).hexdigest(), "bytes": len(gz),
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "raw_bytes": len(raw)}


def extra_endpoints(bench_by_day: dict[str, list[str]], emerging_by_day: dict[str, list[str]],
                    calendar: list[str]) -> set[tuple[str, str]]:
    """額外代號的端點：與主樣本同一組期距與進場點（T+10／T+3 × t0=D／D+1）。"""
    days = set(bench_by_day) | set(emerging_by_day)
    merged = {d: sorted(set(bench_by_day.get(d, [])) | set(emerging_by_day.get(d, []))) for d in days}
    return demand_endpoints(merged, calendar)


def extra_ranges(extra_need: set[tuple[str, str]], need: set[tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """只抓主需求集合沒涵蓋的端點；區間＝這些端點各代號的 [首日, 末日]。"""
    return code_ranges(extra_need - need)


def collect_extra(src, mode: str, extra_info: dict, need: set[tuple[str, str]]) -> tuple[dict, dict]:
    """回 (extra ranges, 摘要)。"""
    if mode == "none":
        return {}, {"mode": "none"}
    if mode != "benchmark_emerging":
        raise ValueError(f"未知額外代號範圍 {mode}")
    bench = {}
    for d in extra_info.get("cls", {}):
        try:
            j = src.fl.json(src.fl_ref, f"data/daily/{d.replace('-', '')}.json")
        except RuntimeError:
            bench[d] = []
            continue
        ic = j["cols"].index("code")
        bench[d] = benchmark_codes((r[ic] for r in j["rows"]), src.meta_stocks, extra_info["cls"][d])
    emg = extra_info.get("emerging", {})
    xneed = extra_endpoints(bench, emg, src.calendar)
    rng = extra_ranges(xneed, need)
    summ = {"mode": mode, "benchmark_codes": len({c for v in bench.values() for c in v}),
            "benchmark_codes_per_day_max": max((len(v) for v in bench.values()), default=0),
            "emerging_codes": len({c for v in emg.values() for c in v}),
            "extra_endpoints": len(xneed - need), "extra_codes": len(rng)}
    return rng, summ


def demand_hash(need: set[tuple[str, str]]) -> str:
    """需求端點集合 hash：sha256("<code>,<YYYY-MM-DD>\\n"… 依排序)。Stage 2 可據此核對同一集合。"""
    h = hashlib.sha256()
    for c, d in sorted(need):
        h.update(f"{c},{d}\n".encode())
    return h.hexdigest()


def _fields(rows_by_code: dict) -> list[str]:
    return sorted({k for rows in rows_by_code.values() for r in rows[:1] for k in r})


def stage1_core(fm: FinMind, need: set[tuple[str, str]], unadj_close: set[tuple[str, str]],
                preflight_date: str, stage_dir: Path | None, persist: str = "commit",
                extra: dict | None = None) -> dict:
    """§3.4 決策樹本體。任何 FetchError（含 AuthError）往外拋＝不產生決定。
    兩個來源不論採用與否，只要有抓到就保存原始資料備查。"""
    ranges = code_ranges(need)
    log(f"認證預檢 {PREFLIGHT_DATASET} {PREFLIGHT_ID} {preflight_date} …")
    fm.preflight(preflight_date)
    files = {}
    log("試 TaiwanStockPriceAdj …")
    adj_rows, adj_info = fetch_all(fm, "TaiwanStockPriceAdj", ranges, stage_dir and stage_dir / "TaiwanStockPriceAdj")
    cov, tot = coverage_priceadj(need, adj_rows)
    adj = dict(adj_info, covered=cov, total=tot, coverage=round(cov / tot, 6) if tot else 0.0)
    if adj_rows:
        adj["fields"] = _fields(adj_rows)
        files["TaiwanStockPriceAdj"] = persist_raw("price_adj", adj_rows, persist)
    log(f"  PriceAdj：取得={adj['obtained']} 覆蓋 {cov}/{tot}")
    divr = None
    decision = decide(adj, None)
    if decision != "TaiwanStockPriceAdj":
        log("試 TaiwanStockDividendResult 自行還原 …")
        div_rows, div_info = fetch_all(fm, "TaiwanStockDividendResult", ranges,
                                       stage_dir and stage_dir / "TaiwanStockDividendResult")
        if div_info["obtained"] and not div_info["codes_nonempty"]:
            # 期間涵蓋除權息旺季，全部回空與「無權限但回空」無法區分；不得當成 100% 可還原
            raise FetchError("TaiwanStockDividendResult 全部代號回空清單，無法與無權限區分，拒絕下決定")
        cov2, tot2 = coverage_dividend(need, div_rows, unadj_close)
        divr = dict(div_info, covered=cov2, total=tot2, coverage=round(cov2 / tot2, 6) if tot2 else 0.0)
        divr["codes_unadjustable"] = sum(1 for c, (lo, hi) in ranges.items()
                                         if c in div_rows and not dividend_code_adjustable(div_rows[c], lo, hi))
        if div_rows:
            divr["fields"] = _fields(div_rows)
            files["TaiwanStockDividendResult"] = persist_raw("dividend_result", div_rows, persist)
        log(f"  DividendResult：取得={divr['obtained']} 覆蓋 {cov2}/{tot2}")
        decision = decide(adj, divr)
    if extra:
        ds = {"TaiwanStockPriceAdj": "TaiwanStockPriceAdj",
              "TaiwanStockDividendResult": "TaiwanStockDividendResult"}.get(decision)
        if ds:
            log(f"另抓額外代號 {len(extra)} 檔（{ds}，不計入覆蓋率）…")
            rows, xi = fetch_all(fm, ds, extra, stage_dir and stage_dir / f"extra_{ds}")
            if not xi["obtained"]:
                # 主需求才剛用同一來源抓成功；額外代號回「不可用」是矛盾，不寫空檔、不標 adopted
                raise FetchError(f"額外代號以 {ds} 抓取時回「不可用」，與主需求矛盾：{xi.get('reason')}")
            files["extra"] = persist_raw("extra_price_adj" if ds == "TaiwanStockPriceAdj" else "extra_dividend_result",
                                         rows, persist)
            files["extra"].update(dataset=ds, codes=len(rows))
    for k, v in files.items():
        v["adopted"] = (k == decision) or (k == "extra")
    return {"adj": adj, "divr": divr, "decision": decision, "files": files}


def cmd_stage1(args) -> int:
    if args.dry_run:
        return stage1_dry(args)
    if PRICE_SOURCE_PATH.exists() and not args.allow_overwrite:
        log(f"::error::{PRICE_SOURCE_PATH.name} 已存在；價格口徑決定不得在看過報酬後變更（§3.4）。"
            "確定要重做請明確指定 --allow-overwrite")
        return 2
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    if not token:
        log("::error::找不到環境變數 FINMIND_TOKEN")
        return 2
    src = make_sources(args)
    xinfo: dict = {}
    codes_by_day, excl = sample_codes(src, xinfo)
    need = demand_endpoints(codes_by_day, src.calendar)
    ranges = code_ranges(need)
    log(f"需求端點 {len(need)}、代號 {len(ranges)}、日曆 {src.calendar[0]}～{src.calendar[-1]}")
    unadj = load_unadjusted(src, {d for _, d in need}, set(ranges))
    unadj_close = {(c, d) for c, d in need if has_close(unadj, c, d)}
    xranges, xsumm = collect_extra(src, args.extra_universe, xinfo, need)
    log(f"額外代號（不計入覆蓋率）：{xsumm}")
    try:
        core = stage1_core(FinMind(token), need, unadj_close, src.calendar[-1], CACHE / "stage1",
                           args.persist, xranges)
    except FetchError as e:
        log(f"::error::{type(e).__name__}: {e}（未寫決定檔）")
        return 1
    decision = core["decision"]
    doc = {
        "schema": 1, "spec": SPEC, "stage": 1,
        "generated_at": dt.datetime.now(TAIPEI).isoformat(timespec="seconds"),
        "appendix_a_hash": appendix_hash(), "appendix_a_days": len(APPENDIX_A),
        "sources": {"postmkt": src.pm.rev_parse(args.ref), "taiwan_flow_live_v2": src.v2.rev_parse(args.v2_ref),
                    "taiwan_flows": src.fl.rev_parse(args.flows_ref)},
        "calendar_end": src.calendar_end, "calendar_span": [src.calendar[0], src.calendar[-1]],
        "sample": {"filtered_obs": sum(len(v) for v in codes_by_day.values()), "excluded": excl},
        "demand": {"endpoints": len(need), "codes": len(ranges), "with_unadjusted_close": len(unadj_close),
                   "sha256": demand_hash(need), "horizons": [H_MAIN, H_AUX], "t0_offsets": list(T0_OFFSETS)},
        "coverage_min": COVERAGE_MIN,
        "TaiwanStockPriceAdj": core["adj"],
        "TaiwanStockDividendResult": core["divr"] if core["divr"] is not None else {
            "attempted": False, "reason": "PriceAdj 已達門檻，依決策樹結束"},
        "decision": decision,
        "report_first_line": "未還原除權息" if decision == "unadjusted_close" else None,
        "price_data": {"persist": args.persist, "extra_universe": xsumm, "files": core["files"]},
    }
    write_decision(doc, token)
    log(f"決定：{decision}；寫入 {PRICE_SOURCE_PATH}")
    return 0


def write_decision(doc: dict, token: str | None = None, path: Path | None = None) -> Path:
    path = path or PRICE_SOURCE_PATH
    text = json.dumps(mask_obj(doc, token), ensure_ascii=False, indent=1)
    json.loads(text)   # 寫出前自我檢查：必須是合法 JSON
    path.write_text(text + "\n", encoding="utf-8")
    return path


def stage1_dry(args) -> int:
    """免 token：只組需求端點並報告數量與未還原 close 存在數，不打 FinMind、不寫決定檔。"""
    src = make_sources(args)
    xinfo: dict = {}
    codes_by_day, excl = sample_codes(src, xinfo)
    need = demand_endpoints(codes_by_day, src.calendar)
    ranges = code_ranges(need)
    unadj = load_unadjusted(src, {d for _, d in need}, set(ranges))
    have = sum(1 for c, d in need if has_close(unadj, c, d))
    xranges, xsumm = collect_extra(src, args.extra_universe, xinfo, need)
    log("額外代號（不計入覆蓋率）：" + json.dumps(xsumm, ensure_ascii=False))
    log(json.dumps({"filtered_obs": sum(len(v) for v in codes_by_day.values()), "excluded": excl,
                    "demand_sha256": demand_hash(need),
                    "calendar_span": [src.calendar[0], src.calendar[-1]], "endpoints": len(need),
                    "codes": len(ranges), "with_unadjusted_close": have}, ensure_ascii=False))
    return 0


def _dump(p: Path, obj) -> dict:
    p.parent.mkdir(parents=True, exist_ok=True)
    b = json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()
    p.write_bytes(b)
    try:
        name = str(p.relative_to(ROOT))
    except ValueError:
        name = str(p)
    return {"file": name, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("versions", "counts", "stage1"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=str(ROOT), help="postmkt git（需完整歷史）")
        p.add_argument("--ref", default="HEAD")
        p.add_argument("--v2-repo", required=True)
        p.add_argument("--v2-ref", default="origin/main")
        p.add_argument("--flows-repo", required=True)
        p.add_argument("--flows-ref", default="origin/main")
        p.add_argument("--calendar-end", default=DEFAULT_CALENDAR_END,
                       help="價格日曆截止日（§3.6；預設 2026-10-22，與規格事前數字同口徑）")
        if name == "counts":
            p.add_argument("--index", default=str(ROOT / "index.html"))
            p.add_argument("--out")
        if name == "stage1":
            p.add_argument("--allow-overwrite", action="store_true")
            p.add_argument("--dry-run", action="store_true", help="免 token：只算需求端點，不打 FinMind、不寫檔")
            p.add_argument("--persist", choices=PERSIST_MODES, default="commit")
            p.add_argument("--extra-universe", choices=EXTRA_UNIVERSE_MODES, default="benchmark_emerging")
    args = ap.parse_args(argv)
    try:
        return {"versions": cmd_versions, "counts": cmd_counts, "stage1": cmd_stage1}[args.cmd](args)
    except Exception as e:  # noqa: BLE001 — 例外訊息也要遮罩，不讓 traceback 帶出 token
        log(f"::error::{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
