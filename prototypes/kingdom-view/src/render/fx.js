// Small effects: tips to click, fireflies, sparkle bursts, and fireworks for a new rank.
import * as THREE from 'three';
import { P } from './palette.js';
import { HALF } from './veil.js';

function pointsMaterial(additive = true) {
  return new THREE.ShaderMaterial({
    uniforms: { uScale: { value: 1000 } },
    vertexShader: `attribute float size; attribute vec3 tint; attribute float alpha; varying vec3 vTint; varying float vA; uniform float uScale;
      void main() { vTint = tint; vA = alpha; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * uScale / -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `varying vec3 vTint; varying float vA;
      void main() { vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard; float core = smoothstep(0.5, 0.0, r); gl_FragColor = vec4(vTint * (0.6 + core * 1.8), vA * core); }`,
    transparent: true,
    depthWrite: false,
    blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
  });
}

class PointPool {
  constructor(scene, max, additive = true) {
    this.max = max;
    this.items = [];
    const geo = new THREE.BufferGeometry();
    this.pos = new Float32Array(max * 3);
    this.size = new Float32Array(max);
    this.tint = new Float32Array(max * 3);
    this.alpha = new Float32Array(max);
    geo.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(this.size, 1));
    geo.setAttribute('tint', new THREE.BufferAttribute(this.tint, 3));
    geo.setAttribute('alpha', new THREE.BufferAttribute(this.alpha, 1));
    this.mat = pointsMaterial(additive);
    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.points.renderOrder = 8;
    scene.add(this.points);
  }

  write(list) {
    const n = Math.min(list.length, this.max);
    for (let i = 0; i < n; i++) {
      const p = list[i];
      this.pos[i * 3] = p.x; this.pos[i * 3 + 1] = p.y; this.pos[i * 3 + 2] = p.z;
      this.size[i] = p.size;
      this.tint[i * 3] = p.c.r; this.tint[i * 3 + 1] = p.c.g; this.tint[i * 3 + 2] = p.c.b;
      this.alpha[i] = p.a;
    }
    this.points.geometry.setDrawRange(0, n);
    for (const a of ['position', 'size', 'tint', 'alpha']) this.points.geometry.attributes[a].needsUpdate = true;
  }
}

export class Effects {
  constructor(scene, game) {
    this.scene = scene;
    // Tips: a spinning gold coin inside a soft ring of light.
    this.coins = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.15, 0.15, 0.035, 14).rotateX(Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(P.heartflame).multiplyScalar(2.4) }), 64);
    this.rings = new THREE.InstancedMesh(new THREE.TorusGeometry(0.34, 0.025, 5, 24).rotateX(Math.PI / 2), new THREE.MeshBasicMaterial({ color: new THREE.Color(P.heartCream).multiplyScalar(2.2), transparent: true, opacity: 0.8, depthWrite: false }), 64);
    for (const mesh of [this.coins, this.rings]) { mesh.count = 0; mesh.frustumCulled = false; scene.add(mesh); }
    // Fireflies drift along the forest edge and over the pond.
    this.flies = new PointPool(scene, 160);
    this.flyData = [];
    const rand = (a, b) => a + Math.random() * (b - a);
    for (let i = 0; i < 160; i++) {
      let x;
      let z;
      for (let tries = 0; tries < 30; tries++) {
        x = Math.floor(rand(4, 40));
        z = Math.floor(rand(4, 40));
        const t = game.terrain[z * 44 + x];
        if (t === 1 || t === 2) break;
      }
      this.flyData.push({ x: x + rand(0, 1) - HALF, z: z + rand(0, 1) - HALF, y: rand(0.4, 2.2), ph: rand(0, 20), sp: rand(0.3, 0.8) });
    }
    this.sparks = new PointPool(scene, 500);
    this.sparkList = [];
    this.fireworks = [];
    this.gold = new THREE.Color(P.heartflame);
  }

  burst(x, y, z, { color = P.heartflame, n = 14, speed = 1.6, size = 0.12, life = 0.9, up = 1.2 } = {}) {
    const c = new THREE.Color(color);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = speed * (0.4 + Math.random() * 0.6);
      this.sparkList.push({ x, y, z, vx: Math.cos(a) * s, vy: up * (0.5 + Math.random()), vz: Math.sin(a) * s, life, age: 0, size: size * (0.6 + Math.random() * 0.8), c, g: 2.5 });
    }
  }

  celebrate(cx, cz) {
    for (let k = 0; k < 9; k++) {
      this.fireworks.push({ x: cx + (Math.random() - 0.5) * 12, z: cz + (Math.random() - 0.5) * 10, y: 0.5, vy: 9 + Math.random() * 3, t: -k * 0.45, fuse: 0.9 + Math.random() * 0.4, color: [P.heartflame, P.lotus, P.veilB, '#9FE07A', P.heartCream][k % 5] });
    }
  }

  update(game, dt, time, night) {
    // Tips
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    game.tips.forEach((t, i) => {
      const bob = Math.sin(time * 3 + t.id) * 0.06;
      m.compose(new THREE.Vector3(t.x - HALF, 0.55 + bob, t.z - HALF), q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), time * 2.4 + t.id), new THREE.Vector3(1, 1, 1));
      this.coins.setMatrixAt(i, m);
      const s = 1 + 0.12 * Math.sin(time * 4 + t.id);
      m.compose(new THREE.Vector3(t.x - HALF, 0.1, t.z - HALF), q.identity(), new THREE.Vector3(s, 1, s));
      this.rings.setMatrixAt(i, m);
    });
    this.coins.count = this.rings.count = Math.min(64, game.tips.length);
    this.coins.instanceMatrix.needsUpdate = this.rings.instanceMatrix.needsUpdate = true;
    // Fireflies
    const flies = [];
    if (night > 0.05) {
      const c = new THREE.Color('#F5E27A');
      for (const f of this.flyData) {
        const blink = Math.max(0, Math.sin(time * f.sp * 3 + f.ph));
        flies.push({ x: f.x + Math.sin(time * f.sp + f.ph) * 0.6, y: f.y + Math.sin(time * f.sp * 1.7 + f.ph) * 0.3, z: f.z + Math.cos(time * f.sp * 0.8 + f.ph) * 0.6, size: 0.09, c, a: night * blink * 0.9 });
      }
    }
    this.flies.write(flies);
    // Sparks and fireworks
    for (const fw of this.fireworks) {
      fw.t += dt;
      if (fw.t < 0) continue;
      if (fw.t < fw.fuse) {
        fw.y += fw.vy * dt;
        fw.vy -= 6 * dt;
        this.sparkList.push({ x: fw.x, y: fw.y, z: fw.z, vx: 0, vy: -0.3, vz: 0, life: 0.35, age: 0, size: 0.1, c: new THREE.Color(P.heartCream), g: 0 });
      } else if (!fw.done) {
        fw.done = true;
        this.burst(fw.x, fw.y, fw.z, { color: fw.color, n: 70, speed: 4.2, size: 0.2, life: 1.8, up: 0.8 });
      }
    }
    this.fireworks = this.fireworks.filter(f => !f.done || f.t < f.fuse + 2);
    this.sparkList = this.sparkList.filter(p => (p.age += dt) < p.life);
    const out = [];
    for (const p of this.sparkList) {
      p.vy -= p.g * dt;
      p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      p.vx *= 0.96; p.vz *= 0.96;
      out.push({ x: p.x, y: p.y, z: p.z, size: p.size, c: p.c, a: 1 - p.age / p.life });
    }
    this.sparks.write(out);
  }

  setScale(px) {
    this.flies.mat.uniforms.uScale.value = px;
    this.sparks.mat.uniforms.uScale.value = px;
  }
}
