// tests/test_revenue_frontend.mjs —— 月營收 tab 前端（2026-11-12 階段二，規格正本 docs/revenue-beatmiss.md §5）
// 從 index.html 抽出 `rev-pure:begin`～`rev-pure:end` 區段在 node vm 沙箱跑，以 tests/fixtures/revenue_sample.json
// （取自 data/revenue/2026-10.json 的子集：每類至少一檔＋A／B 層各檔，universe_n／reported_n／counts 依子集重算）
// 驗月份白名單／index 形狀／篩選／數值格式／generated_at 檢查，並以原始碼靜態檢查 lazy 載入、標示句、esc()、
// 來源欄不轉連結、CSS 前綴與首屏不碰本 tab。
// 用法：node tests/test_revenue_frontend.mjs（pytest 由 tests/test_revenue_frontend.py 代跑）
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const B = "// ---- rev-pure:begin", E = "// ---- rev-pure:end ----";
assert.equal(html.split(B).length, 2, "rev-pure:begin 須唯一");
assert.equal(html.split(E).length, 2, "rev-pure:end 須唯一");
const pure = html.slice(html.indexOf(B), html.indexOf(E));

const sb = { console };
vm.createContext(sb);
new vm.Script(pure + `
Object.assign(this, { REV_LABEL, revLabel, REV_MONTH_RE, REV_GEN_RE, REV_CLS, REV_CLS_SUMMARY, revNum, revGenOk, revIndex, revPickMonth,
  revMonthOk, revRows, revList, revSectorNames, revFilter, revFmt, revPct, revDir, revThText });`).runInContext(sb);
const S = sb;
const J = JSON.parse(fs.readFileSync(path.join(ROOT, "tests", "fixtures", "revenue_sample.json"), "utf8"));

let n = 0;
const ok = (name, f) => { f(); n++; console.log("ok  ", name); };
const R = x => JSON.parse(JSON.stringify(x));   // vm 另一個 realm 的物件：deepEqual 前先轉回本 realm

ok("常數：標示句逐字、分類順序（高預期仍Beat／低預期仍Miss 置前）", () => {
  assert.equal(S.REV_LABEL, "AI 研判，未經回測，非保證");
  assert.equal(J.label, S.REV_LABEL, "資料檔 label 與常數同一句");
  assert.deepEqual(R(S.REV_CLS), ["高預期仍Beat", "低預期仍Miss", "Beat", "Miss", "符合"]);
  assert.deepEqual(R(S.REV_CLS_SUMMARY), ["高預期仍Beat", "低預期仍Miss", "Beat", "Miss"]);
  assert.deepEqual(Object.keys(J.counts), R(S.REV_CLS), "與 build_revenue.py 的分類鍵一致");
});

ok("REV_MONTH_RE／revPickMonth：格式合且在清單內才採用，否則 null", () => {
  const ms = ["2026-10", "2026-09", "2026-08"];
  assert.equal(S.revPickMonth("2026-09", ms), "2026-09");
  for (const v of ["2026-07", "2026-9", "2026-09-01", "2026/09", " 2026-09", "2026-09x", "<img>", "", null, undefined, 202609, {}, ["2026-09"]])
    assert.equal(S.revPickMonth(v, ms), null, String(v));
  assert.equal(S.revPickMonth("2026-09", null), null);
  assert.equal(S.revPickMonth("2026-09", []), null);
  assert.equal(S.revPickMonth("../x", ["../x"]), null, "清單內含壞值也不得放行");
});

ok("revIndex：months 新到舊、壞值剔除、去重；latest 須在 months 內；形狀不對回 null", () => {
  assert.deepEqual(R(S.revIndex({ schema: 1, months: ["2026-08", "2026-09", "2026-10"], latest: "2026-10" })),
    { months: ["2026-10", "2026-09", "2026-08"], latest: "2026-10" });
  assert.deepEqual(R(S.revIndex({ months: [], latest: null })), { months: [], latest: null });   // 規格 §2 已知限制
  assert.deepEqual(R(S.revIndex({ months: ["2026-09", "<x>", 202610, null, "2026-09", "2026-1"], latest: "2026-10" })),
    { months: ["2026-09"], latest: null });
  assert.deepEqual(R(S.revIndex({ months: ["2026-09"], latest: null })), { months: ["2026-09"], latest: null });
  for (const v of [null, undefined, "x", 1, [], {}, { months: "2026-10" }, { months: { a: 1 } }]) assert.equal(S.revIndex(v), null, JSON.stringify(v));
  // 線上實檔（若存在）也須可解析、且每個月份檔通過形狀檢查
  const ip = path.join(ROOT, "data", "revenue", "index.json");
  if (fs.existsSync(ip)){
    const x = S.revIndex(JSON.parse(fs.readFileSync(ip, "utf8")));
    assert.ok(x && x.months.length && x.latest === x.months[0], "實檔 index.json");
    for (const m of x.months) assert.ok(S.revMonthOk(JSON.parse(fs.readFileSync(path.join(ROOT, "data", "revenue", m + ".json"), "utf8")), m), m);
  }
});

ok("revMonthOk：rows 須為陣列、month 須與要求月份一致", () => {
  assert.equal(S.revMonthOk(J, "2026-10"), true);
  assert.equal(S.revMonthOk(J, "2026-09"), false);
  for (const v of [null, undefined, "x", [], {}, { month: "2026-10" }, { month: "2026-10", rows: {} }]) assert.equal(S.revMonthOk(v, "2026-10"), false, JSON.stringify(v));
});

const rows = S.revRows(J);
ok("revRows／revList：只收物件列（rows 另須有字串代號），順序＝資料檔順序", () => {
  assert.equal(rows.length, J.rows.length);
  assert.deepEqual(R(rows.map(r => r.code)), J.rows.map(r => r.code));
  const r = S.revRows({ rows: [null, 1, "x", [1], {}, { code: 2330 }, { code: "" }, { code: "2330" }] });
  assert.deepEqual(R(r), [{ code: "2330" }]);
  assert.deepEqual(R(S.revRows(null)), []); assert.deepEqual(R(S.revRows({ rows: "x" })), []);
  assert.deepEqual(R(S.revList([null, 1, [2], { a: 1 }])), [{ a: 1 }]);
  assert.deepEqual(R(S.revList("x")), []); assert.deepEqual(R(S.revList(undefined)), []);
});

ok("revFilter：分類／次產業可單獨或同時篩；all＝不篩；維持原順序", () => {
  assert.equal(S.revFilter(rows, "all", "all").length, rows.length);
  for (const c of S.REV_CLS){
    const got = S.revFilter(rows, c, "all"), want = J.rows.filter(r => r.cls === c);
    assert.equal(got.length, J.counts[c], c);
    assert.deepEqual(R(got.map(r => r.code)), want.map(r => r.code));
  }
  const secs = S.revSectorNames(rows);
  assert.deepEqual(R(secs), [...new Set(J.rows.map(r => r.sector))]);
  for (const s of secs) assert.deepEqual(R(S.revFilter(rows, "all", s).map(r => r.code)), J.rows.filter(r => r.sector === s).map(r => r.code));
  const r0 = J.rows[0];
  assert.ok(S.revFilter(rows, r0.cls, r0.sector).some(r => r.code === r0.code));
  assert.equal(S.revFilter(rows, "不存在", "all").length, 0);
  assert.equal(S.revFilter(rows, undefined, null).length, rows.length);
  assert.deepEqual(R(S.revSectorNames([{ sector: "甲" }, { sector: 1 }, { sector: "" }, {}, { sector: "甲" }, { sector: "乙" }])), ["甲", "乙"]);
});

ok("revNum／revFmt：只收有限 number；toFixed＋千分位；非數值「—」", () => {
  assert.equal(S.revNum(1.5), 1.5); assert.equal(S.revNum(0), 0);
  for (const v of [null, undefined, "23.12", NaN, Infinity, -Infinity, {}, [1], true]) assert.equal(S.revNum(v), null, String(v));
  assert.equal(S.revFmt(3674.73, 2), "3,674.73"); assert.equal(S.revFmt(4.1, 2), "4.10"); assert.equal(S.revFmt(149, 0), "149");
  assert.equal(S.revFmt(null, 1), "—"); assert.equal(S.revFmt("<b>", 1), "—"); assert.equal(S.revFmt("12", 1), "—");
});

ok("revPct／revDir：帶號百分比，正負號與方向依捨入後的值", () => {
  assert.equal(S.revPct(47.4, 1), "+47.4%"); assert.equal(S.revPct(-8.6, 1), "-8.6%"); assert.equal(S.revPct(0, 1), "0.0%");
  assert.equal(S.revPct(0.04, 1), "0.0%"); assert.equal(S.revPct(-0.04, 1), "0.0%"); assert.equal(S.revPct(1515.8, 1), "+1,515.8%");
  assert.equal(S.revPct(null, 1), "—"); assert.equal(S.revPct("5", 1), "—"); assert.equal(S.revPct(NaN, 1), "—");
  assert.equal(S.revDir(3, 1), 1); assert.equal(S.revDir(-3, 1), -1); assert.equal(S.revDir(0.04, 1), 0); assert.equal(S.revDir(-0.04, 1), 0);
  assert.equal(S.revDir(null, 1), null); assert.equal(S.revDir("1", 1), null);
});

ok("revGenOk：generated_at 須以 ISO 8601 YYYY-MM-DDTHH:MM 開頭", () => {
  for (const v of [J.generated_at, "2026-11-12T08:09:11+08:00", "2026-11-12T08:09", "2026-11-12T00:09:11Z"]) assert.equal(S.revGenOk(v), true, String(v));
  for (const v of [null, undefined, "", 1762906151, "2026-11-12", "2026-11-12 08:09:11", "<img src=x>2026-11-12T08:09", " 2026-11-12T08:09", "garbage", {}, ["2026-11-12T08:09"]])
    assert.equal(S.revGenOk(v), false, String(v));
});

ok("revThText：門檻取資料檔 thresholds；缺值顯示「—」、不拋錯", () => {
  const t = S.revThText(J.thresholds);
  for (const w of ["A／B 層 ±10%", "C 層 ±15%", "次產業 ±25%", "預期年增 ≥50%", "預期季增 ≥15%", "≤−10%", "相差達 10 個百分點", "A 公司法說財測", "C 模型推估"]) assert.ok(t.includes(w), w);
  const t2 = S.revThText({ ab: 12, c: "15", lo: -8 });
  assert.ok(t2.includes("A／B 層 ±12%") && t2.includes("C 層 ±—%") && t2.includes("≤−8%"));
  for (const v of [null, undefined, "x", 1, []]) assert.ok(S.revThText(v).includes("A／B 層 ±—%"));
  assert.ok(!/NaN|undefined|null/.test(S.revThText(null)));
});

// ---- 靜態檢查（讀碼）----
ok("index.html 內嵌 script 整段可編譯（語法錯誤會讓全站 19 個 tab 一起掛掉）", () => {
  const m = html.match(/<script>([\s\S]*)<\/script>/);
  assert.ok(m, "找不到內嵌 <script>");
  new vm.Script(m[1], { filename: "index.html<script>" });   // 只編譯、不執行
});
const secStart = html.indexOf("// ================= 月營收 tab");
const secEnd = html.indexOf("// ---------- 日期 tab");
assert.ok(secStart > 0 && secEnd > secStart, "找不到月營收 tab 區段");
assert.ok(secStart > html.indexOf("// ================= 市場情緒 tab"), "月營收區段須接在市場情緒之後");
const sec = html.slice(secStart, secEnd);

ok("tab 順序：revenue 排在 sentiment 之後、dates 之前；共 19 個", () => {
  const body = html.slice(html.indexOf("const TABS = ["), html.indexOf("];", html.indexOf("const TABS = [")));
  const tabs = [...body.matchAll(/\["([a-z0-9]+)","([^"]+)"\]/g)].map(m => [m[1], m[2]]);
  assert.equal(tabs.length, 19);
  assert.deepEqual(tabs.slice(-3), [["sentiment", "市場情緒"], ["revenue", "月營收"], ["dates", "日期"]]);
  const sub = html.match(/^\s*revenue:"([^"]*)",/m);
  assert.ok(sub && sub[1].includes("AI 研判，未經回測，非保證"), "SUBS.revenue 須帶標示句");
});

ok("lazy 載入：資料 URL 同源相對路徑、只在 revEnsure／revLoadMonth 內抓、load() 不碰、render() 只在本 tab 分派", () => {
  assert.ok(html.includes('const REV_BASE = "data/revenue/";'));
  assert.equal(html.split("loadJSON(REV_BASE").length, 3, "只有 index 與月份檔兩處");
  assert.equal(html.split("REV_BASE").length, 4, "REV_BASE 只有宣告＋兩處載入");
  const outside = html.replace(sec, "").split("\n").filter(l => !/^\s*\/\//.test(l)).join("\n");
  assert.ok(!outside.includes("data/revenue") && !outside.includes("REV_BASE"), "區段外（去註解）不得出現資料路徑");
  const ens = sec.slice(sec.indexOf("function revEnsure("), sec.indexOf("const revSgn"));
  assert.ok(ens.includes('loadJSON(REV_BASE + "index.json")'));
  const lm = sec.slice(sec.indexOf("function revLoadMonth("), sec.indexOf("function revEnsure("));
  assert.ok(lm.includes('loadJSON(REV_BASE + m + ".json")'));
  assert.ok(/\(m in REV\.cache\) \|\| \(m in REV\.err\) \|\| REV\.loading\[m\]/.test(lm), "月份檔：已載／已失敗／載入中都不重抓");
  assert.ok(/if \(REV\.idxErr \|\| REV\.idxLoading\) return;/.test(ens), "index：失敗不重試、in-flight 去重");
  const load = html.match(/^function load\(\)\{.*\}$/m)[0];
  assert.ok(!/rev/i.test(load), load);
  const allCode = html.split("\n").filter(l => !/^\s*\/\//.test(l)).join("\n");   // 去掉整行註解
  assert.equal(allCode.split("revRender()").length, 3, "revRender 只有定義與 render() 分派兩處");
  assert.ok(html.includes('else if (state.tab === "revenue") revRender();'));
  assert.equal(allCode.split("revEnsure()").length, 3, "revEnsure 只有定義與 revRender 內呼叫");
  assert.ok(sec.slice(sec.indexOf("function revRender(")).includes("revEnsure();"));
});

ok("標示句：三種畫面狀態都顯示（載入中／失敗／尚無資料用常數；有資料取 label、缺值退回常數）", () => {
  const rend = sec.slice(sec.indexOf("function revRender("));
  assert.ok(rend.includes('const label = `<div class="rev-label">${esc(REV_LABEL)}</div>`;'));
  assert.ok(rend.includes("const lbl = revLabel(j.label);"));
  assert.equal(S.revLabel(J.label), S.REV_LABEL);
  assert.equal(S.revLabel(S.REV_LABEL + "（試行）"), S.REV_LABEL + "（試行）");
  for (const v of [null, undefined, "", 1, {}, "已回測", "<img src=x>", "AI 研判"]) assert.equal(S.revLabel(v), S.REV_LABEL, String(v));   // 規定句不得被資料檔蓋掉
  assert.ok(rend.includes('<div class="rev-label">${esc(lbl)}</div>'));
  assert.equal((rend.match(/main\.innerHTML = /g) || []).length, 4);
  assert.equal((rend.match(/main\.innerHTML = `<div class="rev">\$\{label\}/g) || []).length, 3);
  assert.ok(rend.includes("尚無資料") && rend.includes("月營收資料尚未產生或讀取失敗") && rend.includes("月份資料讀取失敗"));
  assert.ok(rend.includes("revGenOk(j.generated_at) ? fmtGenTaipei(j.generated_at)"), "generated_at 須先過形狀檢查");
  assert.ok(rend.includes("產出 —"));
});

ok("安全：區段內 ${…} 插值不得直接放資料欄位（須過 esc／revTxt／revFmt／revPct／revSgn）；來源欄不轉連結", () => {
  const code = sec.slice(sec.indexOf(E)).split("\n").filter(l => !/^\s*\/\//.test(l)).join("\n");
  const hits = [...code.matchAll(/\$\{([^{}]*)\}/g)].map(m => m[1].trim());
  assert.ok(hits.length >= 30, "插值檢查命中過少，規則可能失效：" + hits.length);
  // 允許：包在安全函式裡、純程式內部變數（已組好的 HTML 片段／長度／常數判斷式）
  const safeCall = /^(esc|revTxt|revFmt|revPct|revSgn|pp|opt)\(/;
  const safeVar = /^(label|sel|rs\.length|list\.length|rows\.length|miss\.length|h)$/;
  const bad = hits.filter(x => !safeCall.test(x) && !safeVar.test(x)
    && !/^v === cur \? " selected" : ""$/.test(x) && !/^x === m \? " selected" : ""$/.test(x)
    && !/^x === REV\.idx\.latest \? "（最新）" : ""$/.test(x)
    && !/^rows\.filter\(r => r\.cls === REV_CLS\[4\]\)\.length$/.test(x)
    && !/^REV\.idxErr \? "[^"<>]*" : "[^"<>]*"$/.test(x));
  assert.deepEqual(bad, []);
  // 直接取欄位的寫法一律不得出現在模板字串裡
  assert.ok(!/\$\{\s*(r|x|j)\.[a-z_]+\s*\}/.test(code));
  assert.ok(!/<a\b|href=|target=/.test(sec), "本區段不得產生連結（來源欄網址為純文字）");
  assert.ok(sec.includes('{ h:"來源", f:r => revTxt(r.src) }'));
  assert.ok(sec.includes('const revTxt = v => typeof v === "string" && v ? esc(v) : "—";'));
});

ok("個股表欄位＝規格 §5.4(c) 的 15 欄且順序一致；預設排序＝資料檔順序（不帶 sortI）", () => {
  const st = sec.slice(sec.indexOf("function revStockHtml("), sec.indexOf("function revRender("));
  const cols = [...st.matchAll(/\{ h:"([^"]+)",/g)].map(m => m[1]);
  assert.deepEqual(cols, ["分類", "代號", "名稱", "次產業", "當月營收(億)", "月增%", "年增%", "預期季營收(億)", "預期季增%", "預期年增%",
    "達成率%", "正常進度%", "驚喜%", "基準層", "來源"]);
  assert.ok(!/sortI\s*:|sortD\s*:/.test(sec), "不帶 sortI／sortD＝資料檔順序");
  assert.ok(st.includes("], list);") && st.includes("revFilter(rows, REV.fCls, REV.fSec)"));
});

ok("顏色：sgn 著色只經 revSgn，且只用在月增%／年增%／驚喜%（含摘要的驚喜%、台積電年增基準）；CSS 一律 .rev-* 且無紅綠色票", () => {
  const code = sec.split("\n").filter(l => !/^\s*\/\//.test(l)).join("\n");
  assert.equal((code.match(/\bsgn\(/g) || []).length, 1, "sgn() 只在 revSgn 內呼叫");
  const uses = [...code.matchAll(/revSgn\(([a-z]+\.[a-z_]+), 1\)/g)].map(m => m[1]).sort();
  assert.deepEqual(uses, ["j.tsmc_yoy", "r.mom", "r.sur", "r.sur", "r.yoy", "r.yoy"]);
  assert.ok(!/class="(up|down)"/.test(sec));
  const c0 = html.indexOf("/* 月營收 tab"), c1 = html.indexOf("/* 選股二 tab");
  assert.ok(c0 > 0 && c1 > c0);
  const css = html.slice(c0, c1);
  const sels = [...css.replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/^\s*([^{}\n]+)\{/gm)].map(m => m[1].trim());
  assert.ok(sels.length >= 15);
  for (const s of sels) assert.ok(/^\.rev-/.test(s), s);
  for (const c of ["#ef5b5b", "#2fbf71", "--up", "--down", "red", "green"]) assert.ok(!css.replace(/\/\*[\s\S]*?\*\//g, "").includes(c), c);
  for (const m of sec.matchAll(/class="([^"$]+)"/g)) for (const k of m[1].split(/\s+/)) assert.ok(/^(rev(-[a-z]+)?|code|mut|msection|n)$/.test(k), k);
});

ok("hash：rm 只在 tab=revenue 讀寫；頂列 stats 於本 tab 清空", () => {
  assert.ok(html.includes("const HASH_RM_RE = /^\\d{4}-\\d{2}$/;"));
  assert.ok(html.includes('if (out.tab === "revenue"){ const rm = String(q.get("rm") || "").trim(); if (HASH_RM_RE.test(rm)) out.rm = rm; }'));
  assert.ok(html.includes('if (state.tab === "revenue") REV.hashRm = h.rm || "";'));
  assert.equal(html.split('"rm="').length, 3, "rm 寫出只有 currentHash 內兩處（已定月份／清單未到前保留原值）");
  assert.ok(/state\.tab === "pick2" \|\| state\.tab === "revenue"\)\{\n[^\n]*\n\s*el\.innerHTML = "";/.test(html));
});

console.log(`\n${n} passed`);
