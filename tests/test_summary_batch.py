# call_claude_batch（Message Batches 主路徑＋同步回退訊號）離線測試：mock requests，
# 免 token 免網路。契約＝回 {custom_id: 解析結果 或 None}，None 代表「該筆交給同步回退」；
# 任何整包層級的失敗（提交、超時 cancel、結果下載）都必須回全 None、絕不丟例外讓場死掉。
import json

import pytest

import build_summary as bs


class FakeResp:
    def __init__(self, payload=None, text=None, ok=True, status=200):
        self._payload, self.text = payload, text if text is not None else json.dumps(payload or {})
        self.ok, self.status_code = ok, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequests:
    """依序回放 post/get 腳本；同時記錄呼叫過的 URL 供斷言（如 cancel）。"""

    def __init__(self, posts, gets):
        self.posts, self.gets, self.urls = list(posts), list(gets), []

    def post(self, url, **kw):
        self.urls.append(("POST", url))
        return self.posts.pop(0)

    def get(self, url, **kw):
        self.urls.append(("GET", url))
        return self.gets.pop(0)


def msg(text):
    return {"stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": [{"type": "text", "text": text}]}


def result_line(cid, rtype, message=None):
    return json.dumps({"custom_id": cid, "result": {"type": rtype, "message": message}})


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(bs, "BATCH_POLL_SEC", 0)


REQS = {"s0": ("m", "sys", "user0"), "s1": ("m", "sys", "user1")}


def test_batch_success(monkeypatch):
    fake = FakeRequests(
        posts=[FakeResp({"id": "b1", "processing_status": "in_progress"})],
        gets=[FakeResp({"processing_status": "ended", "results_url": "https://x/results"}),
              FakeResp(text="\n".join([result_line("s0", "succeeded", msg("甲")),
                                       result_line("s1", "succeeded", msg("乙"))]))])
    monkeypatch.setattr(bs, "requests", fake)
    out = bs.call_claude_batch(dict(REQS), 60, "t")
    assert out["s0"]["text"] == "甲" and out["s1"]["text"] == "乙"
    assert out["s0"]["usage"] == {"input_tokens": 1, "output_tokens": 2}


def test_batch_deadline_cancels_and_returns_all_none(monkeypatch):
    fake = FakeRequests(
        posts=[FakeResp({"id": "b1", "processing_status": "in_progress"}),
               FakeResp({})],   # cancel 回應
        gets=[])
    monkeypatch.setattr(bs, "requests", fake)
    out = bs.call_claude_batch(dict(REQS), 0, "t")   # 期限 0 → 立即超時
    assert out == {"s0": None, "s1": None}
    assert ("POST", f"{bs.URL_BATCHES}/b1/cancel") in fake.urls


def test_batch_partial_expired_falls_back_per_item(monkeypatch):
    fake = FakeRequests(
        posts=[FakeResp({"id": "b1", "processing_status": "in_progress"})],
        gets=[FakeResp({"processing_status": "ended", "results_url": "https://x/results"}),
              FakeResp(text="\n".join([result_line("s0", "succeeded", msg("甲")),
                                       result_line("s1", "expired")]))])
    monkeypatch.setattr(bs, "requests", fake)
    out = bs.call_claude_batch(dict(REQS), 60, "t")
    assert out["s0"]["text"] == "甲" and out["s1"] is None


def test_batch_submit_error_returns_all_none(monkeypatch):
    fake = FakeRequests(posts=[FakeResp({"type": "error", "error": {"message": "boom"}}, ok=False, status=400)],
                        gets=[])
    monkeypatch.setattr(bs, "requests", fake)
    assert bs.call_claude_batch(dict(REQS), 60, "t") == {"s0": None, "s1": None}


def test_batch_refusal_or_empty_text_falls_back(monkeypatch):
    refusal = {"stop_reason": "refusal", "content": [], "usage": {}}
    fake = FakeRequests(
        posts=[FakeResp({"id": "b1", "processing_status": "in_progress"})],
        gets=[FakeResp({"processing_status": "ended", "results_url": "https://x/results"}),
              FakeResp(text=result_line("s0", "succeeded", refusal))])
    monkeypatch.setattr(bs, "requests", fake)
    assert bs.call_claude_batch({"s0": ("m", "sys", "u")}, 60, "t") == {"s0": None}


def test_deadline_constants_match_spec():
    # am 25 分固定（使用者裁定）；pm 的 180 分只是**上界**，實際綁住 pm 的是台北 23:00 的
    # 牌鐘截止（2026-09-10 第二版：同日第一版曾砍成 30 分，被當晚 104 分鐘成功的那包 batch
    # 推翻——30 分會把它 cancel 掉。理由見 BATCH_DEADLINE_SEC 上方註解）
    assert bs.BATCH_DEADLINE_SEC == {"am": 25 * 60, "pm": 180 * 60}
    assert bs.PM_BATCH_CUTOFF_HM == (23, 0)
    assert bs.SUMMARY_MODELS == ["claude-sonnet-5"]
    assert bs.MIN_OK_FOR_SYNTH == 2


def tpe(hh, mm=0, ss=0):
    """台北時間的固定時點（測試一律注入，不碰真實牆鐘）。日期取哪天無所謂——
    牌鐘只比同日的時分。"""
    import datetime as _dt
    return _dt.datetime(2026, 9, 10, hh, mm, ss, tzinfo=bs.TAIPEI)


def test_batch_deadline_budget():
    import time as _t
    now = _t.monotonic()
    at19 = tpe(19)   # 距 23:00 牌鐘還有 4 小時 > 180 分上界 → 這組不受牌鐘影響
    # 剛進場：剩餘充裕 → 取場次期限本身（容差 2 秒吃掉 monotonic 經過時間）
    assert abs(bs.batch_deadline("am", now, at19) - 25 * 60) <= 2
    assert abs(bs.batch_deadline("pm", now, at19) - 180 * 60) <= 2
    # 閘門耗掉 30 分：剩 225-30-15=180 分，與場次期限打平 → 仍是 180 分
    assert abs(bs.batch_deadline("pm", now - 30 * 60, at19) - 180 * 60) <= 2
    # 閘門耗掉 100 分：剩 225-100-15=110 分 < 180 分 → 這時才改取剩餘預算
    assert abs(bs.batch_deadline("pm", now - 100 * 60, at19) - 110 * 60) <= 2
    # 閘門耗掉 190 分：剩 225-190-15=20 分
    assert abs(bs.batch_deadline("pm", now - 190 * 60, at19) - 20 * 60) <= 2
    # 耗掉 210 分：剩 0 → 跳過 batch
    assert bs.batch_deadline("pm", now - 210 * 60, at19) == 0
    # 耗掉 209.5 分：剩 ~30 秒 < 60 秒門檻 → 同樣跳過
    assert bs.batch_deadline("am", now - int(209.5 * 60), at19) == 0


def test_pm_cutoff_binds_when_near_2300():
    """② 距牌鐘 20 分：三條上限裡「距截止剩餘」最小 → 取它（而不是 180 分或預算）。"""
    import time as _t
    now = _t.monotonic()
    assert abs(bs.batch_deadline("pm", now, tpe(22, 40)) - 20 * 60) <= 2
    # 21:20（實測的 pm 起跑時刻附近）→ 距截止 100 分，仍比 180 分與預算小
    assert abs(bs.batch_deadline("pm", now, tpe(21, 20)) - 100 * 60) <= 2


def test_pm_cutoff_zero_after_2300_skips_batch():
    """③ 已過牌鐘（或不足 60 秒）→ 回 0＝整包跳過 batch 直接同步。"""
    import time as _t
    now = _t.monotonic()
    assert bs.batch_deadline("pm", now, tpe(23, 0)) == 0        # 正好到點
    assert bs.batch_deadline("pm", now, tpe(23, 5)) == 0        # 已過
    assert bs.batch_deadline("pm", now, tpe(23, 59)) == 0
    assert bs.batch_deadline("pm", now, tpe(22, 59, 30)) == 0   # 剩 30 秒 < 60 秒門檻
    # 剩 5 分 → 尚未歸零（確認上一條不是被 60 秒門檻以外的東西砍掉的）
    assert abs(bs.batch_deadline("pm", now, tpe(22, 55)) - 5 * 60) <= 2


def test_am_ignores_pm_cutoff():
    """④ 牌鐘只對 pm 生效：am 在 23:0x 仍是 25 分（am 場實際跑在清晨，這裡只驗不掛鉤）。"""
    import time as _t
    now = _t.monotonic()
    for t in (tpe(22, 40), tpe(23, 0), tpe(23, 30)):
        assert abs(bs.batch_deadline("am", now, t) - 25 * 60) <= 2


def test_now_is_injectable_and_defaults_to_taipei_now(monkeypatch):
    """⑤ now 可注入以重演任一時點；不注入時等同 taipei_now() 的那一刻。"""
    import time as _t
    now = _t.monotonic()
    for hh, mm, want in [(19, 0, 180 * 60), (22, 0, 60 * 60),
                         (22, 40, 20 * 60), (23, 10, 0)]:
        got = bs.batch_deadline("pm", now, tpe(hh, mm))
        assert abs(got - want) <= 2, (hh, mm, got, want)
    monkeypatch.setattr(bs, "taipei_now", lambda: tpe(22, 40))
    assert abs(bs.batch_deadline("pm", now) - 20 * 60) <= 2
    monkeypatch.setattr(bs, "taipei_now", lambda: tpe(23, 10))
    assert bs.batch_deadline("pm", now) == 0


def test_pm_cutoff_does_not_bind_after_midnight():
    """⑥ 跨午夜：`now` 落在台北 00:xx 時，牌鐘不綁、回落 180 分上界（2026-09-13 補）。

    `batch_deadline` 的牌鐘是 `n.replace(hour=23, minute=0)`——**同一個日曆日的 23:00**，
    不是「下一個 23:00」。所以清晨 00:10 算出來的「距截止剩餘」是約 22 小時 50 分（往後看，
    不是負的往前看），三條上限取最小之後由場次期限 180 分勝出。這條路徑原本只有註解描述、
    零測試，而 pm 場實務上會跨午夜（2026-09-10 那班摘要 batch 實跑約 104 分鐘、產物台北 22:58
    落地；逾時回退的幾天更晚），一旦有人把牌鐘改成「取下一個 23:00」或改用 UTC 比較，
    清晨那段就會從 180 分變成 0（整包跳過 batch）或反過來爆表，而現有測試全都在 19:00–23:59
    之間、抓不到。

    **不是**在主張「pm 場一定會跑到清晨」——只是這個時點算得出來、就該有明確的期望值。
    """
    import time as _t
    now = _t.monotonic()
    # 00:10 距同日 23:00 還有 22h50m，遠大於 180 分上界 → 取 180 分
    assert abs(bs.batch_deadline("pm", now, tpe(0, 10)) - 180 * 60) <= 2
    # 00:00 整、以及 02:30、08:00 同理（都在當日 23:00 之前，牌鐘一律不綁）
    for t in (tpe(0, 0), tpe(2, 30), tpe(8, 0)):
        assert abs(bs.batch_deadline("pm", now, t) - 180 * 60) <= 2
    # 清晨時段牌鐘不綁，但**全場預算照樣綁**：耗掉 100 分 → 225-100-15=110 分
    assert abs(bs.batch_deadline("pm", now - 100 * 60, tpe(0, 10)) - 110 * 60) <= 2
    # 對照組：同樣是「距 23:00 很遠」，19:00 早已有測試涵蓋；這裡確認清晨與它同值，
    # 也就是跨午夜沒有走進別條路徑
    assert bs.batch_deadline("pm", now, tpe(0, 10)) == bs.batch_deadline("pm", now, tpe(19, 0))
