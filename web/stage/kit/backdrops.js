// Kit backdrops (F-017 §4), keyed by catalog id. Drawn in the pane's screen space from the ground line's screen y
// (gy) like the reference samples, so a sky stays a sky at any zoom; redrawn only when the camera moves.
// draw(w, h, gy, st, id) -> markup. Regions (metres) are in config/stage_catalog.json.
import { T, hash, shade } from '../style.js';
import { F } from '../svg.js';

const rect = (x, y, w, h, fill, ex = '') => `<rect x="${F(x)}" y="${F(y)}" width="${F(w)}" height="${F(Math.max(0, h))}" fill="${fill}" ${ex}/>`;
const circ = (x, y, r, fill, ex = '') => `<circle cx="${F(x)}" cy="${F(y)}" r="${F(r)}" fill="${fill}" ${ex}/>`;
const sky = (w, h, id, top, bottom) => `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/>` +
  `<stop offset="1" stop-color="${bottom}"/></linearGradient></defs>` + rect(0, 0, w, h, `url(#${id})`);
const hills = (w, gy, a = T.hill1, b = T.hill2) => {
  const k = w / 1600;
  return `<path d="M0,${F(gy - 120)} C${F(260 * k)},${F(gy - 230)} ${F(470 * k)},${F(gy - 90)} ${F(720 * k)},${F(gy - 160)} S${F(1180 * k)},${F(gy - 250)} ${F(w)},${F(gy - 130)} L${F(w)},${F(gy)} L0,${F(gy)}Z" fill="${a}"/>` +
    `<path d="M0,${F(gy - 50)} C${F(300 * k)},${F(gy - 120)} ${F(600 * k)},${F(gy - 30)} ${F(900 * k)},${F(gy - 80)} S${F(1400 * k)},${F(gy - 110)} ${F(w)},${F(gy - 60)} L${F(w)},${F(gy)} L0,${F(gy)}Z" fill="${b}"/>`;
};
const ground = (w, h, gy, color = T.ground, rough = false) => {
  let s = rect(0, gy, w, h - gy, color) + rect(0, gy, w, 10, shade(color, 0.9));
  if (rough) for (let i = 0; i < 70; i++) s += circ(hash(i) * w, gy + 18 + hash(i + 9) * Math.max(0, h - gy - 24), 3 + hash(i + 3) * 4, shade(color, 0.85));
  return s;
};
const stars = (w, hmax, n, seed = 0) => { let s = ''; for (let i = 0; i < n; i++) s += circ(hash(i + seed) * w, hash(i + 7 + seed) * hmax, 1.5 + hash(i + 2 + seed) * 2, '#ffffff', `opacity="${F(0.5 + 0.5 * hash(i + 4))}"`); return s; };

export const BACKDROPS = {
  outdoor: (w, h, gy, st, id) => {
    const grey = st.sky === 'overcast';
    let s = sky(w, h, id, grey ? '#AFC3D3' : T.skyTop, grey ? '#E3ECEF' : T.skyBottom) + hills(w, gy);
    if (grey) for (let i = 0; i < 7; i++) s += circ(i * w / 6.2 + 60, 40 + hash(i) * 30, 90 + hash(i + 4) * 40, '#DCE4EA');
    return s + ground(w, h, gy);
  },
  park: (w, h, gy, st, id) => sky(w, h, id, T.skyTop, T.skyBottom) + hills(w, gy) +
    [0.12, 0.3, 0.72, 0.9].map((u, i) => circ(u * w, gy - 40, 46 + 14 * hash(i), '#9CC98A') + circ(u * w + 40, gy - 30, 34, '#8EC07B')).join('') +
    ground(w, h, gy) + rect(0, gy, w, 36, '#D9C9A6'),
  street: (w, h, gy, st, id) => {
    const road = gy - 70;
    let s = sky(w, h, id, T.skyTop, T.skyBottom) + circ(w * 0.86, 150, 60, '#FFD66B') + hills(w, road);
    s += rect(0, road, w, 70, '#9BA3AC');
    for (let x = 40; x < w; x += 200) s += rect(x, road + 32, 90, 7, '#F2F2F2');
    return s + ground(w, h, gy, '#C9C1B4');
  },
  classroom: (w, h, gy) => rect(0, 0, w, h, '#F3E9D8') + rect(0, gy - 40, w, 40, '#E6D3B5') +
    rect(w * 0.78, 120, 240, 200, '#CFE6F5', 'rx="10" stroke="#C9B79A" stroke-width="10"') + `<line x1="${F(w * 0.78 + 120)}" y1="120" x2="${F(w * 0.78 + 120)}" y2="320" stroke="#C9B79A" stroke-width="6"/>` +
    ground(w, h, gy, '#C9A27E'),
  lab_bench: (w, h, gy) => {
    let s = rect(0, 0, w, h, '#E8F1F4');
    for (let x = 0; x < w; x += 140) s += `<line x1="${x}" y1="0" x2="${x}" y2="${F(gy)}" stroke="#D6E3E8" stroke-width="2"/>`;
    for (let y = 0; y < gy; y += 140) s += `<line x1="0" y1="${y}" x2="${F(w)}" y2="${y}" stroke="#D6E3E8" stroke-width="2"/>`;
    return s + rect(0, gy, w, h - gy, '#B98256') + rect(0, gy, w, 14, '#CF9A6C');
  },
  room: (w, h, gy) => rect(0, 0, w, h, '#F3E7D3') + rect(0, gy - 70, w, 70, '#E6D3B5') + ground(w, h, gy, '#C99C6E', true),
  night: (w, h, gy, st, id) => sky(w, h, id, '#18213D', '#3A4774') + stars(w, gy * 0.6, 30) +
    circ(200, 160, 50, '#F4F1DE') + circ(222, 148, 46, '#18213D') + ground(w, h, gy, '#3F5A3B'),
  space: (w, h, gy, st) => {
    const g = st.ground || 'none';
    if (g === 'mars') {
      let s = rect(0, 0, w, h, '#E8B48C') + rect(0, gy, w, h - gy, '#B5532F');
      for (let i = 0; i < 9; i++) s += `<ellipse cx="${F(hash(i + 20) * w)}" cy="${F(gy + 25 + hash(i + 30) * Math.max(0, h - gy - 40))}" rx="${F(18 + hash(i) * 30)}" ry="${F(6 + hash(i) * 8)}" fill="#9A4426"/>`;
      return s;
    }
    let s = rect(0, 0, w, h, '#1C2340') + stars(w, g === 'none' ? h : gy - 20, g === 'none' ? 90 : 40);
    if (g === 'moon') {
      s += rect(0, gy, w, h - gy, '#A9ADB5');
      for (let i = 0; i < 9; i++) s += `<ellipse cx="${F(hash(i + 20) * w)}" cy="${F(gy + 25 + hash(i + 30) * Math.max(0, h - gy - 40))}" rx="${F(18 + hash(i) * 30)}" ry="${F(6 + hash(i) * 8)}" fill="#8E929B"/>`;
    }
    return s;
  },
  pool: (w, h, gy, st, id) => sky(w, h, id, T.skyTop, T.skyBottom) + rect(0, gy - 26, w, 26, '#E6EEF2') +
    `<path d="M0,${F(gy)} ${Array.from({ length: 33 }, (_, i) => `Q${F(i * w / 32 + w / 64)},${F(gy - 8)} ${F((i + 1) * w / 32)},${F(gy)}`).join(' ')} L${F(w)},${F(h)} L0,${F(h)}Z" fill="#5DADE2" opacity="0.85"/>` +
    rect(0, gy + 8, w, 14, 'rgba(255,255,255,0.25)') + rect(0, h - 40, w, 40, '#7FB6D5'),
  soil: (w, h, gy, st, id) => {
    let s = sky(w, h, id, '#CDEBF5', '#F4F7EC') + rect(0, gy, w, h - gy, '#8E6240') + rect(0, gy, w, 16, '#79A65A');
    for (let i = 0; i < 40; i++) s += circ(hash(i) * w, gy + 40 + hash(i + 7) * Math.max(0, h - gy - 50), 4 + hash(i + 3) * 5, '#7D5536');
    return s;
  },
};
