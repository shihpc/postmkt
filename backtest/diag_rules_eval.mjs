// backtest/diag_rules_eval.mjs — 持股診斷燈號執行器（規格 docs/diag-backtest-spec.md §7.1）
//
// 燈號唯一實作就是畫面那份：從 index.html 抽出 `const DIAG_PCT` 起至 `function diagLights`
// 結尾（其後第一個第 0 欄 `}`）止，放進 node vm 沙箱直接執行，不在 Python 另寫一份。
//
// 協定（stdin/stdout，一行一個 JSON）：
//   啟動後先輸出 {"rules":[{id,col,dim,addon}...]}（DIAG_RULES 順序）。
//   之後每讀入一行 {"id":<任意>, "market":{...}, "stocks":{code:{...}}}，
//   輸出一行 {"id":<同>, "res":{code:[total, raw..., c3gated]}}：
//     total ∈ "red"|"yellow"|"green"；raw 依 DIAG_RULES 順序，為 test(s,m) 的原值
//     （true→1、false→0、其他→null）；c3gated＝C3 閘後是否計入（1/0）。
// 用法：node backtest/diag_rules_eval.mjs [index.html 路徑] [--selftest]
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const indexPath = args.find(a => !a.startsWith("--")) || path.join(HERE, "..", "index.html");

export function extractSource(html) {
  const a = html.indexOf("const DIAG_PCT");
  if (a < 0 || html.indexOf("const DIAG_PCT", a + 1) >= 0) throw new Error("const DIAG_PCT 需唯一命中");
  const f = html.indexOf("function diagLights(s, m){", a);
  if (f < 0) throw new Error("找不到 function diagLights(s, m){");
  const e = html.indexOf("\n}\n", f);
  if (e < 0) throw new Error("找不到 diagLights 結尾");
  return html.slice(a, e + 2);
}

export function load(html) {
  const src = extractSource(html);
  const sb = {};
  vm.createContext(sb);
  new vm.Script(src + "\nthis.__api = { DIAG_RULES, diagLights };").runInContext(sb);
  return sb.__api;
}

const tri = v => v === true ? 1 : v === false ? 0 : null;

export function evalVersion(api, market, stocks) {
  const { DIAG_RULES, diagLights } = api;
  const res = {};
  for (const [code, s] of Object.entries(stocks)) {
    const raw = DIAG_RULES.map(r => tri(r.test(s, market)));
    const L = diagLights(s, market);
    const c3 = L.hits.some(r => r.id === "C3") ? 1 : 0;
    res[code] = [L.total, ...raw, c3];
  }
  return res;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const api = load(fs.readFileSync(indexPath, "utf8"));
  const out = s => process.stdout.write(JSON.stringify(s) + "\n");
  out({ rules: api.DIAG_RULES.map(r => ({ id: r.id, col: r.col, dim: r.dim, addon: !!r.addon })) });
  if (args.includes("--selftest")) process.exit(0);
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", line => {
    if (!line.trim()) return;
    const j = JSON.parse(line);
    out({ id: j.id, res: evalVersion(api, j.market || {}, j.stocks || {}) });
  });
}
