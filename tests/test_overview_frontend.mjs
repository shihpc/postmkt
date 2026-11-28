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
new vm.Script(pure + "\nglobalThis.S = { OV_LABEL, OV_STATUS, OV_SUMFILE_RE, ovNum, ovDate, ovFmt, ovSigned, ovLabel, ovShapeOk, ovSide, OV_SIDES, ovSources, ovRows, ovSynthSection, ovUsGateNote, ovSumBadge, ovTotals, ovFutOi, ovMktbal, ovYmd, ovHoldLayer, ovHoldMatch, OV_TOP_N, ovShort, ovMetrics, ovVal, ovVals, ovMd, ovPx, ovEntry, ovIx, ovTop, ovSkipLines };").runInContext(sb);
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
  assert.deepEqual(r, [{ key: "紡織", name: "", count: 3, hits: ["A", "C", "E"], via: "C：人造纖維；E：領先", px: null },
    { key: "2330", name: "台積電", count: 2, hits: ["a"], via: "", px: null }]);   // px（§8.4）：舊檔沒有 → null
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
ok("不改 tbl()：交集表（§8 起）自繪區塊、不經 tbl()、不提供欄位排序；CSS 一律 .ov- 前綴", () => {
  assert.ok(!/[^A-Za-z]tbl\(/.test(sec.replace(/^\s*\/\/.*$/gm, "").replace(/\/\/ [^\n]*$/gm, "")), "市場總覽區段不呼叫 tbl()");
  assert.equal(html.split("\nfunction tbl(").length - 1, 1, "tbl() 仍只有一份定義");
  assert.ok(!/\.sort\(/.test(sec.slice(sec.indexOf("// ---- 交集表渲染"), sec.indexOf("// ---- 我的持股對照（規格 §7，使用者"))), "交集表渲染不排序");
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
// ---- 2026-11-18：卡 6 徽章帶產出時間＋美股資料日未達預期的說明句 ----
const fmtTpe = x => { const t = Date.parse(x); return isNaN(t) ? String(x || "").slice(0, 16).replace("T", " ") : new Date(t).toLocaleString("sv-SE", { timeZone: "Asia/Taipei" }).slice(0, 16); };
ok("ovUsGateNote：us_gate.fresh===false 才出說明句；舊場次／pm 場／形狀不合一律空字串", () => {
  const run = { date: "2026-11-18", slot: "am", us_gate: { expected: "2026-11-17", got: "2026-11-16", fresh: false, waited_sec: 3600 } };
  assert.equal(S.ovUsGateNote(run), "本場產出時美股資料尚未更新（資料日 2026-11-16，預期 2026-11-17），文中美股數字可能是前一個交易日的。");
  assert.equal(S.ovUsGateNote({ us_gate: { expected: "2026-11-17", got: null, fresh: false } }), "本場產出時讀不到美股資料日（預期 2026-11-17），文中美股數字可能是前一個交易日的。");
  assert.equal(S.ovUsGateNote({ us_gate: { expected: "2026-11-17", got: "<img src=x>", fresh: false } }), "本場產出時讀不到美股資料日（預期 2026-11-17），文中美股數字可能是前一個交易日的。");   // 外來字串不過日期白名單就不進句子
  for (const c of [null, undefined, "x", {}, { us_gate: null }, { us_gate: "x" }, { us_gate: { expected: "2026-11-17", got: "2026-11-17", fresh: true } },
    { us_gate: { expected: "2026-11-17", got: "2026-11-16" } }, { us_gate: { expected: "2026-11-17", got: "2026-11-16", fresh: 0 } },
    { us_gate: { expected: "<b>", got: "2026-11-16", fresh: false } }, { us_gate: { got: "2026-11-16", fresh: false } }]) assert.equal(S.ovUsGateNote(c), "");
});
ok("ovSumBadge：資料日＋場次＋產出時間（台北）；同日只寫時分；generated_at 缺或壞掉不寫產出時間", () => {
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am", generated_at: "2026-11-18T07:05:12+08:00" }, fmtTpe), "2026-11-18 早場｜產出 07:05（台北）");
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am", generated_at: "2026-11-17T23:05:12Z" }, fmtTpe), "2026-11-18 早場｜產出 07:05（台北）");      // UTC 也轉台北
  assert.equal(S.ovSumBadge({ date: "2026-11-17", slot: "pm", generated_at: "2026-11-18T00:12:00+08:00" }, fmtTpe), "2026-11-17 晚場｜產出 2026-11-18 00:12（台北）");   // 晚場跨午夜：寫完整日期
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am" }, fmtTpe), "2026-11-18 早場");
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am", generated_at: "<script>" }, fmtTpe), "2026-11-18 早場");
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am", generated_at: 123 }, fmtTpe), "2026-11-18 早場");
  assert.equal(S.ovSumBadge({ date: "x", slot: "zz", generated_at: "2026-11-18T07:05:00+08:00" }, fmtTpe), "—｜產出 2026-11-18 07:05（台北）");
  assert.equal(S.ovSumBadge({ date: "2026-11-18", slot: "am", generated_at: "2026-11-18T07:05:00+08:00" }), "2026-11-18 早場");     // 沒給格式函式
  assert.equal(S.ovSumBadge(null, fmtTpe), ""); assert.equal(S.ovSumBadge(undefined, fmtTpe), "");
});
ok("卡 6（讀碼）：徽章走 ovSumBadge＋fmtGenTaipei；說明句經 esc()、排在研判內文之前；彙總分析自動產出同樣標示；三站同步碼只呼叫", () => {
  const i = html.indexOf("function ovSumHtml("), b = html.slice(i, html.indexOf("function ovBriefHtml(", i));
  assert.ok(i > 0 && b.includes("const usNote = ovUsGateNote(c);"));
  assert.ok(b.includes('(usNote ? `<div class="ov-usnote">${esc(usNote)}</div>` : "")'));
  assert.ok(b.indexOf("ov-usnote") < b.indexOf("mdToHtml(sec)"));
  assert.ok(b.includes("return ovSumBadge(OV.d.sum, fmtGenTaipei);"));
  assert.ok(html.includes('h += ovCard("6 盤勢綜合研判", "sumidx", ovSumDate(), ovSumHtml, { ai: true });'));
  assert.ok(html.includes("+ (OV.d[key] !== undefined && dateText ? `<span class=\"ov-date\">${esc(dateText)}</span>` : \"\")"), "徽章文字經 esc()");
  const sh = html.slice(html.indexOf("function summaryHtml("), html.indexOf("// ---------- 雲端歷史"));
  assert.ok(sh.includes('if (usNote) h += `<div class="ov-usnote">${esc(usNote)}</div>`;'));
  assert.equal(html.split("function mdToHtml(").length - 1, 1);
  assert.ok(!/us_gate/.test(html.slice(html.indexOf("function sumCtxPostmkt("), html.indexOf("function sumCtxPostmkt(") + 200)));
  for (const w of ["偏多", "偏空", "建議", "警告", "錯誤"]) assert.ok(!pure.slice(pure.indexOf("function ovUsGateNote("), pure.indexOf("function ovSynthSection(")).replace(/^\s*\/\/.*$/gm, "").includes(w), w);
});

// ====================== §8：交集表顯示各來源的實際數值、個股收盤與漲跌、各來源前幾名、說明收合（2026-11-28） ======================
const MT = (k, label, unit, digits, signed) => ({ k, label, unit, digits, signed: !!signed });
const S8 = () => ({ schema: 1, date: "2026-11-27", label: "AI 研判，未經回測，非保證",
  sectors: { base_date: "2026-11-27", sources: [
      { id: "A", name: "產業鏈資金流：近 5 日三大法人淨買前 10", group: "flow", group_name: "法人資金流", status: "valid", counted: true, date: "2026-11-27", n: 2,
        metrics: [MT("net", "近5日淨額", "億", 2, true)], items: [{ key: "食品", m: { net: 12.71 }, rank: 1 }, { key: "水泥", m: { net: 1.336 }, rank: 8 }] },
      { id: "B", name: "籌碼雷達：近 5 日對近 20 日「加速流入」象限", group: "flow", group_name: "法人資金流", status: "valid", counted: true, date: "2026-11-27", n: 1,
        metrics: [MT("a5", "近5日日均", "億/日", 2, true), MT("a20", "近20日日均", "億/日", 2, true)], items: [{ key: "食品", m: { a5: 2.54, a20: -0.004 } }] },
      { id: "C", name: "主動 ETF 次產業加碼前 10（上卷到產業）", group: "C", status: "valid", counted: true, date: "2026-11-27", n: 1,
        metrics: [MT("val", "主動淨額合計", "億", 2, true)], items: [{ key: "食品", via: ["乳品", "飲料", 5], m: { val: 3.5 }, rank: 2, viam: { "乳品": 2.25, "飲料": "x" } }] },
      { id: "D", name: "連湧／新湧次產業（上卷到產業）", group: "D", status: "stale", counted: false, date: "2026-11-26", n: 1, metrics: [], items: [{ key: "半導體", via: ["基板"] }] },
      { id: "E", name: "日級輪動雷達：連續 3 日「改善」或「領先」", group: "E", status: "valid", counted: true, date: "2026-11-27", n: 2,
        metrics: [MT("rs", "RS-Ratio", "", 2), MT("mom", "RS-Momentum", "", 2)], items: [{ key: "水泥", via: ["領先"], m: { rs: 100.58, mom: 100.45 } }, { key: "食品", via: ["改善"], m: { rs: 99.5, mom: null } }] },
    ], rows: [{ key: "食品", count: 3, hits: ["A", "B", "C", "E"], via: { C: ["乳品"] } }, { key: "水泥", count: 2, hits: ["A", "E"] }] },
  stocks: { base_date: "2026-11-27", sources: [
      { id: "a", name: "外資投信同步買超 Top30", group: "a", status: "valid", counted: true, date: "2026-11-27", n: 12,
        metrics: [MT("f", "外資", "億", 2, true), MT("t", "投信", "億", 2, true), MT("str", "強度", "億", 2)],
        items: Array.from({ length: 12 }, (_, i) => ({ key: String(2301 + i), name: "股" + i, rank: i + 1, m: { f: 6.47 - i, t: 4.47, str: 4.47 }, px: { close: 184.5 + i, chg_pct: 9.82 - i, date: "2026-11-27" } })) },
      { id: "d", name: "月營收 Beat／高預期仍Beat", group: "d", status: "valid", counted: true, date: "2026-10", n: 1,
        metrics: [MT("sur", "驚喜", "%", 1, true), MT("yoy", "年增", "%", 1, true)], items: [{ key: "2301", name: "股0", tag: "高預期仍Beat", m: { sur: 44.7, yoy: -3.25 }, px: null }] },
      { id: "e", name: "千張大戶週增前 20", group: "e", status: "fail", counted: false, date: null, n: 0, items: [] },
      { id: "f", name: "彙總分析精華標的", group: "f", status: "excluded", counted: false, date: null, n: 0, items: [], note: "不納入" },
    ], rows: [{ key: "2301", name: "股0", count: 2, hits: ["a", "d"], px: { close: 1234.5, chg_pct: -0.004, date: "2026-11-26" } }] } });
ok("§8 ovShort／ovMd：來源短名取「：」「（」之前；日期縮成 MM/DD（月頻原樣）", () => {
  assert.equal(S.ovShort("產業鏈資金流：近 5 日三大法人淨買前 10"), "產業鏈資金流"); assert.equal(S.ovShort("主動 ETF 次產業加碼前 10（上卷到產業）"), "主動 ETF 次產業加碼前 10");
  assert.equal(S.ovShort("選股二追蹤名單"), "選股二追蹤名單"); assert.equal(S.ovShort(null), ""); assert.equal(S.ovShort(5), "");
  assert.equal(S.ovMd("2026-11-26"), "11/26"); assert.equal(S.ovMd("2026-10"), "2026-10"); assert.equal(S.ovMd("<b>"), ""); assert.equal(S.ovMd(null), "");
});
ok("§8 ovMetrics：形狀不合的丟棄、digits 夾在 0–4（否則 2）、signed 只認 true；舊檔沒有 metrics → []", () => {
  assert.deepEqual(J(S.ovMetrics({ metrics: [MT("a", "甲", "億", 1, true), { k: "b", label: 5, unit: null, digits: 9, signed: "yes" }, { label: "沒 k" }, null, "x", { k: "" }] })),
    [{ k: "a", label: "甲", unit: "億", digits: 1, signed: true }, { k: "b", label: "", unit: "", digits: 2, signed: false }]);
  for (const x of [null, {}, { metrics: "x" }, { metrics: {} }]) assert.deepEqual(J(S.ovMetrics(x)), []);
});
ok("§8 ovVal／ovVals：數值先過有限數檢查（字串／NaN／null →「—」）、signed 才帶號與方向、四捨五入到 0 不帶負號", () => {
  const m = MT("v", "甲", "億", 2, true), u = MT("v", "乙", "分", 1, false);
  assert.deepEqual(J(S.ovVal(m, 12.714)), { label: "甲", unit: "億", text: "+12.71", sign: 1 });
  assert.deepEqual(J(S.ovVal(m, -1563.2)), { label: "甲", unit: "億", text: "-1,563.20", sign: -1 });
  assert.deepEqual(J(S.ovVal(m, -0.004)), { label: "甲", unit: "億", text: "0.00", sign: 0 });
  assert.deepEqual(J(S.ovVal(u, 77.84)), { label: "乙", unit: "分", text: "77.8", sign: 0 });        // 非 signed：不帶號、不著色
  for (const bad of ["1", NaN, Infinity, null, undefined, {}, true]) assert.deepEqual(J(S.ovVal(m, bad)), { label: "甲", unit: "億", text: "—", sign: 0 });
  assert.deepEqual(J(S.ovVals([m, MT("w", "丙", "", 0)], { m: { v: 1, w: "<img>" } })).map(x => x.text), ["+1.00", "—"]);
  assert.deepEqual(J(S.ovVals([m], { m: { __proto__: null } })).map(x => x.text), ["—"]);
  for (const it of [null, {}, { m: null }, { m: [1] }, { m: "x" }]) assert.deepEqual(J(S.ovVals([m], it)), []);   // 舊檔：沒有 m → 不顯示數值
});
ok("§8 ovPx：收盤與漲跌；close 不是有限數 → null；價格資料日與基準日不同才註明日期", () => {
  assert.deepEqual(J(S.ovPx({ close: 2180.0, chg_pct: 1.63, date: "2026-11-27" }, "2026-11-27")), { close: "2,180", chg: "+1.63%", sign: 1, note: "" });
  assert.deepEqual(J(S.ovPx({ close: 60.55, chg_pct: -9.7, date: "2026-11-26" }, "2026-11-27")), { close: "60.55", chg: "-9.70%", sign: -1, note: "11/26" });
  assert.deepEqual(J(S.ovPx({ close: 33.3, chg_pct: null, date: "2026-11-27" }, "2026-11-27")), { close: "33.3", chg: "", sign: 0, note: "" });
  assert.deepEqual(J(S.ovPx({ close: 10, chg_pct: -0.004, date: "<img>" }, "2026-11-27")), { close: "10", chg: "0.00%", sign: 0, note: "" });
  assert.equal(S.ovPx({ close: 10, chg_pct: 1, date: "2026-11-26" }, null).note, "");                // 無從比對就不註明
  for (const bad of [null, undefined, "x", {}, { close: "10" }, { close: NaN, chg_pct: 1 }]) assert.equal(S.ovPx(bad, "2026-11-27"), null);
});
ok("§8 ovIx：每列只列命中且計入的來源（順序＝hits）、數值／名次／via 與資料檔一致、同組來源標 shared、列順序＝資料檔順序", () => {
  const ix = J(S.ovIx(S8().sectors));
  assert.deepEqual(ix.map(r => [r.key, r.count, r.entries.map(e => e.id)]), [["食品", 3, ["A", "B", "C", "E"]], ["水泥", 2, ["A", "E"]]]);
  const [f, w] = ix, by = Object.fromEntries(f.entries.map(e => [e.id, e]));
  assert.deepEqual(f.entries.map(e => e.shared), [true, true, false, false]);                        // A、B 同組（法人資金流）→ 畫面歸在一起標「同組算 1 票」
  assert.deepEqual(w.entries.map(e => e.shared), [false, false]);                                    // 只中 A：不標
  assert.deepEqual([by.A.short, by.A.rank, by.A.groupName, by.A.vals], ["產業鏈資金流", 1, "法人資金流", [{ label: "近5日淨額", unit: "億", text: "+12.71", sign: 1 }]]);
  assert.deepEqual(by.B.vals.map(v => [v.label, v.text, v.unit, v.sign]), [["近5日日均", "+2.54", "億/日", 1], ["近20日日均", "0.00", "億/日", 0]]);
  assert.equal(by.B.rank, null);
  assert.deepEqual(by.C.via, [{ name: "乳品", label: "主動淨額合計", unit: "億", text: "+2.25", sign: 1 }, { name: "飲料", text: "", unit: "", sign: 0 }]);   // viam 不是有限數 → 只列名稱
  assert.deepEqual([by.C.rank, by.C.vals[0].text], [2, "+3.50"]);
  assert.deepEqual(by.E.via.map(v => [v.name, v.text]), [["改善", ""]]); assert.deepEqual(by.E.vals.map(v => v.text), ["99.50", "—"]);
  assert.deepEqual(w.entries[0].vals[0].text, "+1.34"); assert.equal(w.entries[0].rank, 8);
  assert.ok(ix.every(r => r.entries.every(e => e.id !== "D")), "過期來源不進交集列");
  const st = J(S.ovIx(S8().stocks))[0];
  assert.deepEqual(st.px, { close: "1,234.5", chg: "0.00%", sign: 0, note: "11/26" });
  assert.deepEqual(st.entries.map(e => [e.id, e.rank, e.tag, e.vals.map(v => v.text + v.unit)]), [["a", 1, "", ["+6.47億", "+4.47億", "4.47億"]], ["d", null, "高預期仍Beat", ["+44.7%", "-3.3%"]]]);
  // hits 指到不存在或未計入的來源：略過、不報錯；rank 非正整數 → null
  const g = S8(); g.sectors.rows[1].hits = ["A", "D", "Z"]; g.sectors.sources[0].items[1].rank = "8";
  const w2 = J(S.ovIx(g.sectors))[1]; assert.deepEqual(w2.entries.map(e => e.id), ["A"]); assert.equal(w2.entries[0].rank, null);
});
ok("§8 舊資料檔（沒有 metrics／m／rank／px）：照常列出命中來源與 via，不顯示數值、不報錯", () => {
  const g = S8();
  for (const lay of [g.sectors, g.stocks]){
    for (const s of lay.sources){ delete s.metrics; for (const it of s.items){ delete it.m; delete it.rank; delete it.px; delete it.tag; delete it.viam; } }
    for (const r of lay.rows) delete r.px;
  }
  const ix = J(S.ovIx(g.sectors));
  assert.deepEqual(ix.map(r => [r.key, r.px, r.entries.map(e => [e.id, e.short, e.rank, e.tag, e.vals])]),
    [["食品", null, [["A", "產業鏈資金流", null, "", []], ["B", "籌碼雷達", null, "", []], ["C", "主動 ETF 次產業加碼前 10", null, "", []], ["E", "日級輪動雷達", null, "", []]]],
     ["水泥", null, [["A", "產業鏈資金流", null, "", []], ["E", "日級輪動雷達", null, "", []]]]]);
  assert.deepEqual(ix[0].entries[2].via, [{ name: "乳品", text: "", unit: "", sign: 0 }, { name: "飲料", text: "", unit: "", sign: 0 }]);
  assert.equal(J(S.ovIx(g.stocks))[0].px, null);
  assert.deepEqual(J(S.ovTop(S.ovSources(g.stocks)[0], "2026-11-27", 3)).map(t => [t.key, t.px, t.entry.vals]), [["2301", null, []], ["2302", null, []], ["2303", null, []]]);
  // repo 內 §8 之前的每日快照（真正的舊檔）
  const old = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "overview", "daily", "2026-11-12.json"), "utf8"));
  assert.ok(!old.sectors.sources.some(s => "metrics" in s), "這份快照應是 §8 之前的舊檔");
  for (const lay of [old.sectors, old.stocks, old.out.sectors, old.out.stocks]){
    const rows = S.ovIx(lay); assert.equal(rows.length, lay.rows.length);
    rows.forEach((r, i) => { assert.deepEqual(J(r.entries.map(e => e.id)), lay.rows[i].hits); assert.ok(r.entries.every(e => e.vals.length === 0 && e.rank === null)); assert.equal(r.px, null); });
    for (const s of S.ovSources(lay)) S.ovTop(s, lay.base_date, S.OV_TOP_N);
  }
});
ok("§8 ovTop：各來源前 10 名＝資料檔 items 前 10 項、順序不變；未計入的來源照樣可列", () => {
  const g = S8(), a = S.ovSources(g.stocks)[0];
  assert.equal(S.OV_TOP_N, 10);
  const top = J(S.ovTop(a, g.stocks.base_date, S.OV_TOP_N));
  assert.deepEqual(top.map(t => t.key), Array.from({ length: 10 }, (_, i) => String(2301 + i)));
  assert.deepEqual([top[0].name, top[0].px, top[0].entry.rank, top[0].entry.vals.map(v => v.text)], ["股0", { close: "184.5", chg: "+9.82%", sign: 1, note: "" }, 1, ["+6.47", "+4.47", "4.47"]]);
  assert.equal(top[9].entry.rank, 10);
  const d = S.ovSources(g.sectors).find(s => s.id === "D"); assert.equal(d.counted, false);
  assert.deepEqual(J(S.ovTop(d, "2026-11-27", 10)).map(t => [t.key, t.entry.counted, t.entry.via.map(v => v.name)]), [["半導體", false, ["基板"]]]);
});
ok("§8 ovSkipLines：收合狀態下仍露出的短句——過期／另列寫資料日、讀取失敗寫讀取失敗；有效與不納入的來源不出現", () => {
  const g = S8();
  assert.deepEqual(J(S.ovSkipLines(g.sectors)), ["D 連湧／新湧次產業：資料日 11/26，未計入"]);
  assert.deepEqual(J(S.ovSkipLines(g.stocks)), ["e 千張大戶週增前 20：讀取失敗，未計入"]);
  g.sectors.sources[2].status = "listed"; g.sectors.sources[3].date = "<img src=x>";
  assert.deepEqual(J(S.ovSkipLines(g.sectors)), ["C 主動 ETF 次產業加碼前 10：資料日 11/27，未計入", "D 連湧／新湧次產業：資料日 —，未計入"]);
  assert.deepEqual(J(S.ovSkipLines(null)), []);
});
ok("§8 repo 內實際資料檔：每一列顯示的來源＝該列 hits、數值與名次＝資料檔該來源項目的 m／rank、個股列帶收盤", () => {
  const real = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "overview", "latest.json"), "utf8"));
  let nv = 0, npx = 0, nrow = 0;
  for (const blk of [real, real.out]) for (const [name, lay] of [["sectors", blk.sectors], ["stocks", blk.stocks]]){
    const srcBy = Object.fromEntries(lay.sources.map(s => [s.id, s]));
    S.ovIx(lay).forEach((r, i) => {
      const raw = lay.rows[i]; nrow++;
      assert.equal(r.key, raw.key); assert.equal(r.count, raw.count);
      assert.deepEqual(J(r.entries.map(e => e.id)), raw.hits);
      for (const e of r.entries){
        const s = srcBy[e.id], it = s.items.find(x => x.key === r.key);
        assert.ok(it, e.id + " " + r.key); assert.equal(e.rank, it.rank === undefined ? null : it.rank);
        assert.equal(e.vals.length, s.metrics.length);
        s.metrics.forEach((mt, k) => {
          const v = it.m[mt.k];
          if (v === null){ assert.equal(e.vals[k].text, "—"); return; }
          assert.equal(Number(e.vals[k].text.replace(/[+,]/g, "")), Number(v.toFixed(mt.digits)) || 0, `${e.id} ${r.key} ${mt.k}`); nv++;
          assert.equal(e.vals[k].unit, mt.unit); assert.equal(e.vals[k].label, mt.label);
        });
        assert.deepEqual(J(e.via.map(v => v.name)), it.via || []);
      }
      if (name === "stocks" && raw.px){ assert.equal(Number(r.px.close.replace(/,/g, "")), raw.px.close); npx++; }
      if (name === "sectors") assert.equal(r.px, null);
    });
    for (const s of S.ovSources(lay)){
      const top = S.ovTop(s, lay.base_date, S.OV_TOP_N);
      assert.deepEqual(J(top.map(t => t.key)), s.items.slice(0, 10).map(x => x.key));
    }
  }
  assert.ok(nrow >= 4 && nv >= 10 && npx >= 1, `列 ${nrow}／數值 ${nv}／收盤 ${npx}`);
});
// ---- 渲染函式實跑（不需瀏覽器）：抽出交集表渲染段，配上 index.html 自己的 esc／sgn／stkBtn 執行 ----
const rs0 = sec.indexOf("// ---- 交集表渲染"), rs1 = sec.indexOf("// ---- 我的持股對照（規格 §7，使用者");
assert.ok(rs0 > 0 && rs1 > rs0, "找不到交集表渲染段");
const renderSrc = sec.slice(rs0, rs1);
const grab = re => { const m = html.match(re); assert.ok(m, String(re)); return m[0]; };
const helpers = [grab(/^const esc = [\s\S]*?\n[^\n]*\);\n/m), grab(/^const sgn = .*$/m), grab(/^const HASH_CODE_RE = .*$/m), grab(/^const stkBtn = c => \{[\s\S]*?\n\};/m)].join("\n");
const rsb = { console };
vm.createContext(rsb);
new vm.Script(helpers + "\n" + pure + "\n" + renderSrc + "\nglobalThis.R = { ovTableHtml, ovSrcHtml, ovTopsHtml, ovDet, OV_OPEN, ovSources, esc };").runInContext(rsb);
const R = rsb.R;
const EVIL = '<img src=x onerror="window.__pwn=1">';
ok("§8 渲染：交集表無 <table>／無橫捲容器、未命中的來源不出現（沒有「·」）、同組歸在一起標「同組算 1 票」、數值本體包在不換行的 .ov-vn", () => {
  const h = R.ovTableHtml(S8().sectors, false);
  assert.ok(!/<table|tblbox|<th|·<|>·/.test(h));
  assert.equal(h.split('class="ov-ix"').length - 1, 2);
  assert.ok(h.indexOf("食品") < h.indexOf("水泥"), "列順序＝資料檔順序");
  assert.ok(h.includes('<div class="ov-grpn">法人資金流（A、B 同組算 1 票）</div>'));
  assert.equal(h.split("同組算 1 票").length - 1, 1, "只中 A 的那一列不標");
  assert.ok(h.includes('<b class="ov-vn"><span class="up">+12.71</span> 億</b>') && h.includes('<b class="ov-vn">第 1 名</b>'));
  assert.ok(h.includes('<span class="ov-cnt">清單數 3</span>') && !/ov-cnt[^>]*(up|down)/.test(h), "清單數中性色");
  assert.ok(h.includes('乳品 <b class="ov-vn"><span class="up">+2.25</span> 億</b>') && h.includes('<span class="ov-v ov-tag">領先</span>'));
  assert.ok(!h.includes("連湧"), "過期來源不出現在交集列");
  const t = R.ovTableHtml(S8().stocks, true);
  assert.ok(t.includes('<span class="code">2301</span><button type="button" class="stkbtn" data-stk="2301"'), "個股列保留側欄鈕");
  assert.ok(t.includes('收 <b class="ov-vn">1,234.5</b>') && t.includes("（11/26 價）") && t.includes('<span class="ov-v ov-tag">高預期仍Beat</span>'));
  assert.ok(t.includes('<span class="up">+44.7</span>%</b>') && t.includes('<span class="down">-3.3</span>%</b>'), "% 緊貼數字、正負經 sgn 著色");
  assert.ok(R.ovTableHtml({ sources: [], rows: [], note: "有效計票群組只有 1 個" }, false).includes("有效計票群組只有 1 個"));
});
ok("§8 渲染：各來源前幾名——逐來源一個預設收合的 <details>、未計入的照列並標明、超過 10 項只列前 10", () => {
  const h = R.ovTopsHtml(S8().stocks, true, "in:stk"), s = R.ovTopsHtml(S8().sectors, false, "in:sec");
  assert.equal(h.split("<details").length - 1, 2); assert.equal(s.split("<details").length - 1, 5);   // 沒有項目的來源（e 失敗、f 不納入）不列
  assert.ok(!/<details[^>]* open/.test(h + s), "預設收合");
  assert.ok(h.includes("12 項，列前 10 項") && h.split('class="ov-ix"').length - 1 === 11 && !h.includes('<span class="code">2311</span>'));
  assert.ok(s.includes("｜未計入（過期不計）") && s.includes('data-ovdet="in:sec:D"') && s.includes("順序＝資料檔順序"));
  R.OV_OPEN["in:sec:D"] = true;
  assert.ok(/<details class="ov-det ov-top" data-ovdet="in:sec:D" open>/.test(R.ovTopsHtml(S8().sectors, false, "in:sec")), "開合狀態只看記憶體 OV_OPEN");
  delete R.OV_OPEN["in:sec:D"];
});
ok("§8 注入：名稱、來源名、metrics.label／unit、tag、via、viam 鍵、note、日期塞入 <img onerror> → 輸出不含任何未逃逸的標籤", () => {
  const g = S8();
  for (const lay of [g.sectors, g.stocks]){
    lay.note = EVIL; lay.base_date = EVIL;
    for (const s of lay.sources){
      s.name = EVIL + "：x"; s.group_name = s.group_name ? EVIL : undefined; s.date = EVIL; s.note = EVIL; s.unmapped = [EVIL];
      for (const m of s.metrics || []){ m.label = EVIL; m.unit = EVIL; }
      for (const it of s.items){ it.name = EVIL; it.tag = EVIL; if (it.via){ it.viam = { [EVIL]: 1 }; it.via = [EVIL]; } if (it.px) it.px.date = EVIL; }
    }
    for (const r of lay.rows) r.name = EVIL;
  }
  g.sectors.sources[0].id = EVIL; g.sectors.rows[0].hits[0] = EVIL; g.sectors.rows.push({ key: EVIL, count: 2, hits: ["E"] }); g.sectors.sources[4].items.push({ key: EVIL, via: [EVIL], m: { rs: EVIL, mom: 1 } });
  const out = [R.ovTableHtml(g.sectors, false), R.ovTableHtml(g.stocks, true), R.ovTopsHtml(g.sectors, false, EVIL), R.ovTopsHtml(g.stocks, true, "x"),
    R.ovSrcHtml(R.ovSources(g.sectors), g.sectors.base_date), R.ovSrcHtml(R.ovSources(g.stocks), g.stocks.base_date),
    R.ovTableHtml({ sources: [], rows: [], note: EVIL }, false), S.ovSkipLines(g.sectors).map(R.esc).join("")].join("\n");
  assert.ok(out.includes("&lt;img src=x onerror="), "惡意字串有被帶到畫面（已逃逸）");
  assert.ok(!/<img|onerror="window/.test(out), "不得出現未逃逸的 <img> 或可執行的 onerror 屬性");
  const tags = new Set([...out.matchAll(/<\/?([a-zA-Z0-9]+)/g)].map(m => m[1]));
  assert.deepEqual([...tags].sort(), ["b", "button", "details", "div", "span", "summary"]);
});
ok("§8 讀碼：說明預設收合（常駐只留標示句、切換、基準日、未計入短句）；<details> 開合只寫記憶體、不重繪不發請求；說明列補一句數值意義", () => {
  const r = sec.slice(sec.indexOf("function ovRender("), sec.indexOf("// 「前往持股診斷」"));
  const iLab = r.indexOf('class="ov-label"'), iSides = r.indexOf('class="ov-sides"'), iDet = r.indexOf('ovDet("expl", "來源與口徑說明"'), iTbl = r.indexOf("ovTableHtml(sd.sectors, false)");
  assert.ok(iLab > 0 && iLab < iSides && iSides < iDet && iDet < iTbl);
  assert.equal(r.split('ovDet("expl", "來源與口徑說明"').length - 1, 3, "載入中／流出側尚無資料／正常三個分支都有收合的說明");
  // 長說明（expl）與來源狀態清單（ovSrcHtml）只出現在 ovDet(...) 的內容裡，不直接接到 h
  assert.ok(!/h \+= [^;]*\bexpl\b(?![^;]*ovDet)/.test(r.replace(/ovDet\("expl", "來源與口徑說明", expl[^;]*;/g, "")));
  assert.equal(r.split("ovSrcHtml(").length - 1, 2); assert.ok(r.slice(iDet).indexOf("ovSrcHtml(") < r.slice(iDet).indexOf("ovTableHtml("));
  assert.ok(r.includes("ovSkipLines(sd.sectors).concat(ovSkipLines(sd.stocks))") && r.includes("skip.map(t => `<div>${esc(t)}</div>`)"));
  assert.ok(r.includes("基準日 ${esc(ovDate(j.date) || \"—\")}"));
  assert.ok(r.includes("這些數值僅供對照，<b>不影響排序</b>") && r.includes("各來源前幾名") && r.includes("不另排序不計分"));
  assert.ok(r.indexOf("ovTableHtml(sd.stocks, true)") < r.indexOf("ovTopsHtml(sd.sectors, false") && r.indexOf("ovTopsHtml(sd.stocks, true") < r.indexOf("ovHoldHtml(j)"));
  assert.ok(renderSrc.includes('${OV_OPEN[id] ? " open" : ""}'), "<details> 預設不帶 open");
  const tg = sec.slice(sec.indexOf('document.addEventListener("toggle"'), sec.indexOf("// 兩側切換（document 級委派"));
  assert.ok(tg.includes("OV_OPEN[id] = !!d.open;") && tg.trimEnd().endsWith("}, true);") && !/render\(|ovLoad|loadJSON|fetch\(/.test(tg));
  assert.ok(!/ovLoad|loadJSON|fetch\(|XMLHttpRequest/.test(renderSrc), "交集表渲染段零請求");
  assert.ok(!/ovLoad\(/.test(pure));
  // 我的持股對照段仍不放側欄鈕（側欄鈕只在交集表與各來源前幾名）
  assert.ok(!/stkBtn|ovNameHtml|ovTop/.test(sec.slice(sec.indexOf("function ovHoldCodes("), sec.indexOf("function ovRender("))));
  // hash：沒有新增 key
  for (const fn of ["parseHash", "currentHash", "applyHash", "syncHash"]){
    const i = html.indexOf("function " + fn + "("), b = html.slice(i, html.indexOf("\n}\n", i));
    assert.ok(i > 0 && !/OV_OPEN|ovdet/.test(b), fn);
  }
});
console.log(`\n${n} passed`);
