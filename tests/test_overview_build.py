#!/usr/bin/env python3
# tests/test_overview_build.py —— 市場總覽後端 src/build_overview.py（2026-11-12，規格 docs/market-overview.md §3／§5-2）
# ①parity：B（radarPoints）、e（radarHolders）、E（RRGD 座標與持續性清單）、b（nBuyers≥2）與 index.html 逐位相同（node 抽碼對跑）
# ②計數與排序、stale 不計入、來源缺失降級、次產業上卷／降級、容許窗、label 逐字、冪等、基準來源全缺不寫檔
# 免網路、免 token（跨 repo 檔以 --src-root 指到測試自建的暫存目錄）。
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import build_overview as bo

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
SIB = ROOT.parent   # 姊妹 repo checkout 的上一層（本機才有；CI 無 → 該測試 skip）


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def node(inp):
    exe = shutil.which("node")
    if not exe:
        pytest.fail("找不到 node：parity 測試需要 node 執行 index.html 抽出的前端函式")
    out = subprocess.run([exe, str(ROOT / "tests" / "overview_node.mjs")], input=json.dumps(inp),
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def same(a, b):
    return float(a).hex() == float(b).hex()


# ---------- parity ----------

def check_radar(sr):
    js, py = node({"sr": sr})["points"], bo.radar_points(sr["windows"]["r5"], sr["windows"]["r20"], "chain", "total")
    assert len(js) == len(py) and len(py) > 0
    for a, b in zip(js, py):
        assert a["sector"] == b["sector"] and a["q"] == b["q"] and a["n"] == b["n"]
        assert all(same(a[k], b[k]) for k in ("v20", "v5", "x", "y")), (a, b)


def check_holders(diag):
    js, py = node({"diag": diag})["holders"], bo.radar_holders_up(diag)
    assert js["cover"] == py["cover"] and js["hdd"] == py["hdd"]
    assert [(r["code"], r["name"]) for r in js["up"]] == [(r["code"], r["name"]) for r in py["up"]]
    assert all(same(a["hdw"], b["hdw"]) for a, b in zip(js["up"], py["up"]))


def check_rrgd(series):
    js, p = node({"series": series})["rrgd"], bo.rrgd_prep(series)
    t = p["valid"][-1]
    assert js["t"] == t and js["valid"] == len(p["valid"])
    assert js["imp"] == bo.rrgd_persist_list(p["coords"], t, "改善", bo.RRGD_PERSIST, 1)
    assert js["lead"] == bo.rrgd_persist_list(p["coords"], t, "領先", bo.RRGD_PERSIST, 0)
    assert list(js["coords"]) == p["names"]
    for nm in p["names"]:
        a, b = js["coords"][nm], p["coords"][nm][t]
        assert (a is None) == (b is None)
        if a is not None:
            assert same(a[0], b[0]) and same(a[1], b[1]), nm


def check_cobuy(diff):
    assert node({"diff": diff})["cobuy"] == [s["c"] for s in bo.aetf_co_buy(diff)]


def test_parity_radar_fixture():
    check_radar(load(FIX / "chipradar_sector_ranges_r5r20.json"))


def test_parity_holders_repo_diag():
    check_holders(load(ROOT / "data/diag/diag.json"))


def test_parity_holders_edge():
    check_holders({"stocks": {"2330": {"hdw": 0.5, "hdd": "2026-11-06", "n": "甲"}, "1101": {"hdw": 0.5, "hdd": "2026-10-30", "n": None},
                              "00878": {"hdw": "1", "n": "字串不收"}, "9999": {"hdw": -1, "hdd": "2026-11-06"}, "3008": None,
                              "6488": {"hdw": 0, "hdd": 5}}})


def test_parity_rrgd_fixture():
    s = load(FIX / "overview_series_tail.json")
    check_rrgd(s)
    js = node({"series": s})["rrgd"]
    assert js["date"] == s["dates"][-1]


def test_parity_rrgd_with_gaps():
    s = load(FIX / "overview_series_tail.json")
    names = list(s["chains"])
    s["chains"][names[0]]["ret_ew"][0] = None        # 開頭缺值：指數停在 base
    s["chains"][names[1]]["ret_ew"][30] = None       # 中間缺值：之後整段截斷
    s["chains"][names[2]]["ret_ew"] = [0.0] * len(s["dates"])   # 與大盤的比值仍會動；另測 SD 路徑
    s["market"]["ret_ew"][0] = None
    check_rrgd(s)


def test_parity_cobuy_fixture():
    d = load(FIX / "overview_aetf_diff.json")
    check_cobuy(d)
    assert len(bo.aetf_co_buy(d)) >= 1
    check_cobuy({"stocks": [{"c": "1", "by": {"A": 1, "B": 0}}, {"c": "2", "by": {"A": 1, "B": 2, "C": -3}}, {"c": "3"}, {"c": "4", "by": {"A": -1, "B": -2}}]})


@pytest.mark.skipif(not (SIB / "taiwan-flows/data/sector_ranges_lite.json").exists()
                    or not (SIB / "taiwan-flow-live-v2/data/chain_daily/series.json").exists(), reason="無姊妹 repo 本機 checkout")
def test_parity_real_sibling_files():
    check_radar(load(SIB / "taiwan-flows/data/sector_ranges_lite.json"))
    check_rrgd(load(SIB / "taiwan-flow-live-v2/data/chain_daily/series.json"))
    check_cobuy(load(SIB / "taiwan-flow-live-v2/data/aetf/diff.json"))


def test_radar_quad_matches_frontend_definition():
    assert [bo.radar_quad(x, y) for x, y in ((0, 0), (1, -1), (-1, -1), (-1, 0))] == ["acc_in", "slow_in", "acc_out", "slow_out"]


# ---------- 合成輸入 ----------

def sr(end="2026-11-12", pos=("甲", "乙", "丙")):
    def rows(scale):
        out = [{"sector": s, "net_amt_k": (100 - i) * scale, "n": 10} for i, s in enumerate(pos)]
        return out + [{"sector": "丁", "net_amt_k": -50 * scale, "n": 10}]
    w = lambda n, scale: {"trading_days": n, "end": end, "classifications": {"chain": {"investors": {"total": rows(scale)}}}}  # noqa: E731
    return {"date": end, "windows": {"r5": w(5, 1000), "r20": w(20, 1000)}}


CLASSIFY = {"map": {"1": {"p": [["甲", "甲子"], ["乙", "共用"]]}, "2": {"p": [["丙", "共用"], ["乙", "乙子"]]}}}


def diff(date="2026/11/12"):
    return {"primary_date": date,
            "subs": [{"name": "甲子", "val": 5}, {"name": "共用", "val": 4}, {"name": "乙子", "val": 3}, {"name": "沒對映", "val": 2}, {"name": "負的", "val": -9}],
            "stocks": [{"c": "2330", "n": "台積電", "by": {"A": 1, "B": 2}}, {"c": "2317", "n": "鴻海", "by": {"A": 1}},
                       {"c": "<img>", "n": "壞代號", "by": {"A": 1, "B": 1}}]}


def base_inp():
    return {
        "sr": sr(), "classify": copy.deepcopy(CLASSIFY), "diff": diff(),
        "morning": {"recap": {"baseline_date": "2026-11-11"}, "signals": {"cont_subs": ["甲子"], "new_subs": ["乙子", "甲子"]}},
        "series": ValueError("x"),
        "tf": {"date": "2026-11-12", "pages": {"sync": {"sync_buy": [{"code": "2330", "name": "台積電"}, {"code": "2454", "name": "聯發科"}, {"code": "1101", "name": "台泥"}]}}},
        "track": {"schema": 1, "date": "2026-11-12", "tracking": [{"code": "2454", "name": "聯發科"}, {"code": "2330", "name": "台積電"}]},
        "rev": {"month": "2026-10", "rows": [{"code": "2330", "name": "台積電", "cls": "Beat"}, {"code": "1101", "name": "台泥", "cls": "Miss"},
                                               {"code": "2454", "name": "聯發科", "cls": "高預期仍Beat"}]},
        "diag": {"stocks": {"1101": {"hdw": 0.3, "hdd": "2026-11-06", "n": "台泥"}, "2330": {"hdw": 0.1, "hdd": "2026-11-06", "n": "台積電"}}},
    }


def src(o, layer, sid):
    return next(s for s in o[layer]["sources"] if s["id"] == sid)


def test_label_schema_and_shape():
    o = bo.build(base_inp(), "G")
    assert o["label"] == "AI 研判，未經回測，非保證" == bo.LABEL
    assert o["schema"] == 1 and o["date"] == "2026-11-12" and o["generated_at"] == "G" and o["side"] == "long"
    assert set(o["sectors"]) >= {"base_date", "sources", "rows"} and set(o["stocks"]) >= {"base_date", "sources", "rows"}
    assert src(o, "stocks", "f")["status"] == "excluded" and src(o, "stocks", "f")["counted"] is False


def test_count_and_sort():
    o = bo.build(base_inp(), "G")
    # 個股：2330＝a,b,c,d,e（5）；2454＝a,c,d（3）；1101＝a,e（2）；2317 只在 b 的單一 ETF → 不是共識
    assert [(r["key"], r["count"], r["hits"]) for r in o["stocks"]["rows"]] == [
        ("2330", 5, ["a", "b", "c", "d", "e"]), ("2454", 3, ["a", "c", "d"]), ("1101", 2, ["a", "e"])]
    assert o["stocks"]["rows"][0]["name"] == "台積電"
    assert all(r["count"] >= 2 for r in o["stocks"]["rows"] + o["sectors"]["rows"])
    # 類股：A＝甲乙丙；B＝甲乙丙（x>0、y=0 → acc_in）；C＝甲（甲子）乙（乙子）；D stale；E 失敗
    assert [(r["key"], r["count"]) for r in o["sectors"]["rows"]] == [("乙", 3), ("甲", 3), ("丙", 2)]
    assert o["sectors"]["rows"][0]["via"] == {"C": ["乙子"]}


def test_sort_tie_by_key_ascending():
    i = base_inp()
    i["tf"]["pages"]["sync"]["sync_buy"] = [{"code": c, "name": ""} for c in ("9999", "1111", "5555")]
    i["track"]["tracking"] = [{"code": c, "name": ""} for c in ("5555", "9999", "1111")]
    i["diff"], i["rev"], i["diag"] = ValueError(), ValueError(), ValueError()
    assert [r["key"] for r in bo.build(i, "G")["stocks"]["rows"]] == ["1111", "5555", "9999"]


def test_stale_not_counted():
    i = base_inp()
    i["track"]["date"] = "2026-11-11"
    o = bo.build(i, "G")
    c = src(o, "stocks", "c")
    assert c["status"] == "stale" and c["stale"] is True and c["counted"] is False and c["ok"] is True and c["n"] == 2
    assert [(r["key"], r["hits"]) for r in o["stocks"]["rows"]] == [("2330", ["a", "b", "d", "e"]), ("1101", ["a", "e"]), ("2454", ["a", "d"])]
    d = src(o, "sectors", "D")   # morning 的資料日＝前一交易日 → stale
    assert d["status"] == "stale" and d["date"] == "2026-11-11" and [x["key"] for x in d["items"]] == ["乙", "甲"]
    assert all("D" not in r["hits"] for r in o["sectors"]["rows"])


def test_source_failure_degrades():
    i = base_inp()
    i["diff"] = ValueError("boom")
    i["rev"] = {"month": "bad"}
    o = bo.build(i, "G")
    for layer, sid in (("stocks", "b"), ("stocks", "d"), ("sectors", "C"), ("sectors", "E")):
        s = src(o, layer, sid)
        assert s["status"] == "fail" and s["ok"] is False and s["counted"] is False and s["items"] == []
    assert [(r["key"], r["hits"]) for r in o["stocks"]["rows"]] == [("2330", ["a", "c", "e"]), ("1101", ["a", "e"]), ("2454", ["a", "c"])]


def test_fewer_than_two_valid_sources_outputs_no_rows():
    i = base_inp()
    for k in ("diff", "track", "rev", "diag"):
        i[k] = ValueError()
    o = bo.build(i, "G")
    assert o["stocks"]["rows"] == [] and "少於 2 個" in o["stocks"]["note"]


def test_base_missing():
    i = base_inp()
    i["tf"] = ValueError()
    o = bo.build(i, "G")
    assert o["date"] == "2026-11-12" and o["stocks"]["base_date"] is None and o["stocks"]["rows"] == []
    assert src(o, "stocks", "c")["status"] == "stale"
    i["sr"] = ValueError()
    assert bo.build(i, "G") is None


def test_rollup_unique_parent_only_and_downgrade():
    o = bo.build(base_inp(), "G")
    c = src(o, "sectors", "C")
    assert c["status"] == "valid" and c["items"] == [{"key": "乙", "via": ["乙子"]}, {"key": "甲", "via": ["甲子"]}]
    assert c["unmapped"] == ["共用", "沒對映"] and c["subs"] == ["甲子", "共用", "乙子", "沒對映"]
    i = base_inp()
    i["classify"] = ValueError("404")
    o = bo.build(i, "G")
    for sid in ("C", "D"):
        s = src(o, "sectors", sid)
        assert s["status"] == "listed" and s["counted"] is False and s["items"] == [] and s["subs"] and "不計入" in s["note"]
    assert all(set(r["hits"]) <= {"A", "B"} for r in o["sectors"]["rows"])


def test_windows():
    assert bo.revenue_valid("2026-10", "2026-11-01") and bo.revenue_valid("2026-10", "2026-12-15")
    assert not bo.revenue_valid("2026-10", "2026-10-31") and not bo.revenue_valid("2026-10", "2026-12-16")
    assert bo.revenue_valid("2026-11", "2027-01-15") and bo.revenue_valid("2026-12", "2027-02-15")
    assert bo.holder_valid("2026-11-06", "2026-11-16") and bo.holder_valid("2026-11-12", "2026-11-12")
    assert not bo.holder_valid("2026-11-06", "2026-11-17") and not bo.holder_valid("2026-11-13", "2026-11-12")
    i = base_inp()
    i["rev"]["month"] = "2026-08"
    for s in i["diag"]["stocks"].values():
        s["hdd"] = "2026-10-30"
    o = bo.build(i, "G")
    assert src(o, "stocks", "d")["status"] == "stale" and src(o, "stocks", "e")["status"] == "stale"


def test_bad_codes_dropped():
    o = bo.build(base_inp(), "G")
    assert [x["key"] for x in src(o, "stocks", "b")["items"]] == ["2330"]


# ---------- main()：冪等、不寫檔 ----------

def make_tree(tmp, inp):
    root, sib = tmp / "postmkt", tmp
    put = lambda p, o: (p.parent.mkdir(parents=True, exist_ok=True), p.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8"))  # noqa: E731
    put(root / "data/pick2/track.json", inp["track"])
    put(root / "data/diag/diag.json", inp["diag"])
    put(root / "data/revenue/index.json", {"latest": inp["rev"]["month"]})
    put(root / f"data/revenue/{inp['rev']['month']}.json", inp["rev"])
    for key, (repo, path) in bo.SRC_FILES.items():
        if isinstance(inp.get(key), dict):
            put(sib / repo / path, inp[key])
    return root


def test_main_idempotent_and_snapshot(tmp_path):
    root = make_tree(tmp_path, base_inp())
    args = ["--root", str(root), "--src-root", str(tmp_path)]
    assert bo.main(args) == 0
    lp, dp = root / "data/overview/latest.json", root / "data/overview/daily/2026-11-12.json"
    a = load(lp)
    assert a == load(dp) and a["label"] == bo.LABEL and len(a["stocks"]["rows"]) == 3
    raw, raw_d = lp.read_bytes(), dp.read_bytes()
    lp.write_text(json.dumps({**a, "generated_at": "2000-01-01T00:00:00+08:00"}, ensure_ascii=False), encoding="utf-8")
    old = lp.read_bytes()
    assert bo.main(args) == 0
    assert lp.read_bytes() == old and dp.read_bytes() == raw_d   # 只差 generated_at → 不重寫
    assert raw != old
    # 內容真的變了才重寫，且同一 date 覆寫同一個快照檔
    t = load(root / "data/pick2/track.json")
    t["tracking"] = []
    (root / "data/pick2/track.json").write_text(json.dumps(t), encoding="utf-8")
    assert bo.main(args) == 0
    assert all("c" not in r["hits"] for r in load(lp)["stocks"]["rows"]) and load(lp) == load(dp) and lp.read_bytes() != old
    assert sorted(p.name for p in (root / "data/overview/daily").iterdir()) == ["2026-11-12.json"]


def test_main_no_base_writes_nothing(tmp_path):
    i = base_inp()
    i["sr"], i["tf"] = None, None
    root = make_tree(tmp_path, i)
    assert bo.main(["--root", str(root), "--src-root", str(tmp_path)]) == 2
    assert not (root / "data/overview").exists()


def test_committed_snapshot_schema():
    p = ROOT / "data/overview/latest.json"
    o = load(p)
    assert o["schema"] == 1 and o["label"] == bo.LABEL and bo.DATE_RE.match(o["date"])
    assert load(ROOT / f"data/overview/daily/{o['date']}.json")["date"] == o["date"]
    for layer in ("sectors", "stocks"):
        counted = {s["id"] for s in o[layer]["sources"] if s["counted"]}
        rows = o[layer]["rows"]
        assert rows == sorted(rows, key=lambda r: (-r["count"], r["key"]))
        for r in rows:
            assert r["count"] == len(r["hits"]) >= 2 and set(r["hits"]) <= counted
        for s in o[layer]["sources"]:
            assert s["status"] in ("valid", "stale", "fail", "listed", "excluded") and s["counted"] == (s["status"] == "valid")
