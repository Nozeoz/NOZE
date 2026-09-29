// Time of day: sky, sun and moon, fog, lamp light pools, and a pool of real point lights that
// follows the camera so nearby walls and faces catch the lantern glow (docs/08 §7).
import * as THREE from 'three';
import { P } from './palette.js';

const KEYS = [
  { m: 0, sky: '#18214C', ground: '#0B1020', hemi: 0.5, sun: '#93A8FF', sunI: 0.55, fog: '#111A33', fogD: 0.02 },
  { m: 280, sky: '#18214C', ground: '#0B1020', hemi: 0.5, sun: '#93A8FF', sunI: 0.55, fog: '#111A33', fogD: 0.02 },
  { m: 350, sky: '#E7A6B0', ground: '#5A4A48', hemi: 0.95, sun: '#FFB38A', sunI: 1.3, fog: '#C9A0A8', fogD: 0.014 },
  { m: 430, sky: '#D6ECF5', ground: '#8C9A62', hemi: 1.35, sun: '#FFF0D8', sunI: 2.9, fog: '#BCD4CE', fogD: 0.009 },
  { m: 960, sky: '#D6ECF5', ground: '#8C9A62', hemi: 1.35, sun: '#FFF0D8', sunI: 2.9, fog: '#BCD4CE', fogD: 0.009 },
  { m: 1050, sky: '#F2A874', ground: '#6A4A5A', hemi: 1.0, sun: '#FF9A55', sunI: 1.8, fog: '#CF8E7C', fogD: 0.012 },
  { m: 1130, sky: '#3A3474', ground: '#1A1830', hemi: 0.6, sun: '#A08CFF', sunI: 0.65, fog: '#221F4A', fogD: 0.017 },
  { m: 1200, sky: '#18214C', ground: '#0B1020', hemi: 0.5, sun: '#93A8FF', sunI: 0.55, fog: '#111A33', fogD: 0.02 },
  { m: 1440, sky: '#18214C', ground: '#0B1020', hemi: 0.5, sun: '#93A8FF', sunI: 0.55, fog: '#111A33', fogD: 0.02 },
];
const cache = new Map();
const col = hex => { if (!cache.has(hex)) cache.set(hex, new THREE.Color(hex)); return cache.get(hex); };

export function skyAt(minute) {
  const m = ((minute % 1440) + 1440) % 1440;
  let i = 0;
  while (i < KEYS.length - 2 && KEYS[i + 1].m <= m) i++;
  const a = KEYS[i];
  const b = KEYS[i + 1];
  const t = Math.max(0, Math.min(1, (m - a.m) / Math.max(1, b.m - a.m)));
  const mix = (x, y) => x + (y - x) * t;
  return {
    sky: col(a.sky).clone().lerp(col(b.sky), t),
    ground: col(a.ground).clone().lerp(col(b.ground), t),
    sun: col(a.sun).clone().lerp(col(b.sun), t),
    fog: col(a.fog).clone().lerp(col(b.fog), t),
    hemi: mix(a.hemi, b.hemi), sunI: mix(a.sunI, b.sunI), fogD: mix(a.fogD, b.fogD),
  };
}

function radialTexture() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 128;
  const g = cv.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.35, 'rgba(255,255,255,0.55)');
  grad.addColorStop(0.7, 'rgba(255,255,255,0.14)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export class Lighting {
  constructor(scene, { shadows = true, shadowSize = 2048, pool = 8 } = {}) {
    this.scene = scene;
    this.hemi = new THREE.HemisphereLight('#ffffff', '#445533', 1);
    scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight('#ffffff', 2);
    this.sun.castShadow = shadows;
    if (shadows) {
      this.sun.shadow.mapSize.set(shadowSize, shadowSize);
      const cam = this.sun.shadow.camera;
      cam.left = -26; cam.right = 26; cam.top = 26; cam.bottom = -26; cam.near = 1; cam.far = 120;
      this.sun.shadow.bias = -0.0004;
      this.sun.shadow.normalBias = 0.03;
    }
    scene.add(this.sun);
    scene.add(this.sun.target);
    scene.fog = new THREE.FogExp2('#111A33', 0.02);
    scene.background = new THREE.Color('#111A33');
    this.points = [];
    for (let i = 0; i < pool; i++) {
      const pl = new THREE.PointLight(P.window, 0, 6, 1.7);
      pl.position.set(0, -50, 0);
      scene.add(pl);
      this.points.push(pl);
    }
    this.poolTex = radialTexture();
    this.pools = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({
      map: this.poolTex, color: '#FFB35C', transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: 0,
    }), 400);
    this.pools.count = 0;
    this.pools.renderOrder = 4;
    this.pools.frustumCulled = false;
    scene.add(this.pools);
    this.assignTimer = 0;
    this.lightsVersion = -1;
  }

  update({ minute, night, target, lights, lightsVersion, dt, flicker }) {
    const s = skyAt(minute);
    this.hemi.color.copy(s.sky);
    this.hemi.groundColor.copy(s.ground);
    this.hemi.intensity = s.hemi;
    this.sun.color.copy(s.sun);
    this.sun.intensity = s.sunI;
    this.scene.fog.color.copy(s.fog);
    this.scene.fog.density = s.fogD;
    this.scene.background.copy(s.fog);
    // Sun from the south-east in the morning to the south-west at dusk; the moon rides high at night.
    const m = ((minute % 1440) + 1440) % 1440;
    let az;
    let el;
    if (m >= 330 && m <= 1140) {
      const t = (m - 330) / (1140 - 330);
      az = THREE.MathUtils.degToRad(15 + 150 * t);
      el = THREE.MathUtils.degToRad(12 + 50 * Math.sin(Math.PI * t));
    } else {
      az = THREE.MathUtils.degToRad(125);
      el = THREE.MathUtils.degToRad(52);
    }
    const tx = Math.round(target.x);
    const tz = Math.round(target.z);
    this.sun.position.set(tx + Math.cos(az) * Math.cos(el) * 50, Math.sin(el) * 50, tz + Math.sin(az) * Math.cos(el) * 50);
    this.sun.target.position.set(tx, 0, tz);
    // Light pools on the ground under every lamp, window and brazier.
    if (lightsVersion !== this.lightsVersion) {
      this.lightsVersion = lightsVersion;
      const mat = new THREE.Matrix4();
      const n = Math.min(lights.length, 400);
      for (let i = 0; i < n; i++) {
        const L = lights[i];
        const size = L.r * (L.strong ? 1.75 : 1.6);
        mat.compose(new THREE.Vector3(L.x, 0.05 + (i % 7) * 0.002, L.z), new THREE.Quaternion(), new THREE.Vector3(size, 1, size));
        this.pools.setMatrixAt(i, mat);
      }
      this.pools.count = n;
      this.pools.instanceMatrix.needsUpdate = true;
    }
    this.pools.material.opacity = 0.3 * night;
    // Real point lights for the closest sources.
    this.assignTimer -= dt;
    if (this.assignTimer <= 0) {
      this.assignTimer = 0.3;
      const ranked = lights
        .map(L => ({ L, d: Math.hypot(L.x - target.x, L.z - target.z) - (L.strong ? 12 : 0) - (L.main ? 1.5 : 0) }))
        .sort((a, b) => a.d - b.d);
      this.assigned = ranked.slice(0, this.points.length).map(r => r.L);
    }
    const flick = 0.92 + 0.08 * Math.sin(performance.now() * 0.013) * Math.sin(performance.now() * 0.0071);
    this.points.forEach((pl, i) => {
      const L = this.assigned && this.assigned[i];
      if (!L || night < 0.02) { pl.intensity = 0; return; }
      pl.position.set(L.x, Math.max(L.y, 0.9), L.z);
      pl.distance = L.r * (L.strong ? 2.2 : 1.9);
      pl.intensity = night * (L.strong ? 14 * flick : 2.3 * L.r);
    });
    if (flicker) {
      flicker.light.intensity = 0.8 + night * 7 * flick;
    }
  }
}
