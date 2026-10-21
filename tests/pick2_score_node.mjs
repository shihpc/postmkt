// tests/pick2_score_node.mjs —— 供 tests/test_pick2_build.py 的 parity 測試呼叫：
// 從 index.html 抽 pick2-pure 區段＋pk2Rows()（以最小 stub 取代 state／PK2／scrYear 等頁面全域），
// 讀 stdin JSON {diag, screen, codes:[...]}（台股），輸出 {code:{score, n}}——即畫面「多空總分」欄實際算出的值。
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const ROOT = path.resolve(import.meta.dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const B = "// ---- pick2-pure:begin", E = "// ---- pick2-pure:end ----";
const pure = html.slice(html.indexOf(B), html.indexOf(E));
const i0 = html.indexOf("function pk2Rows(list){");
const rowsSrc = html.slice(i0, html.indexOf("\n}\n", i0) + 2);
const n0 = html.indexOf("const pk2N = ");
const pk2NSrc = html.slice(n0, html.indexOf("\n", n0));
if (i0 < 0 || n0 < 0) throw new Error("index.html 找不到 pk2Rows 或 pk2N");
const inp = JSON.parse(fs.readFileSync(0, "utf8"));
const sb = { console, INPUT: inp, OUT: null };
vm.createContext(sb);
new vm.Script(pure + "\n" + pk2NSrc + "\n" + `
const state = { diag: INPUT.diag, screen: INPUT.screen };
const PK2 = { csv: null, ich: null, uni: null };
const pk2Def = () => [];
const scrYear = () => null;
const scrEstMean = () => null;
const stkName = () => "";
` + rowsSrc + `
const out = {};
for (const r of pk2Rows(INPUT.codes.map(code => ({ m: "TW", code, added: false })))) out[r.code] = { score: r.score, n: pk2Score(r).n };
OUT = JSON.stringify(out);
`).runInContext(sb);
process.stdout.write(sb.OUT);
