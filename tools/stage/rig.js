// Motion source for the 2D samples: the CC0 Quaternius mannequin + Universal Animation Library 1+2 clips, used only
// to read joint positions. Output per clip: frames of [x, y, z] per joint, metres, person 1.0 m tall (scaled when drawn),
// facing +X, feet on the ground (y = 0 at the clip's lowest foot), z > 0 = the near side (the right side).
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';

export const JOINTS = ['pelvis', 'spine_02', 'spine_03', 'neck_01', 'Head', 'clavicle_l', 'upperarm_l', 'lowerarm_l',
  'hand_l', 'middle_01_l', 'clavicle_r', 'upperarm_r', 'lowerarm_r', 'hand_r', 'middle_01_r', 'thigh_l', 'calf_l',
  'foot_l', 'ball_l', 'thigh_r', 'calf_r', 'foot_r', 'ball_r'];

export async function bakeAll(fps = 24) {
  const [man, fbx] = await Promise.all([new GLTFLoader().loadAsync('assets/ual/ual2.glb'),
    new FBXLoader().loadAsync('assets/ual/ual1_ue.fbx')]);
  const clips = {};
  for (const c of man.animations) clips[c.name] = c;
  for (const c of fbx.animations) {
    const k = c.clone(); k.name = c.name.split('|').pop(); k.tracks = k.tracks.filter(t => !t.name.startsWith('root.'));
    if (!clips[k.name]) clips[k.name] = k;
  }
  const root = man.scene; root.rotation.y = Math.PI / 2; root.updateMatrixWorld(true);
  const bones = {}; const names = []; root.traverse(o => { if (o.isBone) { bones[o.name] = o; names.push(o.name); } });
  const rest = new THREE.Box3().setFromObject(root, true), k = 1 / (rest.max.y - rest.min.y);
  const mixer = new THREE.AnimationMixer(root), v = new THREE.Vector3(), out = {};
  for (const [name, clip] of Object.entries(clips)) {
    mixer.stopAllAction(); mixer.uncacheRoot(root);
    const a = mixer.clipAction(clip); a.play();
    const n = Math.max(2, Math.round(clip.duration * fps)), frames = [];
    let ground = Infinity;
    for (let i = 0; i < n; i++) {
      mixer.setTime((i / n) * clip.duration); root.updateMatrixWorld(true);
      const f = JOINTS.map(j => { bones[j].getWorldPosition(v); return [v.x * k, v.y * k, v.z * k]; });
      ground = Math.min(ground, f[JOINTS.indexOf('ball_l')][1], f[JOINTS.indexOf('ball_r')][1]);
      frames.push(f);
    }
    const r = x => Math.round(x * 1000) / 1000;
    out[name] = { dur: r(clip.duration), frames: frames.map(f => f.map(p => [r(p[0]), r(p[1] - ground + 0.025), r(p[2])])) };
  }
  return { joints: JOINTS, fps, bones: names, clips: out };
}
