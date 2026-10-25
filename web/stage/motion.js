// The motion pack (F-017 §4): CC0 mocap baked to 2D joints (data/motion.json, 1 m tall, facing +x, feet on the
// ground) and the clip table (config/stage_clips.json). The same sampling as copilot.stage.motion, so a socket Python
// computes is where the stage draws it.
let M = null, JI = {}, CLIPS = {};

export async function loadMotion(motionUrl, clipsUrl) {
  const [m, c] = await Promise.all([fetch(motionUrl).then((r) => r.json()), fetch(clipsUrl).then((r) => r.json())]);
  M = m; JI = Object.fromEntries(m.joints.map((j, i) => [j, i]));
  CLIPS = Object.fromEntries(c.clips.map((r) => [r.name, r]));
  for (const r of Object.values(CLIPS)) if (r.contact) r.code = { l: [...r.contact.l].map(Number), r: [...r.contact.r].map(Number) };
}
export const joints = () => JI;
export const clip = (name) => CLIPS[name];
export const clipNames = () => Object.keys(M.clips);
export const hasClip = (name) => !!(M && M.clips[name]);
export const duration = (name) => M.clips[name].dur;

// the pose at clip time t: frames lerped; mirror flips x (a push played mirrored leans back: a pull)
export function sample(name, t, loop = true, mirror = false) {
  const c = M.clips[name], n = c.frames.length;
  const tt = loop ? ((t % c.dur) + c.dur) % c.dur : Math.max(0, Math.min(t, c.dur * 0.999));
  const u = (tt / c.dur) * (loop ? n : n - 1), i = Math.floor(u), k = u - i;
  const a = c.frames[i % n], b = c.frames[loop ? (i + 1) % n : Math.min(i + 1, n - 1)];
  const s = mirror ? -1 : 1;
  const out = a.map((p, q) => [s * (p[0] + (b[q][0] - p[0]) * k), p[1] + (b[q][1] - p[1]) * k, p[2] + (b[q][2] - p[2]) * k]);
  out.u = u % n; out.n = n; out.clip = name; out.mirror = mirror;  // frame position, for the foot lock
  return out;
}

// the foot lock's x shift (per m of height) at a sampled frame: keeps a planted foot still at stride speed
export function lockAt(name, fr) {
  const r = CLIPS[name];
  if (!r || !r.lock) return null;
  const i = Math.floor(fr.u), j = (i + 1) % fr.n, k = fr.u - i;
  return { l: r.lock.l[i] + (r.lock.l[j] - r.lock.l[i]) * k, r: r.lock.r[i] + (r.lock.r[j] - r.lock.r[i]) * k,
    cl: r.code.l[Math.round(fr.u) % fr.n], cr: r.code.r[Math.round(fr.u) % fr.n] };
}

// stride speed in m/s for a person h metres tall (rate 1)
export const strideSpeed = (name, h) => ((CLIPS[name] && CLIPS[name].stride_mps) || 0) * h;

export function blend(a, b, k) {
  const out = a.map((p, q) => [p[0] + (b[q][0] - p[0]) * k, p[1] + (b[q][1] - p[1]) * k, p[2] + (b[q][2] - p[2]) * k]);
  out.u = b.u; out.n = b.n; out.clip = b.clip; out.mirror = b.mirror;
  return out;
}
