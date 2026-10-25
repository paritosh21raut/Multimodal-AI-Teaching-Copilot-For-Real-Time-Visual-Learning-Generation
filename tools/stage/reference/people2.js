// V2 2D samples, part 2: shaped people (tapered limbs, shaped torso, clothes, hair styles, faces), a chibi variant,
// a cast of looks, two-bone arm IK (hands on things), and procedural animals (dog, cat, horse, cow, bird, fish).
// People still move by the baked motion-capture joints (motion.json); animals by a gait synced to their speed.
export function install(K) {
  const { JI, sample, F, lerp, shade, FIG } = K;

  // ---------- drawing ----------
  const smooth = (pts, closed = true) => {
    const n = pts.length; let d = `M${F(pts[0][0])},${F(pts[0][1])}`;
    for (let i = 0; i < (closed ? n : n - 1); i++) {
      const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      d += `C${F(p1[0] + (p2[0] - p0[0]) / 6)},${F(p1[1] + (p2[1] - p0[1]) / 6)} ${F(p2[0] - (p3[0] - p1[0]) / 6)},${F(p2[1] - (p3[1] - p1[1]) / 6)} ${F(p2[0])},${F(p2[1])}`;
    }
    return d + (closed ? 'Z' : '');
  };
  // prims: {k:'d', d, fill} path · {k:'c', c, r, fill} · {k:'e', c, rx, ry, a, fill} · {k:'l', a, b, w, c} ; no: no outline
  function draw(prims, T, ow) {
    let o = '', f = '';
    const ink = T.ink;
    for (const p of prims) {
      if (p.k === 'd') { if (T.outline && !p.no) o += `<path d="${p.d}" fill="${ink}" stroke="${ink}" stroke-width="${F(2 * ow)}" stroke-linejoin="round"/>`; f += `<path d="${p.d}" fill="${p.fill}"${p.op ? ` opacity="${p.op}"` : ''}/>`; }
      else if (p.k === 'c') { if (T.outline && !p.no) o += `<circle cx="${F(p.c[0])}" cy="${F(p.c[1])}" r="${F(p.r + ow)}" fill="${ink}"/>`; f += `<circle cx="${F(p.c[0])}" cy="${F(p.c[1])}" r="${F(p.r)}" fill="${p.fill}"${p.op ? ` opacity="${p.op}"` : ''}/>`; }
      else if (p.k === 'e') { const tr = `transform="rotate(${F(p.a || 0)} ${F(p.c[0])} ${F(p.c[1])})"`;
        if (T.outline && !p.no) o += `<ellipse cx="${F(p.c[0])}" cy="${F(p.c[1])}" rx="${F(p.rx + ow)}" ry="${F(p.ry + ow)}" fill="${ink}" ${tr}/>`;
        f += `<ellipse cx="${F(p.c[0])}" cy="${F(p.c[1])}" rx="${F(p.rx)}" ry="${F(p.ry)}" fill="${p.fill}" ${tr}${p.op ? ` opacity="${p.op}"` : ''}/>`; }
      else if (p.k === 'l') { if (T.outline && !p.no) o += `<line x1="${F(p.a[0])}" y1="${F(p.a[1])}" x2="${F(p.b[0])}" y2="${F(p.b[1])}" stroke="${ink}" stroke-width="${F(p.w + 2 * ow)}" stroke-linecap="round"/>`;
        f += `<line x1="${F(p.a[0])}" y1="${F(p.a[1])}" x2="${F(p.b[0])}" y2="${F(p.b[1])}" stroke="${p.c}" stroke-width="${F(p.w)}" stroke-linecap="round"/>`; }
    }
    return o + f;
  }
  const norm = (v) => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
  // a limb tapering from width wa at a to wb at b (rounded ends)
  function taper(a, b, wa, wb, fill, out) {
    const t = norm([b[0] - a[0], b[1] - a[1]]), n = [-t[1], t[0]];
    out.push({ k: 'd', d: `M${F(a[0] + n[0] * wa / 2)},${F(a[1] + n[1] * wa / 2)}L${F(b[0] + n[0] * wb / 2)},${F(b[1] + n[1] * wb / 2)}L${F(b[0] - n[0] * wb / 2)},${F(b[1] - n[1] * wb / 2)}L${F(a[0] - n[0] * wa / 2)},${F(a[1] - n[1] * wa / 2)}Z`, fill },
      { k: 'c', c: a, r: wa / 2, fill }, { k: 'c', c: b, r: wb / 2, fill });
  }
  // two-bone IK in screen space: the elbow for a hand at `target`, bending down (screen +y)
  function ik(s, target, l1, l2) {
    let dx = target[0] - s[0], dy = target[1] - s[1], d = Math.hypot(dx, dy); const dm = Math.min(d, (l1 + l2) * 0.999);
    const ux = dx / (d || 1), uy = dy / (d || 1), a = (l1 * l1 - l2 * l2 + dm * dm) / (2 * dm), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
    const base = [s[0] + ux * a, s[1] + uy * a], e1 = [base[0] - uy * h, base[1] + ux * h], e2 = [base[0] + uy * h, base[1] - ux * h];
    return [e1[1] > e2[1] ? e1 : e2, [s[0] + ux * dm, s[1] + uy * dm]];
  }

  // ---------- cast ----------
  const CAST = {
    man:    { sex: 'm', skin: '#E9B591', hair: '#2E2B29', hairStyle: 'short', top: '#3E8E9E', sleeve: 'long', bottom: '#3B4A6B', bottomType: 'pants', shoes: '#4A3F38' },
    man2:   { sex: 'm', skin: '#8D5A3B', hair: '#1F1B18', hairStyle: 'bald', beard: true, top: '#F2C14E', sleeve: 'short', bottom: '#4A4E69', bottomType: 'pants', shoes: '#3A3330', build: 1.12 },
    man3:   { sex: 'm', skin: '#C68A64', hair: '#3A2A20', hairStyle: 'curly', glasses: true, top: '#7B6CD9', sleeve: 'long', bottom: '#2F3E46', bottomType: 'pants', shoes: '#E8E4DC' },
    woman:  { sex: 'f', skin: '#C98E6B', hair: '#4A2E20', hairStyle: 'long', top: '#E07A5F', sleeve: 'short', bottom: '#3D5A80', bottomType: 'pants', shoes: '#5A4A42' },
    woman2: { sex: 'f', skin: '#F1C7A5', hair: '#2B1D14', hairStyle: 'bun', top: '#7FB069', sleeve: 'long', bottom: '#5B5F97', bottomType: 'skirt', shoes: '#4A3F38' },
    woman3: { sex: 'f', skin: '#7A4B32', hair: '#1C1410', hairStyle: 'ponytail', top: '#F28FAD', sleeve: 'short', bottom: '#3B5BA5', bottomType: 'pants', shoes: '#F4F1EA' },
    boy:    { sex: 'm', child: true, skin: '#E2A77F', hair: '#3B2A20', hairStyle: 'short', top: '#E4572E', sleeve: 'short', bottom: '#3B4A6B', bottomType: 'shorts', shoes: '#2F80ED' },
    girl:   { sex: 'f', child: true, skin: '#B87A55', hair: '#2B1D14', hairStyle: 'ponytail', top: '#FFC857', sleeve: 'short', bottom: '#6C5CE7', bottomType: 'skirt', shoes: '#E4572E' },
    elder:  { sex: 'm', skin: '#E3B08C', hair: '#D9D6D0', hairStyle: 'bald', beard: true, glasses: true, top: '#8D99AE', sleeve: 'long', bottom: '#5C5C5C', bottomType: 'pants', shoes: '#3A3330' },
    elderw: { sex: 'f', skin: '#D9A07A', hair: '#E2E0DC', hairStyle: 'bun', glasses: true, top: '#B5838D', sleeve: 'long', bottom: '#6D597A', bottomType: 'skirt', shoes: '#3A3330' },
  };
  K.CAST = CAST;
  // the classic 2D looks (capsule figure) for the same cast, so every style can show every person
  for (const [k, c] of Object.entries(CAST)) if (!K.LOOK[k]) K.LOOK[k] = { skin: c.skin, shirt: c.top, sleeve: c.sleeve, pants: c.bottom,
    shoes: c.shoes, hair: c.hair, hairStyle: c.hairStyle === 'long' ? 'long' : 'short' };
  const castOf = (look) => look && look.top ? look : (Object.values(CAST).find(c => c.top === (look && look.shirt)) || CAST.man);

  // ---------- shaped person ----------
  // o: {head: head scale, limb: limb width scale}
  function shaped(p, V, T, o) {
    const fr = p.fr || sample(p.clip, p.t, p.loop !== false), L = castOf(p.cast ? CAST[p.cast] : p.look);
    const child = L.child, h = p.h || (child ? 1.25 : L.sex === 'f' ? 1.66 : 1.78), d = p.dir || 1;
    const hs = (o.head || 1) * (child ? 1.3 : 1), lw = (o.limb || 1) * (L.build || 1), fem = L.sex === 'f';
    const W = k => k * h * V.s;
    const P = j => { const q = fr[JI[j]]; return [V.sx(p.x + d * q[0] * h), V.sy((p.y || 0) + q[1] * h)]; };
    const dk = (c, far) => far ? shade(c, 0.82) : c;
    const ow = Math.max(2, W(0.007));
    // head frame
    const nk = P('neck_01'), hd = P('Head');
    let vx = hd[0] - nk[0], vy = hd[1] - nk[1]; const vl = Math.hypot(vx, vy) || 1; vx /= vl; vy /= vl;
    const fx = -vy * d, fy = vx * d, r = W(0.07) * hs, hc = [hd[0] + vx * r * 0.85, hd[1] + vy * r * 0.85];
    const at = (u, v) => [hc[0] + fx * u * r + vx * v * r, hc[1] + fy * u * r + vy * v * r];
    const ring = (a0, a1, rad, step = 12) => { const out = []; for (let a = a0; a <= a1 + 0.01; a += step) out.push(at(Math.cos(a * Math.PI / 180) * rad, Math.sin(a * Math.PI / 180) * rad)); return out; };

    const arm = (s, far) => {
      const out = [], sh = P('upperarm' + s);
      let el = P('lowerarm' + s), wr = P('hand' + s);
      if (p.ik && p.ik[s]) { const tg = [V.sx(p.ik[s][0]), V.sy(p.ik[s][1])];
        [el, wr] = ik(sh, tg, Math.hypot(el[0] - sh[0], el[1] - sh[1]), Math.hypot(wr[0] - el[0], wr[1] - el[1]) + W(0.035)); }
      const fore = L.sleeve === 'long' ? L.top : L.skin;
      taper(sh, el, W(0.058) * lw, W(0.046) * lw, dk(L.sleeve === 'long' ? L.top : L.skin, far), out);
      if (L.sleeve !== 'long') taper(sh, lerp(sh, el, 0.5), W(0.068) * lw, W(0.062) * lw, dk(L.top, far), out);
      taper(el, wr, W(0.046) * lw, W(0.036) * lw, dk(fore, far), out);
      const ang = Math.atan2(wr[1] - el[1], wr[0] - el[0]) * 180 / Math.PI, hc2 = [wr[0] + Math.cos(ang * Math.PI / 180) * W(0.03), wr[1] + Math.sin(ang * Math.PI / 180) * W(0.03)];
      if (o.chibi) { const hr = W(0.036) * lw, hcc = [wr[0] + Math.cos(ang * Math.PI / 180) * hr * 0.9, wr[1] + Math.sin(ang * Math.PI / 180) * hr * 0.9];
        if (L.sleeve === 'long') out.push({ k: 'e', c: wr, rx: W(0.03) * lw, ry: W(0.026) * lw, a: ang, fill: dk(shade(L.top, 0.85), far) });
        out.push({ k: 'c', c: hcc, r: hr, fill: dk(L.skin, far) }, { k: 'c', c: [hcc[0] - Math.sin(ang * Math.PI / 180) * hr * 0.75 * d, hcc[1] + Math.cos(ang * Math.PI / 180) * hr * 0.75 * d], r: hr * 0.42, fill: dk(shade(L.skin, 0.94), far) });
      } else out.push({ k: 'e', c: hc2, rx: W(0.042), ry: W(0.026), a: ang, fill: dk(L.skin, far) });
      return out;
    };
    const leg = (s, far) => {
      const out = [], th = P('thigh' + s), kn = P('calf' + s), an = P('foot' + s), ba = P('ball' + s);
      const pantsLeg = L.bottomType === 'pants', thighC = L.bottomType === 'skirt' ? L.skin : L.bottom;
      taper(th, kn, W(0.088) * lw, W(0.064) * lw, dk(L.bottomType === 'shorts' ? L.skin : thighC, far), out);
      if (L.bottomType === 'shorts') taper(th, lerp(th, kn, 0.6), W(0.096) * lw, W(0.084) * lw, dk(L.bottom, far), out);
      taper(kn, an, W(0.064) * lw, W(0.048) * lw, dk(pantsLeg ? L.bottom : L.skin, far), out);
      const u = norm([ba[0] - an[0], ba[1] - an[1]]), heel = [an[0] - u[0] * W(0.012), an[1] - u[1] * W(0.012) + W(0.024)], toe = [ba[0] + u[0] * W(0.022), ba[1] + u[1] * W(0.022)];
      if (o.chibi) { const nn = [-u[1], u[0]], dn = nn[1] > 0 ? 1 : -1, so = W(0.02);
        taper([heel[0] + nn[0] * so * dn, heel[1] + nn[1] * so * dn], [toe[0] + nn[0] * so * dn, toe[1] + nn[1] * so * dn], W(0.03), W(0.026), dk('#F4F1EA', far), out);
        taper(heel, toe, W(0.052), W(0.046), dk(L.shoes, far), out); }
      else taper(heel, toe, W(0.05), W(0.042), dk(L.shoes, far), out);
      out.push({ k: 'c', c: an, r: W(0.03), fill: dk(L.shoes, far) });
      return out;
    };
    // torso: the spine offset to the front / back by half-depths (1 m units, scaled by the build)
    const pel = P('pelvis'), sp2 = P('spine_02'), sp3 = P('spine_03'), nb = lerp(sp3, nk, 0.75);
    const prof = fem ? [[0.07, 0.075], [0.066, 0.062], [0.09, 0.068], [0.03, 0.032]] : [[0.072, 0.07], [0.076, 0.066], [0.088, 0.076], [0.034, 0.036]];
    const S = [lerp(pel, sp2, -0.25), sp2, sp3, nb];
    const off = (i) => { const a = S[Math.max(0, i - 1)], b = S[Math.min(3, i + 1)], t = norm([b[0] - a[0], b[1] - a[1]]); return [-t[1] * d, t[0] * d]; };
    const front = S.map((q, i) => { const n = off(i); return [q[0] + n[0] * W(prof[i][0]) * lw, q[1] + n[1] * W(prof[i][0]) * lw]; });
    const back = S.map((q, i) => { const n = off(i); return [q[0] - n[0] * W(prof[i][1]) * lw, q[1] - n[1] * W(prof[i][1]) * lw]; });
    const belt = 0.42;   // where the shirt ends between S0 and S1
    const fb = lerp(front[0], front[1], belt), bb = lerp(back[0], back[1], belt);
    const shirt = smooth([fb, front[1], front[2], front[3], back[3], back[2], back[1], bb]);
    const hips = `M${F(fb[0])},${F(fb[1])}L${F(front[0][0])},${F(front[0][1])}L${F(back[0][0])},${F(back[0][1])}L${F(bb[0])},${F(bb[1])}Z`;
    const body = [];
    // long hair / ponytail behind the body
    const hairBack = [];
    if (L.hairStyle === 'long') hairBack.push({ k: 'd', d: smooth([at(-0.3, 0.9), at(-1.05, 0.2), at(-1.1, -1.0), at(-0.75, -2.0), at(-0.1, -1.7), at(0.0, -0.4)]), fill: L.hair });
    if (L.hairStyle === 'ponytail') hairBack.push({ k: 'd', d: smooth([at(-0.8, 0.55), at(-1.45, 0.1), at(-1.55, -0.9), at(-1.2, -1.15), at(-1.05, -0.2)]), fill: L.hair });
    body.push({ k: 'd', d: hips, fill: L.bottomType === 'skirt' ? L.bottom : L.bottom });
    body.push({ k: 'd', d: shirt, fill: L.top });
    if (o.chibi) {
      const mid = [1, 2, 3].map(i => lerp(front[i], back[i], 0.6));
      body.push({ k: 'd', d: smooth([lerp(fb, bb, 0.6), ...mid, back[3], back[2], back[1], bb]), fill: shade(L.top, 0.9), no: 1 });
      body.push({ k: 'd', d: smooth([lerp(front[3], back[3], 0.15), lerp(front[3], back[3], 0.75), lerp(lerp(front[2], back[2], 0.4), front[3], 0.72), lerp(lerp(front[2], back[2], 0.15), front[3], 0.62)]), fill: shade(L.top, 1.18), no: 1 });
      if (L.bottomType !== 'skirt') body.push({ k: 'l', a: lerp(fb, bb, 0.04), b: lerp(fb, bb, 0.96), w: W(0.022), c: shade(L.bottom, 0.75), no: 1 });
    }
    if (L.bottomType === 'skirt') {
      const cl = P('calf_l'), cr = P('calf_r'), xs = [cl[0], cr[0], P('thigh_l')[0], P('thigh_r')[0]];
      const ky = Math.max(cl[1], cr[1]) - W(0.03), fx2 = d > 0 ? Math.max(...xs) + W(0.06) : Math.min(...xs) - W(0.06), bx2 = d > 0 ? Math.min(...xs) - W(0.07) : Math.max(...xs) + W(0.07);
      body.push({ k: 'd', d: smooth([fb, [fx2, ky], [bx2, ky], bb]), fill: L.bottom });
    }
    // collar line + neck + head
    const neck = [];
    taper(nb, at(-0.15, -0.75), W(0.05), W(0.05), shade(L.skin, 0.93), neck);
    const head = [];
    head.push({ k: 'd', d: smooth([...ring(-60, 200, 1.0, 20), at(-0.55, -0.92), at(0.1, -1.12), at(0.62, -0.95)]), fill: L.skin });
    head.push({ k: 'c', c: at(0.98, -0.12), r: r * 0.17, fill: L.skin });
    const hair = [];
    const cap = (a0, a1, rad) => ring(a0, a1, rad, 10);
    if (L.hairStyle === 'short') hair.push({ k: 'd', d: smooth([...cap(55, 215, 1.08), at(-0.55, -0.05), at(0.1, 0.62), at(0.7, 0.6)]), fill: L.hair });
    else if (L.hairStyle === 'long') hair.push({ k: 'd', d: smooth([...cap(50, 225, 1.1), at(-0.5, -0.2), at(0.0, 0.55), at(0.72, 0.62)]), fill: L.hair });
    else if (L.hairStyle === 'bun') { hair.push({ k: 'd', d: smooth([...cap(55, 215, 1.07), at(-0.5, -0.05), at(0.15, 0.6), at(0.7, 0.58)]), fill: L.hair }); hair.push({ k: 'c', c: at(-0.78, 0.82), r: r * 0.42, fill: L.hair }); }
    else if (L.hairStyle === 'ponytail') { hair.push({ k: 'd', d: smooth([...cap(55, 215, 1.08), at(-0.55, -0.05), at(0.1, 0.62), at(0.7, 0.6)]), fill: L.hair }); hair.push({ k: 'c', c: at(-0.88, 0.5), r: r * 0.22, fill: shade(L.hair, 1.3) }); }
    else if (L.hairStyle === 'curly') { for (let a = 40; a <= 230; a += 24) hair.push({ k: 'c', c: at(Math.cos(a * Math.PI / 180) * 0.98, Math.sin(a * Math.PI / 180) * 0.98), r: r * 0.36, fill: L.hair }); hair.push({ k: 'd', d: smooth([...cap(60, 210, 0.95), at(-0.4, 0.0), at(0.2, 0.55)]), fill: L.hair }); }
    else if (L.hairStyle === 'bald') hair.push({ k: 'd', d: smooth([...cap(150, 215, 1.04), at(-0.55, -0.1), at(-0.75, 0.25)]), fill: L.hair, no: 1 });
    if (o.chibi && L.hairStyle !== 'bald' && L.hairStyle !== 'curly') { const hl = ring(85, 140, 0.88, 6);
      hair.push({ k: 'd', d: smooth([...hl, ...ring(85, 140, 0.76, 6).reverse()]), fill: shade(L.hair, 1.6), op: 0.45, no: 1 }); }
    // face (never outlined)
    let face = '';
    const ink = '#2b2522';
    if (L.beard) face += draw([{ k: 'd', d: smooth([at(0.78, -0.3), at(0.72, -0.82), at(0.25, -1.16), at(-0.3, -0.88), at(-0.25, -0.3), at(0.2, -0.5)]), fill: L.hair, no: 1 }], T, ow);
    if (o.chibi) {
      face += draw([{ k: 'c', c: at(-0.12, -0.08), r: r * 0.2, fill: shade(L.skin, 0.9), no: 1 }, { k: 'c', c: at(-0.1, -0.08), r: r * 0.1, fill: shade(L.skin, 0.8), no: 1 },
        { k: 'e', c: at(0.48, 0.02), rx: r * 0.16, ry: r * 0.21, a: 0, fill: '#ffffff', no: 1 }, { k: 'e', c: at(0.54, 0.0), rx: r * 0.12, ry: r * 0.17, a: 0, fill: '#3a2a22', no: 1 },
        { k: 'e', c: at(0.56, -0.02), rx: r * 0.07, ry: r * 0.1, a: 0, fill: '#120d0b', no: 1 }, { k: 'c', c: at(0.6, 0.08), r: r * 0.045, fill: '#ffffff', no: 1 }, { k: 'c', c: at(0.5, -0.09), r: r * 0.022, fill: '#ffffff', no: 1 },
        { k: 'e', c: at(0.4, -0.36), rx: r * 0.15, ry: r * 0.09, a: 0, fill: '#F07A7A', op: 0.4, no: 1 },
        { k: 'c', c: at(0.97, -0.16), r: r * 0.1, fill: shade(L.skin, 0.95), no: 1 }], T, ow);
      const bw = at(0.3, 0.36), bm = at(0.5, 0.44), be = at(0.72, 0.36);
      face += `<path d="M${F(bw[0])},${F(bw[1])} Q${F(bm[0])},${F(bm[1])} ${F(be[0])},${F(be[1])}" fill="none" stroke="${L.hairStyle === 'bald' && !L.beard ? shade(L.skin, 0.55) : L.hair}" stroke-width="${F(r * 0.075)}" stroke-linecap="round"/>`;
      if (!L.beard) { const m0 = at(0.55, -0.48), m1 = at(0.7, -0.66), m2 = at(0.86, -0.46);
        face += `<path d="M${F(m0[0])},${F(m0[1])} Q${F(m1[0])},${F(m1[1])} ${F(m2[0])},${F(m2[1])} Z" fill="#B8524A"/>`; }
    } else
    face += draw([{ k: 'e', c: at(0.5, 0.08), rx: r * 0.13, ry: r * 0.17, a: 0, fill: '#ffffff', no: 1 }, { k: 'e', c: at(0.56, 0.07), rx: r * 0.09, ry: r * 0.13, a: 0, fill: ink, no: 1 }, { k: 'c', c: at(0.6, 0.13), r: r * 0.035, fill: '#ffffff', no: 1 },
      { k: 'l', a: at(0.32, 0.42), b: at(0.72, 0.4), w: r * 0.09, c: L.hairStyle === 'bald' && !L.beard ? shade(L.skin, 0.6) : L.hair, no: 1 },
      { k: 'c', c: at(-0.12, -0.05), r: r * 0.2, fill: shade(L.skin, 0.88), no: 1 },
      { k: 'c', c: at(0.42, -0.35), r: r * 0.16, fill: '#E86F6F', op: 0.25, no: 1 }], T, ow);
    if (!L.beard) face += `<path d="M${F(at(0.58, -0.5)[0])},${F(at(0.58, -0.5)[1])} Q${F(at(0.72, -0.62)[0])},${F(at(0.72, -0.62)[1])} ${F(at(0.84, -0.48)[0])},${F(at(0.84, -0.48)[1])}" fill="none" stroke="#9a4a3a" stroke-width="${F(r * 0.07)}" stroke-linecap="round"/>`;
    if (L.glasses) { const g = at(0.55, 0.1); face += `<circle cx="${F(g[0])}" cy="${F(g[1])}" r="${F(r * 0.25)}" fill="rgba(255,255,255,0.25)" stroke="#2b2522" stroke-width="${F(r * 0.06)}"/>` +
      `<line x1="${F(at(0.3, 0.12)[0])}" y1="${F(at(0.3, 0.12)[1])}" x2="${F(at(-0.12, 0.12)[0])}" y2="${F(at(-0.12, 0.12)[1])}" stroke="#2b2522" stroke-width="${F(r * 0.06)}"/>`; }
    let shadow = '';
    if (!T.outline && !p.noShadow) {
      const gx = (P('ball_l')[0] + P('ball_r')[0]) / 2, gy = V.sy(0), lift = Math.max(0, p.y || 0) * V.s, k = Math.max(0.35, 1 - lift / 600);
      shadow = `<ellipse cx="${F(gx)}" cy="${F(gy)}" rx="${F(W(0.17) * k)}" ry="${F(W(0.028) * k)}" fill="rgba(40,50,40,${F(0.18 * k)})"/>`;
    }
    let extra = '';
    if (p.cane) { const hn = P('hand_r'); extra = `<line x1="${F(hn[0])}" y1="${F(hn[1])}" x2="${F(hn[0] + d * W(0.06))}" y2="${F(V.sy(p.y || 0))}" stroke="#6B4A2F" stroke-width="${F(W(0.016))}" stroke-linecap="round"/>`; }
    return shadow + draw(arm('_l', true), T, ow) + draw(leg('_l', true), T, ow) + draw(hairBack, T, ow) + draw(leg('_r', false), T, ow) +
      draw([...body, ...neck, ...head, ...hair], T, ow) + face + draw(arm('_r', false), T, ow) + extra;
  }
  FIG.shaped = (p, V, T) => shaped(p, V, T, { head: 1.12, limb: 1.05 });
  FIG.chibi = (p, V, T) => shaped(p, V, T, { head: 1.6, limb: 1.22, chibi: 1 });

  // ---------- animals ----------
  const SPECIES = {
    dog:   { L: 0.62, H: 0.24, hip: 0.44, head: 0.12, neck: 0.16, nAng: 50, tail: 0.24, tailUp: 0.8, color: '#C98B4F', belly: '#EBC79B', ear: 'flop', snout: 0.11, stride: 0.55 },
    cat:   { L: 0.42, H: 0.16, hip: 0.27, head: 0.09, neck: 0.07, nAng: 55, tail: 0.34, tailUp: 1.4, color: '#E39B4B', belly: '#F6D2A2', ear: 'point', snout: 0.03, stride: 0.35, stripes: true },
    horse: { L: 1.3, H: 0.62, hip: 1.25, head: 0.2, neck: 0.62, nAng: 58, tail: 0.55, tailUp: -0.3, color: '#8B5A3C', belly: '#A6714E', mane: '#3B2A20', ear: 'point', snout: 0.26, stride: 1.4 },
    cow:   { L: 1.45, H: 0.72, hip: 1.12, head: 0.2, neck: 0.3, nAng: 25, tail: 0.6, tailUp: -0.6, color: '#F5F1EA', spots: '#2E2B29', belly: '#F5F1EA', ear: 'side', horn: true, snout: 0.16, stride: 0.9 },
  };
  // a = {kind, x, y?, t, dir, speed (m/s, 0 stands), pose: walk|stand|sit|fly|swim, scale}
  function animal(a, V, T) {
    const d = a.dir || 1, k = a.scale || 1, ow = Math.max(2, 2.2);
    const X = (u) => V.sx(a.x + d * u * k), Y = (v) => V.sy((a.y || 0) + v * k), S = (m) => m * k * V.s;
    if (a.kind === 'bird') {
      const fl = Math.sin((a.t || 0) * 14) * (a.pose === 'fly' ? 1 : 0), c = [X(0), Y(0)], col = a.color || '#3A86FF';
      const wing = [[X(-0.02), Y(0.03)], [X(-0.12), Y(0.03 + 0.18 * fl)], [X(0.08), Y(0.03)]];
      const pr = [{ k: 'e', c, rx: S(0.12), ry: S(0.06), a: 0, fill: col }, { k: 'c', c: [X(0.11), Y(0.045)], r: S(0.05), fill: col },
        { k: 'd', d: `M${F(X(0.155))},${F(Y(0.05))}L${F(X(0.21))},${F(Y(0.035))}L${F(X(0.155))},${F(Y(0.025))}Z`, fill: '#F2A541' },
        { k: 'd', d: `M${F(X(-0.1))},${F(Y(0.0))}L${F(X(-0.22))},${F(Y(0.05))}L${F(X(-0.2))},${F(Y(-0.04))}Z`, fill: shade(col, 0.8) },
        { k: 'd', d: `M${F(wing[0][0])},${F(wing[0][1])}L${F(wing[1][0])},${F(wing[1][1])}L${F(wing[2][0])},${F(wing[2][1])}Z`, fill: shade(col, 0.75) },
        { k: 'c', c: [X(0.125), Y(0.06)], r: S(0.012), fill: '#1b1b1b', no: 1 }];
      if (a.pose !== 'fly') pr.push({ k: 'l', a: [X(0), Y(-0.05)], b: [X(0), Y(-0.12)], w: S(0.01), c: '#F2A541' });
      return draw(pr, T, ow);
    }
    if (a.kind === 'fish') {
      const wag = Math.sin((a.t || 0) * 7) * 0.5, col = a.color || '#F28C28';
      const tailT = [X(-0.17), Y(0)], tb = [X(-0.3), Y(0.08 + wag * 0.05)], tc = [X(-0.3), Y(-0.08 + wag * 0.05)];
      return draw([{ k: 'd', d: `M${F(tailT[0])},${F(tailT[1])}L${F(tb[0])},${F(tb[1])}L${F(tc[0])},${F(tc[1])}Z`, fill: shade(col, 0.85) },
        { k: 'e', c: [X(0), Y(0)], rx: S(0.2), ry: S(0.09), a: 0, fill: col },
        { k: 'd', d: `M${F(X(-0.02))},${F(Y(0.08))}L${F(X(0.05))},${F(Y(0.15))}L${F(X(0.09))},${F(Y(0.07))}Z`, fill: shade(col, 0.85) },
        { k: 'c', c: [X(0.12), Y(0.025)], r: S(0.018), fill: '#1b1b1b', no: 1 }], T, ow);
    }
    const sp = SPECIES[a.kind], t = a.t || 0, dist = (a.speed || 0) * t;
    if (a.pose === 'sit') {   // dog / cat sitting: haunch on the ground, chest up, front legs straight, tail round the feet
      const Lb = sp.L, hp = sp.hip, Q = (u, v) => [X(u * Lb), Y(v * hp)], col = sp.color, hr = S(sp.head) * 1.1;
      const pr = [];
      const tail = `<path d="M${F(Q(-0.45, 0.08)[0])},${F(Q(-0.45, 0.08)[1])} Q${F(Q(-0.2, -0.05)[0])},${F(Q(-0.2, -0.05)[1])} ${F(Q(0.35, 0.05)[0])},${F(Q(0.35, 0.05)[1])}" fill="none" stroke="${shade(col, 0.85)}" stroke-width="${F(S(0.035))}" stroke-linecap="round"/>`;
      taper(Q(0.2, 1.0), Q(0.22, 0.04), S(0.05), S(0.035), shade(col, 0.82), pr);
      pr.push({ k: 'e', c: Q(-0.18, 0.42), rx: S(Lb * 0.3), ry: S(hp * 0.42), a: 0, fill: col });
      pr.push({ k: 'd', d: smooth([Q(-0.42, 0.25), Q(-0.38, 0.85), Q(-0.05, 1.35), Q(0.25, 1.45), Q(0.32, 1.0), Q(0.2, 0.35), Q(-0.05, 0.08)]), fill: col });
      pr.push({ k: 'd', d: smooth([Q(0.08, 1.25), Q(0.27, 1.3), Q(0.25, 0.7), Q(0.12, 0.6)]), fill: sp.belly, no: 1 });
      if (sp.stripes) [0.6, 0.85, 1.1].forEach(v => pr.push({ k: 'l', a: Q(-0.35, v), b: Q(-0.15, v + 0.05), w: S(0.022), c: shade(col, 0.8), no: 1 }));
      taper(Q(0.25, 1.0), Q(0.28, 0.04), S(0.055), S(0.04), col, pr);
      pr.push({ k: 'e', c: Q(0.3, 0.03), rx: S(0.04), ry: S(0.022), a: 0, fill: shade(col, 0.75) }, { k: 'e', c: Q(-0.02, 0.04), rx: S(0.06), ry: S(0.03), a: 0, fill: shade(col, 0.85) });
      const hc = [X(0.2 * Lb), Y(1.45 * hp) - hr * 0.9];
      if (sp.ear === 'point') for (const e of [-0.45, 0.35]) pr.push({ k: 'd', d: `M${F(hc[0] + d * hr * (e - 0.25))},${F(hc[1] - hr * 0.6)}L${F(hc[0] + d * hr * e)},${F(hc[1] - hr * 1.55)}L${F(hc[0] + d * hr * (e + 0.35))},${F(hc[1] - hr * 0.75)}Z`, fill: shade(col, 0.9) });
      pr.push({ k: 'c', c: hc, r: hr, fill: col }, { k: 'e', c: [hc[0] + d * hr * 0.75, hc[1] + hr * 0.3], rx: hr * 0.45, ry: hr * 0.35, a: 0, fill: sp.belly });
      if (sp.ear === 'flop') pr.push({ k: 'e', c: [hc[0] - d * hr * 0.55, hc[1] + hr * 0.1], rx: hr * 0.32, ry: hr * 0.75, a: d * 15, fill: shade(col, 0.7) });
      const sh = T.outline ? '' : `<ellipse cx="${F(X(0))}" cy="${F(V.sy(a.y || 0))}" rx="${F(S(Lb * 0.5))}" ry="${F(S(0.035))}" fill="rgba(40,50,40,0.16)"/>`;
      return sh + tail + draw(pr, T, ow) + `<circle cx="${F(hc[0] + d * hr * 0.4)}" cy="${F(hc[1] - hr * 0.12)}" r="${F(hr * 0.14)}" fill="#1b1b1b"/>` +
        `<circle cx="${F(hc[0] + d * hr * 1.12)}" cy="${F(hc[1] + hr * 0.2)}" r="${F(hr * 0.12)}" fill="#2b2522"/>`;
    }
    const phi = 2 * Math.PI * dist / sp.stride, amp = a.speed ? 0.42 : 0;
    const legTop = sp.hip - sp.H * 0.3, legLen = legTop, l1 = legLen * 0.52, l2 = legLen * 0.5;
    const legs = [['bl', -0.36, 0, true], ['fl', 0.36, 0.5, true], ['br', -0.36, 1.0, false], ['fr', 0.36, 1.5, false]];
    const foot = (xo, ph, front) => {
      const th1 = amp * Math.sin(phi + ph * Math.PI), lift = Math.max(0, Math.cos(phi + ph * Math.PI)) * (a.speed ? 0.7 : 0);
      const th2 = front ? th1 - lift : th1 + lift * 0.8;
      const hipP = [xo * sp.L, legTop], kn = [hipP[0] + Math.sin(th1) * l1, hipP[1] - Math.cos(th1) * l1];
      return [hipP, kn, [kn[0] + Math.sin(th2) * l2, kn[1] - Math.cos(th2) * l2]];
    };
    const chains = legs.map(([n, xo, ph]) => foot(xo, ph, n[0] === 'f'));
    const lowest = Math.min(...chains.map(c => c[2][1]));
    const bob = -lowest + (a.speed ? 0.012 * Math.abs(Math.sin(2 * phi)) : 0);
    const sit = a.pose === 'sit';
    const tilt = sit ? 32 : 0;   // degrees, rear down
    const rot = (u, v) => { if (!sit) return [u, v + bob]; const ang = tilt * Math.PI / 180, pu = -0.45 * sp.L, pv = sp.hip * 0.42; const du = u - pu, dv = v - pv; return [pu + du * Math.cos(ang) - dv * Math.sin(ang), pv + du * Math.sin(ang) + dv * Math.cos(ang) - (sp.hip * 0.42 - sp.H * 0.55)]; };
    const PT = (u, v) => { const q = rot(u, v); return [X(q[0]), Y(q[1])]; };
    const col = sp.color, far = shade(col, 0.82), lw = S(sp.L * 0.12);
    const out = [], back = [];
    // legs: far first (behind the body), near after
    chains.forEach((c, i) => {
      const isFar = legs[i][3], tgt = isFar ? back : out, cc = isFar ? far : col, front = legs[i][0][0] === 'f';
      if (sit && !front) return;
      let a0 = PT(...c[0]), a1 = PT(...c[1]), a2 = PT(...c[2]);
      if (sit) { a0 = PT(...c[0]); a1 = [a0[0] + d * S(0.0), a0[1] + S(legLen * 0.5)]; a2 = [a0[0] + d * S(0.02), V.sy(0)]; }
      taper(a0, a1, lw * 1.6, lw * 0.85, cc, tgt); taper(a1, a2, lw * 0.85, lw * 0.62, cc, tgt);
      tgt.push({ k: 'e', c: [a2[0] + d * lw * 0.12, a2[1] - lw * 0.1], rx: lw * 0.48, ry: lw * 0.36, a: 0, fill: a.kind === 'horse' || a.kind === 'cow' ? '#3A2E28' : shade(cc, 0.75) });
    });
    if (sit) back.push({ k: 'e', c: PT(-0.36 * sp.L, sp.H * 0.15), rx: S(sp.L * 0.2), ry: S(sp.H * 0.55), a: 0, fill: shade(col, 0.92) });
    // tail
    const tb = PT(-0.5 * sp.L, sp.hip - sp.H * 0.05), wag = Math.sin(t * 6) * 0.15;
    const tm = PT(-0.5 * sp.L - sp.tail * 0.5, sp.hip + sp.tail * 0.5 * sp.tailUp * 0.6 + wag * sp.tail), te = PT(-0.5 * sp.L - sp.tail * 0.75, sp.hip + sp.tail * sp.tailUp * 0.6 + wag * sp.tail * 2);
    back.push({ k: 'd', d: `M${F(tb[0])},${F(tb[1])} Q${F(tm[0])},${F(tm[1])} ${F(te[0])},${F(te[1])}`, fill: 'none', no: 1 });
    const tailSvg = `<path d="M${F(tb[0])},${F(tb[1])} Q${F(tm[0])},${F(tm[1])} ${F(te[0])},${F(te[1])}" fill="none" stroke="${sp.mane || shade(col, 0.85)}" stroke-width="${F(lw * (a.kind === 'horse' ? 1.3 : 0.7))}" stroke-linecap="round"/>`;
    back.pop();
    // body
    const body = [];
    const bpts = [PT(-0.5 * sp.L, sp.hip + sp.H * 0.4), PT(0, sp.hip + sp.H * 0.45), PT(0.5 * sp.L, sp.hip + sp.H * 0.5), PT(0.56 * sp.L, sp.hip),
      PT(0.45 * sp.L, sp.hip - sp.H * 0.45), PT(0, sp.hip - sp.H * 0.55), PT(-0.5 * sp.L, sp.hip - sp.H * 0.4), PT(-0.57 * sp.L, sp.hip)];
    body.push({ k: 'd', d: smooth(bpts), fill: col });
    body.push({ k: 'd', d: smooth([PT(-0.35 * sp.L, sp.hip - sp.H * 0.2), PT(0.35 * sp.L, sp.hip - sp.H * 0.25), PT(0.3 * sp.L, sp.hip - sp.H * 0.5), PT(-0.3 * sp.L, sp.hip - sp.H * 0.45)]), fill: sp.belly, no: 1 });
    if (sp.spots) [[-0.25, 0.15, 0.16], [0.15, 0.25, 0.12], [0.05, -0.1, 0.1], [-0.4, -0.05, 0.08]].forEach(([u, v, rr]) => body.push({ k: 'c', c: PT(u * sp.L, sp.hip + v * sp.H), r: S(rr * sp.L * 0.6), fill: sp.spots, no: 1 }));
    if (sp.stripes) [-0.25, -0.1, 0.05].forEach(u => body.push({ k: 'l', a: PT(u * sp.L, sp.hip + sp.H * 0.45), b: PT(u * sp.L - 0.02, sp.hip + sp.H * 0.1), w: S(0.025), c: shade(col, 0.8), no: 1 }));
    // neck + head
    const na = sp.nAng * Math.PI / 180, nb0 = [0.42 * sp.L, sp.hip + sp.H * 0.2], hcU = nb0[0] + Math.cos(na) * sp.neck, hcV = nb0[1] + Math.sin(na) * sp.neck + (sit ? 0 : 0);
    const nA = PT(nb0[0], nb0[1]), nB = PT(hcU, hcV);
    taper(nA, nB, S(sp.H * 0.75), S(sp.head * 1.3), col, body);
    if (sp.mane) taper(PT(nb0[0] - 0.08, nb0[1] + sp.H * 0.4), PT(hcU - 0.06, hcV + sp.head * 0.6), S(0.08), S(0.06), sp.mane, body);
    const hc = PT(hcU, hcV), hr = S(sp.head);
    body.push({ k: 'c', c: hc, r: hr, fill: col });
    const sn = PT(hcU + sp.snout + sp.head * 0.4, hcV - sp.head * 0.35);
    taper(hc, sn, hr * 1.4, hr * 0.85, col, body);
    body.push({ k: 'c', c: [sn[0] + d * hr * 0.3, sn[1] - hr * 0.05], r: hr * 0.18, fill: '#2b2522', no: 1 });
    if (sp.ear === 'point') body.push({ k: 'd', d: `M${F(PT(hcU - 0.02, hcV + sp.head * 0.6)[0])},${F(PT(hcU - 0.02, hcV + sp.head * 0.6)[1])}L${F(PT(hcU - 0.05, hcV + sp.head * 1.6)[0])},${F(PT(hcU - 0.05, hcV + sp.head * 1.6)[1])}L${F(PT(hcU + 0.05, hcV + sp.head * 0.8)[0])},${F(PT(hcU + 0.05, hcV + sp.head * 0.8)[1])}Z`, fill: shade(col, 0.85) });
    if (sp.ear === 'flop') body.push({ k: 'e', c: PT(hcU - sp.head * 0.45, hcV - sp.head * 0.1), rx: hr * 0.35, ry: hr * 0.8, a: d * 15, fill: shade(col, 0.7) });
    if (sp.ear === 'side') body.push({ k: 'e', c: PT(hcU - sp.head * 0.6, hcV + sp.head * 0.5), rx: hr * 0.55, ry: hr * 0.25, a: -d * 20, fill: shade(col, 0.9) });
    if (sp.horn) body.push({ k: 'd', d: `M${F(PT(hcU - 0.02, hcV + sp.head * 0.8)[0])},${F(PT(hcU - 0.02, hcV + sp.head * 0.8)[1])}Q${F(PT(hcU - 0.05, hcV + sp.head * 1.6)[0])},${F(PT(hcU - 0.05, hcV + sp.head * 1.6)[1])} ${F(PT(hcU + 0.08, hcV + sp.head * 1.5)[0])},${F(PT(hcU + 0.08, hcV + sp.head * 1.5)[1])}L${F(PT(hcU + 0.04, hcV + sp.head * 0.85)[0])},${F(PT(hcU + 0.04, hcV + sp.head * 0.85)[1])}Z`, fill: '#E9DCC0' });
    const eye = PT(hcU + sp.head * 0.35, hcV + sp.head * 0.25);
    const shadow = T.outline ? '' : `<ellipse cx="${F(X(0))}" cy="${F(V.sy(a.y || 0))}" rx="${F(S(sp.L * 0.6))}" ry="${F(S(0.04))}" fill="rgba(40,50,40,0.16)"/>`;
    return shadow + tailSvg + draw(back, T, ow) + draw(body, T, ow) + draw(out, T, ow) + `<circle cx="${F(eye[0])}" cy="${F(eye[1])}" r="${F(hr * 0.16)}" fill="#1b1b1b"/>`;
  }
  K.animal = animal;
  K.smooth = smooth;
  K.ikSolve = ik;
}
