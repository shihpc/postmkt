// tests/test_sentiment_frontend.mjs —— 市場情緒 tab 前端純函式（2026-09-29，規格正本 taiwan-flows/docs/sentiment-tab.md §3）
// 從 index.html 抽出 `sent-pure:begin`～`sent-pure:end` 區段在 node vm 沙箱跑，以 tests/fixtures/sentiment_sample.json
// （最末列 2026-09-24 取規格 §0 實測數字，其餘為合成歷史）驗百分位／差值／均值／均線／SVG path／格式化，
// 並以原始碼靜態檢查 M6（純描述：無判斷字樣、無紅綠色票）與 M4／M5（SENT_URL 同源相對路徑、只在 lazy 函式裡載）。
// 用法：node tests/test_sentiment_frontend.mjs（pytest 由 tests/test_sentiment_frontend.py 代跑）
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const B = "// ---- sent-pure:begin", E = "// ---- sent-pure:end ----";
assert.equal(html.split(B).length, 2, "sent-pure:begin 須唯一");
assert.equal(html.split(E).length, 2, "sent-pure:end 須唯一");
const pure = html.slice(html.indexOf(B), html.indexOf(E));

const sb = { console };
vm.createContext(sb);
new vm.Script(pure + `
Object.assign(this, { SENT_DATE_RE, SENT_WIN, SENT_DISCLAIMER, sentDisclaimer, sentNum, sentGenOk, sentRows, sentSeries, sentDiff, sentStats, sentMa, sentRange, sentPath, sentFmt, sentSigned });`).runInContext(sb);
const S = sb;
const J = JSON.parse(fs.readFileSync(path.join(ROOT, "tests", "fixtures", "sentiment_sample.json"), "utf8"));

let n = 0;
const ok = (name, f) => { f(); n++; console.log("ok  ", name); };
const R = x => JSON.parse(JSON.stringify(x));   // vm 另一個 realm 的物件：deepEqual 前先轉回本 realm
const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} ≉ ${b}`);

ok("常數：60 筆窗、日期白名單、免責句逐字照規格 §3", () => {
  assert.equal(S.SENT_WIN, 60);
  assert.equal(S.SENT_DISCLAIMER, "情緒指標為現況描述，非買賣訊號；無回測依據。");
  for (const d of ["2026-09-24"]) assert.ok(S.SENT_DATE_RE.test(d));
  for (const d of ["2026-9-24", "2026/09/24", "<img>", "2026-09-24x", " 2026-09-24"]) assert.ok(!S.SENT_DATE_RE.test(d), d);
});

ok("sentDisclaimer：前半逐字不變；後半取第一個有 vix 值的列日期（不寫死），無值時省略", () => {
  const BASE = "情緒指標為現況描述，非買賣訊號；無回測依據。";
  // 正例：跳過 vix 為 null／缺欄／字串的前幾列，取第一個有值者
  assert.equal(S.sentDisclaimer([{ date: "2026-03-02", vix: null }, { date: "2026-03-05" }, { date: "2026-03-10", vix: "20.1" },
    { date: "2026-03-11", vix: 21.5 }, { date: "2026-03-12", vix: 22 }]), BASE + "VIX 歷史自 2026-03-11 起。");
  assert.equal(S.sentDisclaimer(S.sentRows(J)), BASE + `VIX 歷史自 ${S.sentRows(J).find(r => typeof r.vix === "number").date} 起。`);
  // 反例：無資料／vix 全 null／日期不合白名單 → 只有前半
  for (const rows of [null, undefined, [], [{ date: "2026-03-11", vix: null }], [{ date: "2026-03-11" }],
                      [{ date: "<img src=x>", vix: 1 }], [{ date: "2026/03/11", vix: 1 }], "garbage"])
    assert.equal(S.sentDisclaimer(rows), BASE, JSON.stringify(rows));
});

ok("sentNum：只收有限 number", () => {
  assert.equal(S.sentNum(1.5), 1.5); assert.equal(S.sentNum(0), 0);
  for (const v of [null, undefined, "23.12", NaN, Infinity, {}, [1], true]) assert.equal(S.sentNum(v), null, String(v));
});

ok("sentRows：形狀不對回 null；壞日期剔除、同日後者覆寫、升序", () => {
  assert.equal(S.sentRows(null), null); assert.equal(S.sentRows({}), null); assert.equal(S.sentRows({ rows: {} }), null);
  const r = S.sentRows({ rows: [
    { date: "2026-09-24", vix: 1 }, { date: "2026-09-22", vix: 2 }, { date: "<img src=x>", vix: 3 },
    { date: "2026-09-24", vix: 4 }, null, [1], { date: 20260923, vix: 5 }, { vix: 6 } ] });
  assert.deepEqual(R(r.map(x => [x.date, x.vix])), [["2026-09-22", 2], ["2026-09-24", 4]]);
});

const rows = S.sentRows(J);
ok("樣本：80 列、末列 2026-09-24 為規格 §0 實測數字", () => {
  assert.equal(rows.length, 80);
  const L = rows[rows.length - 1];
  assert.equal(L.date, "2026-09-24");
  assert.equal(L.vix, 23.12); assert.equal(L.pc_oi, 85.33); assert.equal(L.pc_vol, 121.11);
  assert.equal(L.retail_net, 7415); assert.equal(L.inst_long, 3304); assert.equal(L.inst_short, 10719);
});

ok("sentSeries：null／缺欄／字串的日子跳過（不當 0）", () => {
  const s = S.sentSeries([{ date: "a", x: 1 }, { date: "b", x: null }, { date: "c" }, { date: "d", x: "2" }, { date: "e", x: 0 }], "x");
  assert.deepEqual(R(s.map(p => p.date)), ["a", "e"]);
});

ok("sentDiff：最新減前一筆有值；不足兩筆回 null", () => {
  assert.equal(S.sentDiff([]), null); assert.equal(S.sentDiff([{ date: "a", v: 1 }]), null);
  const s = S.sentSeries(rows, "vix"), d = S.sentDiff(s);
  assert.equal(d.date, "2026-09-24"); assert.equal(d.prevDate, "2026-09-23");
  close(d.d, 23.12 - rows[rows.length - 2].vix);
  // 前一列缺值 → 跳到再前一筆有值的日子
  const g = S.sentDiff(S.sentSeries([{ date: "1", x: 10 }, { date: "2", x: null }, { date: "3", x: 12.5 }], "x"));
  assert.equal(g.prevDate, "1"); close(g.d, 2.5);
});

// 獨立對照實作（不同寫法）：百分位＝≤ 最新值的比例
const refStats = (vals, w) => { const win = vals.slice(Math.max(0, vals.length - w)), x = win[win.length - 1];
  return { n: win.length, pct: Math.round(100 * win.filter(v => v <= x).length / win.length), mean: win.reduce((a, b) => a + b, 0) / win.length }; };
ok("sentStats：近 60 筆百分位與均值（三個指標，對照獨立實作）", () => {
  for (const k of ["vix", "pc_oi", "pc_vol", "retail_ratio"]){
    const s = S.sentSeries(rows, k), st = S.sentStats(s, 60), ref = refStats(s.map(p => p.v), 60);
    assert.equal(st.n, 60); assert.equal(st.full, true); assert.equal(st.pct, ref.pct, k); close(st.mean, ref.mean);
  }
});
ok("sentStats：不足 60 筆以實有筆數、full=false；邊界（最小／最大／單筆／同值）", () => {
  const mk = a => a.map((v, i) => ({ date: String(i), v }));
  let st = S.sentStats(mk([5, 3, 4]), 60);
  assert.deepEqual([st.n, st.full, st.pct], [3, false, 67]); close(st.mean, 4);
  st = S.sentStats(mk([5, 3, 1]), 60); assert.equal(st.pct, 33);          // 最小值：只有自己 ≤ 自己
  st = S.sentStats(mk([1, 3, 9]), 60); assert.equal(st.pct, 100);         // 最大值
  st = S.sentStats(mk([7]), 60); assert.deepEqual([st.n, st.pct, st.mean], [1, 100, 7]);
  st = S.sentStats(mk([2, 2, 2, 2]), 60); assert.equal(st.pct, 100);
  assert.equal(S.sentStats([], 60), null);
  // 窗外的舊值不影響
  st = S.sentStats(mk([100, 1, 2]), 2); assert.deepEqual([st.n, st.pct], [2, 100]); close(st.mean, 1.5);
});

ok("sentMa：前 n-1 點為 null，之後為含自身 n 筆均值", () => {
  const s = [1, 2, 3, 4, 5].map((v, i) => ({ date: String(i), v }));
  const m = S.sentMa(s, 3);
  assert.deepEqual(R(m.slice(0, 2)), [null, null]); close(m[2], 2); close(m[3], 3); close(m[4], 4);
  const vs = S.sentSeries(rows, "vix"), m60 = S.sentMa(vs, 60);
  assert.equal(m60.filter(v => v === null).length, 59);
  close(m60[m60.length - 1], refStats(vs.map(p => p.v), 60).mean, 1e-9);
  assert.ok(S.sentMa(vs.slice(0, 30), 60).every(v => v === null));   // 不足 60 筆：整條不畫
});

ok("sentRange：只看實際出現的值（忽略 null）", () => {
  assert.deepEqual(R(S.sentRange([3, null, -1, 8])), { lo: -1, hi: 8 });
  assert.equal(S.sentRange([null]), null); assert.equal(S.sentRange([]), null);
});

ok("sentPath：等距 x、值域映射 y、null 斷線、單點與同值置中", () => {
  assert.equal(S.sentPath([], 0, 100, 0, 50, 0, 1), "");
  assert.equal(S.sentPath([0, 10], 0, 100, 0, 50, 0, 10), "M0 50L100 0");
  assert.equal(S.sentPath([0, 5, 10], 10, 110, 0, 100, 0, 10), "M10 100L60 50L110 0");
  assert.equal(S.sentPath([0, null, 10, 5], 0, 30, 0, 10, 0, 10), "M0 10 M20 0L30 5");
  assert.equal(S.sentPath([null, null], 0, 30, 0, 10, 0, 10), "");
  assert.equal(S.sentPath([4], 0, 100, 0, 50, 4, 4), "M50 25");
  assert.equal(S.sentPath([4, 4], 0, 100, 0, 50, 4, 4), "M0 25L100 25");
  const d = S.sentPath(S.sentSeries(rows, "vix").map(p => p.v), 50, 552, 8, 130, 12, 35);
  assert.equal((d.match(/[ML]/g) || []).length, 80); assert.ok(!/NaN|Infinity/.test(d));
});

ok("sentFmt／sentSigned：toFixed＋千分位、非數值「—」、帶號", () => {
  assert.equal(S.sentFmt(59603, 0), "59,603"); assert.equal(S.sentFmt(85.33, 2), "85.33"); assert.equal(S.sentFmt(23.1, 2), "23.10");
  assert.equal(S.sentFmt(null, 2), "—"); assert.equal(S.sentFmt("<b>", 2), "—");
  assert.equal(S.sentSigned(7415, 0), "+7,415"); assert.equal(S.sentSigned(-3.456, 2), "-3.46");
  assert.equal(S.sentSigned(0.001, 2), "±0.00"); assert.equal(S.sentSigned(null, 2), "—");
  assert.equal(S.sentSigned(23.12 - 22.5, 2), "+0.62");
});

// ---- 靜態檢查（讀碼）----
ok("index.html 內嵌 script 整段可編譯（語法錯誤會讓全站 17 個 tab 一起掛掉）", () => {
  const m = html.match(/<script>([\s\S]*)<\/script>/);
  assert.ok(m, "找不到內嵌 <script>");
  new vm.Script(m[1], { filename: "index.html<script>" });   // 只編譯、不執行
});
const secStart = html.indexOf("// ================= 市場情緒 tab");
const secEnd = html.indexOf("// ---------- 日期 tab");
assert.ok(secStart > 0 && secEnd > secStart, "找不到市場情緒 tab 區段");
const sec = html.slice(secStart, secEnd);
ok("M6：區段內（去註解、去免責句常數）無判斷字樣；無紅綠色票", () => {
  const code = sec.split("\n").filter(l => !/^\s*\/\//.test(l) && !/const SENT_DISCLAIMER/.test(l)).join("\n");
  for (const w of ["偏多", "偏空", "建議", "訊號", "看多", "看空", "買進", "賣出", "樂觀", "悲觀", "恐慌", "貪婪"]) assert.ok(!code.includes(w), w);
  const css = html.slice(html.indexOf("/* 市場情緒 tab"), html.indexOf("/* 手機（2026-09-06 批次二 #12）"));
  for (const c of ["#ef5b5b", "#2fbf71", "--up", "--down"]) { assert.ok(!sec.includes(c), c); assert.ok(!css.includes(c), c); }
});
ok("M4／M5：SENT_URL 同源相對路徑、只在 sentEnsure 內載入、load() 不碰", () => {
  assert.ok(html.includes('const SENT_URL = "../taiwan-flows/data/sentiment.json";'));
  assert.equal(html.split("loadJSON(SENT_URL)").length, 2);
  const ens = sec.slice(sec.indexOf("function sentEnsure("), sec.indexOf("function sentSvg("));
  assert.ok(ens.includes("loadJSON(SENT_URL)"));
  const load = html.match(/^function load\(\)\{.*\}$/m)[0];
  assert.ok(!/sent/i.test(load), load);
});
ok("sentGenOk：generated_at 須以 ISO 8601 YYYY-MM-DDTHH:MM 開頭才顯示，否則「—」", () => {
  for (const v of [J.generated_at, "2026-09-29T21:30:05+08:00", "2026-09-29T21:30", "2026-09-29T13:30:05Z"])
    assert.equal(S.sentGenOk(v), true, String(v));
  for (const v of [null, undefined, "", 1759152605, "2026-09-29", "2026-09-29 21:30:05", "<img src=x>2026-09-29T21:30",
                   " 2026-09-29T21:30", "2026/09/29T21:30", "garbage", {}, ["2026-09-29T21:30"]])
    assert.equal(S.sentGenOk(v), false, String(v));
  const rend = html.slice(html.indexOf("function sentRender("), html.indexOf("// ---------- 日期 tab"));
  assert.ok(rend.includes("sentGenOk(SENT.j.generated_at) ? fmtGenTaipei(SENT.j.generated_at)"), "sentRender 須先過形狀檢查");
  assert.ok(rend.includes("產出 —"), "形狀不合時顯示「產出 —」");
});
ok("措辭：百分位／均值／均線寫「筆有值資料」而非「日」（序列跳過 null，跨度可能多於 N 個交易日）", () => {
  const rend = html.slice(html.indexOf(B), html.indexOf("// ---------- 日期 tab"));
  assert.ok(rend.includes("筆有值資料第 ${st.pct} 百分位"));
  assert.ok(!/近 \$\{st\.n\} 日/.test(rend) && !rend.includes("60 日均線"));
});
ok("M7：區段內 innerHTML 拼接的外來字串都過 esc()（日期／generated_at）", () => {
  // 所有 ${…date…} 插值都必須包在 esc( ) 裡
  const hits = [...sec.matchAll(/\$\{([^}]*\b(?:date|prevDate|d0|d1|gen)\b[^}]*)\}/g)].map(m => m[1]);
  assert.ok(hits.length >= 8, "插值檢查命中過少，規則可能失效：" + hits.length);
  const bad = hits.filter(x => !/^esc\(/.test(x.trim()));
  assert.deepEqual(bad, []);
});

console.log(`\n${n} passed`);
