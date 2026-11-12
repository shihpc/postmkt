// tests/test_overview_frontend.mjs —— 市場總覽 tab 前端純函式＋靜態守門（2026-11-12，規格 docs/market-overview.md §2／§4／§5）
// 以 node 從 index.html 抽 ov-pure 區段執行；免網路。pytest 由 tests/test_overview_frontend.py 代跑。
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const B = "// ---- ov-pure:begin", E = "// ---- ov-pure:end ----";
assert.ok(html.indexOf(B) > 0 && html.indexOf(E) > html.indexOf(B), "找不到 ov-pure 區段");
const pure = html.slice(html.indexOf(B), html.indexOf(E));
const sb = { console };
vm.createContext(sb);
new vm.Script(pure + "\nglobalThis.S = { OV_LABEL, OV_STATUS, OV_SUMFILE_RE, ovNum, ovDate, ovFmt, ovSigned, ovLabel, ovShapeOk, ovSources, ovRows, ovSynthSection, ovTotals, ovFutOi, ovMktbal, ovYmd };").runInContext(sb);
const S = sb.S;
let n = 0;
const ok = (name, fn) => { fn(); n++; console.log("ok - " + name); };
const J = o => JSON.parse(JSON.stringify(o));

ok("標示句逐字；資料檔 label 缺或不含該句時退回常數", () => {
  assert.equal(S.OV_LABEL, "AI 研判，未經回測，非保證");
  assert.equal(S.ovLabel(null), S.OV_LABEL);
  assert.equal(S.ovLabel({ label: "隨便" }), S.OV_LABEL);
  assert.equal(S.ovLabel({ label: 123 }), S.OV_LABEL);
  assert.equal(S.ovLabel({ label: "AI 研判，未經回測，非保證（試行）" }), "AI 研判，未經回測，非保證（試行）");
});
ok("ovNum／ovDate／格式：字串數字、NaN 一律當缺值", () => {
  assert.equal(S.ovNum("1"), null); assert.equal(S.ovNum(NaN), null); assert.equal(S.ovNum(0), 0);
  assert.equal(S.ovDate("2026-11-12"), "2026-11-12"); assert.equal(S.ovDate("2026/11/12"), ""); assert.equal(S.ovDate(null), "");
  assert.equal(S.ovFmt(1234.56, 1), "1,234.6"); assert.equal(S.ovFmt("x", 1), "—");
  assert.equal(S.ovSigned(-1165.28, 2), "-1,165.28"); assert.equal(S.ovSigned(3, 0), "+3"); assert.equal(S.ovSigned(0.001, 1), "0.0");
  assert.equal(S.ovYmd("2026-11-12"), "20261112"); assert.equal(S.ovYmd("../x"), "");
});
ok("ovShapeOk：schema 1 且兩層都有 sources／rows 陣列", () => {
  const g = { schema: 1, sectors: { sources: [], rows: [] }, stocks: { sources: [], rows: [] } };
  assert.equal(S.ovShapeOk(g), true);
  assert.equal(S.ovShapeOk({ ...g, schema: 2 }), false);
  assert.equal(S.ovShapeOk({ ...g, stocks: { sources: [] } }), false);
  assert.equal(S.ovShapeOk(null), false);
});
ok("ovSources：狀態白名單（不認得的當讀取失敗）、counted 只在 valid 成立", () => {
  const r = J(S.ovSources({ sources: [
    { id: "A", name: "甲", status: "valid", counted: true, date: "2026-11-12", n: 3, items: [{ key: "x" }, { key: 1 }] },
    { id: "D", name: "丁", status: "stale", counted: true, date: "2026-11-11", n: 2, items: [{ key: "y" }], unmapped: ["u", 3] },
    { id: "Z", status: "__proto__" }, { name: "沒 id" }, null,
  ] }));
  assert.deepEqual(r.map(s => [s.id, s.status, s.text, s.counted]), [["A", "valid", "有效", true], ["D", "stale", "過期不計", false], ["Z", "fail", "讀取失敗", false]]);
  assert.deepEqual(r[0].items, [{ key: "x" }]); assert.deepEqual(r[1].unmapped, ["u"]);
  assert.deepEqual(J(S.ovSources(null)), []);
});
ok("ovSources：計票群組（group／group_name）；缺 group 時各自成組", () => {
  const r = J(S.ovSources({ sources: [{ id: "A", status: "valid", counted: true, group: "flow", group_name: "法人資金流" },
    { id: "B", status: "valid", counted: true, group: "flow", group_name: "法人資金流" }, { id: "C", status: "valid", counted: true }] }));
  assert.deepEqual(r.map(s => [s.id, s.group, s.groupName]), [["A", "flow", "法人資金流"], ["B", "flow", "法人資金流"], ["C", "C", ""]]);
});
ok("ovRows：形狀不合的列丟棄、順序＝資料檔順序、via 攤平成文字", () => {
  const r = J(S.ovRows({ rows: [
    { key: "紡織", count: 3, hits: ["A", "C", "E"], via: { C: ["人造纖維"], E: ["領先"] } },
    { key: "2330", name: "台積電", count: 2, hits: ["a", 5] }, { key: 5, count: 2, hits: [] }, { key: "x", count: "2", hits: [] }, { key: "y", count: 2 },
  ] }));
  assert.deepEqual(r, [{ key: "紡織", name: "", count: 3, hits: ["A", "C", "E"], via: "C：人造纖維；E：領先" },
    { key: "2330", name: "台積電", count: 2, hits: ["a"], via: "" }]);
});
ok("ovSynthSection：只取「盤勢綜合研判」一節，到下一個 ## 或 --- 為止", () => {
  const t = "## 精華 alpha 標的\n\n### 1. 1303 南亞\n- x\n\n---\n\n## 盤勢綜合研判\n1. 甲\n2. 乙\n\n---\n*免責*";
  assert.equal(S.ovSynthSection(t), "1. 甲\n2. 乙");
  assert.equal(S.ovSynthSection("## 盤勢綜合研判（補充）\n甲\n## 其他\n乙"), "甲");
  assert.equal(S.ovSynthSection("## 別的\n甲"), ""); assert.equal(S.ovSynthSection(null), "");
});
ok("ovTotals：上市＋上櫃合計（億）與外資佔成交比；取最末交易日與其前一日", () => {
  const mk = (f, t, d) => ({ f_buy_k: 300, f_sell_k: 100, f_net_k: f, t_net_k: t, d_net_k: d, turnover_k: 1000 });
  const j = { dates: ["2026-11-11", "2026-11-12"], rows: { "2026-11-11": { tse: mk(1, 1, 1), otc: mk(1, 1, 1) }, "2026-11-12": { tse: mk(2e5, -1e5, 0), otc: mk(1e5, 5e4, 0) } } };
  const r = J(S.ovTotals(j));
  assert.deepEqual(r, { date: "2026-11-12", prev: "2026-11-11", f: 3, t: -0.5, d: 0, fShare: 20 });
  delete j.rows["2026-11-12"].otc.f_net_k;
  assert.equal(S.ovTotals(j).f, null);
  assert.equal(S.ovTotals({ dates: [], rows: {} }), null); assert.equal(S.ovTotals(null), null);
});
ok("ovFutOi：TX／外資 的多方 − 空方未平倉口數", () => {
  const cols = ["futures_id", "date", "institutional_investors", "long_open_interest_balance_volume", "short_open_interest_balance_volume"];
  const doc = { date: "2026-11-12", cols, rows: [["MTX", "", "外資", 1, 2], ["TX", "", "投信", 9, 9], ["TX", "", "外資", 7218, 106791]] };
  assert.deepEqual(J(S.ovFutOi(doc)), { date: "2026-11-12", net: -99573 });
  assert.equal(S.ovFutOi({ ...doc, rows: [["TX", "", "外資", "7218", 1]] }), null);
  assert.equal(S.ovFutOi({ cols: ["x"], rows: [] }), null); assert.equal(S.ovFutOi(null), null);
});
ok("ovMktbal：最末一列與前一列的金額（億）與異動", () => {
  const r = J(S.ovMktbal({ daily: [{ date: "2026-11-11", margin_money: 6e11, sbl_short_value: 3e12 }, { date: "2026-11-12", margin_money: 6.1e11, sbl_short_value: null }] }));
  assert.equal(r.date, "2026-11-12"); assert.equal(r.prev, "2026-11-11"); assert.equal(r.margin, 6100); assert.equal(Math.round(r.marginD), 100);
  assert.equal(r.sbl, null); assert.equal(r.sblD, null);
  assert.equal(S.ovMktbal({ daily: [] }), null);
});
ok("彙總檔名白名單", () => {
  assert.ok(S.OV_SUMFILE_RE.test("20261112-pm.json")); assert.ok(!S.OV_SUMFILE_RE.test("../x.json")); assert.ok(!S.OV_SUMFILE_RE.test("20261112-pm.json?x"));
});

// ---- 靜態檢查（讀碼）----
ok("index.html 內嵌 script 整段可編譯", () => {
  const m = html.match(/<script>([\s\S]*)<\/script>/);
  assert.ok(m); new vm.Script(m[1], { filename: "index.html<script>" });
});
const secStart = html.indexOf("// ================= 市場總覽 tab"), secEnd = html.indexOf("// ================= 籌碼雷達 tab");
assert.ok(secStart > 0 && secEnd > secStart, "找不到市場總覽 tab 區段");
const sec = html.slice(secStart, secEnd);
ok("TABS：overview 排第一、共 20 個；預設 tab 仍是 insight；SUBS.overview 帶標示句", () => {
  const body = html.slice(html.indexOf("const TABS = ["), html.indexOf("];", html.indexOf("const TABS = [")));
  const tabs = [...body.matchAll(/\["([a-z0-9]+)","([^"]+)"\]/g)].map(m => [m[1], m[2]]);
  assert.equal(tabs.length, 20);
  assert.deepEqual(tabs[0], ["overview", "市場總覽"]);
  assert.ok(/const state = \{ tab:"insight",/.test(html), "預設 tab 不得改變");
  const sub = html.match(/^\s*overview:"([^"]*)",/m);
  assert.ok(sub && sub[1].includes("AI 研判，未經回測，非保證"));
});
ok("lazy：資料只由 ovRender→ovEnsure 觸發，load()／首屏不碰 overview 的任何檔", () => {
  const load = html.match(/^function load\(\)\{.*$/m)[0];
  assert.ok(!/ov[A-Z]/.test(load), load);
  assert.equal(html.split("ovEnsure(").length - 1, 2, "ovEnsure 只該有定義與 ovRender 內一次呼叫");
  assert.ok(/function ovRender\(\)\{\s*ovEnsure\(\);/.test(sec));
  assert.equal(html.split("ovRender(").length - 1, 2);
  assert.ok(html.includes('else if (state.tab === "overview") ovRender();'));
  const rest = html.replace(sec, "").replace(/^\s*\/\/.*$/gm, "").replace(/\/\/ [^\n]*$/gm, "");
  assert.ok(!rest.includes("data/overview/") && !rest.includes("data/futures/"), "overview／futures 路徑只該出現在市場總覽區段（註解除外）");
});
ok("in-flight 去重＋失敗記錯不重試＋晚到只在本 tab 重繪", () => {
  assert.ok(sec.includes("if (OV.d[key] !== undefined || OV.err[key] || OV.loading[key]) return;"));
  assert.ok(sec.includes('if (state.tab === "overview") render();'));
});
ok("全部同源相對路徑：區段內沒有 http(s) 網址（CSP 不需改）", () => {
  assert.ok(!/https?:\/\//.test(sec));
});
ok("三種狀態都顯示標示句：ov-label 在 if(!j) 分支之前無條件輸出", () => {
  const r = sec.slice(sec.indexOf("function ovRender("));
  const iLabel = r.indexOf('<div class="ov-label">${esc(ovLabel(j))}</div>'), iBranch = r.indexOf("if (!j){");
  assert.ok(iLabel > 0 && iBranch > iLabel);
});
ok("盤勢 1–5 的渲染函式不含多空判斷字樣", () => {
  for (const fn of ["ovDayHtml", "ovTotalsHtml", "ovFutHtml", "ovSentHtml", "ovMktbalHtml"]){
    const i = sec.indexOf("function " + fn + "("), body = sec.slice(i, sec.indexOf("\n}\n", i));
    assert.ok(i > 0, fn);
    assert.ok(!/偏多|偏空|建議|看多|看空|買進|賣出訊號/.test(body), fn + " 出現判斷字樣");
  }
});
ok("盤勢 6、7 標「AI 研判」；mdToHtml 只被呼叫（區段內不重新定義三站同步碼）", () => {
  assert.equal(sec.split("{ ai: true }").length - 1, 2);
  assert.ok(sec.includes("mdToHtml(sec)"));
  for (const f of ["mdToHtml", "linkifyStocks", "callClaude", "ghSaveAnalysis"]) assert.ok(!sec.includes("function " + f));
});
ok("外來字串插值過 esc()：區段內 ${…} 直接引用 j./x./s./r./c. 欄位者必須包在 esc／ov*／sent*／sgn 等格式函式內", () => {
  const bad = [...sec.matchAll(/\$\{\s*((?:j|x|s|r|c|o|br|day)\.[A-Za-z_.]+)\s*\}/g)].map(m => m[1])
    .filter(v => !/^(s\.id|st\.n|st\.pct)$/.test(v));
  assert.deepEqual(bad, []);
});
ok("說明列寫明：只做偏多側、排序無回測、輪動雷達 0/12", () => {
  assert.ok(sec.includes("以計票群組計") && sec.includes("資料日是前一交易日") && sec.includes("不是獨立來源"));
  assert.ok(sec.includes("沒有回測依據") && sec.includes("只做偏多（資金流入）側，偏空側未做") && sec.includes("0/12 顯著"));
});
ok("不改 tbl()：交集表走既有 tbl(cols, rows, opts)，CSS 一律 .ov- 前綴", () => {
  assert.ok(sec.includes("tbl(cols, rows, { sortI: 1, sortD: -1 })"));
  const css = html.slice(html.indexOf("/* 市場總覽 tab"), html.indexOf("/* 月營收 tab"));
  for (const m of css.matchAll(/^\s*(\.[a-z][^{]*)\{/gm)) assert.ok(m[1].split(",").every(x => x.trim().startsWith(".ov-")), m[1]);
});
console.log(`\n${n} passed`);
