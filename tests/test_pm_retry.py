#!/usr/bin/env python3
# tests/test_pm_retry.py
# postmkt.json 整檔載入失敗的重試守門（2026-10-11）。原本 ensurePm() 失敗一次就把 state.pmErr 設成 sticky、
# 整個分頁期間不再抓；檔頭 4KB（ensurePmHead）成功時頂列照常顯示資料日／狀態，各盤後 tab 卻永久
# 「尚無盤後資料」，只有重新整理才救得回來。
#   ①node 沙箱：從 index.html 抽出 PM_RETRY_MS／ensurePm／pmUserRender 跑狀態機（CI 會跑，免瀏覽器）
#   ②Playwright（本機有 playwright＋Chromium 才跑，CI 無 → skip）：真頁面端到端
#     a) 整檔第一次失敗、第二次成功 → 不需重新整理即自動恢復，頂列失敗附註消失
#     b) 整檔一直失敗 → 重試有上限（共 4 次請求）、最後顯示失敗文案＋頂列附註、無未捕捉錯誤；
#        之後使用者再點需要 pm 的 tab 會重開一輪；375px 無水平捲軸
#     c) 檔頭 Range 請求走 cache:"no-store"
#     d) 正常情況 17 tab 逐一點擊 console error／pageerror 為 0
# 用法：python -m pytest tests/ -q（需要 node；免網路、免 token）

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from urllib.parse import urlparse

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INDEX = os.path.join(ROOT, "index.html")
FIX = os.path.join(ROOT, "tests", "fixtures")


def _html() -> str:
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


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


def _pick_line(s: str, prefix: str) -> str:
    i = s.index(prefix)
    return s[i:s.index("\n", i)]


# ---------------------------------------------------------------- ① node 沙箱
SANDBOX = r"""
const out = [];
const ok = (c, m) => { if (!c) { console.log("FAIL " + m); process.exitCode = 1; } else out.push(m); };
let timers = [], reqs = 0, plan = [];
const setTimeout = (fn, ms) => { const t = { fn, ms, id: timers.length + 1 }; timers.push(t); return t.id; };
const clearTimeout = id => { timers = timers.filter(t => t.id !== id); };
const fire = () => { const t = timers.shift(); t.fn(); return t.ms; };
const state = { tab: "lending", pm: null, pmErr: null, pmFail: 0 };
const loadJSON = () => { reqs++; const r = plan.shift(); return r === "ok" ? Promise.resolve({ date: "2026-10-08" }) : Promise.reject(new Error("net")); };
const augmentLending = () => {}, buildBkNm = () => {}, renderTopbar = () => {};
// 同真的 render()：需要 pm 的 tab 每次重繪都會呼叫 ensurePm()（finally 也會 render → 必須不會無限重抓）
let renders = 0;
function render(){ renders++; if (state.tab !== "aetf") ensurePm(); }
let PM_P = null;
__PICKED__
const tick = () => new Promise(r => setImmediate(r));
(async () => {
  // A：第一次失敗、第一次重試成功
  plan = ["fail", "ok"];
  await ensurePm(); await tick();
  ok(reqs === 1 && state.pmFail === 1 && state.pmErr === null && !state.pm && timers.length === 1, "A1 首次失敗→pmErr 仍 null、排一次重試");
  ok(timers[0].ms === PM_RETRY_MS[0], "A2 第一次重試間隔＝PM_RETRY_MS[0]");
  render(); render(); await tick();
  ok(reqs === 1, "A3 退避等待中 render() 不提前打請求");
  fire(); await tick(); await tick();
  ok(reqs === 2 && state.pm && state.pmFail === 0 && state.pmErr === null && timers.length === 0, "A4 重試成功→state.pm 就緒、計數歸零");

  // B：一直失敗 → 共 1+N 次請求後放棄；之後 render() 不再抓；使用者動作重開一輪
  state.pm = null; reqs = 0; timers = [];
  plan = Array(20).fill("fail");
  await ensurePm(); await tick();
  const gaps = [];
  while (timers.length){ gaps.push(fire()); await tick(); await tick(); }
  ok(reqs === PM_RETRY_MS.length + 1, "B1 請求總數＝1＋重試次數 (" + reqs + ")");
  ok(JSON.stringify(gaps) === JSON.stringify(PM_RETRY_MS), "B2 間隔依序遞增 " + JSON.stringify(gaps));
  ok(state.pmErr instanceof Error && state.pmFail === PM_RETRY_MS.length + 1, "B3 用盡後才設 pmErr");
  for (let i = 0; i < 5; i++) render(); await tick();
  ok(reqs === PM_RETRY_MS.length + 1 && timers.length === 0, "B4 用盡後 render() 不自動重抓（無無限迴圈）");
  state.tab = "aetf"; pmUserRender(); await tick();
  ok(reqs === PM_RETRY_MS.length + 1 && state.pmErr, "B5 切到不需要 pm 的 tab 不重抓");
  state.tab = "lending"; plan = ["ok"]; pmUserRender(); await tick(); await tick();
  ok(reqs === PM_RETRY_MS.length + 2 && state.pm && state.pmErr === null && state.pmFail === 0, "B6 切回需要 pm 的 tab→重開一輪並成功");

  // C：in-flight 去重見 test_inflight_dedup
  state.pm = null; reqs = 0; timers = [];
  // D：退避等待中使用者動作 → 取消計時、立即打下一次（不重開計數）
  plan = ["fail", "fail"];
  await ensurePm(); await tick();
  ok(state.pmFail === 1 && timers.length === 1, "D1 首次失敗排重試");
  pmUserRender(); await tick(); await tick();
  ok(reqs === 2 && state.pmFail === 2 && timers.length === 1 && timers[0].ms === PM_RETRY_MS[1], "D2 使用者動作提前重試、計數延續");
  console.log(out.length + " 項通過");
})();
"""

DEDUP = r"""
let n = 0, rel;
const setTimeout = () => 0, clearTimeout = () => {};
const state = { tab: "lending", pm: null, pmErr: null, pmFail: 0 };
const loadJSON = () => { n++; return new Promise(r => { rel = r; }); };
const augmentLending = () => {}, buildBkNm = () => {}, renderTopbar = () => {}, render = () => {};
let PM_P = null;
__PICKED__
const a = ensurePm(), b = ensurePm();
PM_USER = true; const c = ensurePm(); PM_USER = false;  // 使用者動作也不得在 in-flight 時另發一個
if (n !== 1 || a !== b || a !== c) { console.log("FAIL dedup n=" + n); process.exitCode = 1; }
else console.log("dedup ok");
rel({});
"""


def _picked() -> str:
    s = _html()
    return "\n".join([
        _pick_line(s, "const PM_RETRY_MS = "),
        _pick_line(s, "let PM_RT = null, PM_USER = false;"),
        _pick_func(s, "ensurePm"),
        _pick_func(s, "pmUserRender"),
    ])


def _run_node(code: str) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    if not node:
        pytest.fail("找不到 node：本測試需要 node 執行 index.html 抽出的前端函式")
    return subprocess.run([node, "-e", code], capture_output=True, text=True, timeout=60)


def test_retry_state_machine():
    r = _run_node(SANDBOX.replace("__PICKED__", _picked()))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout, r.stdout


def test_inflight_dedup():
    r = _run_node(DEDUP.replace("__PICKED__", _picked()))
    assert r.returncode == 0 and "dedup ok" in r.stdout, r.stdout + r.stderr


def test_retry_params_reasonable():
    m = re.search(r"const PM_RETRY_MS = \[([^\]]*)\];", _html())
    ms = [int(x) for x in m.group(1).split(",")]
    assert 1 <= len(ms) <= 5 and ms == sorted(ms) and sum(ms) <= 120_000, ms


def test_head_request_no_store_source():
    s = _pick_func(_html(), "ensurePmHead")
    line = next(x for x in s.splitlines() if 'Range:"bytes=0-4095"' in x)
    assert 'cache:"no-store"' in line and 'cache:"no-cache"' not in line, line


# ---------------------------------------------------------------- ② Playwright 端到端
ORIGIN = "http://pm.test"
SIBLING = {
    "/taiwan-flow-live-v2/data/twse_holidays.json": "twse_holidays_2026.json",
    "/taiwan-flows/data/sentiment.json": "sentiment_sample.json",
    "/taiwan-flows/data/sector_ranges_lite.json": "chipradar_sector_ranges_r5r20.json",
}
CT = {".html": "text/html; charset=utf-8", ".json": "application/json", ".js": "text/javascript"}


def _chromium():
    sync_api = pytest.importorskip("playwright.sync_api", reason="未安裝 playwright（CI 不跑端到端）")
    exe = os.environ.get("PW_CHROMIUM")
    if not exe:
        for c in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",):
            if os.path.exists(c):
                exe = c
    return sync_api, exe


@pytest.fixture()
def browser():
    sync_api, exe = _chromium()
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as e:  # 沒裝瀏覽器
            pytest.skip(f"無法啟動 Chromium：{e}")
        yield b
        b.close()


def _open(browser, full_fail, width=1280, clock=False):
    """full_fail(n) → True 表示第 n 次（1 起算）整檔請求要失敗。回傳 (page, log)。"""
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    page = ctx.new_page()
    log = {"full": 0, "head": [], "errors": [], "pageerrors": []}
    page.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource")
            and log["errors"].append(m.text))
    page.on("pageerror", lambda e: log["pageerrors"].append(str(e)))
    if clock:
        page.clock.install()
    # 記錄頁面對 data/postmkt.json 發出的 fetch init（cache 模式不會出現在攔截到的請求標頭裡，只能在頁面端看）
    page.add_init_script("""(() => { const f = window.fetch; window.__pmFetch = [];
      window.fetch = function(u, o){ if (String(u).includes("postmkt.json")) window.__pmFetch.push({ u: String(u),
        range: !!(o && o.headers && o.headers.Range), cache: o && o.cache }); return f.apply(this, arguments); }; })();""")

    def handle(route):
        req = route.request
        u = urlparse(req.url)
        if u.netloc != "pm.test":
            return route.fulfill(status=404, body="")
        path = u.path
        if path.startswith("/postmkt/"):
            rel = path[len("/postmkt/"):] or "index.html"
            f = os.path.join(ROOT, rel)
            if rel == "data/postmkt.json":
                rng = req.headers.get("range")
                if rng:
                    log["head"].append(req.headers)
                    body = open(f, "rb").read()[:4096]
                    return route.fulfill(status=206, body=body, content_type="application/json",
                                         headers={"content-range": f"bytes 0-4095/{os.path.getsize(f)}"})
                log["full"] += 1
                if full_fail(log["full"]):
                    return route.abort("failed")
        elif path in SIBLING:
            f = os.path.join(FIX, SIBLING[path])
        else:
            return route.fulfill(status=404, body="")
        if not os.path.isfile(f):
            return route.fulfill(status=404, body="")
        route.fulfill(status=200, body=open(f, "rb").read(),
                      content_type=CT.get(os.path.splitext(f)[1], "application/octet-stream"))

    page.route("**/*", handle)
    return page, log


def _main(page) -> str:
    return page.evaluate("document.querySelector('#main').innerText")


def _top(page) -> str:
    return page.evaluate("document.querySelector('#topbar').innerText")


def test_e2e_a_recover_after_one_failure(browser):
    page, log = _open(browser, lambda n: n == 1)
    page.goto(ORIGIN + "/postmkt/#tab=lending")
    page.wait_for_function("() => state.pmFail === 1")
    assert "載入中" in _main(page) and "自動重試中" in _main(page)
    assert "尚無盤後資料" not in _main(page)
    page.wait_for_function("() => !!document.getElementById('tbPmNote')")
    assert "重試中" in _top(page)
    page.wait_for_function("() => !!state.pm", timeout=15000)   # 第一次重試在 3 秒後
    page.wait_for_timeout(200)
    assert log["full"] == 2
    assert page.evaluate("document.querySelectorAll('#main tr').length") > 5
    assert "載入失敗" not in _top(page) and page.evaluate("!document.getElementById('tbPmNote')")
    assert log["pageerrors"] == [] and log["errors"] == []


def test_e2e_b_give_up_then_user_retry(browser):
    page, log = _open(browser, lambda n: True, width=375, clock=True)
    page.goto(ORIGIN + "/postmkt/#tab=lending")
    page.wait_for_function("() => state.pmFail === 1")
    for i, ms in enumerate([3000, 10000, 30000], start=2):
        page.clock.run_for(ms)
        page.wait_for_function(f"() => state.pmFail === {i}")
    page.wait_for_function("() => !!state.pmErr")
    page.clock.run_for(120000)
    page.wait_for_timeout(300)
    assert log["full"] == 4, log["full"]
    t = _main(page)
    assert "尚無盤後資料" in t and "已自動重試 3 次仍失敗" in t
    assert "（完整資料載入失敗，可重新整理）" in _top(page)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # 不需要 pm 的 tab 不重抓；切回需要 pm 的 tab 重開一輪
    page.click('[data-tab="aetf"]')
    page.wait_for_timeout(200)
    assert log["full"] == 4
    page.click('[data-tab="daytrade"]')
    page.wait_for_function("() => state.pmFail === 1")
    assert log["full"] == 5
    assert log["pageerrors"] == [] and log["errors"] == []


def test_e2e_c_head_request_no_store(browser):
    page, log = _open(browser, lambda n: False)
    page.goto(ORIGIN + "/postmkt/")
    page.wait_for_function("() => !!state.pmHead")
    assert len(log["head"]) == 1
    calls = page.evaluate("() => window.__pmFetch")
    heads = [c for c in calls if c["range"]]
    assert len(heads) == 1 and heads[0]["cache"] == "no-store", calls
    page.click('[data-tab="lending"]')
    page.wait_for_function("() => !!state.pm")
    fulls = [c for c in page.evaluate("() => window.__pmFetch") if not c["range"]]
    assert len(fulls) == 1 and fulls[0]["cache"] == "no-cache", fulls   # 整檔維持 loadJSON 既有策略


def _tabs() -> list[str]:
    s = _html()
    block = s[s.index("const TABS = ["):]
    block = block[:block.index("];")]
    return re.findall(r'\["([a-z]+)",', block)


def test_e2e_d_all_tabs_normal(browser):
    tabs = _tabs()
    assert len(tabs) == 17, tabs
    page, log = _open(browser, lambda n: False)
    page.goto(ORIGIN + "/postmkt/")
    page.wait_for_function("() => !!state.pmHead")
    for t in tabs:
        page.click(f'[data-tab="{t}"]')
        page.wait_for_timeout(400)
    page.click('[data-tab="lending"]')
    page.wait_for_function("() => !!state.pm")
    assert log["full"] == 1 and page.evaluate("state.pmFail === 0 && state.pmErr === null")
    assert page.evaluate("!document.getElementById('tbPmNote')")
    assert log["pageerrors"] == [] and log["errors"] == [], json.dumps(log["errors"] + log["pageerrors"], ensure_ascii=False)
