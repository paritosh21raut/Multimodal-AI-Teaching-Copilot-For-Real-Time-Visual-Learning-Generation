// V2 2D samples, part 3: the 3D "B toon" people (CC0 Quaternius base bodies + library hair, clothes painted per bone
// region) rendered side-on into a picture that sits in the 2D scene. Same motion clips as the 2D figures.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { OutlineEffect } from 'three/addons/effects/OutlineEffect.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

const canvas = document.createElement('canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.setClearColor(0x000000, 0);
const outline = new OutlineEffect(renderer, { defaultThickness: 0.004, defaultColor: [0.17, 0.19, 0.22] });
const grad = (() => { const t = new THREE.DataTexture(new Uint8Array([150, 215, 255]), 3, 1, THREE.RedFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true; return t; })();
const BOX = { x0: -1.3, x1: 1.3, y0: -0.05, y1: 2.25 };
const A = {};

function mat(color, map) {
  const m = new THREE.MeshToonMaterial({ color: new THREE.Color(color), gradientMap: grad, ...(map ? { map } : {}) });
  m.userData.outlineParameters = { thickness: 0.004, color: new THREE.Color(color).multiplyScalar(0.5).toArray(), alpha: 1 };
  return m;
}
const SKIN = /^(Head|neck_01|hand_|thumb|index|middle|ring|pinky)/;
function regionOf(n, sleeve) {
  if (SKIN.test(n)) return 0; if (/^(spine|clavicle|upperarm)/.test(n)) return 1;
  if (/^lowerarm/.test(n)) return sleeve ? 1 : 0; if (/^(foot|ball)/.test(n)) return 3; return 2;
}
function smoothCloth(g, reg, iters) {
  const pos = g.attributes.position, nor = g.attributes.normal, n = pos.count, key = new Map(), id = new Int32Array(n);
  for (let i = 0; i < n; i++) { const k = `${Math.round(pos.getX(i) * 2e3)},${Math.round(pos.getY(i) * 2e3)},${Math.round(pos.getZ(i) * 2e3)}`;
    if (!key.has(k)) key.set(k, key.size); id[i] = key.get(k); }
  const m = key.size, nb = Array.from({ length: m }, () => new Set()), cloth = new Uint8Array(m), N = new Float32Array(m * 3);
  const idx = g.index ? g.index.array : Array.from({ length: n }, (_, i) => i);
  for (let t = 0; t < idx.length; t += 3) { const a = id[idx[t]], b = id[idx[t + 1]], c = id[idx[t + 2]]; nb[a].add(b).add(c); nb[b].add(a).add(c); nb[c].add(a).add(b); }
  for (let i = 0; i < n; i++) { const w = id[i]; if (reg[i] === 1 || reg[i] === 2) cloth[w] = 1; N[w * 3] += nor.getX(i); N[w * 3 + 1] += nor.getY(i); N[w * 3 + 2] += nor.getZ(i); }
  for (let it = 0; it < iters; it++) { const M2 = N.slice();
    for (let w = 0; w < m; w++) { if (!cloth[w]) continue; let x = N[w * 3], y = N[w * 3 + 1], z = N[w * 3 + 2];
      for (const q of nb[w]) { x += N[q * 3]; y += N[q * 3 + 1]; z += N[q * 3 + 2]; }
      const l = Math.hypot(x, y, z) || 1; M2[w * 3] = x / l; M2[w * 3 + 1] = y / l; M2[w * 3 + 2] = z / l; }
    N.set(M2); }
  for (let i = 0; i < n; i++) { const w = id[i]; if (cloth[w] && reg[i] !== 0) nor.setXYZ(i, N[w * 3], N[w * 3 + 1], N[w * 3 + 2]); }
  nor.needsUpdate = true;
}
// natural bodies: the free base bodies are "superhero" builds, so smooth the muscle shapes away (Taubin, keeps volume)
// and slim the arms, shoulders and chest towards their bone lines; then recompute normals across UV seams
const LIMB = { upperarm_l: 'lowerarm_l', upperarm_r: 'lowerarm_r', lowerarm_l: 'hand_l', lowerarm_r: 'hand_r', thigh_l: 'calf_l', thigh_r: 'calf_r', calf_l: 'foot_l', calf_r: 'foot_r' };
function demuscle(mesh, fem) {
  const g = mesh.geometry, pos = g.attributes.position, nor = g.attributes.normal, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, n = pos.count;
  const bones = mesh.skeleton.bones, idxOf = Object.fromEntries(bones.map((b, i) => [b.name, i]));
  const bindPos = mesh.skeleton.boneInverses.map(m => new THREE.Vector3().setFromMatrixPosition(m.clone().invert()));
  const dom = new Int32Array(n);
  for (let i = 0; i < n; i++) { let best = 0, bw = -1; for (let k = 0; k < 4; k++) { const w = sw.getComponent(i, k); if (w > bw) { bw = w; best = si.getComponent(i, k); } } dom[i] = best; }
  const key = new Map(), id = new Int32Array(n);
  for (let i = 0; i < n; i++) { const k = `${Math.round(pos.getX(i) * 2e3)},${Math.round(pos.getY(i) * 2e3)},${Math.round(pos.getZ(i) * 2e3)}`; if (!key.has(k)) key.set(k, key.size); id[i] = key.get(k); }
  const m = key.size, Pp = new Float32Array(m * 3), body = new Uint8Array(m), bone = new Int32Array(m), nb = Array.from({ length: m }, () => new Set());
  const v = new THREE.Vector3();
  for (let i = 0; i < n; i++) { const w = id[i]; v.fromBufferAttribute(pos, i).applyMatrix4(mesh.bindMatrix); Pp[w * 3] = v.x; Pp[w * 3 + 1] = v.y; Pp[w * 3 + 2] = v.z;
    bone[w] = dom[i]; if (/^(spine|pelvis|clavicle|upperarm|lowerarm|thigh|calf)/.test(bones[dom[i]].name)) body[w] = 1; }
  const idx = g.index ? g.index.array : Array.from({ length: n }, (_, i) => i);
  for (let t = 0; t < idx.length; t += 3) { const a = id[idx[t]], b = id[idx[t + 1]], c = id[idx[t + 2]]; nb[a].add(b).add(c); nb[b].add(a).add(c); nb[c].add(a).add(b); }
  for (let it = 0; it < 24; it++) for (const lam of [0.6, -0.63]) {
    const Q = Pp.slice();
    for (let w = 0; w < m; w++) { if (!body[w]) continue; let x = 0, y = 0, z = 0, c = 0;
      for (const q of nb[w]) { x += Pp[q * 3]; y += Pp[q * 3 + 1]; z += Pp[q * 3 + 2]; c++; }
      if (!c) continue; Q[w * 3] += lam * (x / c - Pp[w * 3]); Q[w * 3 + 1] += lam * (y / c - Pp[w * 3 + 1]); Q[w * 3 + 2] += lam * (z / c - Pp[w * 3 + 2]); }
    Pp.set(Q);
  }
  const chest = bindPos[idxOf.spine_03], pel = bindPos[idxOf.pelvis];
  for (let w = 0; w < m; w++) {
    if (!body[w]) continue; const nm = bones[bone[w]].name, p3 = new THREE.Vector3(Pp[w * 3], Pp[w * 3 + 1], Pp[w * 3 + 2]);
    if (LIMB[nm] && idxOf[LIMB[nm]] != null) {
      const a = bindPos[bone[w]], b = bindPos[idxOf[LIMB[nm]]], ab = b.clone().sub(a), t = Math.max(0, Math.min(1, p3.clone().sub(a).dot(ab) / ab.lengthSq()));
      const proj = a.clone().addScaledVector(ab, t), k = /^upperarm/.test(nm) ? (fem ? 0.88 : 0.76) : /^lowerarm/.test(nm) ? (fem ? 0.92 : 0.84) : /^thigh/.test(nm) ? (fem ? 0.86 : 0.9) : 0.92;
      p3.sub(proj).multiplyScalar(k).add(proj);
    } else if (/^(spine_03|spine_02|clavicle)/.test(nm)) {
      const kx = fem ? 0.94 : 0.86, kz = fem ? 0.86 : 0.84;
      p3.x = chest.x + (p3.x - chest.x) * kx; p3.z = chest.z + (p3.z - chest.z) * kz;
    } else if (/^(pelvis|spine_01)/.test(nm)) { p3.x = pel.x + (p3.x - pel.x) * (fem ? 0.94 : 0.97); p3.z = pel.z + (p3.z - pel.z) * (fem ? 0.74 : 0.86); }
    Pp[w * 3] = p3.x; Pp[w * 3 + 1] = p3.y; Pp[w * 3 + 2] = p3.z;
  }
  const inv = mesh.bindMatrixInverse;
  for (let i = 0; i < n; i++) { const w = id[i]; if (!body[w]) continue; v.set(Pp[w * 3], Pp[w * 3 + 1], Pp[w * 3 + 2]).applyMatrix4(inv); pos.setXYZ(i, v.x, v.y, v.z); }
  pos.needsUpdate = true;
  // welded face normals (no seams) for the moved vertices
  const N = new Float32Array(m * 3), a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let t = 0; t < idx.length; t += 3) {
    a.fromBufferAttribute(pos, idx[t]); b.fromBufferAttribute(pos, idx[t + 1]); c.fromBufferAttribute(pos, idx[t + 2]);
    const f = b.clone().sub(a).cross(c.clone().sub(a));
    for (const q of [idx[t], idx[t + 1], idx[t + 2]]) { const w = id[q]; N[w * 3] += f.x; N[w * 3 + 1] += f.y; N[w * 3 + 2] += f.z; }
  }
  for (let i = 0; i < n; i++) { const w = id[i]; if (!body[w]) continue; const l = Math.hypot(N[w * 3], N[w * 3 + 1], N[w * 3 + 2]) || 1; nor.setXYZ(i, N[w * 3] / l, N[w * 3 + 1] / l, N[w * 3 + 2] / l); }
  nor.needsUpdate = true;
}

function paintBody(mesh, L) {
  demuscle(mesh, L.sex === 'f');
  const g = mesh.geometry, si = g.attributes.skinIndex, sw = g.attributes.skinWeight, n = si.count, bones = mesh.skeleton.bones, reg = new Float32Array(n);
  for (let i = 0; i < n; i++) { let best = 0, bw = -1; for (let k = 0; k < 4; k++) { const w = sw.getComponent(i, k); if (w > bw) { bw = w; best = si.getComponent(i, k); } }
    reg[i] = regionOf(bones[best].name, L.sleeve === 'long'); }
  g.setAttribute('region', new THREE.BufferAttribute(reg, 1)); smoothCloth(g, reg, 14);
  const skinMul = new THREE.Color(L.skin).lerp(new THREE.Color('#F6D2B6'), 0.72);   // fair tone; detail from the texture's luminance
  const m = mat('#ffffff', mesh.material.map);
  const cols = [skinMul, new THREE.Color(L.top), new THREE.Color(L.bottomType === 'skirt' || L.bottomType === 'shorts' ? L.bottom : L.bottom), new THREE.Color(L.shoes)];
  m.onBeforeCompile = sh => {
    sh.uniforms.regCols = { value: cols };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute float region; varying float vRegion;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvRegion = region;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform vec3 regCols[4]; varying float vRegion;').replace('#include <map_fragment>', `
      int ri = int(vRegion + 0.5); vec3 rc = ri == 0 ? regCols[0] : ri == 1 ? regCols[1] : ri == 2 ? regCols[2] : regCols[3];
      #ifdef USE_MAP
        vec4 tx = texture2D(map, vMapUv); float lu = dot(tx.rgb, vec3(0.3, 0.59, 0.11)) / 0.245; diffuseColor.rgb *= ri == 0 ? rc * clamp(mix(1.0, lu, 0.5), 0.6, 1.12) : rc;
      #else
        diffuseColor.rgb *= rc;
      #endif`);
  };
  m.customProgramCacheKey = () => 'paint3d';
  m.userData.outlineParameters = { thickness: 0.004, color: [0.2, 0.18, 0.17], alpha: 1 };
  mesh.material = m;
}
function attachSkinned(root, part, color) {
  const byName = {}; root.traverse(o => { if (o.isBone) byName[o.name] = o; });
  const c = SkeletonUtils.clone(part.scene), meshes = []; c.traverse(o => { if (o.isSkinnedMesh) meshes.push(o); });
  for (const m of meshes) { m.bind(new THREE.Skeleton(m.skeleton.bones.map(b => byName[b.name] || b), m.skeleton.boneInverses), m.bindMatrix);
    m.material = mat(color); m.frustumCulled = false; root.add(m); }
}
function fitHeight(o, h) {
  o.updateMatrixWorld(true); const b = new THREE.Box3().setFromObject(o, true); o.scale.multiplyScalar(h / (b.max.y - b.min.y));
  o.updateMatrixWorld(true); const b2 = new THREE.Box3().setFromObject(o, true); o.position.y -= b2.min.y;
}

const people = {};
function personOf(name, L, h) {
  const key = name + h.toFixed(2);
  if (people[key]) return people[key];
  const fem = L.sex === 'f', root = SkeletonUtils.clone((fem ? A.ubcF : A.ubcM).scene);
  const meshes = []; root.traverse(o => { if (o.isMesh) meshes.push(o); });
  for (const m of meshes) { m.frustumCulled = false; const nm = m.material.name || '';
    if (/Eye/.test(nm)) { m.material = mat('#ffffff', m.material.map); continue; }
    if (/Hair/.test(nm)) { m.material = mat(L.hair); continue; }
    paintBody(m, L); }
  const hair = { short: ['SimpleParted'], long: ['Long'], bun: ['Buns'], ponytail: ['Long'], curly: ['Buzzed'], bald: [] }[L.hairStyle] || [];
  for (const hn of hair) attachSkinned(root, A.hair[hn], L.hair);
  if (L.beard) attachSkinned(root, A.hair.Beard, L.hair);
  attachSkinned(root, fem ? A.hair.BrowsF : A.hair.Brows, L.hair);
  const holder = new THREE.Group(); holder.add(root); fitHeight(root, h);
  if (L.child) root.traverse(o => { if (o.isBone && o.name === 'Head') o.scale.setScalar(1.25); });
  const mixer = new THREE.AnimationMixer(root), bones = {}; root.traverse(o => { if (o.isBone) bones[o.name] = o; });
  return (people[key] = { holder, root, mixer, bones });
}

export async function install(K) {
  const gl = new GLTFLoader();
  const hairs = ['Hair_SimpleParted', 'Hair_Long', 'Hair_Buns', 'Hair_Buzzed', 'Hair_Beard', 'Eyebrows_Regular', 'Eyebrows_Female'];
  const [m, f, fbx, ual2, ...hs] = await Promise.all([gl.loadAsync('assets/ubc/Superhero_Male_FullBody.gltf'), gl.loadAsync('assets/ubc/Superhero_Female_FullBody.gltf'),
    new FBXLoader().loadAsync('assets/ual/ual1_ue.fbx'), gl.loadAsync('assets/ual/ual2.glb'), ...hairs.map(n => gl.loadAsync(`assets/hair/${n}.gltf`))]);
  A.ubcM = m; A.ubcF = f; A.hair = { SimpleParted: hs[0], Long: hs[1], Buns: hs[2], Buzzed: hs[3], Beard: hs[4], Brows: hs[5], BrowsF: hs[6] };
  A.clips = {}; for (const c of ual2.animations) A.clips[c.name] = c;
  for (const c of fbx.animations) { const k = c.clone(); k.name = c.name.split('|').pop(); k.tracks = k.tracks.filter(t => !t.name.startsWith('root.')); if (!A.clips[k.name]) A.clips[k.name] = k; }
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight('#ffffff', '#cfc6b6', 1.25));
  const sun = new THREE.DirectionalLight('#ffffff', 2.0); sun.position.set(-2, 5, 6); scene.add(sun);
  const cam = new THREE.OrthographicCamera(BOX.x0, BOX.x1, BOX.y1, BOX.y0, 0.1, 50); cam.position.set(0, 0, 10); cam.lookAt(0, 0, 0);
  const cache = new Map();

  K.FIG.toon3d = (p, V, T) => {
    const fr = p.fr || K.sample(p.clip, p.t, p.loop !== false), clip = fr.clip || p.clip, tt = fr.tt != null ? fr.tt : p.t;
    const name = p.cast || Object.keys(K.CAST).find(k => K.CAST[k].top === (p.look && p.look.shirt)) || 'man', L = K.CAST[name];
    const h = p.h || (L.child ? 1.25 : L.sex === 'f' ? 1.66 : 1.78), d = p.dir || 1, pxm = Math.min(320, Math.max(140, V.s));
    const ck = `${name}|${h}|${clip}|${tt.toFixed(3)}|${d}|${pxm}|${T.outline}|${p.ik ? JSON.stringify(p.ik) + p.x + '|' + (p.y || 0) : ''}`;
    let url = cache.get(ck);
    if (!url) {
      const P = personOf(name, L, h);
      P.root.rotation.y = d > 0 ? Math.PI / 2 : -Math.PI / 2;
      P.mixer.stopAllAction(); const c = A.clips[clip];
      if (c) { P.mixer.clipAction(c).play();
        // ground the clip like the 2D bake: its lowest ball over the whole clip sits 0.025 (per metre of height) above the ground
        P.ground = P.ground || {};
        if (P.ground[clip] == null) { let m = 1e9; const v = new THREE.Vector3(); P.holder.position.y = 0;
          for (let i = 0; i <= 16; i++) { P.mixer.setTime(c.duration * 0.999 * i / 16); P.holder.updateMatrixWorld(true);
            for (const b of ['ball_l', 'ball_r']) if (P.bones[b]) { P.bones[b].getWorldPosition(v); m = Math.min(m, v.y); } }
          P.ground[clip] = 0.025 * h - m; }
        P.holder.position.y = P.ground[clip];
        P.mixer.setTime(Math.min(tt, c.duration * 0.999)); }
      P.holder.updateMatrixWorld(true);
      // hands on things: two-bone arm chain solved by CCD towards the scene's target (metres, same frame as the 2D)
      if (p.ik) for (const side of ['_r', '_l']) if (p.ik[side]) {
        const up = P.bones['upperarm' + side], lo = P.bones['lowerarm' + side], hand = P.bones['hand' + side], e = new THREE.Vector3(), bp = new THREE.Vector3();
        hand.getWorldPosition(e);
        const tg = new THREE.Vector3(p.ik[side][0] - p.x, p.ik[side][1] - (p.y || 0), e.z);
        for (let it = 0; it < 12; it++) for (const b of [lo, up]) {
          hand.getWorldPosition(e); b.getWorldPosition(bp);
          const a = e.sub(bp).normalize(), c = tg.clone().sub(bp).normalize();
          if (a.dot(c) > 0.99999) continue;
          const r = new THREE.Quaternion().setFromUnitVectors(a, c), wq = b.getWorldQuaternion(new THREE.Quaternion()), pq = b.parent.getWorldQuaternion(new THREE.Quaternion());
          b.quaternion.copy(pq.invert().multiply(r.multiply(wq))); b.updateMatrixWorld(true);
        }
      }
      scene.add(P.holder);
      renderer.setSize(Math.round((BOX.x1 - BOX.x0) * pxm), Math.round((BOX.y1 - BOX.y0) * pxm), false);
      if (T.outline) outline.render(scene, cam); else renderer.render(scene, cam);
      scene.remove(P.holder);
      url = canvas.toDataURL('image/png');
      if (cache.size > 400) cache.clear();
      cache.set(ck, url);
    }
    const x = V.sx(p.x + BOX.x0), y = V.sy((p.y || 0) + BOX.y1), w = (BOX.x1 - BOX.x0) * V.s, hh = (BOX.y1 - BOX.y0) * V.s;
    const lift = Math.max(0, p.y || 0) * V.s, k = Math.max(0.35, 1 - lift / 600);
    const sh = T.outline || p.noShadow ? '' : `<ellipse cx="${K.F(V.sx(p.x))}" cy="${K.F(V.sy(0))}" rx="${K.F(0.3 * V.s * k)}" ry="${K.F(0.05 * V.s * k)}" fill="rgba(40,50,40,${K.F(0.18 * k)})"/>`;
    return sh + `<image href="${url}" x="${K.F(x)}" y="${K.F(y)}" width="${K.F(w)}" height="${K.F(hh)}"/>`;
  };
}
