// Explainer stage look (F-017 §2): the explainer_flat tokens and the fixed colour roles. No outlines; soft shadows.
export const VW = 1600, VH = 1000;  // the stage's viewBox (16:10)
export const B = 100;               // world drawing units per metre (the camera scales them to the screen)

export const T = {
  bg: '#EAF4F7', ink: '#33363d', muted: '#5d6672', card: 'rgba(255,255,255,0.9)', halo: 'rgba(255,255,255,0.85)',
  ground: '#A9CF8E', groundLine: '#7FAF66', skyTop: '#BFE3F2', skyBottom: '#EEF6F0', hill1: '#CFE5C2', hill2: '#BCDCA8',
  shadow: 'rgba(40,50,40,0.18)',
};

// colour roles: the same meaning in every scene (line style is never the only cue)
export const ROLE = {
  applied: '#F07C1A', friction: '#E04A3A', weight: '#2F6BE0', normal: '#1E9E6A', velocity: '#8A4FE0',
  path: '#8A4FE0', water: '#3B8FE0', ink: T.ink, muted: T.muted, pe: '#43A047', ke: '#E4572E',
};
export const roleColour = (r) => ROLE[r] || r || T.ink;

export const FONT = {
  words: 'Segoe UI,Arial,sans-serif',
  symbol: 'Cambria Math,Cambria,Times New Roman,serif',
};
export const LABEL_MIN = 24;  // px at stage size

export function shade(hex, k) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const f = (x) => Math.max(0, Math.min(255, Math.round(x * k)));
  return '#' + ((1 << 24) | (f(r) << 16) | (f(g) << 8) | f(b)).toString(16).slice(1);
}
export function hash(i) { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
