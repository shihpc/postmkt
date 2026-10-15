// tests/test_pick2.mjs —— 選股二 tab（pick2，2026-10-14）前端純函式＋靜態守門
// 從 index.html 抽出 `pick2-pure:begin`～`pick2-pure:end` 區段在 node vm 沙箱跑：CSV 解析、universe 名單、
// 使用者增刪設定（pm_pick2）讀檔容錯、名單合併 pk2Apply、新增／刪除、代號白名單、評等分布字串。
// 另以原始碼靜態檢查：CSP 未改、資料源為同源相對路徑且只在 pk2Ensure 內載入、pm_pick2 不進任何 fetch／URL／hash、
// 區段內 innerHTML 插值的外來字串都過 esc()、整段內嵌 script 可編譯。
// 用法：node tests/test_pick2.mjs（pytest 由 tests/test_pick2.py 代跑）
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const B = "// ---- pick2-pure:begin", E = "// ---- pick2-pure:end ----";
assert.equal(html.split(B).length, 2, "pick2-pure:begin 須唯一");
assert.equal(html.split(E).length, 2, "pick2-pure:end 須唯一");
const pure = html.slice(html.indexOf(B), html.indexOf(E));
// 整個 選股二 段落（含非純函式的渲染與事件）供靜態檢查
const SB = "// ================= 選股二 tab", SE = "// ---------- 持股診斷 tab（子期1）";
assert.equal(html.split(SB).length, 2, "選股二段落錨點須唯一");
const sect = html.slice(html.indexOf(SB), html.indexOf(SE));
assert.ok(sect.length > 1000 && sect.includes(B));

const sb = { console };
vm.createContext(sb);
new vm.Script(pure + `
Object.assign(this, { PK2_TW_RE, PK2_US_RE, PK2_DISCLAIMER, pk2NormCode, pk2Key, pk2Num, pk2Bool, pk2ParseCsv, pk2CsvDates,
  pk2Universe, pk2EmptyPrefs, pk2ParsePrefs, pk2Apply, pk2Add, pk2Remove, pk2Rating });`).runInContext(sb);
const S = sb;
const R = x => JSON.parse(JSON.stringify(x));   // vm 另一個 realm 的物件：deepEqual 前先轉回本 realm

let n = 0;
const ok = (name, f) => { f(); n++; console.log("ok  ", name); };

ok("代號白名單：台股 ^\\d{4}[0-9A-Z]{0,2}$、美股 ^[A-Z]{1,5}$，先 trim 轉大寫", () => {
  for (const [raw, v] of [["2330", "2330"], [" 2330 ", "2330"], ["00981a", "00981A"], ["6488", "6488"], ["2330AB", "2330AB"]])
    assert.equal(S.pk2NormCode("TW", raw), v, raw);
  for (const raw of ["233", "2330ABC", "A330", "23.0", "", "<img>", "２３３０"]) assert.equal(S.pk2NormCode("TW", raw), null, raw);
  for (const [raw, v] of [["nvda", "NVDA"], [" MU ", "MU"], ["A", "A"], ["GOOGL", "GOOGL"]]) assert.equal(S.pk2NormCode("US", raw), v, raw);
  for (const raw of ["GOOGLE", "BRK.B", "2330", "", "N1"]) assert.equal(S.pk2NormCode("US", raw), null, raw);
  for (const [m, raw] of [["JP", "7203"], ["TW", null], ["US", 123]]) assert.equal(S.pk2NormCode(m, raw), null);
});

ok("pk2Num／pk2Bool：空欄與非有限值一律 null", () => {
  assert.equal(S.pk2Num("3.23"), 3.23); assert.equal(S.pk2Num(" -2.82 "), -2.82); assert.equal(S.pk2Num("0"), 0);
  for (const v of ["", "  ", "nan", "NaN", "inf", "abc", null, undefined, NaN, Infinity]) assert.equal(S.pk2Num(v), null, String(v));
  assert.equal(S.pk2Bool("True"), true); assert.equal(S.pk2Bool("false"), false);
  for (const v of ["", "1", "yes", null]) assert.equal(S.pk2Bool(v), null);
});

ok("pk2ParseCsv：CRLF、空欄、尾端空行、欄數不足、壞代號整列丟棄、日期白名單", () => {
  const t = "﻿market,code,name,date,close,ext,r5,r20,above60,slope60,liq20,r3_pass,note,r1_rank\r\n"
    + "TW,1476,儒鴻,2026-10-13,311.5,3.23,11.85,7.41,False,-2.82,462045232.5,True,,\r\n"
    + "US,MU,美光,2026-10-13,,,,,True,,,,,\r\n"
    + "TW,<img>,x,2026-10-13,1,1,1,1,True,1,1,True,,\r\n"
    + "JP,7203,豐田,2026-10-13,1,1,1,1,True,1,1,True,,\r\n"
    + "TW,2330,台積電,2026/10/13,abc\r\n"
    + "\r\n\r\n";
  const c = S.pk2ParseCsv(t);
  assert.equal(c.rows.length, 3);
  const [a, b, d] = c.rows;
  assert.deepEqual(R([a.market, a.code, a.name, a.date, a.close, a.ext, a.r5, a.r20, a.above60, a.slope60, a.r1_rank]),
    ["TW", "1476", "儒鴻", "2026-10-13", 311.5, 3.23, 11.85, 7.41, false, -2.82, null]);
  assert.deepEqual(R([b.code, b.close, b.r5, b.above60]), ["MU", null, null, true]);
  assert.deepEqual(R([d.code, d.date, d.close, d.r5, d.above60]), ["2330", "", null, null, null]);
  assert.deepEqual(R(S.pk2CsvDates(c)), { TW: "2026-10-13", US: "2026-10-13" });
  // 表頭缺必要欄、非字串 → null
  assert.equal(S.pk2ParseCsv("a,b,c\n1,2,3"), null);
  assert.equal(S.pk2ParseCsv(null), null);
  assert.deepEqual(R(S.pk2ParseCsv("market,code,date,close,r5,r20,above60,ext,slope60").rows), []);
});

ok("pk2ParseCsv：真實 taiwan-backtest latest.csv（若存在）117 列全收", () => {
  const p = path.join(ROOT, "..", "taiwan-backtest", "output", "aisc", "daily", "latest.csv");
  if (!fs.existsSync(p)){ console.log("     （略過：找不到 ../taiwan-backtest/output/aisc/daily/latest.csv）"); return; }
  const c = S.pk2ParseCsv(fs.readFileSync(p, "utf8"));
  assert.ok(c && c.rows.length >= 100, String(c && c.rows.length));
  for (const r of c.rows) assert.ok(r.close === null || Number.isFinite(r.close));
});

ok("pk2Universe：代號白名單、去重、TW 在前；形狀不對回 null", () => {
  const d = S.pk2Universe({ version: "v", TW: [{ code: "2330", name: "台積電" }, { code: "2330", name: "dup" }, { code: "x" }, null,
    { code: "00981A", name: 5 }], US: [{ code: "MU", name: "美光" }, { code: "BRK.B" }] });
  assert.deepEqual(R(d), [{ m: "TW", code: "2330", name: "台積電" }, { m: "TW", code: "00981A", name: "" }, { m: "US", code: "MU", name: "美光" }]);
  for (const j of [null, [], "x", {}, { TW: "a" }]) assert.equal(S.pk2Universe(j), null, JSON.stringify(j));
  const p = path.join(ROOT, "..", "taiwan-backtest", "aisc", "universe.json");
  if (fs.existsSync(p)){
    const u = S.pk2Universe(JSON.parse(fs.readFileSync(p, "utf8")));
    assert.equal(u.length, 117, "現行 universe 117 檔（台股 93＋美股 24）");
  }
});

ok("pk2ParsePrefs：壞資料一律當空；逐筆過白名單去重", () => {
  const E0 = { v: 1, added: [], removed: [] };
  for (const s of ["", "null", "[]", "{", "1", '{"v":2,"added":[{"m":"TW","code":"2330"}]}', '"x"', "{\"v\":1}"])
    assert.deepEqual(R(S.pk2ParsePrefs(s)), E0, s);
  const p = S.pk2ParsePrefs(JSON.stringify({ v: 1, added: [{ m: "TW", code: "2330" }, { m: "TW", code: "2330" }, { m: "US", code: "<b>" },
    { m: "JP", code: "7203" }, "x", { m: "US", code: "nvda" }], removed: { m: "TW", code: "1476" } }));
  assert.deepEqual(R(p), { v: 1, added: [{ m: "TW", code: "2330" }, { m: "US", code: "NVDA" }], removed: [] });
});

const DEF = [{ m: "TW", code: "2330", name: "台積電" }, { m: "TW", code: "1476", name: "儒鴻" }, { m: "US", code: "MU", name: "美光" }];
ok("pk2Apply：預設扣 removed、加 added（不重複）、台股在前美股在後各依代號", () => {
  const L = S.pk2Apply(DEF, { v: 1, added: [{ m: "US", code: "AAPL" }, { m: "TW", code: "2330" }, { m: "TW", code: "0050" }],
    removed: [{ m: "TW", code: "1476" }] });
  assert.deepEqual(R(L.map(x => [x.m, x.code, x.added])), [["TW", "0050", true], ["TW", "2330", false], ["US", "AAPL", true], ["US", "MU", false]]);
  assert.equal(S.pk2Apply(DEF, null).length, 3);
  assert.equal(S.pk2Apply([], { v: 1, added: [{ m: "TW", code: "2330" }], removed: [] }).length, 1, "universe 讀不到時只剩自加");
  // 換池：被刪的預設股不在新池＝自然消失；自加的股永遠保留
  const p = { v: 1, added: [{ m: "TW", code: "6488" }], removed: [{ m: "TW", code: "1476" }] };
  assert.deepEqual(R(S.pk2Apply([{ m: "TW", code: "2330", name: "" }], p).map(x => x.code)), ["2330", "6488"]);
});

ok("pk2Add：白名單、重複提示、預設中被刪過的改為取消刪除", () => {
  const E0 = S.pk2EmptyPrefs();
  let r = S.pk2Add(DEF, E0, "TW", " 0050 ");
  assert.equal(r.ok, true); assert.deepEqual(R(r.prefs.added), [{ m: "TW", code: "0050" }]);
  assert.deepEqual(R(E0), { v: 1, added: [], removed: [] }, "不改動輸入");
  r = S.pk2Add(DEF, r.prefs, "TW", "0050"); assert.equal(r.ok, false); assert.match(r.err, /已在名單/);
  r = S.pk2Add(DEF, E0, "TW", "2330"); assert.equal(r.ok, false); assert.match(r.err, /已在名單/);
  r = S.pk2Add(DEF, E0, "TW", "abc"); assert.equal(r.ok, false); assert.match(r.err, /4 位數字/);
  r = S.pk2Add(DEF, E0, "US", "TOOLONG"); assert.equal(r.ok, false); assert.match(r.err, /英文字母/);
  r = S.pk2Add(DEF, E0, "XX", "2330"); assert.equal(r.ok, false);
  r = S.pk2Add(DEF, { v: 1, added: [], removed: [{ m: "TW", code: "1476" }] }, "TW", "1476");
  assert.equal(r.ok, true); assert.deepEqual(R(r.prefs), { v: 1, added: [], removed: [] });
  r = S.pk2Add(DEF, E0, "US", "nvda"); assert.deepEqual(R(r.prefs.added), [{ m: "US", code: "NVDA" }]);
});

ok("pk2Remove：自加的拿掉、預設的記入 removed、不重複記", () => {
  const p = { v: 1, added: [{ m: "TW", code: "0050" }], removed: [{ m: "TW", code: "1476" }] };
  const q = S.pk2Remove(DEF, p, ["TW:0050", "TW:2330", "TW:1476", "US:ZZZ"]);
  assert.deepEqual(R(q), { v: 1, added: [], removed: [{ m: "TW", code: "1476" }, { m: "TW", code: "2330" }] });
  assert.deepEqual(R(S.pk2Apply(DEF, q).map(x => x.code)), ["MU"]);
  assert.deepEqual(R(p.added), [{ m: "TW", code: "0050" }], "不改動輸入");
});

ok("pk2Rating：五鍵分布字串；全缺回 null", () => {
  assert.equal(S.pk2Rating({ buy: 12, overweight: 3, hold: 1, underweight: 0, sell: 0 }), "買12／加3／持1／減0／賣0");
  assert.equal(S.pk2Rating({ buy: 2 }), "買2／加0／持0／減0／賣0");
  for (const v of [null, {}, { buy: "3" }, { buy: NaN }, "x"]) assert.equal(S.pk2Rating(v), null);
});

ok("免責句逐字", () => {
  assert.equal(S.PK2_DISCLAIMER, "描述性資料，非買賣訊號；AI 供應鏈名單（R1）待回測、不據此下單。所有判讀屬 AI 研判，非投資保證。");
});

ok("CSP 未改：connect-src 仍是既有白名單、不含 taiwan-backtest", () => {
  const m = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)">/);
  assert.ok(m);
  assert.ok(m[1].includes("connect-src 'self' https://api.anthropic.com https://api.finmindtrade.com https://raw.githubusercontent.com https://api.github.com https://taiwan-flow-v2.shihpc.workers.dev"));
  assert.ok(!m[1].includes("backtest"));
  assert.equal(html.split("Content-Security-Policy").length - 1, (html.match(/Content-Security-Policy/g) || []).length);
});

ok("資料源：同源相對路徑、只在 pk2Ensure 內載入、load() 不碰", () => {
  assert.ok(html.includes('const PK2_UNI_URL = "../taiwan-backtest/aisc/universe.json";'));
  assert.ok(html.includes('const PK2_CSV_URL = "../taiwan-backtest/output/aisc/daily/latest.csv";'));
  assert.equal(html.split("loadJSON(PK2_UNI_URL)").length, 2);
  assert.equal(html.split("pk2LoadText(PK2_CSV_URL)").length, 2);
  const i = html.indexOf("function pk2Ensure(){");
  const ens = html.slice(i, html.indexOf("\n}\n", i));
  assert.ok(ens.includes("loadJSON(PK2_UNI_URL)") && ens.includes("pk2LoadText(PK2_CSV_URL)"));
  const ld = html.match(/function load\(\)\{[^\n]*\}/)[0];
  assert.ok(!/pk2|pick2/i.test(ld), ld);
  // 呼叫 pk2Ensure 的只有 renderPick2，renderPick2 只由 render() 的 pick2 分支呼叫
  assert.equal(html.split("pk2Ensure()").length - 1, 2);   // 宣告 1＋呼叫 1
  assert.ok(html.includes('else if (state.tab === "pick2") renderPick2();'));
  assert.equal(html.split("renderPick2()").length - 1, 2);
});

ok("pm_pick2 只進 localStorage：不出現在 fetch／URL／hash／loadJSON 參數", () => {
  assert.equal(html.split('"pm_pick2"').length - 1, 1, "只在 PK2_KEY 宣告處出現字面量");
  const uses = sect.split("PK2_KEY").length - 1;
  assert.ok(uses >= 3);
  for (const ln of sect.split("\n")) if (ln.includes("PK2_KEY") && !ln.includes("const PK2_KEY")){
    assert.ok(/localStorage\.(getItem|setItem|removeItem)\(PK2_KEY/.test(ln), ln.trim());
  }
  for (const bad of [/fetch\([^)]*pk2Prefs/, /location\.hash/, /history\.(replace|push)State/, /encodeURIComponent/])
    assert.ok(!bad.test(sect), String(bad));
  // fetch 只有 pk2LoadText 一處，且 URL 是參數（呼叫端只傳常數 PK2_CSV_URL）
  assert.equal(sect.split("fetch(").length - 1, 1);
});

ok("區段內 innerHTML 插值的外來字串（代號／名稱／日期／版本）都過 esc()", () => {
  // ${…} 插值裡碰到 name／code／date／version／hdd／rym／rt／msg／k 的，必須是 esc(…)
  const hits = [...sect.matchAll(/\$\{([^{}]*(?:\.name|\.code|\.k\b|date|version|refreshed|frozen|hdd|rym|\.rt\b|\.msg|cd\.TW|cd\.US)[^{}]*)\}/g)].map(m => m[1].trim());
  assert.ok(hits.length >= 10, String(hits.length));
  // 例外（逐一點名）：勾選狀態三元式只產生 " checked" 字面量；res.code 只進 PK2.msg（之後經 esc() 或 textContent 顯示，下一條斷言守）
  // stkBtn() 內部先過 HASH_CODE_RE 再 esc()（既有共用鈕）
  const ALLOW = new Set(['PK2.sel.has(r.k) ? " checked" : ""', "res.code", 'r.m === "TW" ? stkBtn(r.code) : ""']);
  const bad = hits.filter(x => !/^esc\(|\? esc\(/.test(x) && !ALLOW.has(x));
  assert.deepEqual(bad, []);
  // PK2.msg 只會以 esc(PK2.msg) 拼進 HTML，或經 textContent 寫入
  const msgUses = [...sect.matchAll(/[^\n]*\bPK2\.msg\b[^\n]*/g)].map(m => m[0]).filter(l => !/PK2\.msg = /.test(l));
  assert.ok(msgUses.length >= 1);
  for (const l of msgUses) assert.ok(/esc\(PK2\.msg\)/.test(l), l.trim());
  assert.ok(/el\.textContent = t;/.test(sect));
});

ok("純描述：區段內不出現判級／訊號字樣與紅綠色票", () => {
  // 註解行（說明「不新增燈號」等規範本身）不算畫面字樣
  const body = sect.replace(PK2_DISC_RE(), "").split("\n").filter(l => !/^\s*\/\//.test(l)).join("\n");
  for (const w of ["偏多", "偏空", "建議買", "建議賣", "買進訊號", "賣出訊號", "燈號", "#ef5b5b", "#2fbf71", "class=\"up\"", "class=\"down\""])
    assert.ok(!body.includes(w), w);
});
function PK2_DISC_RE(){ return /const PK2_DISCLAIMER = "[^"]*";/; }

ok("整段內嵌 script 可編譯", () => {
  const ss = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  assert.ok(ss.length >= 1);
  for (const s of ss) new vm.Script(s);
});

console.log(`\n${n} 項全過`);
