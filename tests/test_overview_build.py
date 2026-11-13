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
    for k in ("up", "down"):   # down＝流出側 e′（§6）
        assert [(r["code"], r["name"]) for r in js[k]] == [(r["code"], r["name"]) for r in py[k]]
        assert all(same(a["hdw"], b["hdw"]) for a, b in zip(js[k], py[k]))


def check_rrgd(series):
    js, p = node({"series": series})["rrgd"], bo.rrgd_prep(series)
    t = p["valid"][-1]
    assert js["t"] == t and js["valid"] == len(p["valid"])
    assert js["imp"] == bo.rrgd_persist_list(p["coords"], t, "改善", bo.RRGD_PERSIST, 1)
    assert js["lead"] == bo.rrgd_persist_list(p["coords"], t, "領先", bo.RRGD_PERSIST, 0)
    assert js["weak"] == bo.rrgd_persist_list(p["coords"], t, "轉弱", bo.RRGD_PERSIST, 1)   # 流出側 E′（§6）
    assert js["lag"] == bo.rrgd_persist_list(p["coords"], t, "落後", bo.RRGD_PERSIST, 0)
    assert list(js["coords"]) == p["names"]
    for nm in p["names"]:
        a, b = js["coords"][nm], p["coords"][nm][t]
        assert (a is None) == (b is None)
        if a is not None:
            assert same(a[0], b[0]) and same(a[1], b[1]), nm


def check_cobuy(diff):
    js = node({"diff": diff})
    assert js["cobuy"] == [s["c"] for s in bo.aetf_co_buy(diff)]
    assert js["cosell"] == [s["c"] for s in bo.aetf_co_buy(diff, -1)]   # 流出側 b′＝nSellers(s)>=2（§6）


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
    assert len(bo.aetf_co_buy(d)) >= 1 and len(bo.aetf_co_buy(d, -1)) >= 1
    assert not ({s["c"] for s in bo.aetf_co_buy(d)} == {s["c"] for s in bo.aetf_co_buy(d, -1)})
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
    # 類股：A＝甲乙丙；B＝甲乙丙（x>0、y=0 → acc_in）——A、B 同一計票群組只算 1 票；C＝甲（甲子）乙（乙子）；D stale；E 失敗
    # 丙只中 A＋B（同組）→ 1 票 → 不上榜
    assert [(r["key"], r["count"], r["hits"]) for r in o["sectors"]["rows"]] == [("乙", 2, ["A", "B", "C"]), ("甲", 2, ["A", "B", "C"])]
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
    assert src(o, "stocks", "a")["counted"] is True


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
    # 只剩 A、B 兩個有效來源，但同屬一個計票群組 → 有效群組 1 個 → 不輸出列
    assert o["sectors"]["rows"] == [] and "計票群組只有 1 個" in o["sectors"]["note"]


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
    blocks = [o] + ([o["out"]] if "out" in o else [])   # out＝資金流出側（2026-11-13 起；舊檔沒有）
    for blk, layer in [(b, x) for b in blocks for x in ("sectors", "stocks")]:
        o = blk
        counted = {s["id"] for s in o[layer]["sources"] if s["counted"]}
        rows = o[layer]["rows"]
        assert rows == sorted(rows, key=lambda r: (-r["count"], r["key"]))
        for r in rows:
            grp = {s["id"]: s["group"] for s in o[layer]["sources"]}
            assert r["count"] == len({grp[h] for h in r["hits"]}) >= 2 and set(r["hits"]) <= counted
            assert len(r["hits"]) == len(set(r["hits"]))
        for s in o[layer]["sources"]:
            assert s["status"] in ("valid", "stale", "fail", "listed", "excluded") and s["counted"] == (s["status"] == "valid")


# ---------- 2026-11-12 驗收補測：門檻、前 N、正值過濾、象限、E 走通、C／b stale、同來源去重、計票群組 ----------

def test_single_source_key_not_listed_and_dedupe_within_source():
    i = base_inp()
    i["tf"]["pages"]["sync"]["sync_buy"] += [{"code": "9904", "name": "只在 a"}, {"code": "9904", "name": "重複"},
                                             {"code": "8888", "name": "a 重複"}, {"code": "8888", "name": "a 重複"}]
    i["track"]["tracking"].append({"code": "8888", "name": "a 重複"})
    o = bo.build(i, "G")
    rows = {r["key"]: r for r in o["stocks"]["rows"]}
    assert "9904" not in rows                      # 只出現在一個來源（即使該來源內重複兩次）→ count 1 → 不上榜
    assert rows["8888"]["hits"] == ["a", "c"] and rows["8888"]["count"] == 2   # 同來源內重複鍵只記一次
    assert min(r["count"] for r in o["stocks"]["rows"]) == 2


def big_sr(npos=14, nneg=3):
    rows = [{"sector": f"正{k:02d}", "net_amt_k": (k + 1) * 1000, "n": 10} for k in range(npos)]
    rows += [{"sector": f"負{k:02d}", "net_amt_k": -(k + 1) * 1000, "n": 10} for k in range(nneg)]
    w = {"trading_days": 5, "end": "2026-11-12", "classifications": {"chain": {"investors": {"total": rows}}}}
    return {"date": "2026-11-12", "windows": {"r5": w, "r20": {**w, "trading_days": 20}}}


def test_src_A_top10_positive_only():
    a = bo.src_A(big_sr())
    assert [x["key"] for x in a["items"]] == [f"正{k:02d}" for k in range(13, 3, -1)]   # 金額遞減的前 10
    few = bo.src_A(big_sr(npos=3, nneg=5))
    assert [x["key"] for x in few["items"]] == ["正02", "正01", "正00"]                  # 不足 10 個時不拿負值補
    z = big_sr(npos=2, nneg=1)
    z["windows"]["r5"]["classifications"]["chain"]["investors"]["total"].append({"sector": "零", "net_amt_k": 0, "n": 10})
    assert [x["key"] for x in bo.src_A(z)["items"]] == ["正01", "正00"]                  # 0 不算淨買
    assert [x["key"] for x in src(bo.build(base_inp(), "G"), "sectors", "A")["items"]] == ["甲", "乙", "丙"]


def test_src_C_top10_positive_only():
    parents = {f"子{k:02d}": [f"業{k:02d}"] for k in range(14)}
    d = {"primary_date": "2026/11/12", "subs": [{"name": f"子{k:02d}", "val": k + 1} for k in range(14)] + [{"name": "負", "val": -99}]}
    c = bo.src_C(d, parents)
    assert c["subs"] == [f"子{k:02d}" for k in range(13, 3, -1)] and len(c["items"]) == 10
    assert sorted(x["key"] for x in c["items"]) == [f"業{k:02d}" for k in range(4, 14)]


def test_src_B_only_acc_in():
    s = sr()
    r5 = s["windows"]["r5"]["classifications"]["chain"]["investors"]["total"]
    r20 = s["windows"]["r20"]["classifications"]["chain"]["investors"]["total"]
    r5.append({"sector": "戊", "net_amt_k": 1000, "n": 10})        # 近 5 日日均 200
    r20.append({"sector": "戊", "net_amt_k": 80000, "n": 10})      # 近 20 日日均 4000 → 流入放緩（slow_in）
    r5.append({"sector": "己", "net_amt_k": 5000, "n": 10})
    r20.append({"sector": "己", "net_amt_k": -90000, "n": 10})     # 流出放緩（slow_out）
    r5.append({"sector": "庚", "net_amt_k": 90000, "n": 3})
    r20.append({"sector": "庚", "net_amt_k": 90000, "n": 3})       # n<8 不列
    q = {p["sector"]: p["q"] for p in bo.radar_points(s["windows"]["r5"], s["windows"]["r20"], "chain", "total")}
    assert q["戊"] == "slow_in" and q["己"] == "slow_out" and q["丁"] == "acc_out" and "庚" not in q
    assert {x["key"] for x in bo.src_B(s)["items"]} == {"甲", "乙", "丙"}


def test_src_E_through_build_with_real_series_fixture():
    series = load(FIX / "overview_series_tail.json")
    p = bo.rrgd_prep(series)
    t = p["valid"][-1]
    imp = bo.rrgd_persist_list(p["coords"], t, "改善", 3, 1)
    lead = bo.rrgd_persist_list(p["coords"], t, "領先", 3, 0)
    weak = bo.rrgd_persist_list(p["coords"], t, "轉弱", 3, 0)
    assert imp and lead and weak and not (set(weak) & set(lead))   # fixture 三種都有，才分得出換象限的突變
    i = base_inp()
    i["series"] = series
    names = list(series["chains"])
    i["sr"] = sr(end=series["dates"][t], pos=tuple(lead[:2]) + (names[0],))
    i["tf"]["date"] = series["dates"][t]
    o = bo.build(i, "G")
    e = src(o, "sectors", "E")
    assert e["status"] == "valid" and e["counted"] is True and e["date"] == series["dates"][t]
    assert {x["key"]: x["via"] for x in e["items"]} == {**{k: ["改善"] for k in imp}, **{k: ["領先"] for k in lead}}
    rows = {r["key"]: r for r in o["sectors"]["rows"]}
    for k in lead[:2]:                             # A（＋B 同組）＋E → 2 票
        assert rows[k]["count"] == 2 and rows[k]["hits"] == ["A", "B", "E"] and rows[k]["via"] == {"E": ["領先"]}
    assert not (set(weak) & set(rows))


def test_aetf_sources_stale_when_primary_date_differs():
    i = base_inp()
    i["diff"] = diff("2026/11/11")
    o = bo.build(i, "G")
    c, b = src(o, "sectors", "C"), src(o, "stocks", "b")
    assert c["date"] == b["date"] == "2026-11-11"
    assert c["status"] == b["status"] == "stale" and c["counted"] is False and b["counted"] is False
    assert all("C" not in r["hits"] for r in o["sectors"]["rows"]) and all("b" not in r["hits"] for r in o["stocks"]["rows"])
    assert o["sectors"]["rows"] == []              # 只剩 A、B（同組）→ 不輸出


def test_vote_groups():
    o = bo.build(base_inp(), "G")
    g = {s["id"]: s["group"] for s in o["sectors"]["sources"]}
    assert g["A"] == g["B"] == "flow" and len({g["C"], g["D"], g["E"], "flow"}) == 4
    assert src(o, "sectors", "A")["group_name"] == src(o, "sectors", "B")["group_name"] == "法人資金流"
    gs = [s["group"] for s in o["stocks"]["sources"]]
    assert len(gs) == len(set(gs))                 # 個股層各自成組
    assert all("group_name" not in s for s in o["stocks"]["sources"])
    # 只中 A 或只中 B 加上另一組，都是 2 票；A＋B 皆中再加另一組仍是 2 票（不是 3）
    i = base_inp()
    i["sr"] = sr(pos=("甲",))
    i["sr"]["windows"]["r5"]["classifications"]["chain"]["investors"]["total"].append({"sector": "乙", "net_amt_k": -5, "n": 10})
    i["sr"]["windows"]["r20"]["classifications"]["chain"]["investors"]["total"].append({"sector": "乙", "net_amt_k": 0, "n": 10})
    rows = {r["key"]: (r["count"], r["hits"]) for r in bo.build(i, "G")["sectors"]["rows"]}
    assert rows == {"甲": (2, ["A", "B", "C"])}     # 乙：r5 為負 → 不在 A；x=0、y<0 → 不在 B；只剩 C → 不上榜


# ====================== 資金流出側（2026-11-13，規格 docs/market-overview.md §6） ======================

def rich_inp():
    """base_inp＋真實形狀的 fixture（籌碼雷達 r5／r20、主動 ETF diff、輪動雷達序列），日期對齊到 2026-11-12"""
    i = base_inp()
    i["series"] = load(FIX / "overview_series_tail.json")
    i["diff"] = load(FIX / "overview_aetf_diff.json")
    s = load(FIX / "chipradar_sector_ranges_r5r20.json")
    s["date"] = "2026-11-12"
    s["windows"]["r5"]["end"] = "2026-11-12"
    i["sr"] = s
    return i


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def test_inflow_output_bit_identical_to_pre_out_golden():
    """流入側輸出逐位不變：golden＝加流出側之前（commit 23a2cbf）的 build() 對同一份輸入的輸出，含鍵的順序。"""
    g = load(FIX / "overview_inflow_golden.json")
    for name, inp in (("base", base_inp()), ("rich", rich_inp())):
        o = bo.build(inp, "G")
        assert list(o) == list(g[name]) + ["out"], name          # 只在最後新增 out
        out = o.pop("out")
        assert dumps(o) == dumps(g[name]), name
        assert set(out) == {"sectors", "stocks"}
    assert len(g["rich"]["sectors"]["rows"]) >= 1 and len(g["rich"]["stocks"]["rows"]) >= 1   # golden 不是空表


def test_inflow_unaffected_when_out_base_missing():
    b = bo.build(out_inp(), "G")
    i = out_inp()
    del i["tf"]["pages"]["sync"]["sync_sell"]
    c = bo.build(i, "G")
    assert dumps({k: v for k, v in b.items() if k != "out"}) == dumps({k: v for k, v in c.items() if k != "out"})
    assert b["side"] == "long" and b["schema"] == 1 and c["date"] == "2026-11-12" and c["stocks"]["rows"]
    # 流出側基準（同步賣超）缺 → 只有流出側個股表不輸出列，其餘來源無從比對資料日
    assert src(c["out"], "stocks", "a")["status"] == "fail" and c["out"]["stocks"]["rows"] == [] and c["out"]["stocks"]["base_date"] is None
    assert src(c["out"], "stocks", "b")["status"] == "stale" and c["out"]["sectors"]["rows"] == b["out"]["sectors"]["rows"]


def out_inp():
    """流出側合成輸入（流入側部分沿用 base_inp）。
    類股：乙、丙、丁 r5＝r20 皆負 → A′ 且 acc_out（B′）；己 r5 小負、r20 大負 → A′ 但 slow_out（不在 B′）；甲、戊為正。
    個股：2603＝a′,b′,d′,e′；1101＝a′,d′,e′（by 全為正 → 不是減碼共識）；2317＝只在 a′（b 只有 1 檔賣、d 為 Beat、e 為增加）。"""
    i = base_inp()
    r5 = [("甲", 100000), ("戊", 50000), ("乙", -100000), ("丙", -90000), ("丁", -80000), ("己", -50)]
    r20 = [("甲", 100000), ("戊", 50000), ("乙", -100000), ("丙", -90000), ("丁", -80000), ("己", -1000000)]
    w = lambda n, rows: {"trading_days": n, "end": "2026-11-12",  # noqa: E731
                         "classifications": {"chain": {"investors": {"total": [{"sector": k, "net_amt_k": v, "n": 10} for k, v in rows]}}}}
    i["sr"] = {"date": "2026-11-12", "windows": {"r5": w(5, r5), "r20": w(20, r20)}}
    i["classify"]["map"]["3"] = {"p": [["己", "己子"]]}
    i["diff"] = {"primary_date": "2026/11/12",
                 "subs": [{"name": "甲子", "val": 9}, {"name": "乙子", "val": -5}, {"name": "己子", "val": -4}, {"name": "共用", "val": -3}],
                 "stocks": [{"c": "2603", "n": "長榮", "by": {"A": -1, "B": -2, "C": 5}}, {"c": "2317", "n": "鴻海", "by": {"A": -1, "B": 3}},
                            {"c": "1101", "n": "台泥", "by": {"A": 1, "B": 2}}, {"c": "<img>", "n": "壞代號", "by": {"A": -1, "B": -1}}]}
    i["tf"]["pages"]["sync"]["sync_sell"] = [{"code": "1101", "name": "台泥"}, {"code": "2603", "name": "長榮"}, {"code": "2317", "name": "鴻海"}]
    i["rev"] = {"month": "2026-10", "rows": [{"code": "1101", "name": "台泥", "cls": "Miss"}, {"code": "2603", "name": "長榮", "cls": "低預期仍Miss"},
                                              {"code": "2317", "name": "鴻海", "cls": "Beat"}, {"code": "2330", "name": "台積電", "cls": "高預期仍Beat"},
                                              {"code": "2454", "name": "聯發科", "cls": "符合"}]}
    i["diag"] = {"stocks": {"2603": {"hdw": -0.3, "hdd": "2026-11-06", "n": "長榮"}, "1101": {"hdw": -0.1, "hdd": "2026-11-06", "n": "台泥"},
                            "2317": {"hdw": 0.5, "hdd": "2026-11-06", "n": "鴻海"}, "2330": {"hdw": 0.1, "hdd": "2026-11-06", "n": "台積電"}}}
    return i


def test_out_shape_sources_and_excluded():
    o = bo.build(out_inp(), "G")
    out = o["out"]
    assert set(out) == {"sectors", "stocks"} and "side" not in out and "label" not in out
    assert [s["id"] for s in out["sectors"]["sources"]] == ["A", "B", "C", "D", "E"]
    assert [s["id"] for s in out["stocks"]["sources"]] == ["a", "b", "c", "d", "e", "f"]
    for layer, sid in (("sectors", "D"), ("stocks", "c"), ("stocks", "f")):   # 無對應來源／不納入
        s = src(out, layer, sid)
        assert s["status"] == "excluded" and s["counted"] is False and s["items"] == [] and "不納入" in s["note"]
    names = " ".join(s["name"] + s.get("note", "") for layer in ("sectors", "stocks") for s in out[layer]["sources"])
    assert "淨賣" in names and "加速流出" in names and "減碼" in names and "同步賣超" in names and "週減" in names and "Miss" in names
    assert not any(w in dumps(out) for w in ("放空", "做空", "賣出建議"))
    assert out["sectors"]["base_date"] == out["stocks"]["base_date"] == "2026-11-12"
    for layer in ("sectors", "stocks"):
        for s in out[layer]["sources"]:
            assert s["counted"] == (s["status"] == "valid")


def test_out_count_sort_and_groups():
    o = bo.build(out_inp(), "G")
    out = o["out"]
    assert [x["key"] for x in src(out, "sectors", "A")["items"]] == ["乙", "丙", "丁", "己"]      # 淨賣金額（絕對值）遞減；正值不收
    assert {x["key"] for x in src(out, "sectors", "B")["items"]} == {"乙", "丙", "丁"}            # 只有 acc_out；己是 slow_out、甲戊是流入
    c = src(out, "sectors", "C")
    assert c["subs"] == ["乙子", "己子", "共用"] and c["unmapped"] == ["共用"]                    # 減碼金額遞減；加碼的甲子不收
    assert c["items"] == [{"key": "乙", "via": ["乙子"]}, {"key": "己", "via": ["己子"]}]
    g = {s["id"]: s["group"] for s in out["sectors"]["sources"]}
    assert g["A"] == g["B"] == "flow" and src(out, "sectors", "A")["group_name"] == src(out, "sectors", "B")["group_name"] == "法人資金流"
    # 乙：A′＋B′（同組 1 票）＋C′ → 2 票（不是 3）；己：A′＋C′ → 2 票；丙、丁只中 A′＋B′（同組）→ 1 票 → 不上榜
    assert [(r["key"], r["count"], r["hits"]) for r in out["sectors"]["rows"]] == [("乙", 2, ["A", "B", "C"]), ("己", 2, ["A", "C"])]
    assert out["sectors"]["rows"][0]["via"] == {"C": ["乙子"]}
    # 個股
    assert [x["key"] for x in src(out, "stocks", "a")["items"]] == ["1101", "2603", "2317"]
    assert [x["key"] for x in src(out, "stocks", "b")["items"]] == ["2603"]                       # by 為負的 ETF ≥2；壞代號丟棄
    assert [x["key"] for x in src(out, "stocks", "d")["items"]] == ["1101", "2603"]               # Miss／低預期仍Miss
    assert [x["key"] for x in src(out, "stocks", "e")["items"]] == ["2603", "1101"]               # hdw<0 由小到大
    assert [(r["key"], r["name"], r["count"], r["hits"]) for r in out["stocks"]["rows"]] == [
        ("2603", "長榮", 4, ["a", "b", "d", "e"]), ("1101", "台泥", 3, ["a", "d", "e"])]
    assert all(r["key"] != "2317" for r in out["stocks"]["rows"])                                 # 只中 a′ 一個來源 → 不上榜
    assert all(r["count"] >= 2 for r in out["sectors"]["rows"] + out["stocks"]["rows"])
    gs = [s["group"] for s in out["stocks"]["sources"]]
    assert len(gs) == len(set(gs))


def test_out_only_flow_group_outputs_no_rows():
    i = out_inp()
    i["diff"] = ValueError("x")
    out = bo.build(i, "G")["out"]
    assert out["sectors"]["rows"] == [] and "計票群組只有 1 個" in out["sectors"]["note"]   # 只剩 A′、B′（同組）


def test_out_src_A_C_top10_negative_only():
    a = bo.src_A(big_sr(npos=3, nneg=14), "out")
    assert [x["key"] for x in a["items"]] == [f"負{k:02d}" for k in range(13, 3, -1)]             # 淨賣金額遞減的前 10
    assert [x["key"] for x in bo.src_A(big_sr(npos=5, nneg=3), "out")["items"]] == ["負02", "負01", "負00"]   # 不足 10 個不拿正值補
    z = big_sr(npos=2, nneg=1)
    z["windows"]["r5"]["classifications"]["chain"]["investors"]["total"].append({"sector": "零", "net_amt_k": 0, "n": 10})
    assert [x["key"] for x in bo.src_A(z, "out")["items"]] == ["負00"]                            # 0 不算淨賣
    parents = {f"子{k:02d}": [f"業{k:02d}"] for k in range(14)}
    d = {"primary_date": "2026/11/12", "subs": [{"name": f"子{k:02d}", "val": -(k + 1)} for k in range(14)] + [{"name": "正", "val": 99}]}
    c = bo.src_C(d, parents, "out")
    assert c["subs"] == [f"子{k:02d}" for k in range(13, 3, -1)] and len(c["items"]) == 10
    assert bo.src_C(d, parents, "in")["subs"] == ["正"]


def test_out_src_B_only_acc_out():
    s = out_inp()["sr"]
    q = {p["sector"]: p["q"] for p in bo.radar_points(s["windows"]["r5"], s["windows"]["r20"], "chain", "total")}
    assert q == {"甲": "acc_in", "戊": "acc_in", "乙": "acc_out", "丙": "acc_out", "丁": "acc_out", "己": "slow_out"}
    assert {x["key"] for x in bo.src_B(s, "out")["items"]} == {"乙", "丙", "丁"}
    assert {x["key"] for x in bo.src_B(s, "in")["items"]} == {"甲", "戊"}
    # acc_out 保證近 5 日淨額 <0（A′、B′ 併組的依據）：真實形狀 fixture 上逐一驗
    f = load(FIX / "chipradar_sector_ranges_r5r20.json")
    pts = [p for p in bo.radar_points(f["windows"]["r5"], f["windows"]["r20"], "chain", "total") if p["q"] == "acc_out"]
    assert pts and all(p["v5"] < 0 for p in pts)


def test_out_src_E_weak_or_lagging_through_build():
    series = load(FIX / "overview_series_tail.json")
    p = bo.rrgd_prep(series)
    t = p["valid"][-1]
    lists = {q: bo.rrgd_persist_list(p["coords"], t, q, 3, 1) for q in ("改善", "領先", "轉弱", "落後")}
    assert all(lists.values())                               # fixture 四個象限都有，才分得出取錯象限的突變
    e = bo.src_E(series, "out")
    assert {x["key"]: x["via"] for x in e["items"]} == {**{k: ["轉弱"] for k in lists["轉弱"]}, **{k: ["落後"] for k in lists["落後"]}}
    assert not ({x["key"] for x in e["items"]} & set(lists["改善"] + lists["領先"]))
    i = out_inp()
    i["series"] = series
    weak = lists["轉弱"][0]
    i["sr"]["windows"]["r5"]["classifications"]["chain"]["investors"]["total"].append({"sector": weak, "net_amt_k": -70000, "n": 10})
    i["sr"]["windows"]["r5"]["end"] = series["dates"][t]
    out = bo.build(i, "G")["out"]
    assert src(out, "sectors", "E")["status"] == "valid"
    rows = {r["key"]: r for r in out["sectors"]["rows"]}
    assert rows[weak]["hits"] == ["A", "E"] and rows[weak]["count"] == 2 and rows[weak]["via"] == {"E": ["轉弱"]}


def test_out_stale_and_windows():
    i = out_inp()
    i["diff"]["primary_date"] = "2026/11/11"
    i["rev"]["month"] = "2026-08"
    for s in i["diag"]["stocks"].values():
        s["hdd"] = "2026-10-30"
    out = bo.build(i, "G")["out"]
    for layer, sid in (("sectors", "C"), ("stocks", "b"), ("stocks", "d"), ("stocks", "e")):
        s = src(out, layer, sid)
        assert s["status"] == "stale" and s["counted"] is False and s["ok"] is True
    assert out["sectors"]["rows"] == [] and out["stocks"]["rows"] == [] and "少於 2 個" in out["stocks"]["note"]


def test_main_writes_out_in_latest_and_daily(tmp_path):
    root = make_tree(tmp_path, out_inp())
    assert bo.main(["--root", str(root), "--src-root", str(tmp_path)]) == 0
    a, d = load(root / "data/overview/latest.json"), load(root / "data/overview/daily/2026-11-12.json")
    assert a == d and a["schema"] == 1 and a["side"] == "long"
    assert [r["key"] for r in a["out"]["stocks"]["rows"]] == ["2603", "1101"] and [r["key"] for r in a["out"]["sectors"]["rows"]] == ["乙", "己"]


@pytest.mark.skipif(not (SIB / "taiwan-flows/data/latest.json").exists(), reason="無姊妹 repo 本機 checkout")
def test_out_real_sibling_key_names():
    """§6.1 的實檔核對：賣方清單鍵名、淨額正負與方向（鍵名改了這裡會紅）"""
    tf = load(SIB / "taiwan-flows/data/latest.json")
    rows = tf["pages"]["sync"]["sync_sell"]
    assert rows and all(r["t_amt_k"] < 0 and r["f_amt_k"] < 0 for r in rows)
    assert all(r["t_amt_k"] > 0 and r["f_amt_k"] > 0 for r in tf["pages"]["sync"]["sync_buy"])
    m = load(SIB / "taiwan-flow-live-v2/data/morning.json")
    assert set(m["signals"]) == {"cont_subs", "new_subs", "dual"}     # 沒有退潮類訊號 → D′ 無對應來源；多了鍵就要回頭檢討
