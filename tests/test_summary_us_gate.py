"""早場閘門的美股新鮮度（2026-11-18）：us.json 的 date ≥ 最近預期美股交易日。

事故：20261118-am 在 07:05 產出，把美股 11-16 的數字寫成「隔夜美股（11/17）」。
舊判準 us_is_today 只看 generated_at 是不是今日，us 班 05:05 起每輪都刷新 generated_at，
對資料日沒有鑑別力。免 token、免網路（http_json／time 全部注入）。"""
import datetime as dt
import json

import pytest

import build_summary as bs

TPE = dt.timezone(dt.timedelta(hours=8))


# ---------- 最近預期美股交易日（Worker lastExpectedUsTradingDate 的移植） ----------

@pytest.mark.parametrize("today,expected", [
    ("2026-11-16", "2026-11-13"),   # 週一 → 上週五（-3）
    ("2026-11-17", "2026-11-16"),   # 週二 → 昨日
    ("2026-11-18", "2026-11-17"),   # 週三（事故日）
    ("2026-11-19", "2026-11-18"),   # 週四
    ("2026-11-20", "2026-11-19"),   # 週五
    ("2026-11-21", "2026-11-20"),   # 週六 → 昨日（週五）
    ("2026-11-22", "2026-11-20"),   # 週日 → 上週五（-2）
    ("2026-11-02", "2026-10-30"),   # 週一跨月
    ("2027-01-01", "2026-12-31"),   # 跨年（美國假日不處理）
    ("2026-03-02", "2026-02-27"),   # 週一跨月（非閏年二月）
])
def test_last_expected_us_trading_date(today, expected):
    assert bs.last_expected_us_trading_date(today) == expected


def test_expected_matches_worker_js_when_available():
    """姊妹 repo 在同層時，與 Worker 的 JS 實作逐日對跑（兩處要同步）。沒有就略過。"""
    import re
    import shutil
    import subprocess
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "taiwan-flow-live-v2" / "worker" / "src" / "index.js"
    if not src.exists() or not shutil.which("node"):
        pytest.skip("無 taiwan-flow-live-v2 checkout 或 node")
    js = src.read_text(encoding="utf-8")
    m = re.search(r"export function lastExpectedUsTradingDate\(dateISO\) \{.*?\n\}", js, re.S)
    a = re.search(r"(?:export )?(?:function addDaysISO\(.*?\n\}|const addDaysISO = .*?;\n)", js, re.S)
    if not m or not a:
        pytest.skip("Worker 原始碼找不到對應函式")
    days = [(dt.date(2026, 11, 1) + dt.timedelta(days=i)).isoformat() for i in range(70)]
    code = (a.group(0).replace("export ", "") + "\n" + m.group(0).replace("export ", "")
            + f"\nconsole.log(JSON.stringify({json.dumps(days)}.map(lastExpectedUsTradingDate)));")
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [bs.last_expected_us_trading_date(d) for d in days]


# ---------- us_is_fresh／us_gate_info ----------

def test_us_fresh_equal_older_newer():
    today = "2026-11-18"                                   # 預期 11-17
    assert bs.us_is_fresh({"date": "2026-11-17"}, today) is True
    assert bs.us_is_fresh({"date": "2026-11-16"}, today) is False
    assert bs.us_is_fresh({"date": "2026-11-18"}, today) is True    # 晚於預期也算新鮮
    assert bs.us_is_fresh({"date": "2026/11/17"}, today) is True    # 斜線日期正規化


def test_us_fresh_ignores_generated_at():
    """事故形狀：generated_at 是今日清晨、date 仍是前前日 → 不新鮮。"""
    us = {"date": "2026-11-16", "generated_at": "2026-11-18T06:58:00+08:00"}
    assert bs.us_is_fresh(us, "2026-11-18") is False
    # 反向：generated_at 很舊但 date 已達預期 → 新鮮（只看資料日）
    assert bs.us_is_fresh({"date": "2026-11-17", "generated_at": "2026-11-01T00:00:00+08:00"}, "2026-11-18") is True


@pytest.mark.parametrize("us", [None, {}, {"date": None}, {"date": ""}, {"date": 20261117},
                                {"date": "garbage"}, {"date": "9999"}, [], "2026-11-17"])
def test_us_fresh_unreadable_or_bad_shape(us):
    assert bs.us_is_fresh(us, "2026-11-18") is False
    assert bs.us_data_date(us) is None


def test_us_fresh_monday_expects_friday():
    assert bs.us_is_fresh({"date": "2026-11-13"}, "2026-11-16") is True     # 週一拿到上週五
    assert bs.us_is_fresh({"date": "2026-11-12"}, "2026-11-16") is False    # 週一拿到上週四


def test_us_gate_info_shape():
    g = bs.us_gate_info({"date": "2026-11-16"}, "2026-11-18", 3600.7)
    assert g == {"expected": "2026-11-17", "got": "2026-11-16", "fresh": False, "waited_sec": 3600}
    assert bs.us_gate_info(None, "2026-11-18") == {
        "expected": "2026-11-17", "got": None, "fresh": False, "waited_sec": 0}
    assert bs.us_gate_info({"date": "2026-11-17"}, "2026-11-18", 0)["fresh"] is True
    json.dumps(g)                                             # 可序列化


# ---------- wait_gate am 第二階段（假時鐘） ----------

class Clock:
    def __init__(self):
        self.t = 1_000_000.0
        self.sleeps = 0

    def time(self):
        return self.t

    def sleep(self, s):
        self.sleeps += 1
        self.t += s


def _gate_env(monkeypatch, us_seq, today="2026-11-18", news_ok=True):
    """us_seq：每次輪詢依序回傳的 us.json（用完後重複最後一個；Exception 實例＝該次拋錯）。"""
    ck = Clock()
    monkeypatch.setattr(bs.time, "time", ck.time)
    monkeypatch.setattr(bs.time, "sleep", ck.sleep)
    monkeypatch.setattr(bs, "is_twse_holiday", lambda d: False)
    calls = {"us": 0, "urls": []}
    news_ts = f"{today}T06:35:00+08:00" if news_ok else f"{today}T05:00:00+08:00"

    def fake(url, *a, **k):
        calls["urls"].append(url)
        if url == bs.URL_MORNING:
            return {"generated_at": f"{today}T07:02:00+08:00"}
        if url == bs.URL_NEWS:
            return {"generated_at": news_ts}
        if url == bs.URL_US:
            v = us_seq[min(calls["us"], len(us_seq) - 1)]
            calls["us"] += 1
            if isinstance(v, Exception):
                raise v
            return v
        raise AssertionError("am 場不該打 " + url)

    monkeypatch.setattr(bs, "http_json", fake)
    return ck, calls


STALE = {"date": "2026-11-16", "generated_at": "2026-11-18T06:58:00+08:00"}   # 事故形狀
FRESH = {"date": "2026-11-17", "generated_at": "2026-11-18T07:41:00+08:00"}


def test_gate_am_passes_immediately_when_us_fresh(monkeypatch):
    ck, calls = _gate_env(monkeypatch, [FRESH])
    assert bs.wait_gate("am", "2026-11-18") == 0
    assert ck.sleeps == 0 and calls["us"] == 1


def test_gate_am_waits_until_us_date_advances(monkeypatch):
    """generated_at 是今日但 date 落後 → 不放行；第 8 輪 date 推進才過（等了 35 分）。"""
    ck, calls = _gate_env(monkeypatch, [STALE] * 7 + [FRESH])
    assert bs.wait_gate("am", "2026-11-18") == 7 * 300
    assert ck.sleeps == 7 and calls["us"] == 8


def test_gate_am_soft_timeout_still_runs(monkeypatch, capsys):
    """美股始終沒到：軟等 60 分後照跑（回傳、不 exit），等待秒數 = 3600。"""
    ck, calls = _gate_env(monkeypatch, [STALE])
    assert bs.wait_gate("am", "2026-11-18") == 3600
    assert ck.sleeps == 12 and calls["us"] == 13
    out = capsys.readouterr().out
    assert "軟等逾時" in out and "us.json date=2026-11-16" in out and "2026-11-17" in out


def test_gate_am_us_unreadable_soft_timeout(monkeypatch):
    ck, _ = _gate_env(monkeypatch, [RuntimeError("404")])
    assert bs.wait_gate("am", "2026-11-18") == 3600          # 讀不到也只是軟等，不 skip、不拋


def test_gate_am_monday_accepts_friday(monkeypatch):
    ck, _ = _gate_env(monkeypatch, [{"date": "2026-11-13"}], today="2026-11-16")
    assert bs.wait_gate("am", "2026-11-16") == 0 and ck.sleeps == 0


def test_gate_am_monday_rejects_thursday(monkeypatch):
    ck, _ = _gate_env(monkeypatch, [{"date": "2026-11-12"}], today="2026-11-16")
    assert bs.wait_gate("am", "2026-11-16") == 3600


def test_gate_pm_unaffected_never_reads_us(monkeypatch):
    """pm 場：不讀 us.json、回傳 None、三源皆今日即過。"""
    ck = Clock()
    monkeypatch.setattr(bs.time, "time", ck.time)
    monkeypatch.setattr(bs.time, "sleep", ck.sleep)
    monkeypatch.setattr(bs, "is_twse_holiday", lambda d: False)
    seen = []

    def fake(url, *a, **k):
        seen.append(url)
        if url == bs.URL_NEWS:
            return {"generated_at": "2026-11-18T22:10:00+08:00"}
        return {"date": "2026-11-18"}

    monkeypatch.setattr(bs, "http_json", fake)
    assert bs.wait_gate("pm", "2026-11-18") is None
    assert bs.URL_US not in seen and ck.sleeps == 0


# ---------- write_output：us_gate 與 index.json 的精簡旗標 ----------

def _six(day):
    return [{"page": p, "model": "m", "tag": "Sonnet5", "date": day, "ok": True, "text": "x",
             "stop_reason": "end_turn", "usage": None} for p in ("盤後分析", "即時類股動態", "新聞晨報")]


def _out(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "OUT_DIR", tmp_path / "summary")
    monkeypatch.setattr(bs, "ROOT", tmp_path)
    return tmp_path / "summary"


SYN = {"model": "m", "ok": True, "text": "## 盤勢綜合研判\n甲", "stop_reason": "end_turn", "usage": None}


def test_write_output_records_stale_us_gate(tmp_path, monkeypatch):
    d = _out(tmp_path, monkeypatch)
    day = bs.taipei_now().date().isoformat()                # 不可寫死：尾端會刪 3 日前舊檔
    ug = bs.us_gate_info({"date": "2000-01-01"}, day, 3600)
    assert ug["fresh"] is False
    bs.write_output("am", day, _six(day), SYN, ug)
    j = json.loads((d / f"{day.replace('-', '')}-am.json").read_text(encoding="utf-8"))
    assert j["us_gate"] == ug and set(ug) == {"expected", "got", "fresh", "waited_sec"}
    run = json.loads((d / "index.json").read_text(encoding="utf-8"))["runs"][0]
    assert run["us_stale"] is True
    assert {"file", "date", "slot", "generated_at"} <= set(run)      # 既有鍵不變


def test_write_output_fresh_us_gate_no_index_flag(tmp_path, monkeypatch):
    d = _out(tmp_path, monkeypatch)
    day = bs.taipei_now().date().isoformat()
    ug = bs.us_gate_info({"date": day}, day, 0)
    assert ug["fresh"] is True
    bs.write_output("am", day, _six(day), SYN, ug)
    j = json.loads((d / f"{day.replace('-', '')}-am.json").read_text(encoding="utf-8"))
    assert j["us_gate"]["fresh"] is True
    assert "us_stale" not in json.loads((d / "index.json").read_text(encoding="utf-8"))["runs"][0]


def test_write_output_without_us_gate_shape_unchanged(tmp_path, monkeypatch):
    """pm 場／舊呼叫方式（不傳 us_gate）：輸出鍵與改動前相同。"""
    d = _out(tmp_path, monkeypatch)
    day = bs.taipei_now().date().isoformat()
    bs.write_output("pm", day, _six(day), SYN)
    j = json.loads((d / f"{day.replace('-', '')}-pm.json").read_text(encoding="utf-8"))
    assert list(j) == ["generated_at", "slot", "date", "dates", "six", "synthesis"]
    assert list(json.loads((d / "index.json").read_text(encoding="utf-8"))["runs"][0]) == [
        "file", "date", "slot", "generated_at"]


# ---------- main()：軟等逾時照跑 → 產出檔帶 us_gate.fresh=false ----------

def _main_env(tmp_path, monkeypatch, slot, us, waited):
    d = _out(tmp_path, monkeypatch)
    day = bs.taipei_now().date().isoformat()
    monkeypatch.setattr(bs, "slot_trading_day", lambda s: day)
    monkeypatch.setattr(bs, "anth_key", lambda: "k")
    monkeypatch.setattr(bs, "wait_gate", lambda s, t: waited)
    monkeypatch.setattr(bs, "load_sources", lambda: {"us": us})
    monkeypatch.setattr(bs, "build_contexts", lambda src: [
        {"page": p, "sys": "S", "user": "U", "primary": day, "empty": False}
        for p in ("盤後分析", "即時類股動態", "新聞晨報")])
    monkeypatch.setattr(bs, "batch_deadline", lambda *a, **k: 0)
    res = {"ok": True, "text": "## 盤勢綜合研判\n甲", "stop_reason": "end_turn", "usage": None, "model": "m"}
    monkeypatch.setattr(bs, "call_claude_retry", lambda *a, **k: dict(res))
    monkeypatch.setattr(bs, "run_synthesis", lambda *a, **k: {**res, "via": "sync"})
    monkeypatch.setattr(bs.sys, "argv", ["build_summary.py", "--slot", slot])
    return d, day


def test_main_am_soft_timeout_writes_flag(tmp_path, monkeypatch, capsys):
    d, day = _main_env(tmp_path, monkeypatch, "am", {"date": "2000-01-03"}, 3600)
    bs.main()
    j = json.loads((d / f"{day.replace('-', '')}-am.json").read_text(encoding="utf-8"))
    assert j["us_gate"] == {"expected": bs.last_expected_us_trading_date(day), "got": "2000-01-03",
                            "fresh": False, "waited_sec": 3600}
    assert j["synthesis"]["text"].startswith("## 盤勢綜合研判")     # 照跑、有產出
    assert "美股資料日未達預期" in capsys.readouterr().out


def test_main_am_us_unreadable_writes_flag(tmp_path, monkeypatch):
    d, day = _main_env(tmp_path, monkeypatch, "am", None, 3600)
    bs.main()
    j = json.loads((d / f"{day.replace('-', '')}-am.json").read_text(encoding="utf-8"))
    assert j["us_gate"]["got"] is None and j["us_gate"]["fresh"] is False


def test_main_am_fresh_records_fresh(tmp_path, monkeypatch):
    d, day = _main_env(tmp_path, monkeypatch, "am", {"date": bs.taipei_now().date().isoformat()}, 600)
    bs.main()
    j = json.loads((d / f"{day.replace('-', '')}-am.json").read_text(encoding="utf-8"))
    assert j["us_gate"]["fresh"] is True and j["us_gate"]["waited_sec"] == 600


def test_main_pm_has_no_us_gate(tmp_path, monkeypatch):
    d, day = _main_env(tmp_path, monkeypatch, "pm", {"date": "2000-01-03"}, None)
    bs.main()
    j = json.loads((d / f"{day.replace('-', '')}-pm.json").read_text(encoding="utf-8"))
    assert "us_gate" not in j
    assert "us_stale" not in json.loads((d / "index.json").read_text(encoding="utf-8"))["runs"][0]
