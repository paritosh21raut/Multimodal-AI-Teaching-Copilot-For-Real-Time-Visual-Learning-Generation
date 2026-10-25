// V2 2D samples, part 4: more scenes in the explainer style — a cast line-up, animals, several people at once, and
// harder topics (relative velocity, refraction, apparent weight, cycles, processes, circuits, orbits).
// Numbers: none are printed unless a constant (with its tag) — the sentences give none; motion is illustrative.
export function install(K) {
  const { VW, VH, JI, sample, natSpeed, F, line, circ, lerp, shade, hash, words, label, arrow, badge, quote, card, sky, hills, ground, view, SCENES, ORDER } = K;
  const P = (p, V, T, fig) => K.person(p, V, T, fig);
  const who = n => ({ cast: n, look: K.LOOK[n] });
  const outdoor = (T, V, id) => (T.outline ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, id) + hills(T, V.gy)) + ground(T, V);
  const toWorld = (V, px, py) => [(px - VW / 2) / V.s + V.cx, (V.gy - py) / V.s];
  const add = (name, sc) => { SCENES[name] = sc; ORDER.push(name); };
  const H = c => (K.CAST[c].child ? 1.25 : K.CAST[c].sex === 'f' ? 1.66 : 1.78);

  add('closeup', { title: 'Close-up: four people, to judge faces, hair and clothes.', still: 0.9,
    draw(T, fig, t) {
      const V = view(360, 0, 940);
      let s = T.outline ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, 'skyCU', '#D6ECF3', '#F3F1E8');
      s += ground(T, V, { color: T.outline ? null : '#BFD9A8' });
      [['man', 'Idle_Talking_Loop', 1], ['woman3', 'Walk_Loop', 1], ['man2', 'Idle_FoldArms_Loop', -1], ['woman2', 'Idle_Loop', -1]].forEach(([c, clip, d], i) => {
        s += P({ ...who(c), clip, t: t + i * 0.5, x: -1.6 + i * 1.05, dir: d, h: H(c) }, V, T, fig);
      });
      return s + quote(this.title, T);
    } });

  add('animalsclose', { title: 'Close-up: a dog walking, a cat sitting, a horse trotting.', still: 0.7,
    draw(T, fig, t) {
      const V = view(330, 0, 900);
      let s = outdoor(T, V, 'skyAC');
      s += K.animal({ kind: 'dog', x: -1.7, t, speed: 1.2, dir: 1 }, V, T);
      s += K.animal({ kind: 'cat', x: -0.55, t, pose: 'sit', dir: -1 }, V, T);
      s += K.animal({ kind: 'horse', x: 1.25, t, speed: 1.8, dir: 1, scale: 0.85 }, V, T);
      return s + quote(this.title, T);
    } });

  add('cast', { title: 'Ten people, ten motions (the same motion clips drive every style).', still: 0.8,
    draw(T, fig, t) {
      const V = view(140, 0, 870);
      let s = outdoor(T, V, 'skyC');
      const L = [['man', 'Walk_Loop', 1, 'walk'], ['woman', 'Idle_Talking_Loop', 1, 'talk'], ['man2', 'Idle_FoldArms_Loop', -1, 'arms folded'],
        ['man3', 'Jog_Fwd_Loop', 1, 'jog'], ['woman2', 'Idle_Loop', 1, 'stand'], ['boy', 'Jump_Loop', 1, 'jump'], ['girl', 'Walk_Loop', 1, 'walk'],
        ['elder', 'Walk_Formal_Loop', 1, 'walk, cane'], ['woman3', 'Idle_TalkingPhone_Loop', 1, 'phone'], ['elderw', 'Idle_Loop', -1, 'stand']];
      L.forEach(([c, clip, d, tag], i) => {
        const x = -5.0 + i * 1.1, y = clip === 'Jump_Loop' ? 0.35 * Math.abs(Math.sin(t * 2.6)) : 0;
        s += P({ ...who(c), clip, t: t + i * 0.37, x, y, dir: d, h: H(c), cane: c === 'elder' }, V, T, fig);
        s += words(V.sx(x), V.gy + 46, tag, T, { size: 20, anchor: 'middle', color: T.muted });
      });
      return s + quote(this.title, T);
    } });

  add('animals', { title: 'A horse, a cow, a dog, a cat, birds and a fish.', still: 0.6,
    draw(T, fig, t) {
      const V = view(150, 0, 830);
      let s = outdoor(T, V, 'skyA');
      s += `<path d="M1270,${V.gy + 20} Q1430,${V.gy + 5} 1590,${V.gy + 20} L1590,980 Q1430,995 1270,980Z" fill="${T.outline ? 'rgba(31,111,209,0.12)' : '#6FB7E0'}" stroke="${T.outline ? T.ink : 'none'}" stroke-width="3"/>`;
      s += K.animal({ kind: 'horse', x: -3.9, t, speed: 1.6, dir: 1 }, V, T);
      s += K.animal({ kind: 'cow', x: -1.0, t, speed: 0, dir: 1 }, V, T);
      s += K.animal({ kind: 'dog', x: 1.3, t, speed: 1.3, dir: 1 }, V, T);
      s += K.animal({ kind: 'cat', x: 2.85, t, pose: 'sit', dir: -1 }, V, T);
      s += K.animal({ kind: 'bird', x: 0.8 + 0.5 * Math.sin(t), y: 3.0 + 0.15 * Math.sin(t * 2), t, pose: 'fly', dir: 1, scale: 1.6 }, V, T);
      s += K.animal({ kind: 'bird', x: -2.6, y: 0.15, t: 0, pose: 'stand', dir: -1, color: '#9C6B4E', scale: 1.4 }, V, T);
      s += K.animal({ kind: 'fish', x: 4.3 + 0.3 * Math.sin(t * 0.8), y: -0.55, t, dir: Math.cos(t * 0.8) > 0 ? 1 : -1, scale: 1.5 }, V, T);
      return s + quote(this.title, T);
    } });

  add('park', { title: 'A man walks his dog in the park; a girl sits on a bench with her cat.', still: 2.2,
    draw(T, fig, t) {
      const V = view(130, 0, 880), v = natSpeed('Walk_Loop') * 1.78, x = -7 + ((v * t) % 13), fr = sample('Walk_Loop', t);
      let s = outdoor(T, V, 'skyP');
      if (!T.outline) s += `<rect y="${V.gy}" width="${VW}" height="36" fill="#D9C9A6"/>`;
      s += K.tree(V, -3.6, 5, T) + K.tree(V, 5.2, 4.2, T);
      // bench + girl sitting on it
      const gf = sample('Sitting_Idle_Loop', t), gh = 1.25, seat = Math.min(gf[JI.thigh_l][1], gf[JI.thigh_r][1]) * gh - 0.06;
      const bx = 2.6, wood = T.outline ? T.fill : '#A0673F';
      s += `<rect x="${F(V.sx(bx - 0.75))}" y="${F(V.sy(seat))}" width="${F(1.5 * V.s)}" height="${F(0.07 * V.s)}" rx="4" fill="${wood}"/>` +
        `<rect x="${F(V.sx(bx - 0.75))}" y="${F(V.sy(seat + 0.5))}" width="${F(1.5 * V.s)}" height="${F(0.07 * V.s)}" rx="4" fill="${wood}" transform="translate(0,0)"/>` +
        [-0.6, 0.6].map(u => `<rect x="${F(V.sx(bx + u) - 4)}" y="${F(V.sy(seat))}" width="8" height="${F(seat * V.s)}" fill="${shade(wood, 0.8)}"/>`).join('');
      s += P({ ...who('girl'), fr: gf, x: bx + 0.12, dir: -1, h: gh }, V, T, fig);
      s += K.animal({ kind: 'cat', x: bx + 1.15, t, pose: 'sit', dir: -1 }, V, T);
      s += K.animal({ kind: 'bird', x: 7 - ((1.6 * t) % 14), y: 3.4 + 0.2 * Math.sin(t * 2), t, pose: 'fly', dir: -1, scale: 1.5 }, V, T);
      // man + dog on a leash, the dog ahead at the same speed
      const dx = x + 1.35, hand = [V.sx(x + fr[JI.hand_r][0] * 1.78), V.sy(fr[JI.hand_r][1] * 1.78)], col = [V.sx(dx + 0.31), V.sy(0.52)];
      s += K.animal({ kind: 'dog', x: dx, t, speed: v, dir: 1 }, V, T);
      s += P({ ...who('man'), fr, x, dir: 1 }, V, T, fig);
      s += `<path d="M${F(hand[0])},${F(hand[1])} Q${F((hand[0] + col[0]) / 2)},${F(Math.max(hand[1], col[1]) + 30)} ${F(col[0])},${F(col[1])}" fill="none" stroke="#C0392B" stroke-width="3"/>`;
      return s + quote(this.title, T);
    } });

  add('tug', { title: 'Tug of war: the left team pulls harder, so the rope moves left.', still: 4.5,
    draw(T, fig, t) {
      const V = view(150, 0, 860), ry = 1.0, c = -0.5 * Math.min(1, (t % 9) / 6);
      let s = outdoor(T, V, 'skyT2');
      s += line([V.sx(0), V.gy + 4], [V.sx(0), V.gy + 60], 5, T.outline ? T.ink : '#ffffff', 'stroke-dasharray="10 8"');
      s += line([V.sx(c - 3.6), V.sy(ry)], [V.sx(c + 3.6), V.sy(ry)], 9, '#C8A165');
      const team = [['man', -1.0], ['man3', -1.9], ['woman3', -2.8], ['man2', 1.0], ['woman', 1.9], ['woman2', 2.8]];
      team.forEach(([cn, off], i) => {
        const d = off < 0 ? 1 : -1, x = c + off, base = sample('Push_Loop', t * 0.7 + i * 0.6);
        const fr = base.map(q => [-q[0] - 0.08, q[1], q[2]]); fr.clip = 'Push_Loop'; fr.tt = base.tt;
        const ik = { _r: [x + d * 0.62, ry], _l: [x + d * 0.48, ry] };
        s += P({ ...who(cn), fr, x, dir: d, h: H(cn), ik }, V, T, fig);
      });
      s += `<path d="M${F(V.sx(c))},${F(V.sy(ry))} l-14,40 l28,0Z" fill="#E4572E"/>`;
      s += arrow(V.sx(c) - 20, V.sy(2.4), V.sx(c) - 260, V.sy(2.4), T.applied, 'F_L', T, { lx: -60, ly: -14 });
      s += arrow(V.sx(c) + 20, V.sy(2.4), V.sx(c) + 170, V.sy(2.4), T.applied, 'F_R', T, { lx: 10, ly: -14 });
      s += arrow(V.sx(c) - 10, V.sy(2.0), V.sx(c) - 110, V.sy(2.0), T.friction, 'F_net', T, { lx: -110, ly: 44 });
      return s + quote(this.title, T) + badge(T);
    } });

  add('classroom', { title: 'The teacher explains at the board; three students listen.', still: 1.3,
    draw(T, fig, t) {
      const V = view(150, 0.2, 880);
      let s = T.outline ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : `<rect width="${VW}" height="${VH}" fill="#F3E9D8"/><rect y="${V.gy - 40}" width="${VW}" height="40" fill="#E6D3B5"/>`;
      s += ground(T, V, { color: T.outline ? null : '#C9A27E' });
      s += `<rect x="150" y="190" width="560" height="340" rx="10" fill="${T.outline ? '#ffffff' : '#FBFBF8'}" stroke="${T.outline ? T.ink : '#9C8B74'}" stroke-width="12"/>` +
        `<path d="M250,470 L600,470 L600,300Z" fill="none" stroke="#3B6EA8" stroke-width="5"/><rect x="420" y="352" width="56" height="44" fill="none" stroke="#C0392B" stroke-width="5" transform="rotate(-26 448 374)"/>`;
      s += P({ ...who('man3'), clip: 'Idle_Talking_Loop', t, x: -2.6, dir: 1 }, V, T, fig);
      [['woman', 0.2, 'Sitting_Talking_Loop'], ['boy', 2.2, 'Sitting_Idle_Loop'], ['girl', 4.1, 'Sitting_Idle_Loop']].forEach(([cn, x, clip], i) => {
        const h = H(cn), fr = sample(clip, t + i * 0.9), d = -1, seat = Math.min(fr[JI.thigh_l][1], fr[JI.thigh_r][1]) * h - 0.07, px = fr[JI.pelvis][0] * h;
        const wood = T.outline ? T.fill : '#8E5B3A', cx = x + d * px;
        s += `<rect x="${F(V.sx(cx - 0.22))}" y="${F(V.sy(seat))}" width="${F(0.48 * V.s)}" height="${F(0.06 * V.s)}" rx="3" fill="${wood}"/>` +
          `<rect x="${F(V.sx(cx + 0.24))}" y="${F(V.sy(seat + 0.5))}" width="${F(0.05 * V.s)}" height="${F((seat + 0.5) * V.s)}" rx="3" fill="${wood}"/>` +
          `<rect x="${F(V.sx(cx - 0.2))}" y="${F(V.sy(seat))}" width="${F(0.04 * V.s)}" height="${F(seat * V.s)}" fill="${shade(wood, 0.8)}"/>`;
        s += P({ ...who(cn), fr, x, dir: d, h }, V, T, fig);
        const top = seat + 0.3, dxk = x - 0.85;
        s += `<rect x="${F(V.sx(dxk - 0.35))}" y="${F(V.sy(top))}" width="${F(0.7 * V.s)}" height="${F(0.06 * V.s)}" rx="3" fill="${T.outline ? T.fill : '#B07A4F'}"/>` +
          `<rect x="${F(V.sx(dxk - 0.3))}" y="${F(V.sy(top))}" width="${F(0.05 * V.s)}" height="${F(top * V.s)}" fill="${shade(T.outline ? T.fill : '#B07A4F', 0.8)}"/>` +
          `<rect x="${F(V.sx(dxk + 0.1))}" y="${F(V.sy(top + 0.03))}" width="${F(0.2 * V.s)}" height="${F(0.03 * V.s)}" fill="#F2F2F2"/>`;
      });
      return s + quote(this.title, T);
    } });

  add('boat', { title: 'A boat heads straight across a river, but the current carries it downstream.', still: 5,
    draw(T, fig, t) {
      const top = 270, bot = 770, x0 = 470, vb = 58, vw = 40, cross = (bot - top) / vb, tt = t % (cross + 2), u = Math.min(tt, cross);
      const bx = x0 + vw * u, by = bot - vb * u, grass = T.outline ? T.bg : '#A9CF8E', water = T.outline ? 'rgba(31,111,209,0.10)' : '#5FA8D3';
      let s = `<rect width="${VW}" height="${VH}" fill="${grass}"/><rect y="${top}" width="${VW}" height="${bot - top}" fill="${water}"/>`;
      if (T.outline) s += line([0, top], [VW, top], 4, T.ink) + line([0, bot], [VW, bot], 4, T.ink);
      for (let i = 0; i < 26; i++) { const yy = top + 30 + hash(i) * (bot - top - 60), xx = ((hash(i + 5) * VW + t * 60) % (VW + 100)) - 50;
        s += line([xx, yy], [xx + 50, yy], 4, T.outline ? '#9fb7d6' : '#8CC3E3'); }
      for (let i = 0; i < 9; i++) { s += circ([hash(i + 30) * VW, 120 + hash(i + 40) * 110], 38 + hash(i) * 20, T.outline ? '#dfe9d6' : '#5E9F55'); s += circ([hash(i + 60) * VW, bot + 70 + hash(i + 70) * 120], 34 + hash(i + 2) * 22, T.outline ? '#dfe9d6' : '#5E9F55'); }
      s += line([x0, bot], [x0, top], 4, T.muted, 'stroke-dasharray="10 12" opacity="0.7"') + words(x0 - 20, top - 12, 'aimed', T, { size: 22, anchor: 'end', color: T.muted });
      s += line([x0, bot], [bx, by], 5, T.path, 'stroke-dasharray="4 10" stroke-linecap="round"');
      s += `<g transform="translate(${F(bx)},${F(by)})"><path d="M0,-58 C22,-30 22,30 16,44 L-16,44 C-22,30 -22,-30 0,-58Z" fill="${T.outline ? '#ffffff' : '#C0392B'}" stroke="${T.outline ? T.ink : '#8E2B20'}" stroke-width="4"/>` +
        `<circle cx="0" cy="8" r="13" fill="${T.outline ? T.fill : '#3E8E9E'}"/><circle cx="0" cy="6" r="8" fill="#E9B591"/></g>`;
      s += arrow(bx, by, bx, by - 130, T.weight, 'v_b', T, { lx: -70, ly: 10 });
      s += arrow(bx, by - 130, bx + 90, by - 130, T.water || '#1f6fd1', 'v_w', T, { lx: 14, ly: 10, dashed: true });
      s += arrow(bx, by, bx + 90, by - 130, T.applied, 'v', T, { lx: 6, ly: 70 });
      const xf = x0 + vw * cross;
      s += line([x0, top - 40], [xf, top - 40], 3, T.ink) + line([x0, top - 50], [x0, top - 30], 3, T.ink) + line([xf, top - 50], [xf, top - 30], 3, T.ink) + label((x0 + xf) / 2, top - 52, 'd', T.ink, T, 'middle', 36);
      s += words(1380, (top + bot) / 2, 'current →', T, { size: 30, color: T.outline ? T.water : '#ffffff', halo: T.outline });
      return s + quote(this.title, T) + badge(T, 'Illustrative · top view');
    } });

  add('refraction', { title: 'A fish in a pond looks closer to the surface than it really is.', still: 2,
    draw(T, fig, t) {
      const V = view(190, 0, 560), surf = 560, water0 = 640, bottom = 940;
      let s = T.outline ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, 'skyF', '#BFE3F2', '#F2F6EE');
      s += T.outline ? line([0, surf], [water0, surf], 4, T.groundLine) : `<rect y="${surf}" width="${water0 + 30}" height="${VH - surf}" fill="#8DBB6A"/><rect y="${surf + 26}" width="${water0 + 90}" height="${VH}" fill="#A07A55"/>`;
      s += `<path d="M${water0},${surf} L${VW},${surf} L${VW},${bottom} L${water0 + 70},${bottom} Z" fill="${T.outline ? 'rgba(31,111,209,0.12)' : '#4E9AD1'}" opacity="${T.outline ? 1 : 0.85}"/>`;
      if (!T.outline) s += `<rect x="${water0}" y="${bottom}" width="${VW}" height="${VH - bottom}" fill="#A07A55"/>`;
      const gx = -2.6, fr = sample('Idle_Loop', t), eye = [V.sx(gx + fr[JI.Head][0] * 1.66) + 12, V.sy(fr[JI.Head][1] * 1.66 + 0.07)];
      const fish = [1210 + 70 * Math.sin(t * 0.5), 860];
      // the surface point where light from the fish leaves the water towards the eye (Snell, n = 1.33)
      const g = sx => 1.33 * Math.sin(Math.atan(Math.abs(fish[0] - sx) / (fish[1] - surf))) - Math.sin(Math.atan(Math.abs(sx - eye[0]) / (surf - eye[1])));
      let lo = eye[0], hi = fish[0]; for (let i = 0; i < 40; i++) { const m = (lo + hi) / 2; if (g(m) > 0) lo = m; else hi = m; }
      const S = [(lo + hi) / 2, surf], yApp = surf + (fish[0] - S[0]) * (surf - eye[1]) / (S[0] - eye[0]);
      s += P({ ...who('woman3'), fr, x: gx, dir: 1 }, V, T, fig);
      const fw = toWorld(V, fish[0], fish[1]), aw = toWorld(V, fish[0], yApp);
      s += `<g opacity="0.38">${K.animal({ kind: 'fish', x: aw[0], y: aw[1], t, dir: -1, scale: 1.6 }, V, T)}</g>`;
      s += K.animal({ kind: 'fish', x: fw[0], y: fw[1], t, dir: -1, scale: 1.6 }, V, T);
      s += line([S[0], surf - 170], [S[0], surf + 230], 3, T.muted, 'stroke-dasharray="8 8"');
      const light = T.outline ? '#C77700' : '#FFD23F';
      s += arrow(fish[0] - 30, fish[1] - 8, (S[0] + fish[0] - 30) / 2, (surf + fish[1] - 8) / 2, light, '', T, { w: 6 }) + line([fish[0] - 30, fish[1] - 8], S, 6, light);
      s += arrow(S[0], S[1], (S[0] + eye[0]) / 2, (S[1] + eye[1]) / 2, light, '', T, { w: 6 }) + line(S, eye, 6, light);
      s += line(S, [fish[0], yApp], 3, T.outline ? T.muted : '#ffffff', 'stroke-dasharray="10 8"');
      s += label(S[0] + 26, surf + 110, 'i', T.ink, T, 'start', 36) + label(S[0] - 44, surf - 70, 'r', T.ink, T, 'start', 36);
      s += words(fish[0] + 70, fish[1] + 40, 'real fish', T, { size: 26, weight: 600 }) + words(fish[0] + 70, yApp - 6, 'where it seems to be', T, { size: 26, weight: 600, color: T.muted });
      s += card(980, 110, [['n_water', '1.33']], 'constant', T, 330);
      return s + quote(this.title, T);
    } });

  add('lift', { title: 'In a lift speeding up on its way up, you press harder on the scale.', still: 1.6,
    draw(T, fig, t) {
      const V = view(165, 0, 800), tt = t % 4, rise = 0.5 * 0.9 * tt * tt;
      let s = `<rect width="${VW}" height="${VH}" fill="${T.outline ? T.bg : '#D9DEE6'}"/>`;
      for (let k = -1; k < 6; k++) { const y = V.gy + 60 + ((k * 3.2 + rise) % 16) * V.s - 4 * V.s; s += `<rect x="0" y="${F(y)}" width="${VW}" height="10" fill="${T.outline ? '#e1dbcf' : '#C5CCD6'}"/>`; }
      s += line([520, 0], [520, VH], 8, T.outline ? T.ink : '#8A93A3') + line([1080, 0], [1080, VH], 8, T.outline ? T.ink : '#8A93A3');
      const ceil = V.sy(2.45);
      s += line([800, 0], [800, ceil], 6, '#5D6470') + `<rect x="560" y="${F(ceil)}" width="480" height="${F(V.gy - ceil + 18)}" rx="10" fill="${T.outline ? '#ffffff' : '#F5EEDF'}" stroke="${T.outline ? T.ink : '#9C8B74'}" stroke-width="8"/>`;
      s += `<rect x="${F(V.sx(-0.32))}" y="${F(V.sy(0.12))}" width="${F(0.64 * V.s)}" height="${F(0.12 * V.s)}" rx="6" fill="${T.outline ? T.fill : '#7F8C9A'}"/>`;
      const nd = 0.35 + 0.25 * Math.min(1, tt), dc = [V.sx(0), V.sy(0.06)];
      s += `<circle cx="${dc[0]}" cy="${dc[1]}" r="12" fill="#ffffff"/>` + line(dc, [dc[0] + 11 * Math.sin(nd), dc[1] - 11 * Math.cos(nd)], 2.5, '#C0392B');
      s += P({ ...who('man'), clip: 'Idle_Loop', t, x: -0.05, y: 0.12, dir: 1 }, V, T, fig);
      const fx = V.sx(0.42);
      s += arrow(fx, V.sy(0.14), fx, V.sy(0.14) - 260, T.normal, 'N', T, { lx: 12, ly: 20 });
      s += arrow(fx + 70, V.sy(1.0), fx + 70, V.sy(1.0) + 165, T.weight, 'mg', T, { lx: 10, ly: 8 });
      s += arrow(1150, 620, 1150, 420, T.vel, 'a', T, { lx: 14, ly: 20 });
      s += `<rect x="1150" y="130" width="410" height="190" rx="18" fill="${T.card}"/>` + words(1175, 180, 'speeding up, going up:', T, { size: 28, weight: 600 }) +
        label(1175, 240, 'N = mg + ma', T.ink, T, 'start', 38) + label(1175, 295, 'N > mg', T.normal, T, 'start', 38);
      return s + quote(this.title, T) + badge(T);
    } });

  add('watercycle', { title: 'The water cycle: evaporation, condensation, precipitation, collection.', still: 2,
    draw(T, fig, t) {
      const ol = T.outline;
      let s = ol ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, 'skyW', '#9FD3EE', '#E8F4F7');
      s += circ([190, 170], 70, ol ? '#ffffff' : '#FFD23F', ol ? `stroke="${T.ink}" stroke-width="4"` : '');
      for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 + t * 0.2; s += line([190 + Math.cos(a) * 88, 170 + Math.sin(a) * 88], [190 + Math.cos(a) * 118, 170 + Math.sin(a) * 118], 6, ol ? T.ink : '#FFC21A'); }
      s += `<path d="M640,700 L900,360 L1060,520 L1240,300 L1600,640 L1600,1000 L640,1000Z" fill="${ol ? T.fill : '#7DAE6A'}" stroke="${ol ? T.ink : 'none'}" stroke-width="4"/>`;
      s += `<path d="M1190,365 L1240,300 L1292,362 L1262,352 L1240,370 L1215,352Z" fill="#ffffff"/><path d="M860,412 L900,360 L942,402 L915,396 L900,410Z" fill="#ffffff"/>`;
      s += `<path d="M0,680 Q330,660 660,690 L700,1000 L0,1000Z" fill="${ol ? 'rgba(31,111,209,0.14)' : '#3D8BD1'}" stroke="${ol ? T.ink : 'none'}" stroke-width="4"/>`;
      for (let i = 0; i < 6; i++) s += `<path d="M${40 + i * 105},${720 + (i % 2) * 30} q22,-14 44,0 t44,0" fill="none" stroke="${ol ? '#7aa7d9' : '#8FC1EC'}" stroke-width="4"/>`;
      s += `<path d="M1180,560 C1050,620 980,610 900,680 S760,740 650,742" fill="none" stroke="${ol ? T.water : '#4FA3EE'}" stroke-width="16" stroke-linecap="round"/>` +
        `<path d="M1180,560 C1050,620 980,610 900,680 S760,740 650,742" fill="none" stroke="#ffffff" stroke-width="3" stroke-dasharray="14 20" stroke-dashoffset="${F(t * 40)}" opacity="0.8"/>`;
      for (let i = 0; i < 18; i++) { const ph = (t * 0.35 + hash(i)) % 1, x = 140 + hash(i + 9) * 420 + Math.sin(ph * 12 + i) * 10, y = 660 - ph * 380; s += circ([x, y], 6, ol ? T.water : '#ffffff', `opacity="${F(0.9 * (1 - ph))}"`); }
      const cloud = (cx, cy, k, fill) => [[-60, 10, 48], [0, -12, 62], [62, 8, 46], [-20, 26, 40], [30, 28, 40]].map(([u, v, r]) => circ([cx + u * k, cy + v * k], r * k, fill, ol ? `stroke="${T.ink}" stroke-width="3"` : '')).join('');
      s += cloud(560, 250, 1.0, ol ? '#ffffff' : '#F4F7FA');
      const cx2 = 1120 + 40 * Math.sin(t * 0.3);
      s += cloud(cx2, 200, 1.25, ol ? '#ffffff' : '#C9D3DE');
      for (let i = 0; i < 26; i++) { const rx = cx2 - 120 + hash(i + 3) * 240, ph = (t * 1.3 + hash(i + 11)) % 1, y = 270 + ph * 220; s += line([rx, y], [rx - 6, y + 26], 4, ol ? T.water : '#3D7CC9'); }
      s += arrow(470, 520, 470, 330, T.applied, '', T, { w: 8 }) + words(300, 600, 'evaporation', T, { size: 30, weight: 700 });
      s += arrow(680, 210, 930, 190, T.applied, '', T, { w: 8 }) + words(580, 150, 'condensation', T, { size: 30, weight: 700 });
      s += words(1300, 470, 'precipitation', T, { size: 30, weight: 700 });
      s += arrow(860, 700, 720, 760, T.applied, '', T, { w: 8 }) + words(820, 820, 'collection', T, { size: 30, weight: 700 });
      return s + quote(this.title, T);
    } });

  add('photosynthesis', { title: 'A leaf uses sunlight to make food from carbon dioxide and water, giving out oxygen.', still: 2,
    draw(T, fig, t) {
      const ol = T.outline, gy = 800, green = ol ? '#dfe9d6' : '#4E9F5A', st = ol ? `stroke="${T.ink}" stroke-width="4"` : '';
      let s = ol ? `<rect width="${VW}" height="${VH}" fill="${T.bg}"/>` : sky(T, 'skyPh', '#CDEBF5', '#F4F7EC');
      s += `<rect y="${gy}" width="${VW}" height="${VH - gy}" fill="${ol ? T.bg : '#8A6142'}"/>` + (ol ? line([0, gy], [VW, gy], 4, T.groundLine) : '');
      for (let i = 0; i < 7; i++) s += `<path d="M700,${gy + 5} q${(i - 3) * 40},60 ${(i - 3) * 70},${120 + (i % 2) * 40}" fill="none" stroke="${ol ? T.ink : '#E8D6B5'}" stroke-width="5"/>`;
      s += `<path d="M690,${gy} C680,650 700,520 700,330 L720,330 C720,520 700,650 712,${gy}Z" fill="${ol ? T.fill : '#3F8A4B'}" ${st}/>`;
      s += `<path d="M710,520 C820,400 1050,380 1180,430 C1060,520 860,580 710,540Z" fill="${green}" ${st}/>` + line([712, 530], [1150, 432], 4, ol ? T.ink : '#2F6F3A');
      s += `<path d="M700,620 C620,560 470,560 400,600 C480,650 620,660 700,640Z" fill="${green}" ${st}/>`;
      s += `<path d="M710,340 C760,260 860,240 920,260 C870,320 780,350 710,360Z" fill="${green}" ${st}/>`;
      s += circ([200, 170], 75, ol ? '#ffffff' : '#FFD23F', ol ? st : '');
      for (let i = 0; i < 4; i++) { const y0 = 220 + i * 40; s += `<line x1="${270 + i * 10}" y1="${y0}" x2="${900 + i * 50}" y2="${420 + i * 18}" stroke="${ol ? '#C77700' : '#FFC21A'}" stroke-width="6" stroke-dasharray="26 18" stroke-dashoffset="${F(-t * 80)}"/>`; }
      for (let i = 0; i < 5; i++) { const ph = (t * 0.25 + i / 5) % 1, x = 1500 - ph * 420, y = 300 + i * 40 + ph * 40;
        s += circ([x - 22, y], 11, '#D9443A') + circ([x, y], 13, '#3C3C3C') + circ([x + 22, y], 11, '#D9443A'); }
      s += words(1320, 270, 'CO₂ in', T, { size: 30, weight: 700 });
      for (let i = 0; i < 4; i++) { const ph = (t * 0.25 + i / 4) % 1, x = 760 - ph * 260, y = 440 - ph * 260 - i * 10; s += circ([x - 10, y], 11, '#D9443A', `opacity="${F(1 - ph * 0.6)}"`) + circ([x + 10, y], 11, '#D9443A', `opacity="${F(1 - ph * 0.6)}"`); }
      s += words(450, 170, 'O₂ out', T, { size: 30, weight: 700 });
      for (let i = 0; i < 6; i++) { const ph = (t * 0.3 + i / 6) % 1, y = gy + 90 - ph * 380; s += `<path d="M706,${F(y - 9)} q8,10 0,16 q-8,-6 0,-16Z" fill="#3D8BD1"/>`; }
      s += words(470, gy + 50, 'water from the roots', T, { size: 26, weight: 600, color: ol ? T.ink : '#ffffff', halo: ol });
      s += words(900, 520, 'glucose made here', T, { size: 26, weight: 700, color: ol ? T.ink : '#1E4D2B' });
      s += `<rect x="330" y="905" width="940" height="66" rx="33" fill="${T.card}"/>` + words(800, 948, 'carbon dioxide + water  →  glucose + oxygen   (needs light)', T, { size: 28, anchor: 'middle', weight: 600 });
      return s + quote(this.title, T);
    } });

  add('circuit', { title: 'Close the switch: electrons flow round the circuit and the bulb lights.', still: 1,
    draw(T, fig, t) {
      const ol = T.outline;
      let s = `<rect width="${VW}" height="${VH}" fill="${ol ? T.bg : '#EFE8DA'}"/>`;
      const loop = [[330, 640], [330, 760], [1250, 760], [1250, 380], [800, 250], [330, 250], [330, 400]];
      const wire = 'M' + loop.map(p => p.join(',')).join('L');
      s += `<path d="${wire}" fill="none" stroke="${ol ? T.ink : '#B5652B'}" stroke-width="12" stroke-linejoin="round"/>`;
      s += `<rect x="270" y="400" width="120" height="240" rx="18" fill="${ol ? '#ffffff' : '#2F3238'}" ${ol ? `stroke="${T.ink}" stroke-width="5"` : ''}/><rect x="270" y="400" width="120" height="70" rx="18" fill="${ol ? T.fill : '#E4572E'}"/><rect x="305" y="380" width="50" height="24" rx="5" fill="#9AA0A6"/>` +
        words(330, 450, '+', T, { size: 44, anchor: 'middle', weight: 700, color: '#ffffff', halo: false }) + words(330, 610, '−', T, { size: 44, anchor: 'middle', weight: 700, color: ol ? T.ink : '#ffffff', halo: false }) + words(180, 530, 'cell', T, { size: 28, weight: 600 });
      s += `<circle cx="680" cy="250" r="14" fill="#555"/><circle cx="880" cy="250" r="14" fill="#555"/>` + line([680, 250], [880, 250], 12, ol ? T.ink : '#6B7280') + words(780, 210, 'switch (closed)', T, { size: 26, anchor: 'middle', weight: 600 });
      const glow = 0.75 + 0.25 * Math.sin(t * 5);
      s += `<circle cx="1250" cy="520" r="${F(130 * glow)}" fill="#FFE27A" opacity="0.35"/><circle cx="1250" cy="520" r="78" fill="${ol ? '#ffffff' : '#FFF3B0'}" stroke="${ol ? T.ink : '#C9A227'}" stroke-width="5"/>` +
        `<path d="M1222,560 q14,-50 28,0 q14,-50 28,0" fill="none" stroke="#E08A00" stroke-width="5"/><rect x="1222" y="596" width="56" height="44" rx="6" fill="#9AA0A6"/>` +
        words(1360, 450, 'bulb', T, { size: 28, weight: 600 });
      // electrons: from the − end, round the circuit, back into +
      const segs = []; let total = 0; for (let i = 0; i < loop.length - 1; i++) { const l = Math.hypot(loop[i + 1][0] - loop[i][0], loop[i + 1][1] - loop[i][1]); segs.push(l); total += l; }
      const at = dd => { let r = ((dd % total) + total) % total; for (let i = 0; i < segs.length; i++) { if (r <= segs[i]) return lerp(loop[i], loop[i + 1], r / segs[i]); r -= segs[i]; } return loop[0]; };
      for (let i = 0; i < 26; i++) { const p = at(i * total / 26 + t * 90); s += circ(p, 11, '#2F80ED') + words(p[0], p[1] + 7, '−', T, { size: 20, anchor: 'middle', weight: 700, color: '#ffffff', halo: false }); }
      s += arrow(520, 205, 640, 205, T.friction, 'I', T, { lx: 10, ly: 10 }) + words(520, 820, 'electrons flow from − to +   ·   current I is drawn from + to −', T, { size: 26, color: T.muted });
      return s + quote(this.title, T);
    } });

  add('orbit', { title: 'The Earth goes round the Sun; the Moon goes round the Earth.', still: 1.5,
    draw(T, fig, t) {
      let s = `<rect width="${VW}" height="${VH}" fill="#11162B"/>`;
      for (let i = 0; i < 90; i++) s += circ([hash(i) * VW, hash(i + 3) * VH], 1 + hash(i + 7) * 2, '#ffffff', `opacity="${F(0.4 + hash(i + 9) * 0.6)}"`);
      const sc = [760, 520], th = t * 0.35, e = [sc[0] + 560 * Math.cos(th), sc[1] + 230 * Math.sin(th)];
      s += `<ellipse cx="${sc[0]}" cy="${sc[1]}" rx="560" ry="230" fill="none" stroke="#7C88B8" stroke-width="3" stroke-dasharray="10 12"/>`;
      const sun = `<defs><radialGradient id="sunG"><stop offset="0.55" stop-color="#FFD23F"/><stop offset="1" stop-color="#FFD23F" stop-opacity="0"/></radialGradient></defs><circle cx="${sc[0]}" cy="${sc[1]}" r="190" fill="url(#sunG)"/><circle cx="${sc[0]}" cy="${sc[1]}" r="105" fill="#FFC21A"/>`;
      const ang = Math.atan2(sc[1] - e[1], sc[0] - e[0]) * 180 / Math.PI, ph = t * 2.2, m = [e[0] + 90 * Math.cos(ph), e[1] + 40 * Math.sin(ph)];
      const body = (c, r, fill, a) => circ(c, r, fill) + `<path d="M${F(c[0])},${F(c[1] - r)} A${F(r)},${F(r)} 0 0 0 ${F(c[0])},${F(c[1] + r)}Z" fill="rgba(0,0,20,0.55)" transform="rotate(${F(a)} ${F(c[0])} ${F(c[1])})"/>`;
      const earth = `<ellipse cx="${F(e[0])}" cy="${F(e[1])}" rx="90" ry="40" fill="none" stroke="#7C88B8" stroke-width="2" stroke-dasharray="6 8"/>` +
        circ(e, 40, '#2F80ED') + `<path d="M${F(e[0] - 18)},${F(e[1] - 20)} q20,-10 30,6 q-6,18 -26,14Z M${F(e[0] + 4)},${F(e[1] + 10)} q16,0 18,16 q-14,6 -22,-6Z" fill="#4CAF50"/>` +
        `<path d="M${F(e[0])},${F(e[1] - 40)} A40,40 0 0 0 ${F(e[0])},${F(e[1] + 40)}Z" fill="rgba(0,0,20,0.55)" transform="rotate(${F(ang)} ${F(e[0])} ${F(e[1])})"/>` +
        line([e[0] - 22, e[1] - 56], [e[0] + 22, e[1] + 56], 3, '#ffffff', 'opacity="0.8"');
      const moon = body(m, 13, '#C9CCD3', Math.atan2(sc[1] - m[1], sc[0] - m[0]) * 180 / Math.PI);
      s += (e[1] < sc[1] ? earth + moon + sun : sun + earth + moon);
      s += words(sc[0], sc[1] + 160, 'Sun', T, { size: 30, anchor: 'middle', weight: 700, color: '#ffffff', halo: false }) +
        words(e[0], e[1] + 82, 'Earth', T, { size: 26, anchor: 'middle', weight: 700, color: '#ffffff', halo: false }) + words(m[0] + 22, m[1] - 18, 'Moon', T, { size: 22, weight: 600, color: '#D7DBE6', halo: false });
      return s + words(48, 66, '“' + this.title + '”', T, { size: 30, color: '#C9CFE3', weight: 400, halo: false }) + badge(T, 'Not to scale');
    } });
}
