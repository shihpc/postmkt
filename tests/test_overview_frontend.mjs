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
new vm.Script(pure + "\nglobalThis.S = { OV_LABEL, OV_STATUS, OV_SUMFILE_RE, ovNum, ovDate, ovFmt, ovSigned, ovLabel, ovShapeOk, ovSide, OV_SIDES, ovSources, ovRows, ovSynthSection, ovTotals, ovFutOi, ovMktbal, ovYmd, ovHoldLayer, ovHoldMatch };").runInContext(sb);
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
ok("ovSide：流入側＝頂層 sectors／stocks；流出側＝頂層 out；out 缺或形狀不合 → null（畫面顯示「尚無資料」）", () => {
  const lay = t => ({ sources: [], rows: [{ key: t, count: 2, hits: [] }] });
  const g = { schema: 1, sectors: lay("入類"), stocks: lay("入股"), out: { sectors: lay("出類"), stocks: lay("出股") } };
  assert.deepEqual(J(S.OV_SIDES), [["in", "資金流入側"], ["out", "資金流出側"]]);
  assert.equal(S.ovSide(g, "in").sectors.rows[0].key, "入類"); assert.equal(S.ovSide(g, "in").stocks.rows[0].key, "入股");
  assert.equal(S.ovSide(g, "out").sectors.rows[0].key, "出類"); assert.equal(S.ovSide(g, "out").stocks.rows[0].key, "出股");
  assert.equal(S.ovSide(g, "亂填").sectors.rows[0].key, "入類");            // 不認得的值一律流入側
  const old = J(g); delete old.out;
  assert.equal(S.ovSide(old, "out"), null); assert.equal(S.ovSide(old, "in").stocks.rows[0].key, "入股");   // 舊檔：流出側尚無資料、流入側照常
  assert.equal(S.ovSide({ ...g, out: { sectors: lay("x") } }, "out"), null);
  assert.equal(S.ovSide({ ...g, out: { sectors: lay("x"), stocks: { sources: [] } } }, "out"), null);
  assert.equal(S.ovSide({ ...g, out: "x" }, "out"), null);
  assert.equal(S.ovShapeOk(old), true);                                       // out 缺不影響整檔形狀檢查
  assert.equal(S.ovSide(null, "in"), null); assert.equal(S.ovSide({ ...g, schema: 2 }, "out"), null);
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
ok("說明列寫明：排序無回測、計票群組、D 的計入條件、輪動雷達 0/12；流出側如實寫出各來源定案（含無對應來源者）", () => {
  assert.ok(sec.includes("以計票群組計") && sec.includes("資料日是前一交易日") && sec.includes("不是獨立來源"));
  assert.ok(sec.includes("沒有回測依據") && sec.includes("0/12 顯著"));
  for (const w of ["淨賣前 10", "「加速流出」象限", "次產業減碼前 10", "「轉弱」或「落後」", "同步賣超", "減碼共識", "Miss／低預期仍Miss", "週減前 20",
    "沒有流出側的對應來源，不納入", "不是操作建議"]) assert.ok(sec.includes(w), w);
});
ok("兩側切換：預設流入側、狀態只存記憶體（不進 hash／localStorage）、切換不發請求", () => {
  assert.ok(html.includes('const OV = { d: {}, err: {}, loading: {}, side: "in" };'));
  assert.ok(sec.includes('data-ovside="${esc(k)}"') && sec.includes('e.target.closest("[data-ovside]")'));
  assert.ok(sec.includes('if ((k === "in" || k === "out") && k !== OV.side){ OV.side = k; render(); }'));
  assert.equal(sec.split("OV.side = ").length - 1, 1, "OV.side 只該在切換 listener 內賦值");
  assert.ok(!/localStorage|sessionStorage|replaceState|location\.hash/.test(sec), "市場總覽區段不得碰儲存或網址");
  for (const fn of ["parseHash", "currentHash", "applyHash"]){
    const i = html.indexOf("function " + fn + "("), body = html.slice(i, html.indexOf("\n}\n", i));
    assert.ok(i > 0 && !/OV\.|ovside/.test(body), fn + " 不得讀寫總覽的側別");
  }
  assert.ok(sec.includes("資金流出側尚無資料") && sec.includes("資金流入側不受影響"));
  // 標示句在切換鈕與 if(!j) 分支之前無條件輸出（兩側、三種狀態都看得到）
  const r = sec.slice(sec.indexOf("function ovRender("));
  assert.ok(r.indexOf('class="ov-label"') < r.indexOf('class="ov-sides"') && r.indexOf('class="ov-sides"') < r.indexOf("if (!j){"));
});
ok("用語：市場總覽區段與 SUBS.overview 一律「資金流出側」，不出現操作建議字樣", () => {
  const sub = html.match(/^\s*overview:"([^"]*)",/m)[1];
  for (const t of [sec, sub]) assert.ok(!/放空|做空|賣出建議|偏空側|看空|賣出訊號/.test(t));
  assert.ok(sub.includes("資金流出側") && sec.includes("資金流出側"));
});
ok("不改 tbl()：交集表走既有 tbl(cols, rows, opts)，CSS 一律 .ov- 前綴", () => {
  assert.ok(sec.includes("tbl(cols, rows, { sortI: 1, sortD: -1 })"));
  const css = html.slice(html.indexOf("/* 市場總覽 tab"), html.indexOf("/* 月營收 tab"));
  for (const m of css.matchAll(/^\s*(\.[a-z][^{]*)\{/gm)) assert.ok(m[1].split(",").every(x => x.trim().startsWith(".ov-")), m[1]);
});
// ---- 我的持股對照（規格 §7）----
const HSRC = (id, group, status, keys, extra) => ({ id, name: "來源" + id, group, status, counted: status === "valid", date: "2026-11-12", n: keys.length,
  items: keys.map(k => typeof k === "string" ? { key: k } : k), ...(extra || {}) });
const HFIX = () => ({ schema: 1, date: "2026-11-12", sectors: { sources: [], rows: [] },
  stocks: { sources: [
      HSRC("a", "a", "valid", [{ key: "1111", name: "甲一" }, { key: "3333", name: "丙三" }]),
      HSRC("b", "b", "valid", ["3333"]),
      HSRC("x1", "flow", "valid", ["4444"]), HSRC("x2", "flow", "valid", [{ key: "4444", name: "丁四" }]),
      HSRC("s", "s", "stale", ["5555", "1111"], { counted: true }),          // 過期來源（即使檔內 counted 誤標為真也不對照）
      HSRC("f", "f", "fail", ["5555"]), HSRC("l", "l", "listed", ["5555"]), HSRC("e", "e", "excluded", ["5555"]),
    ], rows: [{ key: "3333", count: 2, hits: ["a", "b"], name: "丙三" }] },
  out: { sectors: { sources: [], rows: [] },
    stocks: { sources: [
        HSRC("a", "a", "valid", [{ key: "2222", name: "乙二" }, "3333"]),
        HSRC("d", "d", "valid", ["2222"]),
        HSRC("s", "s", "stale", ["9999"]),
      ], rows: [{ key: "2222", count: 2, hits: ["a", "d"], name: "乙二" }] } } });
const HCODES = ["9999", "2222", "1111", "3333", "4444", "5555", "1111", 123, "", null];
ok("持股對照：命中判定、兩側並列、順序＝持股原順序、未命中只計數、過期／失敗／另列／不納入來源不對照", () => {
  const m = J(S.ovHoldMatch(HCODES, HFIX()));
  assert.equal(m.date, "2026-11-12"); assert.equal(m.total, 6); assert.equal(m.hasOut, true);
  assert.deepEqual(m.rows.map(r => r.code), ["2222", "1111", "3333", "4444"]);     // 持股原順序；9999／5555 不逐檔列出
  assert.equal(m.miss, 2);                                                         // 9999（只在流出側過期來源）、5555（只在流入側過期／失敗／另列／不納入來源）
  const by = Object.fromEntries(m.rows.map(r => [r.code, r]));
  assert.deepEqual(by["2222"], { code: "2222", name: "乙二", inHits: [], outHits: ["a", "d"], inInter: false, outInter: true });
  assert.deepEqual(by["1111"], { code: "1111", name: "甲一", inHits: ["a"], outHits: [], inInter: false, outInter: false });   // 過期來源 s 不列入 inHits
  assert.deepEqual(by["3333"], { code: "3333", name: "丙三", inHits: ["a", "b"], outHits: ["a"], inInter: true, outInter: false });
  assert.deepEqual(m.inSrcs.map(s => s.id), ["a", "b", "x1", "x2"]); assert.deepEqual(m.outSrcs.map(s => s.id), ["a", "d"]);
  assert.equal(m.inSrcs[0].name, "來源a"); assert.equal(m.inSrcs[0].date, "2026-11-12");
});
ok("持股對照：交集內判定以計票群組計（取資料檔 rows），同組兩個來源都命中不算在交集內", () => {
  const r = J(S.ovHoldMatch(["4444"], HFIX())).rows[0];
  assert.deepEqual(r.inHits, ["x1", "x2"]); assert.equal(r.inInter, false); assert.equal(r.name, "丁四");
  // rows 裡有、但沒有任何計入來源命中的代號（檔案不一致）不會被標成在交集內
  const g = HFIX(); g.stocks.rows.push({ key: "2222", count: 2, hits: ["a", "b"] });
  assert.equal(J(S.ovHoldMatch(["2222"], g)).rows[0].inInter, false);
});
ok("持股對照：out 缺或形狀不合 → 只對照流入側（hasOut=false），不讀半套的 out", () => {
  const old = HFIX(); delete old.out;
  const half = HFIX(); delete half.out.sectors;                                     // out.stocks 還在但整個 out 形狀不合
  for (const g of [old, half, { ...HFIX(), out: "x" }]){
    const m = J(S.ovHoldMatch(HCODES, g));
    assert.equal(m.hasOut, false); assert.deepEqual(m.outSrcs, []);
    assert.deepEqual(m.rows.map(r => r.code), ["1111", "3333", "4444"]); assert.equal(m.miss, 3);
    assert.ok(m.rows.every(r => r.outHits.length === 0 && r.outInter === false));
  }
});
ok("持股對照：持股空／壞資料、資料檔不可用", () => {
  assert.equal(S.ovHoldMatch(["1111"], null), null); assert.equal(S.ovHoldMatch(["1111"], { schema: 2 }), null);
  for (const c of [[], null, undefined, "1111", { 0: "1111" }, [null, 1, {}, ""]]){
    const m = J(S.ovHoldMatch(c, HFIX())); assert.equal(m.total, 0); assert.deepEqual(m.rows, []); assert.equal(m.miss, 0);
  }
  const m = J(S.ovHoldMatch(["8888", "7777"], HFIX())); assert.equal(m.total, 2); assert.deepEqual(m.rows, []); assert.equal(m.miss, 2);
  assert.equal(J(S.ovHoldMatch(["__proto__", "constructor"], HFIX())).miss, 2);    // 物件原型鍵不會誤命中
  const g = HFIX(); g.out.stocks.sources[0].items = [{ key: "6666", name: "<b>x</b>" }, { key: "6667", name: 5 }];
  assert.deepEqual(J(S.ovHoldMatch(["6667", "6666"], g)).rows.map(r => [r.code, r.name]), [["6667", ""], ["6666", "<b>x</b>"]]);   // 名稱原樣回傳（渲染端 esc）；非字串當空
});
ok("持股對照：repo 內實際資料檔——兩側交集表每一列的代號都判為在該側交集內，且命中來源＝該列 hits", () => {
  const real = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "overview", "latest.json"), "utf8"));
  for (const [side, lay] of [["in", real.stocks], ["out", real.out && real.out.stocks]]){
    if (!lay) continue;
    const m = J(S.ovHoldMatch(lay.rows.map(r => r.key), real));
    assert.equal(m.rows.length, lay.rows.length);
    lay.rows.forEach((r, i) => {
      const x = m.rows[i]; assert.equal(x.code, r.key);
      assert.equal(side === "in" ? x.inInter : x.outInter, true);
      assert.deepEqual([...(side === "in" ? x.inHits : x.outHits)].sort(), [...r.hits].sort());
    });
  }
});
ok("持股對照（讀碼）：沿用 diagHoldings()＋HOLD_CODE_RE；零請求、不碰儲存／網址；不放側欄鈕；標示句在所有 return 之前；用語中性", () => {
  const i0 = sec.indexOf("function ovHoldCodes("), i1 = sec.indexOf("function ovRender(");
  assert.ok(i0 > 0 && i1 > i0);
  const body = sec.slice(i0, i1);
  assert.ok(body.includes("diagHoldings().map(") && body.includes("HOLD_CODE_RE.test(c)"));
  assert.equal(html.split("function diagHoldings(").length - 1, 1, "持股讀取入口只該有一份");
  assert.equal(sec.replace(/^\s*\/\/.*$/gm, "").split("diagHoldings(").length - 1, 1); assert.equal(sec.split("ovHoldCodes(").length - 1, 2);
  // 隱私：對照段不得發請求、不得碰瀏覽器儲存／網址／歷史，也不得產生連結或帶代號的 data-* 屬性
  assert.ok(!/ovLoad|loadJSON|fetch\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|import\(/.test(body));
  assert.ok(!/localStorage|sessionStorage|indexedDB|document\.cookie|location|history|replaceState|pushState|syncHash/.test(body));
  assert.ok(!/nameCell|stkBtn|data-stk|data-mychg|href=|<a |<img|src=/.test(body), "不得放個股摘要側欄鈕或連結（會把代號帶進網址）");
  assert.deepEqual([...body.matchAll(/data-[a-z]+=/g)].map(x => x[0]), ['data-ovgo=']);
  assert.ok(body.includes('data-ovgo="diag"'), "前往持股診斷的鈕只帶固定字面量");
  for (const fn of ["parseHash", "currentHash", "applyHash", "syncHash"]){
    const i = html.indexOf("function " + fn + "("), b = html.slice(i, html.indexOf("\n}\n", i));
    assert.ok(i > 0 && !/ovHold/.test(b), fn + " 不得碰持股對照");
  }
  // 站內切 tab 的 listener 只改 state.tab
  assert.ok(sec.includes('if (!b || state.tab !== "overview" || b.getAttribute("data-ovgo") !== "diag") return;\n  state.tab = "diag"; pmUserRender();'));
  // 純函式不依賴環境
  const pureHold = pure.slice(pure.indexOf("function ovHoldLayer("));
  assert.ok(!/document|window|localStorage|diagHoldings|state\.|OV\./.test(pureHold));
  // 四種狀態：標示句在 ovHoldHtml 的第一個 return 之前無條件輸出
  const hh = body.slice(body.indexOf("function ovHoldHtml("));
  const iLab = hh.indexOf('<div class="ov-label">${esc(ovLabel(j))}</div>'), iRet = hh.indexOf("return ");
  assert.ok(iLab > 0 && iRet > iLab);
  for (const w of ["尚未設定持股清單", "尚未產生或讀取失敗", "都沒有出現在任何個股層來源", "其餘 ", "只對照<b>個股層</b>來源", "會新增網路請求", "對照所用資料日",
    "只在本機比對，不外送", "流入側來源", "流出側來源", "在交集表內", "持股清單原順序"]) assert.ok(hh.includes(w), w);
  assert.ok(!/買進|賣出|放空|做空|建議|加碼|減碼|偏多|偏空|看多|看空/.test(body.replace(/^\s*\/\/.*$/gm, "")), "對照段不得出現操作字樣");
  assert.ok(!/\.sort\(/.test(body) && !/\.sort\(/.test(pureHold), "不排序");
  // 位置：交集表之後、寫入 #main 之前；兩側並列（不看 OV.side）
  const r = sec.slice(i1);
  assert.ok(r.indexOf("ovTableHtml(sd.stocks, true)") < r.indexOf("ovHoldHtml(j) + `</div>`;") && r.indexOf("ovHoldHtml(j) + `</div>`;") < r.indexOf("main.innerHTML"));
  assert.ok(!/OV\.side/.test(body));
  // 外來字串與持股字串都經 esc()
  for (const w of ["esc(r.code)", "esc(r.name)", "esc(a.join(", "esc(s.id)", "esc(s.name)", "esc(m.date"]) assert.ok(hh.includes(w), w);
});
console.log(`\n${n} passed`);
