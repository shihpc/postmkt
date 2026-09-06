# 產出的 model 欄：自動彙總場的 synthesis 與 six[] 都必須記下「實際呼叫時用的模型」，
# 前端（index.html insightCostText）才能估算費用而不必從程式碼常數回推。
# 全離線（mock requests），免 token 免網路。
import json

import pytest

import build_summary as bs


class FakeResp:
    def __init__(self, payload=None, text=None, ok=True, status=200):
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})
        self.ok, self.status_code = ok, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequests:
    def __init__(self, posts, gets):
        self.posts, self.gets, self.urls = list(posts), list(gets), []

    def post(self, url, **kw):
        self.urls.append(("POST", url))
        return self.posts.pop(0)

    def get(self, url, **kw):
        self.urls.append(("GET", url))
        return self.gets.pop(0)


def msg(text):
    return {"stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 4,
                                                 "service_tier": "batch"},
            "content": [{"type": "text", "text": text}]}


def result_line(cid, rtype, message=None):
    return json.dumps({"custom_id": cid, "result": {"type": rtype, "message": message}})


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(bs, "BATCH_POLL_SEC", 0)
    monkeypatch.setattr(bs.time, "sleep", lambda s: None)
    monkeypatch.setattr(bs, "anth_key", lambda: "test-key-not-real")


# ---------- batch 路徑 ----------

def test_batch_result_carries_requested_model(monkeypatch):
    fake = FakeRequests(
        posts=[FakeResp({"id": "b1", "processing_status": "in_progress"})],
        gets=[FakeResp({"processing_status": "ended", "results_url": "https://x/results"}),
              FakeResp(text="\n".join([result_line("s0", "succeeded", msg("甲")),
                                       result_line("synth", "succeeded", msg("乙"))]))])
    monkeypatch.setattr(bs, "requests", fake)
    out = bs.call_claude_batch({"s0": ("claude-sonnet-5", "sys", "u0"),
                                "synth": ("claude-opus-4-8", "sys", "u1")}, 60, "t")
    # 逐筆各自記自己的 model，不是整包共用一個
    assert out["s0"]["model"] == "claude-sonnet-5"
    assert out["synth"]["model"] == "claude-opus-4-8"
    # 既有欄位不動
    assert out["s0"]["text"] == "甲" and out["s0"]["stop_reason"] == "end_turn"


# ---------- 同步（回退）路徑 ----------

def test_sync_retry_carries_actual_model(monkeypatch):
    monkeypatch.setattr(bs.requests, "post",
                        lambda url, headers, json, timeout: FakeResp(
                            {"stop_reason": "end_turn", "usage": {"output_tokens": 1},
                             "content": [{"type": "text", "text": "內容"}]}))
    res = bs.call_claude_retry("claude-opus-4-8", "sys", "u", "彙總")
    assert res["ok"] is True and res["model"] == "claude-opus-4-8"


def test_sync_retry_failure_placeholder_also_carries_model(monkeypatch):
    monkeypatch.setattr(bs.requests, "post",
                        lambda url, headers, json, timeout: FakeResp(
                            {"stop_reason": "max_tokens", "usage": {},
                             "content": [{"type": "thinking", "thinking": "…"}]}))
    res = bs.call_claude_retry("claude-sonnet-5", "sys", "u", "測試份")
    assert res["ok"] is False and res["model"] == "claude-sonnet-5"


def test_batch_timeout_fallback_records_sync_model(monkeypatch):
    """batch 超時 → 同步回退：寫進產出的必須是同步那次實際用的 model（降級路徑守門）。"""
    real_requests = bs.requests
    fake = FakeRequests(posts=[FakeResp({"id": "b1", "processing_status": "in_progress"}),
                               FakeResp({})], gets=[])
    monkeypatch.setattr(bs, "requests", fake)
    got = bs.call_claude_batch({"synth": ("claude-opus-4-8", "sys", "u")}, 0, "彙總").get("synth")
    assert got is None   # batch 這一路沒有結果 → 主程式改走 call_claude_retry

    monkeypatch.setattr(bs, "requests", real_requests)   # 同步回退走真模組（post 另行 mock）
    monkeypatch.setattr(bs.requests, "post",
                        lambda url, headers, json, timeout: FakeResp(
                            {"stop_reason": "end_turn", "usage": {"output_tokens": 1},
                             "content": [{"type": "text", "text": "回退產出"}]}))
    synth = {"via": "sync", **bs.call_claude_retry("claude-opus-4-8", "sys", "u", "彙總")}
    assert synth["model"] == "claude-opus-4-8" and synth["via"] == "sync"


# ---------- write_output ----------

def test_write_output_synthesis_has_model(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "OUT_DIR", tmp_path)
    # 資料日必須相對於「今天」算，不可寫死：write_output 尾端會刪掉檔名日期早於
    # (taipei_now() − 3 日) 的 am/pm 檔，寫死日期的測試會在該日掉出保留窗後由綠轉紅
    # （2026-09-03 實際發生：原本寫死 2026-08-29，cutoff 推到 20260831 後檔案被自己刪掉）。
    day = bs.taipei_now().date().isoformat()
    fname = day.replace("-", "") + "-pm.json"
    six = [{"page": "postmkt", "model": "claude-sonnet-5", "tag": "Sonnet5",
            "date": day, "ok": True, "via": "batch", "text": "甲",
            "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 2}}]
    bs.write_output("pm", day, six,
                    {"text": "彙總", "usage": {"input_tokens": 5, "output_tokens": 6},
                     "via": "batch", "model": "claude-opus-4-8"})
    out = json.loads((tmp_path / fname).read_text(encoding="utf-8"))
    assert out["synthesis"]["model"] == "claude-opus-4-8"
    # 既有欄位一個都沒少
    assert set(out["synthesis"]) == {"text", "usage", "via", "model"}
    assert out["six"][0]["model"] == "claude-sonnet-5"
    assert out["dates"] == {"postmkt": day}


def test_model_values_match_frontend_price_table():
    """寫進產出的 model 字串必須是前端 INSIGHT_PRICES 的鍵，否則費用估算會靜靜消失。"""
    import re
    from pathlib import Path
    html = (Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")
    block = html.split("const INSIGHT_PRICES")[1].split("};")[0]
    keys = set(re.findall(r'"([a-z0-9-]+)":\s*\[', block))
    assert bs.SYNTH_MODEL in keys
    assert set(bs.SUMMARY_MODELS) <= keys


# ---------- main() 的彙總接線（run_synthesis → synthesis_field → write_output） ----------
# 這段是 2026-09-06 補的覆蓋缺口：原本 model／via 的組裝內嵌在 main() 裡，測試只各自驗
# 「call_claude_batch／call_claude_retry 會回報 model」（平行實作），把 main() 裡的
# "model": synth.get("model") 改成錯字串全部測試仍然全綠。以下改為驗「接線」本身。

def _boom(*a, **kw):
    raise AssertionError("這條路不該被呼叫")


def test_run_synthesis_batch_success_wires_batch_model_and_via(monkeypatch):
    """batch 成功：產出欄位的 model／via 必須來自 batch 那一路實際回報的值。"""
    seen = {}

    def fake_batch(reqs, deadline_sec, label):
        seen["reqs"], seen["deadline"] = reqs, deadline_sec
        return {"synth": {"model": reqs["synth"][0], "text": "彙總全文",
                          "stop_reason": "end_turn", "usage": {"output_tokens": 9}}}

    monkeypatch.setattr(bs, "call_claude_batch", fake_batch)
    monkeypatch.setattr(bs, "call_claude_retry", _boom)   # batch 成功就不該回退
    synth = bs.run_synthesis("三份全文", 600)
    assert seen["reqs"]["synth"][0] == bs.SYNTH_MODEL and seen["deadline"] == 600
    assert bs.synthesis_field(synth) == {
        "text": "彙總全文", "usage": {"output_tokens": 9},
        "via": "batch", "model": bs.SYNTH_MODEL}


def test_run_synthesis_batch_timeout_falls_back_to_sync(monkeypatch):
    """batch 逾時／取消／下載失敗（該筆回 None）→ 同步回退，via 轉 sync、model 取同步那次。"""
    monkeypatch.setattr(bs, "call_claude_batch", lambda reqs, dl, label: {"synth": None})
    calls = []

    def fake_retry(model, system, user_msg, label):
        calls.append((model, user_msg, label))
        return {"ok": True, "model": model, "text": "回退全文",
                "stop_reason": "end_turn", "usage": {"output_tokens": 5}}

    monkeypatch.setattr(bs, "call_claude_retry", fake_retry)
    synth = bs.run_synthesis("三份全文", 600)
    assert calls == [(bs.SYNTH_MODEL, "三份全文", f"彙總×{bs.SYNTH_MODEL}")]
    assert bs.synthesis_field(synth) == {
        "text": "回退全文", "usage": {"output_tokens": 5},
        "via": "sync", "model": bs.SYNTH_MODEL}


def test_run_synthesis_zero_deadline_skips_batch(monkeypatch):
    """預算不足（batch_deadline 回 0）或 --sync：完全不打 batch，直接同步。"""
    monkeypatch.setattr(bs, "call_claude_batch", _boom)
    monkeypatch.setattr(bs, "call_claude_retry",
                        lambda model, system, user_msg, label: {
                            "ok": True, "model": model, "text": "同步全文",
                            "stop_reason": "end_turn", "usage": {"output_tokens": 1}})
    assert bs.synthesis_field(bs.run_synthesis("三份全文", 0)) == {
        "text": "同步全文", "usage": {"output_tokens": 1},
        "via": "sync", "model": bs.SYNTH_MODEL}


def test_run_synthesis_propagates_not_ok(monkeypatch):
    """同步也失敗時要把 ok:false 原樣傳回——main() 靠它決定整場失敗（sys.exit(1)）。"""
    monkeypatch.setattr(bs, "call_claude_batch", lambda reqs, dl, label: {"synth": None})
    monkeypatch.setattr(bs, "call_claude_retry",
                        lambda model, system, user_msg, label: {
                            "ok": False, "model": model, "text": "（該份產出失敗：x）",
                            "stop_reason": None, "usage": None})
    synth = bs.run_synthesis("三份全文", 600)
    assert synth["ok"] is False and synth["via"] == "sync"


def test_synthesis_field_missing_model_is_none_not_keyerror():
    """現行行為存證：synth 沒有 model／via 鍵時，欄位仍在、值為 None（不丟 KeyError）。
    這是現況記錄，不是主張它應該如此——要改成別的行為是另一個決策。"""
    field = bs.synthesis_field({"ok": True, "text": "x", "usage": {"output_tokens": 1}})
    assert field["model"] is None and field["via"] is None
    assert set(field) == {"text", "usage", "via", "model"}


def test_synthesis_wiring_end_to_end_reaches_output_json(tmp_path, monkeypatch):
    """batch 逾時回退這條實戰路徑，一路走到落地 JSON：synthesis.model 必須是同步那次的模型。"""
    monkeypatch.setattr(bs, "OUT_DIR", tmp_path)
    monkeypatch.setattr(bs, "call_claude_batch", lambda reqs, dl, label: {"synth": None})
    monkeypatch.setattr(bs, "call_claude_retry",
                        lambda model, system, user_msg, label: {
                            "ok": True, "model": model, "text": "回退全文",
                            "stop_reason": "end_turn", "usage": {"output_tokens": 5}})
    day = bs.taipei_now().date().isoformat()   # 不可寫死日期，理由見 write_output 測試註解
    six = [{"page": "postmkt", "model": "claude-sonnet-5", "tag": "Sonnet5", "date": day,
            "ok": True, "via": "batch", "text": "甲", "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2}}]
    bs.write_output("pm", day, six, bs.synthesis_field(bs.run_synthesis("三份全文", 600)))
    out = json.loads((tmp_path / (day.replace("-", "") + "-pm.json")).read_text(encoding="utf-8"))
    assert out["synthesis"] == {"text": "回退全文", "usage": {"output_tokens": 5},
                                "via": "sync", "model": bs.SYNTH_MODEL}
