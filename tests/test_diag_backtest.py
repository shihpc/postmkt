#!/usr/bin/env python3
# tests/test_diag_backtest.py — 持股診斷燈號回測（docs/diag-backtest-spec.md r4）Stage 1 之前與 Stage 1 的離線測試。
# 涵蓋：選版規則（§2.1）、附錄 A、classify 版本對應與宇宙過濾（§2.6）、需求端點（§3.4）、
# 覆蓋率與決策樹三分支（§3.4）、token 遮罩（鐵律 1）、node 燈號執行器、筆數統計與 §5.4 門檻。
# 全部用假資料，免網路、免 token（node 執行器測試需要 node）。
from __future__ import annotations

import importlib.util
import json
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


@pytest.fixture(autouse=True)
def _no_repo_writes(tmp_path, monkeypatch):
    """所有測試的寫檔都導到 tmp，不得寫進 repo 的 backtest/data／cache／決定檔。"""
    monkeypatch.setattr(R, "DATA_DIR", tmp_path / "_data")
    monkeypatch.setattr(R, "CACHE", tmp_path / "_cache")
    monkeypatch.setattr(R, "PRICE_SOURCE_PATH", tmp_path / "_ps.json")


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
    def __init__(self, code=200, body=None, bad_json=False):
        self.status_code, self._b, self._bad = code, ({"status": 200, "data": []} if body is None else body), bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._b


class _Sess:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        x = self.script.pop(0) if self.script else _Resp()
        if isinstance(x, Exception):
            raise x
        return x


def _fm(script, **kw):
    sess = _Sess(script)
    return R.FinMind(FAKE_TOKEN, session=sess, sleep=lambda s: None, **kw), sess


def _ok(rows):
    return _Resp(200, {"status": 200, "data": rows})


def test_token_goes_in_bearer_header_not_url():
    fm, sess = _fm([_ok([{"date": "2026-07-17"}])])
    fm.get("TaiwanStockPriceAdj", "2330", "2026-07-17", "2026-10-22")
    c = sess.calls[0]
    assert c["headers"] == {"Authorization": f"Bearer {FAKE_TOKEN}"}
    assert "token" not in c["params"] and FAKE_TOKEN not in json.dumps(c["params"]) + c["url"]
    assert c["params"]["data_id"] == "2330"


def test_network_errors_retry_then_fetcherror_masked(capsys):
    boom = ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /api/v4/data?token={FAKE_TOKEN}")
    fm, sess = _fm([boom, boom, boom])
    with pytest.raises(R.FetchError) as ei:
        fm.get("TaiwanStockPriceAdj", "2330", "a", "b")
    assert type(ei.value) is R.FetchError and len(sess.calls) == 3
    assert FAKE_TOKEN not in str(ei.value) and "token=***" in str(ei.value)
    assert FAKE_TOKEN not in capsys.readouterr().out


@pytest.mark.parametrize("resp", [_Resp(500, {"msg": "Internal"}), _Resp(502, bad_json=True), _Resp(200, bad_json=True),
                                  _Resp(400, {"status": 400, "msg": "something odd happened"}),
                                  _Resp(400, {"status": 400, "msg": "parameter dataset error"})])   # 疑似我方寫錯，不得當取不到
def test_server_or_unrecognized_errors_are_transient_not_unavailable(resp):
    fm, sess = _fm([resp] * 3)
    with pytest.raises(R.FetchError) as ei:
        fm.get("X", "2330", "a", "b")
    assert type(ei.value) is R.FetchError and len(sess.calls) == 3


@pytest.mark.parametrize("resp", [_Resp(401, {"msg": "x"}), _Resp(403, {"msg": "x"}),
                                  _Resp(400, {"status": 400, "msg": "Token is invalid"}),
                                  _Resp(200, {"status": 401, "msg": "please login"})])
def test_auth_errors_no_retry(resp):
    fm, sess = _fm([resp] * 3)
    with pytest.raises(R.AuthError):
        fm.get("X", "2330", "a", "b")
    assert len(sess.calls) == 1


@pytest.mark.parametrize("msg", ["Your level is register. Please update your user level.",
                                 "permission denied for this dataset", "需升級 sponsor 才能使用"])
def test_explicit_unavailable(msg):
    fm, sess = _fm([_Resp(400, {"status": 400, "msg": msg})] * 3)
    with pytest.raises(R.DatasetUnavailable):
        fm.get("X", "2330", "a", "b")
    assert len(sess.calls) == 1


def test_rate_limit_waits_then_succeeds():
    waits = []
    sess = _Sess([_Resp(402), _Resp(200, {"status": 402, "msg": "limit"}), _ok([{"date": "d", "close": 1}])])
    fm = R.FinMind(FAKE_TOKEN, session=sess, sleep=waits.append, rate_wait=65)
    assert fm.get("D", "1101", "a", "b") == [{"date": "d", "close": 1}]
    assert waits == [65, 65]


def test_requires_token():
    with pytest.raises(R.AuthError):
        R.FinMind("")


def test_preflight_fails_on_empty_or_error():
    fm, _ = _fm([_ok([])])
    with pytest.raises(R.FetchError, match="回空"):
        fm.preflight("2026-10-22")
    fm, _ = _fm([_Resp(401, {"msg": "bad"})])
    with pytest.raises(R.AuthError):
        fm.preflight("2026-10-22")
    fm, sess = _fm([_ok([{"date": "2026-10-22", "close": 1}])])
    fm.preflight("2026-10-22")
    assert sess.calls[0]["params"]["dataset"] == "TaiwanStockPrice"


RANGES = {c: ("2026-07-17", "2026-07-31") for c in ("1101", "1102", "1103")}


def test_fetch_all_unavailable_on_first_request_is_unobtainable():
    fm, sess = _fm([_Resp(400, {"status": 400, "msg": "Your level is Free"})])
    rows, info = R.fetch_all(fm, "TaiwanStockPriceAdj", RANGES, None)
    assert rows == {} and info["obtained"] is False and len(sess.calls) == 1
    assert FAKE_TOKEN not in json.dumps(info)


def test_fetch_all_unavailable_after_success_is_contradiction():
    fm, _ = _fm([_ok([]), _Resp(400, {"status": 400, "msg": "Your level is Free"})])
    with pytest.raises(R.FetchError, match="矛盾"):
        R.fetch_all(fm, "X", RANGES, None)


def test_fetch_all_single_code_failure_propagates():
    """個別代號重試後仍失敗＝job 失敗，不靜默計入覆蓋率分母。"""
    fm, _ = _fm([_ok([]), ConnectionError("x"), ConnectionError("x"), ConnectionError("x")])
    with pytest.raises(R.FetchError):
        R.fetch_all(fm, "X", RANGES, None)


def test_fetch_all_auth_failure_propagates():
    fm, _ = _fm([_Resp(401, {"msg": "x"})])
    with pytest.raises(R.AuthError):
        R.fetch_all(fm, "X", RANGES, None)


def test_fetch_all_success_and_cache_resume(tmp_path):
    fm, _ = _fm([_ok([]), _ok([{"date": "2026-07-17"}]), _ok([])])
    rows, info = R.fetch_all(fm, "X", RANGES, tmp_path)
    assert set(rows) == set(RANGES) and info["obtained"] and info["codes_nonempty"] == 1
    fm2, sess2 = _fm([ConnectionError("no")] * 5)
    rows2, _ = R.fetch_all(fm2, "X", RANGES, tmp_path)
    assert rows2 == rows and sess2.calls == []


NEED3 = {(c, d) for c in RANGES for d in ("2026-07-17", "2026-07-31")}


def _route(table):
    """依 dataset 回應的假 session：table[dataset] 為 callable(params)->_Resp 或 Exception。"""
    class S(_Sess):
        def get(self, url, params=None, headers=None, timeout=None):
            self.calls.append({"params": params})
            x = table[params["dataset"]](params)
            if isinstance(x, Exception):
                raise x
            return x
    return S([])


def _pre(p):
    return _ok([{"date": p["start_date"], "close": 1}])


def test_core_priceadj_adopted_and_raw_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DATA_DIR", tmp_path)
    s = _route({"TaiwanStockPrice": _pre,
                "TaiwanStockPriceAdj": lambda p: _ok([{"date": d, "close": 10} for d in ("2026-07-17", "2026-07-31")])})
    core = R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None)
    assert core["decision"] == "TaiwanStockPriceAdj" and core["divr"] is None
    assert core["files"]["TaiwanStockPriceAdj"]["adopted"] is True
    assert (tmp_path / "diag_rules_price_adj.json.gz").exists()


def test_core_falls_to_dividend_and_saves_both(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DATA_DIR", tmp_path)
    s = _route({"TaiwanStockPrice": _pre,
                "TaiwanStockPriceAdj": lambda p: _ok([{"date": "2026-07-17", "close": 10}]),   # 50% 覆蓋
                "TaiwanStockDividendResult": lambda p: _ok(
                    [{"date": "2026-07-20", "reference_price": 9.5, "before_price": 10}] if p["data_id"] == "1101" else [])})
    core = R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None)
    assert core["decision"] == "TaiwanStockDividendResult"
    assert core["files"]["TaiwanStockPriceAdj"]["adopted"] is False
    assert core["files"]["TaiwanStockDividendResult"]["adopted"] is True
    assert (tmp_path / "diag_rules_price_adj.json.gz").exists()
    assert (tmp_path / "diag_rules_dividend_result.json.gz").exists()


def test_core_both_unavailable_is_unadjusted():
    s = _route({"TaiwanStockPrice": _pre, "TaiwanStockPriceAdj": lambda p: _Resp(400, {"status": 400, "msg": "Your level is Free"}),
                "TaiwanStockDividendResult": lambda p: _Resp(400, {"status": 400, "msg": "Your level is Free"})})
    core = R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None)
    assert core["decision"] == "unadjusted_close" and core["files"] == {}


@pytest.mark.parametrize("table", [
    {"TaiwanStockPrice": lambda p: _Resp(401, {"msg": "x"})},                                   # 預檢認證失敗
    {"TaiwanStockPrice": lambda p: ConnectionError("down")},                                     # 預檢網路失敗
    {"TaiwanStockPrice": _pre, "TaiwanStockPriceAdj": lambda p: _Resp(503, {"msg": "busy"})},   # 5xx
    {"TaiwanStockPrice": _pre, "TaiwanStockPriceAdj": lambda p: _ok([]),
     "TaiwanStockDividendResult": lambda p: _ok([])},                                            # 股利表全空：無法區分
])
def test_core_failures_raise(table):
    s = _route(table)
    with pytest.raises(R.FetchError):
        R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None)


def test_cmd_stage1_writes_nothing_on_fetch_failure(tmp_path, monkeypatch):
    out = tmp_path / "ps.json"
    monkeypatch.setattr(R, "PRICE_SOURCE_PATH", out)
    monkeypatch.setenv("FINMIND_TOKEN", FAKE_TOKEN)

    class Src:
        calendar = ["2026-07-17", "2026-07-31"]
        calendar_end = "2026-07-31"
    monkeypatch.setattr(R, "make_sources", lambda a: Src())
    monkeypatch.setattr(R, "sample_codes", lambda s, extra=None: ({"2026-07-17": ["1101"]}, {}))
    monkeypatch.setattr(R, "collect_extra", lambda *a: ({}, {"mode": "none"}))
    monkeypatch.setattr(R, "load_unadjusted", lambda s, d, c: {})

    def core(*a, **k):
        raise R.FetchError(f"down token={FAKE_TOKEN}")
    monkeypatch.setattr(R, "stage1_core", core)
    assert R.main(["stage1", "--v2-repo", "x", "--flows-repo", "y"]) == 1
    assert not out.exists()


def test_demand_hash_order_independent():
    a = {("1101", "2026-07-17"), ("2330", "2026-07-31")}
    assert R.demand_hash(a) == R.demand_hash(set(sorted(a, reverse=True))) and len(R.demand_hash(a)) == 64
    assert R.demand_hash(a) != R.demand_hash(a | {("2330", "2026-08-03")})


def test_persist_commit_gzip_reproducible(tmp_path, monkeypatch):
    import gzip
    monkeypatch.setattr(R, "DATA_DIR", tmp_path / "data")
    obj = {"2330": [{"date": "2026-07-17", "close": 1000}], "1101": []}
    m1 = R.persist_raw("price_adj", obj, "commit")
    b1 = (tmp_path / "data" / "diag_rules_price_adj.json.gz").read_bytes()
    m2 = R.persist_raw("price_adj", dict(reversed(list(obj.items()))), "commit")
    assert m1["sha256"] == m2["sha256"] and m1["bytes"] == len(b1)
    assert json.loads(gzip.decompress(b1)) == obj
    assert R.PERSIST_MODES[0] == "commit" and R.EXTRA_UNIVERSE_MODES[0] == "benchmark_emerging"
    with pytest.raises(ValueError):
        R.persist_raw("x", {}, "nope")


def test_benchmark_codes_rules():
    meta = {"2330": {"is_etf": False}, "6488": {"is_etf": False}, "7584": {"is_etf": False},
            "0050": {"is_etf": True}, "1234": {"is_etf": True}}
    cls = {"2330": {"t": "twse"}, "6488": {"t": "tpex"}, "7584": {"t": "emerging"}, "1234": {"t": "twse"},
           "0050": {"t": "twse"}, "9999": {"t": "twse"}}
    got = R.benchmark_codes(["2330", "6488", "7584", "0050", "1234", "9999", "00631L"], meta, cls)
    assert got == ["2330", "6488"]      # 9999 無 meta（is_etf 不明）→ 不納入


def test_extra_endpoints_and_ranges_exclude_main_need():
    cal = [f"d{i:02d}" for i in range(15)]
    need = R.demand_endpoints({"d00": ["A"]}, cal)
    xneed = R.extra_endpoints({"d00": ["A", "B"]}, {"d01": ["E"]}, cal)
    rng = R.extra_ranges(xneed, need)
    assert "A" not in rng and set(rng) == {"B", "E"}
    assert rng["B"] == ("d00", "d11") and rng["E"] == ("d01", "d12")
    assert R.collect_extra(None, "none", {}, need) == ({}, {"mode": "none"})


def test_core_extra_fetched_with_adopted_source_not_in_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DATA_DIR", tmp_path / "data")
    seen = []

    def adj(p):
        seen.append(p["data_id"])
        return _ok([{"date": d, "close": 10} for d in ("2026-07-17", "2026-07-31")])
    s = _route({"TaiwanStockPrice": _pre, "TaiwanStockPriceAdj": adj})
    extra = {"9910": ("2026-07-17", "2026-07-31")}
    core = R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None,
                         "commit", extra)
    assert core["adj"]["total"] == len(NEED3) and core["adj"]["covered"] == len(NEED3)   # 額外代號不進分母
    assert "9910" in seen and core["files"]["extra"]["dataset"] == "TaiwanStockPriceAdj"
    assert (tmp_path / "data" / "diag_rules_extra_price_adj.json.gz").exists()
    assert (tmp_path / "data" / "diag_rules_price_adj.json.gz").exists()


def test_core_no_extra_when_unadjusted():
    unav = lambda p: _Resp(400, {"status": 400, "msg": "Your level is Free"})  # noqa: E731
    s = _route({"TaiwanStockPrice": _pre, "TaiwanStockPriceAdj": unav, "TaiwanStockDividendResult": unav})
    core = R.stage1_core(R.FinMind(FAKE_TOKEN, session=s, sleep=lambda x: None), NEED3, NEED3, "2026-10-22", None,
                         "commit", {"9910": ("a", "b")})
    assert core["decision"] == "unadjusted_close" and "extra" not in core["files"]


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
    """本階段不得有 Stage 2／報酬計算（規格 §3.4：Stage 2 等決定檔 commit 後才開工）。

    只掃程式碼（去掉註解與字串常量難以精確，改掃「計算用的識別字與呼叫」）：
    bootstrap／Holm／Spearman／百分位／亂數／numpy／報酬比值等一律不得出現。"""
    import re as _re
    src = (ROOT / "backtest" / "run_diag_rules.py").read_text(encoding="utf-8")
    mjs = (ROOT / "backtest" / "diag_rules_eval.mjs").read_text(encoding="utf-8")
    assert "def cmd_stage2" not in src and '"stage2"' not in src
    banned = [r"\bimport numpy\b", r"\bnumpy\.", r"\bnp\.", r"default_rng", r"\brandom\.", r"percentile",
              r"def \w*(bootstrap|holm|spearman|excess|forward_return|returns?)\w*\(",
              r"\bstatistics\.", r"\bmean\(", r"\bmedian\(",
              r"close\W*\]?\s*/", r"/\s*\w*close", r"\bR_i\b", r"\bs_D\b"]
    for pat in banned:
        assert not _re.search(pat, src, _re.I), f"run_diag_rules.py 不應出現 {pat}"
        assert not _re.search(pat, mjs, _re.I), f"diag_rules_eval.mjs 不應出現 {pat}"
    assert not (ROOT / "backtest" / "report_diag_rules.md").exists()
    assert not any(p.name.startswith("stage2") for p in (ROOT / "backtest").iterdir())
