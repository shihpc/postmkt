# build_revenue 純函式：離線、免 token。合成序列以「每月 100、逐年 +20%」為底，方便手算驗證。
import datetime as dt
import json

import build_revenue as br


def flat(years, base=100.0, growth=1.2, start=2021):
    """每月營收相同、逐年乘 growth 的序列（億元）。"""
    return {(start + i, m): base * growth ** i for i in range(years) for m in range(1, 13)}


def test_parse_series_uses_revenue_month_not_date():
    rows = [{"date": "2026-11-01", "revenue_year": 2026, "revenue_month": 10, "revenue": 674000000},
            {"date": "2026-10-01", "revenue_year": 2026, "revenue_month": 9, "revenue": "bad"},
            {"revenue_year": 2026, "revenue_month": 13, "revenue": 1}]
    assert br.parse_series(rows) == {(2026, 10): 6.74}


def test_quarter_helpers():
    assert br.q_of(2026, 10) == (2026, 4)
    assert br.qmonths(2026, 4) == [(2026, 10), (2026, 11), (2026, 12)]
    assert br.prev_q(2026, 1) == (2025, 4)
    assert br.prev_m(2026, 1) == (2025, 12)


def test_default_month_is_previous_month():
    assert br.default_month(dt.date(2026, 11, 11)) == (2026, 10)
    assert br.default_month(dt.date(2027, 1, 11)) == (2026, 12)


def test_model_on_steady_series_is_inline():
    # 2026 全年每月 248.832；第四季預期＝趨勢(去年同季×1.2)與季節性(上季×1.0)的幾何平均，再受 0.75–1.30 限制
    r = flat(6)
    r = {k: v for k, v in r.items() if k <= (2026, 10)}
    x = br.analyze(r, 2026, 10)
    pq = 3 * 100 * 1.2 ** 5
    expect_eq = ((3 * 100 * 1.2 ** 4 * 1.2) * pq) ** 0.5
    assert abs(x["exp_q"] - expect_eq) < 1e-6
    assert abs(x["norm"] - 100 / 3) < 1e-6
    assert abs(x["sur"]) < 1e-6 and x["layer"] == "C" and x["k"] == 1
    assert br.classify(x, lumpy=False) == br.CLS_INLINE


def test_eq_clamp_limits_model_expectation():
    # 去年第四季異常放大 → 趨勢項 2.89 倍、季節性中位數 1 倍，幾何平均 1.70 倍 → 被 1.30 倍上限截住
    r = flat(5)
    for m in (10, 11, 12):
        r[(2024, m)] = 500.0
    r = {k: v for k, v in r.items() if k <= (2025, 10)}
    pq = 3 * 100 * 1.2 ** 4
    assert abs(br.model_eq(r, 2025, 4) - pq * 1.30) < 1e-6


def test_missing_month_returns_none():
    r = flat(6)
    r = {k: v for k, v in r.items() if k <= (2026, 9)}
    assert br.analyze(r, 2026, 10) is None


def test_override_layer_uses_cumulative_and_10pct_threshold():
    r = flat(6)
    r = {k: v for k, v in r.items() if k <= (2026, 11)}
    two = 2 * 100 * 1.2 ** 5
    x = br.analyze(r, 2026, 11, (two * 1.5 / 0.88, "A", "財測"))   # 累計 ÷ (預期×2/3) − 1 ＝ −12%
    assert x["layer"] == "A" and x["k"] == 2
    assert abs(x["sur"] - (-12.0)) < 1e-6
    assert br.classify(x, lumpy=False) in (br.CLS_MISS, br.CLS_LO_MISS)


def test_layer_c_second_month_is_incremental():
    # 季初月已大幅超標；第二個月維持同一水準 → 修正後當月驚喜應遠小於季累計口徑
    r = flat(6)
    r = {k: v for k, v in r.items() if k <= (2026, 9)}
    r[(2026, 10)] = r[(2026, 11)] = 400.0
    x = br.analyze(r, 2026, 11)
    eq = br.model_eq(r, 2026, 4)
    cumulative = 800.0 / (eq * 2 / 3) - 1
    eq_rev = 0.7 * (400.0 / (1 / 3)) + 0.3 * eq
    assert abs(x["sur"] / 100 - (400.0 / (eq_rev / 3) - 1)) < 1e-9
    assert x["sur"] / 100 < cumulative


def test_classify_thresholds_and_expectation_level():
    base = {"layer": "C", "exp_yoy": 0.0, "exp_qoq": 0.0}
    assert br.classify(dict(base, sur=14.9), False) == br.CLS_INLINE
    assert br.classify(dict(base, sur=15.0), False) == br.CLS_BEAT
    assert br.classify(dict(base, sur=20.0), True) == br.CLS_INLINE          # 認列不穩次產業門檻 25
    assert br.classify(dict(base, sur=-25.0), True) == br.CLS_MISS
    assert br.classify(dict(base, layer="B", sur=10.0), False) == br.CLS_BEAT
    assert br.classify(dict(base, sur=30.0, exp_yoy=50.0), False) == br.CLS_HI_BEAT
    assert br.classify(dict(base, sur=30.0, exp_qoq=15.0), False) == br.CLS_HI_BEAT
    assert br.classify(dict(base, sur=-30.0, exp_yoy=-10.0), False) == br.CLS_LO_MISS
    assert br.classify(dict(base, sur=-30.0, exp_yoy=None, exp_qoq=None), False) == br.CLS_MISS
    # 高低同時成立：預期年增 ≥50 判高，否則判低
    assert br.classify(dict(base, sur=-30.0, exp_yoy=60.0, exp_qoq=-12.0), False) == br.CLS_MISS
    assert br.classify(dict(base, sur=-30.0, exp_yoy=-20.0, exp_qoq=20.0), False) == br.CLS_LO_MISS


def test_sector_table_aggregates_and_flags():
    a = {(2026, 10): 200.0, (2025, 10): 100.0, (2026, 9): 110.0, (2025, 9): 100.0}
    b = {(2026, 10): 100.0, (2025, 10): 100.0, (2026, 9): 100.0, (2025, 9): 100.0}
    c = {(2026, 10): 50.0}                                            # 月份不齊 → 不計入
    t = br.sector_table({"1": a, "2": b, "3": c}, {"1": "甲", "2": "甲", "3": "甲"}, 2026, 10)
    assert t == [{"name": "甲", "n": 2, "yoy": 50.0, "prev_yoy": 5.0, "delta": 45.0, "signal": "加速"}]


def test_load_overrides_filters_bad_rows():
    exp = {"entries": [{"code": "2383", "quarter": "2026Q4", "exp_rev_100m": 715.4, "layer": "A", "source": "s"},
                       {"code": "x", "quarter": "2026Q4", "exp_rev_100m": 1, "layer": "BBG"},
                       {"code": "y", "quarter": "2026Q4", "exp_rev_100m": 0, "layer": "B"},
                       {"code": "z", "layer": "A"}]}
    assert br.load_overrides(exp) == {("2383", "2026Q4"): (715.4, "A", "s")}


def test_build_month_shape_and_missing():
    uni = {"lumpy_sectors": [], "sectors": {"甲": [{"code": "1", "name": "一"}, {"code": "2", "name": "二"}],
                                            "晶圓代工": [{"code": "2330", "name": "台積電"}]}}
    full = {k: v for k, v in flat(6).items() if k <= (2026, 10)}
    late = {k: v for k, v in flat(6).items() if k <= (2026, 9)}
    p = br.build_month({"1": full, "2": late, "2330": full}, uni, {}, 2026, 10)
    assert p["schema"] == 1 and p["label"] == "AI 研判，未經回測，非保證"
    assert p["month"] == "2026-10" and p["quarter"] == "2026Q4" and p["k"] == 1
    assert p["universe_n"] == 3 and p["reported_n"] == 2
    assert [m["code"] for m in p["missing"]] == ["2"] and "未公布" in p["missing"][0]["why"]
    assert p["tsmc_yoy"] == 20.0 and sum(p["counts"].values()) == 2
    assert set(p["rows"][0]) == {"code", "name", "sector", "cls", "rev", "mom", "yoy", "prev_yoy", "exp_q", "exp_qoq",
                                 "exp_yoy", "ach", "norm", "sur", "layer", "src"}
    json.dumps(p, ensure_ascii=False)                                  # 可序列化
    p2 = br.build_month({"1": full, "2330": full}, uni, {}, 2026, 10, failed=["2"])
    assert p2["missing"] == [{"code": "2", "name": "二", "why": "抓取失敗"}] and p2["fetch_failed"] == ["2"]


def test_write_if_changed_skips_identical_content(tmp_path):
    f = tmp_path / "x.json"
    assert br.write_if_changed(f, {"a": 1}) is True
    first = f.read_text(encoding="utf-8")
    assert br.write_if_changed(f, {"a": 1}) is False
    assert f.read_text(encoding="utf-8") == first                      # 連 generated_at 都沒動
    assert br.write_if_changed(f, {"a": 2}) is True


def test_committed_inputs_are_well_formed():
    uni = json.loads((br.OUT_DIR / "universe.json").read_text(encoding="utf-8"))
    codes = [s["code"] for lst in uni["sectors"].values() for s in lst]
    assert len(codes) == len(set(codes)) and "2330" in codes
    assert set(uni["lumpy_sectors"]) <= set(uni["sectors"])
    exp = json.loads((br.OUT_DIR / "expect.json").read_text(encoding="utf-8"))
    for e in exp["entries"]:
        assert e["layer"] in ("A", "B") and e["source"] and e["as_of"] and e["code"] in codes
        assert "彭博" not in e["source"] and "bloomberg" not in e["source"].lower()


def test_pct_zero_numerator_is_minus_100():
    assert br.pct(0.0, 50.0) == -100.0
    assert br.pct(10.0, 0.0) is None and br.pct(None, 5.0) is None and br.pct(5.0, None) is None


def test_parse_month_validates_format():
    import pytest
    assert br.parse_month("2026-10") == (2026, 10)
    for bad in ("2026-13", "2026-1", "202610", "", "2026-00", "abcd-ef"):
        with pytest.raises(ValueError):
            br.parse_month(bad)


def test_fetch_aborts_early_when_failures_exceed_tenth(monkeypatch):
    import pytest
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise RuntimeError("rate limited")

    monkeypatch.setattr(br, "api_get", boom)
    monkeypatch.setattr(br.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="超過一成"):
        br.fetch_series([str(i) for i in range(100)])
    assert len(calls) == 11                                           # 第 11 檔失敗即中止，不再往下抓


def test_main_skips_month_below_half_reported(monkeypatch, tmp_path):
    uni = {"lumpy_sectors": [], "sectors": {"甲": [{"code": c, "name": c} for c in ("1", "2", "3")]}}
    (tmp_path / "universe.json").write_text(json.dumps(uni), encoding="utf-8")
    (tmp_path / "expect.json").write_text(json.dumps({"entries": []}), encoding="utf-8")
    full = {k: v for k, v in flat(6).items() if k <= (2026, 10)}
    late = {k: v for k, v in flat(6).items() if k <= (2026, 9)}
    monkeypatch.setattr(br, "OUT_DIR", tmp_path)
    monkeypatch.setattr(br, "fetch_series", lambda codes, cache=None: ({"1": full, "2": late, "3": late}, []))
    assert br.main(["--month", "2026-10"]) == 0
    assert not (tmp_path / "2026-10.json").exists()                    # 1/3 已公布 → 不寫檔
    monkeypatch.setattr(br, "fetch_series", lambda codes, cache=None: ({"1": full, "2": full, "3": late}, []))
    assert br.main(["--month", "2026-10"]) == 0
    d = json.loads((tmp_path / "2026-10.json").read_text(encoding="utf-8"))
    assert d["reported_n"] == 2 and "generated_at" in d
    assert json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["latest"] == "2026-10"
