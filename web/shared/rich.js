// Rich slide text (F-007a): KaTeX formulas and chemical formulas with subscripts in ordinary text.
// The chemistry rules mirror copilot.presentation.mathtext.chem_parts (tests: tests/e2e/test_formulas_browser.py).
import { html } from "../vendor/htm-preact-standalone.mjs";
import katex from "../vendor/katex/katex.mjs";

const ELEMENTS = new Set(`H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se
Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W
Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr`.split(/\s+/));
const ELEMENTAL = new Set(["H", "N", "O", "F", "Cl", "Br", "I", "S", "P"]);
const CHEM = /^(\d*)((?:[A-Z][a-z]?\d*)+)$/;

// "C6H12O6" -> {coef: "", parts: [["C","6"],["H","12"],["O","6"]]} or null (B12, N95, H1N1, A4 are not chemistry)
export function chemParts(token) {
  const m = CHEM.exec(token);
  if (!m) return null;
  const parts = [...m[2].matchAll(/([A-Z][a-z]?)(\d*)/g)].map((p) => [p[1], p[2]]);
  if (parts.some(([s]) => !ELEMENTS.has(s))) return null;
  const counts = parts.map(([, n]) => n).filter(Boolean);
  if (!counts.length || counts.some((n) => n === "1" || n.startsWith("0"))) return null;
  if (parts.length === 1 && (!ELEMENTAL.has(parts[0][0]) || +parts[0][1] < 2 || +parts[0][1] > 8)) return null;
  return { coef: m[1], parts };
}

const TOKEN = /(\d*(?:[A-Z][a-z]?\d*)+)(?![A-Za-z0-9])/g;

// Plain text with chemical formulas subscripted: "Plants take in CO2" -> ["Plants take in ", "CO", <sub>2</sub>]
export function rich(text) {
  if (!text || !/[A-Z][a-z]?\d/.test(text)) return text;
  const out = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const before = m.index > 0 ? text[m.index - 1] : "";
    if (/[A-Za-z0-9]/.test(before)) continue; // inside a longer word
    const chem = chemParts(m[1]);
    if (!chem) continue;
    out.push(text.slice(last, m.index), chem.coef);
    for (const [sym, n] of chem.parts) out.push(sym, n ? html`<sub>${n}</sub>` : "");
    last = m.index + m[1].length;
  }
  if (!out.length) return text;
  out.push(text.slice(last));
  return out.filter((x) => x !== "");
}

// KaTeX source -> HTML string, or null when KaTeX cannot render it (the caller shows the plain text instead).
const cache = new Map();
export function texHtml(latex) {
  if (!latex) return null;
  if (cache.has(latex)) return cache.get(latex);
  let out = null;
  try {
    out = katex.renderToString(latex, { throwOnError: true, displayMode: false, strict: "ignore", trust: false });
  } catch (e) {
    console.warn("formula not renderable, showing text:", latex, e && e.message);
  }
  if (cache.size > 200) cache.clear();
  cache.set(latex, out);
  return out;
}

export function Tex({ latex, text, cls = "" }) {
  const h = texHtml(latex);
  return h
    ? html`<span class=${"tex " + cls} dangerouslySetInnerHTML=${{ __html: h }}></span>`
    : html`<span class=${"tex-fallback " + cls}>${rich(text)}</span>`;
}
