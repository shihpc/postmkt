#!/usr/bin/env python3
# tests/test_pick2_build.py —— 選股二追蹤名單後端 src/build_pick2.py（2026-10-19）
# ①parity：Python pk2_score 與 index.html pick2-pure 的 pk2Score（經 pk2Rows 組列）逐位相同（node 抽碼對跑）
# ②選入門檻邊界、刪除不自動選回、手動加入、冪等、ret／pool_ret／mdd 手算、失敗不寫檔
# 免網路、免 token（universe 以本機檔注入）。
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import build_pick2 as bp

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "pick2_parity.json"


def node_scores(diag, screen, codes):
    node = shutil.which("node")
    if not node:
        pytest.fail("找不到 node：parity 測試需要 node 執行 index.html 抽出的 pk2Score")
    out = subprocess.run([node, str(ROOT / "tests" / "pick2_score_node.mjs")],
                         input=json.dumps({"diag": diag, "screen": screen, "codes": codes}),
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def py_scores(diag, screen, codes):
    sc = {r["code"]: r for r in screen["rows"] if isinstance(r, dict) and isinstance(r.get("code"), str)}
    out = {}
    for c in codes:
        s, n = bp.pk2_score(bp.tw_row(c, diag["stocks"].get(c), sc.get(c)))
        out[c] = {"score": s, "n": n}
    return out


def same(a, b):
    """逐位相同：同為 None，或同為有限數且 float 表示完全相同"""
    if a is None or b is None:
        return a is None and b is None
    return float(a).hex() == float(b).hex()


def assert_parity(diag, screen, codes):
    js, py = node_scores(diag, screen, codes), py_scores(diag, screen, codes)
    assert set(js) == set(py) == set(codes)
    bad = [(c, js[c], py[c]) for c in codes if not (same(js[c]["score"], py[c]["score"]) and js[c]["n"] == py[c]["n"])]
    assert bad == []
    return js


def test_parity_fixture():
    f = json.loads(FIX.read_text(encoding="utf-8"))
    js = assert_parity(f["diag"], f["screen"], f["codes"])
    # 人造邊界例的預期值（手算）
    assert js["9901"] == {"score": 56.3, "n": 5}     # 56.25 → half-up；Python round() 會得 56.2
    assert round(56.25, 1) == 56.2                    # 佐證：不可用 Python round()
    assert js["9902"] == {"score": 43.8, "n": 5}
    assert js["9903"]["n"] == 1 and js["9903"]["score"] == 100   # hd 退算 +0.5pp → +1
    assert js["9904"] == {"score": None, "n": 0}
    assert js["9905"] == {"score": 66.7, "n": 2}     # ma20 +1×1、mg5=5 → 0×2：50+50/3
    assert js["9910"] == {"score": 100, "n": 2}      # up 120/100 浮點 19.999…→ 捨 1e-6 後 20% → +1×2；buyr 0.75 → +1×1
    assert js["9911"] == {"score": 83.3, "n": 2}     # up 10% → +0.5×2；buyr 恰 0.7 → +1×1：50+50×2/3
    assert js["9909"] == {"score": None, "n": 0}     # px=0 → up 缺；rating 缺
    assert js["9915"] == {"score": None, "n": 0}


def test_parity_real_data():
    diag = json.loads((ROOT / "data/diag/diag.json").read_text(encoding="utf-8"))
    screen = json.loads((ROOT / "data/screen/screen.json").read_text(encoding="utf-8"))
    codes = sorted(set(diag["stocks"]) | {r["code"] for r in screen["rows"]})
    assert len(codes) >= 1000
    assert_parity(diag, screen, codes)


def test_spec_matches_index():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    blk = html[html.index("const PK2_SCORE_SPEC = ["):]
    blk = blk[:blk.index("];")]
    js = [(m.group(1), int(m.group(2))) for m in re.finditer(r'\{ k: "(\w+)", cat: "[^"]+", label: "[^"]+", w: (\d+)', blk)]
    assert js == bp.SCORE_SPEC


def test_js_round_half_up():
    assert bp.js_round(562.5) == 563 and bp.js_round(-0.5) == 0 and bp.js_round(-1.5) == -1 and bp.js_round(2.4999) == 2
    assert bp.js_round(0.49999999999999994) == 0   # floor(x+0.5) 的經典陷阱：JS Math.round 得 0


# ---------- build() 規則 ----------

def mk(scores: dict, closes: dict | None = None):
    """以 monkeypatch 用的分數表造輸入：scores＝{code:(score, n)}；closes＝{code: c}"""
    closes = closes or {}
    diag = {"date": "x", "stocks": {c: {"c": closes.get(c, 100.0)} for c in scores}}
    return diag, {"rows": []}, [(c, "名" + c) for c in scores]


@pytest.fixture
def fake_score(monkeypatch):
    table = {}
    monkeypatch.setattr(bp, "pk2_score", lambda r: table.get(r["code"], (None, 0)))
    return table


def run(date, scores, fake, user=None, prev=None, snaps=None, closes=None):
    fake.clear()
    fake.update(scores)
    diag, screen, uni = mk(scores, closes)
    return bp.build(date, uni, diag, screen, user or {}, prev, snaps or {}, "2026-10-19T22:00:00+08:00")


def test_threshold_boundaries(fake_score):
    _, tr = run("2026-10-19", {"1101": (79.9, 12), "1102": (80.0, 12), "1103": (80.0, 8), "1104": (95.0, 9), "1105": (None, 0)}, fake_score)
    assert [t["code"] for t in tr["tracking"]] == ["1102", "1104"]
    assert [x["code"] for x in tr["new_today"]] == ["1102", "1104"]
    assert all(t["src"] == "auto" and t["since"] == "2026-10-19" for t in tr["tracking"])
    assert tr["rule"] == {"min_score": 80, "min_items": 9} and tr["spec"] == "pick2-score-v1" and tr["schema"] == 1
    assert set(tr) == {"schema", "date", "generated_at", "rule", "spec", "tracking", "new_today", "deleted"}
    assert set(tr["tracking"][0]) == {"code", "name", "src", "since", "entry_close", "entry_score", "last_close", "last_score",
                                      "ret", "pool_ret", "mdd", "days"}
    assert set(tr["new_today"][0]) == {"code", "name", "src", "score"}


def test_no_auto_removal_and_delete_not_reselected(fake_score):
    d1, t1 = run("2026-10-19", {"1101": (85.0, 12), "1102": (90.0, 12)}, fake_score)
    # 隔日分數掉到門檻下：不自動移出；使用者刪除 1102 → 不再選回（即使仍 ≥80）
    d2, t2 = run("2026-10-20", {"1101": (40.0, 12), "1102": (99.0, 12)}, fake_score,
                 user={"1102": "del"}, prev=t1, snaps={"2026-10-19": d1})
    assert [t["code"] for t in t2["tracking"]] == ["1101"]
    assert t2["tracking"][0]["since"] == "2026-10-19" and t2["tracking"][0]["last_score"] == 40.0
    assert t2["new_today"] == [] and t2["deleted"] == ["1102"]
    # 再過一天仍不選回
    _, t3 = run("2026-10-21", {"1101": (40.0, 12), "1102": (99.0, 12)}, fake_score,
                user={"1102": "del"}, prev=t2, snaps={"2026-10-19": d1, "2026-10-20": d2})
    assert [t["code"] for t in t3["tracking"]] == ["1101"]


def test_manual_add(fake_score):
    d1, t1 = run("2026-10-19", {"1101": (10.0, 3)}, fake_score, user={"1101": "del"})
    assert t1["tracking"] == []
    # 手動加入解除刪除：since＝加入後第一次建置日、src manual、列入 new_today
    _, t2 = run("2026-10-20", {"1101": (12.0, 3)}, fake_score, user={"1101": "add"}, prev=t1, snaps={"2026-10-19": d1})
    assert [(t["code"], t["src"], t["since"]) for t in t2["tracking"]] == [("1101", "manual", "2026-10-20")]
    assert t2["new_today"] == [{"code": "1101", "name": "名1101", "src": "manual", "score": 12.0}]
    assert t2["deleted"] == []


def test_manual_add_outside_pool_goes_to_extra(fake_score):
    d, tr = run("2026-10-19", {"1101": (10.0, 3)}, fake_score, user={"2330": "add"})
    assert "2330" in d.get("extra", {}) and "2330" not in d["rows"]
    t = tr["tracking"][0]
    assert t["code"] == "2330" and t["src"] == "manual" and t["entry_close"] is None and t["ret"] is None


def test_idempotent_same_date(fake_score):
    d1, t1 = run("2026-10-19", {"1101": (85.0, 12)}, fake_score)
    d2, t2 = run("2026-10-20", {"1101": (85.0, 12), "1102": (81.0, 10)}, fake_score, prev=t1, snaps={"2026-10-19": d1})
    # 同 date 重跑：以 t2 當 prev 再跑一次，結果相同；new_today 只列本 date 首次列入
    d3, t3 = run("2026-10-20", {"1101": (85.0, 12), "1102": (81.0, 10)}, fake_score, prev=t2, snaps={"2026-10-19": d1, "2026-10-20": d2})
    assert t3 == t2 and d3 == d2
    assert [x["code"] for x in t2["new_today"]] == ["1102"]


def test_metrics_hand_calc(fake_score):
    s = {"1101": (85.0, 12), "1102": (10.0, 3)}
    d1, t1 = run("2026-10-19", s, fake_score, closes={"1101": 100.0, "1102": 50.0})
    d2, t2 = run("2026-10-20", s, fake_score, prev=t1, snaps={"2026-10-19": d1}, closes={"1101": 120.0, "1102": 55.0})
    d3, t3 = run("2026-10-21", s, fake_score, prev=t2, snaps={"2026-10-19": d1, "2026-10-20": d2},
                 closes={"1101": 90.0, "1102": 60.0})
    t = t3["tracking"][0]
    assert t["entry_close"] == 100.0 and t["last_close"] == 90.0
    assert t["ret"] == -0.1                    # 90/100−1
    assert t["pool_ret"] == 0.05               # (90/100−1 ＋ 60/50−1)/2 ＝(−0.1＋0.2)/2
    assert t["mdd"] == -0.25                   # 前高 120 → 90
    assert t["days"] == 2
    assert t["entry_score"] == 85.0 and t["last_score"] == 85.0


# ---------- main()：失敗不寫檔 ----------

def setup_root(tmp_path: Path, user=None):
    (tmp_path / "data/diag").mkdir(parents=True)
    (tmp_path / "data/screen").mkdir(parents=True)
    (tmp_path / "data/diag/diag.json").write_text(json.dumps({"date": "2026-10-19", "stocks": {"2330": {"c": 1000.0, "ma20": 1}}}), encoding="utf-8")
    (tmp_path / "data/screen/screen.json").write_text(json.dumps({"date": "2026-10-19", "rows": []}), encoding="utf-8")
    uni = tmp_path / "uni.json"
    uni.write_text(json.dumps({"TW": [{"code": "2330", "name": "台積電"}], "US": []}), encoding="utf-8")
    if user is not None:
        (tmp_path / "data/pick2").mkdir(parents=True)
        (tmp_path / "data/pick2/user.json").write_text(user, encoding="utf-8")
    return uni


def test_main_ok_and_contract(tmp_path):
    uni = setup_root(tmp_path, user=json.dumps({"schema": 1, "log": [{"act": "add", "code": "2330", "at": "2026-10-19T01:00:00Z"}]}))
    assert bp.main(["--root", str(tmp_path), "--universe", str(uni)]) == 0
    d = json.loads((tmp_path / "data/pick2/daily/2026-10-19.json").read_text(encoding="utf-8"))
    assert d["schema"] == 1 and d["date"] == "2026-10-19" and d["spec"] == "pick2-score-v1"
    assert d["rows"]["2330"] == {"name": "台積電", "c": 1000.0, "score": 100.0, "n": 1}
    t = json.loads((tmp_path / "data/pick2/track.json").read_text(encoding="utf-8"))
    assert [x["code"] for x in t["tracking"]] == ["2330"] and t["tracking"][0]["src"] == "manual"


@pytest.mark.parametrize("bad", ["universe", "user"])
def test_main_failure_writes_nothing(tmp_path, bad):
    uni = setup_root(tmp_path, user="{broken" if bad == "user" else None)
    arg = str(tmp_path / "nope.json") if bad == "universe" else str(uni)
    assert bp.main(["--root", str(tmp_path), "--universe", arg]) != 0
    assert not (tmp_path / "data/pick2/track.json").exists()
    assert not (tmp_path / "data/pick2/daily").exists()


def test_parse_user_last_wins_and_shape():
    st = bp.parse_user({"schema": 1, "log": [{"act": "add", "code": "2330"}, {"act": "del", "code": "2330"},
                                             {"act": "x", "code": "2317"}, {"act": "add", "code": "<img>"}, {"act": "add", "code": "00981a"}]})
    assert st == {"2330": "del", "00981A": "add"}
    for bad in [[], {"schema": 2, "log": []}, {"schema": True, "log": []}, {"schema": 1}]:
        with pytest.raises(ValueError):
            bp.parse_user(bad)
