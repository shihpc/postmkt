// tests/test_holidays_frontend.mjs —— 前端休市行事曆（2026-09-29 批次二，規格 taiwan-flow-live-v2/docs/holiday-calendar.md §5b）
// 從 index.html 按名稱抽出 holParse／holClosed／isTradingDay／prevTradingDay／dayDiff／pmStatus／myChgDateInfo／rrgdLagDays，
// 在 node vm 沙箱以 09-25（週五假日）／09-28（週一假日）／09-26 週六／09-29 平日重演，並驗 fail-open（HOL=null）時
// 與改動前的只排週末算法逐字相同。用法：node tests/test_holidays_frontend.mjs（pytest 由 tests/test_holidays_frontend.py 代跑）
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");

function pickLine(re, what) {
  const m = html.match(re);
  if (!m) throw new Error(`index.html 找不到 ${what}`);
  return m[0];
}
function pickBlock(startNeedle) {
  const start = html.indexOf(startNeedle);
  if (start < 0) throw new Error(`index.html 找不到 ${startNeedle}`);
  const open = html.indexOf("{", start);
  let depth = 0, inStr = null;
  for (let i = open; i < html.length; i++) {
    const c = html[i];
    if (inStr) { if (c === "\\") { i++; continue; } if (c === inStr) inStr = null; }
    else if (c === '"' || c === "'" || c === "`") inStr = c;
    else if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) return html.slice(start, i + 1) + (html[i + 1] === ";" ? ";" : ""); }
  }
  throw new Error(`${startNeedle} 大括號未配對`);
}
const fn = n => pickBlock(`function ${n}(`);

const src = [
  "let HOL = null;",
  pickLine(/^const MYCHG_STALE_LAG = \d+;$/m, "MYCHG_STALE_LAG"),
  pickLine(/^const holName = .*$/m, "holName"),
  pickLine(/^const dateNorm = .*$/m, "dateNorm"),
  fn("holParse"), fn("holClosed"), fn("isTradingDay"), fn("prevTradingDay"),
  pickBlock("const dayDiff = "),
  fn("rrgdLagDays"), fn("pmStatus"), fn("myChgDateInfo"),
].join("\n");
const sb = { Date, Set, Array, Number, String, Object, console, twNow: () => { throw new Error("必須注入 nowStr"); } };
vm.createContext(sb);
new vm.Script(src + `
this.setHol = j => { HOL = j == null ? null : holParse(j); return HOL; };
Object.assign(this, { holParse, holClosed, isTradingDay, prevTradingDay, dayDiff, rrgdLagDays, pmStatus, myChgDateInfo });`).runInContext(sb);

const CAL = JSON.parse(fs.readFileSync(path.join(ROOT, "tests", "fixtures", "twse_holidays_2026.json"), "utf8"));
let n = 0;
const ok = (name, f) => { f(); n++; console.log("ok  ", name); };

// 改動前的只排週末算法（逐字搬自改動前 index.html），作 fail-open 對照組
const oldDayDiff = (b, d) => { const DAY = 86400000, end = Date.parse(b + "T00:00:00Z"); let k = 0;
  for (let t = Date.parse(d + "T00:00:00Z") + DAY; t <= end; t += DAY) { const w = new Date(t).getUTCDay(); if (w !== 0 && w !== 6) k++; } return k; };
const oldPrevTd = today => { const dow = new Date(today + "T00:00:00Z").getUTCDay();
  const back = m => new Date(Date.parse(today + "T00:00:00Z") - m * 864e5).toISOString().slice(0, 10);
  return dow === 1 ? back(3) : dow === 0 ? back(2) : back(1); };
const days = []; for (let t = Date.parse("2026-08-01T00:00:00Z"); t <= Date.parse("2026-12-31T00:00:00Z"); t += 864e5) days.push(new Date(t).toISOString().slice(0, 10));

ok("解析：schema 必須是整數 1（true 不收、1.0 照收）、years 無合法年度＝null", () => {
  assert.equal(sb.holParse({ ...CAL, schema: true }), null);
  assert.equal(sb.holParse({ ...CAL, schema: "1" }), null);
  assert.equal(sb.holParse({ ...CAL, schema: 2 }), null);
  assert.notEqual(sb.holParse(JSON.parse(JSON.stringify(CAL).replace('"schema": 1', '"schema": 1.0'))), null);
  assert.equal(sb.holParse({ ...CAL, years: ["2026"] }), null);
  assert.equal(sb.holParse({ ...CAL, closed: "x" }), null);
  assert.equal(sb.holParse(null), null);
  assert.equal(sb.holParse([]), null);
});
ok("fail-open：HOL=null 時 dayDiff／prevTradingDay 與改動前只排週末算法逐字相同（8–12 月全組合）", () => {
  sb.setHol(null);
  for (const a of days) {
    assert.equal(sb.prevTradingDay(a), oldPrevTd(a), a);
    for (const b of days.slice(0, 40)) if (b <= a) assert.equal(sb.dayDiff(a, b), oldDayDiff(a, b), a + " " + b);
  }
});
ok("fail-open：years 未涵蓋該年＝只排週末（2027 假日不扣）", () => {
  sb.setHol({ ...CAL, years: [2026], closed: [...CAL.closed, "2027-01-01"] });
  assert.equal(sb.isTradingDay("2027-01-01"), true);
  assert.equal(sb.isTradingDay("2026-09-25"), false);
});
ok("pmStatus：休市日比照週末（資料日 09-24）", () => {
  sb.setHol(CAL);
  const m = { date: "2026-09-24" };
  assert.equal(sb.pmStatus(m, null, "2026-09-25 21:00:00").txt, "休市定格");
  assert.equal(sb.pmStatus(m, null, "2026-09-28 23:00:00").txt, "休市定格");
  assert.equal(sb.pmStatus(m, null, "2026-09-26 10:00:00").txt, "休市定格");
  assert.equal(sb.pmStatus(m, null, "2026-09-29 10:00:00").txt, "正常");     // 上一交易日＝09-24
  assert.equal(sb.pmStatus(m, null, "2026-09-29 23:00:00").txt, "延遲");     // 過 22:30 仍非今日，真延遲
  assert.equal(sb.pmStatus({ date: "2026-09-23" }, null, "2026-09-28 23:00:00").txt, "延遲");
  assert.match(sb.pmStatus(m, null, "2026-09-25 21:00:00").title, /中秋節休市/);
});
ok("pmStatus fail-open：與改動前相同（09-25 22:30 前正常、09-28／09-26 延遲）", () => {
  sb.setHol(null);
  const m = { date: "2026-09-24" };
  assert.equal(sb.pmStatus(m, null, "2026-09-25 21:00:00").txt, "正常");
  assert.equal(sb.pmStatus(m, null, "2026-09-28 23:00:00").txt, "延遲");
  assert.equal(sb.pmStatus(m, null, "2026-09-26 10:00:00").txt, "延遲");
  assert.equal(sb.pmStatus(m, null, "2026-09-26 10:00:00").title, "資料日 2026-09-24 早於上一交易日 2026-09-25");
});
ok("dayDiff／rrgdLagDays：跳過休市日", () => {
  sb.setHol(CAL);
  assert.equal(sb.dayDiff("2026-09-29", "2026-09-24"), 1);
  assert.equal(sb.dayDiff("2026-09-28", "2026-09-24"), 0);
  assert.equal(sb.rrgdLagDays("2026-09-29", "2026-09-23"), 2);
  sb.setHol(null);
  assert.equal(sb.dayDiff("2026-09-29", "2026-09-24"), 3);
});
ok("myChgDateInfo 第五軸：休市日不累計落後；休市日不說「即今日」", () => {
  sb.setHol(CAL);
  const md = { date: "2026-09-24" };
  let i = sb.myChgDateInfo(md, "2026-09-28 23:00:00");
  assert.equal(i.lag, 0); assert.equal(i.stale, false);
  assert.ok(!i.txt.includes("即今日"), i.txt);
  assert.match(i.txt, /今日 2026-09-28 .*休市/);
  i = sb.myChgDateInfo(md, "2026-09-29 23:00:00");
  assert.equal(i.lag, 1); assert.equal(i.stale, false);
  i = sb.myChgDateInfo({ date: "2026-09-23" }, "2026-09-29 23:00:00");
  assert.equal(i.lag, 2); assert.equal(i.stale, true);
  sb.setHol(null);
  i = sb.myChgDateInfo(md, "2026-09-28 23:00:00");
  assert.equal(i.lag, 2); assert.equal(i.stale, true);                        // 改動前行為
  assert.equal(i.txt, "資料日 2026-09-24（落後今日 2026-09-28 2 個交易日）");
});
console.log(`\n${n} passed`);
