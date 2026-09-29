// Draws every building and prop as instanced models (one draw call per model and variant),
// pops new ones in with a little bounce, and hands out the world positions of their lights,
// chimney smoke and flames. Also animates flames and smoke, and builds fishing piers.
import * as THREE from 'three';
import { buildModel, modelKey } from './models.js';
import { veilify, HALF } from './veil.js';
import { P } from './palette.js';
import { T, idx, inBounds } from '../sim/world.js';

const easeOutBack = t => { const c1 = 1.9; const c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };

export function objectMatrix(o, scale = 1, target = new THREE.Matrix4()) {
  return target.compose(
    new THREE.Vector3(o.x + o.w / 2 - HALF, 0, o.z + o.d / 2 - HALF),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), o.rot * Math.PI / 2),
    new THREE.Vector3(scale, scale, scale),
  );
}

export class ObjectRenderer {
  constructor(scene, { shadows = true } = {}) {
    this.scene = scene;
    this.shadows = shadows;
    this.models = new Map();
    this.meshes = new Map();
    this.groups = new Map();
    this.solidMat = veilify(new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.82, metalness: 0 }));
    this.glowMat = new THREE.MeshBasicMaterial({ vertexColors: true });
    this.version = -1;
    this.lights = [];
    this.smokeSources = [];
    this.flameSpots = [];
    this.lightsVersion = 0;
    this.born = new Map();
    this.initialised = false;
    this.anim = false;
    this.extras = new THREE.Group();
    scene.add(this.extras);
    this.flames = new Flames(scene);
    this.smoke = new Smoke(scene);
  }

  model(key) {
    if (!this.models.has(key)) {
      const m = buildModel(key);
      this.models.set(key, { solid: m.s.build(), glow: m.g.build(), lights: m.lights, smoke: m.smoke, flames: m.flames });
    }
    return this.models.get(key);
  }

  entry(key, count) {
    let e = this.meshes.get(key);
    if (e && e.cap >= count) return e;
    if (e) {
      this.scene.remove(e.solid);
      if (e.glow) this.scene.remove(e.glow);
      e.solid.dispose();
      if (e.glow) e.glow.dispose();
    }
    const model = this.model(key);
    const cap = Math.max(4, Math.ceil(count * 1.5));
    const solid = new THREE.InstancedMesh(model.solid, this.solidMat, cap);
    solid.castShadow = this.shadows;
    solid.receiveShadow = this.shadows;
    solid.frustumCulled = false;
    this.scene.add(solid);
    let glow = null;
    if (model.glow) {
      glow = new THREE.InstancedMesh(model.glow, this.glowMat, cap);
      glow.frustumCulled = false;
      this.scene.add(glow);
    }
    e = { solid, glow, cap };
    this.meshes.set(key, e);
    return e;
  }

  sync(game, time) {
    if (game.version !== this.version) this.rebuild(game, time);
    else if (this.anim) this.updateMatrices(time);
  }

  rebuild(game, time) {
    this.version = game.version;
    this.groups = new Map();
    const seen = new Set();
    for (const o of game.objects.values()) {
      const key = modelKey(o, game);
      if (!this.groups.has(key)) this.groups.set(key, []);
      this.groups.get(key).push(o);
      seen.add(o.id);
      if (!this.born.has(o.id)) this.born.set(o.id, this.initialised ? time : -10);
    }
    for (const id of [...this.born.keys()]) if (!seen.has(id)) this.born.delete(id);
    this.initialised = true;
    for (const [key, e] of this.meshes) if (!this.groups.has(key)) { e.solid.count = 0; if (e.glow) e.glow.count = 0; }
    for (const [key, list] of this.groups) this.entry(key, list.length);
    // World positions of lights, smoke and flames.
    this.lights = [];
    this.smokeSources = [];
    this.flameSpots = [];
    const v = new THREE.Vector3();
    const m = new THREE.Matrix4();
    for (const [key, list] of this.groups) {
      const model = this.model(key);
      for (const o of list) {
        objectMatrix(o, 1, m);
        for (const L of model.lights) { v.set(L.x, L.y, L.z).applyMatrix4(m); this.lights.push({ x: v.x, y: v.y, z: v.z, r: L.r, main: !!L.main, strong: !!L.strong, id: o.id }); }
        for (const s of model.smoke) { v.set(s.x, s.y, s.z).applyMatrix4(m); this.smokeSources.push({ x: v.x, y: v.y, z: v.z, small: !!s.small }); }
        for (const f of model.flames) { v.set(f.x, f.y, f.z).applyMatrix4(m); this.flameSpots.push({ x: v.x, y: v.y, z: v.z, s: f.s, main: !!f.main }); }
      }
    }
    this.lightsVersion++;
    this.buildPiers(game);
    this.updateMatrices(time);
  }

  updateMatrices(time) {
    let animating = false;
    const m = new THREE.Matrix4();
    for (const [key, list] of this.groups) {
      const e = this.meshes.get(key);
      list.forEach((o, i) => {
        const t = time - (this.born.get(o.id) ?? -10);
        let s = 1;
        if (t < 0.45) { s = Math.max(0.01, easeOutBack(Math.max(0, t / 0.45))); animating = true; }
        objectMatrix(o, s, m);
        e.solid.setMatrixAt(i, m);
        if (e.glow) e.glow.setMatrixAt(i, m);
      });
      e.solid.count = list.length;
      e.solid.instanceMatrix.needsUpdate = true;
      if (e.glow) { e.glow.count = list.length; e.glow.instanceMatrix.needsUpdate = true; }
    }
    this.anim = animating;
  }

  // Fishing Huts get a pier out over the pond and a little boat.
  buildPiers(game) {
    this.extras.clear();
    const wood = veilify(new THREE.MeshStandardMaterial({ color: P.wood, flatShading: true, roughness: 0.9 }));
    const dark = veilify(new THREE.MeshStandardMaterial({ color: P.woodDark, flatShading: true, roughness: 0.9 }));
    for (const o of game.objects.values()) {
      if (o.type !== 'fishery') continue;
      const sides = [[0, 1], [1, 0], [0, -1], [-1, 0]].map(([dx, dz]) => {
        let n = 0;
        for (const [x, z] of game.objTiles(o)) {
          const nx = x + dx;
          const nz = z + dz;
          if (inBounds(nx, nz) && game.terrain[idx(nx, nz)] === T.WATER) n++;
        }
        return { dx, dz, n };
      }).sort((a, b) => b.n - a.n);
      const side = sides[0];
      if (!side.n) continue;
      const g = new THREE.Group();
      const deck = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.06, 1.8), wood);
      deck.position.set(0, 0.1, 0.9);
      g.add(deck);
      for (const z of [0.4, 1.0, 1.6]) for (const x of [-0.25, 0.25]) {
        const post = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.6, 5), dark);
        post.position.set(x, -0.15, z);
        g.add(post);
      }
      const hull = new THREE.Mesh(new THREE.SphereGeometry(0.5, 10, 6, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), dark);
      hull.scale.set(0.55, 0.45, 1.3);
      hull.position.set(0.62, 0.02, 1.25);
      g.add(hull);
      const seat = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.04, 0.1), wood);
      seat.position.set(0.62, 0.0, 1.25);
      g.add(seat);
      g.traverse(c => { c.castShadow = this.shadows; c.receiveShadow = this.shadows; });
      const cx = o.x + o.w / 2 - HALF;
      const cz = o.z + o.d / 2 - HALF;
      g.position.set(cx + side.dx * (o.w / 2), 0, cz + side.dz * (o.d / 2));
      g.rotation.y = Math.atan2(side.dx, side.dz);
      this.extras.add(g);
    }
  }

  update(dt, time, night, windowGlow) {
    this.glowMat.color.setScalar(windowGlow);
    this.flames.update(this.flameSpots, time);
    this.smoke.update(this.smokeSources, dt, night);
  }
}

// Heartflame and cooking fires: three nested cones that flicker.
class Flames {
  constructor(scene) {
    const geo = new THREE.ConeGeometry(0.28, 0.8, 7).translate(0, 0.4, 0);
    this.layers = [
      { color: P.ember, k: 3.2, r: 1, h: 1 },
      { color: P.heartflame, k: 4.2, r: 0.68, h: 0.86 },
      { color: P.heartCream, k: 5.5, r: 0.36, h: 0.62 },
    ].map(L => {
      const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(L.color).multiplyScalar(L.k), transparent: true, opacity: 0.92, depthWrite: false });
      const mesh = new THREE.InstancedMesh(geo, mat, 32);
      mesh.count = 0;
      mesh.frustumCulled = false;
      mesh.renderOrder = 6;
      scene.add(mesh);
      return { ...L, mesh };
    });
  }

  update(spots, time) {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    for (const L of this.layers) {
      spots.forEach((f, i) => {
        const w = 1 + 0.12 * Math.sin(time * 9 + i * 1.7 + L.k) * Math.sin(time * 5.3 + i);
        const h = 1 + 0.22 * Math.sin(time * 11 + i * 2.3 + L.k * 0.7) + 0.08 * Math.sin(time * 23 + i);
        q.setFromEuler(new THREE.Euler(0.06 * Math.sin(time * 7 + i), time * 1.3 * (L.k - 4), 0.06 * Math.cos(time * 6 + i)));
        m.compose(new THREE.Vector3(f.x, f.y, f.z), q, new THREE.Vector3(f.s * L.r * w, f.s * L.h * h, f.s * L.r * w));
        L.mesh.setMatrixAt(i, m);
      });
      L.mesh.count = spots.length;
      L.mesh.instanceMatrix.needsUpdate = true;
    }
  }
}

// Soft puffs from chimneys and cooking pots.
class Smoke {
  constructor(scene) {
    this.max = 420;
    this.puffs = [];
    const geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(this.max * 3);
    this.size = new Float32Array(this.max);
    this.alpha = new Float32Array(this.max);
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(this.size, 1));
    geo.setAttribute('alpha', new THREE.BufferAttribute(this.alpha, 1));
    this.mat = new THREE.ShaderMaterial({
      uniforms: { uColor: { value: new THREE.Color('#C8C2B8') }, uScale: { value: 300 } },
      vertexShader: `attribute float size; attribute float alpha; varying float vA; uniform float uScale;
        void main() { vA = alpha; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * uScale / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 uColor; varying float vA;
        void main() { vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard; gl_FragColor = vec4(uColor, vA * smoothstep(0.5, 0.1, r)); }`,
      transparent: true,
      depthWrite: false,
    });
    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.points.renderOrder = 7;
    scene.add(this.points);
    this.clock = 0;
  }

  update(sources, dt, night) {
    this.clock += dt;
    for (const [i, s] of sources.entries()) {
      s.acc = (s.acc || (i * 0.37) % 0.7) + dt;
      const every = s.small ? 0.9 : 0.55;
      while (s.acc > every) {
        s.acc -= every;
        if (this.puffs.length < this.max) this.puffs.push({ x: s.x + (Math.random() - 0.5) * 0.1, y: s.y, z: s.z + (Math.random() - 0.5) * 0.1, age: 0, life: s.small ? 2.2 : 4.2, grow: s.small ? 0.35 : 0.7 });
      }
    }
    let n = 0;
    this.puffs = this.puffs.filter(p => (p.age += dt) < p.life);
    for (const p of this.puffs) {
      const t = p.age / p.life;
      p.y += dt * 0.42;
      p.x += dt * 0.12;
      this.pos[n * 3] = p.x;
      this.pos[n * 3 + 1] = p.y;
      this.pos[n * 3 + 2] = p.z;
      this.size[n] = 0.25 + p.grow * t;
      this.alpha[n] = Math.sin(Math.PI * Math.min(1, t * 1.2)) * 0.34;
      n++;
    }
    this.points.geometry.setDrawRange(0, n);
    for (const a of ['position', 'size', 'alpha']) this.points.geometry.attributes[a].needsUpdate = true;
    this.mat.uniforms.uColor.value.set(night > 0.5 ? '#5C6078' : '#CFC9BF');
  }
}
