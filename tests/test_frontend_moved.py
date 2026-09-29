#!/usr/bin/env python3
# tests/test_frontend_moved.py
# 2026-09-28 搬來的兩個 tab（籌碼雷達 chipradar／社群聲量 social）的前端守門（驗收條件正本 docs/move-radar-social.md）：
#   ①代跑 tests/test_chipradar.mjs（籌碼雷達純函式 17 項，原站 taiwan-flows tests/test_radar.mjs 的案例）
#   ②hash 新 key 白名單：從 index.html 抽出 TABS／HASH_*／parseHash／currentHash 在 node 沙箱跑
#     （rcls／rinv 只在 tab=chipradar、sd 只在 tab=social；非法值靜默丟棄；既有 tab／code／sub／stock 不受影響）
#   ③首屏不多載：load() 與首屏路徑不碰兩個 tab 的資料 URL
# 用法：python -m pytest tests/ -q（需要 node；免網路、免 token）

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INDEX = os.path.join(ROOT, "index.html")


def _html() -> str:
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.fail("找不到 node：本測試需要 node 執行 index.html 抽出的前端函式")
    return node


def _pick_const(s: str, name: str) -> str:
    """抽 `const NAME = …;`：單行直接取；多行（陣列）取到第一個 `];`。"""
    i = s.index(f"const {name} = ")
    line_end = s.index("\n", i)
    line = s[i:line_end]
    if line.rstrip().endswith(";"):
        return line
    j = s.index("];", i)
    return s[i:j + 2]


def _pick_func(s: str, name: str) -> str:
    start = s.index(f"function {name}(")
    open_ = s.index("{", start)
    depth, in_str, i = 0, None, open_
    while i < len(s):
        c = s[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
        i += 1
    raise AssertionError(f"function {name} 大括號未配對")


def test_chipradar_pure_functions():
    out = subprocess.run([_node(), os.path.join(ROOT, "tests", "test_chipradar.mjs")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "17 項全部通過" in out.stdout


HASH_HARNESS = r"""
const R = {};
const parse = h => { location.hash = h; return parseHash(); };
R.crOk = parse("#tab=chipradar&rcls=chain&rinv=trust");
R.crBad = parse("#tab=chipradar&rcls=%3Cimg%3E&rinv=all");
R.crOtherTab = parse("#tab=lending&code=2330&rcls=chain&rinv=trust&sd=2026-09-27");
R.sdOk = parse("#tab=social&sd=2026-09-27");
R.sdBad = [parse("#tab=social&sd=2026-9-27"), parse("#tab=social&sd=%3Cscript%3E"), parse("#tab=social&sd=2026-09-27x")];
R.sdOnCr = parse("#tab=chipradar&sd=2026-09-27");
R.oldRadar = parse("#tab=radar&rcls=chain");
R.mychg = parse("#tab=mychg");
R.stock = parse("#tab=social&stock=2330&sd=2026-09-27");
R.tabs = [...HASH_TABS];
// currentHash：只放非預設值、只在各自的 tab 寫出
const cur = (tab, cr, soc) => { state.tab = tab; Object.assign(CR, cr || {}); Object.assign(SOCIAL, soc || {}); return currentHash(); };
R.curCrDef = cur("chipradar", {rcls:"exchange", rinv:"total"});
R.curCr = cur("chipradar", {rcls:"chain", rinv:"dealer"});
R.curCrOnOther = cur("screen");
R.curSocLatest = cur("social", {rcls:"exchange", rinv:"total"}, {days:["2026-09-28","2026-09-27"], date:"2026-09-28", hashSd:null});
R.curSocOld = cur("social", {}, {date:"2026-09-27"});
R.curSocPending = cur("social", {}, {days:null, date:null, hashSd:"2026-09-20"});
R.curSocPendingBad = cur("social", {}, {days:null, date:null, hashSd:"<x>"});
process.stdout.write(JSON.stringify(R));
"""


@pytest.fixture(scope="module")
def H():
    s = _html()
    src = "\n".join([
        _pick_const(s, "TABS"), "const HASH_TABS = new Set(TABS.map(t => t[0]));",
        _pick_const(s, "HASH_SUBS"), _pick_const(s, "HASH_CODE_RE"),
        _pick_const(s, "HASH_CR"), _pick_const(s, "HASH_SD_RE"),
        _pick_func(s, "parseHash"), _pick_func(s, "currentHash"),
    ])
    stub = ("const location = {hash:''}; const BK_RES = {};"
            "const state = {tab:'insight', oddSub:'intraday', bkSub:'branch', openLend:null, diagOpen:null, stkOpen:null};"
            "const CR = {rcls:'exchange', rinv:'total'}; const SOCIAL = {days:null, date:null, hashSd:null};")
    out = subprocess.run([_node(), "-e", stub + "\n" + src + "\n" + HASH_HARNESS],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_hash_tabs_include_moved(H):
    assert len(H["tabs"]) == 17   # 2026-09-29 加市場情緒 sentiment（排在 social 之後、dates 之前）
    assert H["tabs"][-4:] == ["chipradar", "social", "sentiment", "dates"]
    assert "mychg" in H["tabs"] and "radar" not in H["tabs"]


def test_hash_chipradar_keys(H):
    assert H["crOk"] == {"tab": "chipradar", "rcls": "chain", "rinv": "trust"}
    assert H["crBad"] == {"tab": "chipradar"}           # 非法值靜默丟棄
    assert H["crOtherTab"] == {"tab": "lending", "code": "2330"}   # 新 key 只屬於各自的 tab
    assert H["sdOnCr"] == {"tab": "chipradar"}


def test_hash_social_sd(H):
    assert H["sdOk"] == {"tab": "social", "sd": "2026-09-27"}
    assert H["sdBad"] == [{"tab": "social"}] * 3
    assert H["stock"] == {"tab": "social", "stock": "2330", "sd": "2026-09-27"}


def test_hash_existing_unchanged(H):
    assert H["mychg"] == {"tab": "mychg"}                # 入口站深連結 #tab=mychg 仍有效
    assert H["oldRadar"] == {}                           # 原站舊值不在白名單 → 退回預設


def test_current_hash_writes_only_non_default(H):
    assert H["curCrDef"] == "#tab=chipradar"
    assert H["curCr"] == "#tab=chipradar&rcls=chain&rinv=dealer"
    assert H["curCrOnOther"] == "#tab=screen"            # 離開本 tab 不帶 rcls／rinv
    assert H["curSocLatest"] == "#tab=social"            # 最新一天＝預設，不寫 sd
    assert H["curSocOld"] == "#tab=social&sd=2026-09-27"
    assert H["curSocPending"] == "#tab=social&sd=2026-09-20"   # 清單未到前保留網址原值
    assert H["curSocPendingBad"] == "#tab=social"


def test_first_screen_does_not_touch_moved_data():
    s = _html()
    load = _pick_func(s, "load")
    for name in ("crRender", "crEnsureSr", "loadSocial", "CR_SECT_URL", "SOCIAL_BASE"):
        assert name not in load
    assert 'const CR_SECT_URL = "../taiwan-flows/data/sector_ranges_lite.json";' in s
    # 兩個資料 URL 各只在自己的 lazy 載入函式裡用到
    assert s.count("loadJSON(CR_SECT_URL)") == 1 and "function crEnsureSr()" in s
    assert re.search(r'else if \(state\.tab === "chipradar"\) crRender\(\);', s)
