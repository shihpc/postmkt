// tests/overview_node.mjs —— 供 tests/test_overview_build.py 的 parity 測試呼叫：
// 從 index.html 抽出前端口徑的純函式（radarQuad／radarPoints／radarHolders、RRGD-PURE 區段、aetfInsight 的 nBuyers），
// 讀 stdin JSON {sr?, diag?, series?, diff?}，輸出各口徑的結果——即畫面實際算出的值，供後端移植逐位比對。
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const cut = (a, b) => { const i = html.indexOf(a), j = html.indexOf(b, i); if (i < 0 || j < 0) throw new Error("index.html 找不到 " + a + " … " + b); return html.slice(i, j); };
const radar = cut("const RADAR_MIN_N=8;", "// 散佈圖：inline SVG");
const rrgd = cut("const RRGD_N = 12", "// RRGD-PURE-END");
const nb = html.match(/^\s*const nBuyers = s => .*;$/m);
if (!nb) throw new Error("index.html 找不到 aetfInsight 的 nBuyers");
const inp = JSON.parse(fs.readFileSync(0, "utf8"));
const sb = { console, INPUT: inp, OUT: null };
vm.createContext(sb);
new vm.Script(radar + "\n" + rrgd + "\n" + nb[0] + `
const out = {};
if (INPUT.sr) out.points = radarPoints(INPUT.sr.windows.r5, INPUT.sr.windows.r20, "chain", "total");
if (INPUT.diag){ const h = radarHolders(INPUT.diag, "all"); out.holders = { up: h.up.map(r => ({ code: r.code, name: r.name, hdw: r.hdw })), cover: h.cover, hdd: h.hdd }; }
if (INPUT.series){
  const p = rrgdPrep(INPUT.series), t = p.valid[p.valid.length - 1];
  out.rrgd = { t, date: INPUT.series.dates[t], imp: rrgdPersistList(p.coords, t, "改善", RRGD_PERSIST, RRGD_SORT_MOM),
    lead: rrgdPersistList(p.coords, t, "領先", RRGD_PERSIST, RRGD_SORT_RATIO),
    coords: Object.fromEntries(p.names.map(n => [n, p.coords[n][t]])), valid: p.valid.length };
}
if (INPUT.diff) out.cobuy = (INPUT.diff.stocks || []).filter(s => nBuyers(s) >= 2).map(s => s.c);
OUT = JSON.stringify(out);
`).runInContext(sb);
process.stdout.write(sb.OUT);
