// V2 2D samples, part 5: topic scenes with people (moments, energy, plants, speeding up, echo, shadows, waves,
// floating) and topic-only scenes (states of matter, a magnet's field, the Moon's phases).
// Numbers: none are printed except a tagged constant; positions come from the closed forms named in each scene.
export function install(K) {
  const { VW, VH, JI, sample, natSpeed, F, line, circ, lerp, shade, hash, words, label, arrow, badge, quote, sky, hills, ground, view, SCENES, ORDER } = K;
  const P = (p, V, T, fig) => K.person(p, V, T, fig);
  const who = n => ({ cast: n, look: K.LOOK[n] });
  const H = c => (K.CAST[c].child ? 1.25 : K.CAST[c].sex === 'f' ? 1.66 : 1.78);
  const outdoor = (T, V, id) => (T.outline ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, id) + hills(T, V.gy)) + ground(T, V);
  const add = (name, sc) => { SCENES[name] = sc; ORDER.push(name); };
  const sub = (a, b) => `${a}<tspan baseline-shift="sub" font-size="0.62em">${b}</tspan>`;
  const eq = (x, y, html, T, { size = 36, color, anchor = 'start' } = {}) =>
    `<text x="${F(x)}" y="${F(y)}" text-anchor="${anchor}" font-family="Cambria Math,Cambria,serif" font-style="italic" font-size="${size}" fill="${color || T.ink}">${html}</text>`;
  const panel = (x, y, w, h, T) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18" fill="${T.card}"/>`;
  // a sitting person's seat height above their feet line, and the pelvis offset (both metres)
  const seatOf = (fr, h) => [Math.min(fr[JI.thigh_l][1], fr[JI.thigh_r][1]) * h - 0.06, fr[JI.pelvis][0] * h];
  const smoothstep = u => u * u * (3 - 2 * u);

  // ---------- seesaw: moments balance (W1 d1 = W2 d2) ----------
  add('seesaw', { title: 'A father and daughter balance a seesaw: the heavier one sits nearer the pivot.', still: 1.2,
    draw(T, fig, t) {
      const V = view(175, 0, 850), top = 0.62, pt = top + 0.08, a = 1.6 * Math.sin(t * 1.2);   // a gentle rock about level (deg)
      const d1 = 0.95, d2 = 2.45;        // W1 d1 = W2 d2 with W1 / W2 = d2 / d1 (shown as arrow lengths, no values)
      let s = outdoor(T, V, 'skySS');
      const pv = [V.sx(0), V.sy(top)], ca = Math.cos(a * Math.PI / 180), sa = Math.sin(a * Math.PI / 180);
      const R = (x, y) => { const dx = V.sx(x) - pv[0], dy = V.sy(y) - pv[1]; return [pv[0] + dx * ca - dy * sa, pv[1] + dx * sa + dy * ca]; };
      s += `<path d="M${F(pv[0] - 0.38 * V.s)},${F(V.gy)} L${F(pv[0])},${F(pv[1])} L${F(pv[0] + 0.38 * V.s)},${F(V.gy)}Z" fill="#E4572E"/>`;
      let g = `<rect x="${F(V.sx(-3.0))}" y="${F(V.sy(pt))}" width="${F(6.0 * V.s)}" height="${F(0.08 * V.s)}" rx="7" fill="#F2C14E"/>`;
      [['man', -d1, 1], ['girl', d2, -1]].forEach(([cn, sx, d], i) => {
        const h = H(cn), fr = sample('Sitting_Idle_Loop', t + i * 0.7), [seat, px] = seatOf(fr, h), hx = sx + d * 0.42, hy = pt + 0.42;
        g += `<rect x="${F(V.sx(hx) - 5)}" y="${F(V.sy(hy))}" width="10" height="${F((hy - pt) * V.s)}" fill="#5D6470"/><rect x="${F(V.sx(hx) - 16)}" y="${F(V.sy(hy) - 6)}" width="32" height="12" rx="6" fill="#5D6470"/>`;
        g += P({ ...who(cn), fr, x: sx - d * px, y: pt - seat, dir: d, h, ik: { _r: [hx, hy], _l: [hx - d * 0.03, hy] }, noShadow: true }, V, T, fig);
      });
      // distances along the plank
      const dy = top - 0.2;
      g += line([V.sx(0), V.sy(dy)], [V.sx(-d1), V.sy(dy)], 3, T.muted) + line([V.sx(0), V.sy(dy)], [V.sx(d2), V.sy(dy)], 3, T.muted);
      for (const x of [-d1, 0, d2]) g += line([V.sx(x), V.sy(dy) - 10], [V.sx(x), V.sy(dy) + 10], 3, T.muted);
      g += label(V.sx(-d1 / 2) - 18, V.sy(dy) + 44, 'd_1', T.ink, T, 'start', 38) + label(V.sx(d2 / 2) - 18, V.sy(dy) + 44, 'd_2', T.ink, T, 'start', 38);
      s += `<g transform="rotate(${F(a)} ${F(pv[0])} ${F(pv[1])})">${g}</g>`;
      // weights act straight down from where each one sits
      const w1 = R(-d1, pt), w2 = R(d2, pt);
      s += arrow(w1[0] - 40, w1[1] - 10, w1[0] - 40, w1[1] + 150, T.weight, 'W_1', T, { lx: -60, ly: 0 });
      s += arrow(w2[0] + 40, w2[1] - 10, w2[0] + 40, w2[1] - 10 + 160 * d1 / d2, T.weight, 'W_2', T, { lx: 14, ly: 0 });
      s += panel(1060, 120, 500, 190, T) + words(1085, 168, 'balanced when the moments are equal:', T, { size: 24, weight: 600 }) +
        eq(1085, 232, `${sub('W', '1')} × ${sub('d', '1')} = ${sub('W', '2')} × ${sub('d', '2')}`, T, { size: 40 }) + words(1085, 285, 'moment = force × distance from the pivot', T, { size: 22, color: T.muted });
      return s + quote(this.title, T) + badge(T);
    } });

  // ---------- swing: PE <-> KE (pendulum, small-angle form) ----------
  add('swing', { title: 'On a swing, energy keeps changing between height (PE) and speed (KE).', still: 0.25,
    draw(T, fig, t) {
      const V = view(150, -0.6, 870), Lr = 2.3, top = 3.05, w = Math.sqrt(9.81 / Lr), th0 = 0.62;
      const th = th0 * Math.cos(w * t), thd = -th0 * w * Math.sin(w * t);
      let s = outdoor(T, V, 'skySW');
      const pv = [V.sx(0), V.sy(top)];
      s += line([V.sx(-1.5), V.gy], pv, 14, '#4F7CAC') + line([V.sx(1.5), V.gy], pv, 14, '#4F7CAC') + circ(pv, 16, '#3B5F86');
      // the seat's path, and the lowest / highest heights
      const arc = []; for (let k = -1; k <= 1.0001; k += 0.05) { const q = th0 * k; arc.push(`${F(V.sx(Lr * Math.sin(q)))},${F(V.sy(top - Lr * Math.cos(q)))}`); }
      s += `<path d="M${arc.join('L')}" fill="none" stroke="${T.path}" stroke-width="4" stroke-dasharray="4 12" stroke-linecap="round"/>`;
      const yl = top - Lr, yh = top - Lr * Math.cos(th0);
      s += line([V.sx(1.0), V.sy(yl)], [V.sx(2.6), V.sy(yl)], 3, T.muted, 'stroke-dasharray="10 8"') + line([V.sx(1.2), V.sy(yh)], [V.sx(2.6), V.sy(yh)], 3, T.muted, 'stroke-dasharray="10 8"');
      s += arrow(V.sx(2.45), V.sy(yl), V.sx(2.45), V.sy(yh) + 2, T.muted, 'h', T, { w: 4, lx: 12, ly: 40 });
      // rope + seat + rider, rotated about the top bar
      const h = H('girl'), fr = sample('Sitting_Idle_Loop', 0.4), [seat, px] = seatOf(fr, h), sy0 = yl + 0.05;
      let g = line(pv, [V.sx(0), V.sy(yl)], 5, '#6B4A2F') + `<rect x="${F(V.sx(-0.3))}" y="${F(V.sy(sy0))}" width="${F(0.6 * V.s)}" height="${F(0.07 * V.s)}" rx="5" fill="#A0673F"/>`;
      g += P({ ...who('girl'), fr, x: -px, y: sy0 - seat, dir: 1, h, ik: { _r: [0.02, sy0 + 0.55], _l: [0.0, sy0 + 0.62] }, noShadow: true }, V, T, fig);
      s += `<g transform="rotate(${F(-th * 180 / Math.PI)} ${F(pv[0])} ${F(pv[1])})">${g}</g>`;
      const sp = [V.sx(Lr * Math.sin(th)), V.sy(top - Lr * Math.cos(th))], vs = Lr * thd * 70;
      s += arrow(sp[0], sp[1] + 30, sp[0] + vs * Math.cos(th), sp[1] + 30 - vs * Math.sin(th), T.vel, 'v', T, { lx: 10, ly: -8 });
      // energy bars: PE from the height, KE = the rest (no friction)
      const pe = (1 - Math.cos(th)) / (1 - Math.cos(th0)), ke = 1 - pe, bx = 1110, bw = 380;
      s += panel(1080, 330, 470, 250, T) + words(1105, 375, 'energy (no friction)', T, { size: 26, weight: 600 });
      s += words(1105, 430, 'PE', T, { size: 26, weight: 700, color: '#2E7D32' }) + `<rect x="${bx + 60}" y="406" width="${bw - 60}" height="30" rx="8" fill="#E3E8E3"/><rect x="${bx + 60}" y="406" width="${F((bw - 60) * pe)}" height="30" rx="8" fill="#43A047"/>`;
      s += words(1105, 490, 'KE', T, { size: 26, weight: 700, color: '#C0392B' }) + `<rect x="${bx + 60}" y="466" width="${bw - 60}" height="30" rx="8" fill="#F1E3E1"/><rect x="${bx + 60}" y="466" width="${F((bw - 60) * ke)}" height="30" rx="8" fill="#E4572E"/>`;
      s += words(1105, 552, 'PE + KE stays the same', T, { size: 24, color: T.muted });
      s += words(V.sx(-Lr * Math.sin(th0)) - 210, V.sy(yh) - 30, 'highest: all PE', T, { size: 24, weight: 600 }) + words(V.sx(0) - 90, V.sy(yl) + 110, 'lowest: all KE', T, { size: 24, weight: 600 });
      return s + quote(this.title, T) + badge(T);
    } });

  // ---------- watering a plant (time-lapse growth, water up the stem) ----------
  add('watering', { title: 'She waters the plant; the roots take in water and, with sunlight, the plant grows.', still: 1.6,
    draw(T, fig, t) {
      const V = view(220, -0.6, 860), h = H('woman2'), x = -2.4, d = 1, clip = 'Farm_Watering';
      let s = (T.outline ? '' : sky(T, 'skyWT', '#CDEBF5', '#F4F7EC')) + ground(T, V, { color: '#9CC57E' });
      s += circ([1420, 170], 70, '#FFD23F');
      for (let i = 0; i < 8; i++) { const a2 = i * Math.PI / 4 + t * 0.2; s += line([1420 + Math.cos(a2) * 88, 170 + Math.sin(a2) * 88], [1420 + Math.cos(a2) * 115, 170 + Math.sin(a2) * 115], 6, '#FFC21A'); }
      const can = fr => { const q = fr[JI.hand_r]; const hw = [x + d * q[0] * h, q[1] * h]; const cw = [hw[0] + d * 0.1, hw[1] - 0.13]; return { hw, cw, tip: [cw[0] + d * 0.36, cw[1] + 0.12] }; };
      const ref = can(sample(clip, 1.0)), soil = 0.4, g = 9.81, vx = 0.8;
      const xp = ref.tip[0] + vx * Math.sqrt(2 * (ref.tip[1] - soil) / g);   // where the water lands (projectile from the spout)
      // pot (cut away: soil and roots)
      const pot = [[xp - 0.2, soil], [xp + 0.2, soil], [xp + 0.14, 0], [xp - 0.14, 0]].map(([u, v]) => `${F(V.sx(u))},${F(V.sy(v))}`).join(' ');
      s += `<polygon points="${pot}" fill="#C8693E"/><rect x="${F(V.sx(xp - 0.17))}" y="${F(V.sy(soil))}" width="${F(0.34 * V.s)}" height="${F(0.3 * V.s)}" fill="#6E4A2E"/>`;
      const grow = smoothstep((t % 12) / 12), hg = 0.12 + 0.62 * grow, stem = [V.sx(xp), V.sy(soil)];
      for (let i = 0; i < 5; i++) { const a2 = (-60 + i * 30) * Math.PI / 180, rl = (0.08 + 0.12 * grow) * V.s; s += `<path d="M${F(stem[0])},${F(stem[1])} q${F(Math.sin(a2) * rl * 0.5)},${F(rl * 0.5)} ${F(Math.sin(a2) * rl)},${F(rl * Math.cos(a2) * 0.9)}" fill="none" stroke="#F3E6C4" stroke-width="4"/>`; }
      s += `<rect x="${F(V.sx(xp - 0.2))}" y="${F(V.sy(soil) - 4)}" width="${F(0.4 * V.s)}" height="12" rx="5" fill="#B5582F"/>`;
      s += line(stem, [stem[0], V.sy(soil + hg)], 8, '#3F8A4B');
      const nl = 1 + Math.floor(hg / 0.13);
      for (let i = 0; i < nl; i++) { const y = soil + Math.min(hg - 0.02, 0.1 + i * 0.13), sd = i % 2 ? 1 : -1, lsz = 0.07 + 0.04 * Math.min(1, (hg - i * 0.13) / 0.2);
        s += `<ellipse cx="${F(V.sx(xp + sd * lsz * 0.9))}" cy="${F(V.sy(y + 0.03))}" rx="${F(lsz * V.s)}" ry="${F(lsz * 0.45 * V.s)}" fill="#4E9F5A" transform="rotate(${-sd * 25} ${F(V.sx(xp + sd * lsz * 0.9))} ${F(V.sy(y + 0.03))})"/>`; }
      for (let i = 0; i < 4; i++) { const ph = (t * 0.5 + i / 4) % 1; s += circ([stem[0], V.sy(soil - 0.2 + ph * (hg + 0.15))], 6, '#3D8BD1', `opacity="${F(1 - ph)}"`); }
      // the woman, her can and the water
      const fr = sample(clip, t), c = can(fr);
      s += P({ ...who('woman2'), fr, x, dir: d, h }, V, T, fig);
      const cw = [V.sx(c.cw[0]), V.sy(c.cw[1])], tip = [V.sx(c.tip[0]), V.sy(c.tip[1])];
      s += line([cw[0] + d * 0.08 * V.s, cw[1] - 0.04 * V.s], tip, 0.04 * V.s, '#2F80ED') +
        `<rect x="${F(cw[0] - 0.14 * V.s)}" y="${F(cw[1] - 0.1 * V.s)}" width="${F(0.28 * V.s)}" height="${F(0.22 * V.s)}" rx="12" fill="#2F80ED"/>` +
        `<path d="M${F(cw[0] - 0.08 * V.s)},${F(cw[1] - 0.1 * V.s)} q${F(0.08 * V.s)},${F(-0.14 * V.s)} ${F(0.16 * V.s)},0" fill="none" stroke="#1F5FBF" stroke-width="9"/>`;
      for (let i = 0; i < 10; i++) { const ph = (t * 1.6 + i / 10) % 1, tf = Math.sqrt(2 * (c.tip[1] - soil) / g) * ph;
        s += circ([V.sx(c.tip[0] + vx * tf), V.sy(c.tip[1] - 0.5 * g * tf * tf)], 6, '#5DADE2'); }
      s += P({ ...who('girl'), clip: 'Idle_Talking_Loop', t: t + 0.4, x: xp + 1.2, dir: -1, h: H('girl') }, V, T, fig);
      s += words(V.sx(xp) + 30, V.sy(-0.08) + 70, 'roots take in water', T, { size: 24, weight: 600 }) + words(1180, 300, 'sunlight', T, { size: 26, weight: 700 });
      s += words(48, 960, 'time-lapse: the plant grows over many days', T, { size: 24, color: T.muted });
      return s + quote(this.title, T);
    } });

  // ---------- planting a seed: germination stages ----------
  add('germination', { title: 'A boy plants a seed; underground, the root grows down and the shoot grows up.', still: 1.3,
    draw(T, fig, t) {
      const V = view(150, 0.4, 560);
      let s = (T.outline ? '' : sky(T, 'skyGR', '#CDEBF5', '#F4F7EC')) + `<rect y="${V.gy}" width="${VW}" height="${VH - V.gy}" fill="#8E6240"/><rect y="${V.gy}" width="${VW}" height="16" fill="#79A65A"/>`;
      for (let i = 0; i < 40; i++) s += circ([hash(i) * VW, V.gy + 40 + hash(i + 7) * 400], 4 + hash(i + 3) * 5, '#7D5536');
      const h = H('boy'), x = -4.5, fr = sample('Farm_PlantSeed', t), q = fr[JI.hand_r], hw = [V.sx(x + q[0] * h), V.sy(q[1] * h)];
      s += P({ ...who('boy'), fr, x, dir: 1, h }, V, T, fig);
      s += `<ellipse cx="${F(hw[0] + 6)}" cy="${F(V.gy + 6)}" rx="26" ry="10" fill="#5A3A22"/>` + `<ellipse cx="${F(hw[0] + 6)}" cy="${F(hw[1] + 14 + ((t * 1.2) % 1) * (V.gy - hw[1] - 10))}" rx="9" ry="6" fill="#6B4423"/>`;
      // four stages, drawn enlarged in the soil
      const sw = Math.sin(t * 2) * 3, Y = V.gy + 170, seed = (cx, k = 1) => `<ellipse cx="${cx}" cy="${Y}" rx="${26 * k}" ry="${18 * k}" fill="#8B5A2B"/><path d="M${cx - 18 * k},${Y} q${18 * k},-9 ${36 * k},0" fill="none" stroke="#5E3A1A" stroke-width="3"/>`;
      const root = (cx, len, br) => { let r = `<path d="M${cx},${Y + 14} q${8 + sw},${len * 0.5} 0,${len}" fill="none" stroke="#F3E6C4" stroke-width="6" stroke-linecap="round"/>`;
        for (let i = 0; i < br; i++) { const y = Y + 40 + i * 30, sd = i % 2 ? 1 : -1; r += `<path d="M${cx + 4},${y} q${sd * 20},10 ${sd * 38},26" fill="none" stroke="#F3E6C4" stroke-width="3"/>`; } return r; };
      const xs = [610, 860, 1110, 1360];
      s += seed(xs[0]);
      s += root(xs[1], 90, 0) + seed(xs[1]);
      s += root(xs[2], 150, 2) + `<path d="M${xs[2]},${Y - 12} C${xs[2] - 6},${Y - 80} ${xs[2] + 10},${Y - 140} ${xs[2] - 18},${V.gy + 12}" fill="none" stroke="#7CB342" stroke-width="7" stroke-linecap="round"/>` + seed(xs[2], 0.9);
      s += root(xs[3], 190, 4) + line([xs[3], Y - 10], [xs[3] + sw, V.gy - 120], 8, '#3F8A4B') +
        `<ellipse cx="${xs[3] - 34 + sw}" cy="${V.gy - 124}" rx="38" ry="16" fill="#4E9F5A" transform="rotate(20 ${xs[3] - 34 + sw} ${V.gy - 124})"/><ellipse cx="${xs[3] + 34 + sw}" cy="${V.gy - 124}" rx="38" ry="16" fill="#4E9F5A" transform="rotate(-20 ${xs[3] + 34 + sw} ${V.gy - 124})"/>` +
        `<path d="M${xs[3] - 26},${Y + 6} q26,16 52,0" fill="none" stroke="#8B5A2B" stroke-width="6"/>`;
      for (let i = 0; i < 3; i++) s += arrow(xs[i] + 60, Y + 150, xs[i + 1] - 60, Y + 150, '#F4E3C3', '', T, { w: 5 });
      ['seed', 'root grows down', 'shoot grows up', 'first leaves'].forEach((w, i) => { s += words(xs[i], Y + 235 - (i % 2) * 34, w, T, { size: 24, weight: 700, anchor: 'middle', color: '#ffffff', halo: false }); });
      for (let i = 0; i < 8; i++) { const ph = (t * 0.4 + hash(i + 20)) % 1; s += `<path d="M${F(560 + hash(i) * 860)},${F(V.gy + 30 + ph * 300 - 8)} q7,9 0,15 q-7,-6 0,-15Z" fill="#5DADE2" opacity="${F(1 - ph)}"/>`; }
      s += panel(1040, 120, 520, 120, T) + words(1065, 168, 'a seed needs: water · air · warmth', T, { size: 26, weight: 600 }) + words(1065, 212, 'seed and roots drawn enlarged', T, { size: 22, color: T.muted });
      return s + quote(this.title, T);
    } });

  // ---------- a car speeding up: equal times, growing gaps (x = a t^2 / 2) ----------
  add('speedup', { title: 'A car starts from rest and speeds up: in equal times it goes further and further.', still: 5.0,
    draw(T, fig, t) {
      const V = view(85, 0, 700), a = 1.0, dt = 1.3, x0 = -9.2, n = 4, cyc = n * dt + 2, tt = Math.min(t % cyc, n * dt);
      let s = outdoor(T, V, 'skySU');
      s += `<rect y="${V.gy}" width="${VW}" height="110" fill="#5F6670"/>` + line([0, V.gy + 55], [VW, V.gy + 55], 5, '#F4F1EA', 'stroke-dasharray="40 30"');
      const Vf = view(58, 0, V.gy - 6);   // the far side of the road: smaller = further away
      s += P({ ...who('woman3'), clip: 'Idle_TalkingPhone_Loop', t, x: -2.0, dir: -1, h: H('woman3'), noShadow: true }, Vf, T, fig);
      s += P({ ...who('boy'), clip: 'Idle_Loop', t: t + 0.6, x: -0.9, dir: -1, h: H('boy'), noShadow: true }, Vf, T, fig);
      const xs = []; for (let k = 0; k <= n; k++) xs.push(x0 + 0.5 * a * (k * dt) ** 2);
      for (let k = 0; k <= n; k++) {
        if (k * dt > tt + 1e-6) break;
        const fx = V.sx(xs[k] + 4.45);
        if (k * dt < tt - 0.05) s += `<g opacity="0.25">${K.car(V, xs[k], T, '#E4572E')}</g>`;
        s += line([fx, V.gy + 120], [fx, V.gy + 170], 4, T.ink);
        const cc = [fx, V.sy(2.4)], ang = k * Math.PI / 2;
        s += circ(cc, 26, '#ffffff', `stroke="${T.ink}" stroke-width="4"`) + line(cc, [cc[0] + 18 * Math.sin(ang), cc[1] - 18 * Math.cos(ang)], 4, T.applied) + line([fx, V.sy(2.4) + 28], [fx, V.sy(1.6)], 2, T.muted, 'stroke-dasharray="4 6"');
        if (k > 0) { const px = V.sx(xs[k - 1] + 4.45); s += line([px + 4, V.gy + 150], [fx - 4, V.gy + 150], 4, T.applied); }
      }
      const xc = x0 + 0.5 * a * tt * tt, v = a * tt;
      s += K.car(V, xc, T, '#E4572E', t, v);
      if (v > 0.05) s += arrow(V.sx(xc + 4.6), V.sy(0.7), V.sx(xc + 4.6) + v * 32, V.sy(0.7), T.vel, 'v', T, { lx: 8, ly: -10 });
      s += arrow(V.sx(xc + 1.6), V.sy(1.9), V.sx(xc + 1.6) + 80, V.sy(1.9), T.applied, 'a', T, { w: 5, lx: 8, ly: -8 });
      s += words(48, 960, 'each clock = one more equal tick of time  ·  the gaps along the road keep growing', T, { size: 24, color: '#ffffff', halo: false });
      return s + quote(this.title, T) + badge(T);
    } });

  // ---------- echo: sound goes to the cliff and comes back (mirror source) ----------
  add('echo', { title: 'He shouts towards a cliff; the sound reflects and he hears the echo a moment later.', still: 6.2,
    draw(T, fig, t) {
      const V = view(105, 0, 820), cl = 5.0, h = H('man2'), x = -6.3, cvis = 2.6, fr = sample('Idle_Rail_Call', t);
      let s = outdoor(T, V, 'skyEC');
      const hq = fr[JI.Head], m = [x + hq[0] * h + 0.14, hq[1] * h - 0.04], D = cl - m[0], cyc = 2 * D / cvis + 1.6, tt = t % cyc;
      const cpx = V.sx(cl);
      s += `<path d="M${F(cpx)},${F(V.gy)} L${F(cpx + 30)},${F(V.sy(2))} L${F(cpx + 10)},${F(V.sy(3.6))} L${F(cpx + 50)},${F(V.sy(5.4))} L${F(cpx + 20)},0 L${VW},0 L${VW},${F(V.gy)}Z" fill="#9C8F80"/>` +
        `<path d="M${F(cpx + 60)},${F(V.sy(1.2))} l120,-30 M${F(cpx + 50)},${F(V.sy(3))} l150,-20 M${F(cpx + 70)},${F(V.sy(4.6))} l110,-40" stroke="#857868" stroke-width="6"/>`;
      s += P({ ...who('man2'), fr, x, dir: 1, h }, V, T, fig);
      s += `<defs><clipPath id="ecClip"><rect x="0" y="0" width="${F(cpx)}" height="${VH}"/></clipPath></defs><g clip-path="url(#ecClip)">`;
      const mp = [V.sx(m[0]), V.sy(m[1])], mir = [V.sx(2 * cl - m[0]), mp[1]], A = 30 * Math.PI / 180;
      const arcP = (c, r, sd) => `M${F(c[0] + sd * r * Math.cos(A))},${F(c[1] - r * Math.sin(A))} A${F(r)},${F(r)} 0 0 ${sd > 0 ? 1 : 0} ${F(c[0] + sd * r * Math.cos(A))},${F(c[1] + r * Math.sin(A))}`;
      for (const te of [0, 0.3, 0.6]) {
        const r = cvis * (tt - te) * V.s; if (r <= 0) continue;
        s += `<path d="${arcP(mp, r, 1)}" fill="none" stroke="${T.vel}" stroke-width="6" stroke-linecap="round"/>`;
        if (r > D * V.s) s += `<path d="${arcP(mir, r, -1)}" fill="none" stroke="${T.applied}" stroke-width="6" stroke-linecap="round" opacity="0.85"/>`;
      }
      s += '</g>';
      s += arrow(V.sx(-3), V.sy(3.3), V.sx(2), V.sy(3.3), T.vel, '', T, { w: 5 }) + words(V.sx(-3), V.sy(3.3) - 20, 'sound goes out', T, { size: 26, weight: 600, color: T.vel });
      s += arrow(V.sx(2), V.sy(-0.6), V.sx(-3), V.sy(-0.6), T.applied, '', T, { w: 5 }) + words(V.sx(-3), V.sy(-0.6) + 50, 'echo comes back', T, { size: 26, weight: 600, color: T.applied });
      s += panel(820, 110, 520, 150, T) + words(845, 158, 'distance to the cliff =', T, { size: 26, weight: 600 }) + words(845, 200, 'speed of sound × time to hear the echo ÷ 2', T, { size: 24 }) +
        words(845, 240, 'speed of sound in air ≈ 343 m/s at 20 °C · constant', T, { size: 20, color: T.muted });
      return s + quote(this.title, T) + badge(T, 'Slowed down');
    } });

  // ---------- shadow from a street lamp (similar triangles) ----------
  add('shadow', { title: 'Light travels in straight lines, so the boy casts a shadow; nearer the lamp, it is shorter.', still: 1.0,
    draw(T, fig, t) {
      const V = view(130, 0, 840), xl = 3.6, Hl = 4.0, h = H('boy'), vs = natSpeed('Walk_Loop') * h, x1 = -3.0, x2 = 2.4, span = x2 - x1;
      const u = (t * vs) % (2 * span), fwd = u < span, x = fwd ? x1 + u : x2 - (u - span), d = fwd ? 1 : -1;
      let s = sky(T, 'skySH', '#18213D', '#3A4774') + `<rect y="${V.gy}" width="${VW}" height="${VH - V.gy}" fill="#3F5A3B"/>`;
      for (let i = 0; i < 30; i++) s += circ([hash(i) * VW, hash(i + 5) * 420], 1.5 + hash(i + 9) * 2, '#ffffff', `opacity="${F(0.5 + 0.5 * hash(i + 2))}"`);
      s += circ([200, 160], 50, '#F4F1DE') + circ([222, 148], 46, '#18213D');
      const lp = [V.sx(xl), V.sy(Hl)], tip = xl + (x - xl) * Hl / (Hl - h);   // where the ray over the head meets the ground
      s += `<defs><radialGradient id="shG"><stop offset="0" stop-color="#FFE9A8" stop-opacity="0.75"/><stop offset="1" stop-color="#FFE9A8" stop-opacity="0"/></radialGradient></defs>`;
      s += `<path d="M${F(lp[0])},${F(lp[1])} L${F(V.sx(xl - 6))},${F(V.gy)} L${F(V.sx(xl + 3))},${F(V.gy)}Z" fill="#FFE9A8" opacity="0.13"/><ellipse cx="${F(lp[0])}" cy="${F(V.gy + 10)}" rx="${F(4.5 * V.s)}" ry="40" fill="url(#shG)"/>`;
      s += `<path d="M${F(V.sx(x))},${F(V.gy + 2)} L${F(V.sx(tip))},${F(V.gy + 2)} L${F(V.sx(tip) + 8)},${F(V.gy + 14)} L${F(V.sx(x) + 10)},${F(V.gy + 16)}Z" fill="#1A2418" opacity="0.85"/>`;
      s += P({ ...who('boy'), clip: 'Walk_Loop', t, x, dir: d, h, noShadow: true }, V, T, fig);
      s += line(lp, [V.sx(tip), V.gy], 3, '#FFD54F', 'stroke-dasharray="12 10"') + line(lp, [V.sx(x), V.gy], 3, '#FFD54F', 'stroke-dasharray="12 10" opacity="0.6"');
      s += line([V.sx(xl), V.gy], [V.sx(xl), lp[1] + 20], 14, '#2D3142') + `<path d="M${F(lp[0] - 50)},${F(lp[1] + 22)} L${F(lp[0] + 50)},${F(lp[1] + 22)} L${F(lp[0] + 30)},${F(lp[1] - 18)} L${F(lp[0] - 30)},${F(lp[1] - 18)}Z" fill="#2D3142"/>` + circ([lp[0], lp[1] + 26], 20, '#FFF3B0');
      s += words(Math.min(V.sx(tip), V.sx(x)) + 10, V.gy + 60, 'shadow', T, { size: 28, weight: 700, color: '#ffffff', halo: false });
      s += words(V.sx(xl) - 600, V.sy(Hl) - 40, 'light travels in straight lines', T, { size: 26, weight: 600, color: '#FFE9A8', halo: false });
      s += panel(1090, 120, 470, 120, { ...T, card: 'rgba(255,255,255,0.92)' }) + words(1115, 168, 'nearer the lamp → shorter shadow', T, { size: 26, weight: 600 }) + words(1115, 212, 'further away → longer shadow', T, { size: 26, weight: 600 });
      return s + words(48, 66, '“' + this.title + '”', T, { size: 30, color: '#E6E9F2', weight: 400, halo: false });
    } });

  // ---------- a wave on a rope: y = A sin(k x - w t) ----------
  add('ropewave', { title: 'She shakes a rope: the wave travels along, each bit only moves up and down.', still: 6.5,
    draw(T, fig, t) {
      const V = view(150, 0.2, 820), h = H('woman'), xw = -4.7, x0 = -4.05, y0 = 1.02, xe = 5.0, A = 0.28, lam = 2.4, v = 1.6;
      const k = 2 * Math.PI / lam, w = k * v, tt = t % 9, front = v * tt;
      const Y = xx => (xx - x0 <= front ? A * Math.sin(k * (xx - x0) - w * tt) : 0);
      let s = outdoor(T, V, 'skyRW');
      s += line([V.sx(-4.2), V.sy(y0)], [V.sx(xe), V.sy(y0)], 2, T.muted, 'stroke-dasharray="8 10"');
      s += `<rect x="${F(V.sx(xe))}" y="${F(V.sy(1.5))}" width="${F(0.16 * V.s)}" height="${F(1.5 * V.s)}" fill="#8A5A3B"/>`;
      const pts = []; for (let xx = x0; xx <= xe + 1e-6; xx += 0.04) pts.push(`${F(V.sx(xx))},${F(V.sy(y0 + Y(xx)))}`);
      s += P({ ...who('woman'), clip: 'Idle_Loop', t, x: xw, dir: 1, h, ik: { _r: [x0, y0 + Y(x0)], _l: [x0 - 0.06, y0 + Y(x0) + 0.02] } }, V, T, fig);
      s += `<path d="M${pts.join('L')}" fill="none" stroke="#C8A165" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>`;
      // one marked bit of rope: it only goes up and down
      const xm = 1.0, ym = y0 + Y(xm);
      s += line([V.sx(xm) + 34, V.sy(y0 + A)], [V.sx(xm) + 34, V.sy(y0 - A)], 3, '#C0392B', 'stroke-dasharray="6 6"') + circ([V.sx(xm), V.sy(ym)], 13, '#C0392B');
      // two neighbouring crests (computed) -> wavelength; amplitude at the first
      const cr = []; for (let n = -6; n < 12; n++) { const xx = x0 + (Math.PI / 2 + 2 * Math.PI * n + w * tt) / k; if (xx > x0 + 0.3 && xx < Math.min(xe, x0 + front) - 0.1) cr.push(xx); }
      if (cr.length >= 2) {
        const yb = V.sy(y0 + A) - 40, a0 = V.sx(cr[0]), a1 = V.sx(cr[1]);
        s += line([a0, yb], [a1, yb], 3, T.ink) + line([a0, yb - 12], [a0, yb + 12], 3, T.ink) + line([a1, yb - 12], [a1, yb + 12], 3, T.ink) + label((a0 + a1) / 2 - 10, yb - 16, 'λ', T.ink, T, 'start', 40);
        s += arrow(a0, V.sy(y0), a0, V.sy(y0 + A) + 2, T.applied, 'A', T, { w: 4, lx: -40, ly: 30 });
      }
      s += arrow(V.sx(-1), V.sy(2.3), V.sx(1.6), V.sy(2.3), T.vel, 'v', T, { lx: 10, ly: 10 }) + words(V.sx(-1), V.sy(2.3) - 22, 'the wave moves along', T, { size: 24, weight: 600, color: T.vel });
      s += words(V.sx(xm) + 50, V.sy(y0 - A) + 50, 'this bit only moves up and down', T, { size: 24, weight: 600, color: '#C0392B' });
      s += panel(1130, 110, 430, 110, T) + eq(1155, 180, 'v = f λ', T, { size: 40 }) + words(1300, 178, '(speed = frequency × wavelength)', T, { size: 18, color: T.muted });
      return s + quote(this.title, T) + badge(T);
    } });

  // ---------- floating: upthrust balances weight ----------
  add('float', { title: 'A swimmer and a beach ball float: the water pushes up as hard as gravity pulls down.', still: 2.0,
    draw(T, fig, t) {
      const V = view(165, 0, 900), surf = 1.7, h = H('man'), x = -3.4 + ((0.45 * t) % 4.5);
      let s = (T.outline ? '' : sky(T, 'skyFL', '#CFEAF6', '#F2F7F7'));
      s += `<rect x="0" y="${F(V.sy(surf + 0.25))}" width="${VW}" height="${F(V.gy - V.sy(surf + 0.25))}" fill="#D7E3EA"/>`;
      s += `<rect x="0" y="${F(V.sy(surf))}" width="${VW}" height="${F(V.gy - V.sy(surf))}" fill="#4EA8DE"/>`;
      for (let i = 0; i < 9; i++) s += `<rect x="0" y="${F(V.sy(surf) + 30 + i * 40)}" width="${VW}" height="2" fill="#ffffff" opacity="0.12"/>`;
      s += `<rect y="${V.gy}" width="${VW}" height="${VH - V.gy}" fill="#B8C7D1"/>`;
      const fr = sample('Swim_Fwd_Loop', t), py = surf - 0.1 - fr[JI.pelvis][1] * h;
      s += P({ ...who('man'), fr, x, y: py, dir: 1, h, noShadow: true }, V, T, fig);
      const bx = 3.2, br = 0.3, by = surf + 0.1 + 0.03 * Math.sin(t * 2);
      s += circ([V.sx(bx), V.sy(by)], br * V.s, '#ffffff') + `<path d="M${F(V.sx(bx))},${F(V.sy(by) - br * V.s)} A${F(br * V.s)},${F(br * V.s)} 0 0 1 ${F(V.sx(bx) + br * V.s)},${F(V.sy(by))} L${F(V.sx(bx))},${F(V.sy(by))}Z" fill="#E4572E"/>` +
        `<path d="M${F(V.sx(bx))},${F(V.sy(by) + br * V.s)} A${F(br * V.s)},${F(br * V.s)} 0 0 1 ${F(V.sx(bx) - br * V.s)},${F(V.sy(by))} L${F(V.sx(bx))},${F(V.sy(by))}Z" fill="#2F80ED"/>`;
      // the water in front: the parts below the surface look under water
      let wave = `M0,${F(V.sy(surf))}`; for (let px = 0; px <= VW; px += 20) wave += ` L${px},${F(V.sy(surf) + 5 * Math.sin(px / 60 + t * 2.5))}`;
      s += `<path d="${wave} L${VW},${F(V.gy)} L0,${F(V.gy)}Z" fill="#2E86C1" opacity="0.38"/><path d="${wave}" fill="none" stroke="#ffffff" stroke-width="4" opacity="0.8"/>`;
      const cxm = V.sx(x + fr[JI.spine_02][0] * h), cym = V.sy(py + fr[JI.spine_02][1] * h);
      s += arrow(cxm, cym, cxm, cym - 170, T.normal, 'U', T, { lx: 12, ly: 20 }) + arrow(cxm + 30, cym, cxm + 30, cym + 170, T.weight, 'W', T, { lx: 12, ly: 0 });
      s += arrow(V.sx(bx), V.sy(by), V.sx(bx), V.sy(by) - 70, T.normal, '', T, { w: 5 }) + arrow(V.sx(bx) + 16, V.sy(by), V.sx(bx) + 16, V.sy(by) + 70, T.weight, '', T, { w: 5 });
      s += panel(1060, 120, 500, 150, T) + words(1085, 168, 'floating:  upthrust U = weight W', T, { size: 26, weight: 600 }) + words(1085, 212, 'upthrust = weight of the water pushed aside', T, { size: 22, color: T.muted }) +
        words(1085, 248, 'U up · W down', T, { size: 22, color: T.muted });
      return s + quote(this.title, T);
    } });

  // ---------- states of matter (particles) ----------
  add('states', { title: 'Solid, liquid, gas: the same particles, held tight, sliding, or flying apart.', still: 1.0,
    draw(T, fig, t) {
      let s = `<rect width="${VW}" height="${VH}" fill="${T.outline ? T.bg : '#F3EEE4'}"/>`;
      const boxes = [[110, 'solid', 'ice', '#7FB3D5'], [610, 'liquid', 'water', '#3D8BD1'], [1110, 'gas', 'steam', '#AAB7C4']], W = 380, top = 250, bot = 720;
      boxes.forEach(([bx, nm, eg, col], j) => {
        s += `<rect x="${bx}" y="${top}" width="${W}" height="${bot - top}" rx="14" fill="#ffffff" stroke="#9AA5B1" stroke-width="5"/>`;
        let ps = '';
        if (j === 0) for (let r = 0; r < 6; r++) for (let c = 0; c < 8; c++) { const i = r * 8 + c; ps += circ([bx + 50 + c * 40 + 3 * Math.sin(t * 22 + i), bot - 30 - r * 40 + 3 * Math.cos(t * 19 + i * 1.7)], 17, col); }
        if (j === 1) for (let i = 0; i < 40; i++) { const u = (hash(i) * 8 + t * 0.25 * (0.5 + hash(i + 3))) % 8, row = Math.floor(hash(i + 9) * 5);
          ps += circ([bx + 30 + ((u * 41) % (W - 60)), bot - 28 - row * 37 - 6 * Math.sin(t * 3 + i)], 17, col); }
        if (j === 2) for (let i = 0; i < 12; i++) { const tri = (z, L) => { const m = ((z % (2 * L)) + 2 * L) % (2 * L); return m < L ? m : 2 * L - m; };
          ps += circ([bx + 22 + tri(hash(i) * 700 + t * (160 + 90 * hash(i + 4)), W - 44), top + 22 + tri(hash(i + 8) * 700 + t * (130 + 80 * hash(i + 6)), bot - top - 44)], 17, col); }
        s += ps + words(bx + W / 2, top - 70, nm, T, { size: 38, weight: 700, anchor: 'middle' }) + words(bx + W / 2, top - 28, `(e.g. ${eg})`, T, { size: 24, anchor: 'middle', color: T.muted });
      });
      s += arrow(505, 480, 600, 480, T.applied, '', T, { w: 6 }) + words(552, 450, 'heat', T, { size: 22, anchor: 'middle', weight: 700, color: T.applied }) +
        arrow(1005, 480, 1100, 480, T.applied, '', T, { w: 6 }) + words(1052, 450, 'heat', T, { size: 22, anchor: 'middle', weight: 700, color: T.applied });
      s += words(552, 530, 'melting', T, { size: 22, anchor: 'middle' }) + words(1052, 530, 'boiling', T, { size: 22, anchor: 'middle' });
      [['fixed places, only vibrate', 'keeps its shape'], ['close, slide past each other', 'takes the shape of the container'], ['far apart, fast, everywhere', 'fills the whole container']].forEach(([a2, b], j) => {
        s += words(300 + j * 500, 790, a2, T, { size: 24, weight: 600, anchor: 'middle' }) + words(300 + j * 500, 828, b, T, { size: 22, anchor: 'middle', color: T.muted });
      });
      return s + quote(this.title, T) + badge(T, 'Particles not to scale');
    } });

  // ---------- a bar magnet's field: lines traced through the two-pole field ----------
  let magLines = null;
  const N = [935, 560], S = [665, 560];
  const Bf = (x, y) => { const a = [x - N[0], y - N[1]], b = [x - S[0], y - S[1]], ra = Math.hypot(...a) ** 3 || 1, rb = Math.hypot(...b) ** 3 || 1;
    return [a[0] / ra - b[0] / rb, a[1] / ra - b[1] / rb]; };
  function traceLines() {
    const out = [];
    for (let deg = -160; deg <= 160; deg += 20) {
      const a0 = deg * Math.PI / 180; let p = [N[0] + 16 * Math.cos(a0), N[1] + 16 * Math.sin(a0)];
      if (Math.abs(p[1] - N[1]) < 30 && p[0] < N[0]) continue;
      const pts = [p];
      for (let i = 0; i < 2500; i++) {
        const b1 = Bf(...p), l1 = Math.hypot(...b1) || 1, mid = [p[0] + 2 * b1[0] / l1, p[1] + 2 * b1[1] / l1], b2 = Bf(...mid), l2 = Math.hypot(...b2) || 1;
        p = [p[0] + 4 * b2[0] / l2, p[1] + 4 * b2[1] / l2]; pts.push(p);
        if (Math.hypot(p[0] - S[0], p[1] - S[1]) < 16 || p[0] < -40 || p[0] > VW + 40 || p[1] < 60 || p[1] > VH + 40) break;
      }
      let L = 0; const cum = [0]; for (let i = 1; i < pts.length; i++) { L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); cum.push(L); }
      out.push({ pts, cum, L });
    }
    // lines that leave the screen on the S side: traced back from S against the field
    for (let deg = 120; deg <= 240; deg += 20) {
      const a0 = deg * Math.PI / 180; let p = [S[0] + 16 * Math.cos(a0), S[1] + 16 * Math.sin(a0)]; const pts = [p]; let ok = false;
      for (let i = 0; i < 2500; i++) {
        const b1 = Bf(...p), l1 = Math.hypot(...b1) || 1, mid = [p[0] - 2 * b1[0] / l1, p[1] - 2 * b1[1] / l1], b2 = Bf(...mid), l2 = Math.hypot(...b2) || 1;
        p = [p[0] - 4 * b2[0] / l2, p[1] - 4 * b2[1] / l2]; pts.push(p);
        if (Math.hypot(p[0] - N[0], p[1] - N[1]) < 16) break;
        if (p[0] < -40 || p[0] > VW + 40 || p[1] < 60 || p[1] > VH + 40) { ok = true; break; }
      }
      if (!ok) continue;
      pts.reverse(); let L = 0; const cum = [0]; for (let i = 1; i < pts.length; i++) { L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); cum.push(L); }
      out.push({ pts, cum, L });
    }
    return out;
  }
  add('magnet', { title: 'Field lines leave the N pole of a bar magnet and curve round into the S pole.', still: 0.5,
    draw(T, fig, t) {
      magLines = magLines || traceLines();
      let s = `<rect width="${VW}" height="${VH}" fill="${T.outline ? T.bg : '#F4F1EA'}"/>`;
      for (const ln of magLines) s += `<path d="M${ln.pts.filter((_, i) => i % 3 === 0).map(q => `${F(q[0])},${F(q[1])}`).join('L')}" fill="none" stroke="#8C96A8" stroke-width="3"/>`;
      for (const ln of magLines) for (let k = 0; k < Math.floor(ln.L / 160) + 1; k++) {
        const dd = (k * 160 + t * 70) % ln.L; let i = 1; while (i < ln.cum.length - 1 && ln.cum[i] < dd) i++;
        const q = ln.pts[i], q0 = ln.pts[i - 1], u = Math.atan2(q[1] - q0[1], q[0] - q0[0]) * 180 / Math.PI;
        s += `<path d="M10,0 L-8,-7 L-8,7Z" fill="#3E4A5E" transform="translate(${F(q[0])},${F(q[1])}) rotate(${F(u)})"/>`;
      }
      s += `<rect x="640" y="525" width="160" height="70" rx="8" fill="#2F80ED"/><rect x="800" y="525" width="160" height="70" rx="8" fill="#E4572E"/>` +
        words(720, 576, 'S', T, { size: 40, weight: 700, anchor: 'middle', color: '#ffffff', halo: false }) + words(880, 576, 'N', T, { size: 40, weight: 700, anchor: 'middle', color: '#ffffff', halo: false });
      // compasses line up with the field (needle N end along B)
      for (const [cx, cy] of [[300, 330], [800, 300], [1300, 330], [260, 790], [800, 820], [1340, 790], [460, 560], [1140, 560]]) {
        const b = Bf(cx, cy), ang = Math.atan2(b[1], b[0]) * 180 / Math.PI;
        s += `<circle cx="${cx}" cy="${cy}" r="34" fill="#ffffff" stroke="#5D6470" stroke-width="4"/><g transform="translate(${cx},${cy}) rotate(${F(ang)})"><path d="M26,0 L0,-7 L0,7Z" fill="#E4572E"/><path d="M-26,0 L0,-7 L0,7Z" fill="#9AA5B1"/></g><circle cx="${cx}" cy="${cy}" r="4" fill="#2b2522"/>`;
      }
      s += words(48, 960, 'compass needles (red end = north-seeking) point along the field lines  ·  lines are closest at the poles, where the field is strongest', T, { size: 22, color: T.muted });
      return s + quote(this.title, T);
    } });

  // ---------- the Moon's phases ----------
  add('moonphases', { title: 'The Moon is always half lit by the Sun; as it goes round the Earth we see more or less of that half.', still: 3.0,
    draw(T, fig, t) {
      let s = `<rect width="${VW}" height="${VH}" fill="#121A33"/>`;
      for (let i = 0; i < 60; i++) s += circ([hash(i) * VW, hash(i + 3) * VH], 1.2 + hash(i + 7) * 1.8, '#ffffff', `opacity="${F(0.3 + 0.6 * hash(i + 1))}"`);
      for (let i = 0; i < 6; i++) s += arrow(20, 200 + i * 120, 130, 200 + i * 120, '#FFD54F', '', T, { w: 5 });
      s += words(30, 160, 'sunlight', T, { size: 26, weight: 700, color: '#FFD54F', halo: false });
      const E = [620, 560], R = 270, r = 26, lit = '#F4F1DE', dark = '#3A4258';
      s += `<circle cx="${E[0]}" cy="${E[1]}" r="${R}" fill="none" stroke="#56607A" stroke-width="3" stroke-dasharray="6 10"/>`;
      s += circ(E, 62, '#1F3A6B') + `<path d="M${E[0]},${E[1] - 62} A62,62 0 0 0 ${E[0]},${E[1] + 62}Z" fill="#3D8BD1"/>` + words(E[0], E[1] + 100, 'Earth', T, { size: 24, anchor: 'middle', color: '#ffffff', halo: false });
      const seen = (c, rr, th) => {   // the Moon as seen from Earth at orbit angle th (0 = new, between Earth and Sun)
        const k = ((th % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI), rx = rr * Math.abs(Math.cos(k)), top = `${F(c[0])},${F(c[1] - rr)}`, bot = `${F(c[0])},${F(c[1] + rr)}`;
        const wax = k < Math.PI, cres = Math.cos(k) > 0;
        const d = wax ? `M${top} A${rr},${rr} 0 0 1 ${bot} A${F(rx)},${rr} 0 0 ${cres ? 0 : 1} ${top}Z` : `M${top} A${rr},${rr} 0 0 0 ${bot} A${F(rx)},${rr} 0 0 ${cres ? 1 : 0} ${top}Z`;
        return circ(c, rr, dark) + `<path d="${d}" fill="${lit}"/>`;
      };
      const names = ['new moon', 'waxing crescent', 'first quarter', 'waxing gibbous', 'full moon', 'waning gibbous', 'last quarter', 'waning crescent'];
      for (let i = 0; i < 8; i++) {
        const th = i * Math.PI / 4, p = [E[0] - R * Math.cos(th), E[1] + R * Math.sin(th)], o = [E[0] - (R + 78) * Math.cos(th), E[1] + (R + 78) * Math.sin(th)];
        s += circ(p, r, dark) + `<path d="M${F(p[0])},${F(p[1] - r)} A${r},${r} 0 0 0 ${F(p[0])},${F(p[1] + r)}Z" fill="${lit}"/>`;
        s += seen(o, 22, th) + circ(o, 22, 'none', 'stroke="#56607A" stroke-width="2"');
      }
      const th = (t * 0.32) % (2 * Math.PI), p = [E[0] - R * Math.cos(th), E[1] + R * Math.sin(th)];
      s += circ(p, r + 10, 'none', 'stroke="#FFD54F" stroke-width="5"');
      s += line(E, p, 2, '#FFD54F', 'stroke-dasharray="6 8" opacity="0.7"');
      const nm = names[Math.round(th / (Math.PI / 4)) % 8];
      s += `<rect x="1080" y="230" width="440" height="470" rx="22" fill="#1C2647"/>` + words(1300, 290, 'seen from Earth now', T, { size: 26, anchor: 'middle', color: '#C9D1E8', halo: false });
      s += seen([1300, 470], 130, th) + words(1300, 660, nm, T, { size: 34, weight: 700, anchor: 'middle', color: '#ffffff', halo: false });
      s += words(48, 960, 'inner ring: the Moon from space (sunlit half towards the Sun)  ·  outer ring: what we see from Earth  ·  not to scale', T, { size: 22, color: '#C9D1E8', halo: false });
      return s + words(48, 66, '“' + this.title + '”', T, { size: 28, color: '#E6E9F2', weight: 400, halo: false });
    } });
}
