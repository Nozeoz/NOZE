// Draws everyone who walks the clearing: visitors, stall keepers, the Sworn at their doors,
// settlers at work by day and gathered at the Heartflame by night, and the Sovereign with Flicker.
import * as THREE from 'three';
import { buildCharacter, variantCount, HEAD } from './characters.js';
import { veilify, HALF } from './veil.js';
import { objectMatrix } from './objects.js';
import { TYPES } from '../sim/catalog.js';
import { P } from './palette.js';

const MOVING = new Set(['arrive', 'toStall', 'stroll', 'leave', 'flee']);

export class AgentRenderer {
  constructor(scene, { shadows = true } = {}) {
    this.scene = scene;
    this.shadows = shadows;
    this.meshes = new Map();
    this.solidMat = veilify(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.75, metalness: 0 }));
    this.glowMat = new THREE.MeshBasicMaterial({ vertexColors: true });
    this.phase = new Map();
    this.figures = [];
    // Flicker: a little crowned flame that floats beside the Sovereign.
    const fg = new THREE.Group();
    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.11, 1), new THREE.MeshBasicMaterial({ color: new THREE.Color(P.heartCream).multiplyScalar(5) }));
    const shell = new THREE.Mesh(new THREE.ConeGeometry(0.13, 0.36, 8).translate(0, 0.1, 0), new THREE.MeshBasicMaterial({ color: new THREE.Color(P.heartflame).multiplyScalar(3.2), transparent: true, opacity: 0.85, depthWrite: false }));
    const crown = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.012, 4, 10).rotateX(Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(P.gold).multiplyScalar(2.2) }));
    crown.position.y = 0.24;
    fg.add(core, shell, crown);
    this.flickerLight = new THREE.PointLight(P.heartflame, 1, 7, 1.6);
    fg.add(this.flickerLight);
    scene.add(fg);
    this.flicker = { group: fg, light: this.flickerLight, shell };
  }

  mesh(key) {
    if (this.meshes.has(key)) return this.meshes.get(key);
    const [kind, variant] = key.split(':');
    const model = buildCharacter(kind, Number(variant));
    const cap = 48;
    const solid = new THREE.InstancedMesh(model.solid, this.solidMat, cap);
    solid.castShadow = this.shadows;
    solid.frustumCulled = false;
    this.scene.add(solid);
    let glow = null;
    if (model.glow) {
      glow = new THREE.InstancedMesh(model.glow, this.glowMat, cap);
      glow.frustumCulled = false;
      this.scene.add(glow);
    }
    const e = { solid, glow, n: 0, cap };
    this.meshes.set(key, e);
    return e;
  }

  // Everyone who should be on screen right now, as {key, x, z, angle, moving, id, head}.
  collect(game) {
    const out = [];
    const day = game.minute % 1440 >= 6 * 60 && game.minute % 1440 < 18 * 60;
    for (const v of game.visitors) {
      if (v.state === 'gone') continue;
      const kind = v.kind;
      out.push({
        key: `${kind}:${v.seed % variantCount(kind)}`, x: v.x - HALF, z: v.z - HALF,
        angle: Math.atan2(v.fx ?? 0, v.fz ?? 1), moving: MOVING.has(v.state), id: `v${v.id}`, seed: v.seed,
        head: HEAD[kind] || 1.05, visitor: v, hop: kind === 'mossbun',
      });
    }
    const local = (o, lx, lz, turn = 0) => {
      const m = objectMatrix(o);
      const p = new THREE.Vector3(lx, 0, lz).applyMatrix4(m);
      return { x: p.x, z: p.z, angle: o.rot * Math.PI / 2 + turn };
    };
    const settlers = game.settlers();
    let idleIndex = 0;
    for (const o of game.objects.values()) {
      const def = TYPES[o.type];
      if (o.type === 'stall') out.push({ key: `villager:${o.id % 4}`, ...local(o, 0.1, -0.12), id: `s${o.id}`, seed: o.id, head: 1.05 });
      if (o.type === 'herbalist') out.push({ key: 'linnea:0', ...local(o, 0.3, 0.28), id: 'linnea', seed: 7, head: 1.05, who: 'linnea' });
      if (o.type === 'lodge') out.push({ key: 'bram:0', ...local(o, 0.55, 1.28, 0.4), id: 'bram', seed: 3, head: 1.05, who: 'bram' });
      if (def.worker && o.worker && day) {
        const spot = o.type === 'fishery' ? [0.55, 0.15] : o.type === 'cookhouse' ? [0.55, 0.85] : [-0.5 + (o.id % 3) * 0.5, 0.1];
        const kind = o.worker === 'Hob' ? 'hob:0' : `villager:${settlers.findIndex(s => s.name === o.worker) % 4}`;
        out.push({ key: kind, ...local(o, spot[0], spot[1], Math.PI * ((o.id % 2) ? 0.5 : -0.3)), id: `w${o.id}`, seed: o.id * 5, head: 1.05, work: true, who: o.worker === 'Hob' ? 'hob' : null });
      }
    }
    // Settlers without work, and everyone after dark, gather around the Heartflame.
    const beacon = game.list(o => o.type === 'beacon')[0];
    for (const s of settlers) {
      if (s.job && day) continue;
      if (!beacon) break;
      const k = idleIndex++;
      const a = k * 2.399 + 0.6;
      const r = 1.9 + (k % 3) * 0.45;
      const x = beacon.x + 1 - HALF + Math.cos(a) * r;
      const z = beacon.z + 1 - HALF + Math.abs(Math.sin(a)) * r * 0.9 + 0.6;
      out.push({ key: s.name === 'Hob' ? 'hob:0' : `villager:${k % 4}`, x, z, angle: Math.atan2(beacon.x + 1 - HALF - x, beacon.z + 1 - HALF - z), id: `r${s.name}`, seed: k * 13, head: 1.05 });
    }
    const p = game.player;
    out.push({ key: 'sovereign:0', x: p.x - HALF, z: p.z - HALF, angle: Math.atan2(p.fx, p.fz), moving: p.moving, id: 'player', seed: 1, head: 1.1 });
    return out;
  }

  update(game, dt, time, night) {
    const figures = this.collect(game);
    this.figures = figures;
    for (const e of this.meshes.values()) e.n = 0;
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const e3 = new THREE.Euler();
    for (const f of figures) {
      const e = this.mesh(f.key);
      if (e.n >= e.cap) continue;
      let ph = this.phase.get(f.id) || f.seed % 7;
      ph += dt * (f.moving ? 10 : 2.2);
      this.phase.set(f.id, ph);
      let y = 0;
      let tilt = 0;
      let sy = 1;
      if (f.moving) {
        y = Math.abs(Math.sin(ph)) * 0.07;
        tilt = Math.sin(ph) * 0.07;
      } else if (f.work) {
        tilt = 0;
        sy = 1 - 0.05 * Math.max(0, Math.sin(ph * 1.3));
        y = 0;
      } else {
        sy = 1 + 0.018 * Math.sin(ph);
        if (f.hop && Math.sin(ph * 0.7) > 0.93) y = 0.08;
      }
      q.setFromEuler(e3.set(0, f.angle, tilt));
      m.compose(new THREE.Vector3(f.x, y, f.z), q, new THREE.Vector3(1, sy, 1));
      e.solid.setMatrixAt(e.n, m);
      if (e.glow) e.glow.setMatrixAt(e.n, m);
      e.n++;
      f.y = y;
    }
    for (const e of this.meshes.values()) {
      e.solid.count = e.n;
      e.solid.instanceMatrix.needsUpdate = true;
      if (e.glow) { e.glow.count = e.n; e.glow.instanceMatrix.needsUpdate = true; }
    }
    this.glowMat.color.setScalar(0.6 + night * 0.8);
    // Flicker bobs at the Sovereign's shoulder.
    const p = game.player;
    const side = Math.atan2(p.fx, p.fz) + 2.2;
    const fx = p.x - HALF + Math.sin(side) * 0.42;
    const fz = p.z - HALF + Math.cos(side) * 0.42;
    const g = this.flicker.group;
    g.position.x += (fx - g.position.x) * Math.min(1, dt * 6);
    g.position.z += (fz - g.position.z) * Math.min(1, dt * 6);
    g.position.y = 1.15 + Math.sin(time * 2.6) * 0.08;
    this.flicker.shell.scale.y = 1 + 0.15 * Math.sin(time * 13) * Math.sin(time * 7.1);
    this.flicker.shell.rotation.y = time * 2;
  }

  // Head positions for speech bubbles and name tags.
  heads() {
    return this.figures.map(f => ({ id: f.id, x: f.x, y: (f.y || 0) + f.head, z: f.z, visitor: f.visitor, who: f.who }));
  }
}
