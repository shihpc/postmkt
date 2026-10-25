#!/usr/bin/env python3
# tests/test_diag_backtest.py — 持股診斷燈號回測（docs/diag-backtest-spec.md r4）Stage 1 之前與 Stage 1 的離線測試。
# 涵蓋：選版規則（§2.1）、附錄 A、classify 版本對應與宇宙過濾（§2.6）、需求端點（§3.4）、
# 覆蓋率與決策樹三分支（§3.4）、token 遮罩（鐵律 1）、node 燈號執行器、筆數統計與 §5.4 門檻。
# 全部用假資料，免網路、免 token（node 執行器測試需要 node）。
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("run_diag_rules", ROOT / "backtest" / "run_diag_rules.py")
R = importlib.util.module_from_spec(_spec)
sys.modules["run_diag_rules"] = R
_spec.loader.exec_module(R)

FAKE_TOKEN = "fmTOKEN_abcdefghijklmnop0123456789"


# ---------------------------------------------------------------- 選版規則 §2.1
CAL = ["2026-09-23", "2026-09-24", "2026-09-29", "2026-09-30"]
CLOSED = {"2026-09-25", "2026-09-28", "2026-10-01"}


def test_select_last_before_next_trading_day_0900_taipei():
    vs = [  # git log 順序：新 → 舊
        ("late", "2026-09-29T01:00:00Z", "2026-09-24"),   # = 09-29 09:00 台北，不早於 → 排除
        ("v3", "2026-09-29T00:59:59Z", "2026-09-24"),     # 跨休市日，仍早於 09-29 09:00
        ("v2", "2026-09-25T01:00:00Z", "2026-09-24"),
        ("v1", "2026-09-24T13:05:00Z", "2026-09-24"),
        ("b", "2026-09-23T18:00:00Z", "2026-09-23"),
        ("a", "2026-09-23T13:00:00Z", "2026-09-23"),
    ]
    sel = R.select_versions(vs, CAL, CLOSED)
    assert sel == {"2026-09-24": "v3", "2026-09-23": "b"}


def test_select_uses_commit_time_not_list_order_and_skips_day_without_candidate():
    vs = [("old", "2026-09-23T10:00:00Z", "2026-09-23"), ("new", "2026-09-23T20:00:00Z", "2026-09-23"),
          ("toolate", "2026-09-25T02:00:00Z", "2026-09-29")]   # 09-29 的下一交易日 09-30 09:00 之前 → 可選
    sel = R.select_versions(vs, CAL, CLOSED)
    assert sel["2026-09-23"] == "new"
    assert sel["2026-09-29"] == "toolate"
    vs2 = [("x", "2026-09-30T02:00:00Z", "2026-09-29")]       # 晚於 09-30 09:00 台北 → 該日無版
    assert R.select_versions(vs2, CAL, CLOSED) == {}


def test_next_trading_day_beyond_calendar_skips_weekend_and_holiday():
    assert R.next_trading_day("2026-09-24", CAL, CLOSED) == "2026-09-29"
    assert R.next_trading_day("2026-09-30", CAL, CLOSED) == "2026-10-02"    # 10-01 休市
    assert R.next_trading_day("2026-10-02", ["2026-10-02"], set()) == "2026-10-05"  # 週五 → 週一


def test_appendix_a_shape_and_compare():
    assert len(R.APPENDIX_A) == 67
    days = [d for d, _ in R.APPENDIX_A]
    assert days == sorted(days) and len(set(days)) == 67
    assert R.APPENDIX_A[0] == ("2026-07-17", "4ad0d3b") and R.APPENDIX_A[-1] == ("2026-10-22", "5ff32ea")
    full = {d: s + "0" * 33 for d, s in R.APPENDIX_A}
    assert R.compare_appendix(full) == []
    bad = dict(full)
    bad["2026-08-17"] = "deadbee" + "0" * 33
    del bad["2026-10-22"]
    bad["2026-10-23"] = "f" * 40
    diffs = R.compare_appendix(bad)
    assert any("2026-08-17" in x for x in diffs) and any("2026-10-22" in x for x in diffs)
    assert any("2026-10-23" in x and "不在附錄 A" in x for x in diffs)
    assert len(R.appendix_hash()) == 64 and R.appendix_hash() == R.appendix_hash(list(R.APPENDIX_A))


# ---------------------------------------------------------------- §2.6 過濾
def test_classify_version_by_commit_time():
    # 07-17 那版（4ad0d3b，commit 2026-07-18T09:43Z）早於 9dab5e9（10:48Z）→ 對應 47cd70e
    assert R.classify_sha_for("2026-07-18T09:43:33+00:00").startswith("47cd70e")
    assert R.classify_sha_for("2026-07-18T10:49:00+00:00").startswith("9dab5e9")
    assert R.classify_sha_for("2026-10-22T18:50:58+00:00").startswith("bc2dbe2")
    with pytest.raises(ValueError):
        R.classify_sha_for("2026-06-01T00:00:00Z")


def test_filter_reason():
    cls = {"2330": {"t": "twse"}, "6488": {"t": "tpex"}, "7584": {"t": "emerging"}, "0050": {"t": "twse"}}
    assert R.filter_reason("2330", cls) is None
    assert R.filter_reason("6488", cls) is None
    assert R.filter_reason("7584", cls) == "emerging"
    assert R.filter_reason("1234", cls) == "not_in_classify"
    assert R.filter_reason("0050", cls) == "etf0"
    for c in ("Electronic", "00631L", "2887I", "02001L", "123", "12345"):
        assert R.filter_reason(c, cls) == "non4"


# ---------------------------------------------------------------- 需求端點 §3.4
def test_demand_endpoints_horizons_offsets_and_realizability():
    cal = [f"d{i:02d}" for i in range(15)]
    need = R.demand_endpoints({"d00": ["A"], "d04": ["B"], "d12": ["C"]}, cal)
    # A：t0∈{d00,d01}，h∈{10,3} → d00 d10 d03 d01 d11 d04
    assert {d for c, d in need if c == "A"} == {"d00", "d10", "d03", "d01", "d11", "d04"}
    # B：t0=d04 → d14、d07；t0=d05 → d15 超出（不可實現），d08 可
    assert {d for c, d in need if c == "B"} == {"d04", "d14", "d07", "d05", "d08"}
    # C：只有 T+3 t0=d12（d15 超出）…→ d12+3=d15 超出；t0=d13 也超出 → 無端點
    assert {d for c, d in need if c == "C"} == set()
    assert R.code_ranges(need)["A"] == ("d00", "d11")


# ---------------------------------------------------------------- 覆蓋率與決策樹 §3.4
NEED = {("1101", "2026-07-17"), ("1101", "2026-07-31"), ("2330", "2026-07-17"), ("2330", "2026-07-31")}


def test_coverage_priceadj():
    rows = {"1101": [{"date": "2026-07-17", "close": 30.1}, {"date": "2026-07-31", "close": 0}],
            "2330": [{"date": "2026-07-17", "close": 1000}, {"date": "2026-07-31", "close": 1010}]}
    assert R.coverage_priceadj(NEED, rows) == (3, 4)          # close=0 不算
    assert R.coverage_priceadj(NEED, {"2330": rows["2330"]}) == (2, 4)  # 查詢失敗的代號全無


def test_dividend_code_adjustable_rules():
    ok = [{"date": "2026-07-20", "reference_price": 95.0, "before_price": 100.0}]
    assert R.dividend_code_adjustable([], "2026-07-17", "2026-07-31")          # 無紀錄＝可
    assert R.dividend_code_adjustable(ok, "2026-07-17", "2026-07-31")
    for bad in ({"reference_price": None, "before_price": 100.0}, {"reference_price": 0, "before_price": 100.0},
                {"reference_price": 95.0, "before_price": -1}, {"before_price": 100.0}):
        assert not R.dividend_code_adjustable([dict(bad, date="2026-07-20")], "2026-07-17", "2026-07-31")
    # 區間外的壞紀錄不影響
    assert R.dividend_code_adjustable([{"date": "2026-08-20", "reference_price": None}], "2026-07-17", "2026-07-31")


def test_coverage_dividend_failed_code_unadjustable_and_missing_close():
    unadj = {("1101", "2026-07-17"), ("1101", "2026-07-31"), ("2330", "2026-07-17")}  # 2330 07-31 無未還原 close
    div = {"1101": [], "2330": []}
    assert R.coverage_dividend(NEED, div, unadj) == (3, 4)
    assert R.coverage_dividend(NEED, {"1101": []}, unadj) == (2, 4)        # 2330 查詢失敗 → 全端點無
    bad = {"1101": [{"date": "2026-07-20", "reference_price": None, "before_price": 50}], "2330": []}
    assert R.coverage_dividend(NEED, bad, unadj) == (1, 4)               # 1101 有紀錄但無法還原 → 全端點無


def _c(cov, tot=1000, obtained=True):
    return {"obtained": obtained, "covered": cov, "total": tot}


def test_decide_tree_branches():
    assert R.decide(_c(990), None) == "TaiwanStockPriceAdj"                       # 恰 99.0% 採用
    assert R.decide(_c(989), _c(995)) == "TaiwanStockDividendResult"              # PriceAdj 不足 → 股利表
    assert R.decide(_c(0, obtained=False), _c(990)) == "TaiwanStockDividendResult"  # PriceAdj 取不到
    assert R.decide(_c(989), _c(989)) == "unadjusted_close"                       # 兩者皆未達
    assert R.decide(_c(0, obtained=False), _c(0, obtained=False)) == "unadjusted_close"
    assert R.decide(_c(999, obtained=False), None) == "unadjusted_close"          # 未取得不採用
    assert R.decide(_c(0, tot=0), _c(0, tot=0)) == "unadjusted_close"


# ---------------------------------------------------------------- token 遮罩
def test_mask_secret_literal_and_query_suffix(monkeypatch):
    monkeypatch.setenv("FINMIND_TOKEN", FAKE_TOKEN)
    s = f"GET https://x/api?dataset=A&token={FAKE_TOKEN}&data_id=2330 failed; also {FAKE_TOKEN}"
    m = R.mask_secret(s)
    assert FAKE_TOKEN not in m and "token=***&data_id=2330" in m
    monkeypatch.delenv("FINMIND_TOKEN")
    assert "token=***" in R.mask_secret("u?token=abc%2Fdef ok") and "abc" not in R.mask_secret("u?token=abc%2Fdef ok")
    assert R.mask_secret("短字串 x", token="") == "短字串 x"


def test_write_decision_masks_values_and_stays_valid_json(tmp_path):
    doc = {"reason": f"refused url ?token={FAKE_TOKEN}", "nested": [f"x {FAKE_TOKEN}"], "n": 1}
    p = R.write_decision(doc, FAKE_TOKEN, tmp_path / "d.json")
    text = p.read_text(encoding="utf-8")
    assert FAKE_TOKEN not in text
    j = json.loads(text)
    assert j["reason"].endswith("token=***") and j["nested"] == ["x ***"] and j["n"] == 1


class _Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._b = code, body or {"status": 200, "data": []}

    def json(self):
        return self._b


class _Sess:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        x = self.script.pop(0) if self.script else _Resp()
        if isinstance(x, Exception):
            raise x
        return x


def test_finmind_errors_are_masked(capsys):
    boom = ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /api/v4/data?token={FAKE_TOKEN}")
    fm = R.FinMind(FAKE_TOKEN, session=_Sess([boom, boom, boom]), sleep=lambda s: None)
    with pytest.raises(R.FetchError) as ei:
        fm.get("TaiwanStockPriceAdj", "2330", "2026-07-17", "2026-10-22")
    assert FAKE_TOKEN not in str(ei.value) and "token=***" in str(ei.value)
    # 非 200 JSON status 也是失敗；token 只在 query 參數裡
    sess = _Sess([_Resp(200, {"status": 400, "msg": "Your level is register"})] * 3)
    fm2 = R.FinMind(FAKE_TOKEN, session=sess, sleep=lambda s: None)
    with pytest.raises(R.FetchError, match="level"):
        fm2.get("TaiwanStockPriceAdj", "2330", "2026-07-17", "2026-10-22")
    assert sess.calls[0]["token"] == FAKE_TOKEN and sess.calls[0]["data_id"] == "2330"
    assert FAKE_TOKEN not in capsys.readouterr().out


def test_finmind_rate_limit_waits_then_succeeds():
    waits = []
    sess = _Sess([_Resp(402), _Resp(200, {"status": 200, "data": [{"date": "2026-07-17", "close": 1}]})])
    fm = R.FinMind(FAKE_TOKEN, session=sess, sleep=waits.append, rate_wait=65)
    assert fm.get("D", "1101", "a", "b") == [{"date": "2026-07-17", "close": 1}]
    assert waits == [65]


def test_finmind_requires_token():
    with pytest.raises(R.FetchError):
        R.FinMind("")


def test_fetch_all_probe_marks_unobtainable_and_masks(capsys):
    boom = ConnectionError(f"bad url ?token={FAKE_TOKEN}")
    fm = R.FinMind(FAKE_TOKEN, session=_Sess([boom] * 20), retries=1, sleep=lambda s: None)
    ranges = {c: ("2026-07-17", "2026-07-31") for c in ("1101", "1102", "1103", "1104", "1105")}
    rows, info = R.fetch_all(fm, "TaiwanStockPriceAdj", ranges, None, probe=3)
    assert rows == {} and info["obtained"] is False and info["queried"] == 3
    assert FAKE_TOKEN not in json.dumps(info) and FAKE_TOKEN not in capsys.readouterr().out


def test_fetch_all_partial_success_and_cache(tmp_path):
    sess = _Sess([_Resp(200, {"status": 200, "data": []}), ConnectionError("x"),
                  _Resp(200, {"status": 200, "data": [{"date": "2026-07-17"}]})])
    fm = R.FinMind(FAKE_TOKEN, session=sess, retries=1, sleep=lambda s: None)
    ranges = {"1101": ("a", "b"), "1102": ("a", "b"), "1103": ("a", "b")}
    rows, info = R.fetch_all(fm, "X", ranges, tmp_path, probe=3)
    assert set(rows) == {"1101", "1103"} and info["obtained"] and info["failed_codes"] == 1
    # 快取命中不再打 API
    fm2 = R.FinMind(FAKE_TOKEN, session=_Sess([ConnectionError("no")] * 5), retries=1, sleep=lambda s: None)
    rows2, _ = R.fetch_all(fm2, "X", {"1101": ("a", "b"), "1103": ("a", "b")}, tmp_path)
    assert rows2 == {"1101": [], "1103": [{"date": "2026-07-17"}]}


def test_stage1_refuses_without_token_or_when_decision_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(R, "PRICE_SOURCE_PATH", tmp_path / "ps.json")
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    argv = ["stage1", "--v2-repo", str(tmp_path), "--flows-repo", str(tmp_path)]
    assert R.main(argv) == 2
    (tmp_path / "ps.json").write_text("{}")
    monkeypatch.setenv("FINMIND_TOKEN", FAKE_TOKEN)
    assert R.main(argv) == 2
    assert "不得在看過報酬後變更" in capsys.readouterr().out


def test_main_masks_unexpected_exception(monkeypatch, capsys):
    monkeypatch.setenv("FINMIND_TOKEN", FAKE_TOKEN)

    def boom(args):
        raise RuntimeError(f"oops token={FAKE_TOKEN}")
    monkeypatch.setattr(R, "cmd_versions", boom)
    assert R.main(["versions", "--v2-repo", "x", "--flows-repo", "y"]) == 1
    out = capsys.readouterr().out
    assert FAKE_TOKEN not in out and "token=***" in out


# ---------------------------------------------------------------- node 燈號執行器（index.html 原碼）
def _node():
    n = shutil.which("node")
    if not n:
        pytest.fail("找不到 node：燈號執行器需要 node")
    return n


def _eval(market, stocks):
    p = subprocess.run([_node(), str(ROOT / "backtest" / "diag_rules_eval.mjs"), str(ROOT / "index.html")],
                       input=json.dumps({"id": 1, "market": market, "stocks": stocks}) + "\n",
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    lines = [json.loads(x) for x in p.stdout.splitlines()]
    return lines[0]["rules"], lines[1]["res"]


def test_eval_runs_index_html_rules_and_c3_gate():
    rules, res = _eval({"regime": "normal", "ma20": 1, "ma60": 1}, {
        "A": {"fd": 2, "td": 2, "ma20": 1, "rs": 1},          # C3 原值真、P3 綠 → C3 計入、總燈綠
        "B": {"fd": 2, "td": 2},                                # 只有 C3（與系統 S2）→ C3 閘後不計、總燈黃
        "C": {"lo20": 1, "rvs": 5},                             # P1 紅 → 總燈紅
    })
    ids = [r["id"] for r in rules]
    assert ids == ["P1", "P2", "C1", "C2", "S1", "C3", "T1", "C4", "P3", "S2", "F1", "F2", "F3", "F4"]
    k = {i: n for n, i in enumerate(ids)}
    a, b, c = res["A"], res["B"], res["C"]
    assert a[0] == "green" and a[1 + k["C3"]] == 1 and a[-1] == 1
    assert b[0] == "yellow" and b[1 + k["C3"]] == 1 and b[-1] == 0 and b[1 + k["S2"]] == 1
    assert c[0] == "red" and c[1 + k["P1"]] == 1 and c[1 + k["P2"]] is None
    # rule_state：C3 依閘後值；null 不進兩組
    assert R.rule_state(rules, a, k["C3"]) == 1 and R.rule_state(rules, b, k["C3"]) == 0
    assert R.rule_state(rules, c, k["P2"]) is None


# ---------------------------------------------------------------- 筆數統計與 §5.4 門檻
def _rules():
    return [{"id": "P1", "col": "red", "dim": "價量", "addon": False},
            {"id": "C3", "col": "green", "dim": "籌碼", "addon": True},
            {"id": "P3", "col": "green", "dim": "價量", "addon": False},
            {"id": "S2", "col": "green", "dim": "系統", "addon": False}]


def test_recount_counts_days_codes_and_sole_reason():
    rules = _rules()
    cal = [f"d{i:02d}" for i in range(13)]
    days = cal[:3]                       # 只有 d00、d01、d02 可實現 T+10
    obs = []
    for d in days:
        for i in range(12):
            on_p1 = i < 6
            on_p3 = not on_p1
            rec = ["red" if on_p1 else "green", int(on_p1), 1 if on_p3 else 0, int(on_p3), 1, int(on_p3 and i < 8)]
            obs.append({"d": d, "code": f"{i:04d}", "rec": rec, "price_ok": not (d == "d00" and i == 0)})
    rc = R.recount(obs, rules, days, cal, h=10)
    assert rc["realizable_days"] == 3 and rc["total"] == {"red": 18, "green": 18, "yellow": 0}
    p1 = rc["rules"]["P1"]
    assert (p1["trig"], p1["trig_days"], p1["real_trig"], p1["codes"], p1["days55"]) == (18, 3, 18, 6, 3)
    assert p1["sole"] == 18 and p1["nonovl_r3"] == (1, 0, 1)
    assert p1["gate"] == {"trig": 17, "days": 3, "nonovl0": 1, "codes": 6}
    # 綠燈唯一理由：亮著的非系統面綠燈集合（C3 依閘後值計入）只有自己——i=6、7 有 C3 同亮，不算
    assert rc["rules"]["P3"]["sole"] == 12
    assert rc["rules"]["C3"]["sole"] is None and rc["rules"]["S2"]["sole"] is None
    assert rc["rules"]["C3"]["trig"] == 6           # 閘後
    assert rc["rules"]["S2"]["days55"] == 0         # 市場層級：同日無對照


def test_gate_verdict_thresholds():
    ok = {"trig": 300, "days": 20, "nonovl0": 3, "codes": 30}
    assert R.gate_verdict(ok, "P1") == "family"
    for k in ok:
        bad = dict(ok, **{k: ok[k] - 1})
        assert R.gate_verdict(bad, "P1") == "insufficient"
    assert R.gate_verdict(ok, "S2") == "na"


def test_compare_counts_reports_differences():
    rep = {"excl": {"raw": 1, "non4": 0, "etf0": 0, "emerging": 0, "not_in_classify": 0}, "filtered": 1,
           "total": {}, "realizable_days_t10": 0, "realizable_days_t3": 0, "main_t10_obs": 0,
           "missing_t0h": {"row_absent": 0, "close_null": 0, "close_nonpos": 0}, "missing_by_total": {},
           "exd_ret_marked": {}, "exd_nonnull_pct": 0, "f3_sole_green": 0, "f3_sole_green_pct": 0,
           "rules": {rid: {"trig": 0, "trig_days": 0, "null_pct": 0, "real_trig": 0, "codes": 0, "days55": 0,
                           "nonovl_r2": (0, 0, 0), "sole": None,
                           "gate": {"trig": 0, "days": 0, "nonovl0": 0, "codes": 0}}
                     for rid in R.SPEC_EXPECTED["rules"]}}
    diffs = R.compare_counts(rep)
    assert any(x.startswith("原始筆數") for x in diffs)
    assert any(x.startswith("§5.4 預期 P1") for x in diffs)
    assert not any(x.startswith("F2 唯一理由") for x in diffs)   # 規格記「—」不比


def test_no_stage2_and_no_return_computation_in_module():
    """本階段不得有 Stage 2／報酬計算（規格 §3.4：Stage 2 等決定檔 commit 後才開工）。"""
    src = (ROOT / "backtest" / "run_diag_rules.py").read_text(encoding="utf-8")
    assert "def cmd_stage2" not in src and '"stage2"' not in src
    assert not os.path.exists(ROOT / "backtest" / "report_diag_rules.md")
